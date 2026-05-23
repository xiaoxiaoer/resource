"""
BEM 登录模块 — Playwright 自动化登录智泊云/智汇云后台

流程：
1. 登录平台管理方 (bemaomp) → 账号+密码+验证码
2. 导航到车场管理 → 模拟登录到 POMP (bemmgr)
3. POMP 页面用于数据抓取（报表 API）
"""

import asyncio
import json
import os
import re
import time
from urllib.parse import urlencode

import ddddocr
from dotenv import load_dotenv
from playwright.async_api import Page, BrowserContext, async_playwright

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '.env'))

BEM_URL = os.getenv('BEM_BASE_URL', 'https://bemaomp.yidianting.xin')
BEM_USER = os.getenv('BEM_USERNAME')
BEM_PASS = os.getenv('BEM_PASSWORD')

MAX_CAPTCHA_RETRIES = 10
_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = ddddocr.DdddOcr(show_ad=False)
    return _ocr


def _solve_captcha(image_bytes: bytes) -> str:
    ocr = _get_ocr()
    code = ocr.classification(image_bytes)
    code = re.sub(r'[^a-zA-Z0-9]', '', code)
    return code[:4].strip()


async def _switch_to_account_login(page: Page) -> bool:
    toggle = await page.query_selector('.toggle_icon.qr_code')
    if toggle:
        await toggle.click()
        await page.wait_for_timeout(1500)
        return True
    account_input = await page.query_selector('input[placeholder*="账号"]')
    return account_input is not None


async def _fetch_captcha_image(page: Page) -> bytes | None:
    ts = int(time.time() * 1000)
    captcha_url = f'/aomp/getValidateCode.do?id={ts}'

    event = asyncio.Event()
    captcha_bytes = [None]

    async def handle_response(response):
        if 'getValidateCode' in response.url:
            captcha_bytes[0] = await response.body()
            event.set()

    page.on('response', handle_response)
    await page.evaluate("""(url) => fetch(url, {credentials: 'include'})""", captcha_url)
    try:
        await asyncio.wait_for(event.wait(), timeout=10)
    except asyncio.TimeoutError:
        pass
    page.remove_listener('response', handle_response)
    return captcha_bytes[0]


async def _do_login(page: Page, captcha_code: str) -> bool:
    await page.evaluate("""(creds) => {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const inputs = document.querySelectorAll('input');
        for (const inp of inputs) {
            const ph = inp.placeholder || '';
            if (ph.includes('账号') || ph.includes('用户')) {
                setter.call(inp, creds.user);
                inp.dispatchEvent(new Event('input', { bubbles: true }));
            } else if (ph.includes('密码')) {
                setter.call(inp, creds.pwd);
                inp.dispatchEvent(new Event('input', { bubbles: true }));
            } else if (ph.includes('验证码')) {
                setter.call(inp, creds.code);
                inp.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    }""", {'user': BEM_USER, 'pwd': BEM_PASS, 'code': captcha_code})

    await page.wait_for_timeout(500)

    await page.evaluate("""() => {
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            if (btn.textContent?.trim() === '登录') { btn.click(); return; }
        }
    }""")

    try:
        await page.wait_for_url(lambda url: '/#/login' not in url, timeout=5000)
        return True
    except Exception:
        return False


async def login_bem(headless: bool = True) -> tuple[Page, BrowserContext]:
    """
    登录 BEM 平台管理方，返回已认证的 page 和 context。

    Returns:
        (page, context) — 平台管理方的 page，可用于模拟登录到 POMP
    """
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=headless)
    context = await browser.new_context(viewport={'width': 1280, 'height': 900})
    page = await context.new_page()

    await page.goto(f'{BEM_URL}/#/login', wait_until='networkidle')
    await page.wait_for_timeout(2000)

    switched = await _switch_to_account_login(page)
    if not switched:
        raise RuntimeError('无法切换到账号登录模式')

    for attempt in range(MAX_CAPTCHA_RETRIES):
        captcha_img = await _fetch_captcha_image(page)
        if not captcha_img:
            if attempt < MAX_CAPTCHA_RETRIES - 1:
                await page.wait_for_timeout(1000)
                continue
            raise RuntimeError(f'无法获取验证码图片（已尝试 {attempt + 1} 次）')

        captcha_code = _solve_captcha(captcha_img)
        success = await _do_login(page, captcha_code)

        if success:
            page._bem_pw = pw
            page._bem_browser = browser
            return page, context

        if attempt < MAX_CAPTCHA_RETRIES - 1:
            await page.wait_for_timeout(1500)

    raise RuntimeError(f'登录失败，已重试 {MAX_CAPTCHA_RETRIES} 次')


async def simulate_login_pomp(
    page: Page,
    car_park_id: str | None = None,
    car_park_name: str | None = None,
) -> tuple[Page, dict]:
    """
    从平台管理方模拟登录到 POMP 车场后台。

    先通过 AOMP API 查询指定车场（按 parkCode 或 parkName），获取 parkId 等信息。
    然后导航到车场管理页面，搜索并点击模拟登录。

    Args:
        page: 已登录的平台管理方 page
        car_park_id: 停车场编号/车场编码（如 2KR98AUK）
        car_park_name: 停车场名称（如 "一点科技飞机场测试"）

    Returns:
        (pomp_page, park_info) — POMP 页面和车场信息（含 id, name, code, manager）
    """
    context = page.context

    # 1. 通过 AOMP API 获取车场信息
    park_info = await aomp_query_park(page, park_code=car_park_id, park_name=car_park_name)
    if not park_info:
        raise RuntimeError(f'未找到车场（编号={car_park_id}，名称={car_park_name}）')

    # 2. 导航到车场管理页面，搜索指定车场并模拟登录
    await page.goto(f'{BEM_URL}/#/park/manage', wait_until='networkidle')
    await page.wait_for_timeout(5000)

    search_code = park_info.get('code') or car_park_id
    if search_code:
        code_input = page.locator('.el-form-item').filter(has_text='停车场编号').locator('input')
        if await code_input.count() > 0:
            await code_input.first.fill(search_code)
            await page.wait_for_timeout(500)
            await page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.textContent?.includes('搜')) { b.click(); return; }
                }
            }""")
            await page.wait_for_timeout(3000)

    # 点击第一行的模拟登录按钮
    await page.evaluate("""() => {
        const btns = document.querySelectorAll('.vxe-table--body-wrapper button');
        for (const btn of btns) {
            if (btn.textContent?.includes('模拟登录')) { btn.click(); return; }
        }
    }""")

    # 等待 POMP 页面打开
    pomp_page = None
    for _ in range(30):
        await page.wait_for_timeout(500)
        for p in context.pages:
            if 'bemmgr' in p.url:
                pomp_page = p
                break
        if pomp_page:
            break

    if not pomp_page:
        raise RuntimeError('模拟登录未打开 POMP 页面')

    await pomp_page.wait_for_load_state('networkidle')
    await pomp_page.wait_for_timeout(3000)

    pomp_page._bem_pw = getattr(page, '_bem_pw', None)
    pomp_page._bem_browser = getattr(page, '_bem_browser', None)

    return pomp_page, park_info


# --- AOMP API 调用 ---

def _format_park_info(row: dict) -> dict:
    """格式化单条车场信息"""
    return {
        'id': str(row.get('parkId', row.get('id', ''))),
        'name': row.get('parkName', row.get('name', '')),
        'code': row.get('parkCode', row.get('code', '')),
        'type': row.get('parkSystemTypeDesc', ''),
        'manager': row.get('operatorName', '').strip(),
    }


async def aomp_query_park(page: Page, park_code: str | None = None, park_name: str | None = None) -> dict | None:
    """
    通过 AOMP API 查询指定车场信息。

    API: POST /aomp/parkinglot-info/pageQueryParkingLotRecord
    请求体: {"page":1,"rows":20,"parkCode":"xxx","parkName":"xxx"}

    Returns:
        车场信息 dict（含 id, name, code, manager）。
        精确匹配时返回单个车场，无精确匹配时附带 candidates 列表和 exact_match=False。
        未找到返回 None。
    """
    body = {'page': 1, 'rows': 20}
    if park_code:
        body['parkCode'] = park_code
    if park_name:
        body['parkName'] = park_name

    result = await page.evaluate("""async (req) => {
        try {
            const resp = await fetch(req.url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(req.body),
                credentials: 'include',
            });
            const text = await resp.text();
            try {
                return { status: resp.status, data: JSON.parse(text) };
            } catch {
                return { status: resp.status, data: text };
            }
        } catch (e) {
            return { status: 0, error: e.message };
        }
    }""", {'url': f'{BEM_URL}/aomp/parkinglot-info/pageQueryParkingLotRecord', 'body': body})

    if result.get('status') != 200:
        return None

    data = result.get('data', {})
    # 返回结构: {"success": true, "data": {"total": N, "list": [...]}}
    rows = []
    if isinstance(data, dict):
        inner = data.get('data', {})
        if isinstance(inner, dict):
            rows = inner.get('list', [])
        elif isinstance(inner, list):
            rows = inner
    elif isinstance(data, list):
        rows = data

    if not rows:
        return None

    # 只有一个结果，直接返回
    if len(rows) == 1:
        return _format_park_info(rows[0])

    # 多个结果：优先精确匹配 parkCode
    if park_code:
        for row in rows:
            if row.get('parkCode') == park_code:
                return _format_park_info(row)

    # 优先精确匹配 parkName
    if park_name:
        name_trimmed = park_name.strip()
        for row in rows:
            if (row.get('parkName') or '').strip() == name_trimmed:
                return _format_park_info(row)

    # 无精确匹配：返回所有候选，标记 exact_match=False
    info = _format_park_info(rows[0])
    info['exact_match'] = False
    info['candidates'] = [_format_park_info(r) for r in rows]
    return info


# --- POMP API 调用 ---

async def pomp_api_get(page: Page, path: str, params: dict | None = None) -> dict:
    """在 POMP 页面中发起 GET API 请求"""
    result = await page.evaluate("""async (req) => {
        try {
            let url = req.path;
            if (req.params) {
                const qs = Object.entries(req.params)
                    .map(([k, v]) => k + '=' + encodeURIComponent(v))
                    .join('&');
                url += '?' + qs;
            }
            const resp = await fetch(url, { credentials: 'include' });
            const text = await resp.text();
            try {
                return { status: resp.status, data: JSON.parse(text) };
            } catch {
                return { status: resp.status, data: text };
            }
        } catch (e) {
            return { status: 0, error: e.message };
        }
    }""", {'path': path, 'params': params})
    return result


async def pomp_api_post(page: Page, path: str, data: dict | None = None) -> dict:
    """在 POMP 页面中发起 POST API 请求"""
    body = urlencode(data) if data else ''
    result = await page.evaluate("""async (req) => {
        try {
            const resp = await fetch(req.url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: req.body,
                credentials: 'include',
            });
            const text = await resp.text();
            try {
                return { status: resp.status, data: JSON.parse(text) };
            } catch {
                return { status: resp.status, data: text };
            }
        } catch (e) {
            return { status: 0, error: e.message };
        }
    }""", {'url': path, 'body': body})
    return result


async def get_park_list(page: Page) -> list[dict]:
    """获取 POMP 中的停车场列表"""
    result = await pomp_api_get(page, '/mgr/commonFun/queryAllPark.do')
    if result.get('status') == 200 and isinstance(result.get('data'), list):
        return result['data']
    return []


async def fetch_temp_charge_report(
    page: Page,
    park_id: str,
    date_start: str,
    date_end: str,
) -> dict:
    """
    获取临停收费报表数据，按月维度返回。

    queryType=1 + timeDim=MONTH → 每月一行，日期在 statDim 字段（如 "2026-05"）。
    """
    params = {
        'page': '1',
        'rp': '500',
        'queryType': '1',
        'query_parkId': park_id,
        'timeDim': 'MONTH',
        'query_chargeDateStart': date_start,
        'query_chargeDateEnd': date_end,
    }
    return await pomp_api_get(page, '/mgr/report/tmp_charge/newPageList.do', params)


async def fetch_monthly_ticket_report(
    page: Page,
    park_id: str,
    date_start: str,
    date_end: str,
) -> dict:
    """
    获取月票收费报表数据，按月维度返回。

    reportDimension=1 → 每月一行，日期在 reportDateStr 字段（如 "2026-05"）。
    """
    params = {
        'page': '1',
        'rp': '500',
        'parkIds': park_id,
        'reportDimension': '1',
        'reportDateFrom': date_start,
        'reportDateTo': date_end,
    }
    return await pomp_api_get(page, '/mgr/monthTicketBillPaymentReport/list', params)


async def fetch_month_ticket_config(page: Page, park_id: str) -> dict:
    """获取月票配置列表（启用的月票套餐）。"""
    params = {
        'page': '1',
        'rp': '100',
        'query_parkId': park_id,
        'query_ticketStatus': '1',
    }
    return await pomp_api_get(page, '/mgr/monthTicketConfig/list.do', params)


async def cleanup(page: Page) -> None:
    """清理资源"""
    browser = getattr(page, '_bem_browser', None)
    pw = getattr(page, '_bem_pw', None)
    if browser:
        await browser.close()
    if pw:
        await pw.stop()
