# 距离+拓扑复合关系模板（负例）

## 系统角色

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你专注于生成**距离+拓扑复合负例**题目。负例的核心特征是：距离信息为真（两个实体之间确实相距某个距离），但拓扑关系为假（如实体A不在实体B境内）。这种题目测试模型能否区分"距离近"和"拓扑包含"两个不同的空间概念——即两个实体可能距离很近，但并不存在包含关系。

## 任务说明

根据给定的实体对及其空间事实，生成4种题型（判断题、选择题、填空题、问答题）。题目需同时涉及距离和拓扑两个维度，但拓扑关系为假。答案中需指明实体A实际所属的地理单元（actual_container）。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"distance_km": {{fact_distance_km}}, "within": false}
难度: {{difficulty}}
```

> `actual_container` 不由输入数据提供。**请在答案中根据你的地理知识推断entity_a实际属于哪个地理单元**，将推断结果填入 `actual_container` 字段。

## 输出格式要求

严格输出如下JSON结构，不要在JSON前后添加任何文本：

```json
{
  "true_false": {
    "question": "<判断题题目文本，可能利用距离近暗示拓扑包含>",
    "answer": "正确/错误",
    "answer_structured": {"distance_km": <数值>, "within": false, "actual_container": "..."},
    "difficulty": "..."
  },
  "choice": {
    "question": "<选择题题目文本>",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"distance_km": <数值>, "within": false, "actual_container": "..."},
    "difficulty": "..."
  },
  "fill_blank": {
    "question": "<填空题题目文本>",
    "answer": "...",
    "answer_structured": {"fill_answer": "<填空答案>"},
    "difficulty": "..."
  },
  "open_qa": {
    "question": "<问答题题目文本，要求综合判断距离和拓扑>",
    "answer": "<自然语言答案，详细说明距离正确但拓扑为假>",
    "answer_structured": {"distance_km": <数值>, "within": false, "actual_container": "..."},
    "difficulty": "..."
  }
}
```

> **注意**：`actual_container` 字段不由输入数据提供，需由LLM根据地理知识推断entity_a实际所属的地理单元，将推断结果填入该字段。

## 生成约束

### 负例特殊约束
- 距离信息为真，必须在答案中确认距离正确。
- 拓扑关系为假，必须在答案中明确否定并给出 `actual_container`（由LLM根据地理知识推断）。
- 题目设计应包含"陷阱"——"距离近"可能让模型误以为存在拓扑包含关系。
- 选择题的干扰项应包含"距离正确且拓扑包含也正确"的错误选项。
- 关键区分点："距离近"不等于"在境内"。

### 事实一致性约束
- `distance_km` 必须与 `spatial_facts.distance_km` 一致。
- `within` 必须为 false。
- `actual_container` 由LLM根据地理知识推断，必须准确。
- 所有数值不得修改。

### 自然语言多样性约束
- 4道题目的提问风格必须各不相同，避免句式雷同。
- 判断题：可使用"距离很近所以一定在境内"等带有逻辑陷阱的陈述。
- 选择题：正确选项应同时包含正确的距离和正确的拓扑判断。
- 填空题：空白处可考察实际所属区域或拓扑关系判断。
- 问答题：要求给出完整的距离和拓扑分析，强调两者是独立的空间概念。

### 难度约束（{{difficulty}}）
- **easy**：题目明确区分距离和拓扑，容易识别。
- **medium**：需要结合距离信息判断拓扑关系，有一定迷惑性。
- **hard**：距离较近可能产生强烈的拓扑包含错觉，需要仔细分析。

## 完整示例

### 示例1：太湖-上海市

**输入：**
```
实体A: {"name_zh": "太湖", "centroid": [119.95, 31.20], "type": "lake"}
实体B: {"name_zh": "上海市", "centroid": [121.47, 31.23], "type": "city"}
空间事实: {"distance_km": 130, "within": false}
难度: hard
```

**输出：**
```json
{
  "true_false": {
    "question": "太湖距离上海市仅约130公里，作为长三角地区的重要水体，太湖应当属于上海市管辖范围。",
    "answer": "错误",
    "answer_structured": {"distance_km": 130, "within": false, "actual_container": "江苏省/浙江省"},
    "difficulty": "hard"
  },
  "choice": {
    "question": "太湖与上海市之间的空间关系，以下哪项描述最准确？",
    "options": {
      "A": "太湖距离上海市约130公里，且太湖位于上海市境内",
      "B": "太湖距离上海市约130公里，太湖主要位于江苏省和浙江省境内",
      "C": "太湖距离上海市约200公里，且太湖位于浙江省境内",
      "D": "太湖距离上海市约130公里，太湖位于安徽省境内"
    },
    "answer": "B",
    "answer_structured": {"distance_km": 130, "within": false, "actual_container": "江苏省/浙江省"},
    "difficulty": "hard"
  },
  "fill_blank": {
    "question": "太湖距离上海市约____公里，但它并不属于上海市，而是主要位于____和浙江省境内。",
    "answer": "130；江苏",
    "answer_structured": {"fill_answer": "130/江苏"},
    "difficulty": "hard"
  },
  "open_qa": {
    "question": "有人认为"太湖紧邻上海，所以太湖是上海的重要水源地，太湖应该在上海市管辖范围内"。请从空间距离和行政归属两个角度分析这一观点。",
    "answer": "这一观点在距离方面部分正确，但在行政归属方面完全错误。从空间距离来看，太湖与上海市的直线距离约为130公里，确实相对较近，这也是太湖流域与上海经济联系紧密的地理基础。然而，距离近并不等于行政包含。太湖实际上主要位于江苏省境内（涉及苏州、无锡、常州等市），部分水域属于浙江省，并不在上海市的行政管辖范围内。空间距离和行政归属是两个独立的概念，不能因为两个地理实体距离近就推断存在包含关系。",
    "answer_structured": {"distance_km": 130, "within": false, "actual_container": "江苏省/浙江省"},
    "difficulty": "hard"
  }
}
```

### 示例2：张家界-长沙市

**输入：**
```
实体A: {"name_zh": "张家界", "centroid": [110.48, 29.12], "type": "city"}
实体B: {"name_zh": "长沙市", "centroid": [112.97, 28.23], "type": "city"}
空间事实: {"distance_km": 265, "within": false}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "张家界距离长沙市约265公里，属于长沙市管辖的远郊区县。",
    "answer": "错误",
    "answer_structured": {"distance_km": 265, "within": false, "actual_container": "湖南省（张家界市）"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "关于张家界与长沙市之间的空间关系，哪个说法是正确的？",
    "options": {
      "A": "张家界距离长沙市约265公里，且是长沙市下辖的一个区",
      "B": "张家界距离长沙市约150公里，且是独立的地级市",
      "C": "张家界距离长沙市约265公里，是与长沙市同级的地级市",
      "D": "张家界距离长沙市约350公里，属于岳阳市管辖"
    },
    "answer": "C",
    "answer_structured": {"distance_km": 265, "within": false, "actual_container": "湖南省（张家界市）"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "张家界距离长沙市约____公里，它不是长沙市的下辖区县，而是湖南省下辖的独立____市。",
    "answer": "265；地级",
    "answer_structured": {"fill_answer": "265/地级"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "请从空间距离和行政隶属关系两个角度，分析张家界与长沙市之间的关系。",
    "answer": "从空间距离来看，张家界与长沙市之间的直线距离约为265公里，属于湖南省内的中远距离。从行政隶属关系来看，张家界并不属于长沙市管辖，而是湖南省下辖的独立地级市。两者在行政级别上是平级的，同属于湖南省。虽然张家界因旅游业闻名，且与长沙市同属湖南省，但两者之间不存在行政包含关系，是两个独立的地级行政单位。",
    "answer_structured": {"distance_km": 265, "within": false, "actual_container": "湖南省（张家界市）"},
    "difficulty": "medium"
  }
}
```
