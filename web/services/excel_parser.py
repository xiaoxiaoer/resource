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

# openpyxl 已知 bug：新版 Excel 的 DataValidation 带 `id` 属性，openpyxl 不识别
# monkey-patch 让它忽略该属性
try:
    _orig_init = openpyxl.worksheet.datavalidation.DataValidation.__init__
    def _patched_init(self, *args, **kwargs):
        kwargs.pop('id', None)
        _orig_init(self, *args, **kwargs)
    openpyxl.worksheet.datavalidation.DataValidation.__init__ = _patched_init
except Exception:
    pass


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


def _find_label_row(ws, col: int, keyword: str, start: int = 1, end: int = 30) -> int | None:
    """在指定列中查找包含关键词的第一个行号"""
    for row in range(start, end + 1):
        val = ws.cell(row=row, column=col).value
        if val and keyword in str(val):
            return row
    return None


def parse_project_info(ws) -> dict:
    """解析 Sheet 1: 项目基本信息（通过标签关键词查找，兼容不同版本格式）"""
    result = {
        'car_park_name': _cell_str(ws, 2, 2),
        'car_park_address': _cell_str(ws, 3, 2),
    }

    # 通过 col 2 标签关键词查找各行（兼容标签文字变化）
    field_defs = [
        ('property_type',     ['合作客户', '产权方']),
        ('contract_expire_date', ['承包到期']),
        ('parking_fee_rule',  ['收费规则']),
        ('allow_posting',     ['张贴物料', '允许张贴']),
        ('has_own_channel',   ['自有', 'ETC']),
        ('parking_spaces',    ['车位数量', '车位']),
    ]
    for key, keywords in field_defs:
        for kw in keywords:
            row = _find_label_row(ws, 2, kw, 4, 15)
            if row:
                if key == 'contract_expire_date':
                    result[key] = _serial_to_date(_cell_num(ws, row, 3)) or _cell_str(ws, row, 3)
                elif key == 'parking_spaces':
                    result[key] = _safe_int(_cell_num(ws, row, 3))
                else:
                    result[key] = _cell_str(ws, row, 3)
                break

    # 模板占位符清理
    for key in ('contract_expire_date',):
        val = result.get(key)
        if val and not any(c.isdigit() for c in str(val)):
            result[key] = None

    # 月度收入 — 查找「月份」表头行，后续 12 行为数据
    header_row = _find_label_row(ws, 1, '月份', 10, 20)
    if header_row:
        monthly_income = []
        for row in range(header_row + 1, header_row + 13):
            month = _safe_int(_cell_num(ws, row, 1))
            if month is None:
                continue
            monthly_income.append({
                'month': month,
                'temp_income': _cell_num(ws, row, 2),
                'ticket_income': _cell_num(ws, row, 3),
            })
        result['monthly_income'] = monthly_income

        avg_row = _find_label_row(ws, 1, '月均', header_row, header_row + 15)
        if avg_row:
            result['monthly_avg_temp'] = _cell_num(ws, avg_row, 2)
            result['monthly_avg_ticket'] = _cell_num(ws, avg_row, 3)

    return result


def parse_project_info_collection(ws) -> dict:
    """解析「项目信息收集表」sheet（车位置换业务的项目信息）"""
    result = {
        'car_park_name': _cell_str(ws, 2, 2),
        'car_park_address': _cell_str(ws, 3, 2),
        'business_nature': _cell_str(ws, 6, 3),   # 车场业态
        'property_type': _cell_str(ws, 7, 3),     # 合作客户主体
        'contract_expire_date': _serial_to_date(_cell_num(ws, 8, 3)) or _cell_str(ws, 8, 3),
        'parking_fee_rule': _cell_str(ws, 9, 3),
        'allow_posting': _cell_str(ws, 11, 3),
        'settlement_mode': _cell_str(ws, 12, 3),
    }

    # 模板占位符清理
    for key in ('contract_expire_date',):
        val = result.get(key)
        if val and not any(c.isdigit() for c in str(val)):
            result[key] = None

    # 月度收入（rows 15-26，月份 1-12）
    monthly_income = []
    for row in range(15, 27):
        month = _safe_int(_cell_num(ws, row, 1))
        if month is None:
            continue
        monthly_income.append({
            'month': month,
            'temp_income': _cell_num(ws, row, 2),
            'ticket_income': _cell_num(ws, row, 3),
        })
    result['monthly_income'] = monthly_income

    return result


def parse_spot_exchange_calc(ws) -> dict:
    """解析「车位置换测算表」sheet（车位置换业务测算数据）"""
    result = {
        'department': _cell_str(ws, 3, 3),
        'submitter': _cell_str(ws, 3, 5),
        'opportunity_name': _cell_str(ws, 4, 3),
        'crm_quote_no': _cell_str(ws, 5, 3),
        'crm_m_factor': _cell_num(ws, 5, 5),
        'crm_settlement_total': _cell_num(ws, 6, 3),
        'crm_service_fee': _cell_num(ws, 6, 5),
        'equipment_amount': _cell_num(ws, 9, 4),
        'vat_rate': _cell_num(ws, 10, 4),
        'monthly_card_fee': _cell_num(ws, 11, 4),
        'replacement_spaces': _safe_int(_cell_num(ws, 12, 4)),
        'profit_share_ratio': _cell_num(ws, 13, 4),
        'contract_months': _safe_int(_cell_num(ws, 14, 4)),
        'per_space_monthly_income': _cell_num(ws, 15, 4),
        'purchase_unit_price': _cell_num(ws, 16, 4),
        'tax_cost': _cell_num(ws, 17, 4),
        'total_cost': _cell_num(ws, 18, 4),
        'total_revenue': _cell_num(ws, 19, 4),
        'our_profit': _cell_num(ws, 20, 4),
        'customer_profit': _cell_num(ws, 21, 4),
    }
    return result


def parse_calculation_tool(ws) -> dict:
    """解析 Sheet 2: 测算工具（金额券）— 通过标签关键词查找，兼容行偏移"""
    # 构建 col 2 标签→行号 映射
    label_rows = {}
    for row in range(1, min(ws.max_row + 1, 30)):
        label = _cell_str(ws, row, 2)
        if label:
            label_rows[label] = row

    def _find(keyword):
        for label, row in label_rows.items():
            if keyword in label:
                return row
        return None

    def _num(keyword, col, as_int=False):
        row = _find(keyword)
        if row is None:
            return None
        v = _cell_num(ws, row, col)
        return _safe_int(v) if as_int else v

    def _str(keyword, col):
        row = _find(keyword)
        return _cell_str(ws, row, col) if row else None

    # 业务员信息
    result = {
        'department': _str('提交部门', 3),
        'submitter': _str('提交部门', 5),
        'opportunity_name': _str('商机名称', 3),
        'installment_deduction': _str('商机名称', 5),
        'crm_service_fee': _cell_num(ws, 7, 5),
    }

    # 计算字段（col 2 标签, col 4 数值）
    calc_fields = [
        ('equipment_service_amount', '设备、服务置换'),
        ('cash_purchase_amount',     '现金采买'),
        ('business_fee',             '业务费'),
        ('discount_rate',            '采买折扣'),
        ('contract_months',          '合同有效年限', True),
        ('voucher_consume_months',   '券消耗年限', True),
        ('vat_rate',                 '增值税'),
        ('monthly_temp_income',      '月均临停'),
        ('monthly_ticket_income',    '月均月租'),
        ('monthly_total_income',     '月均收入'),
        ('contract_amount',          '合同金额'),
        ('voucher_total_value',      '停车券总价值'),
        ('voucher_monthly_share',    '停车券月均分摊'),
        ('project_gross_profit',     '项目整体毛利'),
    ]
    for item in calc_fields:
        key, kw = item[0], item[1]
        as_int = item[2] if len(item) > 2 else False
        result[key] = _num(kw, 4, as_int=as_int)

    # 付款方式（字符串字段）
    result['payment_method'] = _str('付款方式', 4)

    # 评估区（右侧，rows 4-5 相对固定）
    result['monthly_consume_ratio'] = _cell_num(ws, 4, 8)
    result['actual_purchase_discount'] = _cell_num(ws, 5, 8)

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

    # === 项目信息 ===
    # 格式A: 停车券业务的「1.项目基本信息」sheet
    if '1.项目基本信息' in wb.sheetnames:
        result['project_info'] = parse_project_info(wb['1.项目基本信息'])
    # 格式B: 车位置换业务的「项目信息收集表」sheet
    elif '项目信息收集表' in wb.sheetnames:
        result['project_info'] = parse_project_info_collection(wb['项目信息收集表'])

    # === 测算数据 ===
    # 停车券业务: 测算工具（金额券）
    calc_sheet_name = None
    for name in wb.sheetnames:
        if '测算工具' in name and '金额券' in name:
            calc_sheet_name = name
            break
    if calc_sheet_name:
        result['calculation_tool'] = parse_calculation_tool(wb[calc_sheet_name])

    # 车位置换业务: 折扣采买测算表
    discount_sheet = None
    for name in wb.sheetnames:
        if '折扣采买' in name or '时长采买' in name:
            discount_sheet = name
            break
    if discount_sheet:
        parsed = parse_discount_purchase(wb[discount_sheet])
        if parsed:
            result['discount_purchase'] = parsed

    # 车位置换业务: 车位置换测算表（非「运营」版本）
    spot_calc_sheet = None
    for name in wb.sheetnames:
        if '车位置换测算表' in name and '运营' not in name:
            spot_calc_sheet = name
            break
    if spot_calc_sheet:
        result['spot_exchange_calc'] = parse_spot_exchange_calc(wb[spot_calc_sheet])

    # 从「车位置换运营 测算表」补充数据（总车位数等）
    for name in wb.sheetnames:
        if '车位置换运营' in name and '测算' in name:
            ws_supp = wb[name]
            spaces = _safe_int(_cell_num(ws_supp, 20, 4))
            if spaces:
                if 'project_info' not in result:
                    result['project_info'] = {}
                result['project_info']['parking_spaces'] = spaces
            break

    # 自动判断业务类型
    has_voucher = 'calculation_tool' in result
    has_spot = 'discount_purchase' in result or 'spot_exchange_calc' in result
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
