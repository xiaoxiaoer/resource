"""停车券规则单测。"""

from datetime import datetime, timedelta

from web.services.validators import rules_voucher


def _ctx(pi=None, ct=None):
    return {
        'pi': pi or {}, 'ct': ct or {}, 'sec': {},
        'bem': None, 'bem_error': None, 'company': None,
        'business_type': 'parking_voucher', 'parsed_data': {},
    }


def test_equipment_service_amount_missing():
    item = rules_voucher.check_equipment_service_amount(_ctx(ct={'equipment_service_amount': None}))
    assert item.status == 'risk'


def test_business_fee_none_yields_no_item():
    item = rules_voucher.check_business_fee(_ctx(ct={'business_fee': None}))
    assert item is None


def test_business_fee_with_value_is_manual():
    item = rules_voucher.check_business_fee(_ctx(ct={'business_fee': 5000.0}))
    assert item is not None
    assert item.status == 'manual'


def test_payment_method_optional():
    item = rules_voucher.check_payment_method(_ctx(ct={'payment_method': None}))
    assert item is None


def test_contract_months_zero_is_risk():
    item = rules_voucher.check_contract_months(_ctx(ct={'contract_months': 0}))
    assert item.status == 'risk'


def test_contract_months_ok():
    item = rules_voucher.check_contract_months(_ctx(ct={'contract_months': 36}))
    assert item.status == 'pass'


def test_voucher_gt_contract_pass():
    item = rules_voucher.cross_voucher_gt_contract(_ctx(ct={
        'contract_months': 36, 'voucher_consume_months': 48,
    }))
    assert item.status == 'pass'


def test_voucher_le_contract_is_risk():
    item = rules_voucher.cross_voucher_gt_contract(_ctx(ct={
        'contract_months': 36, 'voucher_consume_months': 36,
    }))
    assert item.status == 'risk'


def test_contract_within_expire_pass():
    expire = (datetime.now() + timedelta(days=365 * 5)).strftime('%Y-%m-%d')
    item = rules_voucher.cross_contract_within_expire(_ctx(
        pi={'property_type': '某某承包方', 'contract_expire_date': expire},
        ct={'contract_months': 36},
    ))
    assert item.status == 'pass'


def test_contract_exceeds_expire_is_risk():
    expire = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')  # 1 年后
    item = rules_voucher.cross_contract_within_expire(_ctx(
        pi={'property_type': '某某承包方', 'contract_expire_date': expire},
        ct={'contract_months': 60},  # 60 月 > 12 月
    ))
    assert item.status == 'risk'


def test_contract_expire_skipped_for_owner():
    item = rules_voucher.cross_contract_within_expire(_ctx(
        pi={'property_type': '某某产权方', 'contract_expire_date': None},
        ct={'contract_months': 60},
    ))
    assert item is None
