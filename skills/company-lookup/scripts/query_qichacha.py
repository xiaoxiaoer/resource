"""
企查查查询脚本

根据公司名称查询企查查，获取参保人数等企业信息。

TODO: 实现以下功能
1. 调用企查查 API 或爬取企查查数据
2. 获取目标企业的参保人数
3. 获取企业经营状态
4. 输出标准 JSON

使用方式：
    python3 query_qichacha.py --company "公司名称"
"""

import argparse
import json
import sys


def query_company_info(company_name: str) -> dict:
    """
    查询企查查获取企业信息。

    Args:
        company_name: 公司名称

    Returns:
        符合 skill.md 定义的 JSON 结构
    """
    # TODO: 实现企查查查询逻辑
    raise NotImplementedError("企查查查询脚本待实现")


def main():
    parser = argparse.ArgumentParser(description="查询企查查企业信息")
    parser.add_argument("--company", required=True, help="公司名称")
    args = parser.parse_args()

    try:
        result = query_company_info(args.company)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except NotImplementedError as e:
        print(json.dumps({"error": str(e), "status": "not_implemented"}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e), "status": "error"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
