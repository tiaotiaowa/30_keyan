#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体对数据质量审查脚本
检查正例和负例数据中的潜在问题
"""

import json
import os
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Any
import sys


def load_jsonl(file_path: str) -> List[Dict]:
    """加载JSONL文件"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def check_duplicates(data: List[Dict]) -> Dict[str, Any]:
    """检查重复数据"""
    print("\n" + "="*60)
    print("1. 重复检测")
    print("="*60)

    # 按关系类型分组 - 使用target_relation字段
    by_relation = defaultdict(list)
    for idx, record in enumerate(data):
        # 优先使用target_relation，如果没有则使用relation.type
        rel_type = record.get('target_relation', record.get('relation', {}).get('type', 'unknown'))
        by_relation[rel_type].append((idx, record))

    results = {
        'unordered_duplicates': {},
        'ordered_duplicates': {},
        'total_duplicates': 0
    }

    # 无序关系检查
    unordered_relations = ['intersects', 'touches', 'overlaps']

    for rel_type in unordered_relations:
        if rel_type not in by_relation:
            continue

        seen = defaultdict(list)
        for idx, record in by_relation[rel_type]:
            a_id = record.get('entity_a', {}).get('entity_id')
            b_id = record.get('entity_b', {}).get('entity_id')
            if a_id and b_id:
                key = frozenset({a_id, b_id})
                seen[key].append(idx)

        duplicates = {k: v for k, v in seen.items() if len(v) > 1}
        if duplicates:
            results['unordered_duplicates'][rel_type] = duplicates
            print(f"\n{rel_type}: 发现 {len(duplicates)} 组重复")
            # 显示前3个样例
            for i, (key, indices) in enumerate(list(duplicates.items())[:3]):
                print(f"  样例{i+1}: {key} -> 出现 {len(indices)} 次 (索引: {indices[:5]}...)")

    # 有序关系检查
    ordered_relations = ['contains', 'within', 'crosses']

    for rel_type in ordered_relations:
        if rel_type not in by_relation:
            continue

        seen = defaultdict(list)
        for idx, record in by_relation[rel_type]:
            a_id = record.get('entity_a', {}).get('entity_id')
            b_id = record.get('entity_b', {}).get('entity_id')
            if a_id and b_id:
                key = (a_id, b_id)  # 有序对
                seen[key].append(idx)

        duplicates = {k: v for k, v in seen.items() if len(v) > 1}
        if duplicates:
            results['ordered_duplicates'][rel_type] = duplicates
            print(f"\n{rel_type}: 发现 {len(duplicates)} 组重复")
            for i, (key, indices) in enumerate(list(duplicates.items())[:3]):
                print(f"  样例{i+1}: ({key[0]}, {key[1]}) -> 出现 {len(indices)} 次")

    # 统计总重复数
    total_unordered = sum(len(v) for v in results['unordered_duplicates'].values())
    total_ordered = sum(len(v) for v in results['ordered_duplicates'].values())
    results['total_duplicates'] = total_unordered + total_ordered

    print(f"\n总计: {total_unordered} 组无序重复 + {total_ordered} 组有序重复 = {results['total_duplicates']} 组")

    return results


def check_reflexive(data: List[Dict]) -> List[Dict]:
    """检查自反关系 (entity_a.entity_id == entity_b.entity_id)"""
    print("\n" + "="*60)
    print("2. 自反检测")
    print("="*60)

    reflexive_cases = []
    for idx, record in enumerate(data):
        a_id = record.get('entity_a', {}).get('entity_id')
        b_id = record.get('entity_b', {}).get('entity_id')
        if a_id and b_id and a_id == b_id:
            reflexive_cases.append({
                'index': idx,
                'entity_id': a_id,
                'record': record
            })

    print(f"发现 {len(reflexive_cases)} 条自反记录")

    if reflexive_cases:
        print("\n前5个样例:")
        for case in reflexive_cases[:5]:
            print(f"  索引 {case['index']}: {case['entity_id']}")
            print(f"    关系: {case['record'].get('relation', {}).get('type', 'unknown')}")

    return reflexive_cases


def check_positive_negative_overlap(positive: List[Dict], negative: List[Dict]) -> Dict[str, Any]:
    """检查正负例重叠"""
    print("\n" + "="*60)
    print("3. 正负例重叠检测")
    print("="*60)

    # 构建正例索引 (按关系类型)
    positive_by_relation = defaultdict(set)
    for record in positive:
        a_id = record.get('entity_a', {}).get('entity_id')
        b_id = record.get('entity_b', {}).get('entity_id')
        rel_type = record.get('target_relation', record.get('relation', {}).get('type', 'unknown'))
        if a_id and b_id:
            # 无序关系使用frozenset
            if rel_type in ['intersects', 'touches', 'overlaps', 'directional']:
                # directional也是无序的（A相对于B的方向）
                key = frozenset({a_id, b_id})
            else:
                key = (a_id, b_id)
            positive_by_relation[rel_type].add(key)

    # 检查负例中的重叠
    overlaps_by_relation = defaultdict(list)
    for idx, record in enumerate(negative):
        a_id = record.get('entity_a', {}).get('entity_id')
        b_id = record.get('entity_b', {}).get('entity_id')
        rel_type = record.get('target_relation', record.get('relation', {}).get('type', 'unknown'))
        if a_id and b_id:
            if rel_type in ['intersects', 'touches', 'overlaps', 'directional']:
                key = frozenset({a_id, b_id})
            else:
                key = (a_id, b_id)

            if key in positive_by_relation.get(rel_type, set()):
                overlaps_by_relation[rel_type].append({
                    'index': idx,
                    'key': key,
                    'record': record
                })

    total_overlaps = sum(len(v) for v in overlaps_by_relation.values())
    print(f"发现 {total_overlaps} 条重叠记录")

    for rel_type, cases in overlaps_by_relation.items():
        print(f"\n{rel_type}: {len(cases)} 条重叠")
        if cases:
            print("  前3个样例:")
            for case in cases[:3]:
                print(f"    {case['key']}")

    return {
        'overlaps_by_relation': dict(overlaps_by_relation),
        'total_overlaps': total_overlaps
    }


def check_missing_values(data: List[Dict]) -> Dict[str, Any]:
    """检查缺失值"""
    print("\n" + "="*60)
    print("4. 缺失值检测")
    print("="*60)

    missing_stats = {
        'name_zh_empty': [],
        'name_en_empty': [],
        'geometry_type_empty': [],
        'centroid_none': []
    }

    for idx, record in enumerate(data):
        # 检查 entity_a
        entity_a = record.get('entity_a', {})
        if not entity_a.get('name_zh'):
            missing_stats['name_zh_empty'].append(('entity_a', idx))
        if not entity_a.get('name_en'):
            missing_stats['name_en_empty'].append(('entity_a', idx))
        if not entity_a.get('geometry_type'):
            missing_stats['geometry_type_empty'].append(('entity_a', idx))
        centroid_a = entity_a.get('centroid')
        # centroid是列表 [lon, lat]
        if not centroid_a or (isinstance(centroid_a, list) and len(centroid_a) < 2):
            missing_stats['centroid_none'].append(('entity_a', idx, centroid_a))

        # 检查 entity_b
        entity_b = record.get('entity_b', {})
        if not entity_b.get('name_zh'):
            missing_stats['name_zh_empty'].append(('entity_b', idx))
        if not entity_b.get('name_en'):
            missing_stats['name_en_empty'].append(('entity_b', idx))
        if not entity_b.get('geometry_type'):
            missing_stats['geometry_type_empty'].append(('entity_b', idx))
        centroid_b = entity_b.get('centroid')
        if not centroid_b or (isinstance(centroid_b, list) and len(centroid_b) < 2):
            missing_stats['centroid_none'].append(('entity_b', idx, centroid_b))

    for field, cases in missing_stats.items():
        print(f"\n{field}: {len(cases)} 条")
        if cases and len(cases) <= 10:
            for case in cases[:5]:
                print(f"  {case}")

    return missing_stats


def check_data_consistency(data: List[Dict]) -> Dict[str, Any]:
    """检查数据一致性"""
    print("\n" + "="*60)
    print("5. 数据一致性检测")
    print("="*60)

    # 收集每个entity_id的属性
    entity_records = defaultdict(lambda: {
        'name_zh': set(),
        'name_en': set(),
        'centroid': set(),
        'type': set(),
        'indices': []
    })

    for idx, record in enumerate(data):
        for entity_key in ['entity_a', 'entity_b']:
            entity = record.get(entity_key, {})
            entity_id = entity.get('entity_id')
            if entity_id:
                entity_records[entity_id]['name_zh'].add(entity.get('name_zh', ''))
                entity_records[entity_id]['name_en'].add(entity.get('name_en', ''))
                entity_records[entity_id]['type'].add(entity.get('type', ''))
                centroid = entity.get('centroid')
                # centroid是列表 [lon, lat]
                if centroid and isinstance(centroid, list) and len(centroid) >= 2:
                    entity_records[entity_id]['centroid'].add((centroid[1], centroid[0]))  # (lat, lon)
                entity_records[entity_id]['indices'].append(idx)

    # 检查不一致
    inconsistencies = {
        'name_zh': [],
        'name_en': [],
        'centroid': [],
        'type': []
    }

    for entity_id, records in entity_records.items():
        if len(records['name_zh']) > 1:
            inconsistencies['name_zh'].append({
                'entity_id': entity_id,
                'names': records['name_zh']
            })
        if len(records['name_en']) > 1:
            inconsistencies['name_en'].append({
                'entity_id': entity_id,
                'names': records['name_en']
            })
        if len(records['centroid']) > 1:
            inconsistencies['centroid'].append({
                'entity_id': entity_id,
                'centroids': list(records['centroid'])
            })
        if len(records['type']) > 1:
            inconsistencies['type'].append({
                'entity_id': entity_id,
                'types': records['type']
            })

    for field, cases in inconsistencies.items():
        print(f"\n{field} 不一致: {len(cases)} 个实体")
        if cases:
            print("  前3个样例:")
            for case in cases[:3]:
                print(f"    {case['entity_id']}: {case.get('names') or case.get('centroids') or case.get('types')}")

    return inconsistencies


def check_boundary_cases(data: List[Dict]) -> Dict[str, Any]:
    """检查边界案例"""
    print("\n" + "="*60)
    print("6. 边界案例检测")
    print("="*60)

    # distance_km == 0
    zero_distance = []
    distances = []
    same_type_pairs = []

    for idx, record in enumerate(data):
        distance = record.get('distance_km')
        if distance is not None:
            distances.append(distance)
            if distance == 0:
                zero_distance.append(idx)

        # 同类型实体对
        entity_a = record.get('entity_a', {})
        entity_b = record.get('entity_b', {})
        if entity_a.get('type') == entity_b.get('type'):
            same_type_pairs.append({
                'index': idx,
                'type': entity_a.get('type'),
                'a_id': entity_a.get('entity_id'),
                'b_id': entity_b.get('entity_id')
            })

    # 同类型分布
    type_dist = Counter(p['type'] for p in same_type_pairs)

    # 距离极端值
    if distances:
        distances_sorted = sorted(distances)
        min_distances = distances_sorted[:10]
        max_distances = distances_sorted[-10:]

        print(f"\ndistance_km == 0: {len(zero_distance)} 条")
        print(f"\n距离最小值 (top 10): {min_distances}")
        print(f"\n距离最大值 (top 10): {max_distances}")
        print(f"\n平均距离: {sum(distances)/len(distances):.2f} km")

    print(f"\n同类型实体对: {len(same_type_pairs)} 条")
    print("\n按类型分布:")
    for type_name, count in type_dist.most_common():
        print(f"  {type_name}: {count}")

    return {
        'zero_distance_count': len(zero_distance),
        'zero_distance_indices': zero_distance[:20],  # 只保存前20个
        'min_distances': distances[:10] if distances else [],
        'max_distances': distances[-10:] if distances else [],
        'same_type_pairs_count': len(same_type_pairs),
        'same_type_distribution': dict(type_dist)
    }


def check_negative_specifics(negative: List[Dict]) -> Dict[str, Any]:
    """检查负例特有问题"""
    print("\n" + "="*60)
    print("7. 负例特别检查")
    print("="*60)

    issues = {
        'missing_reference': [],
        'spatial_facts_not_false': [],
        'c4_field_combinations': defaultdict(int)
    }

    for idx, record in enumerate(negative):
        # reference_entity检查
        if not record.get('reference_entity'):
            issues['missing_reference'].append(idx)

        # spatial_facts检查
        spatial_facts = record.get('spatial_facts', {})
        for key, value in spatial_facts.items():
            if value is not False:  # 负例中应该都是False
                issues['spatial_facts_not_false'].append({
                    'index': idx,
                    'key': key,
                    'value': value
                })

        # C4负例检查 (同时含direction+distance+within)
        has_direction = 'direction' in record and record['direction'] is not None
        has_distance = 'distance_km' in record and record['distance_km'] is not None
        has_within = 'within_km' in record and record['within_km'] is not None

        if has_direction and has_distance and has_within:
            issues['c4_field_combinations']['all_three'] += 1
        elif has_direction and has_distance:
            issues['c4_field_combinations']['direction+distance'] += 1
        elif has_direction and has_within:
            issues['c4_field_combinations']['direction+within'] += 1
        elif has_distance and has_within:
            issues['c4_field_combinations']['distance+within'] += 1

    print(f"\n缺少reference_entity: {len(issues['missing_reference'])} 条")
    print(f"\nspatial_facts非False的值: {len(issues['spatial_facts_not_false'])} 条")
    if issues['spatial_facts_not_false']:
        print("  样例:")
        for case in issues['spatial_facts_not_false'][:5]:
            print(f"    索引{case['index']}: {case['key']}={case['value']}")

    print(f"\nC4负例字段组合:")
    for combo, count in issues['c4_field_combinations'].items():
        print(f"  {combo}: {count}")

    return issues


def check_dataset_stats(positive: List[Dict], negative: List[Dict],
                       positive_path: str, negative_path: str) -> Dict[str, Any]:
    """检查数据集统计信息"""
    print("\n" + "="*60)
    print("8. 数据集统计")
    print("="*60)

    # 文件大小
    pos_size = os.path.getsize(positive_path)
    neg_size = os.path.getsize(negative_path)
    total_size = pos_size + neg_size

    # 实体统计
    all_entities = set()
    for record in positive + negative:
        a_id = record.get('entity_a', {}).get('entity_id')
        b_id = record.get('entity_b', {}).get('entity_id')
        if a_id:
            all_entities.add(a_id)
        if b_id:
            all_entities.add(b_id)

    # 平均记录大小
    pos_avg_size = pos_size / len(positive) if positive else 0
    neg_avg_size = neg_size / len(negative) if negative else 0

    print(f"\n文件大小:")
    print(f"  正例: {pos_size:,} bytes ({pos_size/1024/1024:.2f} MB)")
    print(f"  负例: {neg_size:,} bytes ({neg_size/1024/1024:.2f} MB)")
    print(f"  总计: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")

    print(f"\n记录数:")
    print(f"  正例: {len(positive):,} 条 ({len(positive)/(len(positive)+len(negative))*100:.1f}%)")
    print(f"  负例: {len(negative):,} 条 ({len(negative)/(len(positive)+len(negative))*100:.1f}%)")
    print(f"  总计: {len(positive)+len(negative):,} 条")

    print(f"\n唯一实体数: {len(all_entities):,}")

    print(f"\n平均记录大小:")
    print(f"  正例: {pos_avg_size:.2f} bytes")
    print(f"  负例: {neg_avg_size:.2f} bytes")

    return {
        'positive_size_mb': pos_size / 1024 / 1024,
        'negative_size_mb': neg_size / 1024 / 1024,
        'positive_count': len(positive),
        'negative_count': len(negative),
        'positive_percentage': len(positive) / (len(positive) + len(negative)) * 100,
        'unique_entities': len(all_entities),
        'avg_positive_size_bytes': pos_avg_size,
        'avg_negative_size_bytes': neg_avg_size
    }


def main():
    """主函数"""
    print("实体对数据质量审查")
    print("="*60)

    # 数据路径
    positive_path = r"D:\gis_data\output\pairs_positive.jsonl"
    negative_path = r"D:\gis_data\output\pairs_negative.jsonl"

    # 加载数据
    print("正在加载数据...")
    positive = load_jsonl(positive_path)
    negative = load_jsonl(negative_path)

    print(f"正例: {len(positive)} 条")
    print(f"负例: {len(negative)} 条")

    # 执行所有检查
    results = {
        'positive_duplicates': check_duplicates(positive),
        'negative_duplicates': check_duplicates(negative),
        'positive_reflexive': check_reflexive(positive),
        'negative_reflexive': check_reflexive(negative),
        'overlap': check_positive_negative_overlap(positive, negative),
        'positive_missing': check_missing_values(positive),
        'negative_missing': check_missing_values(negative),
        'positive_consistency': check_data_consistency(positive),
        'negative_consistency': check_data_consistency(negative),
        'positive_boundary': check_boundary_cases(positive),
        'negative_boundary': check_boundary_cases(negative),
        'negative_specific': check_negative_specifics(negative),
        'stats': check_dataset_stats(positive, negative, positive_path, negative_path)
    }

    # 保存结果到JSON
    output_path = r"D:\30_keyan\scripts\data_quality_report.json"
    # 转换不可序列化的类型
    def make_serializable(obj):
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        elif isinstance(obj, defaultdict):
            return dict(obj)
        elif isinstance(obj, tuple):
            return str(obj)
        elif isinstance(obj, list):
            return [make_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        else:
            return obj

    serializable_results = make_serializable(results)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, ensure_ascii=False, indent=2)

    print(f"\n详细结果已保存到: {output_path}")

    # 生成摘要
    print("\n" + "="*60)
    print("审查摘要")
    print("="*60)
    print(f"1. 正例重复: {results['positive_duplicates']['total_duplicates']} 组")
    print(f"2. 负例重复: {results['negative_duplicates']['total_duplicates']} 组")
    print(f"3. 正例自反: {len(results['positive_reflexive'])} 条")
    print(f"4. 负例自反: {len(results['negative_reflexive'])} 条")
    print(f"5. 正负例重叠: {results['overlap']['total_overlaps']} 条")
    print(f"6. 正例name_zh缺失: {len(results['positive_missing']['name_zh_empty'])} 条")
    print(f"7. 负例name_zh缺失: {len(results['negative_missing']['name_zh_empty'])} 条")
    print(f"8. 正例centroid缺失: {len(results['positive_missing']['centroid_none'])} 条")
    print(f"9. 负例centroid缺失: {len(results['negative_missing']['centroid_none'])} 条")
    print(f"10. 正例name不一致: {len(results['positive_consistency']['name_zh'])} 个实体")
    print(f"11. 负例name不一致: {len(results['negative_consistency']['name_zh'])} 个实体")
    print(f"12. 正例零距离: {results['positive_boundary']['zero_distance_count']} 条")
    print(f"13. 负例零距离: {results['negative_boundary']['zero_distance_count']} 条")
    print(f"14. 负例缺少reference: {len(results['negative_specific']['missing_reference'])} 条")
    print(f"15. spatial_facts非False: {len(results['negative_specific']['spatial_facts_not_false'])} 条")


if __name__ == '__main__':
    main()
