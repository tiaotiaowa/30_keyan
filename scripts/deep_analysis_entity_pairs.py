#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体对数据格式审查 - 深度分析脚本
针对发现的问题进行详细分析
"""

import json
import os
import sys
from collections import defaultdict, Counter

# 设置控制台输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# 中国坐标范围
CHINA_BOUNDS = {
    'lon_min': 73,
    'lon_max': 135,
    'lat_min': 18,
    'lat_max': 54
}


def analyze_coordinate_issues(file_path: str, file_type: str) -> dict:
    """分析坐标异常问题"""
    print(f"\n{'='*60}")
    print(f"坐标异常深度分析 - {file_type}")
    print(f"{'='*60}")

    issues = []
    entity_with_coord_issues = set()

    with open(file_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            record = json.loads(line)

            for entity_key in ['entity_a', 'entity_b']:
                entity = record.get(entity_key, {})
                centroid = entity.get('centroid')

                if centroid and len(centroid) == 2:
                    lon, lat = centroid
                    try:
                        lon, lat = float(lon), float(lat)

                        is_out_of_bounds = False
                        reasons = []

                        if not (CHINA_BOUNDS['lon_min'] <= lon <= CHINA_BOUNDS['lon_max']):
                            is_out_of_bounds = True
                            reasons.append(f"经度{lon}超出范围")

                        if not (CHINA_BOUNDS['lat_min'] <= lat <= CHINA_BOUNDS['lat_max']):
                            is_out_of_bounds = True
                            reasons.append(f"纬度{lat}超出范围")

                        if is_out_of_bounds:
                            entity_id = entity.get('entity_id', 'N/A')
                            entity_name = entity.get('name_zh', 'N/A')
                            entity_with_coord_issues.add(entity_id)

                            issues.append({
                                'index': idx,
                                'pair_id': record.get('pair_id'),
                                'entity': entity_key,
                                'entity_id': entity_id,
                                'entity_name': entity_name,
                                'centroid': centroid,
                                'type': entity.get('type'),
                                'reasons': reasons
                            })
                    except:
                        pass

    print(f"\n发现 {len(issues)} 个坐标异常问题")
    print(f"涉及 {len(entity_with_coord_issues)} 个不同实体")

    # 按实体ID分组
    issues_by_entity = defaultdict(list)
    for issue in issues:
        issues_by_entity[issue['entity_id']].append(issue)

    print(f"\nTop 10 问题实体:")
    for entity_id, entity_issues in list(issues_by_entity.items())[:10]:
        print(f"  - {entity_id}: {len(entity_issues)}次出现")
        sample = entity_issues[0]
        print(f"    名称: {sample['entity_name']}")
        print(f"    类型: {sample['type']}")
        print(f"    坐标: {sample['centroid']}")
        print(f"    原因: {', '.join(sample['reasons'])}")

    return {
        'total_issues': len(issues),
        'unique_entities': len(entity_with_coord_issues),
        'issues_by_entity': dict(list(issues_by_entity.items())[:10])
    }


def analyze_reference_entity_missing(file_path: str, file_type: str) -> dict:
    """分析reference_entity缺失问题"""
    print(f"\n{'='*60}")
    print(f"reference_entity缺失深度分析 - {file_type}")
    print(f"{'='*60}")

    missing_records = []
    has_ref_records = []
    ref_values = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            record = json.loads(line)

            ref_entity = record.get('reference_entity')

            if ref_entity is None:
                missing_records.append({
                    'index': idx,
                    'pair_id': record.get('pair_id'),
                    'relation': record.get('target_relation'),
                    'entity_a': record.get('entity_a', {}).get('name_zh'),
                    'entity_b': record.get('entity_b', {}).get('name_zh')
                })
            else:
                has_ref_records.append({
                    'pair_id': record.get('pair_id'),
                    'relation': record.get('target_relation'),
                    'ref_entity': ref_entity
                })
                ref_values.append(ref_entity)

    print(f"\n总记录数: {len(missing_records) + len(has_ref_records)}")
    print(f"缺失reference_entity: {len(missing_records)}")
    print(f"有reference_entity: {len(has_ref_records)}")

    # 按关系类型统计缺失情况
    missing_by_relation = defaultdict(int)
    for rec in missing_records:
        missing_by_relation[rec['relation']] += 1

    print(f"\n按关系类型缺失分布:")
    for relation, count in sorted(missing_by_relation.items(), key=lambda x: x[1], reverse=True):
        print(f"  {relation}: {count} 条缺失")

    # 分析有reference_entity的记录中的值分布
    ref_counter = Counter(ref_values)
    print(f"\nreference_entity值分布 (Top 10):")
    for value, count in ref_counter.most_common(10):
        print(f"  {value}: {count}")

    return {
        'total_missing': len(missing_records),
        'total_has_ref': len(has_ref_records),
        'missing_by_relation': dict(missing_by_relation),
        'ref_distribution': dict(ref_counter.most_common(10)),
        'sample_missing': missing_records[:5]
    }


def analyze_pair_id_continuity(file_path: str, file_type: str) -> dict:
    """分析pair_id编号连续性"""
    print(f"\n{'='*60}")
    print(f"pair_id编号连续性分析 - {file_type}")
    print(f"{'='*60}")

    pair_ids = []
    prefix_groups = defaultdict(list)

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            pair_id = record.get('pair_id')
            pair_ids.append(pair_id)

            # 按前缀分组
            prefix = pair_id.split('_')[0] if '_' in pair_id else pair_id
            # 提取数字部分
            num_str = pair_id.split('_')[-1] if '_' in pair_id else pair_id
            try:
                num = int(num_str)
                prefix_groups[prefix].append((pair_id, num))
            except:
                pass

    print(f"\n总记录数: {len(pair_ids)}")
    print(f"唯一pair_id: {len(set(pair_ids))}")

    # 检查重复
    duplicates = [pid for pid in set(pair_ids) if pair_ids.count(pid) > 1]
    if duplicates:
        print(f"重复的pair_id: {duplicates}")
    else:
        print(f"无重复pair_id")

    # 检查每个前缀的连续性
    print(f"\n各前缀编号连续性:")
    for prefix in sorted(prefix_groups.keys()):
        items = prefix_groups[prefix]
        numbers = [num for _, num in items]
        numbers.sort()

        if numbers:
            print(f"\n  {prefix}:")
            print(f"    总数: {len(numbers)}")
            print(f"    范围: {min(numbers)} - {max(numbers)}")

            # 检查连续性
            expected = list(range(min(numbers), max(numbers) + 1))
            missing = set(expected) - set(numbers)

            if missing:
                print(f"    缺失编号: {sorted(list(missing))[:10]}{'...' if len(missing) > 10 else ''}")
            else:
                print(f"    连续性: 完全连续")

    return {
        'total': len(pair_ids),
        'unique': len(set(pair_ids)),
        'duplicates': duplicates,
        'prefix_groups': {k: len(v) for k, v in prefix_groups.items()}
    }


def main():
    positive_path = r"D:\gis_data\output\pairs_positive.jsonl"
    negative_path = r"D:\gis_data\output\pairs_negative.jsonl"

    all_results = {
        'positive': {},
        'negative': {}
    }

    # 正例文件分析
    if os.path.exists(positive_path):
        all_results['positive']['coord'] = analyze_coordinate_issues(positive_path, "正例")
        all_results['positive']['ref'] = analyze_reference_entity_missing(positive_path, "正例")
        all_results['positive']['pair_id'] = analyze_pair_id_continuity(positive_path, "正例")

    # 负例文件分析
    if os.path.exists(negative_path):
        all_results['negative']['coord'] = analyze_coordinate_issues(negative_path, "负例")
        all_results['negative']['ref'] = analyze_reference_entity_missing(negative_path, "负例")
        all_results['negative']['pair_id'] = analyze_pair_id_continuity(negative_path, "负例")

    return all_results


if __name__ == "__main__":
    main()
