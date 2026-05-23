"""通用规则：项目基本信息表 9 字段 + 月度收入对比 + 合作主体 + 企查查。

字段权威源：prompts/audit_field_rules.md
通用词列表（合作主体填写不规范）：承包方 / 产权方 / 产权方/承包方 / 产权方-承包方 等
"""

import re
from datetime import datetime, timedelta, timezone

from web.services.validators.core import CheckItem

TOLERANCE_PERCENT = 5  # 与 ai_orchestrator._build_comparison 保持一致

BEIJING_TZ = timezone(timedelta(hours=8))


def _parse_date(value):
    """解析多种日期格式，返回 datetime 或 None。

    支持：YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD /
         YYYY年M月D日 / YYYY年M月D号（含零填充变体）
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if '年' in s:
        normalized = re.sub(r'[年]', '-', s)
        normalized = re.sub(r'[月]', '-', normalized)
        normalized = re.sub(r'[日号]', '', normalized)
        try:
            return datetime.strptime(normalized, '%Y-%m-%d')
        except ValueError:
            return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# 合作主体填写不规范的通用词
GENERIC_PROPERTY_TYPES = {
    '承包方', '产权方',
    '产权方/承包方', '产权方-承包方',
    '承包方/产权方', '承包方-产权方',
}


def _is_generic_property_type(value: str | None) -> bool:
    if not value:
        return False
    cleaned = str(value).strip().replace(' ', '').replace('（', '').replace('）', '')
    return cleaned in GENERIC_PROPERTY_TYPES


def _missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _diff_percent(a, b):
    if a is None or b is None:
        return None
    if a == 0 and b == 0:
        return 0.0
    if a == 0 or b == 0:
        return 100.0
    return round(abs(a - b) / max(abs(a), abs(b)) * 100, 1)


def _diff_status(a, b, tol=TOLERANCE_PERCENT):
    if a is None or b is None:
        return None
    if a == 0 and b == 0:
        return 'pass'
    if a == 0 or b == 0:
        return 'warn'
    return 'pass' if _diff_percent(a, b) <= tol else 'warn'


# === 项目基本信息表 9 字段 ===

def check_car_park_name(ctx) -> CheckItem:
    val = ctx['pi'].get('car_park_name')
    return CheckItem(
        code='', label='车场名称',
        status='risk' if _missing(val) else 'pass',
        excel_value=val,
        note='缺失' if _missing(val) else '',
    )


def check_car_park_address(ctx) -> CheckItem:
    val = ctx['pi'].get('car_park_address')
    return CheckItem(
        code='', label='车场地址',
        status='risk' if _missing(val) else 'pass',
        excel_value=val,
        note='缺失' if _missing(val) else '',
    )


def check_property_type(ctx) -> CheckItem:
    val = ctx['pi'].get('property_type')
    if _missing(val):
        return CheckItem(code='', label='合作客户主体', status='risk',
                         excel_value=val, note='缺失')
    if _is_generic_property_type(val):
        return CheckItem(code='', label='合作客户主体', status='risk',
                         excel_value=val,
                         note='填写不规范：应为具体公司名称，而非"承包方"/"产权方"等通用词，否则无法进行企查查核实')
    return CheckItem(code='', label='合作客户主体', status='pass', excel_value=val)


def check_contract_expire_date(ctx) -> CheckItem:
    val = ctx['pi'].get('contract_expire_date')
    property_type = ctx['pi'].get('property_type') or ''
    is_contractor = '承包' in property_type
    if _missing(val):
        if is_contractor:
            return CheckItem(code='', label='承包到期时间', status='risk',
                             excel_value=val, note='承包方时必填')
        return CheckItem(code='', label='承包到期时间', status='pass',
                         excel_value='-', note='非承包方，无需填写')
    # 日期格式解析
    expire = _parse_date(val)
    if expire is None:
        return CheckItem(code='', label='承包到期时间', status='risk',
                         excel_value=val, note='日期格式无法识别')
    # 日期范围校验（以北京时间为准）
    now = datetime.now(BEIJING_TZ).replace(tzinfo=None)
    if expire <= now + timedelta(days=1):
        return CheckItem(code='', label='承包到期时间', status='risk',
                         excel_value=val, note='承包到期时间不足1天或已过期')
    if expire <= now + timedelta(days=365):
        return CheckItem(code='', label='承包到期时间', status='warn',
                         excel_value=val, note='承包到期时间不足1年')
    return CheckItem(code='', label='承包到期时间', status='pass', excel_value=val)


def check_parking_fee_rule(ctx) -> CheckItem:
    val = ctx['pi'].get('parking_fee_rule')
    return CheckItem(
        code='', label='停车场收费规则',
        status='risk' if _missing(val) else 'pass',
        excel_value=val,
        note='缺失' if _missing(val) else '',
    )


def check_allow_posting(ctx) -> CheckItem:
    val = ctx['pi'].get('allow_posting')
    return CheckItem(
        code='', label='是否允许张贴物料',
        status='risk' if _missing(val) else 'pass',
        excel_value=val,
        note='缺失' if _missing(val) else '',
    )


def check_has_own_channel(ctx) -> CheckItem:
    val = ctx['pi'].get('has_own_channel')
    return CheckItem(
        code='', label='是否存在自有小程序/ETC支付渠道',
        status='risk' if _missing(val) else 'pass',
        excel_value=val,
        note='缺失' if _missing(val) else '',
    )


def check_parking_spaces(ctx) -> CheckItem:
    if ctx['business_type'] == 'spot_exchange':
        return None
    val = ctx['pi'].get('parking_spaces')
    if val is None:
        return CheckItem(code='', label='停车场车位数量', status='risk',
                         excel_value=val, note='缺失')
    if val < 10:
        return CheckItem(code='', label='停车场车位数量', status='risk',
                         excel_value=val, note='车位数量不足10个')
    if val <= 100:
        return CheckItem(code='', label='停车场车位数量', status='warn',
                         excel_value=val, note='车位数量10-100个，规模偏小')
    return CheckItem(code='', label='停车场车位数量', status='pass', excel_value=val)


def check_monthly_income_completeness(ctx) -> CheckItem:
    rows = ctx['pi'].get('monthly_income') or []
    if len(rows) < 12:
        return CheckItem(code='', label='月度收入', status='warn',
                         excel_value=f'{len(rows)}/12 个月',
                         note='月度收入数据不足 12 个月，请确认是否补充')
    return CheckItem(code='', label='月度收入', status='pass',
                     excel_value=f'{len(rows)} 个月')


# === 月度收入 BEM 对比（汇总项） ===

def check_monthly_temp_compare(ctx) -> CheckItem:
    pi, ct, bem = ctx['pi'], ctx['ct'], ctx['bem']
    excel_val = pi.get('monthly_avg_temp') or ct.get('monthly_temp_income')
    bem_val = (bem or {}).get('temp_parking', {}).get('summary', {}).get('monthly_avg')
    if bem is None:
        return CheckItem(code='', label='月均临停收入（vs BEM）', status='manual',
                         excel_value=excel_val, ref_source='BEM',
                         note='BEM 数据未获取，待人工对比')
    if excel_val is None:
        return CheckItem(code='', label='月均临停收入（vs BEM）', status='risk',
                         excel_value=excel_val, ref_value=bem_val, ref_source='BEM',
                         note='上传资料缺失月均临停收入')
    if bem_val is None:
        return CheckItem(code='', label='月均临停收入（vs BEM）', status='manual',
                         excel_value=excel_val, ref_source='BEM',
                         note='BEM 无对应数据')
    pct = _diff_percent(excel_val, bem_val)
    status = _diff_status(excel_val, bem_val)
    note = f'差异 {pct}%（容差 {TOLERANCE_PERCENT}%）' if pct is not None else ''
    if status == 'warn':
        note = f'差异 {pct}% 超 {TOLERANCE_PERCENT}%'
    return CheckItem(code='', label='月均临停收入（vs BEM）', status=status,
                     excel_value=excel_val, ref_value=bem_val, ref_source='BEM',
                     note=note)


def check_monthly_ticket_compare(ctx) -> CheckItem:
    pi, ct, bem = ctx['pi'], ctx['ct'], ctx['bem']
    excel_val = pi.get('monthly_avg_ticket') or ct.get('monthly_ticket_income')
    if bem is None:
        return CheckItem(code='', label='月均月票收入（vs BEM）', status='manual',
                         excel_value=excel_val, ref_source='BEM',
                         note='BEM 数据未获取，待人工对比')
    bem_summary = (bem or {}).get('monthly_ticket', {}).get('summary', {})
    bem_val = bem_summary.get('monthly_avg')
    bem_monthly = (bem or {}).get('monthly_ticket', {}).get('monthly', [])
    bem_all_zero = (
        all(m.get('ticket_income', 0) == 0 for m in bem_monthly)
        if bem_monthly else (bem_val == 0 or bem_val is None)
    )
    if bem_all_zero:
        return CheckItem(code='', label='月均月票收入（vs BEM）', status='skip',
                         excel_value=excel_val, ref_value=bem_val or 0, ref_source='BEM',
                         note='BEM 月票数据全为 0，跳过对比')
    if excel_val is None:
        return CheckItem(code='', label='月均月票收入（vs BEM）', status='risk',
                         excel_value=excel_val, ref_value=bem_val, ref_source='BEM',
                         note='上传资料缺失月均月票收入')
    pct = _diff_percent(excel_val, bem_val)
    status = _diff_status(excel_val, bem_val)
    note = f'差异 {pct}%（容差 {TOLERANCE_PERCENT}%）'
    if status == 'warn':
        note = f'差异 {pct}% 超 {TOLERANCE_PERCENT}%'
    return CheckItem(code='', label='月均月票收入（vs BEM）', status=status,
                     excel_value=excel_val, ref_value=bem_val, ref_source='BEM',
                     note=note)


# === 企查查结果 ===

def check_company_lookup_result(ctx) -> CheckItem | None:
    """合作主体是具体公司名时，输出企查查结果作为人工参考项。"""
    pt = ctx['pi'].get('property_type')
    if _missing(pt) or _is_generic_property_type(pt):
        return None  # 已在 check_property_type 中标 risk，这里不重复
    company = ctx.get('company')
    if not company:
        return CheckItem(code='', label='企业信息查询', status='manual',
                         excel_value=pt, ref_source='企查查',
                         note='企查查未查询或失败，请人工核实参保人数与经营状态')
    if company.get('status') == 'error' or company.get('error'):
        return CheckItem(code='', label='企业信息查询', status='manual',
                         excel_value=pt, ref_source='企查查',
                         note=f'企查查失败：{company.get("error", "")[:80]}')
    parts = []
    insurance = company.get('social_insurance_count')
    if insurance is not None and insurance != '':
        parts.append(f'参保人数：{insurance}人')
    biz_status = company.get('status')
    if biz_status:
        parts.append(f'经营状态：{biz_status}')
    capital = company.get('registered_capital')
    if capital:
        parts.append(f'注册资本：{capital}')
    established = company.get('established_date')
    if established:
        parts.append(f'成立日期：{established}')
    return CheckItem(code='', label='企业信息查询', status='manual',
                     excel_value=pt, ref_source='企查查',
                     note='；'.join(parts) if parts else '已查询，仅供参考')


RULES = [
    check_car_park_name,
    check_car_park_address,
    check_property_type,
    check_contract_expire_date,
    check_parking_fee_rule,
    check_allow_posting,
    check_has_own_channel,
    check_parking_spaces,
    check_monthly_income_completeness,
    check_monthly_temp_compare,
    check_monthly_ticket_compare,
    check_company_lookup_result,
]
