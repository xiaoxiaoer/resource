"""
BEM 临停收入数据获取脚本

通过 POMP 报表 API 获取指定车场的临停收入数据。
输出：临停月均收入（实收金额-微信）、各渠道收入明细、趋势分析。

使用方式：
    python3 fetch_temp_parking.py --car-park "车场名称" --car-park-id "505528" [--date-range "2025-05~2026-04"]
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
    fetch_temp_charge_report,
)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))


def parse_date_range(date_range: str | None) -> tuple[str, str]:
    """解析日期范围，默认近12个月。返回带时间的格式。"""
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
    return start_date.strftime('%Y-%m-01 00:00:00'), end_date.strftime('%Y-%m-%d 23:59:59')


def _parse_report_rows(data: dict) -> list[dict]:
    """从 API 返回数据中提取月度收入行（queryType=1 按月维度）"""
    if isinstance(data, dict) and 'data' in data:
        inner = data['data']
        rows = inner.get('rows', []) if isinstance(inner, dict) else []
    elif isinstance(data, dict):
        rows = data.get('rows', [])
    else:
        return []

    if not rows:
        return []

    monthly = []
    for row in rows:
        # 跳过合计行（parkName='合计' 且 statDim 为 null）
        if row.get('parkName') == '合计':
            continue
        monthly.append({
            'month': row.get('statDim', ''),
            'actual_income_wechat': float(row.get('weixinRealValue', 0) or 0),
            'total_income': float(row.get('realValue', 0) or 0),
            'wechat_mini_income': float(row.get('weixinRealValue', 0) or 0),
            'etc_income': 0,
            'receivable': float(row.get('shouldValue', 0) or 0),
            'cash_income': float(row.get('cashRealValue', 0) or 0),
            'alipay_income': float(row.get('aliRealValue', 0) or 0),
            'other_income': float(row.get('otherRealValue', 0) or 0),
            'discount': float(row.get('couponValue', 0) or 0),
            'refund': float(row.get('refundValue', 0) or 0),
        })
    return monthly


def _calc_trend(monthly: list[dict]) -> dict:
    """计算月均值和趋势"""
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
            if change > 10:
                trend = '上升'
            elif change < -10:
                trend = '下降'
            else:
                trend = '平稳'
            trend_note = f'近3个月环比{"上升" if change > 0 else "下降"}{abs(change):.1f}%'
        else:
            trend, trend_note = '平稳', ''
    else:
        trend, trend_note = '数据不足', ''

    return {'monthly_avg': avg, 'trend': trend, 'trend_note': trend_note}


async def fetch_temp_parking_async(
    car_park: str,
    car_park_id: str | None = None,
    date_range: str | None = None,
    park_id: str | None = None,
) -> dict:
    """异步获取临停收入数据"""
    page = None
    try:
        page, context = await login_bem(headless=True)
        pomp_page, park_info = await simulate_login_pomp(page, car_park_id, car_park_name=car_park)

        # 优先用传入的 park_id，否则用 AOMP 车场的 ID
        actual_park_id = park_id or park_info['id']
        start, end = parse_date_range(date_range)

        result = await fetch_temp_charge_report(pomp_page, actual_park_id, start, end)

        if result.get('status') != 200:
            return {
                'status': 'error',
                'error': f'API 请求失败: status={result.get("status")}',
                'park_info': park_info,
            }

        monthly = _parse_report_rows(result.get('data', {}))
        summary = _calc_trend(monthly)

        return {
            'status': 'success',
            'data': {
                'car_park': car_park or park_info.get('name', ''),
                'car_park_id': park_info.get('code', ''),
                'data_source': '智泊云',
                'date_range': f'{start} ~ {end}',
                'monthly': monthly,
                'summary': summary,
            }
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
    finally:
        if page:
            await cleanup(page)


def fetch_temp_parking_data(car_park: str, date_range: str | None = None) -> dict:
    return asyncio.run(fetch_temp_parking_async(car_park, date_range=date_range))


def main():
    parser = argparse.ArgumentParser(description='获取 BEM 临停收入数据')
    parser.add_argument('--car-park', required=True, help='车场名称')
    parser.add_argument('--car-park-id', default=None, help='车场编码（如 2KR98AUK）')
    parser.add_argument('--park-id', default=None, help='POMP 内部 parkId（如 5516）')
    parser.add_argument('--date-range', default=None, help='查询时间范围，格式: YYYY-MM~YYYY-MM')
    args = parser.parse_args()

    result = asyncio.run(fetch_temp_parking_async(
        args.car_park, args.car_park_id, args.date_range, args.park_id
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('status') == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
