# Hibiki 原始数据分析报告

生成时间: 2026-03-09
数据源目录: `C:/Users/60207/Documents/hibiki works/`

---

## 1. 文件清单与统计

| 文件名 | 大小 (bytes) | 记录数 |
|--------|-------------|--------|
| generated_1000.jsonl | 2,148,929 | 1,000 |
| generated_1001_to_2000.jsonl | 1,758,591 | 974 |
| generated_2001_to_3000.jsonl | 1,738,193 | 959 |
| generated_3001_to_4000.jsonl | 1,763,313 | 983 |
| generated_4001_to_5000.jsonl | 1,824,968 | 1,000 |
| generated_5001_to_6000.jsonl | 1,821,243 | 995 |
| generated_6001_to_7000.jsonl | 1,812,273 | 999 |
| generated_7001_to_8000.jsonl | 1,795,978 | 995 |
| generated_8001_to_9000.jsonl | 1,813,497 | 1,000 |
| generated_9001_to_10000.jsonl | 1,795,239 | 995 |
| generated_10001_to_10600.jsonl | 1,083,869 | 598 |
| generated_10601_to_11200.jsonl | 1,077,992 | 594 |
| generated_11201_to_11800.jsonl | 1,069,573 | 599 |
| **总计** | **19,604,658** | **11,691** |

---

## 2. 数据格式分析

### 2.1 完整字段列表 (13个字段)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | string | 唯一标识符，格式如 `geosr_{type}_prompt_{number}_{hash}` |
| `spatial_relation_type` | string | 空间关系类型: topological/metric/directional/composite |
| `topology_subtype` | string | 拓扑子类型 (仅topological类型有) |
| `question` | string | 问题文本 |
| `answer` | string | 答案文本 |
| `reasoning_chain` | list | 推理链步骤数组 |
| `entities` | list | 实体数组 (包含name, type, coords) |
| `spatial_tokens` | list | 空间相关词汇列表 |
| `entity_to_token` | dict/object | 实体到token的映射 |
| `difficulty` | string | 难度级别: easy/medium/hard |
| `difficulty_score` | float | 难度分数 |
| `prompt_id` | string | 提示ID |
| `split` | string | 数据集划分: train/dev/test |

### 2.2 字段完整性确认

**所有用户指定的字段均存在于数据集中:**

- [x] `id` - 存在
- [x] `spatial_relation_type` - 存在
- [x] `topology_subtype` - 存在 (仅topological类型)
- [x] `question` - 存在
- [x] `answer` - 存在
- [x] `reasoning_chain` - 存在
- [x] `entities` - 存在
- [x] `spatial_tokens` - 存在
- [x] `entity_to_token` - 存在 (部分文件)
- [x] `difficulty` - 存在
- [x] `difficulty_score` - 存在
- [x] `prompt_id` - 存在 (部分文件)
- [x] `split` - 存在

---

## 3. Entities字段坐标信息确认

**所有实体的 `entities` 字段都包含坐标信息 (`coords`)**

示例结构:
```json
"entities": [
  {
    "name": "松原",
    "type": "city",
    "coords": [124.825, 45.1411]  // [经度, 纬度]
  },
  {
    "name": "阳泉",
    "type": "city",
    "coords": [113.5833, 37.8667]
  }
]
```

**坐标格式:** `[经度, 纬度]` (WGS84)

---

## 4. 数据分布统计

### 4.1 空间关系类型分布

| 类型 | 数量 | 占比 |
|------|------|------|
| topological (拓扑) | 3,260 | 27.9% |
| metric (度量) | 3,159 | 27.0% |
| directional (方向) | 2,910 | 24.9% |
| composite (复合) | 2,362 | 20.2% |

### 4.2 拓扑子类型分布 (仅topological类型)

| 子类型 | 数量 | 占比 |
|--------|------|------|
| disjoint (分离) | 2,531 | 21.6% |
| within (在...内) | 232 | 2.0% |
| contains (包含) | 226 | 1.9% |
| adjacent (相邻) | 160 | 1.4% |
| overlap (重叠) | 88 | 0.8% |
| touch (接触) | 12 | 0.1% |
| inside (内部) | 7 | 0.1% |
| crosses (交叉) | 1 | 0.0% |
| connected (连接) | 1 | 0.0% |
| separated (分离) | 1 | 0.0% |
| intersect (相交) | 1 | 0.0% |

### 4.3 难度分布

| 难度 | 数量 | 占比 |
|------|------|------|
| medium (中等) | 5,970 | 51.1% |
| easy (简单) | 3,445 | 29.5% |
| hard (困难) | 2,276 | 19.5% |

### 4.4 数据集划分分布

| 划分 | 数量 | 占比 |
|------|------|------|
| train (训练集) | 7,905 | 67.6% |
| test (测试集) | 2,986 | 25.5% |
| dev (开发集) | 800 | 6.8% |

---

## 5. 重要发现

### 5.1 字段完整性问题

1. **entity_to_token 字段不一致:**
   - `generated_1000.jsonl`: 100% 存在该字段
   - 其他所有文件: 0% 存在该字段

2. **prompt_id 字段不一致:**
   - `generated_1000.jsonl`: 0% 存在该字段
   - 其他所有文件: 100% 存在该字段

### 5.2 数据版本差异

数据集似乎来自不同的生成批次或版本:
- **V1 (generated_1000.jsonl)**: 包含 entity_to_token，缺少 prompt_id
- **V2 (其他所有文件)**: 包含 prompt_id，缺少 entity_to_token

### 5.3 推理链 (reasoning_chain) 结构

推理链包含5个步骤:
1. `entity_identification` - 实体识别
2. `spatial_relation_extraction` - 空间关系提取
3. `coordinate_retrieval` - 坐标检索
4. `spatial_calculation` - 空间计算
5. `answer_generation` - 答案生成

---

## 6. 样例数据

### 6.1 拓扑关系示例

```json
{
  "id": "geosr_topological_prompt_0001_3041",
  "spatial_relation_type": "topological",
  "topology_subtype": "contains",
  "question": "长沙市是否位于陕西省境内？",
  "answer": "长沙市不在陕西省境内，它位于湖南省境内。",
  "entities": [
    {"name": "陕西省", "type": "province", "coords": [108.9398, 34.3416]},
    {"name": "长沙", "type": "city", "coords": [112.9388, 28.2282]}
  ],
  "difficulty": "easy",
  "difficulty_score": 2.8,
  "split": "train"
}
```

### 6.2 度量关系示例

```json
{
  "id": "geosr_metric_prompt_1001_1775",
  "spatial_relation_type": "metric",
  "question": "松原和阳泉之间的直线距离是多少公里？",
  "answer": "松原与阳泉的直线距离约为1235.1公里。",
  "entities": [
    {"name": "松原", "type": "city", "coords": [124.825, 45.1411]},
    {"name": "阳泉", "type": "city", "coords": [113.5833, 37.8667]}
  ],
  "difficulty": "easy",
  "prompt_id": "prompt_1001",
  "split": "train"
}
```

### 6.3 方向关系示例

```json
{
  "id": "geosr_directional_prompt_1002_3634",
  "spatial_relation_type": "directional",
  "question": "相对于丽江，南阳位于什么方向？",
  "answer": "南阳位于丽江的东南方向。",
  "entities": [
    {"name": "丽江", "type": "city", "coords": [100.227, 26.8558]},
    {"name": "南阳", "type": "city", "coords": [112.5286, 33.0039]}
  ],
  "difficulty": "easy",
  "prompt_id": "prompt_1002",
  "split": "train"
}
```

---

## 7. 建议与注意事项

1. **字段标准化**: 在合并数据时需要处理 entity_to_token 和 prompt_id 字段的不一致性
2. **坐标验证**: 所有实体都包含坐标，可用于生成带/不带坐标的数据版本
3. **拓扑子类型**: disjoint 类型占主导 (21.6%)，在采样时可能需要平衡
4. **数据集划分**: 现有划分可能需要重新划分以符合项目需求
5. **ID格式**: ID包含空间关系类型信息，可用于按类型筛选数据
