"""停车券业务规则：测算工具表 10 字段 + 2 条交叉规则。

字段权威源：prompts/audit_field_rules.md → 停车券业务测算工具表
"""

from datetime import datetime

from web.services.validators.core import CheckItem
from web.services.validators.rules_common import _missing, _parse_date


def check_equipment_service_amount(ctx) -> CheckItem:
    val = ctx['ct'].get('equipment_service_amount')
    return CheckItem(
        code='', label='设备和服务置换金额',
        status='risk' if val is None else 'pass',
        excel_value=val,
        note='缺失' if val is None else '',
    )


def check_cash_purchase_amount(ctx) -> CheckItem:
    val = ctx['ct'].get('cash_purchase_amount')
    return CheckItem(
        code='', label='现金采买金额',
        status='risk' if val is None else 'pass',
        excel_value=val,
        note='缺失' if val is None else '',
    )


def check_payment_method(ctx) -> CheckItem | None:
    val = ctx['ct'].get('payment_method')
    if _missing(val):
        return None  # 可选字段，无值不输出
    return CheckItem(code='', label='付款方式', status='pass', excel_value=val)


def check_business_fee(ctx) -> CheckItem | None:
    val = ctx['ct'].get('business_fee')
    if val is None or val == 0:
        return None  # 无业务费，不输出
    return CheckItem(code='', label='业务费', status='manual',
                     excel_value=val,
                     note='存在业务费，需运营人工评估合理性')


def check_discount_rate(ctx) -> CheckItem:
    val = ctx['ct'].get('discount_rate')
    return CheckItem(
        code='', label='采买折扣',
        status='risk' if val is None else 'pass',
        excel_value=val,
        note='缺失' if val is None else '',
    )


def check_contract_months(ctx) -> CheckItem:
    val = ctx['ct'].get('contract_months')
    if val is None:
        return CheckItem(code='', label='合同有效年限（月）', status='risk',
                         excel_value=val, note='缺失')
    if val < 1:
        return CheckItem(code='', label='合同有效年限（月）', status='risk',
                         excel_value=val, note='合同有效年限必须 ≥ 1 个月')
    return CheckItem(code='', label='合同有效年限（月）', status='pass',
                     excel_value=f'{val} 个月')


def check_voucher_consume_months(ctx) -> CheckItem:
    val = ctx['ct'].get('voucher_consume_months')
    if val is None:
        return CheckItem(code='', label='券消耗年限（月）', status='risk',
                         excel_value=val, note='缺失')
    if val < 1:
        return CheckItem(code='', label='券消耗年限（月）', status='risk',
                         excel_value=val, note='券消耗年限必须 ≥ 1 个月')
    return CheckItem(code='', label='券消耗年限（月）', status='pass',
                     excel_value=f'{val} 个月')


def check_vat_rate(ctx) -> CheckItem:
    val = ctx['ct'].get('vat_rate')
    display = f'{round(val * 100, 2)}%' if val is not None else None
    return CheckItem(
        code='', label='增值税普通发票',
        status='risk' if val is None else 'pass',
        excel_value=display,
        note='缺失' if val is None else '',
    )


def check_monthly_temp_income(ctx) -> CheckItem:
    val = ctx['ct'].get('monthly_temp_income')
    return CheckItem(
        code='', label='车场月均临停收入（测算表）',
        status='risk' if val is None else 'pass',
        excel_value=val,
        note='缺失' if val is None else '',
    )


def check_monthly_ticket_income(ctx) -> CheckItem:
    val = ctx['ct'].get('monthly_ticket_income')
    return CheckItem(
        code='', label='车场月均月租收入（测算表）',
        status='risk' if val is None else 'pass',
        excel_value=val,
        note='缺失' if val is None else '',
    )


# === 交叉规则 ===

def cross_contract_within_expire(ctx) -> CheckItem | None:
    """合同有效年限须在承包期限内（仅承包方业务）。"""
    pi = ctx['pi']
    property_type = pi.get('property_type') or ''
    if '承包' not in property_type:
        return None
    contract_months = ctx['ct'].get('contract_months')
    expire = _parse_date(pi.get('contract_expire_date'))
    if contract_months is None or expire is None:
        return None  # 缺数据时上面已经标了 risk，这里不重复
    today = datetime.now()
    remaining_months = (expire.year - today.year) * 12 + (expire.month - today.month)
    if contract_months > remaining_months:
        return CheckItem(
            code='', label='合同年限 vs 承包到期',
            status='risk',
            excel_value=f'合同 {contract_months} 月',
            ref_value=f'剩余承包 {remaining_months} 月（至 {expire.strftime("%Y-%m-%d")}）',
            note=f'合同年限超出承包剩余期限 {contract_months - remaining_months} 个月',
        )
    return CheckItem(
        code='', label='合同年限 vs 承包到期',
        status='pass',
        excel_value=f'合同 {contract_months} 月',
        ref_value=f'剩余承包 {remaining_months} 月',
        note='合同年限在承包期限内',
    )


def cross_voucher_gt_contract(ctx) -> CheckItem | None:
    """券消耗年限必须 > 合同有效年限。"""
    contract_months = ctx['ct'].get('contract_months')
    voucher_months = ctx['ct'].get('voucher_consume_months')
    if contract_months is None or voucher_months is None:
        return None
    if voucher_months <= contract_months:
        return CheckItem(
            code='', label='券消耗年限 vs 合同年限',
            status='risk',
            excel_value=f'券消耗 {voucher_months} 月',
            ref_value=f'合同 {contract_months} 月',
            note='券消耗年限必须晚于合同有效年限',
        )
    return CheckItem(
        code='', label='券消耗年限 vs 合同年限',
        status='pass',
        excel_value=f'券消耗 {voucher_months} 月',
        ref_value=f'合同 {contract_months} 月',
        note='券消耗年限晚于合同年限',
    )


RULES = [
    check_equipment_service_amount,
    check_cash_purchase_amount,
    check_payment_method,
    check_business_fee,
    check_discount_rate,
    check_contract_months,
    check_voucher_consume_months,
    check_vat_rate,
    check_monthly_temp_income,
    check_monthly_ticket_income,
    cross_contract_within_expire,
    cross_voucher_gt_contract,
]
