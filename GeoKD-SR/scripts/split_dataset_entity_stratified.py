#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 实体对互斥分层划分脚本 (V3.0 - 改进版)

核心功能：
1. 严格确保 train/dev/test 实体对完全不重叠（实体互斥）
2. 分层贪心分配，确保分布一致性
3. 支持空间类型 + 难度 + 拓扑子类型的24层分布
4. 生成详细验证报告

V3.0 改进：
- 采用"比例优先"策略：先按比例分配实体对数量
- 在满足数量比例的前提下，优化分布一致性
- 使用轮询分配确保各split数量平衡

算法：比例优先分层分配
1. 计算每个split的目标实体对数量
2. 轮询分配实体对，优先分配到数量最少的split
3. 在数量相近时，选择分布偏差最小的split

使用方法：
    python scripts/split_dataset_entity_stratified.py \
        --input data/final/final_1_v6_cleaned.jsonl \
        --output data/final/splits \
        --ratio 0.8:0.1:0.1 \
        --seed 42

作者: GeoKD-SR Team
日期: 2026-03-14
"""

import json
import argparse
import os
import sys
import io
import random
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple, Optional
from collections import Counter, defaultdict
from datetime import datetime

# Windows 控制台编码修复
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class EntityAwareStratifiedSplitter:
    """实体对互斥分层划分器 (V3.0)"""

    def __init__(self, train_ratio: float = 0.8, dev_ratio: float = 0.1,
                 test_ratio: float = 0.1, seed: int = 42, tvd_threshold: float = 0.10):
        """
        初始化划分器
        """
        assert abs(train_ratio + dev_ratio + test_ratio - 1.0) < 0.001, "比例之和必须为1"

        self.train_ratio = train_ratio
        self.dev_ratio = dev_ratio
        self.test_ratio = test_ratio
        self.seed = seed
        self.tvd_threshold = tvd_threshold

        random.seed(seed)

        self.split_ratios = {
            'train': train_ratio,
            'dev': dev_ratio,
            'test': test_ratio
        }

    def get_entity_pair_key(self, entities: List[Dict]) -> Optional[Tuple[str, str]]:
        """提取实体对标识（sorted确保一致性）"""
        if not entities or not isinstance(entities, list) or len(entities) < 2:
            return None

        names = []
        for entity in entities[:2]:
            if isinstance(entity, dict):
                name = entity.get('name', '')
            else:
                name = str(entity)
            if name:
                names.append(name)

        if len(names) < 2:
            return None

        names.sort()
        return (names[0], names[1])

    def get_layer_key(self, record: Dict) -> Tuple:
        """获取分层键 (spatial_relation_type, difficulty, topology_subtype)"""
        spatial_type = record.get('spatial_relation_type', 'unknown')
        difficulty = record.get('difficulty', 'unknown')

        if spatial_type == 'topological':
            topo_subtype = record.get('topology_subtype', 'unknown')
            return (spatial_type, difficulty, topo_subtype)
        else:
            return (spatial_type, difficulty, None)

    def calculate_distribution(self, records: List[Dict]) -> Counter:
        """计算记录的层分布"""
        dist = Counter()
        for record in records:
            layer_key = self.get_layer_key(record)
            dist[layer_key] += 1
        return dist

    def calculate_tvd(self, actual_dist: Counter, target_dist: Counter) -> float:
        """计算总变差距离 (Total Variation Distance)"""
        all_keys = set(actual_dist.keys()) | set(target_dist.keys())

        actual_total = sum(actual_dist.values()) or 1
        target_total = sum(target_dist.values()) or 1

        tvd = 0.0
        for key in all_keys:
            actual_ratio = actual_dist.get(key, 0) / actual_total
            target_ratio = target_dist.get(key, 0) / target_total
            tvd += abs(actual_ratio - target_ratio)

        return tvd / 2

    def split(self, records: List[Dict[str, Any]]) -> Tuple[List, List, List, Dict]:
        """
        执行实体对互斥分层划分

        V3.0 策略：比例优先轮询分配
        1. 计算每个split的目标记录数量
        2. 按实体对记录数降序排列
        3. 轮询分配：选择当前记录数与目标比例差距最大的split
        4. 在比例相近时，选择分布偏差最小的split

        Args:
            records: 数据记录列表

        Returns:
            (train_records, dev_records, test_records, split_info)
        """
        print(f"\n{'='*60}")
        print("开始比例优先分层分配 (V3.0)...")
        print(f"{'='*60}")

        # Step 1: 按实体对分组
        print("\n[1/6] 按实体对分组...")
        pair_groups = defaultdict(list)
        no_entity_records = []

        for record in records:
            entity_pair = self.get_entity_pair_key(record.get('entities', []))
            if entity_pair:
                pair_groups[entity_pair].append(record)
            else:
                no_entity_records.append(record)

        total_records = len(records)
        total_pairs = len(pair_groups)

        print(f"  总记录数: {total_records}")
        print(f"  实体对数: {total_pairs}")
        print(f"  无实体对记录: {len(no_entity_records)}")

        # Step 2: 计算目标数量和分布
        print("\n[2/6] 计算目标数量和分布...")
        overall_dist = self.calculate_distribution(records)

        target_counts = {
            'train': int(total_records * self.train_ratio),
            'dev': int(total_records * self.dev_ratio),
            'test': int(total_records * self.test_ratio)
        }

        target_dists = {}
        for split_name, ratio in self.split_ratios.items():
            target_dist = Counter()
            for layer_key, count in overall_dist.items():
                target_dist[layer_key] = int(count * ratio)
            target_dists[split_name] = target_dist

        print(f"  目标数量: train={target_counts['train']}, dev={target_counts['dev']}, test={target_counts['test']}")

        # Step 3: 初始化split状态
        print("\n[3/6] 初始化split状态...")
        splits_state = {
            'train': {'records': [], 'dist': Counter()},
            'dev': {'records': [], 'dist': Counter()},
            'test': {'records': [], 'dist': Counter()}
        }
        assigned_pairs = {
            'train': set(),
            'dev': set(),
            'test': set()
        }

        # Step 4: 比例优先轮询分配
        print("\n[4/6] 执行比例优先轮询分配...")

        # 按实体对记录数降序排列
        sorted_pairs = sorted(pair_groups.items(), key=lambda x: -len(x[1]))

        # 随机打乱相同记录数的实体对，增加随机性
        random.shuffle(sorted_pairs)

        progress_interval = max(1, total_pairs // 10)

        for idx, (entity_pair, pair_records) in enumerate(sorted_pairs):
            if idx % progress_interval == 0:
                print(f"  进度: {idx}/{total_pairs} ({idx/total_pairs*100:.1f}%)")

            # 计算各split当前比例与目标比例的差距
            gaps = {}
            for split_name in ['train', 'dev', 'test']:
                current_count = len(splits_state[split_name]['records'])
                target_count = target_counts[split_name]

                # 计算当前比例与目标比例的差距
                if target_count > 0:
                    current_ratio = current_count / target_count
                    gap = 1.0 - current_ratio  # 差距越大，越应该分配到这个split
                else:
                    gap = 0

                gaps[split_name] = gap

            # 选择差距最大的split（优先填充比例最低的）
            # 如果差距相近（差距差小于0.1），则选择分布偏差最小的
            max_gap = max(gaps.values())
            candidates = [s for s, g in gaps.items() if abs(g - max_gap) < 0.05]

            if len(candidates) > 1:
                # 差距相近，选择分布偏差最小的
                best_split = None
                best_tvd = float('inf')

                for split_name in candidates:
                    current_dist = splits_state[split_name]['dist']
                    # 模拟添加后的分布
                    simulated_dist = Counter(current_dist)
                    for record in pair_records:
                        layer_key = self.get_layer_key(record)
                        simulated_dist[layer_key] += 1

                    tvd = self.calculate_tvd(simulated_dist, target_dists[split_name])
                    if tvd < best_tvd:
                        best_tvd = tvd
                        best_split = split_name
            else:
                best_split = candidates[0]

            # 分配
            splits_state[best_split]['records'].extend(pair_records)
            for record in pair_records:
                layer_key = self.get_layer_key(record)
                splits_state[best_split]['dist'][layer_key] += 1
            assigned_pairs[best_split].add(entity_pair)

        print(f"  完成: {total_pairs}/{total_pairs} (100.0%)")

        # Step 5: 处理无实体对记录（按比例分配）
        if no_entity_records:
            print(f"\n[5/6] 处理无实体对记录 ({len(no_entity_records)}条)...")
            random.shuffle(no_entity_records)

            n_train = int(len(no_entity_records) * self.train_ratio)
            n_dev = int(len(no_entity_records) * self.dev_ratio)

            splits_state['train']['records'].extend(no_entity_records[:n_train])
            splits_state['dev']['records'].extend(no_entity_records[n_train:n_train+n_dev])
            splits_state['test']['records'].extend(no_entity_records[n_train+n_dev:])

        # Step 6: 打乱顺序并添加split字段
        print("\n[6/6] 打乱顺序并添加split字段...")
        train_records = splits_state['train']['records']
        dev_records = splits_state['dev']['records']
        test_records = splits_state['test']['records']

        random.shuffle(train_records)
        random.shuffle(dev_records)
        random.shuffle(test_records)

        for record in train_records:
            record['split'] = 'train'
        for record in dev_records:
            record['split'] = 'dev'
        for record in test_records:
            record['split'] = 'test'

        # 验证
        print(f"\n{'='*60}")
        print("验证划分结果...")
        print(f"{'='*60}")

        validation = self._validate_split(
            train_records, dev_records, test_records,
            assigned_pairs, overall_dist
        )

        # 构建split_info
        split_info = {
            'validation': validation,
            'counts': {
                'train': len(train_records),
                'dev': len(dev_records),
                'test': len(test_records),
                'total': len(records)
            },
            'entity_pairs': {
                'train': len(assigned_pairs['train']),
                'dev': len(assigned_pairs['dev']),
                'test': len(assigned_pairs['test'])
            },
            'distributions': {
                'overall': dict(overall_dist),
                'train': dict(splits_state['train']['dist']),
                'dev': dict(splits_state['dev']['dist']),
                'test': dict(splits_state['test']['dist'])
            }
        }

        return train_records, dev_records, test_records, split_info

    def _validate_split(self, train_records: List, dev_records: List, test_records: List,
                        assigned_pairs: Dict, overall_dist: Counter) -> Dict:
        """验证划分结果"""
        validation = {
            'entity_exclusion': {
                'train_dev_overlap': 0,
                'train_test_overlap': 0,
                'dev_test_overlap': 0,
                'is_valid': True
            },
            'distribution_consistency': {},
            'count_ratio': {},
            'is_valid': True,
            'issues': [],
            'warnings': []
        }

        # 实体对互斥验证
        train_pairs = assigned_pairs['train']
        dev_pairs = assigned_pairs['dev']
        test_pairs = assigned_pairs['test']

        train_dev_overlap = train_pairs & dev_pairs
        train_test_overlap = train_pairs & test_pairs
        dev_test_overlap = dev_pairs & test_pairs

        validation['entity_exclusion']['train_dev_overlap'] = len(train_dev_overlap)
        validation['entity_exclusion']['train_test_overlap'] = len(train_test_overlap)
        validation['entity_exclusion']['dev_test_overlap'] = len(dev_test_overlap)

        if train_dev_overlap or train_test_overlap or dev_test_overlap:
            validation['entity_exclusion']['is_valid'] = False
            validation['is_valid'] = False
            validation['issues'].append(f"实体对重叠: train/dev={len(train_dev_overlap)}, "
                                        f"train/test={len(train_test_overlap)}, "
                                        f"dev/test={len(dev_test_overlap)}")

        print(f"\n  实体对互斥验证:")
        print(f"    train/dev重叠: {len(train_dev_overlap)} {'✅' if len(train_dev_overlap)==0 else '❌'}")
        print(f"    train/test重叠: {len(train_test_overlap)} {'✅' if len(train_test_overlap)==0 else '❌'}")
        print(f"    dev/test重叠: {len(dev_test_overlap)} {'✅' if len(dev_test_overlap)==0 else '❌'}")

        # 分布一致性验证
        total = len(train_records) + len(dev_records) + len(test_records)

        for split_name, split_records in [('train', train_records), ('dev', dev_records), ('test', test_records)]:
            split_dist = self.calculate_distribution(split_records)
            tvd = self.calculate_tvd(split_dist, overall_dist)

            validation['distribution_consistency'][split_name] = {
                'tvd': tvd,
                'is_acceptable': tvd < self.tvd_threshold
            }

            if tvd >= self.tvd_threshold:
                validation['warnings'].append(f"{split_name}分布偏差: TVD={tvd:.4f}")

            status = '✅' if tvd < self.tvd_threshold else '⚠️' if tvd < 0.15 else '❌'
            print(f"  {split_name}分布一致性: TVD={tvd:.4f} {status}")

        # 数量比例验证
        for split_name, split_records in [('train', train_records), ('dev', dev_records), ('test', test_records)]:
            expected_ratio = self.split_ratios[split_name]
            actual_ratio = len(split_records) / total
            deviation = abs(actual_ratio - expected_ratio)

            validation['count_ratio'][split_name] = {
                'expected': expected_ratio,
                'actual': actual_ratio,
                'deviation': deviation,
                'is_acceptable': deviation < 0.05
            }

            if deviation >= 0.05:
                validation['is_valid'] = False
                validation['issues'].append(f"{split_name}数量比例偏差过大: {deviation:.2%}")

        print(f"\n  数量比例:")
        print(f"    train: {len(train_records)} ({len(train_records)/total*100:.1f}%), 目标{self.train_ratio*100:.1f}%")
        print(f"    dev: {len(dev_records)} ({len(dev_records)/total*100:.1f}%), 目标{self.dev_ratio*100:.1f}%")
        print(f"    test: {len(test_records)} ({len(test_records)/total*100:.1f}%), 目标{self.test_ratio*100:.1f}%")

        return validation


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
                    split_info: Dict, args, output_dir: str) -> str:
    """生成划分报告"""
    output_path = os.path.join(output_dir, 'split_report.md')

    # 计算分布
    def get_spatial_dist(records):
        return Counter(r.get('spatial_relation_type', 'unknown') for r in records)

    def get_difficulty_dist(records):
        return Counter(r.get('difficulty', 'unknown') for r in records)

    def get_topo_subtype_dist(records):
        return Counter(
            r.get('topology_subtype', 'none')
            for r in records
            if r.get('spatial_relation_type') == 'topological'
        )

    train_spatial = get_spatial_dist(train)
    dev_spatial = get_spatial_dist(dev)
    test_spatial = get_spatial_dist(test)

    train_diff = get_difficulty_dist(train)
    dev_diff = get_difficulty_dist(dev)
    test_diff = get_difficulty_dist(test)

    train_topo = get_topo_subtype_dist(train)
    dev_topo = get_topo_subtype_dist(dev)
    test_topo = get_topo_subtype_dist(test)

    total = len(train) + len(dev) + len(test)
    validation = split_info['validation']

    lines = [
        "# GeoKD-SR 实体对互斥分层划分报告",
        "",
        f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> **输入文件**: {args.input}",
        f"> **划分比例**: train={args.train_ratio:.1%}, dev={args.dev_ratio:.1%}, test={args.test_ratio:.1%}",
        f"> **随机种子**: {args.seed}",
        f"> **TVD阈值**: {args.tvd_threshold}",
        "",
        "---",
        "",
        "## 一、划分概览",
        "",
        f"| 数据集 | 记录数 | 实体对数 | 占比 |",
        f"|--------|--------|----------|------|",
        f"| train  | {len(train)} | {split_info['entity_pairs']['train']} | {len(train)/total*100:.1f}% |",
        f"| dev    | {len(dev)} | {split_info['entity_pairs']['dev']} | {len(dev)/total*100:.1f}% |",
        f"| test   | {len(test)} | {split_info['entity_pairs']['test']} | {len(test)/total*100:.1f}% |",
        f"| **总计** | **{total}** | - | **100.0%** |",
        "",
        "---",
        "",
        "## 二、实体对互斥验证",
        "",
        f"| 检查项 | 重叠数 | 状态 |",
        f"|--------|--------|------|",
        f"| train ∩ dev | {validation['entity_exclusion']['train_dev_overlap']} | {'✅ 通过' if validation['entity_exclusion']['train_dev_overlap']==0 else '❌ 失败'} |",
        f"| train ∩ test | {validation['entity_exclusion']['train_test_overlap']} | {'✅ 通过' if validation['entity_exclusion']['train_test_overlap']==0 else '❌ 失败'} |",
        f"| dev ∩ test | {validation['entity_exclusion']['dev_test_overlap']} | {'✅ 通过' if validation['entity_exclusion']['dev_test_overlap']==0 else '❌ 失败'} |",
        "",
        f"**结论**: {'✅ 实体对完全互斥' if validation['entity_exclusion']['is_valid'] else '❌ 存在实体对重叠'}",
        "",
        "---",
        "",
        "## 三、分布一致性验证",
        "",
        "### 3.1 空间关系类型分布",
        "",
        "| 类型 | train | dev | test | 目标 |",
        "|------|-------|-----|------|------|",
    ]

    # 计算整体分布作为目标
    overall_spatial = get_spatial_dist(train + dev + test)

    for dtype in ['directional', 'topological', 'metric', 'composite']:
        train_pct = train_spatial.get(dtype, 0) / len(train) * 100 if train else 0
        dev_pct = dev_spatial.get(dtype, 0) / len(dev) * 100 if dev else 0
        test_pct = test_spatial.get(dtype, 0) / len(test) * 100 if test else 0
        target_pct = overall_spatial.get(dtype, 0) / total * 100 if total else 0
        lines.append(
            f"| {dtype} | {train_spatial.get(dtype, 0)} ({train_pct:.1f}%) | "
            f"{dev_spatial.get(dtype, 0)} ({dev_pct:.1f}%) | "
            f"{test_spatial.get(dtype, 0)} ({test_pct:.1f}%) | "
            f"{overall_spatial.get(dtype, 0)} ({target_pct:.1f}%) |"
        )

    lines.extend([
        "",
        "### 3.2 难度分布",
        "",
        "| 难度 | train | dev | test | 目标 |",
        "|------|-------|-----|------|------|",
    ])

    overall_diff = get_difficulty_dist(train + dev + test)

    for dtype in ['easy', 'medium', 'hard']:
        train_pct = train_diff.get(dtype, 0) / len(train) * 100 if train else 0
        dev_pct = dev_diff.get(dtype, 0) / len(dev) * 100 if dev else 0
        test_pct = test_diff.get(dtype, 0) / len(test) * 100 if test else 0
        target_pct = overall_diff.get(dtype, 0) / total * 100 if total else 0
        lines.append(
            f"| {dtype} | {train_diff.get(dtype, 0)} ({train_pct:.1f}%) | "
            f"{dev_diff.get(dtype, 0)} ({dev_pct:.1f}%) | "
            f"{test_diff.get(dtype, 0)} ({test_pct:.1f}%) | "
            f"{overall_diff.get(dtype, 0)} ({target_pct:.1f}%) |"
        )

    lines.extend([
        "",
        "### 3.3 拓扑子类型分布 (仅topological)",
        "",
        "| 子类型 | train | dev | test |",
        "|--------|-------|-----|------|",
    ])

    for subtype in ['within', 'contains', 'adjacent', 'disjoint', 'overlap']:
        lines.append(
            f"| {subtype} | {train_topo.get(subtype, 0)} | "
            f"{dev_topo.get(subtype, 0)} | "
            f"{test_topo.get(subtype, 0)} |"
        )

    lines.extend([
        "",
        "### 3.4 TVD统计",
        "",
        "| Split | TVD | 评价 |",
        "|-------|-----|------|",
    ])

    for split_name in ['train', 'dev', 'test']:
        tvd_info = validation['distribution_consistency'].get(split_name, {})
        tvd = tvd_info.get('tvd', 0)
        if tvd < 0.05:
            status = "优秀 ✅"
        elif tvd < 0.10:
            status = "良好 ✅"
        elif tvd < 0.15:
            status = "可接受 ⚠️"
        else:
            status = "需改进 ❌"
        lines.append(f"| {split_name} | {tvd:.4f} | {status} |")

    lines.extend([
        "",
        "---",
        "",
        "## 四、验证结论",
        "",
    ])

    if validation['is_valid']:
        lines.append("**✅ 划分验证通过**")
    else:
        lines.append("**❌ 划分验证失败**")

    if validation['issues']:
        lines.append("")
        lines.append("### 问题列表")
        lines.append("")
        for issue in validation['issues']:
            lines.append(f"- ❌ {issue}")

    if validation['warnings']:
        lines.append("")
        lines.append("### 警告列表")
        lines.append("")
        for warning in validation['warnings']:
            lines.append(f"- ⚠️ {warning}")

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


def parse_ratio(ratio_str: str) -> Tuple[float, float, float]:
    """解析比例字符串"""
    parts = ratio_str.split(':')
    if len(parts) != 3:
        raise ValueError(f"比例格式错误: {ratio_str}，应为 'train:dev:test'")

    ratios = tuple(float(p.strip()) for p in parts)
    if abs(sum(ratios) - 1.0) > 0.001:
        raise ValueError(f"比例之和必须等于1: {sum(ratios)}")

    return ratios


def main():
    parser = argparse.ArgumentParser(
        description='GeoKD-SR 实体对互斥分层划分脚本 V3.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/split_dataset_entity_stratified.py \\
        --input data/final/final_1_v6_cleaned.jsonl \\
        --output data/final/splits \\
        --ratio 0.8:0.1:0.1 \\
        --seed 42
        """
    )

    parser.add_argument(
        '--input', '-i',
        required=True,
        help='输入文件路径 (JSONL格式)'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='输出目录'
    )
    parser.add_argument(
        '--ratio',
        default='0.8:0.1:0.1',
        help='划分比例，格式为train:dev:test（默认0.8:0.1:0.1）'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='随机种子（默认42）'
    )
    parser.add_argument(
        '--tvd-threshold',
        type=float,
        default=0.10,
        help='TVD阈值，低于此值认为分布一致（默认0.10）'
    )

    args = parser.parse_args()

    # 解析比例
    train_ratio, dev_ratio, test_ratio = parse_ratio(args.ratio)
    args.train_ratio = train_ratio
    args.dev_ratio = dev_ratio
    args.test_ratio = test_ratio

    print("="*60)
    print("GeoKD-SR 实体对互斥分层划分脚本 V3.0")
    print("="*60)
    print(f"输入文件: {args.input}")
    print(f"输出目录: {args.output}")
    print(f"划分比例: train={train_ratio:.1%}, dev={dev_ratio:.1%}, test={test_ratio:.1%}")
    print(f"随机种子: {args.seed}")
    print(f"TVD阈值: {args.tvd_threshold}")

    # 加载数据
    print("\n加载数据...")
    records = load_jsonl(args.input)
    print(f"加载了 {len(records)} 条记录")

    if len(records) == 0:
        print("错误: 没有加载到任何记录")
        return 1

    # 执行划分
    print("\n执行比例优先分层划分...")
    splitter = EntityAwareStratifiedSplitter(
        train_ratio=train_ratio,
        dev_ratio=dev_ratio,
        test_ratio=test_ratio,
        seed=args.seed,
        tvd_threshold=args.tvd_threshold
    )

    train, dev, test, split_info = splitter.split(records)

    print(f"\n{'='*60}")
    print("划分完成!")
    print(f"{'='*60}")
    print(f"  train: {len(train)} 条")
    print(f"  dev: {len(dev)} 条")
    print(f"  test: {len(test)} 条")

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    # 保存结果
    print("\n保存文件...")
    save_jsonl(train, os.path.join(args.output, 'train.jsonl'))
    save_jsonl(dev, os.path.join(args.output, 'dev.jsonl'))
    save_jsonl(test, os.path.join(args.output, 'test.jsonl'))

    # 生成报告
    report_path = generate_report(train, dev, test, split_info, args, args.output)
    print(f"划分报告: {report_path}")

    # 总结
    print(f"\n{'='*60}")
    if split_info['validation']['is_valid']:
        print("✅ 验证通过: 实体对互斥 + 分布一致性 + 数量比例")
    else:
        print("⚠️ 验证存在问题，请查看报告了解详情")

    print(f"\n输出文件:")
    print(f"  - {os.path.join(args.output, 'train.jsonl')}")
    print(f"  - {os.path.join(args.output, 'dev.jsonl')}")
    print(f"  - {os.path.join(args.output, 'test.jsonl')}")
    print(f"  - {report_path}")

    return 0


if __name__ == '__main__':
    exit(main())
