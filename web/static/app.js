/**
 * 资源置换评估系统 — 前端逻辑
 */
(function() {
    const $ = (sel) => document.querySelector(sel);

    const dropZone = $('#drop-zone');
    const fileInput = $('#file-input');
    const filePreview = $('#file-preview');
    const fileName = $('#file-name');
    const removeBtn = $('#remove-file');
    const parsedPreview = $('#parsed-preview');
    const businessType = $('#business-type');
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
            ['地址', pi.car_park_address],
            ['合作方类型', pi.property_type],
            ['承包到期', pi.contract_expire_date],
            ['车位数量', pi.parking_spaces],
        ];

        if (data.business_type === 'spot_exchange' && Object.keys(sec).length > 0) {
            rows.push(
                ['车场业态', pi.business_nature],
                ['收费规则', pi.parking_fee_rule],
                ['设备金额', sec.equipment_amount ? '¥' + sec.equipment_amount.toLocaleString() : '-'],
                ['置换车位数', sec.replacement_spaces || '-'],
                ['合同月数', sec.contract_months ? sec.contract_months + '个月' : '-'],
                ['月卡费用', sec.monthly_card_fee ? '¥' + sec.monthly_card_fee.toLocaleString() + '/月' : '-'],
                ['车位采购单价', sec.purchase_unit_price ? '¥' + sec.purchase_unit_price.toFixed(2) + '/月' : '-'],
                ['项目总成本', sec.total_cost ? '¥' + Math.round(sec.total_cost).toLocaleString() : '-'],
                ['我司总收入', sec.total_revenue ? '¥' + Math.round(sec.total_revenue).toLocaleString() : '-'],
                ['我司利润额', sec.our_profit ? '¥' + Math.round(sec.our_profit).toLocaleString() : '-'],
            );
        } else {
            rows.push(
                ['自有渠道', pi.has_own_channel],
                ['月均临停收入', pi.monthly_avg_temp ? '¥' + pi.monthly_avg_temp.toLocaleString() : '-'],
                ['月均月票收入', pi.monthly_avg_ticket ? '¥' + pi.monthly_avg_ticket.toLocaleString() : '-'],
                ['合同金额', ct.contract_amount ? '¥' + ct.contract_amount.toLocaleString() : '-'],
                ['停车券总价值', ct.voucher_total_value ? '¥' + ct.voucher_total_value.toLocaleString() : '-'],
            );
        }

        rows.forEach(([k, v]) => {
            html += `<tr><th>${k}</th><td>${v || '-'}</td></tr>`;
        });
        html += '</tbody></table>';
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
        let html = md
            // 表格
            .replace(/^\|(.+)\|\s*\n\|[-:\s|]+\|\s*\n((?:\|.+\|\s*\n)*)/gm, (match, header, body) => {
                const ths = header.split('|').map(s => s.trim()).filter(Boolean).map(s => `<th>${s}</th>`).join('');
                const rows = body.trim().split('\n').map(row => {
                    const tds = row.split('|').map(s => s.trim()).filter(Boolean).map(s => `<td>${s}</td>`).join('');
                    return `<tr>${tds}</tr>`;
                }).join('');
                return `<table><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table>`;
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
        navigator.clipboard.writeText(fullResult).then(() => {
            copyBtn.textContent = '已复制';
            setTimeout(() => { copyBtn.textContent = '复制'; }, 1500);
        });
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
                ['参保人数', company.social_insurance_count != null ? company.social_insurance_count + '人' : '-'],
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
