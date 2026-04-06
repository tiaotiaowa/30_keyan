# 拓扑相邻关系（负例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑相邻关系（负例）**的题目。负例意味着实体A和实体B**不**相邻接壤，空间事实中 `touches` 为 `false`。你需要围绕"A和B不相邻"这一事实设计题目，重点测试学习者识别错误空间陈述的能力。

### 负例专项约束
- 将假关系包装为**看似合理的陈述**，使题目具有迷惑性。
- 正确答案应明确指出相邻关系为假。
- **不要**制造明显荒谬的错误（例如"北京和纽约相邻"这种明显不合理的配对）。
- 优先选择在地图上看起来可能相邻、但实际上不相邻的实体对，增加迷惑性。
- `answer_structured` 中可增加 `actual_relation` 字段，描述A和B之间的实际空间关系（如分离、包含等）。**请在答案中根据你的地理知识推断A和B的实际空间关系**，将推断结果填入 `actual_relation` 字段。输入数据中不提供此字段。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"touches": false}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须围绕"A和B不相邻"这一空间关系事实展开。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"touches": false}
难度: {{difficulty}}
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"touches": false, "actual_relation": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"touches": false, "actual_relation": "...", "correct_option": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"touches": false, "actual_relation": "...", "fill_answer": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"touches": false, "actual_relation": "...", "explanation": "..."},
    "difficulty": "..."
  }
}
```

> **注意**：`actual_relation` 字段不由输入数据提供，需由LLM根据地理知识推断A和B之间的实际空间关系，将推断结果填入该字段。

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"touches": false}`。不得编造任何空间信息。`actual_relation` 由LLM根据地理知识推断。
2. **迷惑性设计**：
   - 题目中的假陈述应该看起来合理，利用地理区域邻近或行政层级相似性制造迷惑。
   - 例如：武汉市和南京市都是长江沿岸的省会城市，但它们并不直接相邻。
3. **多样性自然语言**：4道题目的提问风格、措辞方式、考察角度必须明显不同。
4. **难度适配**：根据 `{{difficulty}}` 调整迷惑程度：
   - easy：假关系有一定迷惑性但可通过常识判断。
   - medium：需要较深入的地理知识才能识别。
   - hard：需要精确的空间推理或多重线索综合判断。
5. **answer_structured包含actual_relation字段**：描述A和B实际的拓扑关系（由LLM根据地理知识推断）。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "武汉市", "centroid": [114.30, 30.59], "type": "city"}
实体B: {"name_zh": "南京市", "centroid": [118.78, 32.06], "type": "city"}
空间事实: {"touches": false}
难度: easy
```

**输出：**
```json
{
  "true_false": {
    "question": "有人认为"武汉和南京都是长江沿岸的大城市，它们之间一定相邻接壤"。这一判断正确吗？",
    "answer": "错误",
    "answer_structured": {"touches": false, "actual_relation": "disjoint（分离，中间隔有其他城市）", "explanation": "武汉和南京不共享边界，中间有其他城市隔开（LLM推断）"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于武汉市和南京市的空间相邻关系，以下哪项正确？",
    "options": {"A": "武汉市与南京市相邻接壤，共享行政边界", "B": "武汉市与南京市不相邻，中间隔有其他行政区", "C": "南京市完全包含武汉市", "D": "武汉市和南京市只隔一条江"},
    "answer": "B",
    "answer_structured": {"touches": false, "actual_relation": "disjoint（分离，中间隔有其他城市）", "correct_option": "B", "explanation": "武汉南京不接壤，空间上分离（LLM推断）"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "武汉和南京虽然都位于长江沿岸，但它们在空间上并不相邻接，两城市之间属于______关系。",
    "answer": "分离（disjoint）",
    "answer_structured": {"touches": false, "actual_relation": "disjoint（分离，中间隔有其他城市）", "fill_answer": "分离（disjoint）", "explanation": "两城市空间分离，不共享边界（LLM推断）"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "武汉和南京都是长江流域的省会城市，容易让人误以为它们相邻。请从空间拓扑的角度解释为什么它们不是相邻关系，并说明如何通过GIS方法验证这一点。",
    "answer": "武汉和南京虽然同属长江流域，但两城市并不共享行政边界。从空间拓扑角度看，ST_Touches(武汉市, 南京市) = false，两市的Polygon几何之间没有边界接触。实际上，它们之间的空间关系是disjoint（分离），中间还隔着多个地级市（如湖北省的黄冈市、黄石市，安徽省的合肥市等）。验证方法是：在GIS中加载两市的行政区域Polygon数据，执行ST_Touches查询。如果返回false，则说明两市不共享边界。还可以用ST_Distance计算两市的距离，进一步确认它们之间的空间间隔。",
    "answer_structured": {"touches": false, "actual_relation": "disjoint（分离，中间隔有其他城市）", "explanation": "武汉南京不接壤，GIS计算可精确验证（LLM推断）"},
    "difficulty": "easy"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "湖南省", "centroid": [111.71, 27.63], "type": "province"}
实体B: {"name_zh": "浙江省", "centroid": [120.15, 29.28], "type": "province"}
空间事实: {"touches": false}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "湖南和浙江两省都位于中国南方地区，有人说它们是相邻省份。这一说法正确吗？",
    "answer": "错误",
    "answer_structured": {"touches": false, "actual_relation": "disjoint（分离，中间隔有江西省）", "explanation": "湖南和浙江中间隔江西省，不共享边界（LLM推断）"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "关于湖南省与浙江省的空间关系，以下哪项描述是正确的？",
    "options": {"A": "湖南省与浙江省直接相邻接壤", "B": "湖南省完全包含浙江省", "C": "湖南省与浙江省不相邻，中间隔有其他省份", "D": "湖南省与浙江省仅隔一条河"},
    "answer": "C",
    "answer_structured": {"touches": false, "actual_relation": "disjoint（分离，中间隔有江西省）", "correct_option": "C", "explanation": "江西隔开湖南和浙江，两省不相邻（LLM推断）"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "湖南省与浙江省虽然在纬度上较为接近，但两省并不接壤，中间被______省隔开。",
    "answer": "江西",
    "answer_structured": {"touches": false, "actual_relation": "disjoint（分离，中间隔有江西省）", "fill_answer": "江西", "explanation": "江西省位于湖南和浙江之间（LLM推断）"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "在一张简化的中国地图上，湖南省和浙江省看起来都是中南/东南沿海的省份，容易让人混淆它们是否相邻。请从空间拓扑角度分析它们的关系，并解释江西省在其中的空间角色。",
    "answer": "从空间拓扑角度看，ST_Touches(湖南省, 浙江省) = false，两省的Polygon几何之间没有边界接触。两省的实际关系是disjoint（分离）。江西省在空间上位于湖南省的东侧和浙江省的西侧，起到了'地理屏障'的作用——它的Polygon分别与湖南省和浙江省共享边界（touches），从而将两省隔开。也就是说，ST_Touches(湖南省, 江西省) = true 且 ST_Touches(江西省, 浙江省) = true，但 ST_Touches(湖南省, 浙江省) = false。这体现了空间拓扑的传递性不成立：如果A与B相邻，B与C相邻，不能推出A与C相邻。",
    "answer_structured": {"touches": false, "actual_relation": "disjoint（分离，中间隔有江西省）", "explanation": "相邻关系不具有传递性，江西隔开湖南和浙江（LLM推断）"},
    "difficulty": "medium"
  }
}
```
