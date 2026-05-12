"""
AI 编排器 — 核心模块

完全由 LLM 通过 function calling 驱动审核流程。
不做硬编码状态机，LLM 自己决定何时获取 BEM 数据、何时查询企业信息。
"""

import json
import os
from pathlib import Path
from typing import AsyncGenerator

from openai import AsyncOpenAI

from web.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, PROMPTS_DIR, TEMPLATES_DIR, SKILLS_DIR
from web.services.skill_runner import run_bem_fetch, run_company_lookup

# --- 工具定义（OpenAI function calling 格式） ---

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_bem_data",
            "description": "从BEM系统获取指定车场的临停收入、月票收入、月票类型数据。返回月均收入、各渠道明细和趋势分析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "car_park_name": {
                        "type": "string",
                        "description": "停车场名称，如'大良保利广场'"
                    },
                    "date_range": {
                        "type": "string",
                        "description": "查询时间范围，格式YYYY-MM~YYYY-MM，不传则默认近12个月"
                    }
                },
                "required": ["car_park_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_company",
            "description": "查询企业的参保人数、经营状态、注册资本、成立日期等信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "公司全称"
                    }
                },
                "required": ["company_name"]
            }
        }
    }
]


def _load_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding='utf-8')
    return ''


def _build_system_prompt(business_type: str) -> str:
    """构建 system prompt，包含所有配置文件"""
    system_md = _load_file(PROMPTS_DIR / 'system.md')
    risk_rules = _load_file(TEMPLATES_DIR / 'risk_rules.json')
    fields_required = _load_file(TEMPLATES_DIR / 'fields_required.json')
    output_template = _load_file(PROMPTS_DIR / 'output_template.md')

    if business_type == 'parking_voucher':
        checklist = _load_file(PROMPTS_DIR / 'audit_checklist_voucher.md')
        skill_md = _load_file(SKILLS_DIR / 'audit-parking-voucher' / 'skill.md')
    else:
        checklist = _load_file(PROMPTS_DIR / 'audit_checklist_spot.md')
        skill_md = _load_file(SKILLS_DIR / 'audit-spot-exchange' / 'skill.md')

    completeness_skill = _load_file(SKILLS_DIR / 'completeness-check' / 'skill.md')
    audit_field_rules = _load_file(PROMPTS_DIR / 'audit_field_rules.md')

    return f"""{system_md}

---

## 审核字段范围规则

{audit_field_rules}

---

## 审核检查清单

{checklist}

---

## 风险判定规则

{risk_rules}

---

## 必填字段定义

{fields_required}

---

## 完整性检查 Skill

{completeness_skill}

---

## 审核业务 Skill

{skill_md}

---

## 输出模板

{output_template}

---

## 工作指引

1. 先检查资料完整性（对照必填字段定义），如有缺失项直接输出缺失项并要求补充
2. 完整性通过后，调用工具获取 BEM 数据和企查查数据
3. 按检查清单逐项对比分析，每项给出 ✅/⚠️/❌/📋 标记
4. 按输出模板格式输出完整审核结果
5. 业务类型为：{"停车券业务" if business_type == "parking_voucher" else "车位置换业务"}
"""


def _build_comparison(parsed_data: dict, tool_results: list[dict]) -> dict:
    """构建数据对比结构：Excel 上传数据 vs BEM 系统数据"""
    pi = parsed_data.get('project_info', {})
    ct = parsed_data.get('calculation_tool', {})
    comparison: dict = {
        'summary': [],
        'monthly_detail': {'temp_parking': [], 'monthly_ticket': []},
        'ticket_types': [],
        'company_info': None,
    }

    # 从 tool_results 中提取 BEM 和企业数据
    bem_data = None
    company_data = None
    for tr in tool_results:
        try:
            content = json.loads(tr['content'])
        except (json.JSONDecodeError, KeyError):
            continue
        # 判断是 BEM 数据还是企业查询数据
        if 'temp_parking' in content or ('data' in content and isinstance(content.get('data'), dict) and 'temp_parking' in content['data']):
            bem_data = content
        elif 'social_insurance_count' in content or 'company_name' in content:
            company_data = content
        elif content.get('status') == 'error' and not bem_data:
            # 记住错误，后续显示
            bem_data = content

    # --- BEM 数据对比 ---
    if bem_data and bem_data.get('status') == 'error':
        # BEM 脚本出错，在对比区显示错误信息
        comparison['bem_error'] = bem_data.get('error', '未知错误')
        comparison['bem_stderr'] = bem_data.get('_stderr', '')

    if bem_data and bem_data.get('status') != 'error':
        # 统一取 data 层
        bem = bem_data.get('data', bem_data) if bem_data.get('status') == 'success' else bem_data.get('data', bem_data)

        def _diff_status(excel_val, bem_val):
            if excel_val is None or bem_val is None:
                return 'missing'
            if excel_val == 0 and bem_val == 0:
                return 'match'
            if excel_val == 0 or bem_val == 0:
                return 'warning'
            pct = abs(excel_val - bem_val) / max(abs(excel_val), abs(bem_val)) * 100
            return 'match' if pct <= 5 else 'warning'

        def _diff_percent(excel_val, bem_val):
            if not excel_val or not bem_val:
                return None
            if excel_val == 0 and bem_val == 0:
                return 0.0
            return round(abs(excel_val - bem_val) / max(abs(excel_val), abs(bem_val)) * 100, 1)

        # 月均临停收入
        excel_temp = pi.get('monthly_avg_temp') or ct.get('monthly_temp_income')
        bem_temp = bem.get('temp_parking', {}).get('summary', {}).get('monthly_avg')
        comparison['summary'].append({
            'label': '月均临停收入',
            'excel_value': excel_temp,
            'bem_value': bem_temp,
            'unit': '元/月',
            'diff_percent': _diff_percent(excel_temp, bem_temp),
            'status': _diff_status(excel_temp, bem_temp),
        })

        # 月均月票收入
        excel_ticket = pi.get('monthly_avg_ticket') or ct.get('monthly_ticket_income')
        bem_ticket = bem.get('monthly_ticket', {}).get('summary', {}).get('monthly_avg')

        # BEM 月票数据全为 0 时跳过对比验证
        bem_ticket_monthly = bem.get('monthly_ticket', {}).get('monthly', [])
        bem_ticket_all_zero = (
            all(m.get('ticket_income', 0) == 0 for m in bem_ticket_monthly)
            if bem_ticket_monthly
            else (bem_ticket == 0 or bem_ticket is None)
        )
        if bem_ticket_all_zero:
            comparison['summary'].append({
                'label': '月均月票收入',
                'excel_value': excel_ticket,
                'bem_value': bem_ticket or 0,
                'unit': '元/月',
                'diff_percent': None,
                'status': 'skip_bem_zero',
            })
        else:
            comparison['summary'].append({
                'label': '月均月票收入',
                'excel_value': excel_ticket,
                'bem_value': bem_ticket,
                'unit': '元/月',
                'diff_percent': _diff_percent(excel_ticket, bem_ticket),
                'status': _diff_status(excel_ticket, bem_ticket),
            })

        # 临停收入趋势
        temp_trend = bem.get('temp_parking', {}).get('summary', {})
        if temp_trend.get('trend'):
            comparison['summary'].append({
                'label': '临停收入趋势',
                'excel_value': None,
                'bem_value': f"{temp_trend.get('trend', '')} ({temp_trend.get('trend_note', '')})",
                'unit': '',
                'diff_percent': None,
                'status': 'info',
            })

        # 月票收入趋势
        ticket_trend = bem.get('monthly_ticket', {}).get('summary', {})
        if ticket_trend.get('trend'):
            comparison['summary'].append({
                'label': '月票收入趋势',
                'excel_value': None,
                'bem_value': f"{ticket_trend.get('trend', '')} ({ticket_trend.get('trend_note', '')})",
                'unit': '',
                'diff_percent': None,
                'status': 'info',
            })

        # 月度明细 — 临停（BEM month 格式 "YYYY-MM"，Excel month 格式为整数 1-12）
        bem_monthly_temp = {}
        for m in bem.get('temp_parking', {}).get('monthly', []):
            month_key = m.get('month', '')
            # 提取月份整数用于匹配：int("2026-05".split("-")[1]) → 5
            try:
                month_num = int(str(month_key).split('-')[-1])
            except (ValueError, IndexError):
                continue
            bem_monthly_temp[month_num] = m

        for row in pi.get('monthly_income', []):
            month = row.get('month')
            excel_val = row.get('temp_income')
            bem_row = bem_monthly_temp.get(month, {})
            bem_val = bem_row.get('actual_income_wechat') or bem_row.get('total_income')
            comparison['monthly_detail']['temp_parking'].append({
                'month': str(month),
                'excel': excel_val,
                'bem': bem_val,
                'status': _diff_status(excel_val, bem_val),
            })

        # 月度明细 — 月票
        bem_monthly_ticket = {}
        for m in bem.get('monthly_ticket', {}).get('monthly', []):
            month_key = m.get('month', '')
            try:
                month_num = int(str(month_key).split('-')[-1])
            except (ValueError, IndexError):
                continue
            bem_monthly_ticket[month_num] = m

        for row in pi.get('monthly_income', []):
            month = row.get('month')
            excel_val = row.get('ticket_income')
            bem_row = bem_monthly_ticket.get(month, {})
            bem_val = bem_row.get('ticket_income')
            comparison['monthly_detail']['monthly_ticket'].append({
                'month': str(month),
                'excel': excel_val,
                'bem': bem_val,
                'status': _diff_status(excel_val, bem_val),
            })

        # 月票类型
        for tt in bem.get('ticket_types', []):
            comparison['ticket_types'].append({
                'name': tt.get('name', ''),
                'price': tt.get('price'),
                'is_internal': tt.get('is_internal', False),
                'active_count': tt.get('active_count'),
                'category': tt.get('category', ''),
            })

    # --- 企业信息 ---
    if company_data:
        comparison['company_info'] = {
            'name': company_data.get('company_name', ''),
            'social_insurance_count': company_data.get('social_insurance_count'),
            'status': company_data.get('status', ''),
            'registered_capital': company_data.get('registered_capital', ''),
            'established_date': company_data.get('established_date', ''),
        }

    return comparison


async def run_audit(
    business_type: str,
    parsed_data: dict,
    yield_event=None,
) -> AsyncGenerator[str, None]:
    """
    AI 驱动的审核流程。

    通过 SSE 事件流式输出：
    - yield_event(event_type, data) 由调用方提供

    返回 AsyncGenerator[str] 产出 SSE 格式的事件字符串。
    """
    system_prompt = _build_system_prompt(business_type)

    car_park_name = parsed_data.get('project_info', {}).get('car_park_name', '')
    user_content = f"""# 上传的车场资料数据

```json
{json.dumps(parsed_data, ensure_ascii=False, indent=2)}
```

**重要**：调用 fetch_bem_data 时，car_park_name 必须使用上方数据中 project_info.car_park_name 的值「{car_park_name}」，不要使用文件名中的车场名称。

请按照检查清单和风险规则，完成审核并输出结果。"""

    messages = [{"role": "user", "content": user_content}]

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    if not LLM_API_KEY or LLM_API_KEY == 'your_api_key':
        yield sse("error", {"message": "LLM API Key 未配置，请在 .env 中设置 LLM_API_KEY"})
        return

    client = AsyncOpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )

    full_text = ""

    while True:
        yield sse("status", {"phase": "thinking"})

        try:
            response = await client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOLS,
                stream=True,
                max_tokens=4096,
            )
        except Exception as e:
            yield sse("error", {"message": str(e)})
            return

        # 收集流式响应
        tool_calls_data = {}
        current_text = ""

        async for chunk in response:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            # 处理文本内容
            if delta.content:
                current_text += delta.content
                full_text += delta.content
                yield sse("token", {"text": delta.content})

            # 处理 tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {
                            "id": tc.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc.id:
                        tool_calls_data[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_data[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_data[idx]["arguments"] += tc.function.arguments

            # 流结束
            if choice.finish_reason == "stop":
                # 保存助手文本回复到消息历史
                if current_text:
                    messages.append({"role": "assistant", "content": current_text})

                yield sse("result", {"markdown": full_text})
                yield sse("done", {})
                return

            if choice.finish_reason == "tool_calls":
                break

        # 如果有文本，先加入消息
        if current_text:
            messages.append({"role": "assistant", "content": current_text})

        # 执行 tool calls
        if not tool_calls_data:
            yield sse("done", {})
            return

        # 构建 assistant message 的 tool_calls 部分
        assistant_tool_calls = []
        tool_results = []

        for idx in sorted(tool_calls_data.keys()):
            tc = tool_calls_data[idx]
            assistant_tool_calls.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": tc["arguments"],
                }
            })

            # 解析参数
            try:
                args = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                args = {}

            # 执行对应的脚本
            name = tc["name"]
            yield sse("tool_call", {"tool": name, "args": args, "status": "running"})

            try:
                if name == "fetch_bem_data":
                    result = await run_bem_fetch(
                        car_park_name=args.get("car_park_name", ""),
                        date_range=args.get("date_range"),
                    )
                elif name == "lookup_company":
                    result = await run_company_lookup(
                        company_name=args.get("company_name", ""),
                    )
                else:
                    result = {"error": f"Unknown tool: {name}"}
            except Exception as e:
                result = {"error": str(e)}

            yield sse("tool_call", {"tool": name, "args": args, "status": "done"})

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

        # 发射数据对比事件
        comparison = _build_comparison(parsed_data, tool_results)
        yield sse("comparison_data", comparison)

        # 添加 assistant 的 tool_calls 消息到历史
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": assistant_tool_calls,
        })

        # 添加 tool results 到历史
        messages.extend(tool_results)

        # 继续循环，让 LLM 基于工具结果继续生成
