#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拓扑子类型分布验证脚本

用途：验证 prompts_config_full.json 中的拓扑子类型分布是否均衡
作者：Claude Code
日期：2026-03-08
"""

import json
from collections import Counter
from pathlib import Path


def verify_topology_distribution(file_path: str, target_ratio: float = 0.20):
    """
    验证拓扑子类型分布

    Args:
        file_path: JSON配置文件路径
        target_ratio: 目标比例（默认0.20即20%）

    Returns:
        dict: 包含验证结果的字典
    """
    # 读取数据
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompts = data['prompts']

    # 筛选拓扑类型
    topo_entries = [
        entry for entry in prompts
        if entry.get('relation_type') == 'topological'
    ]

    # 统计子类型
    subtype_counter = Counter(
        entry.get('topology_subtype')
        for entry in topo_entries
    )

    total = len(topo_entries)

    # 计算偏差
    results = {
        'total': total,
        'target_ratio': target_ratio,
        'subtypes': {},
        'max_deviation': 0,
        'is_balanced': False
    }

    for subtype in ['within', 'contains', 'adjacent', 'disjoint', 'overlap']:
        count = subtype_counter.get(subtype, 0)
        actual_ratio = count / total if total > 0 else 0
        deviation = abs(actual_ratio - target_ratio)

        results['subtypes'][subtype] = {
            'count': count,
            'actual_ratio': actual_ratio,
            'deviation': deviation
        }

        results['max_deviation'] = max(results['max_deviation'], deviation)

    # 判断是否均衡（最大偏差 < 2%）
    results['is_balanced'] = results['max_deviation'] < 0.02

    return results


def print_results(results: dict):
    """打印验证结果"""
    print('='*70)
    print('拓扑子类型分布验证结果')
    print('='*70)
    print(f'拓扑类型总数: {results["total"]}')
    print(f'目标比例: {results["target_ratio"]:.1%}')
    print()

    print('详细统计:')
    print(f"{'子类型':<12} {'数量':>6} {'实际占比':>10} {'目标占比':>10} {'偏差':>10}")
    print('-'*70)

    for subtype, data in results['subtypes'].items():
        print(f"{subtype:<12} {data['count']:>6} "
              f"{data['actual_ratio']:>10.1%} "
              f"{results['target_ratio']:>10.1%} "
              f"{data['deviation']:>10.2%}")

    print('-'*70)
    print(f'最大偏差: {results["max_deviation"]:.2%}')
    print()

    if results['is_balanced']:
        print('[OK] 结论: 分布均衡，符合要求')
    else:
        print('[WARNING] 结论: 分布偏差较大，需要修正')

    print('='*70)


if __name__ == '__main__':
    # 默认文件路径
    default_path = Path(__file__).parent.parent / 'data' / 'prompts' / 'prompts_config_full.json'

    # 执行验证
    results = verify_topology_distribution(str(default_path))

    # 打印结果
    print_results(results)

    # 返回退出码
    exit(0 if results['is_balanced'] else 1)
