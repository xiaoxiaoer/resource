"""端到端校验入口测试。"""

from web.services.validators import run_validation


def test_run_validation_voucher_full(voucher_pi_full, voucher_ct_full, bem_data_ok, company_data_ok):
    parsed = {
        'project_info': voucher_pi_full,
        'calculation_tool': voucher_ct_full,
        'business_type': 'parking_voucher',
    }
    result = run_validation('parking_voucher', parsed, bem_data_ok, company_data_ok)
    assert result.business_type == 'parking_voucher'
    assert result.count('pass') > 0
    assert result.count('risk') == 0
    # 编号连续
    for i, item in enumerate(result.checks, start=1):
        assert item.code == f'C{i}'


def test_run_validation_voucher_missing_fields(voucher_pi_full, bem_data_ok):
    voucher_pi_full['car_park_name'] = None
    parsed = {
        'project_info': voucher_pi_full,
        'calculation_tool': {},  # 全部缺失
        'business_type': 'parking_voucher',
    }
    result = run_validation('parking_voucher', parsed, bem_data_ok, None)
    assert result.count('risk') >= 5  # 至少 5 个测算字段缺失 + 车场名缺失


def test_run_validation_voucher_ticket_skip(voucher_pi_full, voucher_ct_full, bem_data_ticket_zero):
    parsed = {
        'project_info': voucher_pi_full,
        'calculation_tool': voucher_ct_full,
        'business_type': 'parking_voucher',
    }
    result = run_validation('parking_voucher', parsed, bem_data_ticket_zero, None)
    assert result.count('skip') == 1
    skip_items = result.by_status('skip')
    assert '月均月票收入' in skip_items[0].label


def test_run_validation_voucher_generic_property_type(voucher_pi_full, voucher_ct_full, bem_data_ok):
    voucher_pi_full['property_type'] = '承包方'
    parsed = {
        'project_info': voucher_pi_full,
        'calculation_tool': voucher_ct_full,
        'business_type': 'parking_voucher',
    }
    result = run_validation('parking_voucher', parsed, bem_data_ok, None)
    risk_items = result.by_status('risk')
    assert any('合作客户主体' in c.label for c in risk_items)
    # 企查查项不应出现（被跳过）
    assert not any('企业信息查询' in c.label for c in result.checks)


def test_run_validation_spot_full(spot_pi_full, spot_sec_full, bem_data_ok):
    parsed = {
        'project_info': spot_pi_full,
        'spot_exchange_calc': spot_sec_full,
        'business_type': 'spot_exchange',
    }
    result = run_validation('spot_exchange', parsed, bem_data_ok, None)
    assert result.business_type == 'spot_exchange'
    # equipment_amount == 300000 != 280000(CRM) → pass
    eq = [c for c in result.checks if c.label == '设备和服务置换金额'][0]
    assert eq.status == 'pass'


def test_run_validation_spot_contract_short(spot_pi_full, spot_sec_full, bem_data_ok):
    spot_sec_full['contract_months'] = 24
    parsed = {
        'project_info': spot_pi_full,
        'spot_exchange_calc': spot_sec_full,
        'business_type': 'spot_exchange',
    }
    result = run_validation('spot_exchange', parsed, bem_data_ok, None)
    warn_items = result.by_status('warn')
    assert any('合同有效年限' in c.label for c in warn_items)


def test_basic_info_owner_classification(voucher_pi_full, bem_data_ok):
    voucher_pi_full['property_type'] = '广州市某物业承包方'
    parsed = {
        'project_info': voucher_pi_full,
        'calculation_tool': {},
        'business_type': 'parking_voucher',
    }
    result = run_validation('parking_voucher', parsed, bem_data_ok, None)
    assert result.basic_info['产权/承包'] == '承包方'
