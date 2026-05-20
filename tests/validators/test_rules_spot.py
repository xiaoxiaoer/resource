"""车位置换规则单测。"""

from web.services.validators import rules_spot


def _ctx(pi=None, sec=None, bem=None):
    return {
        'pi': pi or {}, 'ct': {}, 'sec': sec or {},
        'bem': bem, 'bem_error': None, 'company': None,
        'business_type': 'spot_exchange', 'parsed_data': {},
    }


def test_equipment_amount_equals_crm_is_manual():
    item = rules_spot.check_equipment_amount(_ctx(sec={
        'equipment_amount': 300000.0, 'crm_settlement_total': 300000.0,
    }))
    assert item.status == 'manual'
    assert 'CRM' in item.note


def test_equipment_amount_differs_from_crm_is_pass():
    item = rules_spot.check_equipment_amount(_ctx(sec={
        'equipment_amount': 300000.0, 'crm_settlement_total': 280000.0,
    }))
    assert item.status == 'pass'


def test_equipment_amount_missing_is_risk():
    item = rules_spot.check_equipment_amount(_ctx(sec={'equipment_amount': None}))
    assert item.status == 'risk'


def test_contract_months_below_36_is_warn():
    item = rules_spot.check_contract_months(_ctx(sec={'contract_months': 24}))
    assert item.status == 'warn'


def test_contract_months_ge_36_is_pass():
    item = rules_spot.check_contract_months(_ctx(sec={'contract_months': 36}))
    assert item.status == 'pass'


def test_monthly_card_fee_no_bem(spot_sec_full):
    item = rules_spot.check_monthly_card_fee(_ctx(sec=spot_sec_full, bem=None))
    assert item.status == 'manual'


def test_monthly_card_fee_match_bem(spot_sec_full, bem_data_ok):
    bem = bem_data_ok['data']
    item = rules_spot.check_monthly_card_fee(_ctx(sec=spot_sec_full, bem=bem))
    # spot_sec_full.monthly_card_fee = 300, bem external_prices = [300]
    assert item.status == 'pass'


def test_monthly_card_fee_warn_when_diff(spot_sec_full, bem_data_ok):
    spot_sec_full['monthly_card_fee'] = 600.0
    bem = bem_data_ok['data']
    item = rules_spot.check_monthly_card_fee(_ctx(sec=spot_sec_full, bem=bem))
    assert item.status == 'warn'


def test_replacement_spaces_zero_is_risk():
    item = rules_spot.check_replacement_spaces(_ctx(sec={'replacement_spaces': 0}))
    assert item.status == 'risk'
