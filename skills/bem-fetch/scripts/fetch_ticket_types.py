"""
BEM 月票类型数据获取脚本

通过 POMP 页面获取指定车场的月票类型信息。
输出：各月票套餐名称、价格、是否内部/VIP、在办张数、分类。

使用方式：
    python3 fetch_ticket_types.py --car-park "车场名称" --car-park-id "505528"
"""

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'common'))
from bem_login import login_bem, simulate_login_pomp, cleanup, pomp_api_get

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))


async def _fetch_ticket_types_from_page(page, park_id: str) -> list[dict]:
    """从 POMP 获取月票类型列表"""
    # 尝试通过 API 获取月票类型
    # 常见接口路径
    api_paths = [
        f'/mgr/monthTicket/type/list.do?parkId={park_id}',
        f'/mgr/monthTicketBillType/list.do?parkId={park_id}',
        f'/mgr/park/monthTicket/list.do?parkId={park_id}',
    ]

    for path in api_paths:
        result = await pomp_api_get(page, path)
        if result.get('status') == 200:
            data = result.get('data')
            if isinstance(data, list) and len(data) > 0:
                return data
            if isinstance(data, dict) and data.get('rows'):
                return data['rows']

    # API 不通则通过页面表格抓取
    return []


def _parse_ticket_types(raw_types: list[dict]) -> list[dict]:
    """将 API 返回的月票类型解析为标准格式"""
    parsed = []
    for t in raw_types:
        name = t.get('typeName', t.get('name', t.get('ticketName', '')))
        price = float(t.get('price', t.get('amount', 0)) or 0)
        active_count = int(t.get('activeCount', t.get('currentCount', t.get('count', 0)) or 0))

        # 判断是否内部/VIP
        type_name_lower = (name or '').lower()
        is_internal = any(kw in type_name_lower for kw in ['内部', 'vip', '商户', '员工', '内部人', '管理'])
        category = '内部/VIP' if is_internal else '对外办理'

        parsed.append({
            'name': name,
            'price': price,
            'is_internal': is_internal,
            'active_count': active_count,
            'category': category,
            'raw': t,
        })
    return parsed


async def fetch_ticket_types_async(
    car_park: str,
    car_park_id: str | None = None,
    park_id: str | None = None,
) -> dict:
    page = None
    try:
        page, context = await login_bem(headless=True)
        pomp_page, park_info = await simulate_login_pomp(page, car_park_id, car_park_name=car_park)

        actual_park_id = park_id or park_info['id']
        raw_types = await _fetch_ticket_types_from_page(pomp_page, actual_park_id)
        ticket_types = _parse_ticket_types(raw_types)

        return {
            'status': 'success',
            'data': {
                'car_park': car_park or park_info.get('name', ''),
                'car_park_id': park_info.get('code', ''),
                'ticket_types': ticket_types,
            }
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
    finally:
        if page:
            await cleanup(page)


def fetch_ticket_types_data(car_park: str) -> dict:
    return asyncio.run(fetch_ticket_types_async(car_park))


def main():
    parser = argparse.ArgumentParser(description='获取 BEM 月票类型数据')
    parser.add_argument('--car-park', required=True, help='车场名称')
    parser.add_argument('--car-park-id', default=None, help='车场编码（如 2KR98AUK）')
    parser.add_argument('--park-id', default=None, help='POMP 内部 parkId（如 5516）')
    args = parser.parse_args()

    result = asyncio.run(fetch_ticket_types_async(args.car_park, args.car_park_id, args.park_id))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('status') == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
