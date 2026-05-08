"""
BEM 月票收入数据获取脚本

从智泊云/智汇云后台获取指定车场的月票收入数据。
输出：月票月均收入、趋势分析。

TODO: 实现以下功能
1. 登录 BEM 系统（智泊云/智汇云）
2. 定位到指定车场
3. 获取近12个月的月票收入数据
4. 计算月均值和趋势
5. 输出标准 JSON

使用方式：
    python3 fetch_monthly_ticket.py --car-park "车场名称" [--date-range "2025-05~2026-04"]
"""

import argparse
import json
import sys


def fetch_monthly_ticket_data(car_park: str, date_range: str | None = None) -> dict:
    """
    从 BEM 系统获取月票收入数据。

    Args:
        car_park: 车场名称
        date_range: 查询时间范围，格式 "YYYY-MM~YYYY-MM"，默认近12个月

    Returns:
        符合 skill.md 定义的 JSON 结构
    """
    # TODO: 实现 BEM 系统数据获取逻辑
    raise NotImplementedError("BEM 月票收入数据获取脚本待实现")


def main():
    parser = argparse.ArgumentParser(description="获取 BEM 月票收入数据")
    parser.add_argument("--car-park", required=True, help="车场名称")
    parser.add_argument("--date-range", default=None, help="查询时间范围，格式: YYYY-MM~YYYY-MM")
    args = parser.parse_args()

    try:
        result = fetch_monthly_ticket_data(args.car_park, args.date_range)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except NotImplementedError as e:
        print(json.dumps({"error": str(e), "status": "not_implemented"}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e), "status": "error"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
