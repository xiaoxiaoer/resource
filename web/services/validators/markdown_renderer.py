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


_RISK_ADJUSTMENTS = {
    '资产占比风险': [
        ('≤40%', 0), ('40%-60%', 3), ('60%-70%', 5), ('>70%', 20),
    ],
    '运营权可持续性': [
        ('≥1年', 0), ('0.5-1年', 5), ('0-0.5年', 10), ('<0年', 30),
    ],
    '经营质量风险': [
        ('≥12个月', 0), ('6-11个月', 3), ('3-5个月', 10), ('<3个月', 20),
    ],
    '运营方背景风险': [
        ('中大型（参保人数>30人/已正常消耗1年）', 0),
        ('小型（参保人数10-30人）', 1),
        ('微型（参保人数5-10人）', 5),
        ('个体（参保人数<5人）', 10),
    ],
    '回款风险': [
        ('无特殊支付渠道', 0), ('仅小程序', 3), ('仅ETC', 7), ('ETC+小程序', 10),
    ],
    '采买金额': [
        ('≤10万', 1), ('10万-30万', 3), ('30-50万', 5), ('>50万', 10),
    ],
}


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
    risk_eval = result.evaluation.get('risk_evaluation')
    risk_rating = result.evaluation.get('risk_rating')
    if not risk_eval and not risk_rating:
        return '## 项目评估（原样输出）\n\n（无评估区数据）'
    lines = ['## 项目评估（原样输出）', '']
    lines.append('| 风险维度 | 评估指标 | 输入值/选项 | 扣减率 | 说明 |')
    lines.append('|----------|---------|------------|--------|------|')

    # 风险维度行
    if risk_eval:
        total_deduction = 0
        for s in risk_eval:
            cat = _escape_pipe(s.get('category', ''))
            ind = _escape_pipe(s.get('indicator', ''))
            val = _escape_pipe(str(s.get('value', '')))
            score = _escape_pipe(str(s.get('score', '')))
            desc = _escape_pipe(s.get('description', ''))
            lines.append(f'| {cat} | {ind} | {val} | {score} | {desc} |')
            total_deduction += float(s.get('score', 0) or 0)

    # 风险评分行
    if risk_rating is not None:
        try:
            rating_val = float(risk_rating)
        except (ValueError, TypeError):
            rating_val = None
        if rating_val is not None and risk_eval:
            calc_score = 100 - total_deduction
            if abs(calc_score - rating_val) < 0.01:
                note = f'100 - {int(total_deduction)} = {int(calc_score)} ✅'
            else:
                note = f'100 - {int(total_deduction)} = {int(calc_score)} ⚠️ 不一致'
            lines.append(f'| 风险分数 | | {int(rating_val)} | | {note} |')
        else:
            lines.append(f'| 风险分数 | | {_escape_pipe(str(risk_rating))} | | |')

    # 风险分数 < 70 时输出可调整点
    if rating_val is not None and rating_val < 70 and risk_eval:
        lines.append('')
        lines.append(f'### 风险评估调整建议（当前风险分数：{int(rating_val)}）')
        lines.append('')
        deductions = []
        for s in risk_eval:
            score = float(s.get('score', 0) or 0)
            if score > 0:
                deductions.append((s, score))
        deductions.sort(key=lambda x: -x[1])
        for s, score in deductions:
            cat = s.get('category', '')
            ind = s.get('indicator', '')
            rules = _RISK_ADJUSTMENTS.get(cat)
            lines.append(f'- **{cat}**（当前扣减率：{int(score)}）')
            if rules:
                rule_parts = [f'{threshold}扣减{rate}' for threshold, rate in rules]
                lines.append(f'  {ind}：{"，".join(rule_parts)}')
    return '\n'.join(lines)


_MARGIN_SUGGESTIONS = [
    ('降低现金采买金额', '减少现金采买金额以降低总成本'),
    ('降低业务费', '协商降低业务费'),
    ('降低签约折扣率', '降低折扣率减少折扣让利'),
    ('增值税发票优化', '增值税普通发票沟通成增值税专用发票'),
    ('提升税点', '税点从3%提升至5%或9%'),
    ('增加置换车位数量', '通过增加车位数量分摊固定成本'),
    ('沟通分润模式', '调整分润模式改善收益分配'),
]


def _render_margin_suggestion(result: ValidationResult) -> str:
    ev = result.evaluation
    margin = ev.get('gross_margin_before')
    if margin is None:
        return ''
    try:
        margin_val = float(margin)
    except (ValueError, TypeError):
        return ''
    if margin_val >= 0:
        return ''
    pct = f'{margin_val * 100:.2f}%'
    lines = [f'## 毛利率调整建议（优价前毛利率：{pct}）', '']
    lines.append('优价前毛利率为负，建议按以下优先级调整业务参数：')
    lines.append('')
    for i, (title, desc) in enumerate(_MARGIN_SUGGESTIONS, 1):
        lines.append(f'{i}. **{title}**：{desc}')
    # 优价兜底
    discount = ev.get('discount_factor')
    margin_after = ev.get('gross_margin_after')
    fallback_parts = []
    if discount is not None:
        fallback_parts.append(f'当前优价系数：{_fmt_value(discount)}')
    if margin_after is not None:
        try:
            fallback_parts.append(f'当前毛利率：{float(margin_after) * 100:.2f}%')
        except (ValueError, TypeError):
            pass
    fallback_note = '，'.join(fallback_parts) if fallback_parts else ''
    lines.append(f'{len(_MARGIN_SUGGESTIONS) + 1}. **以上均不行时**：使用优价方法{"（" + fallback_note + "）" if fallback_note else ""}')
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


def _render_notes(result: ValidationResult) -> str:
    if not result.notes:
        return ''
    lines = ['## 备注']
    for n in result.notes:
        lines.append(f'- {n}')
    return '\n'.join(lines)


def render_markdown(result: ValidationResult) -> str:
    sections = [
        '# 资源置换评估初审结果',
        _render_basic_info(result),
        '---',
        _render_checks(result),
        '---',
        _render_evaluation(result),
    ]
    margin_block = _render_margin_suggestion(result)
    if margin_block:
        sections.append(margin_block)
        sections.append('---')
    sections.append(_render_trend(result))
    sections.append('---')
    notes_block = _render_notes(result)
    if notes_block:
        sections.append(notes_block)
        sections.append('---')
    sections.append(_render_summary(result))
    return '\n\n'.join(s for s in sections if s)
