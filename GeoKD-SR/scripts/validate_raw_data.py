#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 原始数据验证脚本

验证级别：
L1: JSON格式有效性
L2: 必需字段完整性
L3: reasoning_chain 5步结构
L4: entities 坐标字段
L5: spatial_tokens 数量
L6: 分布合理性

使用方法：
    python scripts/validate_raw_data.py --input data/geosr_chain/raw_merged.jsonl --output outputs/raw_validation/
"""

import json
import argparse
import os
import re
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter, defaultdict
from datetime import datetime


class DataValidator:
    """数据验证器"""

    # 必需字段
    REQUIRED_FIELDS = [
        'id', 'spatial_relation_type', 'topology_subtype', 'question', 'answer',
        'reasoning_chain', 'entities', 'spatial_tokens', 'difficulty',
        'difficulty_score', 'prompt_id'
    ]

    # 有效枚举值
    VALID_SPATIAL_TYPES = ['directional', 'topological', 'metric', 'composite']
    VALID_TOPOLOGY_SUBTYPES = ['within', 'contains', 'adjacent', 'disjoint', 'overlap', 'none', '']
    VALID_DIFFICULTIES = ['easy', 'medium', 'hard']

    # 目标分布（允许10%偏差）
    TARGET_DISTRIBUTION = {
        'directional': (0.25, 0.10),
        'topological': (0.275, 0.10),
        'metric': (0.275, 0.10),
        'composite': (0.20, 0.10),
    }

    DIFFICULTY_DISTRIBUTION = {
        'easy': (0.30, 0.10),
        'medium': (0.50, 0.10),
        'hard': (0.20, 0.10),
    }

    # 中国坐标范围
    COORD_RANGE = {
        'lon': (73.0, 135.0),
        'lat': (18.0, 54.0)
    }

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 验证结果
        self.results = {
            'total_records': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'issues': defaultdict(list),
            'warnings': defaultdict(list),
            'stats': {}
        }

    def validate_all(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
        """验证所有记录"""
        valid_records = []
        invalid_records = []

        self.results['total_records'] = len(records)

        for i, record in enumerate(records):
            is_valid, issues = self.validate_record(record, i)

            if is_valid:
                valid_records.append(record)
            else:
                invalid_records.append(record)
                for issue in issues:
                    self.results['issues'][issue].append(i)

        self.results['valid_records'] = len(valid_records)
        self.results['invalid_records'] = len(invalid_records)

        # 收集统计信息
        self._collect_stats(valid_records + invalid_records)

        return valid_records, invalid_records

    def validate_record(self, record: Dict[str, Any], index: int) -> Tuple[bool, List[str]]:
        """验证单条记录"""
        issues = []

        # L1: JSON格式已在加载时验证

        # L2: 必需字段完整性
        for field in self.REQUIRED_FIELDS:
            if field not in record:
                issues.append(f'L2_missing_{field}')

        if issues:
            return False, issues

        # L2.1: 字段类型检查
        if not isinstance(record.get('reasoning_chain', []), list):
            issues.append('L2_invalid_reasoning_chain_type')
        if not isinstance(record.get('entities', []), list):
            issues.append('L2_invalid_entities_type')
        if not isinstance(record.get('spatial_tokens', []), list):
            issues.append('L2_invalid_spatial_tokens_type')

        # L2.2: 枚举值检查
        spatial_type = record.get('spatial_relation_type', '')
        if spatial_type not in self.VALID_SPATIAL_TYPES:
            issues.append(f'L2_invalid_spatial_type:{spatial_type}')

        difficulty = record.get('difficulty', '')
        if difficulty not in self.VALID_DIFFICULTIES:
            issues.append(f'L2_invalid_difficulty:{difficulty}')

        # L3: reasoning_chain 5步结构
        reasoning_chain = record.get('reasoning_chain', [])
        if isinstance(reasoning_chain, list):
            if len(reasoning_chain) != 5:
                issues.append(f'L3_invalid_chain_length:{len(reasoning_chain)}')

        # L4: entities 坐标字段
        entities = record.get('entities', [])
        if isinstance(entities, list) and len(entities) >= 2:
            for j, entity in enumerate(entities[:2]):
                if 'name' not in entity:
                    issues.append(f'L4_missing_entity_name:{j}')
                if 'coords' not in entity:
                    issues.append(f'L4_missing_coords:{j}')
                elif entity['coords']:
                    coords = entity['coords']
                    if not isinstance(coords, list) or len(coords) < 2:
                        issues.append(f'L4_invalid_coords_format:{j}')
                    else:
                        # 检查坐标范围（中国境内）
                        lon, lat = coords[0], coords[1]
                        if not (self.COORD_RANGE['lon'][0] <= lon <= self.COORD_RANGE['lon'][1]):
                            issues.append(f'L4_lon_out_of_range:{j}:{lon}')
                        if not (self.COORD_RANGE['lat'][0] <= lat <= self.COORD_RANGE['lat'][1]):
                            issues.append(f'L4_lat_out_of_range:{j}:{lat}')

        # L5: spatial_tokens 数量
        spatial_tokens = record.get('spatial_tokens', [])
        if isinstance(spatial_tokens, list):
            if len(spatial_tokens) == 0:
                issues.append('L5_empty_spatial_tokens')
            elif len(spatial_tokens) > 20:
                issues.append(f'L5_too_many_tokens:{len(spatial_tokens)}')

            # 检查tokens是否在question中出现
            question = record.get('question', '')
            missing_tokens = [t for t in spatial_tokens if t not in question]
            if missing_tokens:
                issues.append(f'L5_tokens_not_in_question:{len(missing_tokens)}')

        # L6: 拓扑子类型检查（仅topological）
        if spatial_type == 'topological':
            topo_subtype = record.get('topology_subtype', '')
            if topo_subtype not in ['within', 'contains', 'adjacent', 'disjoint', 'overlap']:
                issues.append(f'L6_invalid_topology_subtype:{topo_subtype}')

        return len(issues) == 0, issues

    def _collect_stats(self, records: List[Dict[str, Any]]):
        """收集统计信息"""
        # 空间关系分布
        spatial_dist = Counter(r.get('spatial_relation_type', 'unknown') for r in records)
        self.results['stats']['spatial_distribution'] = dict(spatial_dist)

        # 难度分布
        difficulty_dist = Counter(r.get('difficulty', 'unknown') for r in records)
        self.results['stats']['difficulty_distribution'] = dict(difficulty_dist)

        # 拓扑子类型分布
        topology_subtypes = Counter(
            r.get('topology_subtype', 'none')
            for r in records
            if r.get('spatial_relation_type') == 'topological'
        )
        self.results['stats']['topology_subtype_distribution'] = dict(topology_subtypes)

        # 推理链长度分布
        chain_lengths = Counter(len(r.get('reasoning_chain', [])) for r in records)
        self.results['stats']['chain_length_distribution'] = dict(chain_lengths)

        # 实体数量分布
        entity_counts = Counter(len(r.get('entities', [])) for r in records)
        self.results['stats']['entity_count_distribution'] = dict(entity_counts)

        # 检查分布是否符合目标
        total = len(records)
        distribution_issues = []

        for dtype, (target, tolerance) in self.TARGET_DISTRIBUTION.items():
            actual = spatial_dist.get(dtype, 0) / total if total > 0 else 0
            if abs(actual - target) > tolerance:
                distribution_issues.append(f'{dtype}: target={target:.1%}, actual={actual:.1%}')

        for dtype, (target, tolerance) in self.DIFFICULTY_DISTRIBUTION.items():
            actual = difficulty_dist.get(dtype, 0) / total if total > 0 else 0
            if abs(actual - target) > tolerance:
                distribution_issues.append(f'{dtype}: target={target:.1%}, actual={actual:.1%}')

        self.results['stats']['distribution_issues'] = distribution_issues

    def generate_report(self) -> str:
        """生成验证报告"""
        lines = [
            "# GeoKD-SR 原始数据验证报告",
            "",
            f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            "## 一、验证概览",
            "",
            f"- **总记录数**: {self.results['total_records']}",
            f"- **有效记录**: {self.results['valid_records']} ({self.results['valid_records']/max(self.results['total_records'],1)*100:.1f}%)",
            f"- **无效记录**: {self.results['invalid_records']} ({self.results['invalid_records']/max(self.results['total_records'],1)*100:.1f}%)",
            "",
            "---",
            "",
            "## 二、问题统计",
            "",
            "| 问题类型 | 出现次数 |",
            "|----------|----------|",
        ]

        for issue, indices in sorted(self.results['issues'].items(), key=lambda x: -len(x[1])):
            lines.append(f"| {issue} | {len(indices)} |")

        lines.extend([
            "",
            "---",
            "",
            "## 三、分布统计",
            "",
            "### 3.1 空间关系类型分布",
            "",
            "| 类型 | 数量 | 占比 |",
            "|------|------|------|",
        ])

        total = self.results['total_records']
        for dtype in ['directional', 'topological', 'metric', 'composite']:
            count = self.results['stats'].get('spatial_distribution', {}).get(dtype, 0)
            pct = count / total * 100 if total > 0 else 0
            lines.append(f"| {dtype} | {count} | {pct:.1f}% |")

        lines.extend([
            "",
            "### 3.2 难度分布",
            "",
            "| 难度 | 数量 | 占比 |",
            "|------|------|------|",
        ])

        for dtype in ['easy', 'medium', 'hard']:
            count = self.results['stats'].get('difficulty_distribution', {}).get(dtype, 0)
            pct = count / total * 100 if total > 0 else 0
            lines.append(f"| {dtype} | {count} | {pct:.1f}% |")

        lines.extend([
            "",
            "### 3.3 拓扑子类型分布",
            "",
            "| 子类型 | 数量 |",
            "|--------|------|",
        ])

        for subtype in ['within', 'contains', 'adjacent', 'disjoint', 'overlap']:
            count = self.results['stats'].get('topology_subtype_distribution', {}).get(subtype, 0)
            lines.append(f"| {subtype} | {count} |")

        # 分布问题
        if self.results['stats'].get('distribution_issues'):
            lines.extend([
                "",
                "---",
                "",
                "## 四、分布偏差警告",
                "",
            ])
            for issue in self.results['stats']['distribution_issues']:
                lines.append(f"- {issue}")

        lines.extend([
            "",
            "---",
            "",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ""
        ])

        return '\n'.join(lines)

    def save_results(self):
        """保存验证结果"""
        # 保存报告
        report = self.generate_report()
        report_path = self.output_dir / 'validation_report.md'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"验证报告: {report_path}")

        # 保存JSON结果
        results_path = self.output_dir / 'validation_results.json'
        # 转换defaultdict为dict
        output_results = {
            'total_records': self.results['total_records'],
            'valid_records': self.results['valid_records'],
            'invalid_records': self.results['invalid_records'],
            'issues': {k: v for k, v in self.results['issues'].items()},
            'warnings': {k: v for k, v in self.results['warnings'].items()},
            'stats': self.results['stats']
        }
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(output_results, f, ensure_ascii=False, indent=2)
        print(f"JSON结果: {results_path}")


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """加载JSONL文件"""
    records = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"警告: JSON解析失败: {e}")
    return records


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 原始数据验证脚本')
    parser.add_argument(
        '--input', '-i',
        default='D:/30_keyan/GeoKD-SR/data/geosr_chain/raw_merged.jsonl',
        help='输入文件路径'
    )
    parser.add_argument(
        '--output', '-o',
        default='D:/30_keyan/GeoKD-SR/outputs/raw_validation/',
        help='输出目录'
    )

    args = parser.parse_args()

    print("="*60)
    print("GeoKD-SR 原始数据验证脚本")
    print("="*60)
    print(f"输入文件: {args.input}")
    print(f"输出目录: {args.output}")

    # 加载数据
    print("\n加载数据...")
    records = load_jsonl(args.input)
    print(f"加载了 {len(records)} 条记录")

    # 验证
    print("\n验证数据...")
    validator = DataValidator(args.output)
    valid_records, invalid_records = validator.validate_all(records)

    # 保存结果
    validator.save_results()

    # 打印摘要
    print("\n" + "="*60)
    print("验证完成")
    print("="*60)
    print(f"总记录数: {len(records)}")
    print(f"有效记录: {len(valid_records)}")
    print(f"无效记录: {len(invalid_records)}")

    if validator.results['issues']:
        print("\n主要问题:")
        for issue, indices in sorted(validator.results['issues'].items(), key=lambda x: -len(x[1]))[:10]:
            print(f"  {issue}: {len(indices)} 次")

    return 0


if __name__ == '__main__':
    exit(main())
