# GeoKD-SR OSM地理空间推理数据集 Pipeline 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于OSM真实数据和geoatlas行政区划数据，使用PostGIS精确计算空间关系，生成10,000条地理空间推理实体对数据集。

**Architecture:** PostgreSQL 18 + PostGIS 3.6空间数据库存储所有地理数据，Python pipeline逐步提取实体、计算空间关系、构建实体对、生成QA、验证质量、划分导出。

**Tech Stack:** PostgreSQL 18, PostGIS 3.6, Python 3.10+, geopandas, shapely, psycopg2, GLM-4.7 API

**Design Spec:** `C:\Users\60207\.claude\plans\serene-wiggling-thacker.md`

---

## File Structure

```
D:\gis_data\
├── osm_china/                        # OSM原始数据 (已有，35省)
├── geoatlas/                         # 行政区划数据 (已有)
├── pipeline/                         # [创建] Python pipeline脚本
│   ├── config.yaml                   # 全局配置(DB连接/路径/采样参数)
│   ├── 00_setup_db.py                # Task 1: 创建DB+PostGIS扩展
│   ├── 01_import_data.py             # Task 2: 导入geoatlas+OSM到PostGIS
│   ├── 02_extract_entities.py        # Task 3: 提取实体→entity_database.json
│   ├── 03_compute_spatial.py         # Task 4: 计算空间关系→spatial_relations/
│   ├── 04_build_pairs.py             # Task 5: 构建实体对→entity_pairs.jsonl
│   ├── 05_generate_qa.py             # Task 6: GLM-4.7生成QA+推理链
│   ├── 06_validate.py                # Task 7: 质量验证
│   ├── 07_split_export.py            # Task 8: 数据划分与导出
│   ├── difficulty_scorer.py          # 难度评分模块(被04/07调用)
│   └── db_utils.py                   # 数据库工具函数
├── output/                           # [创建] 输出目录
│   ├── entity_database.json          # 统一实体库
│   ├── spatial_relations/            # 空间关系计算结果
│   │   ├── directional.jsonl
│   │   ├── topo_contains.jsonl
│   │   ├── topo_within.jsonl
│   │   ├── topo_touches.jsonl
│   │   ├── topo_crosses.jsonl
│   │   ├── topo_disjoint.jsonl
│   │   ├── metric.jsonl
│   │   └── composite.jsonl
│   ├── entity_pairs.jsonl            # 10,000条实体对
│   ├── qa_dataset.jsonl              # GLM生成的完整数据集
│   ├── validated_dataset.jsonl       # 验证后数据集
│   └── splits/                       # 最终划分
│       ├── train.jsonl               # 8,000条
│       ├── dev.jsonl                 # 1,000条
│       └── test.jsonl                # 1,000条
└── logs/                             # [创建] 运行日志
```

---

## Task 1: 配置PostgreSQL + PostGIS数据库

**Files:**
- Create: `D:\gis_data\pipeline\config.yaml`
- Create: `D:\gis_data\pipeline\db_utils.py`
- Create: `D:\gis_data\pipeline\00_setup_db.py`

### 前置确认

psql连接需要密码。请先确认:
```bash
# 测试连接 (会提示输入密码)
D:\postgresql\bin\psql.exe -U postgres -p 5432 -c "SELECT version();"
```

如果PostGIS尚未安装到数据库:
```bash
# 先运行PostGIS安装程序
D:\postgis\postgis_3_6_pg18.exe
# 安装完成后，在psql中启用:
CREATE EXTENSION postgis;
```

- [ ] **Step 1: 创建pipeline目录和配置文件**

`config.yaml`:
```yaml
database:
  host: localhost
  port: 5432
  dbname: geokd_sr
  user: postgres
  password: ""  # 需要用户填写

paths:
  base_dir: D:/gis_data
  osm_dir: D:/gis_data/osm_china
  geoatlas_dir: D:/gis_data/geoatlas
  output_dir: D:/gis_data/output
  log_dir: D:/gis_data/logs

spatial:
  srid: 4326  # WGS84
  area_min_km2: 1.0  # 水体最小面积

sampling:
  total_pairs: 10000
  split_ratio: [0.8, 0.1, 0.1]
  difficulty_ratio:
    easy: 0.30
    medium: 0.50
    hard: 0.20
```

- [ ] **Step 2: 创建db_utils.py — 数据库工具函数**

```python
"""数据库连接和工具函数"""
import psycopg2
import psycopg2.extras
import yaml
import os
import logging

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_connection(config=None):
    if config is None:
        config = load_config()
    db = config['database']
    return psycopg2.connect(
        host=db['host'], port=db['port'],
        dbname=db['dbname'], user=db['user'],
        password=db['password']
    )

def execute_sql(sql, params=None, fetch=False):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch:
                return cur.fetchall()
            conn.commit()
    finally:
        conn.close()

def execute_sql_many(sql, params_list):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, params_list)
            conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 3: 创建00_setup_db.py — 数据库初始化**

```python
"""Step 0: 创建数据库geokd_sr并启用PostGIS扩展"""
import psycopg2
import yaml
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

def setup_database():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    db = config['database']
    # 先连接默认的postgres库
    conn = psycopg2.connect(
        host=db['host'], port=db['port'],
        dbname='postgres', user=db['user'],
        password=db['password']
    )
    conn.autocommit = True

    with conn.cursor() as cur:
        # 检查数据库是否已存在
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db['dbname'],))
        if cur.fetchone():
            print(f"数据库 {db['dbname']} 已存在，跳过创建")
        else:
            cur.execute(f'CREATE DATABASE {db["dbname"]}')
            print(f"数据库 {db['dbname']} 创建成功")

    conn.close()

    # 连接到新数据库，启用PostGIS
    conn = psycopg2.connect(
        host=db['host'], port=db['port'],
        dbname=db['dbname'], user=db['user'],
        password=db['password']
    )
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
        cur.execute("SELECT PostGIS_Version()")
        version = cur.fetchone()[0]
        print(f"PostGIS 版本: {version}")

        # 创建空间索引工作表(后续导入数据时使用)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS spatial_ref_sys_override (
                auth_name varchar(50),
                auth_srid integer,
                srtext varchar(2048)
            )
        """)

    conn.close()
    print("数据库初始化完成!")

if __name__ == "__main__":
    setup_database()
```

- [ ] **Step 4: 运行初始化脚本**

```bash
cd D:\gis_data
mkdir pipeline output logs output\spatial_relations output\splits 2>nul
python pipeline\00_setup_db.py
```

Expected output:
```
数据库 geokd_sr 创建成功 (或 已存在)
PostGIS 版本: 3.6.x
数据库初始化完成!
```

- [ ] **Step 5: 安装Python依赖**

```bash
pip install psycopg2-binary geopandas shapely pyyaml tqdm
```

- [ ] **Step 6: Commit**

```bash
git add D:/gis_data/pipeline/config.yaml D:/gis_data/pipeline/db_utils.py D:/gis_data/pipeline/00_setup_db.py
git commit -m "feat(pipeline): 数据库初始化和配置文件"
```

---

## Task 2: 导入数据到PostGIS

**Files:**
- Create: `D:\gis_data\pipeline\01_import_data.py`

- [ ] **Step 1: 编写数据导入脚本**

```python
"""Step 1: 导入geoatlas GeoJSON + OSM Shapefile到PostGIS"""
import geopandas as gpd
import os
import sys
import glob
import logging
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(__file__))
from db_utils import get_connection, load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def import_geoatlas():
    """导入行政区划数据"""
    config = load_config()
    geoatlas_dir = config['paths']['geoatlas_dir']
    conn = get_connection(config)

    for filename in ['province.geojson', 'city.geojson']:
        filepath = os.path.join(geoatlas_dir, filename)
        table_name = f"geoatlas_{filename.replace('.geojson', '')}"

        logger.info(f"导入 {filepath} → {table_name}")
        gdf = gpd.read_file(filepath, encoding='utf-8')

        # 确保是WGS84
        if gdf.crs is None:
            gdf = gdf.set_crs('EPSG:4326')
        elif gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs('EPSG:4326')

        # 统一列名(小写)
        gdf.columns = [c.lower() for c in gdf.columns]

        # 写入PostGIS
        gdf.to_postgis(table_name, conn, if_exists='replace', index=False)
        logger.info(f"  导入 {len(gdf)} 条记录到 {table_name}")

    conn.close()
    logger.info("geoatlas导入完成")

def import_osm_shapefiles():
    """导入32省OSM Shapefile"""
    config = load_config()
    osm_dir = config['paths']['osm_dir']
    conn = get_connection(config)

    # 需要导入的图层(对应设计文档中的筛选条件)
    target_layers = {
        'gis_osm_natural_free_1': 'natural',          # 山峰(Point)
        'gis_osm_water_a_free_1': 'water_a',          # 湖泊(Polygon)
        'gis_osm_waterways_free_1': 'waterways',       # 河流(Line)
        'gis_osm_pois_free_1': 'pois',                 # 景点/设施(Point)
        'gis_osm_landuse_a_free_1': 'landuse_a',       # 森林/公园(Polygon)
        'gis_osm_roads_free_1': 'roads',               # 道路(Line)
        'gis_osm_railways_free_1': 'railways',          # 铁路(Line)
        'gis_osm_transport_free_1': 'transport',        # 交通设施(Point)
    }

    # 获取所有省目录
    province_dirs = sorted([
        d for d in os.listdir(osm_dir)
        if os.path.isdir(os.path.join(osm_dir, d)) and d.endswith('-free.shp')
    ])

    logger.info(f"找到 {len(province_dirs)} 个省目录")

    for layer_file, layer_name in target_layers.items():
        # 为每个图层创建统一表
        create_table_sql = f"""
        DROP TABLE IF EXISTS osm_{layer_name};
        CREATE TABLE osm_{layer_name} (
            id SERIAL PRIMARY KEY,
            osm_id VARCHAR(50),
            name VARCHAR(200),
            fclass VARCHAR(100),
            code INTEGER,
            geom geometry(Geometry, 4326)
        );
        CREATE INDEX idx_osm_{layer_name}_geom ON osm_{layer_name} USING GIST(geom);
        CREATE INDEX idx_osm_{layer_name}_name ON osm_{layer_name}(name) WHERE name IS NOT NULL;
        """
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
        conn.commit()

        total_rows = 0
        for prov_dir in tqdm(province_dirs, desc=f"导入 osm_{layer_name}"):
            shp_path = os.path.join(osm_dir, prov_dir, f"{layer_file}.shp")
            if not os.path.exists(shp_path):
                continue

            try:
                gdf = gpd.read_file(shp_path, encoding='utf-8')
                if len(gdf) == 0:
                    continue

                # 确保WGS84
                if gdf.crs is None:
                    gdf = gdf.set_crs('EPSG:4326')
                elif gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs('EPSG:4326')

                # 标准化列名
                col_map = {}
                for col in gdf.columns:
                    if col.lower() in ['osm_id', 'name', 'fclass', 'code']:
                        col_map[col] = col.lower()
                gdf = gdf.rename(columns=col_map)

                # 仅保留需要的列
                keep_cols = [c for c in ['osm_id', 'name', 'fclass', 'code', 'geometry'] if c in gdf.columns]
                gdf = gdf[keep_cols]

                # 追加到统一表
                table_name = f"osm_{layer_name}"
                gdf.to_postgis(table_name, conn, if_exists='append', index=False)
                total_rows += len(gdf)

            except Exception as e:
                logger.warning(f"  导入 {shp_path} 失败: {e}")
                continue

        logger.info(f"  osm_{layer_name}: 共导入 {total_rows} 条记录")

    conn.close()
    logger.info("OSM Shapefile导入完成")

if __name__ == "__main__":
    import_geoatlas()
    import_osm_shapefiles()
```

- [ ] **Step 2: 运行数据导入**

```bash
python D:\gis_data\pipeline\01_import_data.py
```

Expected: geoatlas 35省+475市, OSM各图层~数万条, 总耗时~10-30分钟

- [ ] **Step 3: 验证导入结果**

```sql
-- 在psql中执行
SELECT 'geoatlas_province' as tbl, count(*) FROM geoatlas_province
UNION ALL SELECT 'geoatlas_city', count(*) FROM geoatlas_city
UNION ALL SELECT 'osm_natural', count(*) FROM osm_natural
UNION ALL SELECT 'osm_water_a', count(*) FROM osm_water_a
UNION ALL SELECT 'osm_waterways', count(*) FROM osm_waterways
UNION ALL SELECT 'osm_pois', count(*) FROM osm_pois
UNION ALL SELECT 'osm_landuse_a', count(*) FROM osm_landuse_a
UNION ALL SELECT 'osm_roads', count(*) FROM osm_roads
UNION ALL SELECT 'osm_railways', count(*) FROM osm_railways
UNION ALL SELECT 'osm_transport', count(*) FROM osm_transport;
```

- [ ] **Step 4: Commit**

```bash
git add D:/gis_data/pipeline/01_import_data.py
git commit -m "feat(pipeline): 数据导入脚本(geoatlas+OSM Shapefile)"
```

---

## Task 3: 提取实体到统一实体库

**Files:**
- Create: `D:\gis_data\pipeline\02_extract_entities.py`
- Output: `D:\gis_data\output\entity_database.json`

- [ ] **Step 1: 编写实体提取脚本**

核心逻辑:
1. 从geoatlas提取35省+475市 → administrative类型
2. 从osm_natural筛选peak → terrain类型
3. 从osm_water_a筛选area>1km² → water_body类型
4. 从osm_waterways筛选name非空 → waterway类型
5. 从osm_pois筛选fclass → landmark/facility类型
6. 从osm_transport筛选fclass → transport类型
7. 从osm_landuse_a筛选fclass → area类型
8. 从osm_roads筛选code → road类型
9. 从osm_railways筛选name非空 → railway类型

每条实体格式:
```json
{
  "entity_id": "admin_city_420100",
  "entity_type": "administrative",
  "entity_subtype": "city",
  "name_zh": "武汉市",
  "name_en": "",
  "geometry_type": "Polygon",
  "centroid": [114.3055, 30.5930],
  "source": "geoatlas",
  "properties": {"adcode": 420100, "level": "city"}
}
```

中英文映射: OSM name字段可能含中文名或英文名，需要分离处理。

- [ ] **Step 2: 运行实体提取**

```bash
python D:\gis_data\pipeline\02_extract_entities.py
```

Expected: 输出 `entity_database.json`, 各类型实体统计

- [ ] **Step 3: 验证实体库**

```bash
python -c "
import json
with open('D:/gis_data/output/entity_database.json') as f:
    db = json.load(f)
from collections import Counter
types = Counter(e['entity_type']+'/'+e['entity_subtype'] for e in db)
for t, c in types.most_common():
    print(f'{t}: {c}')
print(f'总计: {len(db)} 个实体')
"
```

- [ ] **Step 4: Commit**

---

## Task 4: 计算空间关系

**Files:**
- Create: `D:\gis_data\pipeline\03_compute_spatial.py`
- Output: `D:\gis_data\output\spatial_relations/*.jsonl`

- [ ] **Step 1: 编写空间关系计算脚本**

按设计文档的11种子类型，使用PostGIS函数计算:

| 子类型 | PostGIS函数 | 说明 |
|--------|------------|------|
| directional | ST_Azimuth + ST_DistanceSphere | 方位角+距离 |
| metric | ST_DistanceSphere | 点-点距离 |
| topo.contains | ST_Contains | 面含面/面含点 |
| topo.within | ST_Within | 面在面内/点在面内 |
| topo.touches | ST_Touches | 面面相邻 |
| topo.crosses | ST_Crosses | 线穿面 |
| topo.disjoint | ST_Disjoint | 分离 |

SQL示例(方向关系):
```sql
SELECT
    a.entity_id as entity_a_id, a.name_zh as entity_a_name,
    a.centroid as entity_a_centroid,
    b.entity_id as entity_b_id, b.name_zh as entity_b_name,
    b.centroid as entity_b_centroid,
    degrees(ST_Azimuth(ST_SetSRID(ST_MakePoint(b.centroid[0], b.centroid[1]), 4326),
                        ST_SetSRID(ST_MakePoint(a.centroid[0], a.centroid[1]), 4326))) as azimuth_deg,
    ST_DistanceSphere(
        ST_SetSRID(ST_MakePoint(a.centroid[0], a.centroid[1]), 4326),
        ST_SetSRID(ST_MakePoint(b.centroid[0], b.centroid[1]), 4326)
    ) / 1000.0 as distance_km
FROM entity_province a, entity_city b
WHERE a.adcode != b.parent_adcode  -- 跨省
```

- [ ] **Step 2: 运行空间关系计算**

```bash
python D:\gis_data\pipeline\03_compute_spatial.py
```

Expected: 各子类型空间关系JSONL文件

- [ ] **Step 3: 验证计算结果**

检查各文件的行数是否满足采样需求:
- directional: >=2500对
- metric: >=2500对
- topo_contains: >=500对
- topo_within: >=500对
- topo_touches: >=500对
- topo_crosses: >=500对
- topo_disjoint: >=500对
- composite候选: 足够

- [ ] **Step 4: Commit**

---

## Task 5: 构建实体对(10,000条)

**Files:**
- Create: `D:\gis_data\pipeline\04_build_pairs.py`
- Create: `D:\gis_data\pipeline\difficulty_scorer.py`
- Output: `D:\gis_data\output\entity_pairs.jsonl`

- [ ] **Step 1: 编写难度评分模块 difficulty_scorer.py**

按照设计文档5.3节的双轨难度体系实现

- [ ] **Step 2: 编写实体对构建脚本**

按分配表采样:
- 方向2500 + 距离2500 + 拓扑(5×500) + 复合(875+500+500+625) = 10000
- 每条实体对包含: pair_id, spatial_relation_type, entity_a/b, spatial_result, reference_entity, answer_structured

- [ ] **Step 3: 运行实体对构建**

```bash
python D:\gis_data\pipeline\04_build_pairs.py
```

- [ ] **Step 4: 验证实体对分布**

检查:
- 各子类型数量是否符合设计
- 难度分布是否接近30/50/20
- 参考实体标注是否正确

- [ ] **Step 5: Commit**

---

## Task 6: GLM-4.7 API生成QA

**Files:**
- Create: `D:\gis_data\pipeline\05_generate_qa.py`
- Output: `D:\gis_data\output\qa_dataset.jsonl`

- [ ] **Step 1: 设计GLM Prompt模板**

为每种关系类型设计prompt，输入实体对JSON，输出:
- question_zh / question_en
- answer_zh / answer_en
- answer_structured (与实体对中的参考答案一致)
- reasoning_chain (5步)

- [ ] **Step 2: 编写QA生成脚本**

使用GLM-4.7 API批量生成，带重试和速率限制

- [ ] **Step 3: 运行QA生成**

```bash
python D:\gis_data\pipeline\05_generate_qa.py
```

Expected: 10,000条QA数据

- [ ] **Step 4: Commit**

---

## Task 7: 质量验证

**Files:**
- Create: `D:\gis_data\pipeline\06_validate.py`
- Output: `D:\gis_data\output\validated_dataset.jsonl`

- [ ] **Step 1: 编写验证脚本**

验证项:
1. PostGIS反向验证: 重新计算空间关系确认正确性
2. answer_structured与spatial_result一致性
3. 实体坐标与源数据匹配
4. 必填字段完整性检查

- [ ] **Step 2: 运行验证**

```bash
python D:\gis_data\pipeline\06_validate.py
```

Expected: 输出验证报告，标注通过/不通过条目

- [ ] **Step 3: Commit**

---

## Task 8: 数据划分与导出

**Files:**
- Create: `D:\gis_data\pipeline\07_split_export.py`
- Output: `D:\gis_data\output\splits/train.jsonl`, `dev.jsonl`, `test.jsonl`

- [ ] **Step 1: 编写划分脚本**

11种子类型严格8:1:1划分:
- 每种子类型内独立shuffle
- 实体对互斥(同一对实体所有关系在同一split)
- 分层验证(TVD<0.05)

- [ ] **Step 2: 运行划分导出**

```bash
python D:\gis_data\pipeline\07_split_export.py
```

Expected:
- train.jsonl: 8,000条
- dev.jsonl: 1,000条
- test.jsonl: 1,000条

- [ ] **Step 3: 验证最终数据**

```python
# 检查各split的分布
for split in ['train', 'dev', 'test']:
    # 检查: 关系类型分布、拓扑子类型分布、难度分布
    # 所有TVD < 0.05
```

- [ ] **Step 4: Commit**

---

## 关键依赖和注意事项

1. **密码**: config.yaml中的database.password必须填写
2. **PostGIS安装**: 如果未安装到geokd_sr数据库，先运行 `CREATE EXTENSION postgis;`
3. **磁盘空间**: OSM数据导入后PostGIS数据库约5-10GB
4. **内存**: 空间关系计算需要较大内存，建议8GB+
5. **GLM API Key**: Task 6需要有效的GLM-4.7 API密钥
6. **耗时预估**: 数据导入~20min, 实体提取~10min, 空间计算~30min, QA生成~2-4h(API限速)

## Spec Coverage Check

| 设计文档章节 | 对应Task | 覆盖 |
|-------------|---------|------|
| 一、数据源 | Task 1-2 | ✓ |
| 二、实体系统 | Task 3 | ✓ |
| 三、实体对格式 | Task 5 | ✓ |
| 四、空间关系详细设计 | Task 4-5 | ✓ |
| 五、难度体系 | Task 5 (difficulty_scorer.py) | ✓ |
| 六、数据格式 | Task 5-6 | ✓ |
| 七、数据划分 | Task 8 | ✓ |
| 八、技术架构 | Task 1-2 | ✓ |
| 九、实验兼容性 | Task 8 | ✓ |
