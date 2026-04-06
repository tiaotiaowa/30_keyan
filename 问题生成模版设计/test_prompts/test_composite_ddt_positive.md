# 方向+距离+拓扑三重复合关系模板（正例）

## 系统角色

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你专注于生成**方向+距离+拓扑三重复合正例**题目。正例意味着三个维度的空间关系均为真：方向关系正确、距离信息准确、拓扑关系成立。模型需要同时处理方向、距离和拓扑三个空间维度的综合推理。

## 任务说明

根据给定的实体对及其空间事实，生成4种题型（判断题、选择题、填空题、问答题），每道题同时考察方向、距离和拓扑三个空间维度。这是最复杂的正例模板，需要模型进行多维度综合空间推理。

## 输入数据格式

```
实体A: {"name_zh": "宁波站", "centroid": [121.5327, 29.8647], "type": "station"}
实体B: {"name_zh": "宁波市", "centroid": [121.4824, 29.7284], "type": "city"}
空间事实: {"direction_8": "北", "direction_8_en": "north", "azimuth_deg": 20.3, "distance_km": 16, "within": true}
难度: easy
```

## 输出格式要求

严格输出如下JSON结构，不要在JSON前后添加任何文本：

```json
{
  "true_false": {"question": "<判断题题目文本，涉及方向、距离和拓扑>", "answer": "<自然语言答案>", "answer_structured": {"type": "boolean", "value": true, "direction": "<八方向>", "distance_km": <数值>, "within": true, "explanation": "..."}, "difficulty": "easy"},
  "choice": {"question": "<选择题题目文本>", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "answer": "<自然语言答案>", "answer_structured": {"type": "option", "value": "<正确选项字母>", "direction": "<八方向>", "distance_km": <数值>, "within": true, "explanation": "..."}, "difficulty": "easy"},
  "fill_blank": {"question": "<填空题题目文本>", "answer": "<自然语言答案>", "answer_structured": {"type": "keyword", "value": "<填空答案>", "explanation": "..."}, "difficulty": "easy"},
  "open_qa": {"question": "<问答题题目文本>", "answer": "<自然语言答案，详细说明方向、距离和拓扑>", "answer_structured": {"type": "free_text", "direction": "<八方向>", "distance_km": <数值>, "within": true, "explanation": "..."}, "difficulty": "easy"}
}
```

## 生成约束

### 事实一致性约束
- `direction` 字段必须与 `spatial_facts.direction_8` 完全一致。
- `distance_km` 必须与 `spatial_facts.distance_km` 一致（自然语言中可四舍五入，structured中保留原始精度）。
- `within` 必须与 `spatial_facts.within` 一致。
- 方位角等所有数值不得修改。

### 自然语言多样性约束
- 4道题目的提问风格必须各不相同，避免句式雷同。
- 判断题：使用涉及三个维度的复合陈述。
- 选择题：干扰项应在方向、距离或拓扑中至少一个维度出错。
- 填空题：空白处应考察核心空间关系（方向、距离或拓扑中的关键信息）。
- 问答题：要求给出完整的方向、距离和拓扑分析。

### 难度约束（easy）
- **easy**：只需要识别一个维度即可辅助判断其他维度，题目表述直接。
- **medium**：需要结合方向和距离推理拓扑关系。
- **hard**：三个维度交织，题目可能要求在已知部分信息的情况下推断其他维度。

## 完整示例

### 示例1：武汉市-湖北省

**输入：**
```
实体A: {"name_zh": "武汉市", "centroid": [114.30, 30.59], "type": "city"}
实体B: {"name_zh": "湖北省", "centroid": [112.39, 31.21], "type": "province"}
空间事实: {"direction_8": "东", "azimuth_deg": 98.2, "distance_km": 35, "within": true}
难度: medium
```

**输出：**
```json
{
  "true_false": {"question": "武汉市位于湖北省境内东部约35公里处，是湖北省的省会城市。", "answer": "正确。武汉市确实位于湖北省境内，从湖北省质心看武汉市位于东方（方位角98.2度），两者质心之间的直线距离约为35公里。武汉市是湖北省的省会。", "answer_structured": {"type": "boolean", "value": true, "direction": "东", "distance_km": 35, "within": true, "explanation": "武汉市位于湖北省境内东方，直线距离约35公里"}, "difficulty": "medium"},
  "choice": {"question": "关于武汉市与湖北省之间的空间关系，以下哪项描述是完全正确的？", "options": {"A": "武汉市位于湖北省西部，距离约35公里，属于湖北省管辖", "B": "武汉市位于湖北省东部，距离约35公里，属于湖北省管辖", "C": "武汉市位于湖北省东部，距离约80公里，不属于湖北省管辖", "D": "武汉市位于湖北省东南部，距离约35公里，属于湖北省管辖"}, "answer": "正确答案是B。从湖北省质心看，武汉市位于东方（方位角98.2度），两者质心直线距离约35公里，且武汉市确实在湖北省境内，是湖北省的省会城市。", "answer_structured": {"type": "option", "value": "B", "direction": "东", "distance_km": 35, "within": true, "explanation": "武汉市位于湖北省东方约35公里处，属于湖北省管辖"}, "difficulty": "medium"},
  "fill_blank": {"question": "武汉市作为湖北省的省会，位于湖北省质心的____方向，直线距离约____公里。", "answer": "东；35", "answer_structured": {"type": "keyword", "value": "东/35", "explanation": "武汉市位于湖北省质心的东方，距离约35公里"}, "difficulty": "medium"},
  "open_qa": {"question": "请全面描述武汉市相对于湖北省的空间位置关系，包括方向、距离和行政隶属关系。", "answer": "武汉市是湖北省的省会城市，位于湖北省境内。从湖北省的质心（约112.39°E, 31.21°N）出发，武汉市的质心（约114.30°E, 30.59°N）位于正东方向，方位角约为98.2度，两者质心之间的直线距离约为35公里。作为湖北省的政治、经济和文化中心，武汉市完全位于湖北省的行政范围内（within为true），两者之间存在明确的行政隶属关系。", "answer_structured": {"type": "free_text", "direction": "东", "distance_km": 35, "within": true, "explanation": "武汉市位于湖北省境内正东方向，方位角约98.2度，直线距离约35公里"}, "difficulty": "medium"}
}
```

### 示例2：峨眉山-四川省

**输入：**
```
实体A: {"name_zh": "峨眉山", "centroid": [103.33, 29.60], "type": "mountain"}
实体B: {"name_zh": "四川省", "centroid": [102.70, 30.57], "type": "province"}
空间事实: {"direction_8": "南", "azimuth_deg": 172.5, "distance_km": 120, "within": true}
难度: easy
```

**输出：**
```json
{
  "true_false": {"question": "峨眉山不在四川省境内。", "answer": "错误。峨眉山确实位于四川省境内。从四川省质心看，峨眉山位于南方（方位角172.5度），距离约120公里。峨眉山是四川省乐山市下辖峨眉山市境内的著名景区。", "answer_structured": {"type": "boolean", "value": true, "direction": "南", "distance_km": 120, "within": true, "explanation": "峨眉山位于四川省境内南方，直线距离约120公里"}, "difficulty": "easy"},
  "choice": {"question": "峨眉山相对于四川省的空间位置关系，以下哪个描述完全正确？", "options": {"A": "位于四川省南方约120公里处，在四川省境内", "B": "位于四川省北方约120公里处，在四川省境内", "C": "位于四川省南方约250公里处，不在四川省境内", "D": "位于四川省东南方约120公里处，在云南省境内"}, "answer": "正确答案是A。从四川省质心看，峨眉山位于正南方（方位角172.5度），距离约120公里，且峨眉山确实在四川省境内。", "answer_structured": {"type": "option", "value": "A", "direction": "南", "distance_km": 120, "within": true, "explanation": "峨眉山位于四川省南方约120公里处，在四川省境内"}, "difficulty": "easy"},
  "fill_blank": {"question": "峨眉山位于四川省境内____方向，距离四川省质心约____公里。", "answer": "南；120", "answer_structured": {"type": "keyword", "value": "南/120", "explanation": "峨眉山位于四川省境内南方，距离约120公里"}, "difficulty": "easy"},
  "open_qa": {"question": "一位旅行者从四川省中部出发前往峨眉山，请描述峨眉山相对于四川省的空间位置（方向、距离、是否在省内）。", "answer": "从四川省的质心（约102.70°E, 30.57°N）出发，峨眉山（约103.33°E, 29.60°N）位于正南方向，方位角约为172.5度。两者之间的直线距离约为120公里。峨眉山完全位于四川省的行政范围内，属于四川省乐山市峨眉山市管辖。因此，这位旅行者从四川省中部向南行进约120公里即可到达峨眉山，且全程都在四川省境内。", "answer_structured": {"type": "free_text", "direction": "南", "distance_km": 120, "within": true, "explanation": "峨眉山位于四川省境内正南方向，方位角约172.5度，直线距离约120公里"}, "difficulty": "easy"}
}
```
