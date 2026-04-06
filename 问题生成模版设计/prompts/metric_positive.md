# 距离推理正例模板（Metric Positive）

## 系统角色

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 任务描述

根据给定的两个地理实体和它们之间的距离事实，生成包含**判断题、选择题、填空题、问答题**各一道的数据集条目。

核心任务：判断两实体之间的直线距离（单位：公里）。

## 输入数据

```json
{
  "entity_a": {
    "name_zh": "{{entity_a_name}}",
    "centroid": {{entity_a_centroid}},
    "type": "{{entity_a_type}}"
  },
  "entity_b": {
    "name_zh": "{{entity_b_name}}",
    "centroid": {{entity_b_centroid}},
    "type": "{{entity_b_type}}"
  },
  "spatial_facts": {
    "distance_km": {{fact_distance_km}}
  },
  "difficulty": "{{difficulty}}"
}
```

### 占位符说明

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `{{entity_a_name}}` | 实体A中文名称 | "北京市" |
| `{{entity_a_centroid}}` | 实体A质心坐标 [lng, lat] | [116.407, 39.904] |
| `{{entity_a_type}}` | 实体A地理类型 | "city" |
| `{{entity_b_name}}` | 实体B中文名称 | "上海市" |
| `{{entity_b_centroid}}` | 实体B质心坐标 [lng, lat] | [121.474, 31.230] |
| `{{entity_b_type}}` | 实体B地理类型 | "city" |
| `{{fact_distance_km}}` | A与B之间的直线距离（公里） | 1068 |
| `{{difficulty}}` | 难度等级 | "easy" / "medium" / "hard" |

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
      "distance_km": 1068,
      "explanation": "..."
    },
    "difficulty": "{{difficulty}}"
  },
  "choice": {
    "question": "（选择题题目文本）",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "（自然语言答案，如'正确答案是C'）",
    "answer_structured": {
      "type": "option",
      "value": "C",
      "distance_km": 1068,
      "explanation": "..."
    },
    "difficulty": "{{difficulty}}"
  },
  "fill_blank": {
    "question": "（填空题题目文本，用___表示空白处）",
    "answer": "（自然语言答案）",
    "answer_structured": {
      "type": "keyword",
      "value": "1068",
      "explanation": "..."
    },
    "difficulty": "{{difficulty}}"
  },
  "open_qa": {
    "question": "（问答题题目文本）",
    "answer": "（自然语言详细答案）",
    "answer_structured": {
      "type": "free_text",
      "distance_km": 1068,
      "explanation": "..."
    },
    "difficulty": "{{difficulty}}"
  }
}
```

## 多样性约束

### 判断题多样性

- **精确值陈述**：直接给出精确距离（如"北京与上海之间的直线距离约为1068公里"）
- **近似值陈述**：使用"大约""接近""将近"等表述（如"北京和上海的直线距离接近1100公里"）
- **比较型陈述**：将距离与另一个参照距离对比（如"北京到上海的直线距离比北京到天津的距离远得多"）
- **范围型陈述**：给出距离范围（如"北京到上海的直线距离在1000至1100公里之间"）
- 判断题的value可以是true（陈述正确）或false（陈述错误，故意给出错误距离）

### 选择题多样性

- 可嵌入不同场景：
  - **出行规划场景**："小明要从A市到B市出差，两地直线距离约为多少？"
  - **地理知识场景**："以下哪个数值最接近A市与B市之间的直线距离？"
  - **比较判断场景**："关于A和B之间的距离，以下哪个说法是正确的？"
  - **地图估算场景**："在比例尺为1:500万的地图上，A和B的直线距离约为多少？"

- 干扰项生成策略：
  - 真实距离的**0.5倍**左右（如真实296公里，干扰项约150公里）
  - 真实距离的**1.5倍**左右（如真实296公里，干扰项约450公里）
  - 真实距离的**3倍**左右（如真实296公里，干扰项约900公里）
  - 真实距离的**0.3倍**或**2倍**等明显偏大/偏小的值
  - 干扰项应为整数或合理近似值
- 选项顺序随机排列，正确答案可以是A/B/C/D中的任意一个
- 正确答案应标注"约"字（如"约296公里"），因为距离为近似直线距离

### 填空题多样性

变换句式，不局限于"A和B之间的距离是___公里"一种格式：
- "A市与B市的直线距离约为___公里"
- "从A到B的空中直线距离大约是___公里"
- "若乘坐飞机从A飞往B，直线航程约为___公里"
- "在地图上量算，A和B相距约___公里（直线距离）"
- "A市到B市的最近直线距离是___公里"

### 问答题多样性

要求不同的作答方式：
- **描述型**："A市和B市之间的直线距离是多少？请给出具体数值"
- **比较型**："A市和B市的直线距离约为多少？请将这个距离与另一个你熟悉的城市间距离进行比较"
- **场景型**："一位旅行者想从A市前往B市，请告诉他两地之间的直线距离，并说明这个距离大约相当于什么概念"
- **分析型**："已知A市和B市的地理位置，请分析两地的直线距离，并解释为什么两地的实际交通距离可能与直线距离不同"

### 连续生成约束

连续生成同一实体对时，确保每次的题目风格、句式、场景、干扰项都不重复。

## 难度控制

通过 `{{difficulty}}` 占位符控制题目难度：

### easy（简单）
- 判断题：直接给出精确距离值
- 选择题：4个选项差异较大（如296、150、900、450），容易区分
- 填空题：使用基本句式
- 问答题：直接问距离数值

### medium（中等）
- 判断题：使用近似值或范围陈述
- 选择题：嵌入场景，干扰项包含接近真实距离的值（如真实296，干扰项含250、350）
- 填空题：结合场景或使用复杂句式
- 问答题：要求比较或结合场景作答

### hard（困难）
- 判断题：需要判断近似值是否合理，或进行距离换算
- 选择题：干扰项非常接近真实值（如真实296，选项含280、296、310、330）
- 填空题：需要多步推理或换算
- 问答题：要求详细分析、换算、或结合多种地理知识

---

## 完整示例

### 示例1：北京-上海

**输入：**

```json
{
  "entity_a": {
    "name_zh": "北京市",
    "centroid": [116.407, 39.904],
    "type": "city"
  },
  "entity_b": {
    "name_zh": "上海市",
    "centroid": [121.474, 31.230],
    "type": "city"
  },
  "spatial_facts": {
    "distance_km": 1068
  },
  "difficulty": "easy"
}
```

**输出：**

```json
{
  "true_false": {
    "question": "北京与上海之间的直线距离约为1068公里。",
    "answer": "正确。北京市与上海市之间的直线距离约为1068公里。",
    "answer_structured": {
      "type": "boolean",
      "value": true,
      "distance_km": 1068,
      "explanation": "北京与上海的直线距离约为1068公里"
    },
    "difficulty": "easy"
  },
  "choice": {
    "question": "北京市与上海市之间的直线距离大约是多少？",
    "options": {"A": "约500公里", "B": "约800公里", "C": "约1068公里", "D": "约3200公里"},
    "answer": "正确答案是C。北京市与上海市之间的直线距离约为1068公里。",
    "answer_structured": {
      "type": "option",
      "value": "C",
      "distance_km": 1068,
      "explanation": "北京与上海的直线距离约为1068公里"
    },
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "北京市与上海市的直线距离约为___公里。",
    "answer": "1068公里",
    "answer_structured": {
      "type": "keyword",
      "value": "1068",
      "explanation": "北京与上海的直线距离约为1068公里"
    },
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请说明北京市和上海市之间的直线距离是多少公里。",
    "answer": "北京市与上海市之间的直线距离约为1068公里。这个距离是指两地质心之间的最短空间距离，实际交通距离会因路线不同而更长。",
    "answer_structured": {
      "type": "free_text",
      "distance_km": 1068,
      "explanation": "北京市与上海市质心之间的直线距离约为1068公里"
    },
    "difficulty": "easy"
  }
}
```

### 示例2：武汉-长沙

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
    "distance_km": 296
  },
  "difficulty": "medium"
}
```

**输出：**

```json
{
  "true_false": {
    "question": "武汉和长沙的直线距离大约在300公里左右。",
    "answer": "正确。武汉市与长沙市之间的直线距离约为296公里，确实在300公里左右。",
    "answer_structured": {
      "type": "boolean",
      "value": true,
      "distance_km": 296,
      "explanation": "武汉与长沙的直线距离约为296公里"
    },
    "difficulty": "medium"
  },
  "choice": {
    "question": "小李要从武汉驾车前往长沙出差，他想了解两地之间的直线距离。以下哪个数据最接近实际？",
    "options": {"A": "约150公里", "B": "约296公里", "C": "约450公里", "D": "约900公里"},
    "answer": "正确答案是B。武汉市与长沙市之间的直线距离约为296公里。",
    "answer_structured": {
      "type": "option",
      "value": "B",
      "distance_km": 296,
      "explanation": "武汉与长沙的直线距离约为296公里"
    },
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "若乘坐飞机从武汉飞往长沙，直线航程约为___公里。",
    "answer": "296公里",
    "answer_structured": {
      "type": "keyword",
      "value": "296",
      "explanation": "武汉与长沙的直线航程约为296公里"
    },
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "武汉市和长沙市的直线距离约为多少？请将这个距离与你熟悉的一个城市间距离进行比较，帮助理解其远近程度。",
    "answer": "武汉市与长沙市之间的直线距离约为296公里。这个距离大约相当于北京到济南的直线距离，开车大约需要3-4小时，乘坐高铁则更快。两座城市同属长江中游城市群，距离相对较近。",
    "answer_structured": {
      "type": "free_text",
      "distance_km": 296,
      "explanation": "武汉与长沙的直线距离约为296公里，相当于北京到济南的距离"
    },
    "difficulty": "medium"
  }
}
```
