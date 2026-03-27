#!/usr/bin/env python3
"""
将 topology_supplement_prompts.json 三等份划分
用于3个并行Agent执行

划分方案:
- Agent-1: overlap(521) + disjoint(48) + adjacent(66) = 635
- Agent-2: within(512) + contains(123) = 635
- Agent-3: contains(260) + adjacent(374) = 634
"""

import json
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent
PROMPTS_FILE = BASE_DIR / "data" / "prompts" / "topology_supplement_prompts.json"
OUTPUT_DIR = BASE_DIR / "data" / "prompts" / "agent_splits"


def load_prompts():
    """加载提示词"""
    with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('prompts', [])


def group_by_subtype_and_difficulty(prompts):
    """按子类型和难度分组"""
    groups = defaultdict(lambda: {'easy': [], 'medium': [], 'hard': []})
    for p in prompts:
        subtype = p.get('topology_subtype')
        diff = p.get('difficulty', 'medium')
        if subtype and diff in ['easy', 'medium', 'hard']:
            groups[subtype][diff].append(p)
    return groups


def split_prompts_three_ways():
    """三等份划分提示词"""
    print("=" * 60)
    print("开始划分提示词")
    print("=" * 60)

    # 加载提示词
    prompts = load_prompts()
    print(f"总提示词数: {len(prompts)}")

    # 按子类型和难度分组
    groups = group_by_subtype_and_difficulty(prompts)

    # 打印分布
    print("\n当前分布:")
    for subtype in ['overlap', 'within', 'adjacent', 'contains', 'disjoint']:
        g = groups[subtype]
        total = len(g['easy']) + len(g['medium']) + len(g['hard'])
        print(f"  {subtype}: easy={len(g['easy'])}, medium={len(g['medium'])}, hard={len(g['hard'])}, total={total}")

    # Agent-1: overlap(521) + disjoint(48) + adjacent(66) = 635
    agent1_prompts = []
    # overlap 全部
    agent1_prompts.extend(groups['overlap']['easy'] + groups['overlap']['medium'] + groups['overlap']['hard'])
    # disjoint 全部
    agent1_prompts.extend(groups['disjoint']['easy'] + groups['disjoint']['medium'] + groups['disjoint']['hard'])
    # adjacent 部分 (66: 22 easy + 34 medium + 10 hard)
    agent1_prompts.extend(groups['adjacent']['easy'][:22])
    agent1_prompts.extend(groups['adjacent']['medium'][:34])
    agent1_prompts.extend(groups['adjacent']['hard'][:10])

    # Agent-2: within(512) + contains(123) = 635
    agent2_prompts = []
    # within 全部
    agent2_prompts.extend(groups['within']['easy'] + groups['within']['medium'] + groups['within']['hard'])
    # contains 部分 (123: 40 easy + 62 medium + 21 hard)
    agent2_prompts.extend(groups['contains']['easy'][:40])
    agent2_prompts.extend(groups['contains']['medium'][:62])
    agent2_prompts.extend(groups['contains']['hard'][:21])

    # Agent-3: contains剩余(260) + adjacent剩余(374) = 634
    agent3_prompts = []
    # contains 剩余
    agent3_prompts.extend(groups['contains']['easy'][40:])
    agent3_prompts.extend(groups['contains']['medium'][62:])
    agent3_prompts.extend(groups['contains']['hard'][21:])
    # adjacent 剩余
    agent3_prompts.extend(groups['adjacent']['easy'][22:])
    agent3_prompts.extend(groups['adjacent']['medium'][34:])
    agent3_prompts.extend(groups['adjacent']['hard'][10:])

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 保存划分后的文件
    agents_data = [
        ("agent1", agent1_prompts, "overlap(521) + disjoint(48) + adjacent(66)"),
        ("agent2", agent2_prompts, "within(512) + contains(123)"),
        ("agent3", agent3_prompts, "contains(260) + adjacent(374)")
    ]

    print("\n划分结果:")
    for agent_name, agent_prompts, desc in agents_data:
        # 统计分布
        subtype_counts = defaultdict(int)
        diff_counts = defaultdict(int)
        for p in agent_prompts:
            subtype_counts[p.get('topology_subtype')] += 1
            diff_counts[p.get('difficulty')] += 1

        output_data = {
            "metadata": {
                "agent": agent_name,
                "total_count": len(agent_prompts),
                "description": desc,
                "subtype_distribution": dict(subtype_counts),
                "difficulty_distribution": dict(diff_counts),
                "source": "topology_supplement_prompts.json"
            },
            "prompts": agent_prompts
        }

        output_path = OUTPUT_DIR / f"{agent_name}_prompts.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n  {agent_name}: {len(agent_prompts)} 条")
        print(f"    子类型: {dict(subtype_counts)}")
        print(f"    难度: easy={diff_counts['easy']}, medium={diff_counts['medium']}, hard={diff_counts['hard']}")
        print(f"    保存到: {output_path}")

    print("\n" + "=" * 60)
    print("划分完成!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    split_prompts_three_ways()
