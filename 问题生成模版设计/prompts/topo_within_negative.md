# 拓扑包含于关系（负例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑包含于关系（负例）**的题目。负例意味着实体A**不**在实体B内部，空间事实中 `within` 为 `false`。你需要围绕"A不在B内部"这一事实设计题目，重点测试学习者识别错误空间陈述的能力。

### 负例专项约束
- 将假关系包装为**看似合理的陈述**，使题目具有迷惑性。
- 正确答案应明确指出包含于关系为假，并给出A实际所在的容器实体。
- **不要**制造明显荒谬的错误（例如"北京在太平洋内部"这种明显不合理的配对）。
- `answer_structured` 中必须增加 `actual_container` 字段，指明A实际在哪个实体内部。
- **请在答案中根据你的地理知识推断entity_a实际属于哪个地理单元**，将推断结果填入 `actual_container` 字段。输入数据中不提供此字段。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"within": false}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须围绕"A不在B内部"这一空间关系事实展开。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"within": false}
难度: {{difficulty}}
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"within": false, "actual_container": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"within": false, "actual_container": "...", "correct_option": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"within": false, "actual_container": "...", "fill_answer": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"within": false, "actual_container": "...", "explanation": "..."},
    "difficulty": "..."
  }
}
```

> **注意**：`actual_container` 字段不由输入数据提供，需由LLM根据地理知识推断entity_a实际在哪个实体内部，将推断结果填入该字段。

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"within": false}`。不得编造任何空间信息。`actual_container` 由LLM根据地理知识推断，必须准确。
2. **迷惑性设计**：
   - 题目中的假陈述应该看起来合理，利用地理邻近性或名称相似性制造迷惑。
   - 例如：华山和河南省在地理位置上有一定关联，但华山实际位于陕西省。
3. **多样性自然语言**：4道题目的提问风格、措辞方式、考察角度必须明显不同。
4. **难度适配**：根据 `{{difficulty}}` 调整迷惑程度：
   - easy：假关系有一定迷惑性但可通过常识判断。
   - medium：需要较深入的地理知识才能识别。
   - hard：需要精确的空间推理或多重线索综合判断。
5. **answer_structured必须包含actual_container字段**：指明A实际在哪个实体内部（由LLM根据地理知识推断）。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "华山", "centroid": [110.08, 34.48], "type": "mountain"}
实体B: {"name_zh": "河南省", "centroid": [113.65, 34.76], "type": "province"}
空间事实: {"within": false}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "有旅行攻略写道"华山位于河南省境内，是中原大地上的名山"，这一说法是否正确？",
    "answer": "错误",
    "answer_structured": {"within": false, "actual_container": "陕西省", "explanation": "华山实际位于陕西省，不在河南省内部（LLM推断）"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "华山是中国五岳之一，被誉为'西岳'。关于它的空间归属，以下哪项正确？",
    "options": {"A": "华山位于河南省境内", "B": "华山位于山西省境内", "C": "华山位于陕西省境内", "D": "华山跨越河南和陕西两省"},
    "answer": "C",
    "answer_structured": {"within": false, "actual_container": "陕西省", "correct_option": "C", "explanation": "华山Point在陕西省Polygon内部，不在河南省内部（LLM推断）"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "华山虽然地处中原腹地附近，但它并不在河南省境内，而是完全位于______省的行政区域范围内。",
    "answer": "陕西",
    "answer_structured": {"within": false, "actual_container": "陕西省", "fill_answer": "陕西", "explanation": "华山实际归属陕西省（LLM推断）"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "华山位于河南省与陕西省的交界区域附近，有人因此认为它"地跨两省"。请从空间拓扑关系角度分析这种说法为什么不准确。",
    "answer": "这种说法不准确。虽然华山地处河南与陕西交界的附近区域，但从空间拓扑上看，ST_Within(华山, 河南省) = false，华山并不在河南省的行政区域内。实际上，华山的Point几何完全落在陕西省的Polygon几何内部，即华山完全属于陕西省。空间上的"靠近边界"不等于"跨越边界"，ST_Within的结果明确表明华山只在陕西省一侧。",
    "answer_structured": {"within": false, "actual_container": "陕西省", "explanation": "靠近边界不等于跨越边界，华山完全在陕西省内部（LLM推断）"},
    "difficulty": "medium"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "太湖", "centroid": [120.15, 31.24], "type": "lake"}
实体B: {"name_zh": "安徽省", "centroid": [117.28, 31.86], "type": "province"}
空间事实: {"within": false}
难度: hard
```

**输出：**
```json
{
  "true_false": {
    "question": "太湖作为中国第三大淡水湖，有观点认为它位于安徽省境内。这一说法正确吗？",
    "answer": "错误",
    "answer_structured": {"within": false, "actual_container": "江苏省/浙江省（跨两省）", "explanation": "太湖不在安徽省内部，实际跨江苏和浙江两省（LLM推断）"},
    "difficulty": "hard"
  },
  "choice": {
    "question": "太湖地处长三角地区，关于其空间归属，以下哪项描述最准确？",
    "options": {"A": "太湖完全位于安徽省境内", "B": "太湖完全位于浙江省境内", "C": "太湖主要位于江苏省和浙江省境内", "D": "太湖位于安徽省和江苏省交界处"},
    "answer": "C",
    "answer_structured": {"within": false, "actual_container": "江苏省/浙江省（跨两省）", "correct_option": "C", "explanation": "太湖横跨江苏和浙江，不在安徽境内（LLM推断）"},
    "difficulty": "hard"
  },
  "fill_blank": {
    "question": "有人误以为太湖在安徽省境内，但实际上太湖主要位于______省和______省之间。",
    "answer": "江苏、浙江",
    "answer_structured": {"within": false, "actual_container": "江苏省/浙江省（跨两省）", "fill_answer": "江苏、浙江", "explanation": "太湖实际跨越江苏和浙江两省（LLM推断）"},
    "difficulty": "hard"
  },
  "open_qa": {
    "question": "安徽省、江苏省和浙江省都位于华东地区，太湖的位置经常被混淆。请利用空间拓扑概念，说明为什么ST_Within(太湖, 安徽省) = false，并分析太湖与这三个省的实际空间关系。",
    "answer": "ST_Within(太湖, 安徽省) = false的原因是：太湖的Polygon几何范围与安徽省的Polygon几何范围没有内部包含关系。太湖的实际空间位置在安徽省的东部，其水域范围主要横跨江苏省和浙江省。太湖与安徽省的关系可能是相离(disjoint)或仅边界接触(touches)，但绝不是'在安徽省内部'(within)。这提醒我们，同一地理区域内的多个省份，其内部的地理要素归属需要精确的空间计算来确定，不能仅凭'同属华东'就做出错误判断。",
    "answer_structured": {"within": false, "actual_container": "江苏省/浙江省（跨两省）", "explanation": "太湖不在安徽内部，实际跨越江苏和浙江，与安徽的关系可能是相离或接触（LLM推断）"},
    "difficulty": "hard"
  }
}
```
