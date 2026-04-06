# 拓扑穿越关系（负例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑穿越关系（负例）**的题目。负例意味着线状实体A**不**穿越面状实体B，空间事实中 `crosses` 为 `false`。你需要围绕"A不穿越B"这一事实设计题目，重点测试学习者识别错误空间陈述的能力。

### 负例专项约束
- 将假关系包装为**看似合理的陈述**，使题目具有迷惑性。
- 正确答案应明确指出穿越关系为假。
- **不要**制造明显荒谬的错误（例如"京沪高铁穿越西藏"这种明显不合理的配对）。
- 优先选择在地理位置上有一定关联但实际不穿越的实体对，增加迷惑性。
- 实体A通常是线状（river/road/railway），B是面状（province/city）。
- `answer_structured` 中可增加 `actual_relation` 字段，描述A和B之间的实际空间关系。**请在答案中根据你的地理知识推断A和B的实际空间关系**，将推断结果填入 `actual_relation` 字段。输入数据中不提供此字段。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"crosses": false}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须围绕"A不穿越B"这一空间关系事实展开。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"crosses": false}
难度: {{difficulty}}
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"crosses": false, "actual_relation": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"crosses": false, "actual_relation": "...", "correct_option": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"crosses": false, "actual_relation": "...", "fill_answer": "...", "explanation": "..."},
    "difficulty": "..."
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"crosses": false, "actual_relation": "...", "explanation": "..."},
    "difficulty": "..."
  }
}
```

> **注意**：`actual_relation` 字段不由输入数据提供，需由LLM根据地理知识推断A和B之间的实际空间关系，将推断结果填入该字段。

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"crosses": false}`。不得编造任何空间信息。`actual_relation` 由LLM根据地理知识推断。
2. **迷惑性设计**：
   - 题目中的假陈述应该看起来合理，利用河流名称、省份位置等制造迷惑。
   - 例如：黄河是中国北方的大河，但它并不穿越江西省。
3. **多样性自然语言**：4道题目的提问风格、措辞方式、考察角度必须明显不同。
4. **难度适配**：根据 `{{difficulty}}` 调整迷惑程度：
   - easy：假关系有一定迷惑性但可通过常识判断。
   - medium：需要较深入的地理知识才能识别。
   - hard：需要精确的空间推理或多重线索综合判断。
5. **answer_structured包含actual_relation字段**：描述A和B实际的拓扑关系（如disjoint分离等，由LLM根据地理知识推断）。
6. **几何类型关注**：题目中应适当体现A是线状实体、B是面状实体的几何特征。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "黄河", "centroid": [104.50, 36.00], "type": "river"}
实体B: {"name_zh": "江西省", "centroid": [115.89, 28.68], "type": "province"}
空间事实: {"crosses": false}
难度: easy
```

**输出：**
```json
{
  "true_false": {
    "question": "有人说"黄河是中国第二长河，它流经了包括江西在内的多个南方省份"。这一说法中关于江西的部分正确吗？",
    "answer": "错误",
    "answer_structured": {"crosses": false, "actual_relation": "disjoint（分离，黄河位于北方，江西位于南方）", "explanation": "黄河在北方，江西在南方，空间上分离（LLM推断）"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于黄河与江西省的空间关系，以下哪项是正确的？",
    "options": {"A": "黄河穿越了江西省", "B": "黄河的某条支流穿越了江西省", "C": "黄河不经过江西省", "D": "黄河在江西省注入大海"},
    "answer": "C",
    "answer_structured": {"crosses": false, "actual_relation": "disjoint（分离，黄河位于北方，江西位于南方）", "correct_option": "C", "explanation": "黄河和江西空间分离，无交集（LLM推断）"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "黄河是中国北方的主要河流，它______（穿越/不穿越）江西省。",
    "answer": "不穿越",
    "answer_structured": {"crosses": false, "actual_relation": "disjoint（分离，黄河位于北方，江西位于南方）", "fill_answer": "不穿越", "explanation": "黄河河道在北方，与江西省空间分离（LLM推断）"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "有人将黄河和长江混淆，认为黄河也流经了南方省份。请从空间拓扑的角度分析黄河与江西省的关系，并说明为什么crosses关系为false。",
    "answer": "黄河与江西省之间不存在穿越关系。ST_Crosses(黄河, 江西省) = false，原因在于黄河的LineString几何与江西省的Polygon几何在空间上完全分离(disjoint)。黄河发源于青海省，流经北方九省区后注入渤海，其河道全部位于中国北方（纬度大致在34-42度之间）。而江西省位于长江以南（纬度大致在24-30度之间），两者之间的纬度差距使黄河的任何河段都不可能进入江西省境内。这是一个典型的crosses为负的案例：线状实体与面状实体在空间上完全不重叠。",
    "answer_structured": {"crosses": false, "actual_relation": "disjoint（分离，黄河位于北方，江西位于南方）", "explanation": "黄河和江西在空间上完全分离，纬度差距大（LLM推断）"},
    "difficulty": "easy"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "珠江", "centroid": [110.50, 23.50], "type": "river"}
实体B: {"name_zh": "湖南省", "centroid": [111.71, 27.63], "type": "province"}
空间事实: {"crosses": false}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "珠江作为中国南方最大的河流系统，有观点认为其干流穿越了湖南省。这一观点是否正确？",
    "answer": "错误",
    "answer_structured": {"crosses": false, "actual_relation": "disjoint（分离，珠江流域在湖南以南）", "explanation": "珠江在湖南以南，两者空间分离（LLM推断）"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "珠江是中国第三大河流，关于它和湖南省的空间关系，以下哪个判断正确？",
    "options": {"A": "珠江干流穿越了湖南省", "B": "珠江与湖南省空间上分离，不穿越该省", "C": "珠江完全位于湖南省内部", "D": "珠江仅在湖南省边界上经过"},
    "answer": "B",
    "answer_structured": {"crosses": false, "actual_relation": "disjoint（分离，珠江流域在湖南以南）", "correct_option": "B", "explanation": "珠江和湖南空间分离（LLM推断）"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "珠江虽然是中国南方的重要水系，但其干流并没有穿越湖南省，穿越湖南省的主要河流是______。",
    "answer": "湘江（长江支流）",
    "answer_structured": {"crosses": false, "actual_relation": "disjoint（分离，珠江流域在湖南以南）", "fill_answer": "湘江（长江支流）", "explanation": "湖南境内主要河流是湘江，属长江水系，不是珠江（LLM推断）"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "湖南省位于中国南方，珠江也是中国南方的主要河流，有人因此推测珠江穿越了湖南。请结合水系分布和空间拓扑知识，分析这种推测的错误之处。",
    "answer": "这种推测的错误在于将'同属中国南方'等同于'空间相交'。从空间拓扑角度看，ST_Crosses(珠江, 湖南省) = false，珠江的LineString几何与湖南省的Polygon几何没有交集。实际上，湖南省属于长江流域，其主要河流是湘江（长江的支流），而非珠江。珠江水系主要分布在湖南省以南的广西、广东等地。两者的分水岭大致在南岭山脉一带，这条山脉将珠江流域和长江流域分隔开来。因此，虽然湖南和珠江流域都在中国南方，但它们分属不同的水系，空间上并不相交。",
    "answer_structured": {"crosses": false, "actual_relation": "disjoint（分离，珠江流域在湖南以南）", "explanation": "同属南方不等于空间相交，南岭山脉分隔珠江和长江水系（LLM推断）"},
    "difficulty": "medium"
  }
}
```
