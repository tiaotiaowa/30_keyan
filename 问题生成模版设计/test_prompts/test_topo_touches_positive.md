# 拓扑相邻关系（正例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑相邻关系（正例）**的题目。正例意味着实体A和实体B共享边界（相邻接壤），空间事实中 `touches` 为 `true`。你需要围绕"A和B相邻"这一真关系，设计4种不同风格的自然语言题目。

### 概念说明
- `touches` 在PostGIS中表示两个几何体的边界有接触，但内部不相交。
- 对于两个Polygon，这意味着它们共享边界线段（相邻接壤）但互不包含。
- 对于Point和Polygon，Point恰好落在Polygon的边界上。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"touches": true}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须测试"A和B是否相邻接壤"这一空间关系，且正确答案为"是"。

## 输入数据格式

```
实体A: {"name_zh": "丰台区", "centroid": [116.2504, 39.8357], "type": "city"}
实体B: {"name_zh": "朝阳区", "centroid": [116.5153, 39.9535], "type": "city"}
空间事实: {"touches": true}
难度: easy
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"type": "boolean", "value": true, "touches": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"type": "option", "value": "A", "touches": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "keyword", "value": "...", "touches": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "free_text", "touches": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  }
}
```

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"touches": true}`。不得编造任何空间信息。
2. **多样性自然语言**：
   - 判断题：用不同句式提问，如"是否相邻接壤"、"是否共享边界"、"是否是邻省/邻市"等。
   - 选择题：选项设计应包含干扰项，但正确答案唯一。
   - 填空题：挖空部分应考察空间关系知识。
   - 简答题：要求解释或推理，鼓励结合地理常识。
3. **难度适配**：根据 `easy` 调整题目复杂度：
   - easy：直接问相邻关系
   - medium：需要结合地理背景理解
   - hard：需要多步推理或结合多种空间概念
4. **提问风格差异化**：4道题目的提问风格、措辞方式、考察角度必须明显不同。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "河北省", "centroid": [114.48, 38.04], "type": "province"}
实体B: {"name_zh": "山东省", "centroid": [117.00, 36.67], "type": "province"}
空间事实: {"touches": true}
难度: easy
```

**输出：**
```json
{
  "true_false": {
    "question": "河北省与山东省是否在地理上相邻接壤？",
    "answer": "正确。河北省与山东省共享行政边界，两省在空间上是相邻的。ST_Touches(河北省, 山东省) = true。",
    "answer_structured": {"type": "boolean", "value": true, "touches": true, "explanation": "河北省和山东省的Polygon共享边界线段，相邻关系成立"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于河北省与山东省的空间关系，以下哪个说法正确？",
    "options": {"A": "两省完全分离，没有共同边界", "B": "两省相邻接壤，共享行政边界", "C": "山东省完全包含河北省", "D": "河北省完全包含山东省"},
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "touches": true, "explanation": "两省Polygon边界接触，内部不重叠"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "河北省南部与______省相邻接壤，两省共享行政边界线。",
    "answer": "山东",
    "answer_structured": {"type": "keyword", "value": "山东", "touches": true, "explanation": "河北与山东共享边界，touches关系为真"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "在PostGIS中，ST_Touches函数是如何判定两个面状实体相邻的？请结合河北省和山东省的例子说明。",
    "answer": "在PostGIS中，ST_Touches(A, B)判断两个几何体的边界是否有接触而内部不相交。对于河北省和山东省两个Polygon，它们各自的边界线在某个区段上重合（即共享边界线段），但河北省的内部区域与山东省的内部区域没有重叠。因此ST_Touches(河北省, 山东省) = true，表明两省是相邻接壤关系而非互相包含或完全分离。",
    "answer_structured": {"type": "free_text", "touches": true, "explanation": "边界接触但内部不重叠，典型的相邻关系"},
    "difficulty": "easy"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "四川省", "centroid": [102.70, 30.57], "type": "province"}
实体B: {"name_zh": "甘肃省", "centroid": [103.83, 36.06], "type": "province"}
空间事实: {"touches": true}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "四川省与甘肃省虽然在地图上看似距离较远，但实际上它们是共享边界的相邻省份。这一说法正确吗？",
    "answer": "正确。虽然四川省和甘肃省的核心区域相距较远，但四川省的北部（阿坝州一带）与甘肃省的南部边界确实相接，两省共享行政边界。ST_Touches(四川省, 甘肃省) = true。",
    "answer_structured": {"type": "boolean", "value": true, "touches": true, "explanation": "四川北部与甘肃南部边界相接，touches关系成立"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "在中国西部省份中，以下哪一对省份之间存在直接的行政边界接壤关系？",
    "options": {"A": "四川省与甘肃省", "B": "四川省与新疆维吾尔自治区", "C": "四川省与西藏自治区", "D": "甘肃省与云南省"},
    "answer": "A",
    "answer_structured": {"type": "option", "value": "A", "touches": true, "explanation": "四川和甘肃的Polygon边界有接触"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "四川省不仅与云南、贵州等南方省份相邻，其北部还与______省共享行政边界。",
    "answer": "甘肃",
    "answer_structured": {"type": "keyword", "value": "甘肃", "touches": true, "explanation": "四川北部与甘肃南部边界相接"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "很多人只知道四川与重庆、云南、贵州相邻，却不了解四川还与甘肃接壤。请从GIS空间分析的角度，解释如何验证这种不太直观的相邻关系。",
    "answer": "验证两省是否相邻，最可靠的方法是进行空间拓扑计算。在PostGIS中，使用ST_Touches(四川省, 甘肃省)函数，系统会精确计算两个Polygon几何的边界是否有交集。如果返回true，则说明两省确实共享边界。在本例中，四川省北部的阿坝藏族羌族自治州区域与甘肃省南部的行政边界确实相接，尽管两省的质心距离较远，但边界线段存在重叠，因此touches关系为真。这体现了GIS精确计算优于主观直觉判断的优势。",
    "answer_structured": {"type": "free_text", "touches": true, "explanation": "GIS精确计算可验证非直观的相邻关系，四川甘肃确实边界相接"},
    "difficulty": "medium"
  }
}
```
