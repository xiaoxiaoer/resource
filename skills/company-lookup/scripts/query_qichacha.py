"""
企业信息查询脚本 — 启信宝 (qixin.com) 免费公开信息爬取

根据公司名称查询启信宝，获取参保人数、经营状态等企业信息。

使用方式：
    python3 query_qichacha.py --company "公司名称"
"""

import argparse
import asyncio
import json
import re
import sys
import urllib.parse

from playwright.async_api import async_playwright

from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))


async def _search_qixin(page, company_name: str) -> str | None:
    """在启信宝搜索公司，返回第一个结果的详情页 URL"""
    encoded = urllib.parse.quote(company_name)
    await page.goto(f'https://www.qixin.com/search?key={encoded}', wait_until='networkidle')
    await page.wait_for_timeout(3000)

    href = await page.evaluate("""() => {
        // 搜索结果中的公司链接
        const links = document.querySelectorAll('a[href*="/company/"]');
        for (const link of links) {
            const text = link.textContent?.trim() || '';
            if (text.length > 2) return link.href;
        }
        return null;
    }""")
    return href


async def _extract_detail(page) -> dict:
    """从启信宝公司详情页提取信息"""
    body_text = await page.evaluate('() => document.body.innerText')

    result = {}

    # 经营状态
    m = re.search(r'经营状态\s*([存续在营注销吊销停业迁入迁出\s]+)', body_text)
    if m:
        result['status'] = m.group(1).strip()

    # 注册资本
    m = re.search(r'注册资本\s*([\d,.]+\s*万[^\s]*)', body_text)
    if m:
        result['registered_capital'] = m.group(1).strip()

    # 成立日期
    m = re.search(r'成立日期\s*(\d{4}-\d{2}-\d{2})', body_text)
    if m:
        result['established_date'] = m.group(1)

    # 社保人数 — 多种格式
    m = re.search(r'社保人数[：:\s]*(\d+)', body_text)
    if m:
        result['social_insurance_count'] = int(m.group(1))
    else:
        m = re.search(r'(\d+)人[（(]\d{4}年?.*?社保人数[）)]', body_text)
        if m:
            result['social_insurance_count'] = int(m.group(1))
        else:
            m = re.search(r'员工数量[：:\s]*(\d+)人', body_text)
            if m:
                result['social_insurance_count'] = int(m.group(1))

    # 企业名称
    m = re.search(r'^([^\n]+?有限公司|公司|集团|企业|厂)', body_text, re.MULTILINE)
    if m:
        result['name'] = m.group(1).strip()

    return result


async def query_company_async(company_name: str) -> dict:
    """异步查询企业信息"""
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 900})
        page = await context.new_page()

        # 搜索公司
        detail_url = await _search_qixin(page, company_name)
        if not detail_url:
            return {
                'company_name': company_name,
                'status': '查询失败',
                'social_insurance_count': -1,
                'error': '未在启信宝找到该企业',
            }

        # 打开详情页
        await page.goto(detail_url, wait_until='networkidle')
        await page.wait_for_timeout(3000)

        info = await _extract_detail(page)

        return {
            'company_name': info.get('name', company_name),
            'social_insurance_count': info.get('social_insurance_count', -1),
            'status': info.get('status', '未知'),
            'registered_capital': info.get('registered_capital', ''),
            'established_date': info.get('established_date', ''),
        }

    except Exception as e:
        return {
            'company_name': company_name,
            'status': '查询失败',
            'social_insurance_count': -1,
            'error': str(e),
        }
    finally:
        await browser.close()
        await pw.stop()


def query_company_info(company_name: str) -> dict:
    """查询企业公开信息（同步入口）"""
    return asyncio.run(query_company_async(company_name))


def main():
    parser = argparse.ArgumentParser(description='查询企业公开信息（启信宝）')
    parser.add_argument('--company', required=True, help='公司名称')
    args = parser.parse_args()

    try:
        result = query_company_info(args.company)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get('error'):
            sys.exit(1)
    except Exception as e:
        print(json.dumps({'error': str(e), 'status': 'error'}, ensure_ascii=False))
        sys.exit(1)


if __name__ == '__main__':
    main()
