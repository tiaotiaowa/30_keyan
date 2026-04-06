# 距离+拓扑复合关系模板（正例）

## 系统角色

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你专注于生成**距离+拓扑复合正例**题目。正例意味着距离信息和拓扑关系均为真且一致。例如，两个实体之间确实相距某个距离，且拓扑关系（如disjoint）也正确。模型需要同时验证距离和拓扑两个维度。

## 任务说明

根据给定的实体对及其空间事实，生成4种题型（判断题、选择题、填空题、问答题），每道题同时考察距离关系和拓扑关系，两个维度的答案均为事实一致。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"distance_km": {{fact_distance_km}}, "within": false, "disjoint": true}
难度: {{difficulty}}
```

> 拓扑字段说明：`within: false` 表示实体A不在实体B内，`disjoint: true` 表示两者不相交。其他可能的拓扑字段包括 `touches`、`crosses`、`intersects` 等，根据实际情况使用。

## 输出格式要求

严格输出如下JSON结构，不要在JSON前后添加任何文本：

```json
{
  "true_false": {"question": "<判断题题目文本>", "answer": "<自然语言答案>", "answer_structured": {"type": "boolean", "value": true, "distance_km": <数值>, "within": false, "disjoint": true, "explanation": "..."}, "difficulty": "{{difficulty}}"},
  "choice": {"question": "<选择题题目文本>", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "answer": "<自然语言答案>", "answer_structured": {"type": "option", "value": "<正确选项字母>", "distance_km": <数值>, "within": false, "disjoint": true, "explanation": "..."}, "difficulty": "{{difficulty}}"},
  "fill_blank": {"question": "<填空题题目文本>", "answer": "<自然语言答案>", "answer_structured": {"type": "keyword", "value": "<填空答案>", "explanation": "..."}, "difficulty": "{{difficulty}}"},
  "open_qa": {"question": "<问答题题目文本>", "answer": "<自然语言答案，详细说明距离和拓扑关系>", "answer_structured": {"type": "free_text", "distance_km": <数值>, "within": false, "disjoint": true, "explanation": "..."}, "difficulty": "{{difficulty}}"}
}
```

## 生成约束

### 事实一致性约束
- `distance_km` 必须与 `spatial_facts.distance_km` 一致（可四舍五入到整数用于自然语言表述，但structured中保留原始精度）。
- `within` 和 `disjoint` 等拓扑字段必须与 `spatial_facts` 中的值完全一致。
- 所有数值不得修改。

### 自然语言多样性约束
- 4道题目的提问风格必须各不相同，避免句式雷同。
- 判断题：使用涉及距离和拓扑的复合陈述。
- 选择题：干扰项应包含距离偏差或拓扑关系反转的错误选项。
- 填空题：空白处应考察距离数值或拓扑关系。
- 问答题：要求给出完整的距离和拓扑分析。

### 难度约束（{{difficulty}}）
- **easy**：明确给出距离范围，拓扑关系清晰。
- **medium**：需要结合距离和拓扑进行判断。
- **hard**：题目表述隐含推理，可能涉及"距离近但不在境内"等容易混淆的概念。

## 完整示例

### 示例1：西湖-上海市

**输入：**
```
实体A: {"name_zh": "西湖", "centroid": [120.15, 30.25], "type": "lake"}
实体B: {"name_zh": "上海市", "centroid": [121.47, 31.23], "type": "city"}
空间事实: {"distance_km": 162, "within": false, "disjoint": true}
难度: medium
```

**输出：**
```json
{
  "true_false": {"question": "西湖与上海市的直线距离约为160公里，且西湖不在上海市行政范围内。", "answer": "正确。西湖与上海市之间的直线距离约为162公里，且西湖不在上海市的行政范围内，两者在空间上不相交（disjoint）。", "answer_structured": {"type": "boolean", "value": true, "distance_km": 162, "within": false, "disjoint": true, "explanation": "西湖与上海直线距离约162公里，且西湖不在上海市境内"}, "difficulty": "medium"},
  "choice": {"question": "关于西湖与上海市之间的空间关系，以下哪项描述是正确的？", "options": {"A": "西湖距离上海市约162公里，且位于上海市境内", "B": "西湖距离上海市约260公里，且不在上海市境内", "C": "西湖距离上海市约162公里，且不在上海市境内", "D": "西湖距离上海市约100公里，且与上海市接壤"}, "answer": "正确答案是C。西湖与上海市的直线距离约为162公里，且西湖不在上海市的行政范围内，两者在空间上不相交。", "answer_structured": {"type": "option", "value": "C", "distance_km": 162, "within": false, "disjoint": true, "explanation": "西湖与上海直线距离约162公里，不在上海市境内"}, "difficulty": "medium"},
  "fill_blank": {"question": "西湖与上海市的直线距离约为____公里，西湖____（填"在"或"不在"）上海市境内。", "answer": "162；不在", "answer_structured": {"type": "keyword", "value": "162/不在", "explanation": "西湖与上海直线距离约162公里，不在上海市境内"}, "difficulty": "medium"},
  "open_qa": {"question": "请分析西湖与上海市之间的空间关系，包括距离和拓扑两个方面。", "answer": "从空间距离来看，西湖（位于浙江省杭州市）与上海市的直线距离约为162公里，属于中近距离范围。从拓扑关系来看，西湖不在上海市的行政范围内，两者在空间上不相交（disjoint）。西湖位于浙江省，与上海市分属不同的省级行政区。虽然地理距离并不算远，但两者之间不存在包含或交叉关系。", "answer_structured": {"type": "free_text", "distance_km": 162, "within": false, "disjoint": true, "explanation": "西湖位于浙江省杭州市，与上海直线距离约162公里，空间上不相交"}, "difficulty": "medium"}
}
```

### 示例2：洱海-昆明市

**输入：**
```
实体A: {"name_zh": "洱海", "centroid": [100.18, 25.73], "type": "lake"}
实体B: {"name_zh": "昆明市", "centroid": [102.71, 25.04], "type": "city"}
空间事实: {"distance_km": 278, "within": false, "disjoint": true}
难度: easy
```

**输出：**
```json
{
  "true_false": {"question": "洱海是昆明市境内的一个湖泊。", "answer": "错误。洱海不在昆明市境内，两者之间的直线距离约为278公里。洱海位于云南省大理白族自治州。", "answer_structured": {"type": "boolean", "value": true, "distance_km": 278, "within": false, "disjoint": true, "explanation": "洱海与昆明直线距离约278公里，不在昆明市境内"}, "difficulty": "easy"},
  "choice": {"question": "洱海与昆明市的直线距离大约是多少？洱海是否在昆明市内？", "options": {"A": "约150公里，在昆明市内", "B": "约278公里，不在昆明市内", "C": "约400公里，不在昆明市内", "D": "约278公里，在昆明市内"}, "answer": "正确答案是B。洱海与昆明市的直线距离约为278公里，且洱海不在昆明市行政范围内。", "answer_structured": {"type": "option", "value": "B", "distance_km": 278, "within": false, "disjoint": true, "explanation": "洱海与昆明直线距离约278公里，不在昆明市境内"}, "difficulty": "easy"},
  "fill_blank": {"question": "洱海距离昆明市约____公里，它位于大理白族自治州，而不在昆明市范围内。", "answer": "278", "answer_structured": {"type": "keyword", "value": "278", "explanation": "洱海与昆明直线距离约278公里"}, "difficulty": "easy"},
  "open_qa": {"question": "一个游客从昆明出发想去洱海旅游，请说明洱海与昆明之间的距离关系和行政归属。", "answer": "洱海与昆明市之间的直线距离约为278公里，属于同省内的中远距离。洱海不在昆明市的行政范围内，两者在空间上不相交。洱海位于云南省大理白族自治州境内，是该州最著名的自然景观之一。从昆明出发前往洱海需要经过约278公里的路程。", "answer_structured": {"type": "free_text", "distance_km": 278, "within": false, "disjoint": true, "explanation": "洱海位于大理白族自治州，与昆明直线距离约278公里，不在昆明市境内"}, "difficulty": "easy"}
}
```
