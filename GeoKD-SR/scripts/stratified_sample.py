#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 分层采样脚本

功能：
1. 按空间关系类型 × 难度分层采样
2. 确保拓扑子类型均匀分布
3. 采样指定数量的记录
4. 输出采样后的数据集

目标分布 (V2.1规范):
- directional: 25%
- topological: 27.5%
- metric: 27.5%
- composite: 20%

难度分布:
- easy: 30%
- medium: 50%
- hard: 20%

拓扑子类型分布 (仅topological):
- within: 20%
- contains: 20%
- adjacent: 20%
- disjoint: 20%
- overlap: 20%

使用方法：
    python scripts/stratified_sample.py --input data/geosr_chain/raw_merged.jsonl --output data/geosr_chain/sampled_10000.jsonl --total 10000
"""

import json
import argparse
import os
import random
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import Counter, defaultdict
from datetime import datetime


class StratifiedSampler:
    """分层采样器"""

    # 目标分布配置
    SPATIAL_DISTRIBUTION = {
        'directional': 0.25,
        'topological': 0.275,
        'metric': 0.275,
        'composite': 0.20
    }

    DIFFICULTY_DISTRIBUTION = {
        'easy': 0.30,
        'medium': 0.50,
        'hard': 0.20
    }

    TOPOLOGY_SUBTYPE_DISTRIBUTION = {
        'within': 0.20,
        'contains': 0.20,
        'adjacent': 0.20,
        'disjoint': 0.20,
        'overlap': 0.20
    }

    def __init__(self, total: int = 10000, seed: int = 42):
        self.total = total
        self.seed = seed
        random.seed(seed)

        # 计算各层的目标数量
        self._calculate_targets()

    def _calculate_targets(self):
        """计算各层的目标数量"""
        # 空间关系 × 难度 交叉分布
        self.cross_targets = {}
        for spatial, spatial_pct in self.SPATIAL_DISTRIBUTION.items():
            for diff, diff_pct in self.DIFFICULTY_DISTRIBUTION.items():
                key = (spatial, diff)
                target = int(self.total * spatial_pct * diff_pct)
                self.cross_targets[key] = target

        # 拓扑子类型目标数量
        topo_total = int(self.total * self.SPATIAL_DISTRIBUTION['topological'])
        self.topo_subtype_targets = {
            subtype: int(topo_total * pct)
            for subtype, pct in self.TOPOLOGY_SUBTYPE_DISTRIBUTION.items()
        }

    def sample(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行分层采样"""
        # 按 (spatial_type, difficulty, topo_subtype) 分组
        groups = defaultdict(list)

        for record in records:
            spatial = record.get('spatial_relation_type', 'unknown')
            difficulty = record.get('difficulty', 'unknown')
            topo_subtype = record.get('topology_subtype', 'none')

            # 主键：空间类型 × 难度
            key = (spatial, difficulty)
            # 子键：拓扑子类型（仅对topological）
            sub_key = (key, topo_subtype if spatial == 'topological' else 'none')

            groups[sub_key].append(record)

        # 采样
        sampled = []
        sampled_stats = defaultdict(lambda: defaultdict(int))

        # 首先处理topological类型（需要考虑子类型平衡）
        topo_sampled = defaultdict(list)
        topo_key = 'topological'

        for diff in ['easy', 'medium', 'hard']:
            cross_key = (topo_key, diff)
            cross_target = self.cross_targets.get(cross_key, 0)

            # 按子类型分配
            for subtype in self.TOPOLOGY_SUBTYPE_DISTRIBUTION.keys():
                sub_key = (cross_key, subtype)
                if sub_key in groups:
                    subtype_target = int(cross_target * self.TOPOLOGY_SUBTYPE_DISTRIBUTION[subtype])
                    available = groups[sub_key]
                    random.shuffle(available)

                    # 采样
                    n = min(subtype_target, len(available))
                    selected = available[:n]
                    topo_sampled[subtype].extend(selected)

                    for r in selected:
                        sampled_stats[topo_key][diff] += 1
                        sampled_stats[f'{topo_key}_{subtype}'][diff] += 1

        # 将topological采样结果加入总结果
        for subtype_records in topo_sampled.values():
            sampled.extend(subtype_records)

        # 处理其他类型
        for spatial in ['directional', 'metric', 'composite']:
            for diff in ['easy', 'medium', 'hard']:
                cross_key = (spatial, diff)
                target = self.cross_targets.get(cross_key, 0)
                sub_key = (cross_key, 'none')

                if sub_key in groups:
                    available = groups[sub_key]
                    random.shuffle(available)

                    n = min(target, len(available))
                    selected = available[:n]
                    sampled.extend(selected)

                    for r in selected:
                        sampled_stats[spatial][diff] += 1

        # 如果数量不足，从剩余记录中补充
        current_total = len(sampled)
        if current_total < self.total:
            # 获取已采样的ID集合
            sampled_ids = set(r.get('id') for r in sampled)

            # 剩余记录
            remaining = [r for r in records if r.get('id') not in sampled_ids]
            random.shuffle(remaining)

            # 补充
            needed = self.total - current_total
            sampled.extend(remaining[:needed])
            print(f"补充了 {min(needed, len(remaining))} 条记录")

        # 如果数量超过，随机裁剪
        if len(sampled) > self.total:
            random.shuffle(sampled)
            sampled = sampled[:self.total]
            print(f"裁剪到 {self.total} 条记录")

        return sampled, sampled_stats

    def get_distribution_report(self, records: List[Dict[str, Any]]) -> Dict:
        """获取分布报告"""
        spatial_dist = Counter(r.get('spatial_relation_type', 'unknown') for r in records)
        difficulty_dist = Counter(r.get('difficulty', 'unknown') for r in records)

        topo_subtypes = Counter(
            r.get('topology_subtype', 'none')
            for r in records
            if r.get('spatial_relation_type') == 'topological'
        )

        cross_dist = Counter(
            (r.get('spatial_relation_type', 'unknown'), r.get('difficulty', 'unknown'))
            for r in records
        )

        return {
            'total': len(records),
            'spatial_distribution': dict(spatial_dist),
            'difficulty_distribution': dict(difficulty_dist),
            'topology_subtype_distribution': dict(topo_subtypes),
            'cross_distribution': {f"{k[0]}_{k[1]}": v for k, v in cross_dist.items()}
        }


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


def generate_report(original_stats: Dict, sampled_stats: Dict, output_path: str):
    """生成采样报告"""
    lines = [
        "# GeoKD-SR 分层采样报告",
        "",
        f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## 一、采样概览",
        "",
        f"- **原始记录数**: {original_stats['total']}",
        f"- **采样记录数**: {sampled_stats['total']}",
        "",
        "---",
        "",
        "## 二、空间关系类型分布对比",
        "",
        "| 类型 | 原始数量 | 原始占比 | 采样数量 | 采样占比 | 目标占比 |",
        "|------|----------|----------|----------|----------|----------|",
    ]

    targets = StratifiedSampler.SPATIAL_DISTRIBUTION
    for dtype in ['directional', 'topological', 'metric', 'composite']:
        orig_count = original_stats['spatial_distribution'].get(dtype, 0)
        orig_pct = orig_count / max(original_stats['total'], 1) * 100
        samp_count = sampled_stats['spatial_distribution'].get(dtype, 0)
        samp_pct = samp_count / max(sampled_stats['total'], 1) * 100
        target_pct = targets.get(dtype, 0) * 100
        lines.append(f"| {dtype} | {orig_count} | {orig_pct:.1f}% | {samp_count} | {samp_pct:.1f}% | {target_pct:.1f}% |")

    lines.extend([
        "",
        "---",
        "",
        "## 三、难度分布对比",
        "",
        "| 难度 | 原始数量 | 原始占比 | 采样数量 | 采样占比 | 目标占比 |",
        "|------|----------|----------|----------|----------|----------|",
    ])

    diff_targets = StratifiedSampler.DIFFICULTY_DISTRIBUTION
    for dtype in ['easy', 'medium', 'hard']:
        orig_count = original_stats['difficulty_distribution'].get(dtype, 0)
        orig_pct = orig_count / max(original_stats['total'], 1) * 100
        samp_count = sampled_stats['difficulty_distribution'].get(dtype, 0)
        samp_pct = samp_count / max(sampled_stats['total'], 1) * 100
        target_pct = diff_targets.get(dtype, 0) * 100
        lines.append(f"| {dtype} | {orig_count} | {orig_pct:.1f}% | {samp_count} | {samp_pct:.1f}% | {target_pct:.1f}% |")

    lines.extend([
        "",
        "---",
        "",
        "## 四、拓扑子类型分布对比",
        "",
        "| 子类型 | 原始数量 | 采样数量 | 目标占比 |",
        "|--------|----------|----------|----------|",
    ])

    topo_targets = StratifiedSampler.TOPOLOGY_SUBTYPE_DISTRIBUTION
    for subtype in ['within', 'contains', 'adjacent', 'disjoint', 'overlap']:
        orig_count = original_stats['topology_subtype_distribution'].get(subtype, 0)
        samp_count = sampled_stats['topology_subtype_distribution'].get(subtype, 0)
        target_pct = topo_targets.get(subtype, 0) * 100
        lines.append(f"| {subtype} | {orig_count} | {samp_count} | {target_pct:.1f}% |")

    lines.extend([
        "",
        "---",
        "",
        f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ""
    ])

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 分层采样脚本')
    parser.add_argument(
        '--input', '-i',
        default='D:/30_keyan/GeoKD-SR/data/geosr_chain/raw_merged.jsonl',
        help='输入文件路径'
    )
    parser.add_argument(
        '--output', '-o',
        default='D:/30_keyan/GeoKD-SR/data/geosr_chain/sampled_10000.jsonl',
        help='输出文件路径'
    )
    parser.add_argument(
        '--total', '-t',
        type=int,
        default=10000,
        help='目标采样数量'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='随机种子'
    )

    args = parser.parse_args()

    print("="*60)
    print("GeoKD-SR 分层采样脚本")
    print("="*60)
    print(f"输入文件: {args.input}")
    print(f"输出文件: {args.output}")
    print(f"目标数量: {args.total}")
    print(f"随机种子: {args.seed}")

    # 加载数据
    print("\n加载数据...")
    records = load_jsonl(args.input)
    print(f"加载了 {len(records)} 条记录")

    # 原始分布统计
    sampler = StratifiedSampler(args.total, args.seed)
    original_stats = sampler.get_distribution_report(records)

    # 执行采样
    print("\n执行分层采样...")
    sampled_records, sample_stats = sampler.sample(records)
    print(f"采样完成: {len(sampled_records)} 条记录")

    # 采样后分布统计
    sampled_stats = sampler.get_distribution_report(sampled_records)

    # 保存结果
    print(f"\n保存到: {args.output}")
    save_jsonl(sampled_records, args.output)

    # 生成报告
    report_path = args.output.replace('.jsonl', '_report.md')
    generate_report(original_stats, sampled_stats, report_path)
    print(f"采样报告: {report_path}")

    # 打印摘要
    print("\n" + "="*60)
    print("采样结果摘要")
    print("="*60)
    print(f"原始记录数: {original_stats['total']}")
    print(f"采样记录数: {sampled_stats['total']}")

    print("\n空间关系类型分布:")
    for dtype in ['directional', 'topological', 'metric', 'composite']:
        count = sampled_stats['spatial_distribution'].get(dtype, 0)
        pct = count / max(sampled_stats['total'], 1) * 100
        target = sampler.SPATIAL_DISTRIBUTION.get(dtype, 0) * 100
        print(f"  {dtype}: {count} ({pct:.1f}%) [目标: {target:.1f}%]")

    print("\n难度分布:")
    for dtype in ['easy', 'medium', 'hard']:
        count = sampled_stats['difficulty_distribution'].get(dtype, 0)
        pct = count / max(sampled_stats['total'], 1) * 100
        target = sampler.DIFFICULTY_DISTRIBUTION.get(dtype, 0) * 100
        print(f"  {dtype}: {count} ({pct:.1f}%) [目标: {target:.1f}%]")

    print("\n完成!")
    return 0


if __name__ == '__main__':
    exit(main())
