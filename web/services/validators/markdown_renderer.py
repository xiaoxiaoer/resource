"""ValidationResult → 5 区域 Markdown。

输出结构与 prompts/output_template.md 保持一致：
基本信息 / 检查结果 / 项目评估 / 趋势分析 / 总结
"""

from web.services.validators.core import CheckItem, STATUS_ICON, ValidationResult


def _fmt_value(val) -> str:
    if val is None or val == '':
        return '-'
    if isinstance(val, float):
        if val.is_integer():
            return f'{int(val):,}'
        return f'{val:,.2f}'
    if isinstance(val, int):
        return f'{val:,}'
    s = str(val)
    return s if s.strip() else '-'


def _escape_pipe(s: str) -> str:
    return s.replace('|', '\\|').replace('\n', '；')


def _render_basic_info(result: ValidationResult) -> str:
    lines = ['## 基本信息']
    for k, v in result.basic_info.items():
        lines.append(f'- {k}：{v}')
    return '\n'.join(lines)


def _render_check_table(items: list[CheckItem], title: str) -> str:
    if not items:
        return ''
    icon = STATUS_ICON.get(items[0].status, '')
    lines = [f'### {icon} {title}（{len(items)}项）', '']
    lines.append('| 序号 | 检查项 | 状态 | 是否有风险 | 资料数据 | 说明 |')
    lines.append('|------|--------|------|------------|---------|------|')
    risk_map = {
        'pass': '无风险',
        'warn': '有风险',
        'risk': '有风险',
        'manual': '待确认',
        'skip': '跳过对比',
    }
    for it in items:
        excel_str = _fmt_value(it.excel_value)
        note = _escape_pipe(it.note or '')
        status_icon = STATUS_ICON.get(it.status, '')
        risk_label = risk_map.get(it.status, '-')
        # 把参考数据并入说明，用逗号分隔避免前端表格解析问题
        if it.ref_value is not None:
            ref_label = f'{it.ref_source}' if it.ref_source else '系统'
            ref_val_str = _fmt_value(it.ref_value)
            note = f'{ref_label}：{ref_val_str}，{note}' if note else f'{ref_label}：{ref_val_str}'
        lines.append(f'| {it.code} | {_escape_pipe(it.label)} | {status_icon} | {risk_label} | {excel_str} | {note} |')
    return '\n'.join(lines)


def _render_checks(result: ValidationResult) -> str:
    out = ['## 检查结果', '']
    sections = [
        ('pass', '通过项'),
        ('warn', '需关注项'),
        ('risk', '风险项'),
        ('manual', '人工确认项'),
        ('skip', '跳过对比项'),
    ]
    for status, title in sections:
        items = result.by_status(status)
        block = _render_check_table(items, title)
        if block:
            out.append(block)
            out.append('')
    return '\n'.join(out).rstrip()


def _fmt_eval_value(label: str, v) -> str:
    if v is None or v == '':
        return '-'
    if label == '月均消耗比例':
        try:
            return f'{float(v):.2f}%'
        except (ValueError, TypeError):
            return str(v)
    if label == '实际采买折扣':
        try:
            return f'{float(v):.3f}'
        except (ValueError, TypeError):
            return str(v)
    return _fmt_value(v)


def _render_evaluation(result: ValidationResult) -> str:
    if not result.evaluation:
        return '## 项目评估（原样输出）\n\n（无评估区数据）'
    lines = ['## 项目评估（原样输出）', '']
    lines.append('| 序号 | 评估项 | 数据值 |')
    lines.append('|------|--------|-------|')
    for i, (k, v) in enumerate(result.evaluation.items(), 1):
        if v is None:
            continue
        lines.append(f'| E{i} | {_escape_pipe(k)} | {_fmt_eval_value(k, v)} |')
    if len(lines) == 3:
        lines.append('| - | （无评估区数据） | - |')
    return '\n'.join(lines)


def _render_trend(result: ValidationResult) -> str:
    if not result.trend:
        return '## 趋势分析\n\n（无趋势数据）'
    lines = ['## 趋势分析']
    for t in result.trend:
        lines.append(f'- {t}')
    return '\n'.join(lines)


def _render_summary(result: ValidationResult) -> str:
    n_pass = result.count('pass')
    n_warn = result.count('warn')
    n_risk = result.count('risk')
    n_manual = result.count('manual')
    n_skip = result.count('skip')
    parts = [f'{n_pass} 项通过', f'{n_warn} 项需关注', f'{n_risk} 项风险', f'{n_manual} 项待确认']
    if n_skip:
        parts.append(f'{n_skip} 项跳过对比')
    summary_line = '，'.join(parts) + '。'
    if n_risk > 0:
        advice = '存在风险项，建议补齐资料并由业务复审后再提交。'
    elif n_warn > 0:
        advice = '存在需关注项，请运营核对差异原因。'
    elif n_manual > 0:
        advice = '存在待人工确认项，请运营完成核实后入库。'
    else:
        advice = '资料完整且与系统数据一致，可进入下一审核环节。'
    return f'## 总结\n\n{summary_line}{advice}'


def render_markdown(result: ValidationResult) -> str:
    sections = [
        '# 资源置换评估初审结果',
        _render_basic_info(result),
        '---',
        _render_checks(result),
        '---',
        _render_evaluation(result),
        _render_trend(result),
        '---',
        _render_summary(result),
    ]
    return '\n\n'.join(s for s in sections if s)
