# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

资源置换业务评估测算工具。运营人员上传车场资料（Excel），系统自动解析、获取 BEM 系统数据对比，通过 LLM 驱动审核输出初审结果。

## 常用命令

```bash
# 启动开发服务器（支持热重载）
python -m web.app

# 解析 Excel 文件（调试用）
python -m web.services.excel_parser path/to/file.xlsx

# 安装依赖
pip install -r requirements.txt

# Playwright 浏览器安装（BEM 数据抓取需要）
playwright install chromium
```

目前没有测试套件（tests/ 目录为空）。

## 架构：Harness + Skills

```
运营人员 → Web UI → AI Orchestrator（LLM + Function Calling）→ Skills → 审核结果
```

- **Web 层**（`web/`）：FastAPI 应用，SSE 流式输出
- **AI 编排**（`web/services/ai_orchestrator.py`）：通过 DeepSeek/OpenAI 兼容 API 的 function calling 驱动审核流程，LLM 自主决定何时调用工具
- **Skills**（`skills/`）：独立能力模块，`skill.md` 定义行为（嵌入 system prompt），`scripts/` 放固化脚本
- **配置**（`templates/`）：风险规则和必填字段外置为 JSON，业务调整改配置不改代码

## 核心数据流

1. 运营上传 Excel → `excel_parser.py` 解析为结构化 JSON
2. 运营点击审核 → `ai_orchestrator.py` 组装 system prompt（合并所有 prompt/skill/rule 文件）
3. LLM 通过 function calling 调用 `fetch_bem_data` 和 `lookup_company` 工具
4. `skill_runner.py` 以子进程执行 `skills/*/scripts/` 下的 Python 脚本
5. `_build_comparison()` 程序化构建 Excel vs BEM 数据对比，通过 SSE 发送到前端

## 审核字段范围

**权威规则源**：`prompts/audit_field_rules.md`（所有 checklist、skill 文件引用此文件）

- **停车券业务**：项目基本信息全部字段 + 测算工具 10 个字段
- **车位置换业务**：项目基本信息全部字段 + 测算工具 6 个字段
- **项目评估数据**：原样输出，不做验证

## Excel 解析关键点

`excel_parser.py` 使用**标签关键词查找**（`_find_label_row`）而非固定行号定位字段，兼容不同版本格式的 Excel 模板。支持两种 sheet 结构：

- 停车券：`1.项目基本信息` + `测算工具（金额券）`
- 车位置换：`项目信息收集表` + `车位置换测算表` + `折扣采买测算表`

## 关键约束

- BEM 数据必须通过 `skills/bem-fetch/scripts/` 下的固化脚本获取（Playwright + 验证码 OCR），AI 不直接操作 BEM 系统
- 企查查查询通过 `skills/company-lookup/scripts/query_qichacha.py` 执行
- 检查规则在 `templates/risk_rules.json`，必填字段在 `templates/fields_required.json`
- 审核输出格式遵循 `prompts/output_template.md`
- LLM API Key 和 BEM 登录凭证配置在 `.env`

## 业务类型

| 类型 | 说明 |
|------|------|
| 停车券业务 (parking_voucher) | 停车券置换资源评估 |
| 车位置换业务 (spot_exchange) | 车位置换资源评估 |

## Skills 目录

| Skill | 路径 | 调用方式 |
|-------|------|---------|
| bem-fetch | `skills/bem-fetch/` | 子进程执行 Playwright 脚本 |
| company-lookup | `skills/company-lookup/` | 子进程执行 Playwright 脚本 |
| completeness-check | `skills/completeness-check/` | 纯 prompt 驱动，无脚本 |
| audit-parking-voucher | `skills/audit-parking-voucher/` | 纯 prompt 驱动，嵌入 system prompt |
| audit-spot-exchange | `skills/audit-spot-exchange/` | 纯 prompt 驱动，嵌入 system prompt |
