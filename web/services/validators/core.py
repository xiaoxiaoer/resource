"""程序化校验引擎核心。

规则定义为纯函数，每条规则一个 check_xxx 函数，接受 ctx dict，返回 CheckItem 或 None。
core.py 按业务类型维护规则列表，依次调用并自动编号。

规则权威源：prompts/audit_field_rules.md、templates/risk_rules.json（人类文档，代码不再解析）
"""

from dataclasses import dataclass, field
from typing import Any, Callable


Status = str  # 'pass' | 'warn' | 'risk' | 'manual' | 'skip'

STATUS_ICON = {
    'pass': '✅',
    'warn': '⚠️',
    'risk': '❌',
    'manual': '📋',
    'skip': '🔵',
}


@dataclass
class CheckItem:
    code: str
    label: str
    status: Status
    excel_value: Any = None
    ref_value: Any = None
    ref_source: str = ''  # 'BEM' / 'CRM' / '企查查' / ''
    note: str = ''


@dataclass
class ValidationResult:
    business_type: str
    basic_info: dict = field(default_factory=dict)
    checks: list[CheckItem] = field(default_factory=list)
    evaluation: dict = field(default_factory=dict)
    trend: list[str] = field(default_factory=list)

    notes: list[str] = field(default_factory=list)

    def count(self, status: Status) -> int:
        return sum(1 for c in self.checks if c.status == status)

    def by_status(self, status: Status) -> list[CheckItem]:
        return [c for c in self.checks if c.status == status]


RuleFn = Callable[[dict], CheckItem | list[CheckItem] | None]


def _normalize(items) -> list[CheckItem]:
    if items is None:
        return []
    if isinstance(items, CheckItem):
        return [items]
    return list(items)


def _run_rules(ctx: dict, rules: list[RuleFn]) -> list[CheckItem]:
    out: list[CheckItem] = []
    for fn in rules:
        out.extend(_normalize(fn(ctx)))
    # 重编号 C1..Cn
    for i, item in enumerate(out, start=1):
        item.code = f'C{i}'
    return out


def run_validation(
    business_type: str,
    parsed_data: dict,
    bem_data: dict | None = None,
    company_data: dict | None = None,
) -> ValidationResult:
    """程序化校验入口。

    Args:
        business_type: 'parking_voucher' | 'spot_exchange'
        parsed_data: excel_parser 输出
        bem_data: skill_runner.run_bem_fetch 返回值（含 status/data 字段），None 表示未获取
        company_data: skill_runner.run_company_lookup 返回值，None 表示未查询
    """
    # 延迟导入避免循环引用
    from web.services.validators import rules_common, rules_voucher, rules_spot

    pi = parsed_data.get('project_info') or {}
    ct = parsed_data.get('calculation_tool') or {}
    sec = parsed_data.get('spot_exchange_calc') or {}

    bem = _extract_bem(bem_data)
    bem_error = _extract_bem_error(bem_data)

    ctx = {
        'business_type': business_type,
        'parsed_data': parsed_data,
        'pi': pi,
        'ct': ct,
        'sec': sec,
        'bem': bem,
        'bem_error': bem_error,
        'company': company_data,
    }

    rules: list[RuleFn] = list(rules_common.RULES)
    if business_type == 'parking_voucher':
        rules.extend(rules_voucher.RULES)
    elif business_type == 'spot_exchange':
        rules.extend(rules_spot.RULES)

    checks = _run_rules(ctx, rules)

    notes: list[str] = []
    if bem is not None:
        notes.append('月票配置数据仅展示前100条，如需完整数据请联系技术支持')

    result = ValidationResult(
        business_type=business_type,
        basic_info=_basic_info(business_type, pi),
        checks=checks,
        evaluation=_evaluation(business_type, ct, sec),
        trend=_trend(bem),
        notes=notes,
    )
    return result


def _basic_info(business_type: str, pi: dict) -> dict:
    name = '停车券业务' if business_type == 'parking_voucher' else '车位置换业务'
    property_type = pi.get('property_type') or ''
    if '承包' in property_type and '产权' not in property_type:
        owner = '承包方'
    elif '产权' in property_type and '承包' not in property_type:
        owner = '产权方'
    else:
        owner = '-'
    return {
        '业务类型': name,
        '车场名称': pi.get('car_park_name') or '-',
        '合作客户主体': property_type or '-',
        '产权/承包': owner,
    }


def _evaluation(business_type: str, ct: dict, sec: dict) -> dict:
    ev = {}
    if ct.get('evaluation_scores'):
        ev['risk_evaluation'] = ct['evaluation_scores']
    if ct.get('risk_rating'):
        ev['risk_rating'] = ct['risk_rating']
    for key in ('gross_margin_before', 'gross_margin_after', 'discount_factor',
                'discount_factor_auth', 'equivalent_value', 'gross_margin_after_auth',
                'equipment_accrual_base', 'voucher_accrual'):
        if ct.get(key) is not None:
            ev[key] = ct[key]
    return ev


def _trend(bem: dict | None) -> list[str]:
    if not bem:
        return []
    out = []
    temp = bem.get('temp_parking', {}).get('summary', {})
    if temp.get('trend'):
        note = temp.get('trend_note', '')
        out.append(f"临停收入趋势：{temp['trend']}{(' (' + note + ')') if note else ''}")
    ticket = bem.get('monthly_ticket', {}).get('summary', {})
    if ticket.get('trend'):
        note = ticket.get('trend_note', '')
        out.append(f"月票收入趋势：{ticket['trend']}{(' (' + note + ')') if note else ''}")
    return out


def _extract_bem(bem_data: dict | None) -> dict | None:
    if not bem_data:
        return None
    if bem_data.get('status') == 'error':
        return None
    return bem_data.get('data', bem_data)


def _extract_bem_error(bem_data: dict | None) -> str | None:
    if bem_data and bem_data.get('status') == 'error':
        return bem_data.get('error', '未知错误')
    return None
