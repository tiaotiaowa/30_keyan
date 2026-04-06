"""
从 PostGIS geoatlas_province / geoatlas_city 提取完整geometry，
更新 entity_database_v3.json 中对应实体的 geometry 字段，
同时更新 geokr_entity 表。
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import psycopg2
from shapely.geometry import shape, Point, mapping

# 1. 读取当前 JSON
json_path = 'D:/gis_data/output/entity_database_v3.json'
with open(json_path, 'r', encoding='utf-8') as f:
    entities = json.load(f)
print(f"读取实体: {len(entities)}")

# 2. 建立 name -> entity 映射 (province + city)
name_map = {}
for e in entities:
    if e['type'] in ('province', 'city'):
        name_map[e['name_zh']] = e

# 3. 连接 PostGIS
conn = psycopg2.connect(host='localhost', port=5432, dbname='geokd_sr',
                        user='postgres', password='19950625')
cur = conn.cursor()

# 4. 从 geoatlas_province 提取完整 geometry
cur.execute("SELECT name, ST_AsGeoJSON(geometry) FROM geoatlas_province;")
province_rows = cur.fetchall()
print(f"\ngeoatlas_province 记录: {len(province_rows)}")

updated_province = 0
for name, geojson_str in province_rows:
    if name in name_map:
        old_geom = name_map[name].get('geometry')
        old_pts = len(str(old_geom)) if old_geom else 0
        new_geom = json.loads(geojson_str)
        name_map[name]['geometry'] = new_geom
        new_pts = len(str(new_geom))
        updated_province += 1

print(f"更新省份 geometry: {updated_province}")

# 5. 从 geoatlas_city 提取完整 geometry
cur.execute("SELECT name, ST_AsGeoJSON(geometry) FROM geoatlas_city;")
city_rows = cur.fetchall()
print(f"geoatlas_city 记录: {len(city_rows)}")

updated_city = 0
for name, geojson_str in city_rows:
    if name in name_map:
        new_geom = json.loads(geojson_str)
        name_map[name]['geometry'] = new_geom
        updated_city += 1

print(f"更新城市 geometry: {updated_city}")

# 6. 删除已不存在的3条澳门堂区（之前已从geokr_entity删除）
before = len(entities)
entities = [e for e in entities if not (e['type'] == 'city' and e.get('geometry') is None)]
after = len(entities)
print(f"\n移除无geometry实体: {before - after} 条")

# 7. 重新编号 entity_id（按type分组，与geokr_entity表一致）
from collections import defaultdict
type_counters = defaultdict(int)
for e in sorted(entities, key=lambda x: (x['type'], x.get('entity_id', ''))):
    type_counters[e['type']] += 1
    e['entity_id'] = f"{e['type']}_{type_counters[e['type']]:04d}"

# 8. 保存更新后的 JSON
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(entities, f, ensure_ascii=False, indent=2)

print(f"\n已保存更新后的 JSON: {json_path}")
print(f"总实体数: {len(entities)}")

# 9. 同步更新 geokr_entity 表
conn.autocommit = False
cur2 = conn.cursor()

# 先更新 geometry
updated_db = 0
for name, geojson_str in province_rows:
    if name in name_map:
        eid = name_map[name]['entity_id']
        cur2.execute("UPDATE geokr_entity SET geom = ST_GeomFromGeoJSON(%s) WHERE entity_id = %s;",
                     (geojson_str, eid))
        updated_db += cur2.rowcount

for name, geojson_str in city_rows:
    if name in name_map:
        eid = name_map[name]['entity_id']
        cur2.execute("UPDATE geokr_entity SET geom = ST_GeomFromGeoJSON(%s) WHERE entity_id = %s;",
                     (geojson_str, eid))
        updated_db += cur2.rowcount

conn.commit()
print(f"\ngeokr_entity 表 geometry 更新: {updated_db} 条")

# 10. 验证
cur.execute("""
    SELECT 'province' as type, count(*),
           sum(ST_NPoints(geom)) as total_pts
    FROM geokr_entity WHERE type='province'
    UNION ALL
    SELECT 'city', count(*), sum(ST_NPoints(geom))
    FROM geokr_entity WHERE type='city';
""")
print("\n=== 更新后验证 ===")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}条, 总点数={r[2]}")

# 对比更新前后
cur.execute("""
    SELECT a.name,
           ST_NPoints(a.geometry) as atlas_pts,
           ST_NPoints(b.geom) as new_pts
    FROM geoatlas_province a
    JOIN geokr_entity b ON a.name = b.name_zh AND b.type='province'
    LIMIT 5;
""")
print("\n=== 省份更新后对比 ===")
for r in cur.fetchall():
    match = '✓' if r[1] == r[2] else '✗'
    print(f"  {r[0]}: atlas={r[1]}, new={r[2]} {match}")

conn.close()
print("\n完成!")
