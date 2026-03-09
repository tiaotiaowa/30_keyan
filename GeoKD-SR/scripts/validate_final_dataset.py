#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 最终数据集验证脚本

验证项目：
1. 数据量验证：总数10,000, train 8,000, dev 1,000, test 1,000
2. 分布验证：各空间关系类型比例
3. 互斥验证：train/dev/test实体对无重叠
4. 格式验证：所有记录包含必需字段

使用方法：
    python scripts/validate_final_dataset.py --input data/geosr_chain/v3/ --output outputs/v3_validation/
"""

import json
import argparse
import os
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from collections import Counter, defaultdict
from datetime import datetime


class FinalDatasetValidator:
    """最终数据集验证器"""

    # 目标配置
    TARGET_COUNTS = {
        'train': 8000,
        'dev': 1000,
        'test': 1000
    }

    TARGET_SPATIAL_DISTRIBUTION = {
        'directional': (0.25, 0.05),
        'topological': (0.275, 0.05),
        'metric': (0.275, 0.05),
        'composite': (0.20, 0.05)
    }

    TARGET_DIFFICULTY_DISTRIBUTION = {
        'easy': (0.30, 0.05),
        'medium': (0.50, 0.05),
        'hard': (0.20, 0.05)
    }

    REQUIRED_FIELDS = [
        'id', 'spatial_relation_type', 'topology_subtype', 'question', 'answer',
        'reasoning_chain', 'entities', 'spatial_tokens', 'difficulty',
        'difficulty_score', 'prompt_id', 'split', 'entity_to_token'
    ]

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.train_records = []
        self.dev_records = []
        self.test_records = []

        self.validation_results = {
            'passed': True,
            'checks': {},
            'issues': [],
            'warnings': []
        }

    def load_all_splits(self):
        """加载所有split"""
        train_path = self.input_dir / 'train.jsonl'
        dev_path = self.input_dir / 'dev.jsonl'
        test_path = self.input_dir / 'test.jsonl'

        if train_path.exists():
            self.train_records = self._load_jsonl(train_path)
        if dev_path.exists():
            self.dev_records = self._load_jsonl(dev_path)
        if test_path.exists():
            self.test_records = self._load_jsonl(test_path)

        print(f"加载: train={len(self.train_records)}, dev={len(self.dev_records)}, test={len(self.test_records)}")

    def _load_jsonl(self, file_path: Path) -> List[Dict]:
        """加载JSONL文件"""
        records = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        self.validation_results['issues'].append(f"JSON解析错误: {file_path}: {e}")
        return records

    def validate_all(self) -> bool:
        """执行所有验证"""
        print("\n" + "="*60)
        print("执行验证...")
        print("="*60)

        # 1. 数据量验证
        self._validate_counts()

        # 2. 分布验证
        self._validate_distribution()

        # 3. 实体对互斥验证
        self._validate_entity_exclusion()

        # 4. 格式验证
        self._validate_format()

        return self.validation_results['passed']

    def _validate_counts(self):
        """验证数据量"""
        print("\n[1] 数据量验证")

        checks = {}
        all_passed = True

        for split_name, target in self.TARGET_COUNTS.items():
            records = getattr(self, f'{split_name}_records')
            actual = len(records)
            passed = actual == target

            checks[split_name] = {
                'target': target,
                'actual': actual,
                'passed': passed
            }

            status = "[OK]" if passed else "[FAIL]"
            print(f"  {split_name}: {actual}/{target} {status}")

            if not passed:
                all_passed = False
                self.validation_results['issues'].append(
                    f"{split_name}数量不匹配: 期望{target}, 实际{actual}"
                )

        # 验证总数
        total = len(self.train_records) + len(self.dev_records) + len(self.test_records)
        total_passed = total == 10000
        checks['total'] = {
            'target': 10000,
            'actual': total,
            'passed': total_passed
        }

        status = "[OK]" if total_passed else "[FAIL]"
        print(f"  total: {total}/10000 {status}")

        self.validation_results['checks']['counts'] = checks

    def _validate_distribution(self):
        """验证分布"""
        print("\n[2] 分布验证")

        all_records = self.train_records + self.dev_records + self.test_records
        total = len(all_records)

        if total == 0:
            self.validation_results['issues'].append("没有记录可供验证")
            return

        # 空间关系分布
        spatial_dist = Counter(r.get('spatial_relation_type', 'unknown') for r in all_records)
        print("\n  空间关系类型分布:")

        spatial_checks = {}
        for dtype, (target, tolerance) in self.TARGET_SPATIAL_DISTRIBUTION.items():
            actual = spatial_dist.get(dtype, 0) / total
            passed = abs(actual - target) <= tolerance

            spatial_checks[dtype] = {
                'target': target,
                'actual': actual,
                'passed': passed,
                'count': spatial_dist.get(dtype, 0)
            }

            status = "[OK]" if passed else "[FAIL]"
            print(f"    {dtype}: {actual:.1%} (目标: {target:.1%}) {status}")

            if not passed:
                self.validation_results['warnings'].append(
                    f"{dtype}分布偏差: 目标{target:.1%}, 实际{actual:.1%}"
                )

        self.validation_results['checks']['spatial_distribution'] = spatial_checks

        # 难度分布
        difficulty_dist = Counter(r.get('difficulty', 'unknown') for r in all_records)
        print("\n  难度分布:")

        difficulty_checks = {}
        for dtype, (target, tolerance) in self.TARGET_DIFFICULTY_DISTRIBUTION.items():
            actual = difficulty_dist.get(dtype, 0) / total
            passed = abs(actual - target) <= tolerance

            difficulty_checks[dtype] = {
                'target': target,
                'actual': actual,
                'passed': passed,
                'count': difficulty_dist.get(dtype, 0)
            }

            status = "[OK]" if passed else "[FAIL]"
            print(f"    {dtype}: {actual:.1%} (目标: {target:.1%}) {status}")

        self.validation_results['checks']['difficulty_distribution'] = difficulty_checks

        # 拓扑子类型分布
        topo_records = [r for r in all_records if r.get('spatial_relation_type') == 'topological']
        topo_subtypes = Counter(r.get('topology_subtype', 'none') for r in topo_records)
        print(f"\n  拓扑子类型分布 (共{len(topo_records)}条):")

        for subtype in ['within', 'contains', 'adjacent', 'disjoint', 'overlap']:
            count = topo_subtypes.get(subtype, 0)
            print(f"    {subtype}: {count}")

        self.validation_results['checks']['topology_subtype_distribution'] = dict(topo_subtypes)

    def _get_entity_pair_key(self, entities: List[Dict]) -> str:
        """获取实体对唯一标识"""
        if not entities or len(entities) < 2:
            return ""
        names = sorted([e.get('name', '') for e in entities[:2]])
        return f"{names[0]}|{names[1]}"

    def _validate_entity_exclusion(self):
        """验证实体对互斥"""
        print("\n[3] 实体对互斥验证")

        # 提取各split的实体对
        train_pairs = set()
        dev_pairs = set()
        test_pairs = set()

        for r in self.train_records:
            pair = self._get_entity_pair_key(r.get('entities', []))
            if pair:
                train_pairs.add(pair)

        for r in self.dev_records:
            pair = self._get_entity_pair_key(r.get('entities', []))
            if pair:
                dev_pairs.add(pair)

        for r in self.test_records:
            pair = self._get_entity_pair_key(r.get('entities', []))
            if pair:
                test_pairs.add(pair)

        # 检查重叠
        train_dev_overlap = train_pairs & dev_pairs
        train_test_overlap = train_pairs & test_pairs
        dev_test_overlap = dev_pairs & test_pairs

        all_passed = True

        print(f"  train实体对: {len(train_pairs)}")
        print(f"  dev实体对: {len(dev_pairs)}")
        print(f"  test实体对: {len(test_pairs)}")

        # train/dev
        passed = len(train_dev_overlap) == 0
        status = "[OK]" if passed else "[FAIL]"
        print(f"  train/dev重叠: {len(train_dev_overlap)} {status}")
        if not passed:
            all_passed = False
            self.validation_results['issues'].append(f"train/dev实体对重叠: {len(train_dev_overlap)}")

        # train/test
        passed = len(train_test_overlap) == 0
        status = "[OK]" if passed else "[FAIL]"
        print(f"  train/test重叠: {len(train_test_overlap)} {status}")
        if not passed:
            all_passed = False
            self.validation_results['issues'].append(f"train/test实体对重叠: {len(train_test_overlap)}")

        # dev/test
        passed = len(dev_test_overlap) == 0
        status = "[OK]" if passed else "[FAIL]"
        print(f"  dev/test重叠: {len(dev_test_overlap)} {status}")
        if not passed:
            all_passed = False
            self.validation_results['issues'].append(f"dev/test实体对重叠: {len(dev_test_overlap)}")

        self.validation_results['checks']['entity_exclusion'] = {
            'train_pairs': len(train_pairs),
            'dev_pairs': len(dev_pairs),
            'test_pairs': len(test_pairs),
            'train_dev_overlap': list(train_dev_overlap)[:10],  # 只保存前10个
            'train_test_overlap': list(train_test_overlap)[:10],
            'dev_test_overlap': list(dev_test_overlap)[:10],
            'passed': all_passed
        }

        if not all_passed:
            self.validation_results['passed'] = False

    def _validate_format(self):
        """验证格式"""
        print("\n[4] 格式验证")

        all_records = self.train_records + self.dev_records + self.test_records
        field_missing = defaultdict(int)
        chain_length_issues = 0
        entity_coords_issues = 0

        for record in all_records:
            # 检查必需字段
            for field in self.REQUIRED_FIELDS:
                if field not in record:
                    field_missing[field] += 1

            # 检查推理链长度
            chain = record.get('reasoning_chain', [])
            if not isinstance(chain, list) or len(chain) != 5:
                chain_length_issues += 1

            # 检查实体坐标
            entities = record.get('entities', [])
            has_coords = any('coords' in e and e['coords'] for e in entities) if entities else False
            if not has_coords:
                entity_coords_issues += 1

        # 输出结果
        format_passed = True

        if field_missing:
            print("  字段缺失:")
            for field, count in field_missing.items():
                print(f"    {field}: {count}")
                format_passed = False
        else:
            print("  字段完整性: [OK]")

        if chain_length_issues > 0:
            print(f"  推理链长度问题: {chain_length_issues} [FAIL]")
            format_passed = False
        else:
            print("  推理链长度: [OK]")

        print(f"  有坐标记录: {len(all_records) - entity_coords_issues}")
        print(f"  无坐标记录: {entity_coords_issues}")

        self.validation_results['checks']['format'] = {
            'field_missing': dict(field_missing),
            'chain_length_issues': chain_length_issues,
            'records_with_coords': len(all_records) - entity_coords_issues,
            'records_without_coords': entity_coords_issues,
            'passed': format_passed
        }

        if not format_passed:
            self.validation_results['warnings'].append("格式验证存在问题")

    def generate_report(self) -> str:
        """生成验证报告"""
        lines = [
            "# GeoKD-SR 最终数据集验证报告",
            "",
            f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> **输入目录**: {self.input_dir}",
            "",
            "---",
            "",
            "## 验证结果摘要",
            "",
        ]

        if self.validation_results['passed']:
            lines.append("[OK] **所有验证通过**")
        else:
            lines.append("[FAIL] **存在验证失败项**")

        lines.extend([
            "",
            "---",
            "",
            "## 一、数据量验证",
            "",
            "| Split | 目标 | 实际 | 状态 |",
            "|-------|------|------|------|",
        ])

        counts = self.validation_results['checks'].get('counts', {})
        for split in ['train', 'dev', 'test', 'total']:
            if split in counts:
                c = counts[split]
                status = "[OK]" if c['passed'] else "[FAIL]"
                lines.append(f"| {split} | {c['target']} | {c['actual']} | {status} |")

        lines.extend([
            "",
            "---",
            "",
            "## 二、分布验证",
            "",
            "### 2.1 空间关系类型分布",
            "",
            "| 类型 | 目标 | 实际 | 状态 |",
            "|------|------|------|------|",
        ])

        spatial = self.validation_results['checks'].get('spatial_distribution', {})
        for dtype in ['directional', 'topological', 'metric', 'composite']:
            if dtype in spatial:
                s = spatial[dtype]
                status = "[OK]" if s['passed'] else "[FAIL]"
                lines.append(f"| {dtype} | {s['target']:.1%} | {s['actual']:.1%} | {status} |")

        lines.extend([
            "",
            "### 2.2 难度分布",
            "",
            "| 难度 | 目标 | 实际 | 状态 |",
            "|------|------|------|------|",
        ])

        difficulty = self.validation_results['checks'].get('difficulty_distribution', {})
        for dtype in ['easy', 'medium', 'hard']:
            if dtype in difficulty:
                d = difficulty[dtype]
                status = "[OK]" if d['passed'] else "[FAIL]"
                lines.append(f"| {dtype} | {d['target']:.1%} | {d['actual']:.1%} | {status} |")

        # 实体对互斥
        exclusion = self.validation_results['checks'].get('entity_exclusion', {})
        lines.extend([
            "",
            "---",
            "",
            "## 三、实体对互斥验证",
            "",
            f"- **train实体对数**: {exclusion.get('train_pairs', 0)}",
            f"- **dev实体对数**: {exclusion.get('dev_pairs', 0)}",
            f"- **test实体对数**: {exclusion.get('test_pairs', 0)}",
            "",
        ])

        if exclusion.get('passed', False):
            lines.append("[OK] **实体对互斥验证通过**")
        else:
            lines.append("[FAIL] **实体对互斥验证失败**")
            if exclusion.get('train_dev_overlap'):
                lines.append(f"- train/dev重叠: {len(exclusion['train_dev_overlap'])}个")
            if exclusion.get('train_test_overlap'):
                lines.append(f"- train/test重叠: {len(exclusion['train_test_overlap'])}个")
            if exclusion.get('dev_test_overlap'):
                lines.append(f"- dev/test重叠: {len(exclusion['dev_test_overlap'])}个")

        # 格式验证
        format_check = self.validation_results['checks'].get('format', {})
        lines.extend([
            "",
            "---",
            "",
            "## 四、格式验证",
            "",
            f"- **字段完整性**: {'[OK]' if not format_check.get('field_missing') else '[FAIL]'}",
            f"- **推理链长度**: {'[OK]' if format_check.get('chain_length_issues', 0) == 0 else '[FAIL]'}",
            f"- **有坐标记录**: {format_check.get('records_with_coords', 0)}",
            f"- **无坐标记录**: {format_check.get('records_without_coords', 0)}",
        ])

        # 问题列表
        if self.validation_results['issues']:
            lines.extend([
                "",
                "---",
                "",
                "## 五、问题列表",
                "",
            ])
            for issue in self.validation_results['issues']:
                lines.append(f"- [FAIL] {issue}")

        if self.validation_results['warnings']:
            lines.extend([
                "",
                "## 六、警告列表",
                "",
            ])
            for warning in self.validation_results['warnings']:
                lines.append(f"- ⚠️ {warning}")

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
        print(f"\n验证报告: {report_path}")

        # 保存JSON
        results_path = self.output_dir / 'validation_results.json'
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, ensure_ascii=False, indent=2)
        print(f"JSON结果: {results_path}")


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 最终数据集验证脚本')
    parser.add_argument(
        '--input', '-i',
        default='D:/30_keyan/GeoKD-SR/data/geosr_chain/v3',
        help='输入目录（包含train.jsonl, dev.jsonl, test.jsonl）'
    )
    parser.add_argument(
        '--output', '-o',
        default='D:/30_keyan/GeoKD-SR/outputs/v3_validation',
        help='输出目录'
    )

    args = parser.parse_args()

    print("="*60)
    print("GeoKD-SR 最终数据集验证脚本")
    print("="*60)
    print(f"输入目录: {args.input}")
    print(f"输出目录: {args.output}")

    # 创建验证器
    validator = FinalDatasetValidator(args.input, args.output)

    # 加载数据
    print("\n加载数据...")
    validator.load_all_splits()

    # 执行验证
    passed = validator.validate_all()

    # 保存结果
    validator.save_results()

    # 最终结果
    print("\n" + "="*60)
    if passed:
        print("[OK] 验证通过!")
    else:
        print("[FAIL] 验证失败!")
        for issue in validator.validation_results['issues']:
            print(f"  - {issue}")
    print("="*60)

    return 0 if passed else 1


if __name__ == '__main__':
    exit(main())
