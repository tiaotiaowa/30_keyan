# 方向推理正例模板（Directional Positive）

## 系统角色

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 任务描述

根据给定的两个地理实体和它们之间的空间方向事实，生成包含**判断题、选择题、填空题、问答题**各一道的数据集条目。

核心任务：判断实体A相对于实体B的8方位方向（东、南、西、北、东北、东南、西北、西南）。

## 输入数据

```json
{
  "entity_a": {
    "name_zh": "吉林省",
    "centroid": [126.195, 43.6704],
    "type": "province"
  },
  "entity_b": {
    "name_zh": "江门市",
    "centroid": [112.6778, 22.2652],
    "type": "city"
  },
  "spatial_facts": {
    "direction_8": "东北",
    "azimuth_deg": 32.3
  },
  "difficulty": "easy"
}
```

### 占位符说明

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `吉林省` | 实体A中文名称 | "武汉市" |
| `[126.195, 43.6704]` | 实体A质心坐标 [lng, lat] | [114.305, 30.593] |
| `province` | 实体A地理类型 | "city" |
| `江门市` | 实体B中文名称 | "长沙市" |
| `[112.6778, 22.2652]` | 实体B质心坐标 [lng, lat] | [112.938, 28.228] |
| `city` | 实体B地理类型 | "city" |
| `东北` | A相对于B的8方位方向 | "东北" |
| `32.3` | A相对于B的方位角度数 | 29.7 |
| `easy` | 难度等级 | "easy" / "medium" / "hard" |

## 输出格式

输出严格为JSON，结构如下：

```json
{
  "true_false": {
    "question": "（判断题题目文本）",
    "answer": "（自然语言答案）",
    "answer_structured": {
      "type": "boolean",
      "value": true,
      "direction": "东北",
      "explanation": "..."
    },
    "difficulty": "easy"
  },
  "choice": {
    "question": "（选择题题目文本）",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "（自然语言答案，如'正确答案是B'）",
    "answer_structured": {
      "type": "option",
      "value": "B",
      "direction": "东北",
      "explanation": "..."
    },
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "（填空题题目文本，用___表示空白处）",
    "answer": "（自然语言答案）",
    "answer_structured": {
      "type": "keyword",
      "value": "东北",
      "explanation": "..."
    },
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "（问答题题目文本）",
    "answer": "（自然语言详细答案）",
    "answer_structured": {
      "type": "free_text",
      "direction": "东北",
      "explanation": "..."
    },
    "difficulty": "easy"
  }
}
```

## 多样性约束

### 判断题多样性

- **正向陈述**：直接说明A在B的某个方向（如"武汉市在长沙市的东北方向"）
- **反向陈述**：说明B在A的相反方向（如"长沙市在武汉市的西南方向"），此时方向需取反
  - 反向对应关系：东↔西、南↔北、东北↔西南、东南↔西北
- 判断题的value可以是true（陈述正确）或false（陈述错误，故意给出错误方向）

### 选择题多样性

- 可嵌入不同场景：
  - **旅行场景**："小明计划从B出发前往A，他应该往哪个方向走？"
  - **出差场景**："公司总部在B，分公司在A，从总部到分公司的方向是？"
  - **导航场景**："如果你正在B市，想要前往A市，导航仪会提示你向哪个方向行驶？"
  - **知识问答场景**："关于A和B的相对位置，以下哪个说法是正确的？"
- 选项顺序随机排列，正确答案可以是A/B/C/D中的任意一个
- 干扰项应从8方位中选取，包含与正确方向相邻的方向（如正确答案是东北，干扰项可包含北、东）和非相邻方向

### 填空题多样性

变换句式，不局限于"A位于B的___方向"一种格式：
- "从B前往A，大致需要向___方向行进"
- "站在B市眺望A市，你会面朝___方向"
- "A市坐落在B市的___方位"
- "在地图上，A位于B的___一侧"
- "如果以B为参照点，A处于___方向"

### 问答题多样性

要求不同的作答方式：
- **描述型**："请描述A相对于B的空间方位关系"
- **分析型**："根据A和B的地理位置，分析A在B的哪个方向，并解释原因"
- **对比型**："如果从B出发分别向正东和正北方向移动，A位于什么方向？请说明你的判断"
- **应用型**："一位旅行者在B市想知道A市在什么方向，你会如何回答？请详细说明"

### 连续生成约束

连续生成同一实体对时，确保每次的题目风格、句式、场景都不重复。

## 难度控制

通过 `easy` 占位符控制题目难度：

### easy（简单）
- 判断题：直接使用正向陈述，如"A在B的东北方向"
- 选择题：直接提问方向，4个选项覆盖差异较大的方位
- 填空题：使用基本句式，如"A位于B的___方向"
- 问答题：直接问"A在B的什么方向"

### medium（中等）
- 判断题：可使用反向陈述或嵌入简单场景
- 选择题：嵌入旅行/导航场景，干扰项包含相邻方向
- 填空题：使用较复杂句式或结合场景
- 问答题：要求分析或结合场景作答

### hard（困难）
- 判断题：结合方位角信息进行提问，如"A在B的偏东方向，方位角约为30度"
- 选择题：干扰项为相邻方向，需结合方位角精确判断
- 填空题：需多步推理或结合地图知识
- 问答题：要求精确角度描述、多步推理、或对比分析

---

## 完整示例

### 示例1：武汉-长沙

**输入：**

```json
{
  "entity_a": {
    "name_zh": "武汉市",
    "centroid": [114.305, 30.593],
    "type": "city"
  },
  "entity_b": {
    "name_zh": "长沙市",
    "centroid": [112.938, 28.228],
    "type": "city"
  },
  "spatial_facts": {
    "direction_8": "东北",
    "azimuth_deg": 29.7
  },
  "difficulty": "easy"
}
```

**输出：**

```json
{
  "true_false": {
    "question": "武汉市位于长沙市的东北方向。",
    "answer": "正确。武汉市位于长沙市的东北方向。",
    "answer_structured": {
      "type": "boolean",
      "value": true,
      "direction": "东北",
      "explanation": "武汉市位于长沙市的东北方向"
    },
    "difficulty": "easy"
  },
  "choice": {
    "question": "小明计划从长沙出发前往武汉旅游，他应该往哪个方向走？",
    "options": {"A": "西南方向", "B": "西北方向", "C": "东北方向", "D": "东南方向"},
    "answer": "正确答案是C。从长沙出发前往武汉应向东北方向走。",
    "answer_structured": {
      "type": "option",
      "value": "C",
      "direction": "东北",
      "explanation": "从长沙出发前往武汉应向东北方向走"
    },
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "从长沙前往武汉，大致需要向___方向行进。",
    "answer": "东北",
    "answer_structured": {
      "type": "keyword",
      "value": "东北",
      "explanation": "从长沙前往武汉需要向东北方向行进"
    },
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请描述武汉市相对于长沙市的空间方位关系。",
    "answer": "武汉市位于长沙市的东北方向。从方位角来看，武汉市相对长沙市的方位角约为29.7度，属于东北方位。",
    "answer_structured": {
      "type": "free_text",
      "direction": "东北",
      "explanation": "武汉市位于长沙市的东北方向，方位角约29.7度"
    },
    "difficulty": "easy"
  }
}
```

### 示例2：广州-长沙

**输入：**

```json
{
  "entity_a": {
    "name_zh": "广州市",
    "centroid": [113.264, 23.129],
    "type": "city"
  },
  "entity_b": {
    "name_zh": "长沙市",
    "centroid": [112.938, 28.228],
    "type": "city"
  },
  "spatial_facts": {
    "direction_8": "南",
    "azimuth_deg": 195.3
  },
  "difficulty": "medium"
}
```

**输出：**

```json
{
  "true_false": {
    "question": "长沙市在广州市的北方向，也就是说广州市在长沙市的南方向。",
    "answer": "正确。广州市位于长沙市的南方向，反过来长沙市位于广州市的北方向。",
    "answer_structured": {
      "type": "boolean",
      "value": true,
      "direction": "南",
      "explanation": "广州市位于长沙市的南方向"
    },
    "difficulty": "medium"
  },
  "choice": {
    "question": "某公司总部设在长沙市，现在要在广州市设立分公司。从总部视角看，分公司位于哪个方向？",
    "options": {"A": "东南方向", "B": "西南方向", "C": "南方向", "D": "西方向"},
    "answer": "正确答案是C。从长沙市（总部）视角看，广州市（分公司）位于南方向。",
    "answer_structured": {
      "type": "option",
      "value": "C",
      "direction": "南",
      "explanation": "从长沙市视角看，广州市位于南方向"
    },
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "站在长沙市向南眺望，广州市正好处在___方向上。",
    "answer": "南",
    "answer_structured": {
      "type": "keyword",
      "value": "南",
      "explanation": "广州市位于长沙市的正南方向"
    },
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "一位旅行者正在长沙市，他想去广州市游玩。请你分析广州市相对于长沙市的方向关系，并为他提供方位指引。",
    "answer": "广州市位于长沙市的正南方向，方位角约为195.3度。旅行者从长沙出发，应向正南方行进即可到达广州。",
    "answer_structured": {
      "type": "free_text",
      "direction": "南",
      "explanation": "广州市位于长沙市的正南方向，方位角约195.3度"
    },
    "difficulty": "medium"
  }
}
```
