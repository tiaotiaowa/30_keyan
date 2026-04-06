# 拓扑包含于关系（正例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑包含于关系（正例）**的题目。正例意味着实体A确实位于实体B内部，空间事实中 `within` 为 `true`。你需要围绕"A在B内部"这一真关系，设计4种不同风格的自然语言题目。

### 概念说明
- `within` 与 `contains` 互为反向关系：ST_Within(A, B) = true 等价于 ST_Contains(B, A) = true。
- 本模板中，A是被包含的较小实体，B是包含A的较大容器实体。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"within": true}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须测试"A是否在B内部"这一空间关系，且正确答案为"是"。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"within": true}
难度: {{difficulty}}
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"type": "boolean", "value": true, "within": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"type": "option", "value": "A", "within": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "keyword", "value": "...", "within": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "free_text", "within": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  }
}
```

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"within": true}`。不得编造任何空间信息。
2. **多样性自然语言**：
   - 判断题：用不同句式提问，如"是否位于...内部"、"是否处于...范围内"、"是否在...之中"等。
   - 选择题：选项设计应包含干扰项，但正确答案唯一。
   - 填空题：挖空部分应考察空间关系知识。
   - 简答题：要求解释或推理，鼓励结合地理常识。
3. **难度适配**：根据 `{{difficulty}}` 调整题目复杂度：
   - easy：直接问包含于关系
   - medium：需要结合地理背景理解
   - hard：需要多步推理或结合多种空间概念
4. **提问风格差异化**：4道题目的提问风格、措辞方式、考察角度必须明显不同。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "泰山", "centroid": [117.10, 36.26], "type": "mountain"}
实体B: {"name_zh": "山东省", "centroid": [117.00, 36.67], "type": "province"}
空间事实: {"within": true}
难度: easy
```

**输出：**
```json
{
  "true_false": {
    "question": "泰山作为五岳之首，其地理位置是否处于山东省的行政区域内？",
    "answer": "正确。泰山的空间位置位于山东省的行政区域范围内，ST_Within(泰山, 山东省) = true。",
    "answer_structured": {"type": "boolean", "value": true, "within": true, "explanation": "泰山的Point几何位于山东省的Polygon几何内部"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于泰山的空间位置，以下哪种描述是准确的？",
    "options": {"A": "泰山位于河南省境内", "B": "泰山位于山东省境内", "C": "泰山位于河北省境内", "D": "泰山位于山西省境内"},
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "within": true, "explanation": "泰山Point在山东省Polygon内部"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "五岳之首的泰山，在空间位置上完全位于______省的行政区域范围之内。",
    "answer": "山东",
    "answer_structured": {"type": "keyword", "value": "山东", "within": true, "explanation": "泰山的空间位置在山东省内部"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请解释为什么在GIS空间分析中，ST_Within(泰山, 山东省)的查询结果为true。",
    "answer": "在GIS中，ST_Within(A, B)判断A是否完全在B的内部。泰山以Point几何表示，山东省以Polygon几何表示。由于泰山的地理坐标(117.10, 36.26)落在山东省Polygon的内部（而非边界上或外部），因此ST_Within返回true。这从空间拓扑上确认了泰山确实位于山东省境内。",
    "answer_structured": {"type": "free_text", "within": true, "explanation": "泰山Point在山东省Polygon内部，within关系成立"},
    "difficulty": "easy"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "洱海", "centroid": [100.19, 25.82], "type": "lake"}
实体B: {"name_zh": "云南省", "centroid": [101.49, 25.04], "type": "province"}
空间事实: {"within": true}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "从空间拓扑角度分析，洱海的整个湖面区域是否完全在云南省的管辖范围内？",
    "answer": "正确。洱海的Polygon几何范围完全位于云南省的Polygon几何范围内部，即洱海全湖都在云南省境内。",
    "answer_structured": {"type": "boolean", "value": true, "within": true, "explanation": "洱海Polygon完全在云南省Polygon内部"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "洱海是中国著名的高原湖泊，关于它与云南省的空间关系，以下描述哪个正确？",
    "options": {"A": "洱海跨越了云南和四川两省", "B": "洱海与云南省仅有部分交集", "C": "洱海完全位于云南省境内", "D": "洱海位于云南省的边界上"},
    "answer": "C",
    "answer_structured": {"type": "option", "value": "C", "within": true, "explanation": "洱海完全在云南省内部"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "大理著名的高原湖泊洱海，在空间拓扑上被完全包含在______省的行政区域之中。",
    "answer": "云南",
    "answer_structured": {"type": "keyword", "value": "云南", "within": true, "explanation": "洱海在云南省行政区域内部"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "请比较ST_Within和ST_Contains在描述洱海与云南省关系时的异同。",
    "answer": "对于洱海与云南省的关系：ST_Within(洱海, 云南省) = true，表示洱海完全在云南省内部；同时ST_Contains(云南省, 洱海) = true，表示云南省完全包含洱海。这两个函数描述的是同一空间关系的两个方向。ST_Within关注的是"被包含者"的视角（洱海在哪里），ST_Contains关注的是"容器"的视角（云南省包含什么）。在本例中两者等价，互为反向表达。",
    "answer_structured": {"type": "free_text", "within": true, "explanation": "Within和Contains互为反向关系，洱海within云南 等价于 云南contains洱海"},
    "difficulty": "medium"
  }
}
```
