# 拓扑包含关系（正例）题目生成模板

你是一个地理空间推理数据集生成专家。你的任务是根据PostGIS精确计算的空间事实，为每对地理实体生成4种类型的自然语言题目。

【核心约束】
1. 你不做任何空间计算。所有事实已由PostGIS精确计算并给出。
2. answer_structured必须从spatial_facts直接派生，不得修改任何数值。
3. answer的自然语言表达必须与answer_structured完全一致。
4. 4道题目的提问风格必须各不相同。
5. 输出严格为JSON，不要添加任何额外文本。

## 特化角色

你当前专注于生成**拓扑包含关系（正例）**的题目。正例意味着实体A确实包含实体B，空间事实中 `contains` 为 `true`。你需要围绕"包含"这一真关系，设计4种不同风格的自然语言题目。

## 任务说明

给定一对地理实体A和B，以及PostGIS计算的空间事实 `{"contains": true}`，生成4种题型的自然语言题目：
- 题型1：判断题（是非题）
- 题型2：选择题（单选）
- 题型3：填空题
- 题型4：简答题/推理题

所有题目都必须测试"A是否包含B"这一空间关系，且正确答案为"是"。

## 输入数据格式

```
实体A: {"name_zh": "{{entity_a_name}}", "centroid": {{entity_a_centroid}}, "type": "{{entity_a_type}}"}
实体B: {"name_zh": "{{entity_b_name}}", "centroid": {{entity_b_centroid}}, "type": "{{entity_b_type}}"}
空间事实: {"contains": true}
难度: {{difficulty}}
```

## 输出格式要求

输出严格的JSON，结构如下：

```json
{
  "true_false": {
    "question": "...",
    "answer": "正确/错误",
    "answer_structured": {"type": "boolean", "value": true, "contains": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "choice": {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A/B/C/D",
    "answer_structured": {"type": "option", "value": "A", "contains": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "fill_blank": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "keyword", "value": "...", "contains": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  },
  "open_qa": {
    "question": "...",
    "answer": "...",
    "answer_structured": {"type": "free_text", "contains": true, "explanation": "..."},
    "difficulty": "easy/medium/hard"
  }
}
```

## 生成约束

1. **事实一致性**：所有答案必须严格基于 `spatial_facts: {"contains": true}`。不得编造任何空间信息。
2. **多样性自然语言**：
   - 判断题：用不同句式提问，如"是否包含"、"是否覆盖"、"是否完全涵盖"等。
   - 选择题：选项设计应包含干扰项，但正确答案唯一。
   - 填空题：挖空部分应考察空间关系知识。
   - 简答题：要求解释或推理，鼓励结合地理常识。
3. **难度适配**：根据 `{{difficulty}}` 调整题目复杂度：
   - easy：直接问包含关系
   - medium：需要结合地理背景理解
   - hard：需要多步推理或结合多种空间概念
4. **提问风格差异化**：4道题目的提问风格、措辞方式、考察角度必须明显不同。

## 示例

### 示例1

**输入：**
```
实体A: {"name_zh": "湖北省", "centroid": [112.29, 30.99], "type": "province"}
实体B: {"name_zh": "武汉市", "centroid": [114.30, 30.59], "type": "city"}
空间事实: {"contains": true}
难度: easy
```

**输出：**
```json
{
  "true_false": {
    "question": "湖北省的行政区域范围是否完全覆盖了武汉市？",
    "answer": "正确。根据PostGIS空间计算，湖北省包含武汉市，即武汉市完全位于湖北省的行政区域范围内。",
    "answer_structured": {"type": "boolean", "value": true, "contains": true, "explanation": "湖北省作为省级行政区，其Polygon几何范围包含武汉市的Polygon几何范围"},
    "difficulty": "easy"
  },
  "choice": {
    "question": "关于武汉市与湖北省的空间关系，以下哪个说法是正确的？",
    "options": {"A": "武汉市与湖北省相邻但不重叠", "B": "湖北省包含武汉市", "C": "武汉市与湖北省完全分离", "D": "武汉市与湖北省仅边界接触"},
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "contains": true, "explanation": "ST_Contains(湖北省, 武汉市) = true，武汉市几何范围在湖北省几何范围内部"},
    "difficulty": "easy"
  },
  "fill_blank": {
    "question": "武汉市作为省会城市，其行政区域被______省的行政区域完全包含。",
    "answer": "湖北",
    "answer_structured": {"type": "keyword", "value": "湖北", "contains": true, "explanation": "湖北省的空间范围完全包含武汉市的空间范围"},
    "difficulty": "easy"
  },
  "open_qa": {
    "question": "请从空间包含关系的角度解释为什么说武汉市属于湖北省管辖。",
    "answer": "从空间拓扑关系来看，湖北省的行政区域Polygon几何范围完全包含武汉市的行政区域Polygon几何范围（ST_Contains = true）。这意味着武汉市的所有领土范围都落在湖北省的边界之内，这是行政区划上武汉市归属湖北省管辖的地理空间基础。",
    "answer_structured": {"type": "free_text", "contains": true, "explanation": "湖北省几何范围包含武汉市几何范围，武汉完全在湖北省内部"},
    "difficulty": "easy"
  }
}
```

### 示例2

**输入：**
```
实体A: {"name_zh": "中国", "centroid": [104.19, 35.86], "type": "country"}
实体B: {"name_zh": "四川省", "centroid": [102.70, 30.57], "type": "province"}
空间事实: {"contains": true}
难度: medium
```

**输出：**
```json
{
  "true_false": {
    "question": "从空间拓扑角度来看，中国的领土范围是否完全覆盖了四川省的全部辖区？",
    "answer": "正确。中国领土的几何范围完全覆盖四川省辖区，四川省作为中国的一个省级行政区，其全部空间范围都在中国国境线以内。",
    "answer_structured": {"type": "boolean", "value": true, "contains": true, "explanation": "中国的Polygon几何完全包含四川省的Polygon几何"},
    "difficulty": "medium"
  },
  "choice": {
    "question": "假设在GIS系统中对中国和四川省进行空间叠加分析，以下哪种拓扑关系描述是准确的？",
    "options": {"A": "两者互不相干，空间上完全分离", "B": "中国的空间范围包含四川省的空间范围", "C": "四川省与中国仅有边界接触", "D": "四川省穿越了中国"},
    "answer": "B",
    "answer_structured": {"type": "option", "value": "B", "contains": true, "explanation": "ST_Contains计算确认包含关系为真"},
    "difficulty": "medium"
  },
  "fill_blank": {
    "question": "在空间数据库中执行ST_Contains(中国, 四川省)的查询，返回结果为______，表明两实体之间存在拓扑包含关系。",
    "answer": "true（真）",
    "answer_structured": {"type": "keyword", "value": "true（真）", "contains": true, "explanation": "PostGIS计算确认中国几何范围包含四川省几何范围"},
    "difficulty": "medium"
  },
  "open_qa": {
    "question": "在地理信息系统（GIS）中，'包含'（Contains）是一个重要的空间拓扑关系。请结合中国与四川省的关系，阐述这一概念。",
    "answer": "在GIS中，ST_Contains(A, B)为true表示A的几何范围完全包含B的几何范围，且B的内部与A的内部有交集但不与A的边界接触。就中国与四川省而言，中国的国境线Polygon完全包围四川省的行政区域Polygon，四川省的全部辖区都落在中国领土范围内，没有任何部分溢出。这种关系体现了国家与省级行政区之间的空间层级关系。",
    "answer_structured": {"type": "free_text", "contains": true, "explanation": "中国完全包含四川，体现了国家-省的空间层级"},
    "difficulty": "medium"
  }
}
```
