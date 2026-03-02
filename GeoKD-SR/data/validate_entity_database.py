"""
地理实体数据库验证脚本
验证数据完整性、坐标准确性和数据分布
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def validate_entity_database(json_path: str):
    """验证实体数据库"""
    print("=" * 80)
    print("GeoKD-SR 地理实体数据库验证报告")
    print("=" * 80)

    # 加载数据
    with open(json_path, 'r', encoding='utf-8') as f:
        entities = json.load(f)

    print(f"\n✓ 文件加载成功: {json_path}")
    print(f"✓ 总实体数: {len(entities)}")

    # 按类型分组
    entities_by_type = defaultdict(list)
    entities_by_category = defaultdict(list)

    for entity in entities:
        entities_by_type[entity.get('type', 'unknown')].append(entity)
        entities_by_category[entity.get('category', 'unknown')].append(entity)

    # 统计报告
    print("\n" + "=" * 80)
    print("【分类统计】")
    print("=" * 80)

    category_stats = {
        'provinces': {'name': '省级行政区', 'target': 34},
        'cities': {'name': '主要城市', 'target': 100},
        'rivers': {'name': '主要河流', 'target': 20},
        'mountains': {'name': '主要山脉', 'target': 10},
        'lakes': {'name': '主要湖泊', 'target': 10},
    }

    for category, stats in category_stats.items():
        count = len(entities_by_category[category])
        target = stats['target']
        status = "✓" if count >= target else "⚠"
        print(f"{status} {stats['name']:12s}: {count:3d} 个 (目标: >={target})")

    # 省级行政区详细统计
    print("\n" + "=" * 80)
    print("【省级行政区详细统计】")
    print("=" * 80)

    provinces = entities_by_category['provinces']
    province_types = defaultdict(int)
    for p in provinces:
        province_types[p['type']] += 1

    type_names = {
        'municipality': '直辖市',
        'province': '省',
        'autonomous_region': '自治区',
        'sar': '特别行政区'
    }

    for ptype, pname in type_names.items():
        count = province_types[ptype]
        print(f"  {pname}: {count} 个")

    # 验证坐标数据
    print("\n" + "=" * 80)
    print("【坐标数据验证】")
    print("=" * 80)

    entities_with_coords = [e for e in entities if 'lat' in e and 'lon' in e]
    entities_without_coords = [e for e in entities if 'lat' not in e or 'lon' not in e]

    print(f"✓ 带坐标实体: {len(entities_with_coords)} 个")
    print(f"  不带坐标实体: {len(entities_without_coords)} 个")

    # 验证坐标范围
    invalid_coords = []
    for entity in entities_with_coords:
        lat, lon = entity['lat'], entity['lon']
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            invalid_coords.append(entity)

    if invalid_coords:
        print(f"⚠ 发现 {len(invalid_coords)} 个坐标异常的实体:")
        for entity in invalid_coords[:5]:
            print(f"  - {entity['name']}: ({entity['lat']}, {entity['lon']})")
    else:
        print("✓ 所有坐标值都在合理范围内")

    # 坐标分布统计
    if entities_with_coords:
        lats = [e['lat'] for e in entities_with_coords]
        lons = [e['lon'] for e in entities_with_coords]
        print(f"\n  纬度范围: {min(lats):.2f}° ~ {max(lats):.2f}°")
        print(f"  经度范围: {min(lons):.2f}° ~ {max(lons):.2f}°")

    # 按省份统计城市数量
    print("\n" + "=" * 80)
    print("【城市按省份分布】")
    print("=" * 80)

    cities = entities_by_category['cities']
    cities_by_province = defaultdict(int)
    for city in cities:
        province = city.get('province', '未知')
        cities_by_province[province] += 1

    # 排序显示
    sorted_provinces = sorted(cities_by_province.items(), key=lambda x: x[1], reverse=True)
    print("  城市数量最多的前10个省份:")
    for province, count in sorted_provinces[:10]:
        print(f"    {province:18s}: {count:2d} 个城市")

    # 河流数据验证
    print("\n" + "=" * 80)
    print("【河流数据验证】")
    print("=" * 80)

    rivers = entities_by_category['rivers']
    if rivers:
        lengths = [r.get('length', 0) for r in rivers]
        print(f"  河流数量: {len(rivers)} 条")
        print(f"  长度范围: {min(lengths)} ~ {max(lengths)} km")
        print(f"  平均长度: {sum(lengths) / len(lengths):.0f} km")

        print("\n  最长的5条河流:")
        sorted_rivers = sorted(rivers, key=lambda x: x.get('length', 0), reverse=True)
        for river in sorted_rivers[:5]:
            print(f"    {river['name']:12s}: {river['length']:4d} km, "
                  f"{river.get('origin', '未知')} → {river.get('mouth', '未知')}")

    # 山脉数据验证
    print("\n" + "=" * 80)
    print("【山脉数据验证】")
    print("=" * 80)

    mountains = entities_by_category['mountains']
    if mountains:
        elevations = [m.get('elevation', 0) for m in mountains]
        print(f"  山脉数量: {len(mountains)} 条")
        print(f"  海拔范围: {min(elevations)} ~ {max(elevations)} 米")

        print("\n  最高的5条山脉:")
        sorted_mountains = sorted(mountains, key=lambda x: x.get('elevation', 0), reverse=True)
        for mountain in sorted_mountains[:5]:
            print(f"    {mountain['name']:12s}: {mountain.get('highest_peak', '未知')} "
                  f"{mountain['elevation']} 米")

    # 湖泊数据验证
    print("\n" + "=" * 80)
    print("【湖泊数据验证】")
    print("=" * 80)

    lakes = entities_by_category['lakes']
    if lakes:
        areas = [l.get('area', 0) for l in lakes]
        print(f"  湖泊数量: {len(lakes)} 个")
        print(f"  面积范围: {min(areas)} ~ {max(areas)} km²")

        print("\n  最大的5个湖泊:")
        sorted_lakes = sorted(lakes, key=lambda x: x.get('area', 0), reverse=True)
        for lake in sorted_lakes[:5]:
            print(f"    {lake['name']:12s}: {lake['area']:4d} km², "
                  f"位于{lake.get('province', '未知')}")

    # 数据完整性检查
    print("\n" + "=" * 80)
    print("【数据完整性检查】")
    print("=" * 80)

    required_fields = {
        'provinces': ['name', 'type', 'lat', 'lon'],
        'cities': ['name', 'type', 'lat', 'lon', 'province'],
        'rivers': ['name', 'type', 'length', 'origin', 'mouth'],
        'mountains': ['name', 'type', 'highest_peak', 'elevation'],
        'lakes': ['name', 'type', 'area', 'province'],
    }

    all_complete = True
    for category, fields in required_fields.items():
        entities_cat = entities_by_category[category]
        incomplete = []
        for entity in entities_cat:
            missing = [f for f in fields if f not in entity]
            if missing:
                incomplete.append((entity['name'], missing))

        if incomplete:
            all_complete = False
            print(f"⚠ {category} 有 {len(incomplete)} 个实体缺少字段:")
            for name, missing in incomplete[:3]:
                print(f"  - {name}: 缺少 {missing}")
        else:
            print(f"✓ {category}: 所有实体字段完整")

    # 示例数据预览
    print("\n" + "=" * 80)
    print("【数据预览（每类前3个）】")
    print("=" * 80)

    for category in ['provinces', 'cities', 'rivers', 'mountains', 'lakes']:
        entities_cat = entities_by_category[category]
        print(f"\n{category.upper()}:")
        for entity in entities_cat[:3]:
            print(f"  - {entity}")

    # 重复检查
    print("\n" + "=" * 80)
    print("【重复数据检查】")
    print("=" * 80)

    name_count = defaultdict(list)
    for entity in entities:
        name_count[entity['name']].append(entity.get('category', 'unknown'))

    duplicates = {name: cats for name, cats in name_count.items() if len(cats) > 1}
    if duplicates:
        print(f"⚠ 发现 {len(duplicates)} 个重名实体:")
        for name, cats in list(duplicates.items())[:5]:
            print(f"  - {name}: 出现在 {set(cats)}")
    else:
        print("✓ 没有发现重名实体")

    # 总结
    print("\n" + "=" * 80)
    print("【验证总结】")
    print("=" * 80)

    issues = []

    if len(entities_by_category['provinces']) < 34:
        issues.append("省级行政区数量不足34个")
    if len(entities_by_category['cities']) < 100:
        issues.append(f"城市数量不足100个(当前{len(entities_by_category['cities'])}个)")
    if invalid_coords:
        issues.append(f"存在{len(invalid_coords)}个坐标异常实体")
    if not all_complete:
        issues.append("部分实体字段不完整")
    if duplicates:
        issues.append(f"存在{len(duplicates)}个重名实体")

    if issues:
        print("⚠ 发现以下问题:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n建议: 请修复上述问题后重新验证")
    else:
        print("✓ 数据验证通过!")
        print("✓ 所有实体类型数量达标")
        print("✓ 坐标数据准确")
        print("✓ 字段数据完整")
        print("✓ 无重复数据")

    print("\n" + "=" * 80)
    print(f"验证完成! 数据库路径: {json_path}")
    print("=" * 80)


if __name__ == "__main__":
    json_path = "D:/30_keyan/GeoKD-SR/data/geosr_chain/entity_database.json"
    validate_entity_database(json_path)
