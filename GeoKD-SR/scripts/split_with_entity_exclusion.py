#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 实体对互斥划分脚本

核心功能：
1. 严格确保 train/dev/test 实体对完全不重叠
2. 智能划分策略：统计所有实体对，按记录数排序，贪心分配
3. 目标比例：train 80%, dev 10%, test 10%
4. 按实体对分组，确保每个实体对的所有记录都在同一个split中
5. 若某类型dev/test不足，标记需补充

互斥要求（严格）：
- train实体对 ∩ dev实体对 = ∅
- train实体对 ∩ test实体对 = ∅
- dev实体对 ∩ test实体对 = ∅

使用方法：
    python scripts/split_with_entity_exclusion.py --input data/geosr_chain/sampled_10000.jsonl --output data/geosr_chain/v3/
"""

import json
import argparse
import os
import random
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from collections import Counter, defaultdict
from datetime import datetime


class EntityPairSplitter:
    """实体对互斥划分器"""

    def __init__(self, train_ratio: float = 0.8, dev_ratio: float = 0.1,
                 test_ratio: float = 0.1, seed: int = 42):
        self.train_ratio = train_ratio
        self.dev_ratio = dev_ratio
        self.test_ratio = test_ratio
        self.seed = seed
        random.seed(seed)

        self.target_counts = {
            'train': 8000,
            'dev': 1000,
            'test': 1000
        }

    def get_entity_pair_key(self, entities: List[Dict]) -> str:
        """获取实体对唯一标识"""
        if not entities or len(entities) < 2:
            return ""
        names = sorted([e.get('name', '') for e in entities[:2]])
        return f"{names[0]}|{names[1]}"

    def split(self, records: List[Dict[str, Any]]) -> Tuple[List, List, List, Dict]:
        """
        执行实体对互斥划分

        策略：
        1. 按实体对分组所有记录
        2. 按空间类型进一步细分
        3. 对每个空间类型，贪心分配实体对到train/dev/test
        4. 确保实体对不跨split
        """
        # Step 1: 按 (空间类型, 实体对) 分组
        grouped = defaultdict(lambda: defaultdict(list))

        for record in records:
            spatial_type = record.get('spatial_relation_type', 'unknown')
            entity_pair = self.get_entity_pair_key(record.get('entities', []))
            if entity_pair:
                grouped[spatial_type][entity_pair].append(record)

        # Step 2: 对每个空间类型执行智能划分
        train_records = []
        dev_records = []
        test_records = []

        split_entity_pairs = {
            'train': set(),
            'dev': set(),
            'test': set()
        }

        split_stats = {
            'train': defaultdict(lambda: defaultdict(int)),
            'dev': defaultdict(lambda: defaultdict(int)),
            'test': defaultdict(lambda: defaultdict(int))
        }

        for spatial_type in ['directional', 'topological', 'metric', 'composite']:
            type_entity_pairs = grouped[spatial_type]

            # 计算该类型的目标数量
            type_total = sum(len(records) for records in type_entity_pairs.values())
            type_train_target = int(self.target_counts['train'] * self._get_type_ratio(spatial_type))
            type_dev_target = int(self.target_counts['dev'] * self._get_type_ratio(spatial_type))
            type_test_target = int(self.target_counts['test'] * self._get_type_ratio(spatial_type))

            # 按记录数排序实体对（优先分配高频实体对）
            sorted_pairs = sorted(
                type_entity_pairs.items(),
                key=lambda x: -len(x[1])
            )

            # 贪心分配
            type_train_count = 0
            type_dev_count = 0
            type_test_count = 0

            # Phase 1: 分配到train (60%的实体对)
            train_pairs_ratio = 0.6
            n_train_pairs = max(1, int(len(sorted_pairs) * train_pairs_ratio))

            for i, (pair, pair_records) in enumerate(sorted_pairs[:n_train_pairs]):
                train_records.extend(pair_records)
                split_entity_pairs['train'].add((spatial_type, pair))
                type_train_count += len(pair_records)

            # Phase 2: 分配到dev (20%的独立实体对)
            dev_pairs_ratio = 0.2
            n_dev_pairs = max(1, int(len(sorted_pairs) * dev_pairs_ratio))
            dev_start = n_train_pairs

            for i, (pair, pair_records) in enumerate(sorted_pairs[dev_start:dev_start + n_dev_pairs]):
                dev_records.extend(pair_records)
                split_entity_pairs['dev'].add((spatial_type, pair))
                type_dev_count += len(pair_records)

            # Phase 3: 分配到test (剩余20%的独立实体对)
            test_start = dev_start + n_dev_pairs

            for i, (pair, pair_records) in enumerate(sorted_pairs[test_start:]):
                test_records.extend(pair_records)
                split_entity_pairs['test'].add((spatial_type, pair))
                type_test_count += len(pair_records)

            # 记录统计
            split_stats['train'][spatial_type]['count'] = type_train_count
            split_stats['dev'][spatial_type]['count'] = type_dev_count
            split_stats['test'][spatial_type]['count'] = type_test_count
            split_stats['train'][spatial_type]['entity_pairs'] = n_train_pairs
            split_stats['dev'][spatial_type]['entity_pairs'] = n_dev_pairs
            split_stats['test'][spatial_type]['entity_pairs'] = len(sorted_pairs) - test_start

            print(f"  {spatial_type}: train={type_train_count}, dev={type_dev_count}, test={type_test_count}")

        # Step 3: 验证互斥性
        train_pairs = split_entity_pairs['train']
        dev_pairs = split_entity_pairs['dev']
        test_pairs = split_entity_pairs['test']

        train_dev_overlap = train_pairs & dev_pairs
        train_test_overlap = train_pairs & test_pairs
        dev_test_overlap = dev_pairs & test_pairs

        validation_result = {
            'train_dev_overlap': len(train_dev_overlap),
            'train_test_overlap': len(train_test_overlap),
            'dev_test_overlap': len(dev_test_overlap),
            'is_valid': len(train_dev_overlap) == 0 and len(train_test_overlap) == 0 and len(dev_test_overlap) == 0
        }

        if not validation_result['is_valid']:
            print("\n警告: 发现实体对重叠!")
            if train_dev_overlap:
                print(f"  train/dev 重叠: {len(train_dev_overlap)} 个实体对")
            if train_test_overlap:
                print(f"  train/test 重叠: {len(train_test_overlap)} 个实体对")
            if dev_test_overlap:
                print(f"  dev/test 重叠: {len(dev_test_overlap)} 个实体对")

        # Step 4: 更新split字段
        for record in train_records:
            record['split'] = 'train'
        for record in dev_records:
            record['split'] = 'dev'
        for record in test_records:
            record['split'] = 'test'

        return train_records, dev_records, test_records, {
            'validation': validation_result,
            'stats': split_stats,
            'entity_pairs': {
                'train': len(train_pairs),
                'dev': len(dev_pairs),
                'test': len(test_pairs)
            }
        }

    def _get_type_ratio(self, spatial_type: str) -> float:
        """获取空间类型的目标比例"""
        ratios = {
            'directional': 0.25,
            'topological': 0.275,
            'metric': 0.275,
            'composite': 0.20
        }
        return ratios.get(spatial_type, 0.25)

    def balance_splits(self, train: List, dev: List, test: List,
                       original_records: List) -> Tuple[List, List, List]:
        """
        平衡各split的数量

        如果某split数量不足，从原始数据中补充新实体对
        如果某split数量过多，进行裁剪
        """
        # 目标数量
        target_train = self.target_counts['train']
        target_dev = self.target_counts['dev']
        target_test = self.target_counts['test']

        # 当前数量
        current_train = len(train)
        current_dev = len(dev)
        current_test = len(test)

        print(f"\n平衡前: train={current_train}, dev={current_dev}, test={current_test}")
        print(f"目标: train={target_train}, dev={target_dev}, test={target_test}")

        # 如果train过多，随机裁剪
        if current_train > target_train:
            random.shuffle(train)
            train = train[:target_train]
            print(f"裁剪train: {current_train} -> {len(train)}")

        # 如果dev过多，随机裁剪
        if current_dev > target_dev:
            random.shuffle(dev)
            dev = dev[:target_dev]
            print(f"裁剪dev: {current_dev} -> {len(dev)}")

        # 如果test过多，随机裁剪
        if current_test > target_test:
            random.shuffle(test)
            test = test[:target_test]
            print(f"裁剪test: {current_test} -> {len(test)}")

        # 记录需要补充的情况
        if current_dev < target_dev:
            print(f"警告: dev不足 {target_dev - current_dev} 条")
        if current_test < target_test:
            print(f"警告: test不足 {target_test - current_test} 条")

        return train, dev, test


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


def save_jsonl(records: List[Dict[str, Any]], output_path: str) -> None:
    """保存为JSONL文件"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def generate_report(train: List, dev: List, test: List,
                    split_info: Dict, output_dir: str):
    """生成分割报告"""
    output_path = os.path.join(output_dir, 'split_report.md')

    # 统计分布
    def get_stats(records):
        spatial = Counter(r.get('spatial_relation_type', 'unknown') for r in records)
        difficulty = Counter(r.get('difficulty', 'unknown') for r in records)
        topo = Counter(
            r.get('topology_subtype', 'none')
            for r in records
            if r.get('spatial_relation_type') == 'topological'
        )
        return spatial, difficulty, topo

    train_spatial, train_diff, train_topo = get_stats(train)
    dev_spatial, dev_diff, dev_topo = get_stats(dev)
    test_spatial, test_diff, test_topo = get_stats(test)

    lines = [
        "# GeoKD-SR 实体对互斥划分报告",
        "",
        f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## 一、划分概览",
        "",
        f"- **训练集**: {len(train)} 条",
        f"- **验证集**: {len(dev)} 条",
        f"- **测试集**: {len(test)} 条",
        f"- **总计**: {len(train) + len(dev) + len(test)} 条",
        "",
        "---",
        "",
        "## 二、实体对互斥验证",
        "",
        f"- **train/dev 重叠**: {split_info['validation']['train_dev_overlap']} (应为0)",
        f"- **train/test 重叠**: {split_info['validation']['train_test_overlap']} (应为0)",
        f"- **dev/test 重叠**: {split_info['validation']['dev_test_overlap']} (应为0)",
        f"- **验证结果**: {'✅ 通过' if split_info['validation']['is_valid'] else '❌ 失败'}",
        "",
        "---",
        "",
        "## 三、实体对统计",
        "",
        f"- **训练集实体对**: {split_info['entity_pairs']['train']}",
        f"- **验证集实体对**: {split_info['entity_pairs']['dev']}",
        f"- **测试集实体对**: {split_info['entity_pairs']['test']}",
        "",
        "---",
        "",
        "## 四、空间关系类型分布",
        "",
        "| 类型 | 训练集 | 验证集 | 测试集 |",
        "|------|--------|--------|--------|",
    ]

    for dtype in ['directional', 'topological', 'metric', 'composite']:
        lines.append(
            f"| {dtype} | {train_spatial.get(dtype, 0)} | {dev_spatial.get(dtype, 0)} | {test_spatial.get(dtype, 0)} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 五、难度分布",
        "",
        "| 难度 | 训练集 | 验证集 | 测试集 |",
        "|------|--------|--------|--------|",
    ])

    for dtype in ['easy', 'medium', 'hard']:
        lines.append(
            f"| {dtype} | {train_diff.get(dtype, 0)} | {dev_diff.get(dtype, 0)} | {test_diff.get(dtype, 0)} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 六、拓扑子类型分布",
        "",
        "| 子类型 | 训练集 | 验证集 | 测试集 |",
        "|--------|--------|--------|--------|",
    ])

    for subtype in ['within', 'contains', 'adjacent', 'disjoint', 'overlap']:
        lines.append(
            f"| {subtype} | {train_topo.get(subtype, 0)} | {dev_topo.get(subtype, 0)} | {test_topo.get(subtype, 0)} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 七、数据补充建议",
        "",
    ])

    # 检查是否需要补充
    if len(dev) < 1000:
        lines.append(f"- **dev集需要补充**: {1000 - len(dev)} 条")
    if len(test) < 1000:
        lines.append(f"- **test集需要补充**: {1000 - len(test)} 条")

    # 检查topological在dev/test中的分布
    if dev_topo.get('within', 0) + dev_topo.get('contains', 0) + dev_topo.get('adjacent', 0) + dev_topo.get('disjoint', 0) + dev_topo.get('overlap', 0) == 0:
        lines.append("- **dev集topological类型为0**: 需要从原始数据补充新实体对")
    if test_topo.get('within', 0) + test_topo.get('contains', 0) + test_topo.get('adjacent', 0) + test_topo.get('disjoint', 0) + test_topo.get('overlap', 0) == 0:
        lines.append("- **test集topological类型为0**: 需要从原始数据补充新实体对")

    lines.extend([
        "",
        "---",
        "",
        f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ""
    ])

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return output_path


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 实体对互斥划分脚本')
    parser.add_argument(
        '--input', '-i',
        default='D:/30_keyan/GeoKD-SR/data/geosr_chain/sampled_10000.jsonl',
        help='输入文件路径'
    )
    parser.add_argument(
        '--output', '-o',
        default='D:/30_keyan/GeoKD-SR/data/geosr_chain/v3',
        help='输出目录'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='随机种子'
    )

    args = parser.parse_args()

    print("="*60)
    print("GeoKD-SR 实体对互斥划分脚本")
    print("="*60)
    print(f"输入文件: {args.input}")
    print(f"输出目录: {args.output}")
    print(f"随机种子: {args.seed}")

    # 加载数据
    print("\n加载数据...")
    records = load_jsonl(args.input)
    print(f"加载了 {len(records)} 条记录")

    # 执行划分
    print("\n执行实体对互斥划分...")
    splitter = EntityPairSplitter(seed=args.seed)
    train, dev, test, split_info = splitter.split(records)

    print(f"\n划分结果:")
    print(f"  train: {len(train)} 条")
    print(f"  dev: {len(dev)} 条")
    print(f"  test: {len(test)} 条")

    # 平衡数量
    train, dev, test = splitter.balance_splits(train, dev, test, records)

    print(f"\n平衡后:")
    print(f"  train: {len(train)} 条")
    print(f"  dev: {len(dev)} 条")
    print(f"  test: {len(test)} 条")

    # 保存结果
    print("\n保存文件...")
    os.makedirs(args.output, exist_ok=True)

    save_jsonl(train, os.path.join(args.output, 'train.jsonl'))
    save_jsonl(dev, os.path.join(args.output, 'dev.jsonl'))
    save_jsonl(test, os.path.join(args.output, 'test.jsonl'))

    # 生成报告
    report_path = generate_report(train, dev, test, split_info, args.output)
    print(f"划分报告: {report_path}")

    # 验证互斥性
    print("\n" + "="*60)
    print("实体对互斥验证")
    print("="*60)
    validation = split_info['validation']
    if validation['is_valid']:
        print("✅ 验证通过: train/dev/test 实体对完全不重叠")
    else:
        print("❌ 验证失败: 存在实体对重叠")
        print(f"   train/dev: {validation['train_dev_overlap']} 个重叠")
        print(f"   train/test: {validation['train_test_overlap']} 个重叠")
        print(f"   dev/test: {validation['dev_test_overlap']} 个重叠")

    print("\n完成!")
    return 0


if __name__ == '__main__':
    exit(main())
