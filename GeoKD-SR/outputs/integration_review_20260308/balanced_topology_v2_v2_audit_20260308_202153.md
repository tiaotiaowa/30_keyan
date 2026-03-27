# GeoKD-SR 四级审查报告

> **审查时间**: 2026-03-08T20:21:53.314211
> **数据文件**: data\geosr_chain\balanced_topology_v2.jsonl
> **数据总量**: 9512 条

---

## 一、执行摘要

- **整体通过率**: 60.0%
- **严重问题**: 0 个
- **重要问题**: 2772 个

### 审查层级概览

| 层级 | 名称 | 检查项 | 通过项 | 通过率 | 状态 |
|------|------|--------|--------|--------|------|
| L1 | 格式审查 | 4 | 4 | 100% | ✅ |
| L2 | 逻辑审查 | 8 | 6 | 75% | ⚠️ |
| L3 | 分布审查 | 8 | 2 | 25% | ❌ |
| L4 | 语义审查 | 10 | 4 | 40% | ❌ |

---

## 二、L1 格式审查

### 检查项详情

| ID | 检查项 | 通过率 | 状态 |
|----|--------|--------|------|
| L1-1 | 字段完整性 | - | - |
| L1-2 | 数据类型 | - | - |
| L1-3 | ID唯一性 | - | - |
| L1-4 | JSON格式 | - | - |


---

## 三、L2 逻辑审查

### 检查项详情

| ID | 检查项 | 通过率 | 状态 |
|----|--------|--------|------|
| L2-5 | 推理链步数 | - | - |
| L2-6 | 推理链字段 | - | - |
| L2-7 | 坐标有效性 | - | - |
| L2-8 | 坐标一致性 | - | - |
| L2-9 | difficulty一致性 | - | - |
| L2-10 | 答案逻辑 | - | - |
| L2-11 | 距离准确性 | - | - |
| L2-12 | entity_to_token | - | - |

### 问题详情

- 🟡 **geosr_directional_prompt_5374_2436**: reasoning_chain应为5步，实际6步
- 🟢 **geosr_directional_prompt_5374_2436**: 步骤4缺少calculation_result字段
- 🟢 **geosr_directional_prompt_1447_7597**: 山东省的坐标在推理链和entities中不一致
- 🟢 **geosr_metric_prompt_1449_1866**: 邯郸的坐标在推理链和entities中不一致
- 🟢 **geosr_composite_prompt_1450_7852**: 百色的坐标在推理链和entities中不一致
- 🟢 **geosr_topological_prompt_7537_2353**: 七台河的坐标在推理链和entities中不一致
- 🟢 **geosr_topological_prompt_7540_8336**: 安徽省的坐标在推理链和entities中不一致
- 🟢 **geosr_topological_prompt_7576_8722**: 福建省的坐标在推理链和entities中不一致
- 🟡 **geosr_metric_prompt_0002_7592**: difficulty=medium与score=1.3不匹配
- 🟡 **geosr_metric_prompt_0003_3851**: difficulty=medium与score=1.3不匹配
- 🟡 **geosr_metric_prompt_0004_5700**: difficulty=medium与score=1.8不匹配
- 🟡 **geosr_directional_prompt_0005_8238**: difficulty=medium与score=1.7不匹配
- 🟡 **geosr_directional_prompt_0011_5082**: difficulty=hard与score=1.7不匹配
- 🟡 **geosr_composite_prompt_0012_9702**: difficulty=easy与score=3.2不匹配
- 🟡 **geosr_composite_prompt_0013_7991**: difficulty=medium与score=3.7不匹配
- 🟡 **geosr_composite_prompt_0014_5246**: difficulty=medium与score=3.7不匹配
- 🟡 **geosr_metric_prompt_0015_4919**: difficulty=hard与score=1.8不匹配
- 🟡 **geosr_composite_prompt_0017_7275**: difficulty=easy与score=3.2不匹配
- 🟡 **geosr_metric_prompt_0018_9890**: difficulty=medium与score=1.3不匹配
- 🟡 **geosr_metric_prompt_0021_9947**: difficulty=hard与score=1.3不匹配
- ... 共 3383 个问题

---

## 四、L3 分布审查

### 检查项详情

| ID | 检查项 | 通过率 | 状态 |
|----|--------|--------|------|
| L3-13 | directional分布 | - | - |
| L3-14 | topological分布 | - | - |
| L3-15 | metric分布 | - | - |
| L3-16 | composite分布 | - | - |
| L3-17 | easy难度分布 | - | - |
| L3-18 | medium难度分布 | - | - |
| L3-19 | hard难度分布 | - | - |
| L3-20 | 实体分布CV | - | - |

### 问题详情

- 🟢 **distribution**: 实体分布变异系数0.704超过0.7

---

## 五、L4 语义审查

### 检查项详情

| ID | 检查项 | 通过率 | 状态 |
|----|--------|--------|------|
| L4-21 | Within关键词 | - | - |
| L4-22 | Contains关键词 | - | - |
| L4-23 | Adjacent关键词 | - | - |
| L4-24 | Disjoint关键词 | - | - |
| L4-25 | Overlap关键词 | - | - |
| L4-26 | 方向表达统一 | - | - |
| L4-27 | spatial_tokens覆盖 | - | - |
| L4-28 | 提示词分布 | - | - |
| L4-29 | 省份覆盖 | - | - |
| L4-30 | 问题多样性 | - | - |

### 问题详情

- 🟢 **geosr_topological_prompt_4404_4934**: within关系缺少关键词: ['位于', '内', '境内', '在...里面']
- 🟢 **geosr_topological_prompt_8320_3660**: within关系缺少关键词: ['位于', '内', '境内', '在...里面']
- 🟢 **geosr_topological_prompt_8325_7951**: within关系缺少关键词: ['位于', '内', '境内', '在...里面']
- 🟢 **geosr_topological_prompt_0001_3041**: contains关系缺少关键词: ['包含', '含有', '有...在里面', '管辖']
- 🟢 **geosr_topological_prompt_0215_6150**: contains关系缺少关键词: ['包含', '含有', '有...在里面', '管辖']
- 🟢 **geosr_topological_prompt_0250_6218**: contains关系缺少关键词: ['包含', '含有', '有...在里面', '管辖']
- 🟢 **geosr_topological_prompt_0407_2276**: contains关系缺少关键词: ['包含', '含有', '有...在里面', '管辖']
- 🟢 **geosr_topological_prompt_0426_2083**: contains关系缺少关键词: ['包含', '含有', '有...在里面', '管辖']
- 🟢 **geosr_topological_prompt_0433_5179**: contains关系缺少关键词: ['包含', '含有', '有...在里面', '管辖']
- 🟢 **geosr_topological_prompt_0536_4643**: contains关系缺少关键词: ['包含', '含有', '有...在里面', '管辖']
- ... 共 9280 个问题

---

## 六、结论与建议

⚠️ **数据质量可接受**: 存在重要问题，建议修复后使用。

**改进建议**:

- **L2**: 3383个问题 (Critical: 0, Important: 2772)
- **L3**: 1个问题 (Critical: 0, Important: 0)
- **L4**: 9280个问题 (Critical: 0, Important: 0)

---

*报告生成时间: 2026-03-08 20:21:53*
