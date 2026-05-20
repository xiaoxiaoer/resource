"""通用规则单测。"""

from datetime import datetime, timedelta

import pytest

from web.services.validators import rules_common
from web.services.validators.rules_common import _is_generic_property_type, _parse_date, BEIJING_TZ


def _ctx(pi=None, ct=None, sec=None, bem=None, company=None):
    return {
        'pi': pi or {}, 'ct': ct or {}, 'sec': sec or {},
        'bem': bem, 'bem_error': None, 'company': company,
        'business_type': 'parking_voucher', 'parsed_data': {},
    }


# 通用词判定

@pytest.mark.parametrize('val,expected', [
    ('承包方', True),
    ('产权方', True),
    ('产权方/承包方', True),
    ('产权方-承包方', True),
    ('承包方/产权方', True),
    (' 承包方 ', True),
    ('某某科技有限公司', False),
    ('', False),
    (None, False),
])
def test_is_generic_property_type(val, expected):
    assert _is_generic_property_type(val) is expected


# 基本信息字段

def test_car_park_name_missing():
    item = rules_common.check_car_park_name(_ctx(pi={'car_park_name': None}))
    assert item.status == 'risk'


def test_car_park_name_ok():
    item = rules_common.check_car_park_name(_ctx(pi={'car_park_name': '测试车场'}))
    assert item.status == 'pass'


def test_property_type_generic_word_marked_risk():
    item = rules_common.check_property_type(_ctx(pi={'property_type': '承包方'}))
    assert item.status == 'risk'
    assert '具体公司名称' in item.note


def test_property_type_real_company():
    item = rules_common.check_property_type(_ctx(pi={'property_type': '某某科技有限公司'}))
    assert item.status == 'pass'


def test_contract_expire_required_for_contractor():
    item = rules_common.check_contract_expire_date(_ctx(pi={
        'property_type': '某某科技有限公司（承包方）', 'contract_expire_date': None
    }))
    assert item.status == 'risk'


def test_contract_expire_optional_for_owner():
    item = rules_common.check_contract_expire_date(_ctx(pi={
        'property_type': '某某科技产权方', 'contract_expire_date': None
    }))
    assert item.status == 'pass'


def test_parking_spaces_zero_is_risk():
    item = rules_common.check_parking_spaces(_ctx(pi={'parking_spaces': 0}))
    assert item.status == 'risk'


def test_parking_spaces_below_10_is_risk():
    item = rules_common.check_parking_spaces(_ctx(pi={'parking_spaces': 5}))
    assert item.status == 'risk'
    assert '不足10' in item.note


def test_parking_spaces_10_to_100_is_warn():
    item = rules_common.check_parking_spaces(_ctx(pi={'parking_spaces': 50}))
    assert item.status == 'warn'


def test_parking_spaces_above_100_is_pass():
    item = rules_common.check_parking_spaces(_ctx(pi={'parking_spaces': 500}))
    assert item.status == 'pass'


def test_monthly_income_incomplete():
    item = rules_common.check_monthly_income_completeness(_ctx(pi={
        'monthly_income': [{'month': 1, 'temp_income': 100, 'ticket_income': 50}]
    }))
    assert item.status == 'risk'


# BEM 对比

def test_monthly_temp_compare_no_bem(voucher_pi_full):
    item = rules_common.check_monthly_temp_compare(_ctx(pi=voucher_pi_full, bem=None))
    assert item.status == 'manual'


def test_monthly_temp_compare_match(voucher_pi_full, bem_data_ok):
    bem = bem_data_ok['data']
    item = rules_common.check_monthly_temp_compare(_ctx(pi=voucher_pi_full, bem=bem))
    assert item.status == 'pass'


def test_monthly_temp_compare_warn(voucher_pi_full, bem_data_ok):
    voucher_pi_full['monthly_avg_temp'] = 20000.0  # 100% 差异
    bem = bem_data_ok['data']
    item = rules_common.check_monthly_temp_compare(_ctx(pi=voucher_pi_full, bem=bem))
    assert item.status == 'warn'


def test_monthly_ticket_compare_skip_when_bem_zero(voucher_pi_full, bem_data_ticket_zero):
    bem = bem_data_ticket_zero['data']
    item = rules_common.check_monthly_ticket_compare(_ctx(pi=voucher_pi_full, bem=bem))
    assert item.status == 'skip'
    assert 'BEM 月票数据全为 0' in item.note


def test_monthly_ticket_compare_match(voucher_pi_full, bem_data_ok):
    bem = bem_data_ok['data']
    item = rules_common.check_monthly_ticket_compare(_ctx(pi=voucher_pi_full, bem=bem))
    assert item.status == 'pass'


# 企查查

def test_company_lookup_skipped_for_generic_word():
    item = rules_common.check_company_lookup_result(_ctx(
        pi={'property_type': '承包方'}, company=None,
    ))
    assert item is None  # 不重复输出


def test_company_lookup_no_data_for_real_company():
    item = rules_common.check_company_lookup_result(_ctx(
        pi={'property_type': '某某公司'}, company=None,
    ))
    assert item is not None
    assert item.status == 'manual'


def test_company_lookup_with_data(company_data_ok):
    item = rules_common.check_company_lookup_result(_ctx(
        pi={'property_type': '某某科技有限公司'}, company=company_data_ok,
    ))
    assert item is not None
    assert item.status == 'manual'
    assert '参保人数' in item.note
    assert '50' in item.note


# _parse_date 日期格式解析

@pytest.mark.parametrize('value,expected', [
    ('2030-12-31', '2030-12-31'),
    ('2030/12/31', '2030-12-31'),
    ('2030.12.31', '2030-12-31'),
    ('2030年12月31日', '2030-12-31'),
    ('2030年12月31号', '2030-12-31'),
    ('2030年6月5日', '2030-06-05'),
    (None, None),
    ('', None),
    ('not-a-date', None),
])
def test_parse_date_formats(value, expected):
    result = _parse_date(value)
    if expected is None:
        assert result is None
    else:
        assert result.strftime('%Y-%m-%d') == expected


def test_parse_date_datetime_passthrough():
    dt = datetime(2030, 12, 31)
    assert _parse_date(dt) is dt


# 承包到期时间范围校验

def _now_beijing():
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def test_contract_expire_expired_is_risk():
    yesterday = (_now_beijing() - timedelta(days=2)).strftime('%Y-%m-%d')
    item = rules_common.check_contract_expire_date(_ctx(pi={
        'property_type': '某某科技（承包方）', 'contract_expire_date': yesterday,
    }))
    assert item.status == 'risk'
    assert '已过期' in item.note


def test_contract_expire_within_1day_is_risk():
    today_str = _now_beijing().strftime('%Y-%m-%d')
    item = rules_common.check_contract_expire_date(_ctx(pi={
        'property_type': '某某科技（承包方）', 'contract_expire_date': today_str,
    }))
    assert item.status == 'risk'


def test_contract_expire_within_1year_is_warn():
    date_str = (_now_beijing() + timedelta(days=180)).strftime('%Y-%m-%d')
    item = rules_common.check_contract_expire_date(_ctx(pi={
        'property_type': '某某科技（承包方）', 'contract_expire_date': date_str,
    }))
    assert item.status == 'warn'
    assert '不足1年' in item.note


def test_contract_expire_beyond_1year_is_pass():
    date_str = (_now_beijing() + timedelta(days=400)).strftime('%Y-%m-%d')
    item = rules_common.check_contract_expire_date(_ctx(pi={
        'property_type': '某某科技（承包方）', 'contract_expire_date': date_str,
    }))
    assert item.status == 'pass'


def test_contract_expire_unparseable_is_risk():
    item = rules_common.check_contract_expire_date(_ctx(pi={
        'property_type': '某某科技（承包方）', 'contract_expire_date': 'invalid',
    }))
    assert item.status == 'risk'
    assert '无法识别' in item.note


def test_contract_expire_chinese_format_warn():
    d = _now_beijing() + timedelta(days=180)
    date_str = f'{d.year}年{d.month}月{d.day}日'
    item = rules_common.check_contract_expire_date(_ctx(pi={
        'property_type': '某某科技（承包方）', 'contract_expire_date': date_str,
    }))
    assert item.status == 'warn'
