# 拓扑分离关系（正例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑分离关系（正例）**的题目。正例意味着实体A和实体B完全分离（无交集），空间事实中 `disjoint` 为 `true`。你需要围绕"A和B完全分离"这一真关系，设计4种不同风格的自然语言题目。

### 概念说明
- `disjoint` 在PostGIS中表示两个几何体之间没有任何空间交集——既不相邻（touches），也不包含（contains），也不穿越（crosses），也没有任何重叠（overlaps）。
- 两个分离的实体之间被其他实体或空间隔开。
- disjoint是所有空间关系中最"远"的关系。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"disjoint": true}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须测试"A和B是否完全分离"这一空间关系，且正确答案为"是"。

## 输入数据格式

```
实体A: {"name_zh": "桂林市", "centroid": [110.5181, 25.3523], "type": "city"}
实体B: {"name_zh": "九江市", "centroid": [115.4567, 29.3191], "type": "city"}
空间事实: {"disjoint": true}
难度: easy
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"type": "boolean", "value": true, "disjoint": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"type": "option", "value": "A", "disjoint": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "keyword", "value": "...", "disjoint": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "free_text", "disjoint": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  }
}
```

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"disjoint": true}`。不得编造任何空间信息。
2. **多样性自然语言**：
   - 判断题：用不同句式提问，如"是否完全分离"、"是否没有任何空间交集"、"是否互不相邻"等。
   - 选择题：选项设计应包含干扰项，但正确答案唯一。
   - 填空题：挖空部分应考察空间关系知识。
   - 简答题：要求解释或推理，鼓励结合地理常识。
3. **难度适配**：根据 `easy` 调整题目复杂度：
   - easy：直接问分离关系
   - medium：需要结合地理背景理解
   - hard：需要多步推理或结合多种空间概念
4. **提问风格差异化**：4道题目的提问风格、措辞方式、考察角度必须明显不同。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "北京市", "centroid": [116.41, 39.90], "type": "city"}
实体B: {"name_zh": "上海市", "centroid": [121.47, 31.23], "type": "city"}
空间事实: {"disjoint": true}
难度: easy
```

**输出：**
```json
{
  "true_false": {
    "question": "北京市和上海市在空间上是否完全分离，没有任何行政区域上的交集？",
    "answer": "正确。北京市和上海市在空间上完全分离，ST_Disjoint(北京市, 上海市) = true。两市之间隔着河北省、天津市、山东省、江苏省等多个行政区域。",
    "answer_structured": {"type": "boolean", "value": true, "disjoint": true, "explanation": "北京和上海的Polygon没有任何空间交集，中间隔有多个省份"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于北京市和上海市的空间关系，以下哪个说法是正确的？",
    "options": {"A": "两市相邻接壤", "B": "两市完全分离，中间隔有其他行政区", "C": "上海市包含北京市", "D": "北京市包含上海市"},
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "disjoint": true, "explanation": "北京上海空间分离，无任何交集"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "北京市和上海市虽然都是直辖市，但两城市在空间上完全______，中间隔有多个省份。",
    "answer": "分离（disjoint）",
    "answer_structured": {"type": "keyword", "value": "分离（disjoint）", "disjoint": true, "explanation": "两市空间完全分离"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "北京市和上海市都是中国的直辖市，请从空间拓扑的角度分析它们之间的关系，并说明disjoint关系的判定标准。",
    "answer": "在空间拓扑中，ST_Disjoint(A, B) = true表示A和B的几何体没有任何交集——包括内部、边界和外部都没有接触。对于北京市和上海市，两个城市的Polygon几何之间既不相邻(touches=false)、也不互相包含(contains=false/within=false)、也不重叠(overlaps=false)，完全满足disjoint的条件。两市分别位于华北平原和长江三角洲，中间隔有河北、天津、山东、江苏等省市，直线距离约1000公里。这表明'同级别行政区划'(都是直辖市)并不意味着空间上必然相邻或有交集。",
    "answer_structured": {"type": "free_text", "disjoint": true, "explanation": "北京上海无任何空间交集，完全分离"},
    "difficulty": "easy"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "新疆维吾尔自治区", "centroid": [87.63, 43.79], "type": "province"}
实体B: {"name_zh": "海南省", "centroid": [109.75, 19.20], "type": "province"}
空间事实: {"disjoint": true}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "新疆维吾尔自治区和海南省分别位于中国的西北和最南端，两省区之间是否存在任何空间交集？",
    "answer": "正确，两省区之间不存在任何空间交集。ST_Disjoint(新疆维吾尔自治区, 海南省) = true，它们在空间上完全分离。",
    "answer_structured": {"type": "boolean", "value": true, "disjoint": true, "explanation": "新疆在西北内陆，海南在南部海岛，空间上完全分离"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "新疆和海南是中国陆地面积最大和最小的省级行政区，关于它们的空间关系，以下哪个正确？",
    "options": {"A": "两省区相邻接壤", "B": "两省区完全分离，中间隔有多个省份", "C": "海南省被新疆包含", "D": "两省区有部分区域重叠"},
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "disjoint": true, "explanation": "新疆和海南空间分离，距离遥远"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "新疆和海南虽然都是省级行政区，但新疆位于西北内陆，海南位于南海之中，两者在空间上完全______。",
    "answer": "分离（无交集）",
    "answer_structured": {"type": "keyword", "value": "分离（无交集）", "disjoint": true, "explanation": "新疆和海南在空间上完全分离"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "新疆是中国面积最大的省级行政区，海南是中国最小的省级行政区（陆地面积）。请从空间角度分析为什么这两个极端在拓扑上是分离关系，并思考在什么情况下两个省级行政区不可能满足disjoint条件。",
    "answer": "新疆和海南满足ST_Disjoint = true的原因很明显：新疆位于中国西北边陲（质心约87.63E, 43.79N），海南是中国南部的海岛省份（质心约109.75E, 19.20N），两省区之间不仅隔着甘肃、青海、四川、贵州、广西等多个省区，还跨越了数千公里的距离。它们的空间范围没有任何重叠、接触或包含关系。两个省级行政区不可能满足disjoint条件的情况是：当它们相邻接壤时(touches=true)，或一方包含另一方时(contains=true/within=true)，或两者有重叠区域时(overlaps=true)。在中国省级行政区划中，大部分相邻省份之间都是touches关系，不满足disjoint条件。",
    "answer_structured": {"type": "free_text", "disjoint": true, "explanation": "新疆和海南距离遥远，中间隔多个省份，完全分离"},
    "difficulty": "medium"
  }
}
```
