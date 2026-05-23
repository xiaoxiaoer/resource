"""
BEM 月票配置数据获取脚本

获取指定车场已启用的月票套餐配置信息。
输出：月票名称、价格、总张数、已售张数。

使用方式：
    python3 fetch_month_ticket_config.py --car-park "车场名称" --car-park-id "2KR98AUK"
"""

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'common'))
from bem_login import login_bem, simulate_login_pomp, cleanup, fetch_month_ticket_config

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))


def _parse_ticket_configs(raw_data: dict) -> list[dict]:
    """解析月票配置列表"""
    if isinstance(raw_data, dict) and 'data' in raw_data:
        inner = raw_data['data']
        rows = inner.get('rows', []) if isinstance(inner, dict) else []
    elif isinstance(raw_data, dict):
        rows = raw_data.get('rows', [])
    elif isinstance(raw_data, list):
        return raw_data
    else:
        return []

    configs = []
    for row in rows:
        configs.append({
            'ticketName': row.get('ticketName', ''),
            'price': row.get('price'),
            'maxSellNum': row.get('maxSellNum'),
            'sellNum': row.get('sellNum'),
        })
    return configs


async def fetch_month_ticket_config_async(
    car_park: str,
    car_park_id: str | None = None,
    park_id: str | None = None,
) -> dict:
    page = None
    try:
        page, context = await login_bem(headless=True)
        pomp_page, park_info = await simulate_login_pomp(page, car_park_id, car_park_name=car_park)

        if park_info.get('exact_match') is False:
            await cleanup(page)
            return {
                'status': 'multiple_matches',
                'message': f'找到 {len(park_info["candidates"])} 个匹配车场，请指定精确车场',
                'candidates': park_info['candidates'],
            }

        actual_park_id = park_id or park_info['id']
        raw = await fetch_month_ticket_config(pomp_page, actual_park_id)

        if raw.get('status') == 200:
            configs = _parse_ticket_configs(raw.get('data', {}))
            return {
                'status': 'success',
                'data': {
                    'car_park': car_park or park_info.get('name', ''),
                    'car_park_id': park_info.get('code', ''),
                    'ticket_configs': configs,
                }
            }
        else:
            return {'status': 'error', 'error': f'API 请求失败: status={raw.get("status")}'}

    except Exception as e:
        return {'status': 'error', 'error': str(e)}
    finally:
        if page:
            await cleanup(page)


def main():
    parser = argparse.ArgumentParser(description='获取 BEM 月票配置数据')
    parser.add_argument('--car-park', required=True, help='车场名称')
    parser.add_argument('--car-park-id', default=None, help='车场编码（如 2KR98AUK）')
    parser.add_argument('--park-id', default=None, help='POMP 内部 parkId（如 5516）')
    args = parser.parse_args()

    result = asyncio.run(fetch_month_ticket_config_async(args.car_park, args.car_park_id, args.park_id))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('status') == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
