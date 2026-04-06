# 拓扑分离关系（负例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑分离关系（负例）**的题目。负例意味着实体A和实体B**不是**完全分离的，它们之间存在某种空间交集（相邻、包含、穿越等），空间事实中 `disjoint` 为 `false`。你需要围绕"A和B不是完全分离的"这一事实设计题目，重点测试学习者识别错误空间陈述的能力。

### 负例专项约束
- 将假关系包装为**看似合理的陈述**，使题目具有迷惑性。
- 正确答案应明确指出分离关系为假，并说明A和B之间的实际空间关系。
- **不要**制造明显荒谬的错误。
- 优先选择在地理位置上看起来可能分离、但实际上有空间交集的实体对，增加迷惑性。
- `answer_structured` 中必须增加 `actual_relation` 字段，详细描述A和B之间的实际空间关系（如相邻、被包围、包含等）。**请在答案中根据你的地理知识推断A和B的实际空间关系**，将推断结果填入 `actual_relation` 字段。输入数据中不提供此字段。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"disjoint": false}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须围绕"A和B不是完全分离的"这一空间关系事实展开。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"disjoint": false}
难度: {{difficulty}}
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"disjoint": false, "actual_relation": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"disjoint": false, "actual_relation": "...", "correct_option": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"disjoint": false, "actual_relation": "...", "fill_answer": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"disjoint": false, "actual_relation": "...", "explanation": "..."},
    "difficulty": "..."
  }
}
```

> **注意**：`actual_relation` 字段不由输入数据提供，需由LLM根据地理知识推断A和B之间的实际空间关系，将推断结果填入该字段。

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"disjoint": false}`。不得编造任何空间信息。`actual_relation` 由LLM根据地理知识推断，必须准确描述实际关系。
2. **迷惑性设计**：
   - 题目中的假陈述应该看起来合理。利用实体在地图上的距离感或行政区划差异制造迷惑。
   - 例如：河北省和北京市看起来可能是分离的（北京是独立的直辖市），但实际上它们是相邻的。
3. **多样性自然语言**：4道题目的提问风格、措辞方式、考察角度必须明显不同。
4. **难度适配**：根据 `{{difficulty}}` 调整迷惑程度：
   - easy：假关系有一定迷惑性但可通过常识判断。
   - medium：需要较深入的地理知识才能识别。
   - hard：需要精确的空间推理或多重线索综合判断。
5. **answer_structured必须包含actual_relation字段**：说明A和B实际的拓扑关系（如touches相邻、contains包含、within包含于等，由LLM根据地理知识推断）。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "河北省", "centroid": [114.48, 38.04], "type": "province"}
实体B: {"name_zh": "北京市", "centroid": [116.41, 39.90], "type": "city"}
空间事实: {"disjoint": false}
难度: easy
```

**输出：**
```json
{
  "true_false": {
    "question": "有人认为"北京是独立的直辖市，与河北省之间没有任何空间接触"。这一说法正确吗？",
    "answer": "错误",
    "answer_structured": {"disjoint": false, "actual_relation": "touches（相邻接壤，河北省包围北京市外围）", "explanation": "河北环绕北京，两省市的边界直接接触，不是分离关系（LLM推断）"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于河北省与北京市的空间关系，以下哪个描述是正确的？",
    "options": {"A": "两省市完全分离，没有空间接触", "B": "两省市相邻接壤，河北省环绕北京", "C": "北京市完全包含河北省", "D": "两省市仅通过一条河流相连"},
    "answer": "B",
    "answer_structured": {"disjoint": false, "actual_relation": "touches（相邻接壤，河北省包围北京市外围）", "correct_option": "B", "explanation": "河北环绕北京，边界直接接触（LLM推断）"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "河北省和北京市虽然行政上相互独立，但在空间上并不分离，它们之间的实际关系是______。",
    "answer": "相邻接壤（河北省环绕包围北京市）",
    "answer_structured": {"disjoint": false, "actual_relation": "touches（相邻接壤，河北省包围北京市外围）", "fill_answer": "相邻接壤（河北省环绕包围北京市）", "explanation": "河北环绕北京，属于touches关系（LLM推断）"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "北京市作为直辖市，行政上不隶属于河北省。有人据此推断两省市在空间上'完全分离'。请从空间拓扑角度反驳这一观点，并说明行政独立性与空间分离性的区别。",
    "answer": "行政独立性和空间分离性是两个不同的概念。行政上独立不代表空间上分离。从空间拓扑角度看，ST_Disjoint(河北省, 北京市) = false，说明两省市的几何范围存在空间接触。具体而言，河北省的Polygon几何围绕北京市的Polygon几何，两者共享一段较长的边界线——这是一种touches（相邻接壤）关系。事实上，北京的北部、西部和南部都与河北省直接接壤（如承德、张家口、保定、廊坊等河北城市环绕北京）。这种'行政独立但空间相邻'的情况在中国行政区划中很常见（如天津与河北、上海与江苏/浙江等）。",
    "answer_structured": {"disjoint": false, "actual_relation": "touches（相邻接壤，河北省包围北京市外围）", "explanation": "行政独立不等于空间分离，河北环绕北京，边界直接接触（LLM推断）"},
    "difficulty": "easy"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "青海省", "centroid": [96.78, 36.62], "type": "province"}
实体B: {"name_zh": "四川省", "centroid": [102.70, 30.57], "type": "province"}
空间事实: {"disjoint": false}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "有观点认为"青海省地处青藏高原，四川省位于四川盆地，两省在空间上没有任何接触"。这一说法正确吗？",
    "answer": "错误",
    "answer_structured": {"disjoint": false, "actual_relation": "touches（相邻接壤，两省共享西部边界）", "explanation": "青海和四川在西部地区共享行政边界，不相离（LLM推断）"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "青海省和四川省分别以高原和盆地著称，关于它们的空间关系，以下哪项正确？",
    "options": {"A": "两省完全分离，互不接触", "B": "两省相邻接壤，共享西部边界", "C": "四川省完全包含青海省", "D": "两省仅有水域上的接触"},
    "answer": "B",
    "answer_structured": {"disjoint": false, "actual_relation": "touches（相邻接壤，两省共享西部边界）", "correct_option": "B", "explanation": "青海东南与四川西北接壤（LLM推断）"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "青海省和四川省虽然在地理景观上差异巨大（高原vs盆地），但两省在空间上并不分离，实际的关系是______。",
    "answer": "相邻接壤（共享西部边界）",
    "answer_structured": {"disjoint": false, "actual_relation": "touches（相邻接壤，两省共享西部边界）", "fill_answer": "相邻接壤（共享西部边界）", "explanation": "两省在西部地区接壤（LLM推断）"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "青海省位于青藏高原，四川省以四川盆地闻名，两者的地理特征截然不同。这容易让人误以为它们在空间上是分离的。请从空间拓扑角度说明为什么它们不是disjoint关系，并解释地理特征差异与空间拓扑关系之间的独立性。",
    "answer": "地理特征的差异（高原vs盆地）不等于空间上的分离。从空间拓扑角度看，ST_Disjoint(青海省, 四川省) = false，两省的Polygon几何之间存在边界接触——即ST_Touches(青海省, 四川省) = true。青海省的东南部（如果洛州、阿坝州相邻区域）与四川省的西北部（如阿坝藏族羌族自治州）直接接壤，共享行政边界线。这个案例说明：空间拓扑关系（是否相邻、是否分离）是由几何形状的精确空间位置决定的，与地理地貌特征无关。两个地理特征完全不同的区域完全可以是相邻的，正如青海的高原和四川的盆地在行政边界上直接接触一样。",
    "answer_structured": {"disjoint": false, "actual_relation": "touches（相邻接壤，两省共享西部边界）", "explanation": "地理特征差异不等于空间分离，青海四川在边界上直接接触（LLM推断）"},
    "difficulty": "medium"
  }
}
```
