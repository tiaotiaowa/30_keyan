# 方向+拓扑复合关系模板（负例）

## 系统角色

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你专注于生成**方向+拓扑复合负例**题目。负例的核心特征是：方向关系为真（实体A确实在实体B的某个方向），但拓扑关系为假（实体A不在实体B境内）。这种题目测试模型能否在方向信息正确的情况下，准确识别拓扑关系的真伪，避免"方向近就认为在里面"的认知偏差。

## 任务说明

根据给定的实体对及其空间事实，生成4种题型（判断题、选择题、填空题、问答题）。题目需同时涉及方向和拓扑两个维度，但拓扑关系为假。答案中需指明实体A实际所属的地理单元（actual_container）。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"direction_8": "{{fact_direction_8}}", "azimuth_deg": {{fact_azimuth_deg}}, "within": false}
难度: {{difficulty}}
```

> `actual_container` 不由输入数据提供。**请在答案中根据你的地理知识推断entity_a实际属于哪个地理单元**，将推断结果填入 `actual_container` 字段。

## 输出格式要求

严格输出如下JSON结构，不要在JSON前后添加任何文本：

```json
{
  "true_false": {
    "question": "<判断题题目文本，可能暗示错误拓扑>",
    "answer": "正确/错误",
    "answer_structured": {"direction": "<八方向>", "within": false, "actual_container": "..."},
    "difficulty": "..."
  },
  "choice": {
    "question": "<选择题题目文本>",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"direction": "<八方向>", "within": false, "actual_container": "..."},
    "difficulty": "..."
  },
  "fill_blank": {
    "question": "<填空题题目文本>",
    "answer": "...",
    "answer_structured": {"fill_answer": "<填空答案>"},
    "difficulty": "..."
  },
  "open_qa": {
    "question": "<问答题题目文本，要求综合判断>",
    "answer": "<自然语言答案，详细说明方向正确但拓扑为假>",
    "answer_structured": {"direction": "<八方向>", "within": false, "actual_container": "..."},
    "difficulty": "..."
  }
}
```

> **注意**：`actual_container` 字段不由输入数据提供，需由LLM根据地理知识推断entity_a实际所属的地理单元，将推断结果填入该字段。

## 生成约束

### 负例特殊约束
- 方向事实为真，必须在答案中确认方向正确。
- 拓扑关系为假，必须在答案中明确否定并给出 `actual_container`（由LLM根据地理知识推断）。
- 题目设计应包含"陷阱"——方向正确可能让模型误以为拓扑也对。
- 选择题的干扰项应包含"方向正确且拓扑也正确"的错误选项。

### 事实一致性约束
- `direction` 字段必须与 `spatial_facts.direction_8` 完全一致。
- `within` 必须为 false。
- `actual_container` 由LLM根据地理知识推断，必须准确。
- 所有数值不得修改。

### 自然语言多样性约束
- 4道题目的提问风格必须各不相同，避免句式雷同。
- 判断题：可使用看似合理但拓扑错误的陈述，测试模型辨别能力。
- 选择题：正确选项应同时包含正确的方向和正确的拓扑判断。
- 填空题：空白处可考察实际所属区域（actual_container）或拓扑关系。
- 问答题：要求给出完整的空间推理，包括方向和拓扑的分析。

### 难度约束（{{difficulty}}）
- **easy**：题目明确提问拓扑关系，只需判断是否在境内。
- **medium**：需要同时验证方向和拓扑，题目可能暗示错误拓扑。
- **hard**：题目设计为高迷惑性，需要多步推理才能发现拓扑为假。

## 完整示例

### 示例1：西湖-江苏省

**输入：**
```
实体A: {"name_zh": "西湖", "centroid": [120.15, 30.25], "type": "lake"}
实体B: {"name_zh": "江苏省", "centroid": [119.46, 32.97], "type": "province"}
空间事实: {"direction_8": "东南", "azimuth_deg": 143.2, "within": false}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "西湖位于江苏省境内东南方向，因此西湖属于江苏省管辖。",
    "answer": "错误",
    "answer_structured": {"direction": "东南", "within": false, "actual_container": "浙江省"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "关于西湖与江苏省的空间关系，以下哪个说法最准确？",
    "options": {
      "A": "西湖位于江苏省东南方且在江苏省境内",
      "B": "西湖位于江苏省东南方，但实际位于浙江省境内",
      "C": "西湖位于江苏省西南方且在江苏省境内",
      "D": "西湖位于江苏省东南方，实际位于上海市境内"
    },
    "answer": "B",
    "answer_structured": {"direction": "东南", "within": false, "actual_container": "浙江省"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "西湖虽然在江苏省的____方向，但它实际位于____省境内。",
    "answer": "东南；浙江",
    "answer_structured": {"fill_answer": "东南/浙江"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "有人说"西湖在江苏省东南方，所以西湖是江苏的景点"，请分析这一说法的正确性。",
    "answer": "这一说法是错误的。方向关系和拓扑关系是两个不同的空间概念。从江苏省质心（约119.46°E, 32.97°N）看，西湖（约120.15°E, 30.25°N）确实位于东南方向，方位角约143.2度。但是，西湖并不在江苏省的行政范围内，它实际位于浙江省杭州市。方向上的接近并不意味着行政区划上的包含。",
    "answer_structured": {"direction": "东南", "within": false, "actual_container": "浙江省"},
    "difficulty": "medium"
  }
}
```

### 示例2：黄山-浙江省

**输入：**
```
实体A: {"name_zh": "黄山", "centroid": [118.17, 30.13], "type": "mountain"}
实体B: {"name_zh": "浙江省", "centroid": [120.15, 29.28], "type": "province"}
空间事实: {"direction_8": "西北", "azimuth_deg": 305.8, "within": false}
难度: hard
```

**输出：**
```json
{
  "true_false": {
    "question": "黄山风景名胜区位于浙江省西北部山区，是浙江省的著名旅游景点。",
    "answer": "错误",
    "answer_structured": {"direction": "西北", "within": false, "actual_container": "安徽省"},
    "difficulty": "hard"
  },
  "choice": {
    "question": "黄山与浙江省之间的空间关系，下列哪项描述是正确的？",
    "options": {
      "A": "黄山位于浙江省西北方向，属于浙江省管辖",
      "B": "黄山位于浙江省西南方向，属于安徽省管辖",
      "C": "黄山位于浙江省西北方向，实际属于安徽省管辖",
      "D": "黄山位于浙江省正北方向，属于江苏省管辖"
    },
    "answer": "C",
    "answer_structured": {"direction": "西北", "within": false, "actual_container": "安徽省"},
    "difficulty": "hard"
  },
  "fill_blank": {
    "question": "从浙江省出发向____方向可以到达黄山风景区，但黄山实际不在浙江省，而是位于____省。",
    "answer": "西北；安徽",
    "answer_structured": {"fill_answer": "西北/安徽"},
    "difficulty": "hard"
  },
  "open_qa": {
    "question": "一位游客计划从杭州（浙江省省会）前往黄山旅游，请分析黄山相对于浙江省的空间位置关系，并说明黄山属于哪个省份。",
    "answer": "从浙江省的质心（约120.15°E, 29.28°N）出发，黄山（约118.17°E, 30.13°N）位于西北方向，方位角约305.8度。虽然黄山距离浙江省较近，但它并不在浙江省的行政范围内，而是位于安徽省黄山市。因此，这位游客从杭州前往黄山实际上是一次跨省旅行。",
    "answer_structured": {"direction": "西北", "within": false, "actual_container": "安徽省"},
    "difficulty": "hard"
  }
}
```
