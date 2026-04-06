"""
将 entity_database_v3.json 导入 PostGIS，创建 geokr_entity 表
"""
import json
import psycopg2
from shapely.geometry import shape, Point

# 1. 读取实体数据
with open('D:/gis_data/output/entity_database_v3.json', 'r', encoding='utf-8') as f:
    entities = json.load(f)
print(f"读取实体数: {len(entities)}")

# 2. 连接数据库
conn = psycopg2.connect(
    host='localhost', port=5432, dbname='geokd_sr',
    user='postgres', password='19950625'
)
conn.autocommit = False
cur = conn.cursor()

# 3. 删除旧表（如果存在）
cur.execute("DROP TABLE IF EXISTS geokr_entity CASCADE;")
print("已清理旧表")

# 4. 创建新表
cur.execute("""
CREATE TABLE geokr_entity (
    entity_id   VARCHAR(50) PRIMARY KEY,
    type        VARCHAR(30) NOT NULL,
    name_zh     VARCHAR(200) NOT NULL,
    name_en     VARCHAR(200),
    geometry_type VARCHAR(20) NOT NULL,
    centroid    GEOMETRY(Point, 4326) NOT NULL,
    geom        GEOMETRY(Geometry, 4326)
);
""")
print("已创建 geokr_entity 表")

# 5. 创建空间索引
cur.execute("CREATE INDEX idx_geokr_entity_centroid ON geokr_entity USING GIST(centroid);")
cur.execute("CREATE INDEX idx_geokr_entity_geom ON geokr_entity USING GIST(geom);")
cur.execute("CREATE INDEX idx_geokr_entity_type ON geokr_entity(type);")
print("已创建索引")

# 6. 解析并插入数据
inserted = 0
skipped = 0
for e in entities:
    eid = e['entity_id']
    etype = e['type']
    name_zh = e['name_zh']
    name_en = e.get('name_en', '')
    geometry_type = e['geometry_type']
    centroid = e['centroid']  # [lon, lat]

    # 解析 geometry 字段
    g = e.get('geometry')
    geom_wkb = None
    if g is not None:
        try:
            if isinstance(g, list):
                # Point: [lon, lat]
                shapely_geom = Point(g)
            elif isinstance(g, dict):
                shapely_geom = shape(g)
            else:
                shapely_geom = None

            if shapely_geom is not None:
                geom_wkb = shapely_geom.wkb_hex
        except Exception as ex:
            print(f"  跳过 {eid}: geometry解析失败 - {ex}")
            skipped += 1
            continue

    # 插入
    centroid_wkb = Point(centroid).wkb_hex
    if geom_wkb is not None:
        cur.execute(
            "INSERT INTO geokr_entity (entity_id, type, name_zh, name_en, geometry_type, centroid, geom) "
            "VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326), ST_GeomFromText(%s, 4326))",
            (eid, etype, name_zh, name_en, geometry_type,
             Point(centroid).wkt,
             shapely_geom.wkt if geom_wkb else None)
        )
    else:
        cur.execute(
            "INSERT INTO geokr_entity (entity_id, type, name_zh, name_en, geometry_type, centroid, geom) "
            "VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326), NULL)",
            (eid, etype, name_zh, name_en, geometry_type,
             Point(centroid).wkt)
        )
        skipped += 1

    inserted += 1
    if inserted % 300 == 0:
        print(f"  已插入 {inserted}/{len(entities)}...")

conn.commit()
print(f"\n导入完成: 成功 {inserted}, 跳过(null geometry) {skipped}")

# 7. 验证
cur.execute("SELECT count(*) FROM geokr_entity;")
total = cur.fetchone()[0]
print(f"\ngeokr_entity 表总行数: {total}")

cur.execute("""
    SELECT type, count(*) as cnt
    FROM geokr_entity
    GROUP BY type
    ORDER BY cnt DESC;
""")
print("\n各类型统计:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

cur.execute("SELECT count(*) FROM geokr_entity WHERE geom IS NOT NULL;")
has_geom = cur.fetchone()[0]
print(f"\n有geometry的实体: {has_geom}/{total}")

cur.execute("SELECT count(*) FROM geokr_entity WHERE geom IS NULL;")
null_geom = cur.fetchone()[0]
print(f"geometry为NULL: {null_geom}")

conn.close()
print("\n完成!")
