# 审核字段范围规则

> 本文件定义两种业务类型的审核字段范围、检查方式和输出规则。
> 所有审核 checklist、completeness check 和 skill 文件均以此文件为准。

---

## 停车券业务 (parking_voucher)

### 项目基本信息表 — 全部检查

| 序号 | 字段 key | 中文名 | 检查方式 |
|------|----------|--------|---------|
| 1 | car_park_name | 车场名称 | 完整性 |
| 2 | car_park_address | 车场地址 | 完整性 |
| 3 | property_type | 合作客户主体/产权方承包方 | 完整性 |
| 4 | contract_expire_date | 承包到期时间 | 完整性 + 承包方时必填 |
| 5 | parking_fee_rule | 收费规则 | 完整性 |
| 6 | allow_posting | 是否允许张贴物料 | 完整性 |
| 7 | has_own_channel | 是否自有小程序/ETC | 完整性 |
| 8 | parking_spaces | 车位数量 | 完整性 |
| 9 | monthly_income | 月度收入（临停+月租） | 完整性 + BEM 对比 |

### 测算工具表 — 仅检查以下 10 个字段

| 序号 | 字段 key | 中文名 | 检查方式 |
|------|----------|--------|---------|
| 1 | equipment_service_amount | 设备和服务置换金额 | 完整性 |
| 2 | cash_purchase_amount | 现金采买金额 | 完整性 |
| 3 | payment_method | 付款方式 | 完整性 |
| 4 | business_fee | 业务费 | 有则 📋 人工评估 |
| 5 | discount_rate | 采买折扣 | 完整性 |
| 6 | contract_months | 合同有效年限 | 完整性 + 期限检查 |
| 7 | voucher_consume_months | 券消耗年限 | 完整性 + vs 合同年限 |
| 8 | vat_rate | 增值税普通发票 | 完整性 |
| 9 | monthly_temp_income | 车场月均临停收入 | 完整性 + BEM 对比 |
| 10 | monthly_ticket_income | 车场月均月租收入 | 完整性 + BEM 对比（见特殊规则） |

### 项目评估 — 原样输出，不做验证

| 序号 | 字段 key | 中文名 | 检查方式 |
|------|----------|--------|---------|
| E1 | monthly_consume_ratio | 月均消耗比例 | 原样输出 |
| E2 | actual_purchase_discount | 实际采买折扣 | 原样输出 |
| E3 | overall_assessment | 整体评估情况 | 原样输出 |
| E4+ | 其他评估字段 | 提成系数表、风险评分等 | 原样输出 |

**原样输出**：以表格形式展示 Excel 中的评估数据（序号 E1、E2...），不做通过/不通过判断。

### 不输出的字段

以下测算工具字段不检查、不输出：

- contract_amount（合同金额）
- voucher_total_value（停车券总价值）
- voucher_monthly_share（停车券月均分摊）
- monthly_total_income（月均收入合计）
- project_gross_profit（项目整体毛利）
- equipment_gross_profit（设备预估毛利）

### 特殊规则：月租收入 BEM 数据全为 0

当 BEM 月票数据的 `monthly_ticket.summary.monthly_avg` 为 0，且 `monthly_ticket.monthly` 中所有 `ticket_income` 均为 0 时：

- **跳过月租收入的对比验证**
- 仍然显示测算表中的月租收入数值
- 在输出中标注"BEM 月票数据为 0，跳过对比"
- 不做通过/不通过判断

---

## 车位置换业务 (spot_exchange)

### 项目基本信息表 — 全部检查

| 序号 | 字段 key | 中文名 | 检查方式 |
|------|----------|--------|---------|
| 1 | car_park_name | 车场名称 | 完整性 |
| 2 | car_park_address | 车场地址 | 完整性 |
| 3 | property_type | 合作客户主体 | 完整性 |
| 4 | contract_expire_date | 承包到期时间 | 完整性 + 承包方时必填 |
| 5 | parking_fee_rule | 收费规则 | 完整性 |
| 6 | allow_posting | 是否允许张贴物料 | 完整性 |
| 7 | has_own_channel | 是否自有小程序/ETC | 完整性 |
| 8 | monthly_income | 月度收入（临停+月租） | 完整性 + BEM 对比 |

### 测算工具表 — 仅检查以下 6 个字段

| 序号 | 字段 key | 中文名 | 检查方式 |
|------|----------|--------|---------|
| 1 | equipment_amount | 设备和服务置换金额 | 完整性 + vs CRM 结算价 |
| 2 | vat_rate | 增值税专用发票 | 完整性 |
| 3 | monthly_card_fee | 对外办理月卡费用 | 完整性 + BEM 对比 |
| 4 | replacement_spaces | 置换车位数 | 完整性 |
| 5 | profit_share_ratio | 回本后甲方分润比例 | 完整性 |
| 6 | contract_months | 合同有效年限 | 完整性 + ≥36 个月 |

### 项目评估 — 原样输出，不做验证

| 序号 | 字段 key | 中文名 | 检查方式 |
|------|----------|--------|---------|
| E1 | monthly_consume_ratio | 月均消耗比例 | 原样输出 |
| E2 | actual_purchase_discount | 实际采买折扣 | 原样输出 |
| E3 | overall_assessment | 整体评估情况 | 原样输出 |
| E4+ | 其他评估字段 | 提成系数表、风险评分等 | 原样输出 |

**原样输出**：以表格形式展示 Excel 中的评估数据（序号 E1、E2...），不做通过/不通过判断。

### 不输出的字段

以下测算工具字段不检查、不输出：

- per_space_monthly_income（单车位月均收入）
- purchase_unit_price（车位采购单价）
- tax_cost（税金成本）
- total_cost（项目总成本）
- total_revenue（我司总收入）
- our_profit（我司利润额）
- customer_profit（客户利润额）
- crm_quote_no / crm_m_factor / crm_settlement_total / crm_service_fee

---

## 通用规则

1. 项目基本信息表的字段两个业务类型都全量检查
2. 测算工具表只检查上述明确列出的字段，其他字段不输出
3. 项目评估区域一律以表格形式输出（序号 E1、E2...），原样展示数据，不做验证判断
4. Excel 解析器继续解析所有字段（保留原始数据），只是审核输出中不展示
5. 业务调整时只需修改本文件，checklist 和 skill 文件引用本文件内容
6. **合作客户主体检查规则**：
   - 如果填写的是具体公司名称（如"贵州西部建材城开发有限公司"），则查询企查查获取参保人数
   - 如果填写的是通用词（如"承包方"、"产权方"、"产权方/承包方"、"产权方-承包方"等），则：
     - 不调用企查查查询工具
     - 在审核结果中标注"❌ 合作客户主体填写不正确：请填写具体公司名称"

## 输出稳定性要求（严格执行）

7. **输出内容必须稳定**：同一份 Excel 文件的审核结果应该是完全一致的，不能随机变化
8. **只输出指定字段**：审核结果中只能出现本文件中列出的字段，不得添加任何其他字段
9. **不得添加额外段落**：除了"基本信息"、"检查结果"、"项目评估"、"趋势分析"、"总结"这五个固定区域外，不得添加其他任何区域或段落
10. **不得添加表情符号**：除了状态标记（✅、⚠️、❌、📋、🔵）外，不得在文本中添加任何表情符号或装饰性符号
11. **不得修改字段名**：使用本文件中列出的字段中文名，不得简化、扩展或修改
