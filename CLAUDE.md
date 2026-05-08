# 资源置换评估系统

## 项目概述

资源置换业务评估测算工具。运营人员通过 AI Chat 对话框上传车场资料，系统自动与 BEM 系统数据对比分析，输出初审结果。

## 架构：Harness + Skills

```
运营人员 → AI Chat（Harness） → 调度 Skills → 输出初审结果
```

- **Harness**：AI Chat 对话界面，负责文件接收、解析、Skill 调度、上下文管理
- **Skills**：各自独立的能力模块，通过 `skill.md` 定义行为，`scripts/` 放固化脚本

## 业务类型

| 类型 | 说明 |
|------|------|
| 停车券业务 | 停车券置换资源评估 |
| 车位置换业务 | 车位置换资源评估 |

## 标准审核流程

```
1. 运营上传车场资料（Excel/图片）
   → completeness-check skill 检查字段完整性
   → 不全：输出缺失项，要求补充
   → 全：进入下一步

2. 确认业务类型（停车券 / 车位置换）
   → bem-fetch skill 获取 BEM 系统数据（临停/月票/月票类型）
   → company-lookup skill 查询企查查（参保人数）

3. 执行对应审核 skill
   → audit-parking-voucher（停车券）或 audit-spot-exchange（车位置换）
   → 逐项对比 + 风险检查

4. 输出初审结果（按 output_template.md 格式）
```

## Skills 目录

| Skill | 路径 | 用途 |
|-------|------|------|
| bem-fetch | `skills/bem-fetch/` | 从 BEM 系统获取临停、月票、月票类型数据 |
| completeness-check | `skills/completeness-check/` | 检查上传资料的必填字段完整性 |
| audit-parking-voucher | `skills/audit-parking-voucher/` | 停车券业务逐项审核 |
| audit-spot-exchange | `skills/audit-spot-exchange/` | 车位置换业务逐项审核 |
| company-lookup | `skills/company-lookup/` | 企查查查询合作客户参保人数 |

## 关键约束

- BEM 数据必须通过 `skills/bem-fetch/scripts/` 下的固化脚本获取，AI 不直接操作 BEM 系统
- 检查规则配置在 `templates/risk_rules.json`，业务调整时改配置不改 skill
- 审核结果统一按 `prompts/output_template.md` 格式输出
- 必填字段定义在 `templates/fields_required.json`

## 文件上传支持

- Excel (.xlsx/.xls)：解析为结构化数据
- 图片 (.png/.jpg/.jpeg)：AI 视觉识别提取数据
- 多文件上传：信息收集表 + 测算表可同时上传
