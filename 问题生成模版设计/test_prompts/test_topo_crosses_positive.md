# 拓扑穿越关系（正例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑穿越关系（正例）**的题目。正例意味着线状实体A穿越了面状实体B，空间事实中 `crosses` 为 `true`。你需要围绕"A穿越B"这一真关系，设计4种不同风格的自然语言题目。

### 概念说明
- `crosses` 在PostGIS中表示一个几何体穿越另一个几何体。典型场景是LineString穿越Polygon。
- 穿越意味着：线状实体的路径从面状实体的一侧进入，从另一侧穿出，与面状实体的内部有交集但不是完全包含在内。
- 实体A通常是线状（river河流/road道路/railway铁路），实体B通常是面状（province省/city城市/district区）。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"crosses": true}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须测试"A是否穿越B"这一空间关系，且正确答案为"是"。

## 输入数据格式

```
实体A: {"name_zh": "京沪高速", "centroid": [118.275, 35.6078], "type": "road"}
实体B: {"name_zh": "江苏省", "centroid": [119.4939, 32.9646], "type": "province"}
空间事实: {"crosses": true}
难度: easy
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"type": "boolean", "value": true, "crosses": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"type": "option", "value": "A", "crosses": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "keyword", "value": "...", "crosses": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "free_text", "crosses": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  }
}
```

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"crosses": true}`。不得编造任何空间信息。
2. **多样性自然语言**：
   - 判断题：用不同句式提问，如"是否穿越"、"是否流经"、"是否横穿"、"是否途经"等。
   - 选择题：选项设计应包含干扰项，但正确答案唯一。
   - 填空题：挖空部分应考察空间关系知识。
   - 简答题：要求解释或推理，鼓励结合地理常识。
3. **难度适配**：根据 `easy` 调整题目复杂度：
   - easy：直接问穿越关系
   - medium：需要结合地理背景理解
   - hard：需要多步推理或结合多种空间概念
4. **提问风格差异化**：4道题目的提问风格、措辞方式、考察角度必须明显不同。
5. **几何类型关注**：题目中应适当体现A是线状实体、B是面状实体的几何特征。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "长江", "centroid": [112.50, 30.50], "type": "river"}
实体B: {"name_zh": "湖北省", "centroid": [112.29, 30.99], "type": "province"}
空间事实: {"crosses": true}
难度: easy
```

**输出：**
```json
{
  "true_false": {
    "question": "长江是否流经湖北省？",
    "answer": "正确。长江作为线状水体穿越了湖北省的面状行政区域，ST_Crosses(长江, 湖北省) = true。",
    "answer_structured": {"type": "boolean", "value": true, "crosses": true, "explanation": "长江LineString穿越湖北省Polygon，从西侧进入到东侧穿出"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于长江与湖北省的空间关系，以下哪种描述是正确的？",
    "options": {"A": "长江完全绕过湖北省", "B": "长江穿越湖北省", "C": "湖北省完全包含长江的全段", "D": "长江仅与湖北省的边界接触"},
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "crosses": true, "explanation": "长江LineString穿越湖北省Polygon"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "长江自西向东横贯中国中部，其中______段穿越了湖北省的行政区域。",
    "answer": "长江中游",
    "answer_structured": {"type": "keyword", "value": "长江中游", "crosses": true, "explanation": "长江中游段穿越湖北省"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请从空间拓扑角度解释，为什么说长江'穿越'湖北省而不是'包含于'湖北省。",
    "answer": "在空间拓扑中，'穿越'(crosses)和'包含于'(within)是不同的关系。ST_Crosses(长江, 湖北省) = true意味着长江的LineString几何与湖北省的Polygon几何的内部有交集，但长江并未完全落在湖北省内部——它从湖北西部进入，从东部穿出，继续流向其他省份。而如果ST_Within(长江, 湖北省) = true，则意味着长江的全部线段都在湖北省内部，这显然不符合事实，因为长江流经多个省份。因此，'穿越'更准确地描述了长江与湖北的空间关系。",
    "answer_structured": {"type": "free_text", "crosses": true, "explanation": "crosses表示部分穿越而非完全包含，长江穿越湖北但不仅限于湖北"},
    "difficulty": "easy"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "京广铁路", "centroid": [114.00, 32.00], "type": "railway"}
实体B: {"name_zh": "河南省", "centroid": [113.65, 34.76], "type": "province"}
空间事实: {"crosses": true}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "作为中国南北交通大动脉的京广铁路，其线路是否穿越了河南省？",
    "answer": "正确。京广铁路从北向南穿越河南省，途经郑州等重要城市。ST_Crosses(京广铁路, 河南省) = true。",
    "answer_structured": {"type": "boolean", "value": true, "crosses": true, "explanation": "京广铁路LineString从北到南穿越河南省Polygon"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "京广铁路连接北京和广州两大城市，关于它与河南省的空间关系，以下哪个说法准确？",
    "options": {"A": "京广铁路不经过河南省", "B": "京广铁路的线路穿越了河南省", "C": "京广铁路完全在河南省内部", "D": "京广铁路仅与河南省边界相切"},
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "crosses": true, "explanation": "京广铁路南北纵贯河南省"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "京广铁路自北京出发一路南下，途经______省省会郑州，穿越该省后继续向湖北方向延伸。",
    "answer": "河南",
    "answer_structured": {"type": "keyword", "value": "河南", "crosses": true, "explanation": "京广铁路穿越河南省并经过省会郑州"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "京广铁路穿越了包括河南在内的多个省份。请从GIS角度说明，如何判断一条铁路线是否穿越了一个省份，并区分'穿越'和'经过'（边界接触）的不同。",
    "answer": "在GIS中，判断铁路线是否穿越省份使用ST_Crosses函数。ST_Crosses(京广铁路, 河南省) = true表示铁路的LineString与河南省的Polygon内部有交集——即铁路线不只是沿着省界走，而是实际进入了省的内部区域。这与'经过'(ST_Touches)不同：如果ST_Touches为true，说明铁路线仅与省界接触而没有进入省内。京广铁路实际穿过河南省的核心区域（如郑州），所以是crosses而非touches。ST_Crosses强调的是线状实体从面状实体的内部穿过，有明确的进入和穿出过程。",
    "answer_structured": {"type": "free_text", "crosses": true, "explanation": "crosses要求线进入面的内部，与touches（仅边界接触）有本质区别"},
    "difficulty": "medium"
  }
}
```
