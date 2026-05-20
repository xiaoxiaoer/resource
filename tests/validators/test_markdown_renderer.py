"""Markdown 渲染测试。"""

from web.services.validators import run_validation, render_markdown


def test_render_full_voucher(voucher_pi_full, voucher_ct_full, bem_data_ok, company_data_ok):
    parsed = {
        'project_info': voucher_pi_full,
        'calculation_tool': voucher_ct_full,
        'business_type': 'parking_voucher',
    }
    result = run_validation('parking_voucher', parsed, bem_data_ok, company_data_ok)
    md = render_markdown(result)
    # 5 个固定区域
    assert '## 基本信息' in md
    assert '## 检查结果' in md
    assert '## 项目评估' in md
    assert '## 趋势分析' in md
    assert '## 总结' in md
    # 状态图标
    assert '✅' in md
    # 总结统计
    assert '项通过' in md


def test_render_skip_section(voucher_pi_full, voucher_ct_full, bem_data_ticket_zero):
    parsed = {
        'project_info': voucher_pi_full,
        'calculation_tool': voucher_ct_full,
        'business_type': 'parking_voucher',
    }
    result = run_validation('parking_voucher', parsed, bem_data_ticket_zero, None)
    md = render_markdown(result)
    assert '🔵 跳过对比项' in md or '🔵' in md


def test_render_risk_section_when_missing(voucher_pi_full, bem_data_ok):
    voucher_pi_full['car_park_name'] = None
    parsed = {
        'project_info': voucher_pi_full,
        'calculation_tool': {},
        'business_type': 'parking_voucher',
    }
    result = run_validation('parking_voucher', parsed, bem_data_ok, None)
    md = render_markdown(result)
    assert '❌' in md
    assert '建议' in md  # 总结的建议
