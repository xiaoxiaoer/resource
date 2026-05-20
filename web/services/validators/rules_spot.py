"""车位置换业务规则：测算工具表 6 字段 + 3 条交叉规则。

字段权威源：prompts/audit_field_rules.md → 车位置换业务测算工具表
"""

from datetime import datetime

from web.services.validators.core import CheckItem
from web.services.validators.rules_common import _diff_percent, _diff_status, _parse_date, TOLERANCE_PERCENT



def check_equipment_amount(ctx) -> CheckItem:
    """设备和服务置换金额 — 完整性 + 与 CRM 结算价对比（相同时 manual）。"""
    sec = ctx['sec']
    val = sec.get('equipment_amount')
    crm = sec.get('crm_settlement_total')
    if val is None:
        return CheckItem(code='', label='设备和服务置换金额',
                         status='risk', excel_value=val, note='缺失')
    if crm is not None and val == crm:
        return CheckItem(
            code='', label='设备和服务置换金额',
            status='manual',
            excel_value=val, ref_value=crm, ref_source='CRM',
            note='与 CRM 结算价完全相同，需与业务确认是否填错',
        )
    return CheckItem(code='', label='设备和服务置换金额',
                     status='pass', excel_value=val,
                     ref_value=crm if crm is not None else None,
                     ref_source='CRM' if crm is not None else '')


def check_vat_rate(ctx) -> CheckItem:
    val = ctx['sec'].get('vat_rate')
    return CheckItem(
        code='', label='增值税专用发票',
        status='risk' if val is None else 'pass',
        excel_value=val,
        note='缺失' if val is None else '',
    )


def check_monthly_card_fee(ctx) -> CheckItem:
    """对外办理月卡费用 — 完整性 + 与 BEM 非内部月票价对比。"""
    val = ctx['sec'].get('monthly_card_fee')
    if val is None:
        return CheckItem(code='', label='对外办理月卡费用',
                         status='risk', excel_value=val, note='缺失')
    bem = ctx['bem']
    if not bem:
        return CheckItem(code='', label='对外办理月卡费用',
                         status='manual', excel_value=val, ref_source='BEM',
                         note='BEM 数据未获取，待人工核实对外月票价')
    # 取所有非内部的月票套餐价
    external_prices = [
        tt.get('price') for tt in bem.get('ticket_types', [])
        if not tt.get('is_internal') and tt.get('price') is not None
    ]
    if not external_prices:
        return CheckItem(code='', label='对外办理月卡费用',
                         status='manual', excel_value=val, ref_source='BEM',
                         note='BEM 未查到对外月票套餐，待人工核实')
    # 与最接近 val 的对外月票价对比
    nearest = min(external_prices, key=lambda p: abs(p - val))
    status = _diff_status(val, nearest)
    pct = _diff_percent(val, nearest)
    note = f'BEM 对外月票价：{external_prices}'
    if status == 'warn':
        note = f'与 BEM 对外月票价差异 {pct}%（容差 {TOLERANCE_PERCENT}%）；BEM 价格：{external_prices}'
    return CheckItem(code='', label='对外办理月卡费用',
                     status=status, excel_value=val,
                     ref_value=nearest, ref_source='BEM', note=note)


def check_replacement_spaces(ctx) -> CheckItem:
    val = ctx['sec'].get('replacement_spaces')
    if val is None:
        return CheckItem(code='', label='置换车位数', status='risk',
                         excel_value=val, note='缺失')
    if val < 1:
        return CheckItem(code='', label='置换车位数', status='risk',
                         excel_value=val, note='置换车位数必须 ≥ 1')
    return CheckItem(code='', label='置换车位数', status='pass', excel_value=val)


def check_profit_share_ratio(ctx) -> CheckItem:
    val = ctx['sec'].get('profit_share_ratio')
    return CheckItem(
        code='', label='回本后甲方分润比例',
        status='risk' if val is None else 'pass',
        excel_value=val,
        note='缺失' if val is None else '',
    )


def check_contract_months(ctx) -> CheckItem:
    val = ctx['sec'].get('contract_months')
    if val is None:
        return CheckItem(code='', label='合同有效年限（月）', status='risk',
                         excel_value=val, note='缺失')
    if val < 36:
        return CheckItem(
            code='', label='合同有效年限（月）',
            status='warn', excel_value=f'{val} 个月',
            note='车位置换业务要求合同有效年限 ≥ 36 个月',
        )
    return CheckItem(code='', label='合同有效年限（月）',
                     status='pass', excel_value=f'{val} 个月')


# === 交叉规则 ===

def cross_contract_ge_36(ctx) -> CheckItem | None:
    """该检查已合并入 check_contract_months，避免重复输出。"""
    return None


def cross_contract_within_expire(ctx) -> CheckItem | None:
    pi = ctx['pi']
    property_type = pi.get('property_type') or ''
    if '承包' not in property_type:
        return None
    contract_months = ctx['sec'].get('contract_months')
    expire = _parse_date(pi.get('contract_expire_date'))
    if contract_months is None or expire is None:
        return None
    today = datetime.now()
    remaining = (expire.year - today.year) * 12 + (expire.month - today.month)
    if contract_months > remaining:
        return CheckItem(
            code='', label='合同年限 vs 承包到期',
            status='risk',
            excel_value=f'合同 {contract_months} 月',
            ref_value=f'剩余承包 {remaining} 月（至 {expire.strftime("%Y-%m-%d")}）',
            note=f'合同年限超出承包剩余期限 {contract_months - remaining} 个月',
        )
    return CheckItem(
        code='', label='合同年限 vs 承包到期',
        status='pass',
        excel_value=f'合同 {contract_months} 月',
        ref_value=f'剩余承包 {remaining} 月',
        note='合同年限在承包期限内',
    )


RULES = [
    check_equipment_amount,
    check_vat_rate,
    check_monthly_card_fee,
    check_replacement_spaces,
    check_profit_share_ratio,
    check_contract_months,
    cross_contract_within_expire,
]
