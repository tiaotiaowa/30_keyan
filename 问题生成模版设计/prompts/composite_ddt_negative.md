# 方向+距离+拓扑三重复合关系模板（负例）

## 系统角色

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你专注于生成**方向+距离+拓扑三重复合负例**题目。这是最复杂的负例模板，核心特征是：方向和距离信息均为真（实体A确实在实体B的某个方向、相距某个距离），但拓扑关系为假（实体A不在实体B境内）。这种题目测试模型能否在两个空间维度都正确的情况下，不被误导而错误判断拓扑关系，实现真正的多维度空间推理。

## 任务说明

根据给定的实体对及其空间事实，生成4种题型（判断题、选择题、填空题、问答题）。题目同时涉及方向、距离和拓扑三个维度，方向和距离为真但拓扑为假。答案中需指明实体A实际所属的地理单元（actual_container）。这是最高难度的空间推理测试。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"direction_8": "{{fact_direction_8}}", "azimuth_deg": {{fact_azimuth_deg}}, "distance_km": {{fact_distance_km}}, "within": false}
难度: {{difficulty}}
```

> `actual_container` 不由输入数据提供。**请在答案中根据你的地理知识推断entity_a实际属于哪个地理单元**，将推断结果填入 `actual_container` 字段。

## 输出格式要求

严格输出如下JSON结构，不要在JSON前后添加任何文本：

```json
{
  "true_false": {
    "question": "<判断题题目文本，利用方向和距离正确信息暗示错误拓扑>",
    "answer": "正确/错误",
    "answer_structured": {"direction": "<八方向>", "distance_km": <数值>, "within": false, "actual_container": "..."},
    "difficulty": "..."
  },
  "choice": {
    "question": "<选择题题目文本>",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"direction": "<八方向>", "distance_km": <数值>, "within": false, "actual_container": "..."},
    "difficulty": "..."
  },
  "fill_blank": {
    "question": "<填空题题目文本>",
    "answer": "...",
    "answer_structured": {"fill_answer": "<填空答案>"},
    "difficulty": "..."
  },
  "open_qa": {
    "question": "<问答题题目文本，要求三维度综合推理>",
    "answer": "<自然语言答案，详细分析三个维度>",
    "answer_structured": {"direction": "<八方向>", "distance_km": <数值>, "within": false, "actual_container": "..."},
    "difficulty": "..."
  }
}
```

> **注意**：`actual_container` 字段不由输入数据提供，需由LLM根据地理知识推断entity_a实际所属的地理单元，将推断结果填入该字段。

## 生成约束

### 负例特殊约束
- 方向信息为真，必须在答案中确认方向正确。
- 距离信息为真，必须在答案中确认距离正确。
- 拓扑关系为假，必须在答案中明确否定并给出 `actual_container`（由LLM根据地理知识推断）。
- 题目设计应包含强烈的"陷阱"——方向和距离都正确可能让模型误以为拓扑也对。
- 选择题的干扰项应包含"方向正确、距离正确、拓扑也正确"的错误选项。
- 这是最复杂的负例，需要模型在三个维度中准确区分事实和陷阱。
- 题目应体现多维度推理能力：不能仅凭一个维度正确就假定其他维度也正确。

### 事实一致性约束
- `direction` 字段必须与 `spatial_facts.direction_8` 完全一致。
- `distance_km` 必须与 `spatial_facts.distance_km` 一致。
- `within` 必须为 false。
- `actual_container` 由LLM根据地理知识推断，必须准确。
- 方位角等所有数值不得修改。

### 自然语言多样性约束
- 4道题目的提问风格必须各不相同，避免句式雷同。
- 判断题：使用三个维度信息混合的陈述，其中部分正确部分错误。
- 选择题：正确选项应同时准确反映三个维度的空间事实。
- 填空题：空白处可考察关键的区别性信息（如actual_container）。
- 问答题：要求给出完整的三维度分析，明确指出哪些维度为真哪些为假。

### 难度约束（{{difficulty}}）
- **easy**：题目虽涉及三个维度，但陷阱较为明显。
- **medium**：需要综合三个维度分析，方向和距离的正确性增加了迷惑性。
- **hard**：三个维度紧密交织，陷阱设计精巧，需要深度推理才能发现拓扑为假。

## 完整示例

### 示例1：广州市-湖北省

**输入：**
```
实体A: {"name_zh": "广州市", "centroid": [113.26, 23.13], "type": "city"}
实体B: {"name_zh": "湖北省", "centroid": [112.39, 31.21], "type": "province"}
空间事实: {"direction_8": "南", "azimuth_deg": 194.6, "distance_km": 837, "within": false}
难度: hard
```

**输出：**
```json
{
  "true_false": {
    "question": "广州市位于湖北省正南方约837公里处，作为华中地区的重要城市，广州市应当归湖北省管辖。",
    "answer": "错误",
    "answer_structured": {"direction": "南", "distance_km": 837, "within": false, "actual_container": "广东省"},
    "difficulty": "hard"
  },
  "choice": {
    "question": "以下关于广州市与湖北省空间关系的描述，哪一项完全正确？",
    "options": {
      "A": "广州市位于湖北省南方约837公里，且广州市隶属于湖北省",
      "B": "广州市位于湖北省南方约837公里，但广州市实际隶属于广东省",
      "C": "广州市位于湖北省西南方约500公里，隶属于广东省",
      "D": "广州市位于湖北省南方约837公里，且与湖北省接壤"
    },
    "answer": "B",
    "answer_structured": {"direction": "南", "distance_km": 837, "within": false, "actual_container": "广东省"},
    "difficulty": "hard"
  },
  "fill_blank": {
    "question": "广州市位于湖北省____方向约837公里处，但它并不属于湖北省，而是____省的省会。",
    "answer": "南；广东",
    "answer_structured": {"fill_answer": "南/广东"},
    "difficulty": "hard"
  },
  "open_qa": {
    "question": "一篇地理文章写道："广州市位于湖北省以南约837公里，因此广州市是湖北省最南端的城市。"请从方向、距离和行政隶属三个角度全面分析这句话的正确性。",
    "answer": "这句话在方向和距离维度上是正确的，但在行政隶属维度上是完全错误的。具体分析如下：\n\n1. 方向维度：从湖北省的质心（约112.39°E, 31.21°N）出发，广州市的质心（约113.26°E, 23.13°N）确实位于正南方，方位角约为194.6度。\n\n2. 距离维度：两者质心之间的直线距离确实约为837公里。\n\n3. 拓扑/行政隶属维度：广州市并不在湖北省的行政范围内。广州市是广东省的省会，是一个完全独立的省级行政单位的中心城市，与湖北省不存在任何行政隶属关系。\n\n因此，虽然广州市确实在湖北省的正南方约837公里处，但不能由此推断广州市属于湖北省。方向近、距离明确，不代表存在行政包含关系。这是空间推理中常见的"距离-拓扑混淆"错误。",
    "answer_structured": {"direction": "南", "distance_km": 837, "within": false, "actual_container": "广东省"},
    "difficulty": "hard"
  }
}
```

### 示例2：桂林市-湖南省

**输入：**
```
实体A: {"name_zh": "桂林市", "centroid": [110.29, 25.27], "type": "city"}
实体B: {"name_zh": "湖南省", "centroid": [111.72, 27.63], "type": "province"}
空间事实: {"direction_8": "南", "azimuth_deg": 198.3, "distance_km": 285, "within": false}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "桂林市位于湖南省南部约285公里处，是湖南省著名的旅游城市。",
    "answer": "错误",
    "answer_structured": {"direction": "南", "distance_km": 285, "within": false, "actual_container": "广西壮族自治区"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "关于桂林市与湖南省之间的空间关系，以下哪一项描述完全正确？",
    "options": {
      "A": "桂林市位于湖南省南方约285公里，属于湖南省管辖",
      "B": "桂林市位于湖南省西南方约400公里，属于广西壮族自治区",
      "C": "桂林市位于湖南省南方约285公里，实际属于广西壮族自治区",
      "D": "桂林市位于湖南省东南方约285公里，属于广东省管辖"
    },
    "answer": "C",
    "answer_structured": {"direction": "南", "distance_km": 285, "within": false, "actual_container": "广西壮族自治区"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "桂林市在湖南省____方向约285公里处，但它实际上不在湖南省，而是____壮族自治区的著名旅游城市。",
    "answer": "南；广西",
    "answer_structured": {"fill_answer": "南/广西"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "桂林以"桂林山水甲天下"闻名，有人说"桂林在湖南南边不到300公里，所以桂林是湖南的"。请从方向、距离和行政区划三个维度分析这种说法。",
    "answer": "这种说法在方向和距离上基本正确，但在行政区划归属上完全错误。具体分析：\n\n1. 方向维度：从湖南省质心（约111.72°E, 27.63°N）出发，桂林市（约110.29°E, 25.27°N）确实位于南方，方位角约为198.3度。\n\n2. 距离维度：两者质心之间的直线距离约为285公里，"不到300公里"的说法基本准确。\n\n3. 行政区划维度：桂林市并不隶属于湖南省。桂林市是广西壮族自治区下辖的地级市，与湖南省是不同的省级行政区。\n\n虽然桂林距离湖南较近且位于其南方，但空间距离近并不意味着存在行政隶属关系。桂林与湖南之间有明确的省界，分属不同的省级政区。这种"因为近所以属于"的推理在地理空间判断中是常见的逻辑错误。",
    "answer_structured": {"direction": "南", "distance_km": 285, "within": false, "actual_container": "广西壮族自治区"},
    "difficulty": "medium"
  }
}
```
