"""
BEM 月票类型数据获取脚本

从智泊云/智汇云后台获取指定车场的月票类型信息。
输出：各月票套餐名称、价格、是否内部/VIP、在办张数、分类。

TODO: 实现以下功能
1. 登录 BEM 系统（智泊云/智汇云）
2. 定位到指定车场
3. 获取所有月票类型
4. 标注内部/VIP类型 vs 对外办理类型
5. 输出标准 JSON

使用方式：
    python3 fetch_ticket_types.py --car-park "车场名称"
"""

import argparse
import json
import sys


def fetch_ticket_types_data(car_park: str) -> dict:
    """
    从 BEM 系统获取月票类型数据。

    Args:
        car_park: 车场名称

    Returns:
        符合 skill.md 定义的 JSON 结构
    """
    # TODO: 实现 BEM 系统数据获取逻辑
    raise NotImplementedError("BEM 月票类型数据获取脚本待实现")


def main():
    parser = argparse.ArgumentParser(description="获取 BEM 月票类型数据")
    parser.add_argument("--car-park", required=True, help="车场名称")
    args = parser.parse_args()

    try:
        result = fetch_ticket_types_data(args.car_park)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except NotImplementedError as e:
        print(json.dumps({"error": str(e), "status": "not_implemented"}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e), "status": "error"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
