# BEM 数据获取 Skill

## 描述

从 BEM（智泊云/智汇云）系统获取指定车场的临停收入、月票收入、月票类型数据。
所有 BEM 数据获取必须通过本 skill 下的固化脚本完成，AI 不直接操作 BEM 系统。

## 触发条件

- 进入车场数据复核环节时自动触发
- 运营明确要求获取 BEM 数据时触发

## 输入参数

| 参数 | 必填 | 说明 |
|------|------|------|
| car_park_name | 是 | 车场名称 |
| car_park_id | 否 | 车场ID（如有） |
| date_range | 否 | 查询时间范围，默认近12个月 |

## 执行步骤

### 1. 获取临停收入数据

运行脚本：
```bash
python3 skills/bem-fetch/scripts/fetch_temp_parking.py --car-park "{car_park_name}" [--date-range "{date_range}"]
```

输出 JSON 结构：
```json
{
  "car_park": "车场名称",
  "data_source": "智泊云/智汇云",
  "date_range": "2025-05 ~ 2026-04",
  "monthly": [
    {
      "month": "2026-04",
      "actual_income_wechat": 12345.67,
      "total_income": 15000.00,
      "wechat_mini_income": 8000.00,
      "etc_income": 2000.00
    }
  ],
  "summary": {
    "monthly_avg": 13000.00,
    "trend": "下降/平稳/上升",
    "trend_note": "近3个月环比下降15%"
  }
}
```

关键字段说明：
- `actual_income_wechat`：临停收入-实收金额-微信（与测算表对比的核心字段）
- `total_income`：临停总收入
- `wechat_mini_income`：微信小程序（开放平台）收入
- `etc_income`：ETC 收入

### 2. 获取月票收入数据

运行脚本：
```bash
python3 skills/bem-fetch/scripts/fetch_monthly_ticket.py --car-park "{car_park_name}" [--date-range "{date_range}"]
```

输出 JSON 结构：
```json
{
  "car_park": "车场名称",
  "data_source": "智泊云/智汇云",
  "date_range": "2025-05 ~ 2026-04",
  "monthly": [
    {
      "month": "2026-04",
      "ticket_income": 8000.00
    }
  ],
  "summary": {
    "monthly_avg": 7500.00,
    "trend": "下降/平稳/上升",
    "trend_note": ""
  }
}
```

### 3. 获取月票类型数据

运行脚本：
```bash
python3 skills/bem-fetch/scripts/fetch_ticket_types.py --car-park "{car_park_name}"
```

输出 JSON 结构：
```json
{
  "car_park": "车场名称",
  "ticket_types": [
    {
      "name": "月卡A",
      "price": 300.00,
      "is_internal": false,
      "active_count": 50,
      "category": "对外办理"
    },
    {
      "name": "VIP商户月卡",
      "price": 200.00,
      "is_internal": true,
      "active_count": 10,
      "category": "内部/VIP"
    }
  ]
}
```

关键字段说明：
- `is_internal = false` 的为对外办理月票，用于与测算表对比
- `is_internal = true` 的为内部/VIP月票，不参与对比

## 可消耗收入占比计算

当车场存在自有小程序/APP/ETC 时：

```
可消耗收入占比 = [总计 - 微信小程序（开放平台） - ETC] / 总计
```

数据来源：临停收入中各渠道明细。

## 输出

将上述三个脚本的结果汇总后，提供给调用方（audit skill）使用。
