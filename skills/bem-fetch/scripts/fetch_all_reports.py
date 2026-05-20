"""
BEM 统一数据获取脚本

一次登录获取全部报表数据（临停收费、月票收费、月票类型）。
复用 common/bem_login.py 的 API 函数，不修改原有独立脚本。

使用方式：
    python3 fetch_all_reports.py --car-park "车场名" --car-park-id "2KR98AUK" [--date-range "2025-05~2026-04"] [--reports temp,ticket,types]
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'common'))
from bem_login import (
    login_bem, simulate_login_pomp, cleanup,
    fetch_temp_charge_report, fetch_monthly_ticket_report, pomp_api_get,
)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))


def parse_date_range(date_range: str | None) -> tuple[str, str]:
    """解析日期范围，默认近12个月（当前月-1 往前12个月）。"""
    if date_range:
        parts = date_range.split('~')
        start = parts[0].strip() + '-01 00:00:00'
        end_parts = parts[1].strip().split('-')
        year, month = int(end_parts[0]), int(end_parts[1])
        last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).day
        end = f'{parts[1].strip()}-{last_day} 23:59:59'
        return start, end

    now = datetime.now()
    # 结束日期：上个月的最后一天
    end_date = datetime(now.year, now.month, 1) - timedelta(days=1)
    # 开始日期：往前第12个月的第一天
    start_date = (end_date - relativedelta(months=11)).replace(day=1)
    return start_date.strftime('%Y-%m-01 00:00:00'), end_date.strftime('%Y-%m-%d 23:59:59')


def _parse_temp_rows(data: dict) -> list[dict]:
    """解析临停收费报表行"""
    if isinstance(data, dict) and 'data' in data:
        inner = data['data']
        rows = inner.get('rows', []) if isinstance(inner, dict) else []
    elif isinstance(data, dict):
        rows = data.get('rows', [])
    else:
        return []

    monthly = []
    for row in rows:
        if row.get('parkName') == '合计':
            continue
        monthly.append({
            'month': row.get('statDim', ''),
            'actual_income_wechat': float(row.get('weixinRealValue', 0) or 0),
            'total_income': float(row.get('realValue', 0) or 0),
            'wechat_mini_income': float(row.get('weixinRealValue', 0) or 0),
            'receivable': float(row.get('shouldValue', 0) or 0),
            'cash_income': float(row.get('cashRealValue', 0) or 0),
            'alipay_income': float(row.get('aliRealValue', 0) or 0),
            'other_income': float(row.get('otherRealValue', 0) or 0),
            'discount': float(row.get('couponValue', 0) or 0),
            'refund': float(row.get('refundValue', 0) or 0),
        })
    return monthly


def _calc_temp_trend(monthly: list[dict]) -> dict:
    """计算临停月均值和趋势"""
    if not monthly:
        return {'monthly_avg': 0, 'trend': '无数据', 'trend_note': ''}

    values = [m['total_income'] for m in monthly if m['total_income'] > 0]
    if not values:
        return {'monthly_avg': 0, 'trend': '无收入', 'trend_note': '所有月份收入为0'}

    avg = round(sum(values) / len(values), 2)

    if len(values) >= 3:
        recent = sum(values[-3:]) / 3
        earlier = sum(values[-6:-3]) / 3 if len(values) >= 6 else avg
        if earlier > 0:
            change = (recent - earlier) / earlier * 100
            trend = '上升' if change > 10 else ('下降' if change < -10 else '平稳')
            trend_note = f'近3个月环比{"上升" if change > 0 else "下降"}{abs(change):.1f}%'
        else:
            trend, trend_note = '平稳', ''
    else:
        trend, trend_note = '数据不足', ''

    return {'monthly_avg': avg, 'trend': trend, 'trend_note': trend_note}


def _parse_ticket_rows(data: dict) -> list[dict]:
    """解析月票收费报表行"""
    if isinstance(data, dict) and 'data' in data:
        inner = data['data']
        rows = inner.get('rows', []) if isinstance(inner, dict) else []
    elif isinstance(data, dict):
        rows = data.get('rows', [])
    else:
        return []

    monthly = []
    for row in rows:
        if row.get('parkName') == '合计':
            continue
        monthly.append({
            'month': row.get('reportDateStr', ''),
            'ticket_income': float(row.get('onlineTotalActualAmount', 0) or 0),
        })
    return monthly


def _calc_ticket_trend(monthly: list[dict]) -> dict:
    """计算月票月均值和趋势"""
    values = [m['ticket_income'] for m in monthly if m['ticket_income'] > 0]
    if not values:
        return {'monthly_avg': 0, 'trend': '无数据', 'trend_note': ''}

    avg = round(sum(values) / len(values), 2)

    if len(values) >= 3:
        recent = sum(values[-3:]) / 3
        earlier = sum(values[-6:-3]) / 3 if len(values) >= 6 else avg
        if earlier > 0:
            change = (recent - earlier) / earlier * 100
            trend = '上升' if change > 10 else ('下降' if change < -10 else '平稳')
            trend_note = f'近3个月环比{"上升" if change > 0 else "下降"}{abs(change):.1f}%'
        else:
            trend, trend_note = '平稳', ''
    else:
        trend, trend_note = '数据不足', ''

    return {'monthly_avg': avg, 'trend': trend, 'trend_note': trend_note}


async def _fetch_ticket_types_from_page(page, park_id: str) -> list[dict]:
    """从 POMP 获取月票类型列表"""
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
    return []


def _parse_ticket_types(raw_types: list[dict]) -> list[dict]:
    """解析月票类型"""
    parsed = []
    for t in raw_types:
        name = t.get('typeName', t.get('name', t.get('ticketName', '')))
        price = float(t.get('price', t.get('amount', 0)) or 0)
        active_count = int(t.get('activeCount', t.get('currentCount', t.get('count', 0)) or 0))

        type_name_lower = (name or '').lower()
        is_internal = any(kw in type_name_lower for kw in ['内部', 'vip', '商户', '员工', '内部人', '管理'])
        category = '内部/VIP' if is_internal else '对外办理'

        parsed.append({
            'name': name,
            'price': price,
            'is_internal': is_internal,
            'active_count': active_count,
            'category': category,
        })
    return parsed


async def fetch_all_reports_async(
    car_park: str,
    car_park_id: str | None = None,
    date_range: str | None = None,
    park_id: str | None = None,
    reports: str = 'temp,ticket,types',
) -> dict:
    """一次登录获取全部报表数据"""
    page = None
    try:
        page, context = await login_bem(headless=True)
        pomp_page, park_info = await simulate_login_pomp(page, car_park_id, car_park_name=car_park)

        # 多候选匹配时，返回候选列表让调用方选择
        if park_info.get('exact_match') is False:
            await cleanup(page)
            return {
                'status': 'multiple_matches',
                'message': f'找到 {len(park_info["candidates"])} 个匹配车场，请指定精确车场',
                'matched_park': {'name': park_info['name'], 'code': park_info['code'], 'id': park_info['id']},
                'candidates': park_info['candidates'],
            }

        actual_park_id = park_id or park_info['id']
        start, end = parse_date_range(date_range)
        report_set = set(r.strip() for r in reports.split(','))

        result = {
            'car_park': car_park or park_info.get('name', ''),
            'car_park_id': park_info.get('code', ''),
            'data_source': '智泊云',
            'date_range': f'{start[:10]} ~ {end[:10]}',
        }

        # 临停收费
        if 'temp' in report_set:
            raw = await fetch_temp_charge_report(pomp_page, actual_park_id, start, end)
            if raw.get('status') == 200:
                monthly = _parse_temp_rows(raw.get('data', {}))
                result['temp_parking'] = {
                    'monthly': monthly,
                    'summary': _calc_temp_trend(monthly),
                }
            else:
                result['temp_parking'] = {'error': f'API 请求失败: status={raw.get("status")}'}

        # 月票收费
        if 'ticket' in report_set:
            raw = await fetch_monthly_ticket_report(pomp_page, actual_park_id, start, end)
            if raw.get('status') == 200:
                monthly = _parse_ticket_rows(raw.get('data', {}))
                result['monthly_ticket'] = {
                    'monthly': monthly,
                    'summary': _calc_ticket_trend(monthly),
                }
            else:
                result['monthly_ticket'] = {'error': f'API 请求失败: status={raw.get("status")}'}

        # 月票类型
        if 'types' in report_set:
            raw_types = await _fetch_ticket_types_from_page(pomp_page, actual_park_id)
            result['ticket_types'] = _parse_ticket_types(raw_types)

        return {'status': 'success', 'data': result}

    except Exception as e:
        return {'status': 'error', 'error': str(e)}
    finally:
        if page:
            await cleanup(page)


def main():
    parser = argparse.ArgumentParser(description='BEM 统一数据获取（一次登录获取全部报表）')
    parser.add_argument('--car-park', required=True, help='车场名称')
    parser.add_argument('--car-park-id', default=None, help='车场编码（如 2KR98AUK）')
    parser.add_argument('--park-id', default=None, help='POMP 内部 parkId（如 5516）')
    parser.add_argument('--date-range', default=None, help='查询时间范围，格式: YYYY-MM~YYYY-MM')
    parser.add_argument('--reports', default='temp,ticket,types', help='要获取的报表，逗号分隔: temp,ticket,types')
    args = parser.parse_args()

    result = asyncio.run(fetch_all_reports_async(
        args.car_park, args.car_park_id, args.date_range, args.park_id, args.reports,
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('status') == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
