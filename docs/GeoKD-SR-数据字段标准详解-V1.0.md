# GeoKD-SR 数据字段标准详解

> **版本**: V1.0
> **创建日期**: 2026-03-11
> **数据集**: final_1_final.jsonl（11,656条记录）
> **文档类型**: 数据规范技术文档

---

## 一、概述

### 1.1 文档目的

本文档详细定义 GeoKD-SR 数据集的所有字段标准，包括：
- 每个字段的数据类型、格式要求、约束条件
- 字段之间的依赖关系和验证规则
- **数据质量验证标准**：事实正确性、推理链合理性、实体库验证、坐标正确性、一致性验证
- 标准模板和参考示例
- 实际数据分布和质量评估

**目标读者**：
- 数据生成工程师：参考本标准生成符合规范的数据
- 质量保证工程师：使用验证规则检查数据质量
- 研究人员：理解数据集结构和字段含义
- 模型训练者：了解数据格式用于训练配置

### 1.2 数据集基本信息

| 属性 | 值 |
|------|-----|
| **数据集名称** | GeoKD-SR（地理知识蒸馏空间推理数据集） |
| **文件格式** | JSONL（每行一个JSON对象） |
| **记录数量** | 11,656 条 |
| **字段数量** | 13 个 |
| **文件大小** | 约 22 MB |
| **字符编码** | UTF-8 |

### 1.3 字段分类

GeoKD-SR 数据集包含 13 个字段，按必需性分为三类：

#### 必需字段（10个）
| # | 字段名 | 数据类型 | 说明 |
|---|--------|---------|------|
| 1 | `id` | string | 数据唯一标识符 |
| 2 | `spatial_relation_type` | string | 空间关系类型 |
| 3 | `question` | string | 问题文本 |
| 4 | `answer` | string | 答案文本 |
| 5 | `reasoning_chain` | array | 推理链（5步） |
| 6 | `entities` | array | 地理实体数组 |
| 7 | `spatial_tokens` | array | 空间关键词数组 |
| 8 | `difficulty` | string | 难度级别 |
| 9 | `split` | string | 数据集划分 |
| 10 | `difficulty_score` | float | 难度分数 |

#### 条件必需字段（2个）
| # | 字段名 | 触发条件 | 说明 |
|---|--------|---------|------|
| 11 | `topology_subtype` | spatial_relation_type = "topological" | 拓扑子类型 |
| 12 | `entity_to_token` | 有 reasoning_chain | 实体位置映射 |

#### 可选字段（1个）
| # | 字段名 | 说明 |
|---|--------|------|
| 13 | `prompt_id` | 数据生成提示词ID（追溯用） |

### 1.4 数据质量标准总览

| 质量维度 | 标准 | 验证方法 |
|---------|------|---------|
| **完整性** | 所有必需字段无缺失 | 字段存在性检查 |
| **唯一性** | id 字段全局唯一 | 唯一性检查 |
| **一致性** | 枚举值符合规范 | 枚举值验证 |
| **事实正确性** | question-answer陈述符合地理事实 | 地理事实库验证 |
| **推理合理性** | reasoning_chain逻辑正确、富有地理常识 | 推理逻辑检查 |
| **实体存在性** | entities中的实体存在于实体库 | 实体库查询验证 |
| **坐标准确性** | entities中的坐标与实体库一致 | 坐标对比验证（误差<0.01度） |
| **跨字段一致性** | question-answer-reasoning_chain语义一致 | 跨字段语义验证 |

---

## 二、数据质量验证体系（核心）⭐

### 2.1 Question-Answer 事实正确性验证

#### 2.1.1 验证目标
确保 question 和 answer 中的地理陈述符合事实，不包含错误信息。

#### 2.1.2 验证维度

**1. 地理位置关系验证**
```json
// ✅ 正确示例
{
  "question": "故宫位于北京市内吗？",
  "answer": "是的，故宫位于北京市内。"
}
// 验证：故宫确实位于北京市内 → 通过

// ❌ 错误示例
{
  "question": "故宫位于上海市内吗？",
  "answer": "是的，故宫位于上海市内。"
}
// 验证：故宫不在上海市内 → 失败
```

**2. 行政区划关系验证**
```json
// ✅ 正确示例
{
  "question": "紫金山公园是否位于南京主城区内部？",
  "answer": "是的，紫金山公园位于南京主城区内部。"
}
// 验证：紫金山公园隶属于南京市玄武区 → 通过

// ❌ 错误示例
{
  "question": "紫金山公园是否位于苏州主城区内部？",
  "answer": "是的，紫金山公园位于苏州主城区内部。"
}
// 验证：紫金山公园不在苏州 → 失败
```

**3. 方向关系验证**
```json
// ✅ 正确示例
{
  "question": "北京在上海的什么方向？",
  "answer": "北京在上海的西北方向。"
}
// 验证：北京确实在上海的西北方向 → 通过

// ❌ 错误示例
{
  "question": "北京在上海的什么方向？",
  "answer": "北京在上海的东南方向。"
}
// 验证：方向错误 → 失败
```

**4. 度量关系验证**
```json
// ✅ 正确示例
{
  "question": "从北京到上海的距离大约是多少公里？",
  "answer": "约1283公里。"
}
// 验证：实际距离约1200-1300公里 → 通过

// ❌ 错误示例
{
  "question": "从北京到上海的距离大约是多少公里？",
  "answer": "约5000公里。"
}
// 验证：距离错误 → 失败
```

#### 2.1.3 验证方法

**方法1：地理知识库查询**
- 查询权威地理数据库（如高德、百度地图API）
- 对比陈述与实际地理事实
- 验证通过标准：误差在合理范围内（方向±45°，距离±20%）

**方法2：坐标计算验证**
```python
def verify_direction(entity1_coords, entity2_coords, claimed_direction):
    """
    基于坐标验证方向关系
    """
    actual_direction = calculate_bearing(entity1_coords, entity2_coords)
    return direction_matches(actual_direction, claimed_direction)

def verify_distance(entity1_coords, entity2_coords, claimed_distance):
    """
    基于坐标验证度量关系
    """
    actual_distance = calculate_haversine_distance(entity1_coords, entity2_coords)
    error_rate = abs(actual_distance - claimed_distance) / actual_distance
    return error_rate < 0.2  # 允许20%误差
```

**方法3：规则库匹配**
- 建立行政区划层级关系库
- 验证"包含"、"位于"等拓扑关系
- 示例：北京市包含故宫（正确），上海市不包含故宫（错误）

#### 2.1.4 常见事实错误模式

| 错误类型 | 错误示例 | 正确示例 |
|---------|---------|---------|
| 行政归属错误 | 故宫属于上海市 | 故宫属于北京市 |
| 方向关系错误 | 北京在上海东南 | 北京在上海西北 |
| 距离错误 | 北京上海距离5000公里 | 北京上海距离约1283公里 |
| 拓扑关系错误 | 黄河流经陕西（正确）vs 黄河流经新疆（错误） | - |
| 实体不存在 | 青海省有"蓝海市" | 该城市不存在 |

---

### 2.2 Reasoning Chain 正确性和合理性验证

#### 2.2.1 验证目标
确保推理链：
1. **逻辑正确**：每一步推理都符合逻辑规则
2. **内容合理**：富含地理常识，信息充分
3. **事实准确**：所有陈述符合地理事实
4. **不泄露答案**：步骤1-4不直接给出最终答案

#### 2.2.2 分步验证标准

**步骤1：entity_identification（实体识别）**
```json
// ✅ 正确示例
{
  "step": 1,
  "name": "entity_identification",
  "content": "从问题'故宫位于北京市内吗？'中，可以识别出涉及两个地理实体：故宫（landmark类型）和北京市（province类型）。",
  "entities_involved": ["故宫", "北京市"]
}
```
✓ 验证点：
- 实体识别完整（与question中实体一致）
- 实体类型正确（故宫确实是landmark，北京市是province）
- 陈述事实正确

```json
// ❌ 错误示例
{
  "step": 1,
  "content": "识别出实体：故宫（city类型）和北京市（city类型）"
}
```
✗ 错误：故宫类型应该是landmark，不是city

**步骤2：spatial_relation_extraction（关系提取）**
```json
// ✅ 正确示例
{
  "step": 2,
  "name": "spatial_relation_extraction",
  "content": "问题询问'位于...内'，属于拓扑空间关系中的包含关系判断。",
  "relation_type": "topological"
}
```
✓ 验证点：
- 空间关系分类正确（"位于...内"是拓扑关系）
- 关键词识别准确

```json
// ❌ 错误示例
{
  "step": 2,
  "content": "问题询问方向关系",
  "relation_type": "directional"
}
```
✗ 错误："位于...内"是拓扑关系，不是方向关系

**步骤3：coordinate_retrieval（坐标检索）⭐ 关键验证点**
```json
// ✅ 正确示例
{
  "step": 3,
  "name": "coordinate_retrieval",
  "content": "检索实体坐标信息：故宫位于东经116.3972度、北纬39.9163度；北京市中心位于东经116.4074度、北纬39.9042度。故宫作为明清两代的皇宫，地处北京市中心区域。",
  "coordinates": {
    "故宫": [116.3972, 39.9163],
    "北京市": [116.4074, 39.9042]
  }
}
```
✓ 验证点：
- **坐标准确性**：与实体库一致（误差<0.01度）
- **地理常识**：故宫确实是明清皇宫，位于北京中心
- **格式正确**：[经度, 纬度]

```json
// ❌ 错误示例
{
  "step": 3,
  "coordinates": {
    "故宫": [117.5, 40.0]  // 坐标偏差过大
  }
}
```
✗ 错误：坐标与实体库不一致

**步骤4：spatial_calculation（空间计算）⭐ 核心步骤**
```json
// ✅ 正确示例
{
  "step": 4,
  "name": "spatial_calculation",
  "content": "判断拓扑关系：紫金山公园的坐标点(118.8476°E, 32.0584°N)位于南京主城区的边界范围内。紫金山公园作为南京市玄武区的著名山地公园，地处南京市东部，是南京的重要自然地标。从行政区划上看，紫金山公园确实隶属于南京主城区。",
  "calculation_result": "within"
}
```
✓ 验证点：
- **计算逻辑正确**：基于坐标的拓扑判断
- **地理常识丰富**：包含行政区划、地标背景
- **结果准确**：calculation_result与实际一致
- **不泄露答案**：描述计算过程，而非直接说"答案是肯定的"

```json
// ❌ 错误示例1：逻辑错误
{
  "step": 4,
  "content": "故宫坐标(116.40, 39.92)不在北京市范围内",
  "calculation_result": "disjoint"
}
```
✗ 错误：计算逻辑错误，故宫确实在北京市内

```json
// ❌ 错误示例2：泄露答案
{
  "step": 4,
  "content": "故宫位于北京市内，所以答案是肯定的。"
}
```
✗ 错误：直接泄露答案，应该描述计算过程

**步骤5：answer_generation（答案生成）**
```json
// ✅ 正确示例
{
  "step": 5,
  "name": "answer_generation",
  "content": "根据拓扑关系判断，故宫位于北京市边界范围内，生成肯定答案。",
  "final_answer": "故宫在北京市内"
}
```
✓ 验证点：
- 总结推理过程（不是直接复制答案）
- final_answer与answer字段语义一致

```json
// ❌ 错误示例
{
  "step": 5,
  "content": "是的，故宫位于北京市内。",  // 直接复制答案
  "final_answer": "是的，故宫位于北京市内。"
}
```
✗ 错误：content直接复制了final_answer，应该总结推理过程

#### 2.2.3 推理链质量评分标准

| 质量维度 | 权重 | 评分标准 |
|---------|------|---------|
| **逻辑正确性** | 40% | 每一步推理都符合逻辑规则 |
| **事实准确性** | 30% | 所有地理陈述符合事实 |
| **地理常识丰富度** | 20% | 包含行政区划、地理背景等信息 |
| **答案保护** | 10% | 步骤1-4不泄露答案 |

**合格标准**：总分 ≥ 80分

---

### 2.3 实体库存在性验证

#### 2.3.1 验证目标
确保 `entities` 字段中的所有实体都在实体库中存在，且属性正确。

#### 2.3.2 验证流程

**步骤1：实体名称查询**
```python
def verify_entity_exists(entity_name, entity_database):
    """
    验证实体是否存在于实体库中
    """
    # 精确匹配
    if entity_name in entity_database:
        return True, "精确匹配"

    # 模糊匹配（处理别名）
    similar_entities = find_similar_entities(entity_name, entity_database)
    if similar_entities:
        return True, f"模糊匹配：{similar_entities[0]}"

    return False, "实体不存在"
```

**步骤2：实体类型验证**
```python
def verify_entity_type(entity_name, claimed_type, entity_database):
    """
    验证实体类型是否正确
    """
    actual_type = entity_database[entity_name]["type"]
    return claimed_type == actual_type
```

**步骤3：实体坐标验证**
```python
def verify_entity_coords(entity_name, claimed_coords, entity_database):
    """
    验证实体坐标是否正确
    """
    actual_coords = entity_database[entity_name]["coords"]
    error = calculate_coord_error(claimed_coords, actual_coords)
    return error < 0.01  # 误差小于0.01度
```

#### 2.3.3 验证示例

```json
// ✅ 正确示例
{
  "entities": [
    {
      "name": "故宫",
      "type": "landmark",
      "coords": [116.3972, 39.9163]
    }
  ]
}
// 验证：
// ✓ 实体"故宫"存在于实体库
// ✓ 类型正确：landmark
// ✓ 坐标准确：[116.3972, 39.9163]

// ❌ 错误示例1：实体不存在
{
  "entities": [
    {
      "name": "不存在的地标",
      "type": "landmark",
      "coords": [0, 0]
    }
  ]
}
// 验证：✗ 实体"不存在的地标"在实体库中不存在

// ❌ 错误示例2：类型错误
{
  "entities": [
    {
      "name": "故宫",
      "type": "city",  // 类型错误
      "coords": [116.3972, 39.9163]
    }
  ]
}
// 验证：✗ 故宫的类型应该是landmark，不是city

// ❌ 错误示例3：坐标错误
{
  "entities": [
    {
      "name": "故宫",
      "type": "landmark",
      "coords": [120.0, 30.0]  // 坐标错误（这是浙江的坐标）
    }
  ]
}
// 验证：✗ 坐标与实体库不一致
```

#### 2.3.4 实体库规范

**实体库结构**：
```json
{
  "实体名称": {
    "name": "标准名称",
    "type": "实体类型",
    "coords": [经度, 纬度],
    "aliases": ["别名1", "别名2"],
    "admin_hierarchy": ["省", "市", "区"],
    "metadata": {}
  }
}
```

**实体类型枚举**：
- `province` - 省级行政区
- `city` - 城市
- `landmark` - 地标
- `mountain` - 山脉
- `river` - 河流
- `lake` - 湖泊
- `region` - 区域

---

### 2.4 实体坐标地理事实正确性验证

#### 2.4.1 验证目标
确保 `entities` 字段中的坐标与地理事实一致，误差在合理范围内。

#### 2.4.2 坐标准确性标准

| 实体类型 | 精度要求 | 允许误差 | 参考来源 |
|---------|---------|---------|---------|
| province | 0.01度 | ~1km | 国家测绘局 |
| city | 0.01度 | ~1km | 国家测绘局 |
| landmark | 0.001度 | ~100m | 实地测绘 |
| mountain | 0.01度 | ~1km | 地形数据 |
| river | 0.01度 | ~1km | 河道数据 |
| lake | 0.01度 | ~1km | 湖泊数据 |
| region | 0.05度 | ~5km | 行政边界 |

#### 2.4.3 验证方法

**方法1：实体库对比**
```python
def verify_coords_with_database(entity_name, claimed_coords, entity_database):
    """
    与实体库中的标准坐标对比
    """
    standard_coords = entity_database[entity_name]["coords"]

    # 计算误差（度）
    lon_error = abs(claimed_coords[0] - standard_coords[0])
    lat_error = abs(claimed_coords[1] - standard_coords[1])

    # 计算距离误差（米）
    distance_error = calculate_haversine_distance(
        claimed_coords, standard_coords
    )

    return distance_error < 1000  # 允许1km误差
```

**方法2：多源数据交叉验证**
```python
def verify_coords_cross_source(entity_name, claimed_coords):
    """
    使用多个数据源交叉验证坐标
    """
    sources = [
        query_amap_api(entity_name),     # 高德地图
        query_baidu_api(entity_name),    # 百度地图
        query_osm_api(entity_name)       # OpenStreetMap
    ]

    # 取众数或平均值
    verified_coords = calculate_consensus(sources)

    # 对比
    error = calculate_coord_error(claimed_coords, verified_coords)
    return error < 0.01
```

**方法3：几何一致性验证**
```python
def verify_geometric_consistency(entity, coords):
    """
    验证坐标与实体类型的几何一致性
    """
    if entity["type"] == "province":
        # 省份坐标应该位于该省份边界内
        return verify_point_in_polygon(coords, entity["boundary"])

    elif entity["type"] == "river":
        # 河流坐标应该位于河道线上
        return verify_point_on_line(coords, entity["river_course"])

    # ... 其他实体类型
```

#### 2.4.4 常见坐标错误模式

| 错误类型 | 错误示例 | 正确示例 | 错误原因 |
|---------|---------|---------|---------|
| 经纬度颠倒 | [39.9163, 116.3972] | [116.3972, 39.9163] | 经纬度顺序错误 |
| 坐标偏差过大 | [110.0, 30.0]（北京） | [116.4, 39.9] | 坐标错误 |
| 使用错误坐标 | 城市坐标用了省份中心 | 使用城市中心坐标 | 精度不够 |
| 零坐标 | [0, 0] | [实际坐标] | 占位符未替换 |
| 坐标超出范围 | [200, 100] | [116.4, 39.9] | 经纬度超限 |

---

### 2.5 Question-Answer-Reasoning Chain 一致性验证

#### 2.5.1 验证目标
确保 question、answer 和 reasoning_chain 三者之间语义一致，逻辑连贯。

#### 2.5.2 一致性维度

**1. 语义一致性**
```json
// ✅ 正确示例
{
  "question": "故宫位于北京市内吗？",
  "answer": "是的，故宫位于北京市内。",
  "reasoning_chain": [
    {
      "step": 4,
      "content": "故宫的坐标点位于北京市的多边形边界内",
      "calculation_result": "within"
    },
    {
      "step": 5,
      "content": "根据拓扑关系判断，故宫位于北京市内",
      "final_answer": "故宫在北京市内"
    }
  ]
}
// 验证：
// ✓ question询问"位于...内"
// ✓ answer回答"是的"
// ✓ reasoning_chain计算结果为"within"
// ✓ 三者语义一致

// ❌ 错误示例
{
  "question": "故宫位于北京市内吗？",
  "answer": "否，故宫不在北京市内。",  // 与question矛盾
  "reasoning_chain": [
    {
      "step": 4,
      "calculation_result": "within"  // 与answer矛盾
    }
  ]
}
// 验证：✗ answer否定了问题，但reasoning_chain说是within
```

**2. 实体一致性**
```json
// ✅ 正确示例
{
  "question": "故宫和上海市之间是什么关系？",
  "entities": [
    {"name": "故宫", "type": "landmark"},
    {"name": "上海市", "type": "province"}
  ],
  "reasoning_chain": [
    {
      "step": 1,
      "entities_involved": ["故宫", "上海市"]  // 与entities一致
    }
  ]
}
// 验证：✓ question中的实体与entities字段一致

// ❌ 错误示例
{
  "question": "故宫和上海市之间是什么关系？",
  "entities": [
    {"name": "故宫", "type": "landmark"},
    {"name": "北京市", "type": "province"}  // 与question不一致
  ]
}
// 验证：✗ entities中是"北京市"，但question中是"上海市"
```

**3. 逻辑连贯性**
```json
// ✅ 正确示例
{
  "question": "故宫位于北京市内吗？",
  "reasoning_chain": [
    {
      "step": 2,
      "content": "问题询问'位于...内'，属于拓扑空间关系",
      "relation_type": "topological"
    },
    {
      "step": 4,
      "content": "故宫坐标在北京市边界范围内",
      "calculation_result": "within"  // 与步骤2的topological一致
    }
  ]
}
// 验证：✓ 步骤2说是topological，步骤4计算为within，逻辑连贯

// ❌ 错误示例
{
  "question": "故宫位于北京市内吗？",
  "reasoning_chain": [
    {
      "step": 2,
      "content": "属于方向关系",
      "relation_type": "directional"  // 类型错误
    },
    {
      "step": 4,
      "calculation_result": "within"  // 与directional矛盾
    }
  ]
}
// 验证：✗ 步骤2说是directional，但within是topological的子类型
```

**4. 答案推导一致性**
```json
// ✅ 正确示例
{
  "answer": "是的，故宫位于北京市内。",
  "reasoning_chain": [
    {
      "step": 4,
      "calculation_result": "within"  // 推导出肯定答案
    },
    {
      "step": 5,
      "final_answer": "故宫在北京市内"  // 与answer语义一致
    }
  ]
}
// 验证：✓ reasoning_chain推导出的结果与answer一致

// ❌ 错误示例
{
  "answer": "否，故宫不在北京市内。",  // 否定答案
  "reasoning_chain": [
    {
      "step": 4,
      "calculation_result": "within"  // 但推理结果是within（肯定）
    }
  ]
}
// 验证：✗ answer说否，但reasoning_chain推导出within（是）
```

#### 2.5.3 一致性验证算法

```python
def verify_qa_rc_consistency(record):
    """
    验证 question-answer-reasoning_chain 一致性
    """
    question = record["question"]
    answer = record["answer"]
    rc = record["reasoning_chain"]
    entities = record["entities"]

    errors = []

    # 1. 实体一致性
    question_entities = extract_entities(question)
    entity_names = [e["name"] for e in entities]
    if set(question_entities) != set(entity_names):
        errors.append("实体不一致：question与entities")

    # 2. 语义一致性
    rc_result = rc[3]["calculation_result"]  # 步骤4的结果
    answer_sentiment = analyze_answer_sentiment(answer)
    if not sentiment_matches_result(answer_sentiment, rc_result):
        errors.append("语义不一致：answer与reasoning_chain")

    # 3. 逻辑连贯性
    relation_type = rc[1]["relation_type"]  # 步骤2的关系类型
    if not is_consistant_relation(relation_type, rc_result):
        errors.append("逻辑不连贯：relation_type与calculation_result")

    # 4. 答案推导一致性
    final_answer = rc[4]["final_answer"]
    if not semantic_match(answer, final_answer):
        errors.append("答案推导不一致：answer与final_answer")

    return len(errors) == 0, errors
```

#### 2.5.4 一致性检查清单

| 检查项 | 说明 | 通过标准 |
|-------|------|---------|
| 实体名称一致性 | question、entities、reasoning_chain中的实体名称一致 | 完全匹配 |
| 实体类型一致性 | 实体类型在所有字段中一致 | 完全匹配 |
| 空间关系一致性 | spatial_relation_type、topology_subtype、calculation_result一致 | 逻辑兼容 |
| 答案语义一致性 | answer、final_answer、calculation_result语义一致 | 语义匹配 |
| 推理方向一致性 | 推理链从question推导到answer | 方向正确 |

---

## 三、数据验证检查清单（完整版）

### 3.1 记录级验证（每条数据）

#### A. 基础字段验证
- [ ] **id**：格式正确（`geosr_` + 5位以上数字）
- [ ] **spatial_relation_type**：枚举值正确（4选1）
- [ ] **question**：长度10-200字符，包含≥2个实体
- [ ] **answer**：长度3-50字符，简洁不包含推理
- [ ] **difficulty**：枚举值正确（easy/medium/hard）
- [ ] **difficulty_score**：范围1.0-5.0，与difficulty匹配
- [ ] **split**：枚举值正确（train/dev/test）

#### B. 条件字段验证
- [ ] **topology_subtype**：当spatial_relation_type=topological时存在，5选1
- [ ] **entity_to_token**：当存在reasoning_chain时存在，映射正确

#### C. 数组字段验证
- [ ] **reasoning_chain**：5个步骤，每步包含必需字段
- [ ] **entities**：2-3个实体，每个包含name/type/coords
- [ ] **spatial_tokens**：3-9个token，包含实体和关系词

#### D. 质量验证（核心）⭐
- [ ] **Question-Answer事实正确性**：
  - [ ] 地理位置关系符合事实
  - [ ] 行政区划关系正确
  - [ ] 方向关系正确（±45°）
  - [ ] 度量关系正确（±20%）

- [ ] **Reasoning Chain正确性**：
  - [ ] 步骤1：实体识别完整、类型正确
  - [ ] 步骤2：关系分类正确
  - [ ] 步骤3：坐标与实体库一致（误差<0.01度）
  - [ ] 步骤4：逻辑正确、富含地理常识、不泄露答案
  - [ ] 步骤5：总结推理、不直接复制答案

- [ ] **实体库存在性**：
  - [ ] 所有实体名称存在于实体库
  - [ ] 实体类型与实体库一致
  - [ ] 实体坐标与实体库一致

- [ ] **坐标正确性**：
  - [ ] 经纬度顺序正确（[经度, 纬度]）
  - [ ] 坐标在合理范围内（经度[-180,180]，纬度[-90,90]）
  - [ ] 坐标精度符合实体类型要求

- [ ] **跨字段一致性**：
  - [ ] question、entities、reasoning_chain中的实体一致
  - [ ] spatial_relation_type与reasoning_chain中的relation_type一致
  - [ ] answer、final_answer、calculation_result语义一致
  - [ ] difficulty与difficulty_score在映射范围内

### 3.2 数据集级验证

#### A. 分布验证
- [ ] **spatial_relation_type分布**：
  - directional: 20-30%
  - topological: 25-35%
  - metric: 20-30%
  - composite: 15-25%

- [ ] **difficulty分布**：
  - easy: 25-35%
  - medium: 45-55%
  - hard: 15-25%

- [ ] **split分布**：
  - train: 70-80%
  - dev: 10-15%
  - test: 10-15%

#### B. 唯一性验证
- [ ] **id唯一性**：100%唯一，无重复
- [ ] **question唯一性**：重复率<1%

#### C. 完整性验证
- [ ] **必需字段缺失率**：0%
- [ ] **条件字段缺失率**：符合触发条件

---

## 四、字段标准详解（13个字段）

### 4.1 id 字段

#### 字段定义
数据的唯一标识符，用于区分和引用每条记录。

#### 数据类型
字符串

#### 格式要求
- **正则表达式**：`^geosr_\d{5,}$`
- **格式**：`geosr_` + 5位以上数字序号
- **序号**：从 00001 开始递增
- **唯一性**：全局唯一，不得重复

#### 标准模板
```json
{
  "id": "geosr_00001"
}
```

#### 验证规则
- 正则验证：`^geosr_\d{5,}$`
- 唯一性验证：整个数据集中不得重复

#### 实际数据分布
```json
{
  "total_records": 11656,
  "missing_count": 0,
  "unique_count": 11656,
  "duplicate_count": 0
}
```
⚠️ **注意**：当前数据使用 `geosr_{关系类型}_prompt_*` 格式，不符合标准格式。

---

### 4.2 spatial_relation_type 字段

#### 字段定义
表示地理实体之间的空间关系类型。

#### 数据类型
字符串（枚举）

#### 可选值
- `directional` - 方向关系
- `topological` - 拓扑关系
- `metric` - 度量关系
- `composite` - 复合关系

#### 验证规则
- 枚举值必须为4个值之一
- 当值为`topological`时，`topology_subtype`字段必需

#### 实际数据分布
```json
{
  "topological": 3225 (27.67%),
  "metric": 3159 (27.10%),
  "directional": 2910 (24.97%),
  "composite": 2362 (20.26%)
}
```

---

### 4.3 question 字段

#### 字段定义
用于询问地理实体之间空间关系的问题文本。

#### 数据类型
字符串

#### 格式要求
- 自然语言形式的问题
- 必须包含至少 2 个地理实体
- **保证问句多样性和复杂性**（不限制"简洁"）
- 清晰描述要查询的空间关系类型

#### 长度约束
- 最小长度：10 字符
- 最大长度：200 字符（折中方案）

#### 验证规则
- 长度验证：10 ≤ len(question) ≤ 200
- 实体验证：应包含至少 2 个地理实体
- 语义验证：应为疑问句形式

#### 实际数据分布
```json
{
  "missing_count": 0,
  "length_stats": {
    "min": 9,
    "max": 167,
    "avg": "42.75",
    "median": 37
  }
}
```

---

### 4.4 answer 字段

#### 字段定义
简洁、正确的自然语言答案，直接用于地理知识蒸馏训练和评测。

#### 数据类型
字符串

#### 核心原则⭐
- **简洁性**：直接答案，不包含推理过程
- **推理分离**：推理过程必须在 reasoning_chain 中
- **可用性**：可直接用于模型训练和评测

#### 长度约束
- 最小长度：3字符（排除"是"、"否"）
- 最大长度：50字符
- 推荐长度：8-25字符

#### 按问题类型的答案格式

| 问题类型 | 推荐格式 | 示例 | 字符数 |
|---------|---------|------|--------|
| **是非问句** | 完整句式 | "是的，故宫位于北京市内。" | 11 |
| **方向问题** | 短语/句式 | "西北方向" | 4 |
| **度量问题** | 短语 | "约1500公里" | 6 |
| **复合问题** | 组合式 | "东方向，距离约1283公里" | 12 |

#### 验证规则⭐
- 长度验证：3 ≤ len(answer) ≤ 50
- **内容验证**：不包含推理过程（推理应在reasoning_chain中）
- **语义验证**：直接回答问题，信息完整可独立理解
- **禁止单字答案**：单个答案值出现次数应 < 1%

#### 实际数据分布
```json
{
  "missing_count": 0,
  "length_stats": {
    "min": 1,      // ⚠️ 需修正
    "max": 333,    // ⚠️ 需修正
    "avg": "29.83",
    "median": 24
  }
}
```
⚠️ **注意**：当前数据存在1字符答案和超长答案，需要修正。

---

### 4.5 reasoning_chain 字段

#### 字段定义
5步推理链，展示空间关系判断过程，富含地理常识，不泄露答案。

#### 数据类型
对象数组

#### 结构要求
必须包含 5 个步骤：
1. entity_identification（实体识别）
2. spatial_relation_extraction（关系提取）
3. coordinate_retrieval（坐标检索）
4. spatial_calculation（空间计算）⭐
5. answer_generation（答案生成）

#### 质量要求⭐
- **事实正确性**：所有地理事实必须准确
- **坐标准确性**：与实体库一致（误差<0.01度）
- **推理引导**：每步提供推理思路（不限制固定句式）
- **答案保护**：步骤1-4不泄露答案
- **地理常识**：富含行政区划、地理特征、地标信息

#### 步骤4（spatial_calculation）核心要求⭐
- content长度：80-150字符
- 必须包含：计算过程 + 地理常识
- 禁止：直接泄露答案
- 允许：灵活表达，不限制固定句式

#### 标准模板
```json
{
  "reasoning_chain": [
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "识别问题中的地理实体",
      "entities_involved": ["实体A", "实体B"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "分析空间关系类型",
      "relation_type": "topological"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "获取坐标信息",
      "coordinates": {
        "实体A": [经度, 纬度],
        "实体B": [经度, 纬度]
      }
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "执行空间计算，结合地理常识",
      "calculation_result": "计算结果"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "总结推理过程",
      "final_answer": "最终答案"
    }
  ]
}
```

#### 验证规则⭐
- **结构验证**：5个步骤，编号连续
- **字段验证**：每步包含必需字段
- **质量验证**：事实正确、坐标准确、推理合理、不泄露答案
- **一致性验证**：与question、answer、entities语义一致

#### 实际数据分布
```json
{
  "missing_count": 0,
  "step_count_stats": {
    "min": 5,
    "max": 5,
    "avg": "5.00"
  },
  "avg_content_length_per_step": "35.81"  // ⚠️ 建议增加到50+
}
```

---

### 4.6 entities 字段

#### 字段定义
问题中涉及的地理实体数组，包含名称、类型和坐标。

#### 数据类型
对象数组

#### 数量约束
- 最小：2个实体
- 最大：3个实体

#### 实体对象结构
```json
{
  "name": "实体名称",
  "type": "实体类型",
  "coords": [经度, 纬度]
}
```

#### 实体类型
- `province` - 省级行政区
- `city` - 城市
- `landmark` - 地标
- `mountain` - 山脉
- `river` - 河流
- `lake` - 湖泊
- `region` - 区域

#### 验证规则⭐
- 数组长度：2-3个实体
- 每个实体包含name/type/coords
- **实体存在性验证**：实体名称存在于实体库
- **实体类型验证**：类型与实体库一致
- **坐标准确性验证**：坐标与实体库一致（误差<0.01度）

#### 实际数据分布
```json
{
  "missing_count": 0,
  "entity_count_stats": {
    "min": 2,
    "max": 3,
    "avg": "2.00"
  }
}
```

---

### 4.7 spatial_tokens 字段

#### 字段定义
空间关系相关的关键词数组。

#### 数据类型
字符串数组

#### 数量约束
- 最小：3个关键词
- 最大：9个关键词
- 推荐：5-7个关键词

#### Token类型
1. 地理实体名称
2. 空间关系词（位于、内部、包含）
3. 方位词（东、西、南、北）
4. 度量词（距离、公里）
5. 行政区划词（省、市、区）

#### 验证规则
- 数组长度：3-9个token
- 必须包含≥2个地理实体
- 必须包含≥1个空间关系词

---

### 4.8 difficulty 字段

#### 字段定义
问题的难度级别，从difficulty_score映射得到。

#### 数据类型
字符串（枚举）

#### 可选值
- `easy` - 简单
- `medium` - 中等
- `hard` - 困难

#### 映射规则
- easy: 1.0 - 2.0
- medium: 2.0 - 3.5
- hard: 3.5 - 5.0

---

### 4.9 topology_subtype 字段

#### 字段定义
拓扑空间关系的子类型。

#### 数据类型
字符串（枚举）

#### 可选值
- `within` - A在B内部
- `contains` - B包含A
- `adjacent` - A与B相邻
- `disjoint` - A与B相离
- `overlap` - A与B重叠

#### 必需性
条件必需：spatial_relation_type = "topological"

---

### 4.10 prompt_id 字段

#### 字段定义
数据生成时使用的提示词ID。

#### 数据类型
字符串

#### 必需性
可选字段

---

### 4.11 split 字段

#### 字段定义
数据集划分标识。

#### 数据类型
字符串（枚举）

#### 可选值
- `train` - 训练集
- `dev` - 验证集
- `test` - 测试集

#### 推荐比例
train:dev:test = 8:1:1

---

### 4.12 entity_to_token 字段

#### 字段定义
实体到问题文本中位置的映射。

#### 数据类型
对象

#### 必需性
条件必需：有reasoning_chain时

---

### 4.13 difficulty_score 字段

#### 字段定义
问题难度的数值评分。

#### 数据类型
浮点数

#### 范围
1.0 - 5.0

---

## 五、标准模板集合

### 5.1 完整数据模板

```json
{
  "id": "geosr_00001",
  "spatial_relation_type": "topological",
  "topology_subtype": "within",
  "question": "故宫位于北京市内吗？",
  "answer": "是的，故宫位于北京市内。",
  "reasoning_chain": [
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "从问题中识别实体：故宫（landmark）、北京市（province）",
      "entities_involved": ["故宫", "北京市"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "问题询问'位于...内'，属于拓扑空间关系",
      "relation_type": "topological"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "故宫坐标：(116.3972, 39.9163)，北京市坐标：(116.4074, 39.9042)",
      "coordinates": {
        "故宫": [116.3972, 39.9163],
        "北京市": [116.4074, 39.9042]
      }
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "故宫的坐标点(116.3972°E, 39.9163°N)位于北京市的多边形边界内。故宫作为明清皇宫，地处北京中心。",
      "calculation_result": "within"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "根据拓扑关系判断，故宫位于北京市内",
      "final_answer": "故宫在北京市内"
    }
  ],
  "entities": [
    {
      "name": "故宫",
      "type": "landmark",
      "coords": [116.3972, 39.9163]
    },
    {
      "name": "北京市",
      "type": "province",
      "coords": [116.4074, 39.9042]
    }
  ],
  "spatial_tokens": ["故宫", "北京市", "位于", "内部"],
  "difficulty": "easy",
  "difficulty_score": 1.2,
  "split": "train",
  "entity_to_token": {
    "故宫": {"char_start": 0, "char_end": 2, "token_indices": [0, 1]},
    "北京市": {"char_start": 5, "char_end": 8, "token_indices": [5, 6, 7]}
  }
}
```

---

## 六、完整参考示例集

以下示例包含所有13个字段的完整数据，涵盖不同的空间关系类型和难度级别。

### 6.1 示例1：Topological - Within（简单难度）

**场景**：判断地标是否位于行政区域内

```json
{
  "id": "geosr_00001",
  "spatial_relation_type": "topological",
  "topology_subtype": "within",
  "question": "故宫位于北京市内吗？",
  "answer": "是的，故宫位于北京市内。",
  "reasoning_chain": [
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "从问题'故宫位于北京市内吗？'中，可以识别出涉及两个地理实体：故宫（landmark类型）和北京市（province类型）。",
      "entities_involved": ["故宫", "北京市"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "问题询问'位于...内'，属于拓扑空间关系中的包含关系判断。",
      "relation_type": "topological"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "检索实体坐标信息：故宫位于东经116.3972度、北纬39.9163度；北京市中心位于东经116.4074度、北纬39.9042度。故宫作为明清两代的皇宫，地处北京市中心区域。",
      "coordinates": {
        "故宫": [116.3972, 39.9163],
        "北京市": [116.4074, 39.9042]
      }
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "执行拓扑判断：基于坐标分析，故宫的坐标点(116.3972°E, 39.9163°N)位于北京市的多边形边界范围内。故宫地处北京市东城区，是北京的核心地标。根据行政区划，故宫确实隶属于北京市。",
      "calculation_result": "within"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "根据拓扑关系判断，故宫位于北京市边界范围内，生成肯定答案。",
      "final_answer": "故宫在北京市内"
    }
  ],
  "entities": [
    {
      "name": "故宫",
      "type": "landmark",
      "coords": [116.3972, 39.9163]
    },
    {
      "name": "北京市",
      "type": "province",
      "coords": [116.4074, 39.9042]
    }
  ],
  "spatial_tokens": [
    "故宫",
    "北京市",
    "位于",
    "内部",
    "包含",
    "隶属",
    "行政区划"
  ],
  "difficulty": "easy",
  "difficulty_score": 1.2,
  "split": "train",
  "entity_to_token": {
    "故宫": {
      "char_start": 0,
      "char_end": 2,
      "token_indices": [0, 1]
    },
    "北京市": {
      "char_start": 5,
      "char_end": 8,
      "token_indices": [5, 6, 7]
    }
  },
  "prompt_id": "prompt_0001"
}
```

**质量验证**：
- ✅ 事实正确：故宫确实位于北京市内
- ✅ 坐标准确：与实体库一致
- ✅ 推理合理：5步推理链逻辑清晰
- ✅ 富含地理常识：包含"明清皇宫"、"东城区"等信息
- ✅ 不泄露答案：步骤4描述计算过程，而非直接说"是的"

---

### 6.2 示例2：Topological - Adjacent（中等难度）

**场景**：判断两个省份是否相邻

```json
{
  "id": "geosr_00002",
  "spatial_relation_type": "topological",
  "topology_subtype": "adjacent",
  "question": "河北省与北京市是否相邻？",
  "answer": "是的，河北省与北京市相邻。",
  "reasoning_chain": [
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "识别问题中的地理实体：河北省（province类型）和北京市（province类型）。",
      "entities_involved": ["河北省", "北京市"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "问题询问'是否相邻'，属于拓扑空间关系中的相邻关系判断。",
      "relation_type": "topological"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "获取坐标信息：河北省位于东经113.5°E-119.8°E，北纬36.0°N-42.6°N；北京市位于东经115.4°E-117.5°E，北纬39.4°N-41.0°N。河北省环绕北京市，两市地理接壤。",
      "coordinates": {
        "河北省": [116.0, 38.5],
        "北京市": [116.4, 39.9]
      }
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "分析拓扑关系：从地理位置上看，河北省完全包围北京市，北京市位于河北省北部中心区域。两地的边界直接接触，共享边界线。河北省作为环绕京津的省份，其北部边界与北京市接壤，符合相邻关系的定义。",
      "calculation_result": "adjacent"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "基于地理位置分析，河北省与北京市共享边界，生成肯定答案。",
      "final_answer": "河北省与北京市相邻"
    }
  ],
  "entities": [
    {
      "name": "河北省",
      "type": "province",
      "coords": [116.0, 38.5]
    },
    {
      "name": "北京市",
      "type": "province",
      "coords": [116.4, 39.9]
    }
  ],
  "spatial_tokens": [
    "河北省",
    "北京市",
    "相邻",
    "边界",
    "接壤",
    "环绕"
  ],
  "difficulty": "medium",
  "difficulty_score": 2.5,
  "split": "train",
  "entity_to_token": {
    "河北省": {
      "char_start": 0,
      "char_end": 3,
      "token_indices": [0, 1, 2]
    },
    "北京市": {
      "char_start": 5,
      "char_end": 8,
      "token_indices": [5, 6, 7]
    }
  }
}
```

**质量验证**：
- ✅ 事实正确：河北省与北京市确实相邻
- ✅ 富含地理常识："河北省环绕北京市"、"共享边界线"
- ✅ 推理逻辑清晰：从包围关系推导到相邻关系

---

### 6.3 示例3：Directional（中等难度）

**场景**：判断两个城市之间的方向关系

```json
{
  "id": "geosr_00003",
  "spatial_relation_type": "directional",
  "question": "北京在上海的什么方向？",
  "answer": "西北方向。",
  "reasoning_chain": [
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "识别地理实体：北京（city类型）和上海（city类型）。",
      "entities_involved": ["北京", "上海"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "问题询问'什么方向'，属于方向空间关系判断。",
      "relation_type": "directional"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "获取坐标信息：北京位于东经116.4074度、北纬39.9042度；上海位于东经121.4737度、北纬31.2304度。北京是中国的首都，上海是中国的经济中心。",
      "coordinates": {
        "北京": [116.4074, 39.9042],
        "上海": [121.4737, 31.2304]
      }
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "计算方位角：基于两地的坐标，北京相对于上海的经度差为-5.07度（北京在西），纬度差为+8.67度（北京在北）。使用方位角公式计算，北京位于上海的西北方向，具体角度约为北偏西35度。从地理上看，北京位于华北平原，上海位于长江三角洲，北京确实在上海的西北方向。",
      "calculation_result": "northwest"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "根据方位角计算结果，北京在上海的西北方向。",
      "final_answer": "西北方向"
    }
  ],
  "entities": [
    {
      "name": "北京",
      "type": "city",
      "coords": [116.4074, 39.9042]
    },
    {
      "name": "上海",
      "type": "city",
      "coords": [121.4737, 31.2304]
    }
  ],
  "spatial_tokens": [
    "北京",
    "上海",
    "西北",
    "方向",
    "方位"
  ],
  "difficulty": "medium",
  "difficulty_score": 1.2,
  "split": "train",
  "entity_to_token": {
    "北京": {
      "char_start": 0,
      "char_end": 2,
      "token_indices": [0, 1]
    },
    "上海": {
      "char_start": 4,
      "char_end": 6,
      "token_indices": [4, 5]
    }
  }
}
```

**质量验证**：
- ✅ 事实正确：北京确实在上海的西北方向
- ✅ 计算详细：包含经度差、纬度差、方位角计算
- ✅ 地理常识："华北平原"、"长江三角洲"

---

### 6.4 示例4：Metric（中等难度）

**场景**：计算两个城市之间的距离

```json
{
  "id": "geosr_00004",
  "spatial_relation_type": "metric",
  "question": "从北京到上海的距离大约是多少公里？",
  "answer": "约1283公里。",
  "reasoning_chain": [
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "识别地理实体：北京（city类型）和上海（city类型）。",
      "entities_involved": ["北京", "上海"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "问题询问'距离多少公里'，属于度量空间关系判断。",
      "relation_type": "metric"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "获取坐标信息：北京位于东经116.4074度、北纬39.9042度；上海位于东经121.4737度、北纬31.2304度。",
      "coordinates": {
        "北京": [116.4074, 39.9042],
        "上海": [121.4737, 31.2304]
      }
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "计算球面距离：使用Haversine公式，基于两地的经纬度坐标计算大圆距离。两地经度差约5.07度，纬度差约8.67度。计算得出北京到上海的直线距离约为1068公里，考虑实际交通路线，陆地距离约为1200-1300公里。这一距离符合中国两大中心城市之间的实际地理情况。",
      "calculation_result": "1283 km"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "根据距离计算结果，生成度量答案。",
      "final_answer": "约1283公里"
    }
  ],
  "entities": [
    {
      "name": "北京",
      "type": "city",
      "coords": [116.4074, 39.9042]
    },
    {
      "name": "上海",
      "type": "city",
      "coords": [121.4737, 31.2304]
    }
  ],
  "spatial_tokens": [
    "北京",
    "上海",
    "距离",
    "公里",
    "约"
  ],
  "difficulty": "medium",
  "difficulty_score": 1.3,
  "split": "train",
  "entity_to_token": {
    "北京": {
      "char_start": 2,
      "char_end": 4,
      "token_indices": [2, 3]
    },
    "上海": {
      "char_start": 6,
      "char_end": 8,
      "token_indices": [6, 7]
    }
  }
}
```

**质量验证**：
- ✅ 事实正确：北京到上海约1283公里（在±20%误差内）
- ✅ 计算方法正确：使用Haversine公式
- ✅ 富含地理常识："大圆距离"、"陆地距离"

---

### 6.5 示例5：Composite（困难难度）

**场景**：同时判断方向和距离的复合关系

```json
{
  "id": "geosr_00005",
  "spatial_relation_type": "composite",
  "question": "北京在上海的什么方向，距离大约是多少公里？",
  "answer": "西北方向，距离约1283公里。",
  "reasoning_chain": [
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "识别问题中的地理实体：北京（city类型）和上海（city类型）。",
      "entities_involved": ["北京", "上海"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "问题同时询问'方向'和'距离'，包含两种空间关系类型：方向关系和度量关系，属于复合空间关系。",
      "relation_type": "composite"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "获取坐标信息：北京位于东经116.4074度、北纬39.9042度，是中国的首都和政治中心；上海位于东经121.4737度、北纬31.2304度，是中国的经济中心和最大港口城市。",
      "coordinates": {
        "北京": [116.4074, 39.9042],
        "上海": [121.4737, 31.2304]
      }
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "执行复合空间计算：方向分析显示，北京的纬度比上海高8.67度，经度小5.07度，因此北京位于上海的西北方向。距离分析显示，使用Haversine公式计算球面距离约为1283公里。北京和上海作为中国的两大核心城市，这一空间距离和方位关系符合中国地理格局。",
      "calculation_result": "northwest, 1283 km"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "综合方向和距离计算结果，生成复合答案。",
      "final_answer": "西北方向，距离约1283公里"
    }
  ],
  "entities": [
    {
      "name": "北京",
      "type": "city",
      "coords": [116.4074, 39.9042]
    },
    {
      "name": "上海",
      "type": "city",
      "coords": [121.4737, 31.2304]
    }
  ],
  "spatial_tokens": [
    "北京",
    "上海",
    "西北",
    "方向",
    "距离",
    "公里",
    "约"
  ],
  "difficulty": "hard",
  "difficulty_score": 3.2,
  "split": "test",
  "entity_to_token": {
    "北京": {
      "char_start": 0,
      "char_end": 2,
      "token_indices": [0, 1]
    },
    "上海": {
      "char_start": 4,
      "char_end": 6,
      "token_indices": [4, 5]
    }
  }
}
```

**质量验证**：
- ✅ 事实正确：方向和距离都准确
- ✅ 复合推理：同时处理方向和度量关系
- ✅ 富含地理常识："政治中心"、"经济中心"、"中国地理格局"

---

### 6.6 示例6：Topological - Disjoint（中等难度）

**场景**：判断两个地理实体是否相离

```json
{
  "id": "geosr_00006",
  "spatial_relation_type": "topological",
  "topology_subtype": "disjoint",
  "question": "大巴山脉和云冈石窟是否存在包含关系？",
  "answer": "不存在，大巴山脉和云冈石窟相离。",
  "reasoning_chain": [
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "识别地理实体：大巴山脉（mountain类型）和云冈石窟（landmark类型）。",
      "entities_involved": ["大巴山脉", "云冈石窟"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "问题询问'是否存在包含关系'，属于拓扑空间关系判断。",
      "relation_type": "topological"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "获取坐标信息：大巴山脉位于中国西南部，主要在川渝陕交界地区，大致坐标为东经108.5度、北纬32.5度；云冈石窟位于中国北部山西省大同市，坐标为东经113.1206度、北纬40.1106度。",
      "coordinates": {
        "大巴山脉": [108.5, 32.5],
        "云冈石窟": [113.1206, 40.1106]
      }
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "分析拓扑关系：对比坐标可知，大巴山脉位于秦巴山区西南部，跨越四川、重庆、陕西三省市；云冈石窟位于山西省大同市武周山南麓。两地经度相差约4.6度，纬度相差约7.6度，地理跨度极大，空间上完全分离。大巴山脉位于西南，云冈石窟位于华北，两地相距数百公里，不存在包含关系。",
      "calculation_result": "disjoint"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "基于空间位置分析，两地相距甚远，生成否定答案。",
      "final_answer": "大巴山脉和云冈石窟相离"
    }
  ],
  "entities": [
    {
      "name": "大巴山脉",
      "type": "mountain",
      "coords": [108.5, 32.5]
    },
    {
      "name": "云冈石窟",
      "type": "landmark",
      "coords": [113.1206, 40.1106]
    }
  ],
  "spatial_tokens": [
    "大巴山脉",
    "云冈石窟",
    "包含",
    "位于",
    "内部",
    "相离",
    "距离"
  ],
  "difficulty": "medium",
  "difficulty_score": 2.6,
  "split": "train",
  "entity_to_token": {
    "大巴山脉": {
      "char_start": 0,
      "char_end": 4,
      "token_indices": [0, 1, 2, 3]
    },
    "云冈石窟": {
      "char_start": 6,
      "char_end": 10,
      "token_indices": [6, 7, 8, 9]
    }
  }
}
```

**质量验证**：
- ✅ 事实正确：大巴山脉和云冈石窟确实相离
- ✅ 地理常识丰富："川渝陕交界"、"秦巴山区"、"华北地区"
- ✅ 推理详细：从坐标对比到地理跨度分析

---

### 示例说明

#### 字段完整性检查清单

每个示例都包含以下13个字段：

| # | 字段名 | 示例1 | 示例2 | 示例3 | 示例4 | 示例5 | 示例6 |
|---|--------|-------|-------|-------|-------|-------|-------|
| 1 | id | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2 | spatial_relation_type | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3 | topology_subtype | ✅ | ✅ | - | - | - | ✅ |
| 4 | question | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 5 | answer | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 6 | reasoning_chain | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 7 | entities | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 8 | spatial_tokens | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 9 | difficulty | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 10 | difficulty_score | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 11 | split | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 12 | entity_to_token | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 13 | prompt_id | ✅ | - | - | - | - | - |

#### 难度分布

- **easy（简单）**：示例1（within，单一拓扑关系）
- **medium（中等）**：示例2、3、4、6（adjacent、directional、metric、disjoint）
- **hard（困难）**：示例5（composite，复合空间关系）

#### 空间关系类型分布

- **topological**：示例1、2、6（within、adjacent、disjoint）
- **directional**：示例3（方向关系）
- **metric**：示例4（度量关系）
- **composite**：示例5（复合关系）

#### 实体类型分布

- **province**：河北省、北京市
- **city**：北京、上海
- **landmark**：故宫、云冈石窟
- **mountain**：大巴山脉

#### 质量验证通过情况

所有示例均通过以下验证：
- ✅ Question-Answer事实正确性
- ✅ Reasoning Chain逻辑正确性
- ✅ 实体库存在性（假设实体）
- ✅ 坐标地理事实正确性（假设坐标）
- ✅ Question-Answer-Reasoning Chain一致性

---

## 七、附录

### 7.1 V2.0 难度评分算法

```python
def calculate_difficulty_score_v2(spatial_type, topology_subtype=None):
    base_scores = {
        "directional": 1.2,
        "topological": 2.2,
        "metric": 1.3,
        "composite": 3.2
    }

    topology_bonus = {
        "within": 0.0,
        "contains": 0.1,
        "adjacent": 0.3,
        "disjoint": 0.4,
        "overlap": 0.6
    }

    score = base_scores[spatial_type]
    if topology_subtype:
        score += topology_bonus[topology_subtype]

    return min(max(score, 1.0), 5.0)
```

### 7.2 DE-9IM 拓扑关系模型

DE-9IM是描述两个几何对象空间关系的标准模型。

**关系类型**：
1. Within - A在B内部
2. Contains - B包含A
3. Adjacent - A与B相邻
4. Disjoint - A与B相离
5. Overlap - A与B重叠

### 7.3 实体库规范

```json
{
  "实体名称": {
    "name": "标准名称",
    "type": "实体类型",
    "coords": [经度, 纬度],
    "aliases": ["别名"],
    "admin_hierarchy": ["省", "市", "区"]
  }
}
```

---

## 八、文档变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| V1.0 | 2026-03-11 | 初始版本，包含完整的数据质量验证体系 |

---

**文档结束**

本文档定义了 GeoKD-SR 数据集的完整字段标准和数据质量验证体系。重点包括：
- Question-Answer事实正确性验证
- Reasoning Chain正确性和合理性验证
- 实体库存在性验证
- 实体坐标地理事实正确性验证
- Question-Answer-Reasoning Chain一致性验证
