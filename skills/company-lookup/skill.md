# 企查查查询 Skill

## 描述

根据合作客户主体名称，查询企查查获取参保人数等信息。

## 触发条件

- 审核过程中需要查询合作客户主体信息时触发
- 通常由 audit-parking-voucher 或 audit-spot-exchange skill 调用

## 输入参数

| 参数 | 必填 | 说明 |
|------|------|------|
| company_name | 是 | 合作客户主体名称 |

## 执行步骤

### 1. 查询企查查

运行脚本：
```bash
python3 skills/company-lookup/scripts/query_qichacha.py --company "{company_name}"
```

输出 JSON 结构：
```json
{
  "company_name": "XXX有限公司",
  "social_insurance_count": 50,
  "status": "在营",
  "registered_capital": "100万",
  "established_date": "2020-01-01"
}
```

### 2. 输出结果

将查询结果提供给调用方使用。核心关注：
- 参保人数（供运营参考）
- 经营状态（是否在营）

## 注意事项

- 企查查数据仅供参考，不作为审核通过/拒绝的依据
- 查询失败时不阻塞审核流程，标注"企查查查询失败，需人工查询"即可
