# GeoKD-SR 数据异常筛查报告

> **生成时间**: 2026-03-10 15:33:28
> **数据文件**: `data/final/final_1_cleaned.jsonl`
> **总样本数**: 11,656 条

---

## 一、筛查结果摘要

| 指标 | 数值 |
|------|------|
| 总记录数 | 11,656 |
| 异常记录数 | 1,008 |
| 异常率 | 8.65% |
| 总异常数 | 1,021 |
| 异常类型数 | 4 |

---

## 二、异常类型分布

| 异常类型 | 数量 | 占比 | 严重程度 | 处理优先级 |
|----------|------|------|----------|------------|
| answer_mismatch | 759 | 74.34% | 🟡 低 | P3 |
| entity_not_in_entities | 168 | 16.45% | 🟡 中 | P2 |
| invalid_entity_type | 93 | 9.11% | 🔴 高 | P1 |
| chain_length_error | 1 | 0.10% | 🔴 高 | P0 |

---

## 三、异常详情分析

### 3.1 answer_mismatch (759条)

**问题描述**: `answer` 字段与 `reasoning_chain` 最后一步的 `final_answer` 语义检测为不一致。

**实际情况**: 经人工抽查，大部分为语义相同但表述不同，属于**误报**。

**示例**:
| record_id | answer | final_answer | 判定 |
|-----------|--------|--------------|------|
| geosr_topological_prompt_3022_6496 | 同江市不属于湖北省... | 同江不在湖北省内 | ✅ 语义一致 |
| geosr_topological_prompt_2497_5705 | 长治市位于山西省境内... | 长治和阜新分别位于不同的省份... | ✅ 语义一致 |
| geosr_topological_prompt_10706_2394 | 不存在包含关系... | 不存在包含关系 | ✅ 语义一致 |

**建议**:
- 优化检测逻辑，使用语义相似度模型（如sentence-transformers）
- 或放宽检测规则，只标记明显矛盾的情况

---

### 3.2 entity_not_in_entities (168条)

**问题描述**: `reasoning_chain` 中的 `entities_involved` 包含不在 `entities` 列表中的实体名称。

**典型示例**:
| record_id | 缺失实体 | 所在步骤 |
|-----------|----------|----------|
| geosr_topological_prompt_0156_2288 | 珠江口 | step 1 |
| geosr_topological_prompt_10481_1280 | 广东省 | step 1 |
| geosr_topological_prompt_0593_6617 | 长江 | step 1 |

**原因分析**:
1. 实体名称变体（如"广东省" vs "广东"）
2. 生成的推理链引用了额外上下文实体
3. 实体提取不完整

**建议**:
- 统一实体名称规范（建立实体别名映射表）
- 修复时检查并补充缺失实体

---

### 3.3 invalid_entity_type (93条)

**问题描述**: 实体的 `type` 字段值不在合法范围内。

**合法实体类型**: `province`, `city`, `landmark`, `river`, `mountain`, `lake`, `region`

**发现的非法类型**:
| 类型 | 数量 | 建议映射 |
|------|------|----------|
| country | ~40 | region |
| historical | ~30 | landmark |
| district | ~20 | city |

**示例**:
| record_id | entity_name | 当前类型 | 建议类型 |
|-----------|-------------|----------|----------|
| geosr_topological_prompt_8577_1998 | 中国 | country | region |
| geosr_metric_prompt_0111_7242 | 长城遗址 | historical | landmark |
| geosr_directional_prompt_0499_4706 | 朝阳 | district | city |

**修复方案**:
```python
TYPE_MAPPING = {
    'country': 'region',
    'historical': 'landmark',
    'district': 'city'
}
```

---

### 3.4 chain_length_error (1条)

**问题描述**: 推理链长度不为5。

**异常记录**:
- `geosr_directional_prompt_5374_2436`: 长度为6，应为5

**处理方案**:
- 检查该记录推理链内容
- 删除多余步骤或合并步骤

---

## 四、修复优先级建议

### P0 - 立即处理
1. **chain_length_error (1条)**: 修复或删除异常记录

### P1 - 高优先级
2. **invalid_entity_type (93条)**: 批量映射非法类型到合法类型

### P2 - 中优先级
3. **entity_not_in_entities (168条)**: 评估影响范围，决定是否修复

### P3 - 低优先级
4. **answer_mismatch (759条)**: 优化检测逻辑，当前可忽略

---

## 五、修复脚本建议

### 5.1 修复 invalid_entity_type

```python
# scripts/fix_entity_types.py
TYPE_MAPPING = {
    'country': 'region',
    'historical': 'landmark',
    'district': 'city'
}

def fix_entity_types(record):
    for entity in record.get('entities', []):
        if entity.get('type') in TYPE_MAPPING:
            entity['type'] = TYPE_MAPPING[entity['type']]
    return record
```

### 5.2 修复 chain_length_error

```python
# 手动检查并修复
record_id = "geosr_directional_prompt_5374_2436"
# 查看推理链内容，决定保留哪些步骤
```

---

## 六、相关文件

| 文件 | 路径 |
|------|------|
| 筛查脚本 | `scripts/screen_anomalies.py` |
| JSON报告 | `reports/anomaly_report.json` |
| 运行日志 | `logs/screen_anomalies.log` |
| 本报告 | `docs/anomaly_screening_report_20260310.md` |

---

## 七、结论

数据整体质量良好，主要异常为：
1. **误报**: answer_mismatch 大部分为语义一致但表述不同
2. **可修复**: invalid_entity_type 可通过类型映射批量修复
3. **需评估**: entity_not_in_entities 需进一步评估影响

**建议下一步**:
1. 执行 invalid_entity_type 修复
2. 手动检查 chain_length_error 记录
3. 重新运行筛查脚本验证修复效果

---

*报告生成时间: 2026-03-10 15:33:28*
