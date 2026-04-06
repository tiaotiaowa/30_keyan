#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体对数据分布分析脚本
分析正例和负例中实体类型、关系类型、实体覆盖等分布情况
"""

import json
from collections import Counter, defaultdict
import os
import sys

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 数据路径
POSITIVE_PATH = r"D:\gis_data\output\pairs_positive.jsonl"
NEGATIVE_PATH = r"D:\gis_data\output\pairs_negative.jsonl"

# 12种实体类型
ENTITY_TYPES = [
    "province", "city", "peak", "attraction", "university",
    "lake", "station", "hospital", "airport", "river", "road", "railway"
]

# 关系类型设计目标数量
TARGET_DISTRIBUTION = {
    # 正例目标
    "directional": 2500,
    "metric": 2500,
    "contains": 500,
    "within": 500,
    "touches": 500,
    "crosses": 500,
    "disjoint": 500,
    "C1": 875,
    "C2": 500,
    "C3": 500,
    "C4": 625,
    # 负例目标
    "negative_contains": 150,
    "negative_within": 150,
    "negative_touches": 150,
    "negative_crosses": 150,
    "negative_disjoint": 150,
    "negative_C2": 150,
    "negative_C3": 150,
    "negative_C4": 187,
}

TOTAL_ENTITIES = 1363


def load_jsonl(file_path):
    """加载JSONL文件"""
    data = []
    if not os.path.exists(file_path):
        print(f"警告: 文件不存在 - {file_path}")
        return data

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def normalize_relation(relation_str):
    """标准化关系字符串"""
    # 处理 "topological.contains" 格式
    if "." in relation_str:
        return relation_str.split(".")[-1]
    return relation_str


def analyze_distribution(data, is_positive=True):
    """分析数据分布"""
    results = {
        "relation_counts": Counter(),
        "entity_type_combinations": defaultdict(Counter),
        "entity_appearances": Counter(),
        "entity_pair_relations": defaultdict(set),  # 无序实体对 -> 关系类型集合
        "entity_types_used": set(),
        "total_pairs": len(data),
        "entity_names": {},  # entity_id -> name
    }

    for item in data:
        # 提取关系类型
        relation_raw = item.get("target_relation", "")
        relation = normalize_relation(relation_raw)

        # 负例关系添加前缀
        if item.get("is_negative", False):
            results["relation_counts"][f"negative_{relation}"] += 1
        else:
            results["relation_counts"][relation] += 1

        # 提取实体信息
        entity_a = item.get("entity_a", {})
        entity_b = item.get("entity_b", {})

        a_id = entity_a.get("entity_id", "")
        b_id = entity_b.get("entity_id", "")
        a_type = entity_a.get("type", "unknown")
        b_type = entity_b.get("type", "unknown")
        a_name = entity_a.get("name_zh", a_id)
        b_name = entity_b.get("name_zh", b_id)

        # 记录实体名称
        results["entity_names"][a_id] = a_name
        results["entity_names"][b_id] = b_name

        # 记录实体类型
        results["entity_types_used"].add(a_type)
        results["entity_types_used"].add(b_type)

        # 统计实体类型组合
        type_pair = f"{a_type}->{b_type}"
        results["entity_type_combinations"][relation][type_pair] += 1

        # 统计实体出现次数
        results["entity_appearances"][a_id] += 1
        results["entity_appearances"][b_id] += 1

        # 统计无序实体对的关系重叠
        unordered_pair = tuple(sorted([a_id, b_id]))
        if item.get("is_negative", False):
            results["entity_pair_relations"][unordered_pair].add(f"negative_{relation}")
        else:
            results["entity_pair_relations"][unordered_pair].add(relation)

    return results


def print_separator(title=""):
    """打印分隔符"""
    print("\n" + "="*80)
    if title:
        print(f"  {title}")
        print("="*80)


def analyze_and_report():
    """执行分析并生成报告"""

    # 加载数据
    print("正在加载数据...")
    positive_data = load_jsonl(POSITIVE_PATH)
    negative_data = load_jsonl(NEGATIVE_PATH)

    print(f"正例数据: {len(positive_data)} 条")
    print(f"负例数据: {len(negative_data)} 条")

    # 分析分布
    pos_results = analyze_distribution(positive_data, is_positive=True)
    neg_results = analyze_distribution(negative_data, is_positive=False)

    # ========== 1. 关系类型数量分布 ==========
    print_separator("1. 关系类型数量分布与目标对比")

    print("\n【正例关系分布】")
    print(f"{'关系类型':<15} {'实际数量':<10} {'目标数量':<10} {'差异':<10} {'达成率'}")
    print("-"*70)

    positive_relations = ["directional", "metric", "contains", "within", "touches", "crosses", "disjoint", "C1", "C2", "C3", "C4"]
    for rel in positive_relations:
        actual = pos_results["relation_counts"].get(rel, 0)
        target = TARGET_DISTRIBUTION.get(rel, 0)
        diff = actual - target
        rate = f"{actual/target*100:.1f}%" if target > 0 else "N/A"
        print(f"{rel:<15} {actual:<10} {target:<10} {diff:+<10} {rate}")

    print("\n【负例关系分布】")
    print(f"{'关系类型':<20} {'实际数量':<10} {'目标数量':<10} {'差异':<10} {'达成率'}")
    print("-"*70)

    negative_relations = ["contains", "within", "touches", "crosses", "disjoint", "C2", "C3", "C4"]
    for rel in negative_relations:
        actual = neg_results["relation_counts"].get(f"negative_{rel}", 0)
        target = TARGET_DISTRIBUTION.get(f"negative_{rel}", 0)
        diff = actual - target
        rate = f"{actual/target*100:.1f}%" if target > 0 else "N/A"
        print(f"negative_{rel:<12} {actual:<10} {target:<10} {diff:+<10} {rate}")

    # ========== 2. 实体类型组合多样性 ==========
    print_separator("2. 每种关系类型内的实体类型组合")

    # 合并正负例的实体类型组合
    all_type_combinations = defaultdict(Counter)
    for rel, combos in pos_results["entity_type_combinations"].items():
        all_type_combinations[rel].update(combos)
    for rel, combos in neg_results["entity_type_combinations"].items():
        all_type_combinations[f"negative_{rel}"].update(combos)

    all_relations = sorted(all_type_combinations.keys())
    for rel in all_relations:
        combos = all_type_combinations[rel]
        print(f"\n【{rel}】 共 {len(combos)} 种组合:")
        for combo, count in sorted(combos.items(), key=lambda x: -x[1])[:15]:
            print(f"  {combo:<40} {count}")
        if len(combos) > 15:
            print(f"  ... (共{len(combos)}种组合)")

    # ========== 3. 实体类型使用情况 ==========
    print_separator("3. 12种实体类型使用情况")

    all_entity_types = pos_results["entity_types_used"] | neg_results["entity_types_used"]
    print(f"\n已使用的实体类型 ({len(all_entity_types)}/12):")
    for et in ENTITY_TYPES:
        status = "[OK]" if et in all_entity_types else "[--]"
        print(f"  {status} {et}")

    unused = [et for et in ENTITY_TYPES if et not in all_entity_types]
    if unused:
        print(f"\n未使用的实体类型: {', '.join(unused)}")

    # ========== 4. 实体覆盖率 ==========
    print_separator("4. 实体覆盖率分析")

    # 合并实体出现次数
    all_appearances = pos_results["entity_appearances"] + neg_results["entity_appearances"]
    all_entities = set(all_appearances.keys())
    coverage_rate = len(all_entities) / TOTAL_ENTITIES * 100

    print(f"\n总实体数: {TOTAL_ENTITIES}")
    print(f"出现的实体数: {len(all_entities)}")
    print(f"实体覆盖率: {coverage_rate:.2f}%")
    print(f"未出现的实体数: {TOTAL_ENTITIES - len(all_entities)}")

    # ========== 5. 高频实体TOP20 ==========
    print_separator("5. 高频实体TOP20")

    top20 = all_appearances.most_common(20)

    print(f"\n{'排名':<6} {'实体ID':<20} {'中文名称':<20} {'出现次数'}")
    print("-"*60)
    for i, (entity_id, count) in enumerate(top20, 1):
        name = pos_results["entity_names"].get(entity_id, neg_results["entity_names"].get(entity_id, entity_id))
        print(f"{i:<6} {entity_id:<20} {name:<20} {count}")

    # ========== 6. 实体出现频次分布 ==========
    print_separator("6. 实体出现频次分布")

    freq_ranges = [
        (1, 5, "1-5次"),
        (6, 10, "6-10次"),
        (11, 20, "11-20次"),
        (21, 30, "21-30次"),
        (31, float('inf'), "31次+")
    ]

    print(f"\n{'频次范围':<12} {'实体数量':<10} {'占比'}")
    print("-"*40)

    for min_freq, max_freq, label in freq_ranges:
        if max_freq == float('inf'):
            count = sum(1 for c in all_appearances.values() if c >= min_freq)
        else:
            count = sum(1 for c in all_appearances.values() if min_freq <= c <= max_freq)
        rate = count / len(all_appearances) * 100
        print(f"{label:<12} {count:<10} {rate:.1f}%")

    # ========== 7. 跨关系重叠分析 ==========
    print_separator("7. 跨关系重叠分析 (无序实体对)")

    # 合并正负例的实体对关系
    all_pair_relations = defaultdict(set)
    for pair, rels in pos_results["entity_pair_relations"].items():
        all_pair_relations[pair].update(rels)
    for pair, rels in neg_results["entity_pair_relations"].items():
        all_pair_relations[pair].update(rels)

    overlap_counts = Counter(len(rels) for rels in all_pair_relations.values())

    print(f"\n{'关系类型数':<12} {'实体对数量':<12} {'占比'}")
    print("-"*40)
    for num_rels in sorted(overlap_counts.keys()):
        count = overlap_counts[num_rels]
        rate = count / len(all_pair_relations) * 100
        label = f"{num_rels}种" if num_rels <= 3 else f"{num_rels}种+"
        print(f"{label:<12} {count:<12} {rate:.1f}%")

    # ========== 总结分析 ==========
    print_separator("分析结论")

    conclusions = []

    # 检查关系分布
    pos_rel_stats = []
    for rel in positive_relations:
        actual = pos_results["relation_counts"].get(rel, 0)
        target = TARGET_DISTRIBUTION.get(rel, 0)
        if target > 0:
            pos_rel_stats.append((rel, actual, target, actual/target))

    neg_rel_stats = []
    for rel in negative_relations:
        actual = neg_results["relation_counts"].get(f"negative_{rel}", 0)
        target = TARGET_DISTRIBUTION.get(f"negative_{rel}", 0)
        if target > 0:
            neg_rel_stats.append((rel, actual, target, actual/target))

    well_distributed_pos = sum(1 for _, _, _, rate in pos_rel_stats if 0.9 <= rate <= 1.1)
    well_distributed_neg = sum(1 for _, _, _, rate in neg_rel_stats if 0.9 <= rate <= 1.1)

    conclusions.append(f"1. 正例关系分布: {well_distributed_pos}/{len(positive_relations)}种关系达成率在90%-110%之间")
    conclusions.append(f"2. 负例关系分布: {well_distributed_neg}/{len(negative_relations)}种关系达成率在90%-110%之间")

    # 检查实体类型覆盖
    conclusions.append(f"3. 实体类型覆盖: {len(all_entity_types)}/12种实体类型被使用")

    # 检查实体覆盖率
    conclusions.append(f"4. 实体覆盖率: {coverage_rate:.1f}%的实体出现在训练数据中 ({len(all_entities)}/{TOTAL_ENTITIES})")

    # 检查实体对重叠
    single_type_pairs = overlap_counts.get(1, 0)
    conclusions.append(f"5. 实体对专一度: {single_type_pairs/len(all_pair_relations)*100:.1f}%的实体对只出现在一种关系类型中")

    for conclusion in conclusions:
        print(f"  {conclusion}")

    # 返回结果供发送消息使用
    return {
        "positive_total": len(positive_data),
        "negative_total": len(negative_data),
        "relation_distribution": dict(pos_results["relation_counts"]),
        "negative_relation_distribution": dict(neg_results["relation_counts"]),
        "entity_types_used": list(all_entity_types),
        "entity_coverage": {
            "covered": len(all_entities),
            "total": TOTAL_ENTITIES,
            "rate": coverage_rate
        },
        "top_entities": [(eid, pos_results["entity_names"].get(eid, neg_results["entity_names"].get(eid, eid)), cnt)
                        for eid, cnt in top20[:10]],
        "freq_distribution": {label: sum(1 for c in all_appearances.values() if
                                          (min_freq <= c <= max_freq if max_freq != float('inf') else c >= min_freq))
                             for min_freq, max_freq, label in freq_ranges},
        "overlap_analysis": dict(overlap_counts),
        "total_pairs": len(all_pair_relations),
        "type_combinations": {rel: dict(combos) for rel, combos in all_type_combinations.items()},
        "conclusions": conclusions
    }


if __name__ == "__main__":
    results = analyze_and_report()
