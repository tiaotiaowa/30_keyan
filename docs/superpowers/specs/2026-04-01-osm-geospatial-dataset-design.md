# GeoKD-SR 基于OSM真实数据的地理空间推理数据集设计方案

> 日期: 2026-04-01
> 状态: 设计完成，待实施
> 更新: 新增实体对精简格式、参考实体标注、GLM QA生成策略

## Context

当前GeoKD-SR项目使用的11,770条数据由GLM API生成，存在事实性错误风险。决定基于OSM真实数据和行政区划边界数据，使用PostGIS空间数据库精确计算空间关系，完全替代现有数据集。

**产出物**: ① 实体库(entity_database.json) ② 实体对数据(entity_pairs.jsonl) ③ GLM生成的完整QA数据集
**数据规模**: 10,000条，按8:1:1划分
**工作目录**: D:\gis_data

---

## 一、数据源

### 1.1 行政区划数据（geoatlas）

| 文件 | 层级 | 数量 | 几何类型 | 坐标系 |
|------|------|------|---------|--------|
| province.geojson | 省级 | 35 | Polygon | WGS84 |
| city.geojson | 市/区县级 | 475(363市+112区县, 同级) | Polygon | WGS84 |

字段: adcode, name, center, centroid, childrenNum, level, parent

空间关系: 省级相邻70对、市/区县相邻941对(省内669+跨省272)、省-市包含475对

### 1.2 OSM Shapefile数据

32省18图层, CRS: EPSG:4326, 来源: Geofabrik 2026-03-11

| 图层 | 几何 | 筛选条件 | 用途 |
|------|------|---------|------|
| natural | Point/Polygon | name非空, fclass∈{peak,mountain_range} | 山峰/山脉 |
| water_a | Polygon | name非空, area>1km² | 湖泊/水库 |
| waterways | Line | name非空 | 河流/运河 |
| pois | Point | name非空, fclass∈{attraction,university,hospital,stadium} | 景点/设施 |
| landuse_a | Polygon | name非空, fclass∈{forest,recreation_ground,residential} | 森林/公园 |
| roads | Line | name非空, code∈{5111,5112,5113} | 主要道路 |
| railways | Line | name非空 | 铁路 |
| transport | Point | name非空, fclass∈{station,airport} | 火车站/机场 |

---

## 二、实体库设计

### 2.1 统一实体格式（精简版）

```json
{
  "entity_id": "admin_city_420100",
  "entity_type": "administrative",
  "entity_subtype": "city",
  "name_zh": "武汉市",
  "name_en": "Wuhan",
  "geometry_type": "Polygon",
  "centroid": [114.3055, 30.5930],
  "source": "geoatlas",
  "properties": {"adcode": 420100, "level": "city", "province_zh": "湖北省"}
}
```

字段说明:
- entity_id: `{type}_{subtype}_{id}`
- geometry_type: Point/Polygon/Line
- centroid: [经度, 纬度] WGS84
- properties: 类型特有属性(行政区划有adcode/level，山峰有elevation等)

### 2.2 实体类型体系（11种，无settlement）

| 实体类型 | entity_subtype | 几何 | 来源 | 数量 |
|---------|---------------|------|------|------|
| administrative | province | Polygon | geoatlas | 35 |
| administrative | city/district | Polygon | geoatlas | 475 |
| terrain | peak | Point | OSM natural | ~1万 |
| water_body | lake/reservoir | Polygon | OSM water_a | ~3千 |
| waterway | river/canal | Line | OSM waterways | ~2万 |
| landmark | attraction | Point | OSM pois | ~5万 |
| facility | university/hospital | Point | OSM pois | ~3万 |
| transport | station/airport | Point | OSM transport | ~2万 |
| area | forest/park | Polygon | OSM landuse_a | ~1万 |
| road | national_motorway/trunk | Line | OSM roads | ~3万 |
| railway | rail | Line | OSM railways | ~5千 |

---

## 三、实体对数据格式

### 3.1 参考实体标注规则

| 关系类型 | 参考实体字段 | 含义 | 对称性 |
|---------|------------|------|--------|
| directional | reference_entity=entity_b | "从B看A的方向" | 非对称 |
| topological.contains | reference_entity=entity_a | "A包含B" | 非对称 |
| topological.within | reference_entity=entity_b | "A在B内部" | 非对称 |
| topological.crosses | reference_entity=entity_b | "A穿越B" | 非对称 |
| topological.touches | **无** | "A与B相邻" | 对称 |
| topological.disjoint | **无** | "A与B分离" | 对称 |
| metric | **无** | 距离关系 | 对称 |
| composite | 视组合类型 | 通常取entity_b | 视情况 |

### 3.2 方向关系实体对

```json
{
  "pair_id": "dir_00001",
  "spatial_relation_type": "directional",
  "reference_entity": "entity_b",
  "entity_a": {"entity_id": "admin_city_420100", "name_zh": "武汉市", "centroid": [114.31, 30.59]},
  "entity_b": {"entity_id": "admin_city_430100", "name_zh": "长沙市", "centroid": [112.94, 28.23]},
  "spatial_result": {
    "azimuth_deg": 29.7,
    "direction_8_zh": "东北",
    "direction_8_en": "northeast",
    "distance_km": 296
  }
}
```

### 3.3 拓扑Contains实体对

```json
{
  "pair_id": "topo_contains_00001",
  "spatial_relation_type": "topological",
  "topology_subtype": "contains",
  "reference_entity": "entity_a",
  "entity_a": {"entity_id": "admin_prov_420000", "name_zh": "湖北省"},
  "entity_b": {"entity_id": "admin_city_420100", "name_zh": "武汉市"},
  "spatial_result": {"topology": "contains"}
}
```

### 3.4 拓扑Within实体对

```json
{
  "pair_id": "topo_within_00001",
  "spatial_relation_type": "topological",
  "topology_subtype": "within",
  "reference_entity": "entity_b",
  "entity_a": {"entity_id": "admin_city_420100", "name_zh": "武汉市"},
  "entity_b": {"entity_id": "admin_prov_420000", "name_zh": "湖北省"},
  "spatial_result": {"topology": "within"}
}
```

### 3.5 拓扑Touches实体对（无参考实体）

```json
{
  "pair_id": "topo_touches_00001",
  "spatial_relation_type": "topological",
  "topology_subtype": "touches",
  "entity_a": {"entity_id": "admin_prov_130000", "name_zh": "河北省"},
  "entity_b": {"entity_id": "admin_prov_110000", "name_zh": "北京市"},
  "spatial_result": {"topology": "touches", "shared_border_km": 128.5}
}
```

### 3.6 拓扑Crosses实体对

```json
{
  "pair_id": "topo_crosses_00001",
  "spatial_relation_type": "topological",
  "topology_subtype": "crosses",
  "reference_entity": "entity_b",
  "entity_a": {"entity_id": "ww_yangtze", "name_zh": "长江"},
  "entity_b": {"entity_id": "admin_prov_420000", "name_zh": "湖北省"},
  "spatial_result": {"topology": "crosses"}
}
```

### 3.7 拓扑Disjoint实体对（无参考实体）

```json
{
  "pair_id": "topo_disjoint_00001",
  "spatial_relation_type": "topological",
  "topology_subtype": "disjoint",
  "entity_a": {"entity_id": "admin_prov_110000", "name_zh": "北京市"},
  "entity_b": {"entity_id": "admin_prov_310000", "name_zh": "上海市"},
  "spatial_result": {"topology": "disjoint", "distance_km": 1068}
}
```

### 3.8 距离关系实体对（无参考实体）

```json
{
  "pair_id": "metric_00001",
  "spatial_relation_type": "metric",
  "entity_a": {"entity_id": "admin_city_420100", "name_zh": "武汉市", "centroid": [114.31, 30.59]},
  "entity_b": {"entity_id": "admin_city_430100", "name_zh": "长沙市", "centroid": [112.94, 28.23]},
  "spatial_result": {"distance_km": 296}
}
```

### 3.9 复合关系实体对

```json
{
  "pair_id": "comp_00001",
  "spatial_relation_type": "composite",
  "composite_type": "direction_distance",
  "reference_entity": "entity_b",
  "entity_a": {"entity_id": "admin_city_420100", "name_zh": "武汉市"},
  "entity_b": {"entity_id": "admin_city_430100", "name_zh": "长沙市"},
  "spatial_result": {"azimuth_deg": 29.7, "direction_8_zh": "东北", "distance_km": 296}
}
```

---

## 四、空间关系分配（各25% = 2,500条）

| 类型 | 条数 | 子类型 |
|------|------|--------|
| 方向推理 | 2,500 | 1 |
| 拓扑推理 | 2,500 | 5(contains/within/touches/crosses/disjoint各500) |
| 距离推理 | 2,500 | 1 |
| 复合推理 | 2,500 | 5 |
| **合计** | **10,000** | **12** |

### 4.1 方向推理采样分配

| 编号 | 实体A | 实体B | 采样数 |
|------|-------|-------|--------|
| D1 | province.centroid | city.centroid | 500 |
| D2 | city.centroid | city.centroid(跨省) | 700 |
| D3 | city.centroid | peak.point | 500 |
| D4 | city.centroid | lake.centroid | 400 |
| D5 | city.centroid | attraction.point | 400 |

### 4.2 拓扑推理采样分配

| 子类型 | 面-面 | 点-面 | 线-面 | 合计 |
|--------|-------|-------|-------|------|
| Contains | ~300 | ~200 | 0 | 500 |
| Within | ~300 | ~200 | 0 | 500 |
| Touches | 500 | 0 | 0 | 500 |
| Crosses | 0 | 0 | 500 | 500 |
| Disjoint | ~250 | ~200 | ~50 | 500 |

### 4.3 复合推理采样分配

| 编号 | 组合类型 | 条数 |
|------|---------|------|
| C1 | 方向+距离 | 875 |
| C2 | 方向+拓扑 | 500 |
| C3 | 距离+拓扑 | 500 |
| C4 | 方向+距离+拓扑 | 375 |
| C5 | 多步推理 | 250 |

---

## 五、LLM QA生成策略（GLM-4.7）

### 5.1 输入格式

将实体对数据（含实体名、坐标、关系类型、空间计算结果、参考实体）作为prompt输入。

### 5.2 输出格式要求

每条实体对生成以下字段:

```json
{
  "question_zh": "武汉市位于长沙市的哪个方向？",
  "question_en": "What direction is Wuhan from Changsha?",
  "answer_zh": "武汉市位于长沙市的东北方向，直线距离约296公里",
  "answer_en": "Wuhan is to the northeast of Changsha, approximately 296km away",
  "answer_structured": {
    "direction": "northeast",
    "direction_zh": "东北",
    "distance_km": 296
  },
  "reasoning_chain": [
    {"step": 1, "type": "entity_identification", "content_zh": "识别实体: 武汉市(114.31°E,30.59°N), 长沙市(112.94°E,28.23°N)", "content_en": "Identify entities: Wuhan(114.31°E,30.59°N), Changsha(112.94°E,28.23°N)"},
    {"step": 2, "type": "relation_type_determination", "content_zh": "判断关系类型: 方向推理", "content_en": "Determine relation: directional"},
    {"step": 3, "type": "spatial_data_retrieval", "content_zh": "获取空间数据: 来源geoatlas", "content_en": "Retrieve spatial data: source geoatlas"},
    {"step": 4, "type": "spatial_computation", "content_zh": "方位角≈29.7°→东北方向, 距离≈296km", "content_en": "Azimuth≈29.7°→northeast, distance≈296km"},
    {"step": 5, "type": "answer_generation", "content_zh": "武汉市位于长沙市东北方向", "content_en": "Wuhan is northeast of Changsha"}
  ],
  "difficulty": "medium",
  "difficulty_score": 0.55,
  "spatial_tokens": ["东北", "方向", "公里"],
  "entity_to_token": {"武汉市": [0,3], "长沙市": [7,10]}
}
```

### 5.3 双重答案体系

- **answer_zh/en**: 自然语言答案 — 用于LLM评测(BLEU/ROUGE/BERTScore/LLM评分)
- **answer_structured**: 结构化参考答案 — 用于确定性评测(精确匹配/数值容差)

---

## 六、Pipeline架构

```
D:\gis_data\
├── osm_china/                    # OSM原始数据(已有)
├── geoatlas/                     # 行政区划数据(已有)
├── pipeline/
│   ├── 00_setup_db.py           # PostgreSQL+PostGIS环境搭建
│   ├── 01_import_data.py        # 导入OSM+geoatlas到PostGIS
│   ├── 02_extract_entities.py   # 提取并分类实体→统一实体库
│   ├── 03_compute_spatial.py    # 计算所有空间关系对
│   ├── 04_build_pairs.py        # 构建实体对(分配空间关系+参考实体)
│   ├── 05_generate_qa.py        # GLM-4.7 API生成QA+推理链+难度
│   ├── 06_validate.py           # 质量验证(PostGIS反向+答案交叉验证)
│   └── 07_split_export.py       # 数据划分与导出
├── output/
│   ├── entity_database.json     # 统一实体库
│   ├── entity_pairs.jsonl       # 实体对(含空间关系+参考实体)
│   ├── qa_dataset.jsonl         # GLM生成的完整数据集
│   ├── validated_dataset.jsonl  # 验证后数据集
│   └── splits/                  # 最终划分
│       ├── train.jsonl
│       ├── dev.jsonl
│       └── test.jsonl
└── config/
    └── pipeline_config.yaml
```

---

## 七、实施步骤

### Step 1: 环境搭建
- 安装PostgreSQL 16 + PostGIS 3.4
- 创建数据库和空间扩展
- 解压OSM Shapefile数据

### Step 2: 数据导入
- geoatlas GeoJSON → PostGIS
- OSM Shapefile批量导入(32省)
- 统一坐标系WGS84

### Step 3: 实体提取与分类
- 全量提取所有满足筛选条件的实体
- 构建统一实体库(entity_database.json)
- 生成中英文实体名映射

### Step 4: 空间关系计算
- 方向: ST_Azimuth批量计算
- 拓扑: ST_Contains/ST_Within/ST_Touches/ST_Crosses/ST_Disjoint
- 距离: ST_DistanceSphere批量计算
- 复合: 组合计算

### Step 5: 实体对构建
- 基于空间关系计算结果，构建10,000条实体对
- 按比例分配4种空间关系类型(各2,500条)
- 标注参考实体

### Step 5.5: LLM QA生成(GLM-4.7)
- 输入: 实体对JSON(含实体名、坐标、关系类型、空间计算结果、参考实体)
- GLM-4.7 API生成:
  1. question_zh / question_en
  2. answer_zh / answer_en (自然语言)
  3. answer_structured (结构化参考答案)
  4. reasoning_chain (5步推理链)
  5. difficulty + difficulty_score
  6. spatial_tokens / entity_to_token

### Step 6: 质量验证
- PostGIS反向验证空间关系
- LLM答案与结构化答案交叉验证
- 实体/坐标/关系一致性检查

### Step 7: 数据划分与导出
- 实体对互斥划分(train/dev/test = 8000/1000/1000)
- 分层采样
- 导出最终JSONL

---

## 八、验证方案

1. PostGIS反向验证: 重新计算空间关系确认正确性
2. 答案交叉验证: LLM自然语言答案 vs 结构化参考答案一致性
3. 实体存在性: 确认每个实体在源数据中真实存在
4. 坐标准确性: 坐标与源数据匹配
5. 分布验证: 各split的类型/拓扑子类型分布一致性(TVD<0.05)
