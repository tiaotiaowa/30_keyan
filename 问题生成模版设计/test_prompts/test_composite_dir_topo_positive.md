# 方向+拓扑复合关系模板（正例）

## 系统角色

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你专注于生成**方向+拓扑复合正例**题目。正例意味着方向关系和拓扑关系均为真，模型需要同时验证两个维度的空间事实。

## 任务说明

根据给定的实体对及其空间事实，生成4种题型（判断题、选择题、填空题、问答题），每道题同时考察方向关系和拓扑关系，且两个维度的答案均为肯定/正确。

## 输入数据格式

```
实体A: {"name_zh": "恒山", "centroid": [113.7269, 39.6637], "type": "peak"}
实体B: {"name_zh": "山西省", "centroid": [112.2955, 37.5723], "type": "province"}
空间事实: {"direction_8": "东北", "direction_8_en": "northeast", "azimuth_deg": 34.4, "within": true}
难度: easy
```

> 拓扑字段可以是 `within`、`contains`、`touches`、`crosses`、`disjoint` 等，此处正例模板以 `within: true` 为典型代表。当拓扑字段为其他类型时，请相应替换题目中的"位于...内"/"包含"等表述。

## 输出格式要求

严格输出如下JSON结构，不要在JSON前后添加任何文本：

```json
{
  "true_false": {"question": "<判断题题目文本>", "answer": "<自然语言答案>", "answer_structured": {"type": "boolean", "value": true, "direction": "<八方向>", "within": true, "explanation": "..."}, "difficulty": "easy"},
  "choice": {"question": "<选择题题目文本>", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "answer": "<自然语言答案，说明正确选项>", "answer_structured": {"type": "option", "value": "<正确选项字母>", "direction": "<八方向>", "within": true, "explanation": "..."}, "difficulty": "easy"},
  "fill_blank": {"question": "<填空题题目文本，用____表示空白>", "answer": "<自然语言答案>", "answer_structured": {"type": "keyword", "value": "<填空答案>", "explanation": "..."}, "difficulty": "easy"},
  "open_qa": {"question": "<问答题题目文本>", "answer": "<自然语言答案，详细说明方向和拓扑关系>", "answer_structured": {"type": "free_text", "direction": "<八方向>", "within": true, "explanation": "..."}, "difficulty": "easy"}
}
```

## 生成约束

### 事实一致性约束
- `direction` 字段必须与 `spatial_facts.direction_8` 完全一致。
- `within`（或其他拓扑字段）必须与 `spatial_facts` 中的值完全一致。
- 所有数值（方位角等）不得修改。

### 自然语言多样性约束
- 4道题目的提问风格必须各不相同，避免句式雷同。
- 判断题：使用陈述式或否定反问式。
- 选择题：4个选项中只有1个完全正确，干扰项应具有迷惑性（如方向偏差一个象限、拓扑关系取反等）。
- 填空题：空白处应考察核心空间关系（方向或拓扑）。
- 问答题：要求给出完整的空间推理描述。

### 难度约束（easy）
- **easy**：仅考察单一拓扑关系或方向关系，题目表述直白。
- **medium**：同时考察方向和拓扑，需要结合两个维度作答。
- **hard**：题目表述隐含推理，需要先理解上下文再判断空间关系。

## 完整示例

### 示例1：泰山-山东省

**输入：**
```
实体A: {"name_zh": "泰山", "centroid": [117.10, 36.26], "type": "mountain"}
实体B: {"name_zh": "山东省", "centroid": [117.98, 36.67], "type": "province"}
空间事实: {"direction_8": "南", "azimuth_deg": 188.5, "within": true}
难度: medium
```

**输出：**
```json
{
  "true_false": {"question": "泰山位于山东省境内，且从山东省的行政中心看，泰山大致在正南方向。", "answer": "正确。泰山确实位于山东省境内，从山东省的质心看向泰山的质心，方位角为188.5度，属于正南方向。", "answer_structured": {"type": "boolean", "value": true, "direction": "南", "within": true, "explanation": "泰山位于山东省境内正南方向"}, "difficulty": "medium"},
  "choice": {"question": "关于泰山与山东省的空间关系，以下哪个描述是正确的？", "options": {"A": "泰山位于山东省境内，方向为西南", "B": "泰山位于山东省境内，方向为南", "C": "泰山不在山东省境内，方向为东南", "D": "泰山位于山东省境内，方向为北"}, "answer": "正确答案是B。泰山位于山东省境内，且从山东省质心看泰山位于正南方向（方位角188.5度）。", "answer_structured": {"type": "option", "value": "B", "direction": "南", "within": true, "explanation": "泰山位于山东省境内，从山东省质心看位于正南方向"}, "difficulty": "medium"},
  "fill_blank": {"question": "从山东省的质心出发，泰山位于____方向，且泰山____山东省的行政范围内。", "answer": "南；位于（或：在...内）", "answer_structured": {"type": "keyword", "value": "南/位于", "explanation": "泰山位于山东省质心的南方，且在山东省行政范围内"}, "difficulty": "medium"},
  "open_qa": {"question": "请描述泰山相对于山东省的空间位置关系，包括方向和是否在行政范围内。", "answer": "泰山位于山东省境内。从山东省的质心（约117.98°E, 36.67°N）出发，泰山的质心（约117.10°E, 36.26°N）位于正南方向，方位角约188.5度。因此，泰山既在山东省的行政范围内，也处于其南部位置。", "answer_structured": {"type": "free_text", "direction": "南", "within": true, "explanation": "泰山位于山东省境内正南方向，方位角约188.5度"}, "difficulty": "medium"}
}
```

### 示例2：玄武湖-南京市

**输入：**
```
实体A: {"name_zh": "玄武湖", "centroid": [118.80, 32.08], "type": "lake"}
实体B: {"name_zh": "南京市", "centroid": [118.77, 32.06], "type": "city"}
空间事实: {"direction_8": "东北", "azimuth_deg": 27.3, "within": true}
难度: easy
```

**输出：**
```json
{
  "true_false": {"question": "玄武湖不在南京市范围内。", "answer": "错误。玄武湖确实位于南京市范围内，从南京市质心看玄武湖位于东北方向。", "answer_structured": {"type": "boolean", "value": true, "direction": "东北", "within": true, "explanation": "玄武湖位于南京市范围内东北方向"}, "difficulty": "easy"},
  "choice": {"question": "玄武湖位于南京市的哪个方向且是否在南京市范围内？", "options": {"A": "西北方向，在南京市范围内", "B": "东北方向，在南京市范围内", "C": "东南方向，不在南京市范围内", "D": "东北方向，不在南京市范围内"}, "answer": "正确答案是B。玄武湖位于南京市的东北方向（方位角27.3度），且确实在南京市范围内。", "answer_structured": {"type": "option", "value": "B", "direction": "东北", "within": true, "explanation": "玄武湖位于南京市范围内东北方向"}, "difficulty": "easy"},
  "fill_blank": {"question": "玄武湖坐落在南京市范围内，从南京市质心看，它位于____方向。", "answer": "东北", "answer_structured": {"type": "keyword", "value": "东北", "explanation": "玄武湖位于南京市的东北方向"}, "difficulty": "easy"},
  "open_qa": {"question": "如果有人在南京市质心处向北偏东方向行走，他是否能到达玄武湖？请说明玄武湖与南京市的空间关系。", "answer": "是的，从南京市质心出发向东北方向行进可以到达玄武湖。玄武湖位于南京市范围内，且从南京市质心看玄武湖位于东北方向，方位角约为27.3度。", "answer_structured": {"type": "free_text", "direction": "东北", "within": true, "explanation": "玄武湖位于南京市范围内东北方向，方位角约27.3度"}, "difficulty": "easy"}
}
```
