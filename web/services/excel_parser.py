"""
Excel 解析器 — 解析资源置换运营测算表

支持两种 sheet 结构：
1. 金额券测算（停车券业务）：含"项目基本信息" + "测算工具（金额券）"
2. 时长采买测算（车位置换业务）：含"折扣采买测算表"
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl


def _serial_to_date(serial: float | int | None) -> str | None:
    if serial is None:
        return None
    try:
        # Excel serial date: 1 = 1900-01-01, but Excel has a leap year bug (1900-02-29)
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=int(serial))).strftime('%Y-%m-%d')
    except (ValueError, OverflowError):
        return str(serial)


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    f = _safe_float(val)
    return int(f) if f is not None else None


def _cell_str(ws, row: int, col: int) -> str | None:
    val = ws.cell(row=row, column=col).value
    if val is None:
        return None
    return str(val).strip() or None


def _cell_num(ws, row: int, col: int) -> float | None:
    return _safe_float(ws.cell(row=row, column=col).value)


def parse_project_info(ws) -> dict:
    """解析 Sheet 1: 项目基本信息"""
    result = {
        'car_park_name': _cell_str(ws, 2, 2),
        'car_park_address': _cell_str(ws, 3, 2),
        'property_type': _cell_str(ws, 6, 3),       # 产权方/承包方
        'contract_expire_date': _serial_to_date(_cell_num(ws, 7, 3)),
        'parking_fee_rule': _cell_str(ws, 8, 3),
        'allow_posting': _cell_str(ws, 9, 3),
        'has_own_channel': _cell_str(ws, 10, 3),
        'parking_spaces': _safe_int(_cell_num(ws, 11, 3)),
    }

    # 月度收入（rows 14-25，月份 1-12）
    monthly_income = []
    for row in range(14, 26):
        month = _safe_int(_cell_num(ws, row, 1))
        if month is None:
            continue
        temp_income = _cell_num(ws, row, 2)
        ticket_income = _cell_num(ws, row, 3)
        monthly_income.append({
            'month': month,
            'temp_income': temp_income,
            'ticket_income': ticket_income,
        })
    result['monthly_income'] = monthly_income
    result['monthly_avg_temp'] = _cell_num(ws, 26, 2)
    result['monthly_avg_ticket'] = _cell_num(ws, 26, 3)

    return result


def parse_calculation_tool(ws) -> dict:
    """解析 Sheet 2: 测算工具（金额券）"""
    result = {
        'department': _cell_str(ws, 4, 3),
        'submitter': _cell_str(ws, 4, 5),
        'opportunity_name': _cell_str(ws, 5, 3),
        'installment_deduction': _cell_str(ws, 5, 5),
        'crm_service_fee': _cell_num(ws, 7, 5),
        'equipment_service_amount': _cell_num(ws, 10, 4),
        'cash_purchase_amount': _cell_num(ws, 11, 4),
        'business_fee': _cell_num(ws, 12, 4),
        'discount_rate': _cell_num(ws, 13, 4),
        'contract_months': _safe_int(_cell_num(ws, 14, 4)),
        'voucher_consume_months': _safe_int(_cell_num(ws, 15, 4)),
        'vat_rate': _cell_num(ws, 16, 4),
        'monthly_temp_income': _cell_num(ws, 17, 4),
        'monthly_ticket_income': _cell_num(ws, 18, 4),
        'monthly_total_income': _cell_num(ws, 19, 4),
        'contract_amount': _cell_num(ws, 20, 4),
        'voucher_total_value': _cell_num(ws, 21, 4),
        'voucher_monthly_share': _cell_num(ws, 22, 4),
        'project_gross_profit': _cell_num(ws, 24, 4),
        # 评估区
        'monthly_consume_ratio': _cell_num(ws, 4, 8),
        'actual_purchase_discount': _cell_num(ws, 5, 8),
    }
    return result


def parse_discount_purchase(ws) -> dict | None:
    """解析 Sheet 3: 折扣采买测算表（车位置换业务）"""
    project_name = _cell_str(ws, 2, 2)
    if not project_name or 'XXXXXXX' in (project_name or ''):
        return None

    result = {
        'project_name': project_name,
        'parameters': {},
    }

    # 右侧参数表（rows 4-21, columns N-R）
    for row in range(4, 22):
        seq = _cell_str(ws, row, 14)   # N: 序号
        name = _cell_str(ws, row, 15)  # O: 项目
        value = ws.cell(row=row, column=16).value  # P: 数值
        unit = _cell_str(ws, row, 17)  # Q: 单位
        note = _cell_str(ws, row, 18)  # R: 备注
        if name:
            result['parameters'][name] = {
                'value': value,
                'unit': unit,
                'note': note,
            }

    # 左侧测算数据
    result['total_original_amount'] = _cell_num(ws, 4, 4)
    result['total_aike_amount'] = _cell_num(ws, 5, 4)

    return result


def parse_audit_excel(file_path: str | Path) -> dict:
    """
    解析资源置换运营测算表。

    Returns:
        {
            'file_name': str,
            'project_info': dict,        # Sheet 1
            'calculation_tool': dict,    # Sheet 2（停车券业务）
            'discount_purchase': dict,   # Sheet 3（车位置换业务）
            'business_type': str,        # 自动判断: parking_voucher / spot_exchange / both
        }
    """
    path = Path(file_path)
    wb = openpyxl.load_workbook(str(path), data_only=True)

    result = {'file_name': path.name}

    # Sheet 1: 项目基本信息
    if '1.项目基本信息' in wb.sheetnames:
        result['project_info'] = parse_project_info(wb['1.项目基本信息'])

    # Sheet 2: 测算工具（金额券）— 停车券业务
    calc_sheet_name = None
    for name in wb.sheetnames:
        if '测算工具' in name and '金额券' in name:
            calc_sheet_name = name
            break
    if calc_sheet_name:
        result['calculation_tool'] = parse_calculation_tool(wb[calc_sheet_name])

    # Sheet 3: 折扣采买测算表 — 车位置换业务
    discount_sheet = None
    for name in wb.sheetnames:
        if '折扣采买' in name or '时长采买' in name:
            discount_sheet = name
            break
    if discount_sheet:
        parsed = parse_discount_purchase(wb[discount_sheet])
        if parsed:
            result['discount_purchase'] = parsed

    # 自动判断业务类型
    has_voucher = 'calculation_tool' in result
    has_spot = 'discount_purchase' in result
    if has_voucher and has_spot:
        result['business_type'] = 'both'
    elif has_voucher:
        result['business_type'] = 'parking_voucher'
    elif has_spot:
        result['business_type'] = 'spot_exchange'
    else:
        result['business_type'] = 'unknown'

    wb.close()
    return result


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'doc/2025-12-09【大良保利广场】停车券置换运营测算表更新版-承包方-快过期.xlsx'
    data = parse_audit_excel(path)
    print(json.dumps(data, ensure_ascii=False, indent=2))
