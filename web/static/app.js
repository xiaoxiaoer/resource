/**
 * 资源置换评估系统 — 前端逻辑
 */
(function() {
    const $ = (sel) => document.querySelector(sel);

    // 不输出的内容关键字，用于过滤 LLM 审核结果
    // 来源：prompts/audit_field_rules.md
    const EXCLUDED_PATTERNS = [
        '毛利计算', '项目整体毛利', '设备预估毛利',
        '合同金额', '停车券总价值', '停车券月均分摊', '月均收入合计',
        '单车位月均收入', '车位采购单价', '税金成本', '项目总成本',
        '我司总收入', '我司利润额', '客户利润额',
    ];

    const dropZone = $('#drop-zone');
    const fileInput = $('#file-input');
    const filePreview = $('#file-preview');
    const fileName = $('#file-name');
    const removeBtn = $('#remove-file');
    const parsedPreview = $('#parsed-preview');
    const businessType = $('#business-type');
    const enableLLM = $('#enable-llm');
    const startBtn = $('#start-btn');
    const statusBar = $('#status-bar');
    const statusText = $('#status-text');
    const toolCalls = $('#tool-calls');
    const resultSection = $('#result-section');
    const resultContent = $('#result-content');
    const copyBtn = $('#copy-btn');
    const comparisonSection = $('#comparison-section');
    const comparisonContent = $('#comparison-content');

    let sessionId = null;
    let fullResult = '';

    // --- 拖放上传 ---
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
    });

    removeBtn.addEventListener('click', () => {
        sessionId = null;
        filePreview.classList.add('hidden');
        dropZone.style.display = '';
        statusBar.classList.add('hidden');
        resultSection.classList.add('hidden');
        fileInput.value = '';
    });

    // --- 文件上传 ---
    async function handleFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        startBtn.disabled = true;
        startBtn.textContent = '解析中...';

        try {
            const resp = await fetch('/api/upload', { method: 'POST', body: formData });
            const data = await resp.json();

            if (!resp.ok) {
                alert('上传失败: ' + (data.detail || JSON.stringify(data)));
                startBtn.disabled = false;
                startBtn.textContent = '开始审核';
                return;
            }

            sessionId = data.session_id;
            fileName.textContent = data.file_name;
            dropZone.style.display = 'none';
            filePreview.classList.remove('hidden');

            // 显示解析数据预览
            renderParsedData(data.parsed_data);

            // 自动检测业务类型
            if (data.parsed_data.business_type === 'spot_exchange') {
                businessType.value = 'spot_exchange';
            } else {
                businessType.value = 'parking_voucher';
            }

            startBtn.disabled = false;
            startBtn.textContent = '开始审核';
        } catch (e) {
            alert('上传失败: ' + e.message);
            startBtn.disabled = false;
            startBtn.textContent = '开始审核';
        }
    }

    function renderParsedData(data) {
        if (!data) { parsedPreview.innerHTML = ''; return; }

        const pi = data.project_info || {};
        const ct = data.calculation_tool || {};
        const sec = data.spot_exchange_calc || {};

        let html = '<table><tbody>';
        const rows = [
            ['车场名称', pi.car_park_name],
            ['车场地址', pi.car_park_address],
            ['合作客户主体', pi.property_type],
            ['承包到期日期', pi.contract_expire_date],
            ['停车场收费规则', pi.parking_fee_rule],
            ['是否允许张贴物料', pi.allow_posting],
            ['是否存在自有小程序/ETC支付渠道', pi.has_own_channel],
            ['停车场车位数量', pi.parking_spaces],
        ];

        if (data.business_type === 'spot_exchange' && Object.keys(sec).length > 0) {
            rows.push(
                ['车场业态', pi.business_nature],
                ['车位占用率', pi.occupancy_rate || '-'],
                ['结算模式', pi.settlement_mode || '-'],
                ['设备、服务置换金额（元）', sec.equipment_amount ? '¥' + sec.equipment_amount.toLocaleString() : '-'],
                ['对外办理月卡费用（元/月）', sec.monthly_card_fee ? '¥' + sec.monthly_card_fee.toLocaleString() + '/月' : '-'],
                ['置换车位数', sec.replacement_spaces || '-'],
                ['回本后甲方分润比例', sec.profit_share_ratio !== null ? sec.profit_share_ratio : '-'],
                ['合同有效年限（月）', sec.contract_months ? sec.contract_months + '个月' : '-'],
            );
        } else {
            rows.push(
                ['月均临停收入', pi.monthly_avg_temp ? '¥' + pi.monthly_avg_temp.toLocaleString() : '-'],
                ['月均月票收入', pi.monthly_avg_ticket ? '¥' + pi.monthly_avg_ticket.toLocaleString() : '-'],
            );
        }

        rows.forEach(([k, v]) => {
            html += `<tr><th>${k}</th><td>${v || '-'}</td></tr>`;
        });
        html += '</tbody></table>';

        // 项目评估区
        if (ct.overall_assessment || ct.evaluation_scores) {
            html += '<h4 style="margin:12px 0 6px;font-size:13px;">项目评估</h4>';
            // 评估概要表
            html += '<table><tbody>';
            html += `<tr><th>项目</th><th>数值</th><th>状态</th></tr>`;
            const ratio = ct.monthly_consume_ratio != null ? (ct.monthly_consume_ratio * 100).toFixed(1) + '%' : '-';
            html += `<tr><td>月均消耗比例</td><td>${ratio}</td><td>${ct.consume_ratio_status || '-'}</td></tr>`;
            const discount = ct.actual_purchase_discount != null ? ct.actual_purchase_discount : '-';
            const discountNote = ct.discount_range ? ` (${ct.discount_range})` : '';
            html += `<tr><td>实际采买折扣</td><td>${discount}</td><td>${(ct.discount_status || '-') + discountNote}</td></tr>`;
            html += `<tr><td>整体评估情况</td><td colspan="2">${ct.overall_assessment || '-'}</td></tr>`;
            html += '</tbody></table>';

            // 评分表
            if (ct.evaluation_scores && ct.evaluation_scores.length > 0) {
                html += '<table style="margin-top:8px;"><tbody>';
                html += '<tr><th>所属类别</th><th>需填写</th><th>得分</th></tr>';
                ct.evaluation_scores.forEach(s => {
                    html += `<tr><td>${s.category}</td><td>${s.value || '-'}</td><td>${s.score || '-'}</td></tr>`;
                });
                if (ct.risk_rating) {
                    html += `<tr><td><b>风险评分</b></td><td colspan="2"><b>${ct.risk_rating}</b></td></tr>`;
                }
                html += '</tbody></table>';
            }
        }

        parsedPreview.innerHTML = html;
    }

    // --- 开始审核 ---
    startBtn.addEventListener('click', async () => {
        if (!sessionId) return;

        startBtn.disabled = true;
        statusBar.classList.remove('hidden');
        resultSection.classList.remove('hidden');
        resultContent.innerHTML = '';
        comparisonSection.classList.add('hidden');
        comparisonContent.innerHTML = '';
        toolCalls.innerHTML = '';
        fullResult = '';
        statusText.textContent = '启动审核...';

        try {
            // 启动审核
            const resp = await fetch('/api/audit/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    business_type: businessType.value,
                    enable_llm: enableLLM.checked,
                }),
            });
            const data = await resp.json();

            if (!resp.ok) {
                statusText.textContent = '启动失败: ' + (data.detail || '');
                startBtn.disabled = false;
                return;
            }

            // 连接 SSE 流
            connectSSE(data.stream_url);
        } catch (e) {
            statusText.textContent = '错误: ' + e.message;
            startBtn.disabled = false;
        }
    });

    // --- SSE 流式接收 ---
    function connectSSE(url) {
        let gotError = false;
        const es = new EventSource(url);

        es.addEventListener('status', (e) => {
            const data = JSON.parse(e.data);
            const phaseMap = {
                'thinking': 'AI 思考中...',
            };
            statusText.textContent = phaseMap[data.phase] || data.phase;
        });

        es.addEventListener('token', (e) => {
            const data = JSON.parse(e.data);
            fullResult += data.text;
            resultContent.innerHTML = renderMarkdown(fullResult);
            resultContent.scrollTop = resultContent.scrollHeight;
        });

        es.addEventListener('tool_call', (e) => {
            const data = JSON.parse(e.data);
            const existing = toolCalls.querySelector(`[data-tool="${data.tool}"]`);

            if (existing) {
                existing.querySelector('.tool-status').textContent =
                    data.status === 'done' ? '完成' : '执行中...';
            } else {
                const div = document.createElement('div');
                div.className = 'tool-call-item';
                div.dataset.tool = data.tool;
                div.innerHTML = `<span class="tool-name">${getToolLabel(data.tool)}</span> <span class="tool-status">${data.status === 'done' ? '完成' : '执行中...'}</span>`;
                toolCalls.appendChild(div);
            }
        });

        es.addEventListener('result', (e) => {
            const data = JSON.parse(e.data);
            if (data.markdown) {
                fullResult = data.markdown;
                // 调试：在控制台打印 LLM 输出
                console.log('=== LLM 原始输出 ===');
                console.log(fullResult);
                console.log('=== 渲染后内容 ===');
                resultContent.innerHTML = renderMarkdown(fullResult);
            }
        });

        es.addEventListener('comparison_data', (e) => {
            const data = JSON.parse(e.data);
            renderComparison(data);
        });

        es.addEventListener('error', (e) => {
            try {
                const data = JSON.parse(e.data);
                statusText.textContent = data.message || '未知错误';
            } catch {
                statusText.textContent = '审核出错';
            }
            resultContent.innerHTML = `<div class="error-msg">${statusText.textContent}</div>`;
            gotError = true;
            es.close();
            startBtn.disabled = false;
        });

        es.addEventListener('done', () => {
            statusText.textContent = '审核完成';
            document.querySelector('.spinner')?.style && (document.querySelector('.spinner').style.display = 'none');
            es.close();
            startBtn.disabled = false;
        });

        es.onerror = () => {
            if (!gotError) {
                statusText.textContent = '连接断开，请检查服务是否正常';
                resultContent.innerHTML = `<div class="error-msg">连接断开，请检查服务是否正常</div>`;
            }
            startBtn.disabled = false;
            es.close();
        };
    }

    function getToolLabel(name) {
        const labels = {
            'fetch_bem_data': '获取BEM数据',
            'lookup_company': '查询企业信息',
        };
        return labels[name] || name;
    }

    // --- 简易 Markdown 渲染 ---
    function renderMarkdown(md) {
        // 过滤掉包含"不输出内容"的段落（按标题分段处理）
        const sections = md.split(/^(#{1,3}\s.+)$/gm);
        const filteredSections = [];

        for (let i = 0; i < sections.length; i++) {
            const section = sections[i];
            if (!section.trim()) continue;

            // 检查该段落是否包含不输出的关键字
            const hasExcluded = EXCLUDED_PATTERNS.some(pattern => section.includes(pattern));
            if (!hasExcluded) {
                filteredSections.push(section);
            }
        }
        md = filteredSections.join('');

        // Pre-process: convert inline C{n}【item】[status] description to table rows
        md = md.replace(/^[ \t]*(C\d+)\s*【([^】]+)】\s*\[([^\]]+)\]\s*(.*)$/gm, '| $1 | $2 | $3 | | $4 |');

        // Render all pipe-delimited blocks as tables
        // Handles both: tables with headers (C1-C4) and standalone data blocks (C5+)
        let html = md
            .replace(/((?:^[ \t]*\|[^\n]+?\|[ \t]*(?:\n|$)){2,})/gm, (match, whole) => {
                const lines = whole.trim().split('\n').map(l => l.trim()).filter(l => l);
                if (lines.length < 2) return match;

                // Detect header: contains "序号" or second line is a separator
                const firstIsHeader = lines[0].includes('序号') || /^\|[\s\-:|]+\|$/.test(lines[1] || '');
                let ths, dataStart;
                if (firstIsHeader) {
                    const headerParts = lines[0].split('|');
                    ths = headerParts.slice(1, -1).map(s => s.trim()).map(s => `<th>${s}</th>`).join('');
                    dataStart = /^\|[\s\-:|]+\|$/.test(lines[1]) ? 2 : 1;
                } else {
                    ths = '<th>序号</th><th>检查项</th><th>状态</th><th>资料数量</th><th>说明</th>';
                    dataStart = 0;
                }

                const rows = [];
                for (let i = dataStart; i < lines.length; i++) {
                    const line = lines[i];
                    if (!line.startsWith('|')) continue;
                    if (/^\|[\s\-:|]+\|$/.test(line)) continue;
                    const rowParts = line.split('|');
                    const tds = rowParts.slice(1, -1).map(s => s.trim()).map(s => `<td>${s}</td>`).join('');
                    rows.push(`<tr>${tds}</tr>`);
                }

                if (rows.length === 0) return match;
                return `<table><thead><tr>${ths}</tr></thead><tbody>${rows.join('')}</tbody></table>`;
            })
            // 标题
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            // 分隔线
            .replace(/^---$/gm, '<hr>')
            // 粗体
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            // 行内代码
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // 换行
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        return '<p>' + html + '</p>';
    }

    // --- 复制结果 ---
    copyBtn.addEventListener('click', () => {
        const doCopy = (text) => {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.cssText = 'position:fixed;left:-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        };
        const text = fullResult || resultContent.innerText;
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(() => {
                    copyBtn.textContent = '已复制';
                    setTimeout(() => { copyBtn.textContent = '复制'; }, 1500);
                }).catch(() => {
                    doCopy(text);
                    copyBtn.textContent = '已复制';
                    setTimeout(() => { copyBtn.textContent = '复制'; }, 1500);
                });
            } else {
                doCopy(text);
                copyBtn.textContent = '已复制';
                setTimeout(() => { copyBtn.textContent = '复制'; }, 1500);
            }
        } catch {
            doCopy(text);
            copyBtn.textContent = '已复制';
            setTimeout(() => { copyBtn.textContent = '复制'; }, 1500);
        }
    });

    // --- 数据对比渲染 ---
    function renderComparison(data) {
        if (!data) return;

        let html = '';

        // BEM 脚本错误提示
        if (data.bem_error) {
            html += '<div class="error-msg" style="margin-bottom:12px">';
            html += '<strong>BEM 数据获取失败：</strong>' + escapeHtml(data.bem_error);
            if (data.bem_stderr) {
                html += '<details style="margin-top:8px;font-size:12px"><summary>详细日志</summary><pre style="margin-top:4px;white-space:pre-wrap;font-size:11px;color:#999">' + escapeHtml(data.bem_stderr) + '</pre></details>';
            }
            html += '</div>';
        }

        // 关键指标对比表
        if (data.summary && data.summary.length > 0) {
            html += '<h3 class="comparison-subtitle">关键指标对比</h3>';
            html += '<table class="comparison-table"><thead><tr>';
            html += '<th>指标</th><th>上传数据</th><th>BEM 系统数据</th><th>差异</th><th>状态</th>';
            html += '</tr></thead><tbody>';

            data.summary.forEach(item => {
                const statusClass = item.status === 'match' ? 'diff-match' :
                                    item.status === 'warning' ? 'diff-warning' :
                                    item.status === 'skip_bem_zero' ? 'diff-skip' : 'diff-info';
                const statusLabel = item.status === 'match' ? '一致' :
                                    item.status === 'warning' ? '有差异' :
                                    item.status === 'skip_bem_zero' ? '跳过对比' : '参考';
                const excelDisplay = formatValue(item.excel_value, item.unit);
                const bemDisplay = item.status === 'info' ? item.bem_value : formatValue(item.bem_value, item.unit);
                const diffDisplay = item.diff_percent != null ? item.diff_percent + '%' : '-';

                html += `<tr class="${statusClass}">`;
                html += `<td>${item.label}</td>`;
                html += `<td>${excelDisplay}</td>`;
                html += `<td>${bemDisplay}</td>`;
                html += `<td>${diffDisplay}</td>`;
                html += `<td><span class="diff-badge ${statusClass}">${statusLabel}</span></td>`;
                html += '</tr>';
            });

            html += '</tbody></table>';
        }

        // 月度收入明细 — 临停
        const tempDetail = data.monthly_detail?.temp_parking || [];
        if (tempDetail.length > 0) {
            html += renderMonthlyDetail('月度临停收入明细', tempDetail, '元');
        }

        // 月度收入明细 — 月票
        const ticketDetail = data.monthly_detail?.monthly_ticket || [];
        if (ticketDetail.length > 0) {
            html += renderMonthlyDetail('月度月票收入明细', ticketDetail, '元');
        }

        // 月票类型
        const ticketTypes = data.ticket_types || [];
        if (ticketTypes.length > 0) {
            html += '<h3 class="comparison-subtitle">月票类型</h3>';
            html += '<table class="comparison-table"><thead><tr>';
            html += '<th>名称</th><th>价格</th><th>类别</th><th>在用数量</th>';
            html += '</tr></thead><tbody>';

            ticketTypes.forEach(tt => {
                html += `<tr>`;
                html += `<td>${tt.name}</td>`;
                html += `<td>${tt.price != null ? '¥' + tt.price.toLocaleString() : '-'}</td>`;
                html += `<td>${tt.category || (tt.is_internal ? '内部/VIP' : '对外办理')}</td>`;
                html += `<td>${tt.active_count != null ? tt.active_count : '-'}</td>`;
                html += '</tr>';
            });

            html += '</tbody></table>';
        }

        // 企业信息
        const company = data.company_info;
        if (company) {
            html += '<h3 class="comparison-subtitle">企业信息（企查查）</h3>';
            html += '<table class="comparison-table"><tbody>';
            const companyRows = [
                ['企业名称', company.name],
                ['参保人数', company.social_insurance_count > 0 ? company.social_insurance_count + '人' : (company.error ? '需人工查询' : '-')],
                ['经营状态', company.status],
                ['注册资本', company.registered_capital],
                ['成立日期', company.established_date],
            ];
            companyRows.forEach(([k, v]) => {
                html += `<tr><th>${k}</th><td>${v || '-'}</td></tr>`;
            });
            html += '</tbody></table>';
        }

        if (html) {
            comparisonContent.innerHTML = html;
            comparisonSection.classList.remove('hidden');
        }
    }

    function renderMonthlyDetail(title, rows, unit) {
        let html = `<h3 class="comparison-subtitle collapsible" onclick="this.parentElement.querySelector('.detail-body').classList.toggle('collapsed')">${title} <span class="collapse-hint">点击展开/收起</span></h3>`;
        html += '<div class="detail-body collapsed">';
        html += '<table class="comparison-table monthly-detail-table"><thead><tr>';
        html += '<th>月份</th><th>上传数据</th><th>BEM 数据</th><th>状态</th>';
        html += '</tr></thead><tbody>';

        rows.forEach(row => {
            const statusClass = row.status === 'match' ? 'diff-match' :
                                row.status === 'warning' ? 'diff-warning' : '';
            html += `<tr class="${statusClass}">`;
            html += `<td>${row.month}</td>`;
            html += `<td>${formatValue(row.excel, unit)}</td>`;
            html += `<td>${formatValue(row.bem, unit)}</td>`;
            const statusLabel = row.status === 'match' ? '一致' :
                                row.status === 'warning' ? '有差异' : '-';
            html += `<td><span class="diff-badge ${statusClass}">${statusLabel}</span></td>`;
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        return html;
    }

    function formatValue(val, unit) {
        if (val == null) return '-';
        if (typeof val === 'number') {
            return '¥' + val.toLocaleString() + (unit && unit !== '元' ? unit : '');
        }
        return val;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

})();
