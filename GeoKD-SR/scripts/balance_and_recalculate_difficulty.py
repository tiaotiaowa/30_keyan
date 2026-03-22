"""
数据平衡与难度重算脚本 V2
功能:
1. 平衡拓扑子类型分布（降低disjoint/adjacent）
2. 保持原有difficulty_score计算方法不变
3. 通过调整阈值重新映射difficulty等级
"""

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

# ==================== 配置 ====================

INPUT_FILE = "D:/30_keyan/GeoKD-SR/data/final/final_1_v5.jsonl"
OUTPUT_FILE = "D:/30_keyan/GeoKD-SR/data/final/final_1_v6.jsonl"

# 拓扑子类型目标数量
TOPOLOGY_TARGET = {
    'within': 796,
    'contains': 577,  # 保持不变
    'adjacent': 796,
    'disjoint': 796,
    'overlap': 377   # 保持不变
}

# 难度映射阈值（基于分布分析调整）
# 目标: easy 30%, medium 50%, hard 20%
# 最优阈值: easy<=1.3, hard>3.1 => easy=31.9%, medium=44.1%, hard=24.0%
EASY_THRESHOLD = 1.3   # score <= 1.3 为 easy
HARD_THRESHOLD = 3.1   # score > 3.1 为 hard

# ==================== 难度映射函数 ====================

def score_to_difficulty(score):
    """
    将 difficulty_score 映射到 difficulty 等级

    阈值说明:
    - easy: score <= 1.5 (约30%)
    - medium: 1.5 < score <= 3.2 (约50%)
    - hard: score > 3.2 (约20%)
    """
    if score <= EASY_THRESHOLD:
        return 'easy'
    elif score <= HARD_THRESHOLD:
        return 'medium'
    else:
        return 'hard'


# ==================== 数据平衡函数 ====================

def balance_topology_subtypes(data):
    """
    平衡拓扑子类型分布
    """
    topo_data = [d for d in data if d.get('spatial_relation_type') == 'topological']
    other_data = [d for d in data if d.get('spatial_relation_type') != 'topological']

    by_subtype = defaultdict(list)
    for d in topo_data:
        subtype = d.get('topology_subtype', 'unknown')
        by_subtype[subtype].append(d)

    balanced_topo = []
    for subtype, target_count in TOPOLOGY_TARGET.items():
        records = by_subtype.get(subtype, [])
        if len(records) > target_count:
            random.seed(42)
            sampled = random.sample(records, target_count)
            balanced_topo.extend(sampled)
            print(f"  {subtype}: {len(records)} -> {target_count} (删除 {len(records) - target_count})")
        else:
            balanced_topo.extend(records)
            print(f"  {subtype}: {len(records)} (保持不变)")

    return other_data + balanced_topo


def recalculate_difficulty(data):
    """
    使用新阈值重新映射 difficulty（保持原有 score 不变）
    """
    updated = 0
    for record in data:
        old_diff = record.get('difficulty')
        score = record.get('difficulty_score', 2.0)
        new_diff = score_to_difficulty(score)
        record['difficulty'] = new_diff
        if old_diff != new_diff:
            updated += 1
    return data, updated


# ==================== 主函数 ====================

def main():
    print("="*70)
    print("数据平衡与难度重算脚本 V2")
    print("="*70)

    # 1. 加载数据
    print(f"\n[1] 加载数据: {INPUT_FILE}")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = [json.loads(line) for line in f]
    print(f"  总记录数: {len(data)}")

    # 2. 平衡拓扑子类型
    print(f"\n[2] 平衡拓扑子类型分布")
    data = balance_topology_subtypes(data)
    print(f"  平衡后总记录数: {len(data)}")

    # 3. 重新映射难度
    print(f"\n[3] 重新映射难度等级 (阈值: easy<={EASY_THRESHOLD}, hard>{HARD_THRESHOLD})")
    data, updated = recalculate_difficulty(data)
    print(f"  更新记录数: {updated}")

    # 4. 统计新分布
    print(f"\n[4] 新数据分布统计")

    # 4.1 空间类型分布
    print(f"\n  空间关系类型分布:")
    type_counter = Counter(d.get('spatial_relation_type') for d in data)
    for t, count in sorted(type_counter.items()):
        pct = count / len(data) * 100
        print(f"    {t}: {count} ({pct:.1f}%)")

    # 4.2 拓扑子类型分布
    print(f"\n  拓扑子类型分布:")
    topo_data = [d for d in data if d.get('spatial_relation_type') == 'topological']
    topo_counter = Counter(d.get('topology_subtype') for d in topo_data)
    for t, count in sorted(topo_counter.items()):
        pct = count / len(topo_data) * 100 if topo_data else 0
        print(f"    {t}: {count} ({pct:.1f}%)")

    # 4.3 难度分布
    print(f"\n  难度分布:")
    diff_counter = Counter(d.get('difficulty') for d in data)
    for d_level in ['easy', 'medium', 'hard']:
        count = diff_counter.get(d_level, 0)
        pct = count / len(data) * 100
        target = {'easy': 30, 'medium': 50, 'hard': 20}[d_level]
        status = 'OK' if abs(pct - target) < 5 else 'WARN'
        print(f"    {d_level}: {count} ({pct:.1f}%) [目标: {target}%] {status}")

    # 4.4 各类型的难度分布
    print(f"\n  各空间类型的难度分布:")
    for srt in ['directional', 'topological', 'metric', 'composite']:
        srt_data = [d for d in data if d.get('spatial_relation_type') == srt]
        if srt_data:
            easy = sum(1 for d in srt_data if d.get('difficulty') == 'easy')
            medium = sum(1 for d in srt_data if d.get('difficulty') == 'medium')
            hard = sum(1 for d in srt_data if d.get('difficulty') == 'hard')
            print(f"    {srt}: easy={easy} ({easy/len(srt_data)*100:.1f}%), "
                  f"medium={medium} ({medium/len(srt_data)*100:.1f}%), "
                  f"hard={hard} ({hard/len(srt_data)*100:.1f}%)")

    # 5. 保存数据
    print(f"\n[5] 保存数据: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for record in data:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    print(f"  保存完成: {len(data)} 条记录")

    print("\n" + "="*70)
    print("处理完成!")
    print("="*70)


if __name__ == '__main__':
    main()
