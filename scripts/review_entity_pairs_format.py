#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体对数据格式完整性审查脚本
检查正例和负例数据的格式规范性
"""

import json
import os
import sys
from collections import defaultdict, Counter
from typing import Dict, List, Any, Tuple, Set

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

# 关系类型及其必需字段
RELATION_FIELDS = {
    'directional': ['direction_8', 'direction_8_en', 'azimuth_deg'],
    'metric': ['distance_km'],
    'contains': ['contains'],
    'within': ['within'],
    'touches': ['touches'],
    'crosses': ['crosses'],
    'disjoint': ['disjoint'],
    'C1': ['direction_8', 'direction_8_en', 'azimuth_deg', 'distance_km'],  # composite.direction_distance
    'C2': ['direction_8', 'direction_8_en', 'azimuth_deg', 'within'],  # composite.direction_topology
    'C3': ['distance_km', 'within'],  # composite.distance_topology
    'C4': ['direction_8', 'direction_8_en', 'azimuth_deg', 'distance_km', 'within'],  # composite.direction_distance_topology
}

# 基础必需字段
BASE_REQUIRED_FIELDS = ['pair_id', 'target_relation', 'entity_a', 'entity_b', 'spatial_facts']

# 实体必需子字段
ENTITY_REQUIRED_FIELDS = ['entity_id', 'type', 'name_zh', 'name_en', 'geometry_type', 'centroid']


class DataReviewer:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = []
        self.errors = defaultdict(list)
        self.warnings = defaultdict(list)
        self.stats = defaultdict(int)

    def load_data(self) -> bool:
        """加载JSONL数据"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        self.data.append(record)
                    except json.JSONDecodeError as e:
                        self.errors['json_parse'].append({
                            'line': line_num,
                            'error': str(e),
                            'content': line[:100]
                        })
            print(f"[OK] 成功加载 {len(self.data)} 条记录")
            return True
        except Exception as e:
            print(f"[ERROR] 文件加载失败: {e}")
            return False

    def check_base_fields(self) -> Dict:
        """检查1: 基础必需字段"""
        missing_fields = []
        for idx, record in enumerate(self.data):
            for field in BASE_REQUIRED_FIELDS:
                if field not in record:
                    missing_fields.append({
                        'index': idx,
                        'pair_id': record.get('pair_id', 'N/A'),
                        'missing': field
                    })

        passed = len(self.data) - len(missing_fields)
        return {
            'check': '基础必需字段(pair_id, target_relation, entity_a, entity_b, spatial_facts)',
            'total': len(self.data),
            'passed': passed,
            'failed': len(missing_fields),
            'pass_rate': f"{passed/len(self.data)*100:.2f}%",
            'samples': missing_fields[:5]
        }

    def check_entity_subfields(self) -> Dict:
        """检查2: 实体子字段完整性"""
        entity_issues = []

        for idx, record in enumerate(self.data):
            for entity_key in ['entity_a', 'entity_b']:
                entity = record.get(entity_key, {})
                if not isinstance(entity, dict):
                    entity_issues.append({
                        'index': idx,
                        'pair_id': record.get('pair_id', 'N/A'),
                        'entity': entity_key,
                        'issue': '不是字典类型'
                    })
                    continue

                for field in ENTITY_REQUIRED_FIELDS:
                    if field not in entity:
                        entity_issues.append({
                            'index': idx,
                            'pair_id': record.get('pair_id', 'N/A'),
                            'entity': entity_key,
                            'missing_field': field
                        })

        passed = len(self.data) * 2 - len(entity_issues)
        return {
            'check': '实体子字段(entity_id, type, name_zh, name_en, geometry_type, centroid)',
            'total': len(self.data) * 2,  # 每条记录有2个实体
            'passed': passed,
            'failed': len(entity_issues),
            'pass_rate': f"{passed/(len(self.data)*2)*100:.2f}%",
            'samples': entity_issues[:5]
        }

    def check_spatial_facts_by_relation(self) -> Dict:
        """检查3: spatial_facts字段按关系类型正确设置"""
        spatial_issues = []

        for idx, record in enumerate(self.data):
            target_relation = record.get('target_relation', '')
            spatial_facts = record.get('spatial_facts', {})

            if not isinstance(spatial_facts, dict):
                spatial_issues.append({
                    'index': idx,
                    'pair_id': record.get('pair_id', 'N/A'),
                    'target_relation': target_relation,
                    'issue': 'spatial_facts不是字典类型'
                })
                continue

            # 确定需要检查的字段
            required_fields = []
            relation_lower = target_relation.lower()

            if 'directional' in relation_lower or 'direction_distance' in relation_lower or 'c1' in relation_lower:
                required_fields.extend(['direction_8', 'direction_8_en', 'azimuth_deg'])
            if 'metric' in relation_lower or 'distance' in relation_lower:
                required_fields.append('distance_km')
            if 'topology' in relation_lower or 'within' in relation_lower or 'c2' in relation_lower or 'c3' in relation_lower or 'c4' in relation_lower:
                required_fields.append('within')

            # 处理特定的拓扑关系
            if 'contains' in relation_lower:
                required_fields.append('contains')
            if 'touches' in relation_lower:
                required_fields.append('touches')
            if 'crosses' in relation_lower:
                required_fields.append('crosses')
            if 'disjoint' in relation_lower:
                required_fields.append('disjoint')

            # 检查必需字段是否存在
            for field in set(required_fields):
                if field not in spatial_facts:
                    spatial_issues.append({
                        'index': idx,
                        'pair_id': record.get('pair_id', 'N/A'),
                        'target_relation': target_relation,
                        'missing_field': field
                    })

        passed = len(self.data) - len(spatial_issues)
        return {
            'check': 'spatial_facts字段按关系类型正确设置',
            'total': len(self.data),
            'passed': passed,
            'failed': len(spatial_issues),
            'pass_rate': f"{passed/len(self.data)*100:.2f}%",
            'samples': spatial_issues[:5]
        }

    def check_pair_id_uniqueness(self) -> Dict:
        """检查4: pair_id编号唯一性"""
        pair_ids = []
        duplicates = []

        for idx, record in enumerate(self.data):
            pair_id = record.get('pair_id')
            if pair_id in pair_ids:
                duplicates.append({
                    'pair_id': pair_id,
                    'index': idx
                })
            pair_ids.append(pair_id)

        passed = len(self.data) - len(duplicates)
        return {
            'check': 'pair_id编号唯一性',
            'total': len(self.data),
            'passed': passed,
            'failed': len(duplicates),
            'pass_rate': f"{passed/len(self.data)*100:.2f}%",
            'samples': duplicates[:5]
        }

    def check_is_negative_field(self) -> Dict:
        """检查5: is_negative字段"""
        issues = []

        for idx, record in enumerate(self.data):
            is_negative = record.get('is_negative')

            # 判断是正例还是负例文件
            is_negative_file = 'negative' in self.file_path.lower()

            if is_negative_file:
                # 负例文件：is_negative必须为true
                if is_negative is not True:
                    issues.append({
                        'index': idx,
                        'pair_id': record.get('pair_id', 'N/A'),
                        'is_negative': is_negative,
                        'expected': True,
                        'issue': '负例中is_negative必须为true'
                    })
            else:
                # 正例文件：is_negative应该为false或不存在
                if is_negative is True:
                    issues.append({
                        'index': idx,
                        'pair_id': record.get('pair_id', 'N/A'),
                        'is_negative': is_negative,
                        'issue': '正例中is_negative不应为true'
                    })

        passed = len(self.data) - len(issues)
        return {
            'check': 'is_negative字段正确性',
            'total': len(self.data),
            'passed': passed,
            'failed': len(issues),
            'pass_rate': f"{passed/len(self.data)*100:.2f}%",
            'samples': issues[:5]
        }

    def check_centroid_coordinates(self) -> Dict:
        """检查6: centroid坐标格式和异常值"""
        coord_issues = []

        for idx, record in enumerate(self.data):
            for entity_key in ['entity_a', 'entity_b']:
                entity = record.get(entity_key, {})
                if not isinstance(entity, dict):
                    continue

                centroid = entity.get('centroid')
                if centroid is None:
                    continue

                # 检查格式
                if not isinstance(centroid, list):
                    coord_issues.append({
                        'index': idx,
                        'pair_id': record.get('pair_id', 'N/A'),
                        'entity': entity_key,
                        'centroid': centroid,
                        'issue': 'centroid不是列表'
                    })
                    continue

                if len(centroid) != 2:
                    coord_issues.append({
                        'index': idx,
                        'pair_id': record.get('pair_id', 'N/A'),
                        'entity': entity_key,
                        'centroid': centroid,
                        'issue': f'centroid长度应为2，实际为{len(centroid)}'
                    })
                    continue

                lon, lat = centroid
                try:
                    lon = float(lon)
                    lat = float(lat)

                    # 检查中国范围
                    if not (CHINA_BOUNDS['lon_min'] <= lon <= CHINA_BOUNDS['lon_max']):
                        coord_issues.append({
                            'index': idx,
                            'pair_id': record.get('pair_id', 'N/A'),
                            'entity': entity_key,
                            'centroid': centroid,
                            'issue': f'经度{lon}超出中国范围({CHINA_BOUNDS["lon_min"]}-{CHINA_BOUNDS["lon_max"]})'
                        })

                    if not (CHINA_BOUNDS['lat_min'] <= lat <= CHINA_BOUNDS['lat_max']):
                        coord_issues.append({
                            'index': idx,
                            'pair_id': record.get('pair_id', 'N/A'),
                            'entity': entity_key,
                            'centroid': centroid,
                            'issue': f'纬度{lat}超出中国范围({CHINA_BOUNDS["lat_min"]}-{CHINA_BOUNDS["lat_max"]})'
                        })
                except (ValueError, TypeError):
                    coord_issues.append({
                        'index': idx,
                        'pair_id': record.get('pair_id', 'N/A'),
                        'entity': entity_key,
                        'centroid': centroid,
                        'issue': '坐标值无法转换为数字'
                    })

        passed = len(self.data) * 2 - len(coord_issues)
        return {
            'check': 'centroid坐标格式[lon, lat]及中国范围(lon:73-135, lat:18-54)',
            'total': len(self.data) * 2,
            'passed': passed,
            'failed': len(coord_issues),
            'pass_rate': f"{passed/(len(self.data)*2)*100:.2f}%",
            'samples': coord_issues[:5]
        }

    def check_reference_entity(self) -> Dict:
        """检查8: reference_entity字段"""
        issues = []

        for idx, record in enumerate(self.data):
            ref_entity = record.get('reference_entity')

            # reference_entity应该存在
            if ref_entity is None:
                issues.append({
                    'index': idx,
                    'pair_id': record.get('pair_id', 'N/A'),
                    'issue': '缺少reference_entity字段'
                })
                continue

            # 检查是否是字符串或有效类型
            if not isinstance(ref_entity, (str, type(None))):
                issues.append({
                    'index': idx,
                    'pair_id': record.get('pair_id', 'N/A'),
                    'reference_entity': ref_entity,
                    'issue': f'reference_entity类型应为str或None，实际为{type(ref_entity).__name__}'
                })

        passed = len(self.data) - len(issues)
        return {
            'check': 'reference_entity字段存在性',
            'total': len(self.data),
            'passed': passed,
            'failed': len(issues),
            'pass_rate': f"{passed/len(self.data)*100:.2f}%",
            'samples': issues[:5]
        }

    def analyze_relation_distribution(self) -> Dict:
        """分析关系类型分布"""
        relation_counter = Counter()

        for record in self.data:
            relation = record.get('target_relation', 'unknown')
            relation_counter[relation] += 1

        return {
            'total_relations': len(relation_counter),
            'distribution': dict(relation_counter.most_common())
        }

    def run_all_checks(self) -> List[Dict]:
        """运行所有检查"""
        if not self.load_data():
            return []

        results = []
        results.append(self.check_base_fields())  # 检查1
        results.append(self.check_entity_subfields())  # 检查2
        results.append(self.check_spatial_facts_by_relation())  # 检查3
        results.append(self.check_pair_id_uniqueness())  # 检查4
        results.append(self.check_is_negative_field())  # 检查5
        results.append(self.check_centroid_coordinates())  # 检查6
        # 检查7已在load_data中完成(JSON格式)
        results.append(self.check_reference_entity())  # 检查8

        return results


def format_results(results: List[Dict], relation_dist: Dict, file_path: str) -> str:
    """格式化检查结果"""
    output = []
    output.append("=" * 80)
    output.append(f"数据格式审查报告: {os.path.basename(file_path)}")
    output.append("=" * 80)
    output.append("")

    total_checks = len(results)
    passed_checks = sum(1 for r in results if r['failed'] == 0)

    output.append(f"总记录数: {results[0]['total']}")
    output.append(f"总检查项: {total_checks}")
    output.append(f"完全通过项: {passed_checks}")
    output.append("")

    output.append("-" * 80)
    output.append("详细检查结果:")
    output.append("-" * 80)
    output.append("")

    for i, result in enumerate(results, 1):
        output.append(f"【检查{i}】{result['check']}")
        output.append(f"  总数: {result['total']}")
        output.append(f"  通过: {result['passed']}")
        output.append(f"  失败: {result['failed']}")
        output.append(f"  通过率: {result['pass_rate']}")

        if result['samples']:
            output.append(f"  失败样例:")
            for sample in result['samples'][:3]:
                output.append(f"    - {sample}")
        output.append("")

    output.append("-" * 80)
    output.append("关系类型分布:")
    output.append("-" * 80)
    output.append(f"共 {relation_dist['total_relations']} 种关系类型")
    for relation, count in list(relation_dist['distribution'].items())[:10]:
        output.append(f"  {relation}: {count}")

    return "\n".join(output)


def main():
    positive_path = r"D:\gis_data\output\pairs_positive.jsonl"
    negative_path = r"D:\gis_data\output\pairs_negative.jsonl"

    all_results = []

    # 检查正例文件
    print("\n" + "="*50)
    print("检查正例文件...")
    print("="*50)
    if os.path.exists(positive_path):
        reviewer_pos = DataReviewer(positive_path)
        results_pos = reviewer_pos.run_all_checks()
        relation_dist_pos = reviewer_pos.analyze_relation_distribution()

        report_pos = format_results(results_pos, relation_dist_pos, positive_path)
        print(report_pos)
        all_results.append(('positive', results_pos, relation_dist_pos))
    else:
        print(f"[ERROR] 正例文件不存在: {positive_path}")

    # 检查负例文件
    print("\n" + "="*50)
    print("检查负例文件...")
    print("="*50)
    if os.path.exists(negative_path):
        reviewer_neg = DataReviewer(negative_path)
        results_neg = reviewer_neg.run_all_checks()
        relation_dist_neg = reviewer_neg.analyze_relation_distribution()

        report_neg = format_results(results_neg, relation_dist_neg, negative_path)
        print(report_neg)
        all_results.append(('negative', results_neg, relation_dist_neg))
    else:
        print(f"[ERROR] 负例文件不存在: {negative_path}")

    # 生成总结
    print("\n" + "="*80)
    print("审查总结")
    print("="*80)

    return all_results


if __name__ == "__main__":
    main()
