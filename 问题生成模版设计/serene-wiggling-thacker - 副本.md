# GeoKD-SR 双层数据架构设计方案

## Context

### 问题背景
当前实验设计面临一个根本性质疑：空间关系可以由PostGIS精确计算，为什么要让LLM来做？如果过度结构化，模型可能退化为"空间关系计算器"。

### 解决方案
重新定义研究价值——不是让LLM替代PostGIS做计算，而是验证小模型能否从大模型中**蒸馏学习空间推理能力**：
- **推理能力**：根据已知信息推导空间关系结论
- **自然语言理解**：理解不同表述方式的空间问题并准确回答

### 已确认的关键决策
1. 能力定位：推理能力 + 自然语言理解（非知识检索）
2. 评测场景：有坐标/无坐标两种，分开报告
3. 正负例：方向/距离全正例，拓扑/复合约30%负例
4. 数据规模：10,000实体对 × 4种题型 = 最多40,000条，训练时选择性使用
5. 数据架构：双层结构（实体对事实层 + 题目实例层）

---

## 一、实体对事实层（Layer 1）

### 1.1 结构设计

每个实体对只包含`target_relation`相关的空间事实，按关系类型分5种子结构：

**方向关系对** (`target_relation: "directional"`)
```json
{
  "pair_id": "dir_00142",
  "target_relation": "directional",
  "entity_a": {"name_zh": "武汉市", "centroid": [114.31, 30.59], "type": "city"},
  "entity_b": {"name_zh": "长沙市", "centroid": [112.94, 28.23], "type": "city"},
  "spatial_facts": {
    "direction_8": "东北",
    "azimuth_deg": 29.7
  }
}
```

**距离关系对** (`target_relation: "metric"`)
```json
{
  "pair_id": "metric_00142",
  "target_relation": "metric",
  "entity_a": {"name_zh": "武汉市", "centroid": [114.31, 30.59], "type": "city"},
  "entity_b": {"name_zh": "长沙市", "centroid": [112.94, 28.23], "type": "city"},
  "spatial_facts": {
    "distance_km": 296
  }
}
```

**拓扑关系对** (`target_relation: "topological.contains"` 等5种)
```json
{
  "pair_id": "topo_contains_00001",
  "target_relation": "topological.contains",
  "is_negative": false,
  "entity_a": {"name_zh": "湖北省", "centroid": [112.30, 30.97], "type": "province"},
  "entity_b": {"name_zh": "武汉市", "centroid": [114.31, 30.59], "type": "city"},
  "spatial_facts": {
    "contains": true
  }
}
```

**拓扑负例**
```json
{
  "pair_id": "topo_crosses_00450",
  "target_relation": "topological.crosses",
  "is_negative": true,
  "entity_a": {"name_zh": "长江", "centroid": [113.20, 30.38], "type": "river"},
  "entity_b": {"name_zh": "北京市", "centroid": [116.41, 39.90], "type": "province"},
  "spatial_facts": {
    "crosses": false
  }
}
```

**复合关系对** (direction+topology等)
```json
{
  "pair_id": "comp_dir_topo_00001",
  "target_relation": "composite.direction_topology",
  "is_negative": false,
  "entity_a": {"name_zh": "黄山", "centroid": [118.17, 30.13], "type": "peak"},
  "entity_b": {"name_zh": "安徽省", "centroid": [117.28, 31.86], "type": "province"},
  "spatial_facts": {
    "direction_8": "南",
    "azimuth_deg": 188.5,
    "distance_km": 112,
    "within": true
  }
}
```

### 1.2 数据生成策略：正负例分阶段独立生成

**核心原则**：先全部生成正例（10,000条），再独立生成负例（1,237条），分两个Phase存储，用户按需选择使用。

**正例定义**：空间关系为真的实体对（如"湖北省包含武汉市"→contains=true、"长江穿越湖北省"→crosses=true）
**负例定义**：空间关系为假的实体对（如"长江穿越北京市"→crosses=false、"武汉在河南省内"→within=false）

### 1.3 Phase 1 — 正例数据（10,000条）

| 关系类型 | 子类型 | 正例数 | 说明 |
|---------|--------|--------|------|
| directional | — | 2,500 | 方向总有唯一正确答案 |
| topological.contains | — | 500 | A包含B（contains=true） |
| topological.within | — | 500 | A在B内（within=true） |
| topological.touches | — | 500 | A与B相邻（touches=true） |
| topological.crosses | — | 500 | A穿越B（crosses=true） |
| topological.disjoint | — | 500 | A与B分离（disjoint=true） |
| metric | — | 2,500 | 距离总有确定值 |
| composite.C1(方向+距离) | — | 875 | 方向+距离组合 |
| composite.C2(方向+拓扑) | — | 500 | 方向+拓扑组合（拓扑关系为真） |
| composite.C3(距离+拓扑) | — | 500 | 距离+拓扑组合（拓扑关系为真） |
| composite.C4(三重) | — | 625 | 方向+距离+拓扑（拓扑关系为真） |
| **Phase 1 总计** | | **10,000** | |

> 验证: 2,500 + 2,500 + 2,500 + 875 + 500 + 500 + 625 = 10,000 ✅

### 1.4 Phase 2 — 负例数据（1,237条）

仅对含拓扑分量的关系类型生成负例：

| 关系类型 | 子类型 | 负例数 | 负例含义 |
|---------|--------|--------|---------|
| topological.contains | — | 150 | A不包含B（contains=false） |
| topological.within | — | 150 | A不在B内（within=false） |
| topological.touches | — | 150 | A与B不相邻（touches=false） |
| topological.crosses | — | 150 | A不穿越B（crosses=false） |
| topological.disjoint | — | 150 | A与B不分离（disjoint=false，即有交集） |
| composite.C2(方向+拓扑) | — | 150 | 方向正确但拓扑关系为假 |
| composite.C3(距离+拓扑) | — | 150 | 距离正确但拓扑关系为假 |
| composite.C4(三重) | — | 187 | 方向/距离正确但拓扑关系为假 |
| **Phase 2 总计** | | **1,237** | |

> 验证: 150×5 + 150×2 + 187 = 750 + 300 + 187 = 1,237 ✅

### 1.5 总数据规模

| Phase | 数量 | 用途 |
|-------|------|------|
| Phase 1 (正例) | 10,000 | 基础训练数据 |
| Phase 2 (负例) | 1,237 | 对比实验（可选替换） |
| **总计** | **11,237** | |

### 1.6 负例使用策略

负例独立存储为`pairs_negative.jsonl`，用户在训练时：
- **方案A**: 仅用Phase 1的10,000正例 → 作为baseline
- **方案B**: 从Phase 1中随机抽取1,237条正例替换为Phase 2负例 → 8,763正 + 1,237负 = 10,000
- **方案C**: Phase 1全部 + Phase 2全部 → 11,237条混合训练
- 对比A vs B vs C的评测结果 → 验证负例对模型空间推理能力的影响

---

## 二、题目实例层（Layer 2）

### 2.1 结构设计

每个实体对由LLM生成4种题目实例，通过`pair_id`关联：

**判断题** (`question_type: "true_false"`)
```json
{
  "instance_id": "tf_dir_00142",
  "pair_id": "dir_00142",
  "question_type": "true_false",
  "target_relation": "directional",
  "question": "从长沙出发前往武汉，大致需要朝东北方向行进，这一说法是否正确？",
  "answer": "正确",
  "answer_structured": {"type": "boolean", "value": true},
  "difficulty": "easy"
}
```

**选择题** (`question_type: "choice"`)
```json
{
  "instance_id": "ch_dir_00142",
  "pair_id": "dir_00142",
  "question_type": "choice",
  "target_relation": "directional",
  "question": "小李在长沙出差，周末想去武汉游玩。从长沙看，武汉在哪个方向？\nA. 西北\nB. 东北\nC. 西南\nD. 东南",
  "answer": "B",
  "answer_structured": {"type": "option", "value": "B", "correct_answer": "东北"},
  "difficulty": "medium"
}
```

**填空题** (`question_type: "fill_blank"`)
```json
{
  "instance_id": "fb_dir_00142",
  "pair_id": "dir_00142",
  "question_type": "fill_blank",
  "target_relation": "directional",
  "question": "武汉市位于长沙市的______方向。",
  "answer": "东北",
  "answer_structured": {"type": "keyword", "value": "东北"},
  "difficulty": "easy"
}
```

**问答题** (`question_type: "open_qa"`)
```json
{
  "instance_id": "qa_dir_00142",
  "pair_id": "dir_00142",
  "question_type": "open_qa",
  "target_relation": "directional",
  "question": "请描述武汉相对于长沙的方向关系。",
  "answer": "武汉位于长沙的东北方向。从长沙出发朝东北方向行进即可到达武汉。",
  "answer_structured": {"type": "free_text", "direction": "东北"},
  "difficulty": "medium"
}
```

### 2.2 评测方式

| 题型 | 评测方式 | 确定性 | 指标 |
|------|---------|--------|------|
| 判断题 | 精确匹配(正确/错误) | 100% | Accuracy |
| 选择题 | 精确匹配选项(A/B/C/D) | 100% | Accuracy |
| 填空题 | 关键词匹配+同义词映射 | 高 | Keyword F1 |
| 问答题 | BLEU-4 + ROUGE-L + BERTScore + Spatial F1 | 语义 | 综合指标 |

### 2.3 有坐标/无坐标评测

- **无坐标**：question原样使用（测试模型内部空间知识）
- **有坐标**：在entity名称后追加centroid坐标（测试推理能力）
  - 例："武汉(114.31°E, 30.59°N)"和"长沙(112.94°E, 28.23°N)"之间的方向？
- 两种模式独立评测，分开报告

---

## 三、LLM生成Prompt设计（按空间关系分类）

### 3.0 通用系统Prompt

```
你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
6. 输出严格为JSON，不要添加任何额外文本。
```

### 3.1 方向推理 (directional) Prompt

```
【关系类型】方向推理 (directional)
【任务】判断实体A相对于实体B的8方位方向。

【输入示例】
实体A: {"name_zh": "武汉市", "centroid": [114.31, 30.59], "type": "city"}
实体B: {"name_zh": "长沙市", "centroid": [112.94, 28.23], "type": "city"}
空间事实: {"direction_8": "东北", "azimuth_deg": 29.7}

【输出示例】
{
  "true_false": {
    "question": "判断以下说法是否正确：从长沙出发前往武汉，大致需要朝东北方向行进。",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true, "direction": "东北"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "小李在长沙读大学，周末想去武汉看望朋友。请问从长沙看，武汉在哪个方向？\nA. 西北方向\nB. 东北方向\nC. 西南方向\nD. 东南方向",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "correct_answer": "东北方向"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "武汉市位于长沙市的______方向。",
    "answer": "东北",
    "answer_structured": {"type": "keyword", "value": "东北"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "如果你在长沙旅游，想了解武汉相对于长沙的方位，请描述它们之间的方向关系。",
    "answer": "武汉位于长沙的东北方向。武汉的经纬度(114.31E, 30.59N)相比长沙(112.94E, 28.23N)，经度更大、纬度更高，因此位于东北方。",
    "answer_structured": {"type": "free_text", "direction": "东北"},
    "difficulty": "medium"
  }
}

【多样性要求】
- 判断题：可以正向陈述（"A在B的东北方向"）或反向（"B在A的西南方向"）——注意反向时方向取反
- 选择题：可以嵌入场景（旅行、出差、导航），但核心关系不变
- 填空题：在句子中留方向词填空
- 问答题：要求完整描述方向关系
```

### 3.2 拓扑包含 (topological.contains) Prompt

```
【关系类型】拓扑包含 (topological.contains)
【任务】判断实体A（容器面）是否包含实体B（被含点/面）。

【输入示例 - 正例】
实体A: {"name_zh": "湖北省", "centroid": [112.30, 30.97], "type": "province", "geometry_type": "Polygon"}
实体B: {"name_zh": "武汉市", "centroid": [114.31, 30.59], "type": "city", "geometry_type": "Polygon"}
空间事实: {"contains": true}
是否负例: false

【输出示例】
{
  "true_false": {
    "question": "湖北省的行政区域范围内包含了武汉市，这一说法正确吗？",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于湖北省和武汉市的行政关系，以下哪项描述是正确的？\nA. 武汉市独立于湖北省，是直辖市\nB. 湖北省包含武汉市，武汉是湖北省省会\nC. 武汉市不属于任何省份\nD. 武汉市与湖北省相邻但不包含",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "contains": true},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "武汉市是湖北省的省会城市，它______（在/不在）湖北省的行政区域内。",
    "answer": "在",
    "answer_structured": {"type": "keyword", "value": "在"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请分析湖北省与武汉市之间的空间包含关系。",
    "answer": "武汉市位于湖北省的行政区域内，湖北省包含武汉市。武汉作为湖北省的省会，其行政区域完全在湖北省的管辖范围之内。",
    "answer_structured": {"type": "free_text", "contains": true},
    "difficulty": "easy"
  }
}

【输入示例 - 负例】
实体A: {"name_zh": "河南省", "centroid": [113.65, 34.76], "type": "province", "geometry_type": "Polygon"}
实体B: {"name_zh": "武汉市", "centroid": [114.31, 30.59], "type": "city", "geometry_type": "Polygon"}
空间事实: {"contains": false}
是否负例: true

【负例输出示例】
{
  "true_false": {
    "question": "武汉市属于河南省的行政管辖范围，这一说法是否正确？",
    "answer": "错误",
    "answer_structured": {"type": "boolean", "value": false, "contains": false},
    "difficulty": "easy"
  },
  "choice": {
    "question": "以下哪个省份的行政区域内不包含武汉市？\nA. 湖北省\nB. 河南省\nC. (以上都不包含)\nD. (以上都包含)",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "contains": false, "explanation": "武汉市属于湖北省，不属于河南省"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "武汉市______（属于/不属于）河南省的行政区域。",
    "answer": "不属于",
    "answer_structured": {"type": "keyword", "value": "不属于"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "有人认为武汉市属于河南省，请分析这一说法是否正确并说明理由。",
    "answer": "这一说法不正确。武汉市不属于河南省，而是湖北省的省会城市。武汉位于湖北省东部、长江与汉江交汇处，其行政区域完全在湖北省范围内。河南省虽然与湖北省相邻，但武汉并不在河南省管辖范围内。",
    "answer_structured": {"type": "free_text", "contains": false, "actual_container": "湖北省"},
    "difficulty": "medium"
  }
}

【负例生成规则】
- 判断题：给出一个错误的包含陈述，答案为"错误"
- 选择题：可以问"不包含X的省份是"或"X不属于哪个省份"
- 填空题：用否定词"不属于""不在...内"
- 问答题：给出错误陈述让模型纠正
```

### 3.3 拓扑包含于 (topological.within) Prompt

```
【关系类型】拓扑包含于 (topological.within)
【任务】判断实体A是否在实体B（容器面）内部。

【输入示例】
实体A: {"name_zh": "泰山", "centroid": [117.10, 36.26], "type": "peak"}
实体B: {"name_zh": "山东省", "centroid": [117.00, 36.40], "type": "province"}
空间事实: {"within": true}
是否负例: false

【输出示例】
{
  "true_false": {
    "question": "泰山作为五岳之首，其所在位置在山东省境内，这一判断正确吗？",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true},
    "difficulty": "easy"
  },
  "choice": {
    "question": "泰山位于我国哪个省份的境内？\nA. 河南省\nB. 山西省\nC. 山东省\nD. 河北省",
    "answer": "C",
    "answer_structured": {"type": "option", "value": "C", "within": true},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "五岳之首的泰山坐落于______省境内。",
    "answer": "山东",
    "answer_structured": {"type": "keyword", "value": "山东"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "泰山是中国的著名山峰，请描述它的地理位置归属。",
    "answer": "泰山位于山东省泰安市境内，地处山东省中部。作为五岳之首的东岳，泰山是山东省最具代表性的地理标志之一。",
    "answer_structured": {"type": "free_text", "within": true, "container": "山东省"},
    "difficulty": "medium"
  }
}

【输入示例 - 负例】
实体A: {"name_zh": "华山", "centroid": [110.08, 34.48], "type": "peak"}
实体B: {"name_zh": "河南省", "centroid": [113.65, 34.76], "type": "province"}
空间事实: {"within": false}
是否负例: true

【负例输出示例】
{
  "true_false": {
    "question": "华山位于河南省境内，这一说法是否正确？",
    "answer": "错误",
    "answer_structured": {"type": "boolean", "value": false, "within": false},
    "difficulty": "easy"
  },
  "choice": {
    "question": "华山是中国著名的五岳之一，它位于哪个省份的境内？\nA. 河南省\nB. 陕西省\nC. 山西省\nD. 甘肃省",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "within": false, "actual_within": "陕西省"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "华山______（在/不在）河南省境内，它实际位于陕西省。",
    "answer": "不在",
    "answer_structured": {"type": "keyword", "value": "不在"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "有人说华山在河南省，请分析这一说法是否正确。",
    "answer": "这一说法不正确。华山不在河南省境内。华山位于陕西省渭南市华阴市，是五岳中的西岳。虽然华山地处陕西、河南两省交界区域附近，但它的实际位置在陕西省境内，不属于河南省。",
    "answer_structured": {"type": "free_text", "within": false, "actual_container": "陕西省"},
    "difficulty": "medium"
  }
}
```

### 3.4 拓扑相邻 (topological.touches) Prompt

```
【关系类型】拓扑相邻 (topological.touches)
【任务】判断实体A和实体B是否共享边界（相邻/接壤）。

【输入示例 - 正例】
实体A: {"name_zh": "河北省", "type": "province"}
实体B: {"name_zh": "山东省", "type": "province"}
空间事实: {"touches": true, "shared_border_approx_km": 180}
是否负例: false

【输出示例】
{
  "true_false": {
    "question": "河北省和山东省在地理上接壤相邻，这一说法是否正确？",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true},
    "difficulty": "easy"
  },
  "choice": {
    "question": "以下哪个省份与河北省直接相邻接壤？\nA. 广东省\nB. 山东省\nC. 云南省\nD. 福建省",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "touches": true},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "河北省与______省在地理上直接相邻，两省共享边界。",
    "answer": "山东",
    "answer_structured": {"type": "keyword", "value": "山东"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请描述河北省与山东省之间的空间邻接关系。",
    "answer": "河北省与山东省地理上直接相邻接壤，两省共享约180公里的省际边界。河北省位于山东省的北部，两省在华北平原和山东半岛的交界处相邻。",
    "answer_structured": {"type": "free_text", "touches": true, "shared_border_approx_km": 180},
    "difficulty": "medium"
  }
}

【输入示例 - 负例（城市对）】
实体A: {"name_zh": "武汉市", "type": "city"}
实体B: {"name_zh": "南京市", "type": "city"}
空间事实: {"touches": false}
是否负例: true

【负例输出示例】
{
  "true_false": {
    "question": "武汉市和南京市在行政边界上直接接壤，这一说法正确吗？",
    "answer": "错误",
    "answer_structured": {"type": "boolean", "value": false, "touches": false},
    "difficulty": "medium"
  },
  "choice": {
    "question": "以下哪个城市与武汉市不直接相邻接壤？\nA. 黄石市\nB. 南京市\nC. 孝感市\nD. 黄冈市",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "touches": false},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "武汉市和南京市之间______（有/没有）直接的行政边界接壤。",
    "answer": "没有",
    "answer_structured": {"type": "keyword", "value": "没有"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "有人认为武汉和南京因为同属长江沿线城市所以地理上相邻接壤，请分析这一说法。",
    "answer": "这一说法不正确。武汉和南京虽然都是长江沿岸的重要城市，但两城并不直接相邻接壤。武汉位于湖北省中部，南京位于江苏省西部，两城之间隔着安徽省等地区，直线距离约500多公里，行政边界上没有直接接壤关系。",
    "answer_structured": {"type": "free_text", "touches": false, "explanation": "两城被安徽省隔开"},
    "difficulty": "medium"
  }
}
```

### 3.5 拓扑穿越 (topological.crosses) Prompt

```
【关系类型】拓扑穿越 (topological.crosses)
【任务】判断线状实体A是否穿越面状实体B。

【输入示例 - 正例】
实体A: {"name_zh": "长江", "type": "river", "geometry_type": "Line"}
实体B: {"name_zh": "湖北省", "type": "province", "geometry_type": "Polygon"}
空间事实: {"crosses": true}
是否负例: false

【输出示例】
{
  "true_false": {
    "question": "长江干流穿越湖北省境内，这一地理事实是否正确？",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true},
    "difficulty": "easy"
  },
  "choice": {
    "question": "长江自西向东流经多个省份，以下哪个省份是长江干流穿越的？\nA. 陕西省\nB. 山西省\nC. 湖北省\nD. 河北省",
    "answer": "C",
    "answer_structured": {"type": "option", "value": "C", "crosses": true},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "长江流经中国的多个省份，其中______省是长江干流经过的重要省份之一。",
    "answer": "湖北",
    "answer_structured": {"type": "keyword", "value": "湖北"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请说明长江与湖北省之间的空间穿越关系。",
    "answer": "长江干流自西向东穿越湖北省。从重庆进入湖北后，长江流经三峡地区，穿过宜昌、荆州、武汉、黄冈等城市，最终从鄂东南出境进入江西。湖北省是长江干流经过的重要省份之一。",
    "answer_structured": {"type": "free_text", "crosses": true},
    "difficulty": "medium"
  }
}

【输入示例 - 负例】
实体A: {"name_zh": "黄河", "type": "river"}
实体B: {"name_zh": "江西省", "type": "province"}
空间事实: {"crosses": false}
是否负例: true

【负例输出示例】
{
  "true_false": {
    "question": "黄河穿越江西省，这一说法是否正确？",
    "answer": "错误",
    "answer_structured": {"type": "boolean", "value": false, "crosses": false},
    "difficulty": "easy"
  },
  "choice": {
    "question": "以下哪条河流的干流不穿越江西省？\nA. 赣江\nB. 长江\nC. 黄河\nD. 抚河",
    "answer": "C",
    "answer_structured": {"type": "option", "value": "C", "crosses": false},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "黄河______（穿越/不穿越）江西省境内。",
    "answer": "不穿越",
    "answer_structured": {"type": "keyword", "value": "不穿越"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "黄河是否穿越江西省？请说明原因。",
    "answer": "黄河不穿越江西省。黄河发源于青海，流经四川、甘肃、宁夏、内蒙古、山西、陕西、河南、山东等省份后注入渤海，其干流不经过江西省。江西境内的大河主要是赣江，属于长江水系。",
    "answer_structured": {"type": "free_text", "crosses": false},
    "difficulty": "medium"
  }
}
```

### 3.6 拓扑分离 (topological.disjoint) Prompt

```
【关系类型】拓扑分离 (topological.disjoint)
【任务】判断实体A和实体B在空间上是否完全分离（无交集）。

【输入示例 - 正例(确实分离)】
实体A: {"name_zh": "北京市", "type": "province"}
实体B: {"name_zh": "上海市", "type": "province"}
空间事实: {"disjoint": true}
是否负例: false

【输出示例 - 正例(确实分离)】
{
  "true_false": {
    "question": "北京市和上海市在地理上互不相连，两直辖市之间没有共享边界，这一判断正确吗？",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true, "disjoint": true},
    "difficulty": "easy"
  },
  "choice": {
    "question": "以下哪个省份与北京市在地理上完全分离、不相邻接壤？\nA. 河北省\nB. 天津市\nC. 上海市\nD. 山东省",
    "answer": "C",
    "answer_structured": {"type": "option", "value": "C", "disjoint": true},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "北京市和上海市在空间上______（有/没有）共享边界，两地完全分离。",
    "answer": "没有",
    "answer_structured": {"type": "keyword", "value": "没有"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请分析北京市和上海市之间的空间分离关系。",
    "answer": "北京市和上海市在地理上完全分离，两城市之间没有共享的行政边界。北京位于华北平原北部，上海位于长江入海口，两地直线距离约1068公里，中间隔着河北、天津、山东、安徽、江苏等多个省市。虽然都是直辖市，但空间上不相邻接壤。",
    "answer_structured": {"type": "free_text", "disjoint": true, "distance_km": 1068},
    "difficulty": "medium"
  }
}

【输入示例 - 负例(实际相邻)】
实体A: {"name_zh": "河北省", "type": "province"}
实体B: {"name_zh": "北京市", "type": "province"}
空间事实: {"disjoint": false}
是否负例: true

【负例输出示例】
{
  "true_false": {
    "question": "河北省和北京市在空间上完全分离，没有任何地理交集，这一说法正确吗？",
    "answer": "错误",
    "answer_structured": {"type": "boolean", "value": false, "disjoint": false},
    "difficulty": "easy"
  },
  "choice": {
    "question": "以下哪个省份与北京市在地理上不是完全分离的（即有边界接壤）？\nA. 上海市\nB. 广东省\nC. 河北省\nD. 云南省",
    "answer": "C",
    "answer_structured": {"type": "option", "value": "C", "disjoint": false},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "河北省和北京市在空间上______（是/不是）完全分离的，它们实际上共享边界。",
    "answer": "不是",
    "answer_structured": {"type": "keyword", "value": "不是"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "有人说河北省和北京市在地理上完全分离、没有任何交集，请分析这一说法。",
    "answer": "这一说法不正确。河北省和北京市不是完全分离的，实际上北京市被河北省从北、西、南三面环绕包围，两省市之间有很长的共享行政边界。北京虽然在行政上是独立的直辖市，但地理上完全嵌入河北省境内，两者空间上紧密相连。",
    "answer_structured": {"type": "free_text", "disjoint": false, "actual_relation": "touches/surrounded_by"},
    "difficulty": "medium"
  }
}
```

### 3.7 距离推理 (metric) Prompt

```
【关系类型】距离推理 (metric)
【任务】判断两个实体之间的直线距离。

【输入示例】
实体A: {"name_zh": "北京市", "centroid": [116.41, 39.90], "type": "province"}
实体B: {"name_zh": "上海市", "centroid": [121.47, 31.23], "type": "province"}
空间事实: {"distance_km": 1068}

【输出示例】
{
  "true_false": {
    "question": "北京和上海之间的直线距离约为1068公里，这一说法是否正确？",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true, "distance_km": 1068},
    "difficulty": "easy"
  },
  "choice": {
    "question": "北京和上海是中国最重要的两个直辖市。请问两地之间的直线距离大约是多少？\nA. 约500公里\nB. 约800公里\nC. 约1068公里\nD. 约1500公里",
    "answer": "C",
    "answer_structured": {"type": "option", "value": "C", "correct_answer": "约1068公里", "distance_km": 1068},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "从北京到上海的直线距离约为______公里。",
    "answer": "1068",
    "answer_structured": {"type": "keyword", "value": "1068"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "北京和上海是中国最重要的两座城市，请描述它们之间的大致距离。",
    "answer": "北京和上海之间的直线距离约为1068公里。北京位于华北平原北部，上海位于长江入海口，两座城市一北一南，相距约一千公里。",
    "answer_structured": {"type": "free_text", "distance_km": 1068},
    "difficulty": "medium"
  }
}

```

### 3.8 复合-方向+距离 (composite.direction_distance) Prompt

```
【关系类型】复合推理 - 方向+距离 (composite.direction_distance)
【任务】同时判断实体A相对于实体B的方向和距离。

【输入示例】
实体A: {"name_zh": "武汉市", "centroid": [114.31, 30.59], "type": "city"}
实体B: {"name_zh": "长沙市", "centroid": [112.94, 28.23], "type": "city"}
空间事实: {"direction_8": "东北", "azimuth_deg": 29.7, "distance_km": 296}

【输出示例】
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true, "direction": "东北", "distance_km": 296},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于武汉相对于长沙的地理位置，以下哪项描述最准确？\nA. 位于东南方向约300公里\nB. 位于东北方向约296公里\nC. 位于西北方向约400公里\nD. 位于正东方向约296公里",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "direction": "东北", "distance_km": 296},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "武汉位于长沙的______方向，直线距离约______公里。",
    "answer": "东北，296",
    "answer_structured": {"type": "keyword", "values": ["东北", "296"]},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "请全面描述武汉和长沙之间的空间位置关系，包括方向和大致距离。",
    "answer": "武汉位于长沙的东北方向，两地直线距离约296公里。从坐标来看，武汉(114.31°E, 30.59°N)相比长沙(112.94°E, 28.23°N)，经度略高、纬度明显更高，方位角约29.7°，属于东北方向。两城都是华中地区的重要城市，通过京广高铁连接，车程约1.5小时。",
    "answer_structured": {"type": "free_text", "direction": "东北", "distance_km": 296, "azimuth_deg": 29.7},
    "difficulty": "hard"
  }
}
```

### 3.9 复合-方向+拓扑 (composite.direction_topology) Prompt

```
【关系类型】复合推理 - 方向+拓扑 (composite.direction_topology)
【任务】同时判断实体A相对于实体B的方向以及两者之间的拓扑关系。

【输入示例】
实体A: {"name_zh": "泰山", "centroid": [117.10, 36.26], "type": "peak"}
实体B: {"name_zh": "山东省", "centroid": [117.00, 36.40], "type": "province", "geometry_type": "Polygon"}
空间事实: {"direction_8": "南", "azimuth_deg": 188.5, "within": true}
是否负例: false

【输出示例】
{
  "true_false": {
    "question": "泰山位于山东省境内偏南的位置，这一说法是否正确？",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true, "direction": "南", "within": true},
    "difficulty": "medium"
  },
  "choice": {
    "question": "关于泰山相对于山东省的空间关系，以下哪项描述正确？\nA. 在山东省境外偏西方向\nB. 在山东省境内偏南方向\nC. 在山东省境外偏北方向\nD. 在山东省境内偏东方向",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "direction": "南", "within": true},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "泰山位于山东省境内偏______方向。",
    "answer": "南",
    "answer_structured": {"type": "keyword", "value": "南"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请描述泰山相对于山东省的方向和拓扑关系。",
    "answer": "泰山位于山东省境内偏南方向。从方向看，泰山在山东省的南边;从拓扑看,泰山完全位于山东省境内。",
    "answer_structured": {"type": "free_text", "direction": "南", "within": true},
    "difficulty": "medium"
  }
}

【输入示例 - 负例】
实体A: {"name_zh": "西湖", "centroid": [120.15, 30.25], "type": "lake"}
实体B: {"name_zh": "江苏省", "centroid": [118.76, 32.06], "type": "province", "geometry_type": "Polygon"}
空间事实: {"direction_8": "东南", "azimuth_deg": 143.2, "within": false}
是否负例: true

【负例输出示例】
{
  "true_false": {
    "question": "西湖位于江苏省境内东南方向，这一说法是否正确？",
    "answer": "错误",
    "answer_structured": {"type": "boolean", "value": false, "direction": "东南", "within": false},
    "difficulty": "medium"
  },
  "choice": {
    "question": "关于西湖与江苏省的空间关系，以下哪项正确？\nA. 西湖在江苏省境内偏南方向\nB. 西湖不在江苏省境内，位于江苏省的东南方向\nC. 西湖在江苏省境内偏东方向\nD. 西湖不在江苏省境内，位于江苏省的西北方向",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "direction": "东南", "within": false},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "西湖位于江苏省的______方向，但______（在/不在）江苏省行政区域内。",
    "answer": "东南，不在",
    "answer_structured": {"type": "keyword", "values": ["东南", "不在"]},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "有人说西湖在江苏省境内，请从方向和拓扑两个维度分析这一说法。",
    "answer": "这一说法不正确。从方向上看，西湖（位于浙江杭州）确实在江苏省的东南方向。但从拓扑关系看，西湖不在江苏省境内，而是位于浙江省杭州市。西湖属于浙江省的行政管辖范围，与江苏省没有包含关系。",
    "answer_structured": {"type": "free_text", "direction": "东南", "within": false, "actual_container": "浙江省"},
    "difficulty": "hard"
  }
}
```

### 3.10 复合-距离+拓扑 (composite.distance_topology) Prompt

```
【关系类型】复合推理 - 距离+拓扑 (composite.distance_topology)
【任务】同时判断两实体的距离和拓扑关系。

【输入示例】
实体A: {"name_zh": "西湖", "centroid": [120.15, 30.25], "type": "lake"}
实体B: {"name_zh": "上海市", "centroid": [121.47, 31.23], "type": "province"}
空间事实: {"distance_km": 162, "within": false, "disjoint": true}
是否负例: false

【输出示例】
{
  "true_false": {
    "question": "西湖距离上海约162公里，且西湖不在上海市行政区域内，这一说法正确吗？",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true, "distance_km": 162, "within": false},
    "difficulty": "medium"
  },
  "choice": {
    "question": "关于杭州西湖与上海市的空间关系，以下哪项正确？\nA. 西湖在上海境内，距离约50公里\nB. 西湖不在上海境内，距离约162公里\nC. 西湖在上海境内，距离约162公里\nD. 西湖不在上海境内，距离约500公里",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "distance_km": 162, "within": false},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "西湖距离上海约______公里，且______（在/不在）上海市行政区域内。",
    "answer": "162，不在",
    "answer_structured": {"type": "keyword", "values": ["162", "不在"]},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "请描述西湖与上海市之间的距离和拓扑关系。",
    "answer": "西湖距离上海市直线距离约162公里。从拓扑关系看,西湖不在上海市行政区域内,而是位于浙江省杭州市。虽然西湖距离上海不远,但从行政归属来看,两者并不存在包含关系.",
    "answer_structured": {"type": "free_text", "distance_km": 162, "within": false},
    "difficulty": "medium"
  }
}

【输入示例 - 负例】
实体A: {"name_zh": "太湖", "centroid": [120.22, 31.25], "type": "lake", "geometry_type": "Polygon"}
实体B: {"name_zh": "上海市", "centroid": [121.47, 31.23], "type": "province", "geometry_type": "Polygon"}
空间事实: {"distance_km": 130, "within": false, "disjoint": true}
是否负例: true

【负例输出示例】
{
  "true_false": {
    "question": "太湖距离上海约130公里且位于上海市行政区域内，这一说法正确吗？",
    "answer": "错误",
    "answer_structured": {"type": "boolean", "value": false, "distance_km": 130, "within": false},
    "difficulty": "medium"
  },
  "choice": {
    "question": "关于太湖与上海市的空间关系，以下哪项描述正确？\nA. 太湖在上海境内，距离约50公里\nB. 太湖不在上海境内，距离约130公里\nC. 太湖在上海境内，距离约130公里\nD. 太湖不在上海境内，距离约500公里",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "distance_km": 130, "within": false},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "太湖距离上海约______公里，但太湖______（在/不在）上海市行政区域内。",
    "answer": "130，不在",
    "answer_structured": {"type": "keyword", "values": ["130", "不在"]},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "有人认为太湖属于上海市，请从距离和空间包含两个维度分析这一说法。",
    "answer": "这一说法不完全正确。从距离上看，太湖确实距离上海较近，直线距离约130公里。但从空间包含关系看，太湖主体不在上海市行政区域内。太湖主要位于江苏省苏州市和无锡市境内，南部部分水域属于浙江省湖州市。虽然太湖距离上海不远，但它属于江苏和浙江两省的管辖范围，而非上海市。",
    "answer_structured": {"type": "free_text", "distance_km": 130, "within": false, "actual_container": "江苏省/浙江省"},
    "difficulty": "hard"
  }
}
```

### 3.11 复合-三重 (composite.direction_distance_topology) Prompt

```
【关系类型】复合推理 - 方向+距离+拓扑 (composite.direction_distance_topology)
【任务】同时判断方向、距离和拓扑关系——最复杂的空间推理。

【输入示例】
实体A: {"name_zh": "武汉市", "centroid": [114.31, 30.59], "type": "city"}
实体B: {"name_zh": "湖北省", "centroid": [112.30, 30.97], "type": "province"}
空间事实: {"direction_8": "东", "azimuth_deg": 98.2, "distance_km": 35, "within": true}
是否负例: false

【输出示例】
{
  "true_false": {
    "question": "武汉位于湖北省内偏东方向约35公里处，这一综合描述是否正确？",
    "answer": "正确",
    "answer_structured": {"type": "boolean", "value": true, "direction": "东", "distance_km": 35, "within": true},
    "difficulty": "hard"
  },
  "choice": {
    "question": "综合考虑方向、距离和空间位置关系，以下哪项最准确地描述了武汉市与湖北省的关系？\nA. 武汉在湖北省外西北方向约200公里\nB. 武汉在湖北省内正东方向约35公里\nC. 武汉在湖北省外东南方向约100公里\nD. 武汉在湖北省内西南方向约35公里",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "direction": "东", "distance_km": 35, "within": true},
    "difficulty": "hard"
  },
  "fill_blank": {
    "question": "武汉市位于湖北省______方向约______公里处，且______（在/不在）湖北省行政区域内。",
    "answer": "东，35，在",
    "answer_structured": {"type": "keyword", "values": ["东", "35", "在"]},
    "difficulty": "hard"
  },
  "open_qa": {
    "question": "请从方向、距离和空间包含关系三个维度，全面分析武汉市与湖北省之间的地理关系。",
    "answer": "武汉市位于湖北省行政区域内，从湖北省质心来看，武汉位于正东方向约35公里处。作为湖北省省会，武汉市不仅是湖北省的政治经济中心，在空间位置上也完全在湖北省的管辖范围内。武汉位于湖北省东部，地处长江与汉江交汇处。",
    "answer_structured": {"type": "free_text", "direction": "东", "distance_km": 35, "within": true, "azimuth_deg": 98.2},
    "difficulty": "hard"
  }
}
```

【输入示例 - 负例】
实体A: {"name_zh": "广州市", "centroid": [113.26, 23.13], "type": "city"}
实体B: {"name_zh": "湖北省", "centroid": [112.30, 30.97], "type": "province", "geometry_type": "Polygon"}
空间事实: {"direction_8": "南", "azimuth_deg": 194.6, "distance_km": 837, "within": false}
是否负例: true

【负例输出示例】
{
  "true_false": {
    "question": "广州市位于湖北省境内偏南方向约837公里，这一说法正确吗？",
    "answer": "错误",
    "answer_structured": {"type": "boolean", "value": false, "direction": "南", "distance_km": 837, "within": false, "error": "广州市不在湖北省境内"},
    "difficulty": "hard"
  },
  "choice": {
    "question": "关于广州市与湖北省的空间关系，以下哪项描述最准确？\nA. 广州市在湖北省境内正南方向约837公里\nB. 广州市不在湖北省境内，位于湖北省南方约837公里\nC. 广州市在湖北省境内西南方向约300公里\nD. 广州市不在湖北省境内，位于湖北省北方约837公里",
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "direction": "南", "distance_km": 837, "within": false},
    "difficulty": "hard"
  },
  "fill_blank": {
    "question": "广州市位于湖北省______方向约______公里处，但______（在/不在）湖北省行政区域内。",
    "answer": "南，837，不在",
    "answer_structured": {"type": "keyword", "values": ["南", "837", "不在"]},
    "difficulty": "hard"
  },
  "open_qa": {
    "question": "请从方向、距离和空间归属三个维度分析广州市与湖北省之间的关系。",
    "answer": "从方向上看，广州市位于湖北省的正南方，方位角约194.6°。从距离上看，两地质心直线距离约837公里。从空间归属看，广州市不在湖北省行政区域内，而是广东省的省会。广州和湖北虽然在南北方向上大致对应，但它们分属不同的省份，中间隔着湖南省等地区。",
    "answer_structured": {"type": "free_text", "direction": "南", "distance_km": 837, "within": false, "azimuth_deg": 194.6, "actual_container": "广东省"},
    "difficulty": "hard"
  }
}
```

### 3.12 各关系类型answer_structured字段汇总

| 关系类型 | answer_structured必含字段 |
|---------|------------------------|
| directional | `{direction, azimuth_deg?}` |
| metric | `{distance_km}` |
| topological.contains | `{contains: bool}` |
| topological.within | `{within: bool, container?: str}` |
| topological.touches | `{touches: bool, shared_border_km?: int}` |
| topological.crosses | `{crosses: bool}` |
| topological.disjoint | `{disjoint: bool}` |
| composite.direction_distance | `{direction, distance_km}` |
| composite.direction_topology | `{direction, within/contains/touches/crosses/disjoint}` |
| composite.distance_topology | `{distance_km, within/contains/touches/crosses/disjoint}` |
| composite.direction_distance_topology | `{direction, distance_km, within/contains/touches/crosses/disjoint}` |

### 3.13 关键约束总结

| 约束 | 说明 | 验证方式 |
|------|------|---------|
| 事实一致性 | answer与spatial_facts一致 | 自动比对answer_structured与facts |
| 结构化答案 | answer_structured直接派生 | 格式校验+值校验 |
| 多样性 | 4道题风格各异+每次生成有变化 | 余弦相似度去重检查 |
| 负例正确 | is_negative=true时答案为否定 | 检查answer_structured.value匹配 |

---

## 四、训练数据使用策略

### 4.1 数据划分

划分在**实体对层面(pair_id)**进行，保证同一对的4种题型在同一个split。

**基础划分（基于Phase 1正例）**：

| Split | 正例实体对数 | 题目实例数 |
|-------|-------------|-----------|
| train | 8,000 | 32,000 |
| dev | 1,000 | 4,000 |
| test | 1,000 | 4,000 |

分层采样维度：`target_relation × difficulty`

**负例合并策略**（用户按需选择，见1.6）：
- 负例独立存储，不影响基础划分
- 合并时在train split中按比例替换正例

### 4.2 展平为V5.2兼容格式

训练时将Layer 2实例展平为V5.2期望的扁平格式：

```python
def flatten_to_v52(instance, pair):
    return {
        "id": instance["instance_id"],
        "spatial_relation_type": pair["target_relation"].split(".")[0],
        "topology_subtype": pair["target_relation"].split(".")[1] if "." in pair["target_relation"] else None,
        "question": instance["question"],
        "answer": instance["answer"],
        "answer_structured": instance["answer_structured"],
        "difficulty": instance["difficulty"],
        "entities": [pair["entity_a"], pair["entity_b"]],
        "question_type": instance["question_type"],  # 新增
    }
```

### 4.3 各实验数据选择

| 实验 | 使用题型 | 说明 |
|------|---------|------|
| Exp01 Direct-SFT | 全部4种 | 监督学习答案 |
| Exp02 Standard-KD | 全部4种 | KL蒸馏 |
| Exp03 SRD | 全部4种 | 空间关系加权蒸馏 |
| Exp04 CoT-Distill | open_qa为主 | 推理链蒸馏需开放问答 |
| Exp05 Rev-KL | 全部4种 | 逆向KL |
| Exp06 Self-Distill | 全部4种 | 自蒸馏 |
| Exp07 Attention | 全部4种 | 注意力蒸馏 |
| Exp08 Progressive | 分阶段引入 | 简单→复杂 |
| Exp09 Full | 全部4种 | 完整方法 |

### 4.4 单一题型/复合题型实验

作为额外消融维度：
- **单一题型实验**：只用选择题训练 → 测试选择/判断/填空/问答
- **复合题型实验**：4种题型混合训练 → 测试泛化能力
- 对比分析：模型是否能从一种题型泛化到其他题型

---

## 五、实现Pipeline

```
Step 1a: Phase 1 - 正例实体对生成 (PostGIS)
  ├── 采样实体对（按target_relation，全部正例）
  ├── 计算spatial_facts（仅含target_relation相关字段）
  ├── 输出: pairs_positive.jsonl (10,000条)

Step 1b: Phase 2 - 负例实体对生成 (PostGIS)
  ├── 仅对含拓扑分量的关系生成负例
  ├── 计算spatial_facts（拓扑关系为假）
  ├── 输出: pairs_negative.jsonl (1,237条)

Step 2: 题目实例层生成 (GLM-4.7 API)
  ├── 读取pairs_positive.jsonl + pairs_negative.jsonl
  ├── 逐条调用LLM生成4种题型
  ├── 自动验证answer_structured与facts一致性
  └── 输出: instances_positive.jsonl (40,000条) + instances_negative.jsonl (4,948条)

Step 3: 数据划分与组合
  ├── 按pair_id分层8:1:1划分（基于Phase 1的10,000条）
  ├── 用户选择负例策略（A/B/C）
  ├── 展平为V5.2兼容格式
  └── 输出: train.jsonl / dev.jsonl / test.jsonl

Step 4: 训练与评测
  ├── 选择题型组合
  ├── 运行Exp01-Exp09
  └── 分题型+分坐标模式报告指标
```

### 关键文件

| 文件 | 用途 |
|------|------|
| PostGIS geokd_sr库 | 空间计算 |
| entities_set (853实体) + geoatlas (510行政) | 实体来源 |
| pairs.jsonl | Layer 1输出 |
| instances.jsonl | Layer 2输出 |
| train/dev/test.jsonl | 最终训练数据 |
| V5.2实验代码 (exp/exp01-exp09) | 训练和评测 |

---

## 六、验证方案

1. **事实层验证**: 每条pair的spatial_facts由PostGIS计算，100%确定性
2. **题目层验证**: answer_structured与spatial_facts自动比对
3. **格式验证**: JSON Schema校验
4. **多样性验证**: 题目文本余弦相似度去重检查
5. **分布验证**: 各split的target_relation × difficulty × is_negative分布TVD < 0.05
