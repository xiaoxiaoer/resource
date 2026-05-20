"""
企业信息查询脚本 — 通过百度搜索获取企业参保人数

使用百度搜索结果页面提取企业信息。

使用方式：
    python3 query_company_baidu.py --company "公司名称"
"""

import argparse
import asyncio
import json
import re
import sys

from playwright.async_api import async_playwright


async def query_company_baidu_async(company_name: str) -> dict:
    """通过百度搜索查询企业信息"""
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        )
        page = await context.new_page()

        # 百度搜索
        import urllib.parse
        search_url = f'https://www.baidu.com/s?wd={urllib.parse.quote(company_name)}%20参保人数'
        await page.goto(search_url, timeout=30000)
        await page.wait_for_timeout(3000)

        # 获取页面文本
        body_text = await page.evaluate('() => document.body.innerText')

        result = {
            'company_name': company_name,
            'social_insurance_count': -1,
            'status': '查询失败',
        }

        # 按优先级尝试多种提取方式
        patterns = [
            # 匹配 "参保人数为 13人" 或 "参保人数：13人"
            (r'参保人数[：:\s为]+(\d+)\s*人', '官方数据'),
            # 匹配 "参保人数13人"
            (r'参保人数(\d+)\s*人', '简洁格式'),
            # 匹配 "13人（参保" 或类似
            (r'(\d+)\s*人[（(].*?参保', '反向匹配'),
        ]

        for pattern, source in patterns:
            m = re.search(pattern, body_text)
            if m:
                count = int(m.group(1))
                # 过滤掉明显不合理的数字（如年份2024）
                if 0 < count < 10000:
                    result['social_insurance_count'] = count
                    result['status'] = '在营'
                    result['source'] = source
                    return result

        return result

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
    return asyncio.run(query_company_baidu_async(company_name))


def main():
    parser = argparse.ArgumentParser(description='查询企业公开信息（百度搜索）')
    parser.add_argument('--company', required=True, help='公司名称')
    args = parser.parse_args()

    try:
        result = query_company_info(args.company)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get('error') or result.get('social_insurance_count') == -1:
            sys.exit(1)
    except Exception as e:
        print(json.dumps({'error': str(e), 'status': 'error'}, ensure_ascii=False))
        sys.exit(1)


if __name__ == '__main__':
    main()