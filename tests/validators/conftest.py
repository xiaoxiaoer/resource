"""通用测试 fixture。"""

import pytest


@pytest.fixture
def voucher_pi_full():
    """停车券业务 — 完整的项目基本信息。"""
    return {
        'car_park_name': '测试车场',
        'car_park_address': '测试地址',
        'property_type': '某某科技有限公司',
        'contract_expire_date': '2030-12-31',
        'parking_fee_rule': '5元/小时',
        'allow_posting': '是',
        'has_own_channel': '否',
        'parking_spaces': 500,
        'monthly_income': [
            {'month': m, 'temp_income': 10000.0, 'ticket_income': 5000.0}
            for m in range(1, 13)
        ],
        'monthly_avg_temp': 10000.0,
        'monthly_avg_ticket': 5000.0,
    }


@pytest.fixture
def voucher_ct_full():
    """停车券业务 — 完整的测算工具表。"""
    return {
        'equipment_service_amount': 500000.0,
        'cash_purchase_amount': 100000.0,
        'payment_method': '分期',
        'business_fee': None,
        'discount_rate': 0.85,
        'contract_months': 36,
        'voucher_consume_months': 48,
        'vat_rate': 0.13,
        'monthly_temp_income': 10000.0,
        'monthly_ticket_income': 5000.0,
        'monthly_consume_ratio': 0.5,
        'actual_purchase_discount': 0.82,
    }


@pytest.fixture
def spot_pi_full():
    return {
        'car_park_name': '车位置换测试车场',
        'car_park_address': '测试地址',
        'property_type': '某某物业有限公司',
        'contract_expire_date': '2030-12-31',
        'parking_fee_rule': '5元/小时',
        'allow_posting': '是',
        'has_own_channel': '是',
        'parking_spaces': 300,
        'monthly_income': [
            {'month': m, 'temp_income': 8000.0, 'ticket_income': 12000.0}
            for m in range(1, 13)
        ],
        'monthly_avg_temp': 8000.0,
        'monthly_avg_ticket': 12000.0,
    }


@pytest.fixture
def spot_sec_full():
    return {
        'equipment_amount': 300000.0,
        'vat_rate': 0.13,
        'monthly_card_fee': 300.0,
        'replacement_spaces': 50,
        'profit_share_ratio': 0.3,
        'contract_months': 60,
        'crm_settlement_total': 280000.0,
    }


@pytest.fixture
def bem_data_ok():
    """正常的 BEM 数据响应。"""
    return {
        'status': 'success',
        'data': {
            'temp_parking': {
                'summary': {'monthly_avg': 10000.0, 'trend': '平稳', 'trend_note': ''},
                'monthly': [
                    {'month': f'2026-{m:02d}', 'actual_income_wechat': 10000.0, 'total_income': 10000.0}
                    for m in range(1, 13)
                ],
            },
            'monthly_ticket': {
                'summary': {'monthly_avg': 5000.0, 'trend': '平稳', 'trend_note': ''},
                'monthly': [
                    {'month': f'2026-{m:02d}', 'ticket_income': 5000.0}
                    for m in range(1, 13)
                ],
            },
            'ticket_types': [
                {'name': '对外月票', 'price': 300.0, 'is_internal': False, 'active_count': 50, 'category': '对外办理'},
                {'name': '内部月票', 'price': 100.0, 'is_internal': True, 'active_count': 20, 'category': '内部/VIP'},
            ],
        },
    }


@pytest.fixture
def bem_data_ticket_zero():
    """月票全为 0 的 BEM 响应。"""
    return {
        'status': 'success',
        'data': {
            'temp_parking': {
                'summary': {'monthly_avg': 10000.0, 'trend': '', 'trend_note': ''},
                'monthly': [
                    {'month': f'2026-{m:02d}', 'actual_income_wechat': 10000.0, 'total_income': 10000.0}
                    for m in range(1, 13)
                ],
            },
            'monthly_ticket': {
                'summary': {'monthly_avg': 0, 'trend': '', 'trend_note': ''},
                'monthly': [
                    {'month': f'2026-{m:02d}', 'ticket_income': 0}
                    for m in range(1, 13)
                ],
            },
            'ticket_types': [],
        },
    }


@pytest.fixture
def company_data_ok():
    return {
        'company_name': '某某科技有限公司',
        'social_insurance_count': 50,
        'status': '存续',
        'registered_capital': '1000万',
        'established_date': '2015-01-01',
    }
