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
    fetch_temp_charge_report, fetch_monthly_ticket_report, fetch_month_ticket_config, pomp_api_get,
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


def _extract_bill_total_real_value(data: dict) -> float:
    """从 parkingBillDetail 响应中提取合计行（id 为 null）的 realValue"""
    if not data or data.get('status') != 200:
        return 0
    inner = data.get('data', {})
    if isinstance(inner, dict):
        rows = inner.get('rows', [])
    elif isinstance(inner, list):
        rows = inner
    else:
        return 0
    for row in rows:
        if row.get('id') is None:
            return float(row.get('realValue', 0) or 0)
    return 0


async def _fetch_channel_income_ratio(pomp_page, actual_park_id: str) -> dict:
    """获取自有小程序/ETC支付渠道的可消耗收入占比。

    两次调用 parkingBillDetail/list.do：
    - Query A：带 payOrigin=14 过滤（开放平台收入）
    - Query B：无 payOrigin 过滤（总收入）
    返回 { value_a, value_b, ratio, formula, date_range }
    """
    now = datetime.now()
    end_time = now.strftime('%Y-%m-%d %H:%M:%S')
    start_time = (now - relativedelta(months=3)).strftime('%Y-%m-%d %H:%M:%S')

    base_params = {
        'page': '1',
        'rp': '500',
        'parkIds': str(actual_park_id),
        'query_payTimeFrom': start_time,
        'query_payTimeTo': end_time,
        'query_billType': '0',
    }

    # Query B：总收入（不带 payOrigin 过滤）
    result_b = await pomp_api_get(pomp_page, '/mgr/park/parkingBillDetail/list.do', base_params)

    # Query A：开放平台收入（带 payOrigin=14 过滤）
    params_a = {
        **base_params,
        'query_payOrigin': '14',
        'query_payOriginRemark': '开放平台',
    }
    result_a = await pomp_api_get(pomp_page, '/mgr/park/parkingBillDetail/list.do', params_a)

    value_b = _extract_bill_total_real_value(result_b)
    value_a = _extract_bill_total_real_value(result_a)

    ratio = round(value_a / value_b, 4) if value_b > 0 else 0

    return {
        'value_a': value_a,
        'value_b': value_b,
        'ratio': ratio,
        'formula': f'¥{value_a:,.2f} / ¥{value_b:,.2f} = {ratio:.2%}',
        'date_range': f'{start_time[:10]} ~ {end_time[:10]}',
    }


async def fetch_all_reports_async(
    car_park: str,
    car_park_id: str | None = None,
    date_range: str | None = None,
    park_id: str | None = None,
    reports: str = 'temp,ticket,types,config',
    fetch_channel_income: bool = False,
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

        # 月票配置
        if 'config' in report_set:
            raw = await fetch_month_ticket_config(pomp_page, actual_park_id)
            if raw.get('status') == 200:
                result['ticket_configs'] = _parse_ticket_configs(raw.get('data', {}))
            else:
                result['ticket_configs'] = []

        # 可消耗收入占比（自有小程序/ETC支付渠道）
        if fetch_channel_income:
            try:
                result['channel_income'] = await _fetch_channel_income_ratio(pomp_page, actual_park_id)
            except Exception as e:
                result['channel_income'] = {'error': str(e)}

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
    parser.add_argument('--reports', default='temp,ticket,types,config', help='要获取的报表，逗号分隔: temp,ticket,types,config')
    parser.add_argument('--fetch-channel-income', action='store_true', default=False, help='获取自有小程序/ETC渠道可消耗收入占比')
    args = parser.parse_args()

    result = asyncio.run(fetch_all_reports_async(
        args.car_park, args.car_park_id, args.date_range, args.park_id, args.reports,
        fetch_channel_income=args.fetch_channel_income,
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('status') == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
