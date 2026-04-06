# 拓扑包含关系（负例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑包含关系（负例）**的题目。负例意味着实体A**不**包含实体B，空间事实中 `contains` 为 `false`。你需要围绕"A不包含B"这一假关系设计题目，重点测试学习者识别错误空间陈述的能力。

### 负例专项约束
- 将假关系包装为**看似合理的陈述**，使题目具有迷惑性。
- 正确答案应明确指出包含关系为假，并给出实际容器实体。
- **不要**制造明显荒谬的错误（例如"北京市包含太平洋"这种明显不合理的配对）。
- `answer_structured` 中必须增加 `actual_container` 字段，指明B实际被哪个实体包含。
- **请在答案中根据你的地理知识推断entity_b实际属于哪个地理单元**，将推断结果填入 `actual_container` 字段。输入数据中不提供此字段。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"contains": false}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须围绕"A不包含B"这一空间关系事实展开。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"contains": false}
难度: {{difficulty}}
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"contains": false, "actual_container": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"contains": false, "actual_container": "...", "correct_option": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"contains": false, "actual_container": "...", "fill_answer": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"contains": false, "actual_container": "...", "explanation": "..."},
    "difficulty": "..."
  }
}
```

> **注意**：`actual_container` 字段不由输入数据提供，需由LLM根据地理知识推断entity_b实际被哪个实体包含，将推断结果填入该字段。

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"contains": false}`。不得编造任何空间信息。`actual_container` 由LLM根据地理知识推断，必须准确。
2. **迷惑性设计**：
   - 题目中的假陈述应该看起来合理，利用地理邻近性或层级相似性制造迷惑。
   - 例如：河南省和武汉市都在华中地区，但武汉市并不属于河南省。
3. **多样性自然语言**：4道题目的提问风格、措辞方式、考察角度必须明显不同。
4. **难度适配**：根据 `{{difficulty}}` 调整迷惑程度：
   - easy：假关系有一定迷惑性但可通过常识判断。
   - medium：需要较深入的地理知识才能识别。
   - hard：需要精确的空间推理或多重线索综合判断。
5. **answer_structured必须包含actual_container字段**：指明B实际被哪个实体包含（由LLM根据地理知识推断）。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "河南省", "centroid": [113.65, 34.76], "type": "province"}
实体B: {"name_zh": "武汉市", "centroid": [114.30, 30.59], "type": "city"}
空间事实: {"contains": false}
难度: easy
```

**输出：**
```json
{
  "true_false": {
    "question": "有同学认为"武汉市位于河南省的管辖范围内"，这一说法是否正确？",
    "answer": "错误",
    "answer_structured": {"contains": false, "actual_container": "湖北省", "explanation": "ST_Contains(河南省, 武汉市) = false，武汉市实际被湖北省包含（LLM推断）"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "在以下关于武汉市的空间归属陈述中，哪一项是正确的？",
    "options": {"A": "武汉市被河南省的行政区域所包含", "B": "武汉市被湖北省的行政区域所包含", "C": "武汉市与河南省和湖北省都不相邻", "D": "武汉市位于河南省和湖北省的交界线上"},
    "answer": "B",
    "answer_structured": {"contains": false, "actual_container": "湖北省", "correct_option": "B", "explanation": "河南省不包含武汉市，实际包含武汉市的是湖北省（LLM推断）"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "虽然河南省与武汉市在地理位置上较为接近，但武汉市实际上并不在河南省境内，而是被______省的行政区域所包含。",
    "answer": "湖北",
    "answer_structured": {"contains": false, "actual_container": "湖北省", "fill_answer": "湖北", "explanation": "武汉市的实际归属省份是湖北省（LLM推断）"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "有人主张"武汉是华中地区最大的城市，因此它应该位于河南省境内"。请从空间拓扑关系的角度分析这一主张的错误。",
    "answer": "这一主张在空间拓扑上是错误的。"华中地区最大城市"并不能推出"位于河南省境内"的结论。根据PostGIS空间计算，ST_Contains(河南省, 武汉市) = false，河南省的几何范围不包含武汉市的几何范围。实际上，武汉市是湖北省的省会，其空间范围完全位于湖北省的行政区域内。地理区域概念（华中地区）与具体行政区划归属（省）是两个不同的层次，不能混为一谈。",
    "answer_structured": {"contains": false, "actual_container": "湖北省", "explanation": "河南省不包含武汉市，武汉实际属于湖北省（LLM推断）"},
    "difficulty": "easy"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "浙江省", "centroid": [120.15, 29.28], "type": "province"}
实体B: {"name_zh": "黄山市", "centroid": [118.17, 29.72], "type": "city"}
空间事实: {"contains": false}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "黄山市因盛产黄山毛峰等浙江名茶而闻名，它应当位于浙江省的行政区域内。该说法正确吗？",
    "answer": "错误",
    "answer_structured": {"contains": false, "actual_container": "安徽省", "explanation": "黄山市实际属于安徽省，不属浙江省（LLM推断）"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "黄山市地处皖浙赣三省交界区域，关于其行政归属，以下哪项描述在空间拓扑上是正确的？",
    "options": {"A": "黄山市被浙江省包含", "B": "黄山市与所有相邻省份都相离", "C": "黄山市被安徽省包含", "D": "黄山市同时被浙江和安徽两省包含"},
    "answer": "C",
    "answer_structured": {"contains": false, "actual_container": "安徽省", "correct_option": "C", "explanation": "浙江省不包含黄山市，黄山市实际由安徽省包含（LLM推断）"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "黄山市虽然与浙江省接壤，但在空间拓扑上，它并不被浙江省包含，而是完全位于______省的行政范围内。",
    "answer": "安徽",
    "answer_structured": {"contains": false, "actual_container": "安徽省", "fill_answer": "安徽", "explanation": "黄山市的空间范围在安徽省内部（LLM推断）"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "黄山市紧邻浙江省，两地经济文化往来频繁，甚至有些商品名称容易引发混淆。请从空间拓扑的角度，说明为什么不能因此认定黄山市属于浙江省。",
    "answer": "地理邻近性和文化联系不等同于行政归属。从空间拓扑角度看，ST_Contains(浙江省, 黄山市) = false，浙江省的Polygon几何范围并不包含黄山市的Polygon几何范围。黄山市虽与浙江省接壤（ST_Touches可能为true），但包含关系并不成立。事实上，黄山市的空间范围完全位于安徽省内部，它是安徽省下辖的地级市。两省之间的边界明确将黄山市划归安徽省管辖。",
    "answer_structured": {"contains": false, "actual_container": "安徽省", "explanation": "邻近不等于包含，黄山市由安徽省管辖（LLM推断）"},
    "difficulty": "medium"
  }
}
```
