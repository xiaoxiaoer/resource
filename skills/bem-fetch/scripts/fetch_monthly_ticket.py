"""
BEM 月票收入数据获取脚本

通过 POMP 报表 API 获取指定车场的月票收入数据。
输出：月票月均收入、趋势分析。

使用方式：
    python3 fetch_monthly_ticket.py --car-park "车场名称" --car-park-id "505528" [--date-range "2025-05~2026-04"]
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
    fetch_monthly_ticket_report,
)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))


def parse_date_range(date_range: str | None) -> tuple[str, str]:
    if date_range:
        parts = date_range.split('~')
        start = parts[0].strip() + '-01 00:00:00'
        end_parts = parts[1].strip().split('-')
        year, month = int(end_parts[0]), int(end_parts[1])
        last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).day
        end = f'{parts[1].strip()}-{last_day} 23:59:59'
        return start, end

    now = datetime.now()
    end_date = datetime(now.year, now.month, 1) - timedelta(days=1)
    start_date = (end_date - relativedelta(months=11)).replace(day=1)
    return (
        start_date.strftime('%Y-%m-01 00:00:00'),
        end_date.strftime('%Y-%m-%d 23:59:59'),
    )


def _calc_trend(monthly: list[dict]) -> dict:
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


async def fetch_monthly_ticket_async(
    car_park: str,
    car_park_id: str | None = None,
    date_range: str | None = None,
    park_id: str | None = None,
) -> dict:
    page = None
    try:
        page, context = await login_bem(headless=True)
        pomp_page, park_info = await simulate_login_pomp(page, car_park_id, car_park_name=car_park)

        actual_park_id = park_id or park_info['id']
        start, end = parse_date_range(date_range)

        result = await fetch_monthly_ticket_report(pomp_page, actual_park_id, start, end)

        if result.get('status') != 200:
            return {
                'status': 'error',
                'error': f'API 请求失败: status={result.get("status")}',
                'park_info': park_info,
            }

        api_data = result.get('data', {})
        # 兼容嵌套结构: data.data.rows 或 data.rows
        if isinstance(api_data, dict) and 'data' in api_data:
            inner = api_data['data']
            rows = inner.get('rows', []) if isinstance(inner, dict) else []
        elif isinstance(api_data, dict):
            rows = api_data.get('rows', [])
        else:
            rows = []

        monthly = []
        for row in rows:
            if row.get('parkName') == '合计':
                continue
            monthly.append({
                'month': row.get('reportDateStr', ''),
                'ticket_income': float(row.get('timeTicketTotalIncome', 0) or 0),
                'open_amount': float(row.get('openActualAmount', 0) or 0),
                'renew_amount': float(row.get('renewActualAmount', 0) or 0),
                'raw': row,
            })

        summary = _calc_trend(monthly)

        return {
            'status': 'success',
            'data': {
                'car_park': car_park or park_info.get('name', ''),
                'car_park_id': park_info.get('code', ''),
                'data_source': '智泊云',
                'date_range': f'{start[:10]} ~ {end[:10]}',
                'monthly': monthly,
                'summary': summary,
            }
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
    finally:
        if page:
            await cleanup(page)


def fetch_monthly_ticket_data(car_park: str, date_range: str | None = None) -> dict:
    return asyncio.run(fetch_monthly_ticket_async(car_park, date_range=date_range))


def main():
    parser = argparse.ArgumentParser(description='获取 BEM 月票收入数据')
    parser.add_argument('--car-park', required=True, help='车场名称')
    parser.add_argument('--car-park-id', default=None, help='车场编码（如 2KR98AUK）')
    parser.add_argument('--park-id', default=None, help='POMP 内部 parkId（如 5516）')
    parser.add_argument('--date-range', default=None, help='查询时间范围，格式: YYYY-MM~YYYY-MM')
    args = parser.parse_args()

    result = asyncio.run(fetch_monthly_ticket_async(
        args.car_park, args.car_park_id, args.date_range, args.park_id
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('status') == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
