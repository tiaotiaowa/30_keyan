#!/usr/bin/env python3
"""
补充 topology_supplement_prompts.json 提示词
从 prompts_config_full.json 提取缺失的 disjoint 类型
"""

import json
import random
from pathlib import Path
from collections import Counter

# 配置路径
BASE_DIR = Path(__file__).parent.parent
PROMPTS_CONFIG_FULL = BASE_DIR / "data" / "prompts" / "prompts_config_full.json"
TOPOLOGY_SUPPLEMENT_PROMPTS = BASE_DIR / "data" / "prompts" / "topology_supplement_prompts.json"

# 目标难度分布: easy:30%, medium:50%, hard:20%
DIFFICULTY_DISTRIBUTION = {
    "easy": 0.30,
    "medium": 0.50,
    "hard": 0.20
}

def load_json(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    """保存JSON文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def select_prompts_by_difficulty(prompts, target_count, difficulty_dist):
    """按难度分布选择提示词"""
    # 按难度分组
    by_difficulty = {"easy": [], "medium": [], "hard": []}
    for p in prompts:
        diff = p.get("difficulty", "medium")
        if diff in by_difficulty:
            by_difficulty[diff].append(p)

    # 计算每种难度需要的数量
    counts = {
        "easy": int(target_count * difficulty_dist["easy"]),
        "medium": int(target_count * difficulty_dist["medium"]),
        "hard": target_count - int(target_count * difficulty_dist["easy"]) - int(target_count * difficulty_dist["medium"])
    }

    # 随机选择
    random.seed(42)
    selected = []
    for diff, count in counts.items():
        available = by_difficulty[diff]
        if len(available) >= count:
            selected.extend(random.sample(available, count))
        else:
            selected.extend(available)
            print(f"警告: {diff}难度只有{len(available)}条，需要{count}条")

    return selected

def supplement_disjoint_prompts():
    """补充disjoint类型提示词"""
    print("=" * 60)
    print("Step 1: 加载现有提示词文件")
    print("=" * 60)

    # 加载prompts_config_full.json
    config_full = load_json(PROMPTS_CONFIG_FULL)
    all_prompts = config_full.get("prompts", [])
    print(f"prompts_config_full.json 总提示词数: {len(all_prompts)}")

    # 加载现有topology_supplement_prompts.json
    supplement_data = load_json(TOPOLOGY_SUPPLEMENT_PROMPTS)
    existing_prompts = supplement_data.get("prompts", [])
    print(f"topology_supplement_prompts.json 现有提示词数: {len(existing_prompts)}")

    # 统计现有分布
    existing_by_subtype = Counter(p.get("topology_subtype") for p in existing_prompts)
    print(f"现有子类型分布: {dict(existing_by_subtype)}")

    print("\n" + "=" * 60)
    print("Step 2: 筛选topological类型提示词")
    print("=" * 60)

    # 筛选topological类型
    topological_prompts = [p for p in all_prompts if p.get("relation_type") == "topological"]
    print(f"topological类型总数: {len(topological_prompts)}")

    # 按子类型分组
    by_subtype = {}
    for p in topological_prompts:
        subtype = p.get("topology_subtype")
        if subtype not in by_subtype:
            by_subtype[subtype] = []
        by_subtype[subtype].append(p)

    for subtype, prompts in sorted(by_subtype.items()):
        print(f"  {subtype}: {len(prompts)}条")

    print("\n" + "=" * 60)
    print("Step 3: 补充disjoint类型提示词 (目标50条)")
    print("=" * 60)

    # 获取现有实体对（避免重复）
    existing_entity_pairs = set()
    for p in existing_prompts:
        e1 = p.get("entity1", {}).get("name", "")
        e2 = p.get("entity2", {}).get("name", "")
        existing_entity_pairs.add((e1, e2))

    # 筛选disjoint类型（排除已有实体对）
    disjoint_prompts = by_subtype.get("disjoint", [])
    new_disjoint = []
    for p in disjoint_prompts:
        e1 = p.get("entity1", {}).get("name", "")
        e2 = p.get("entity2", {}).get("name", "")
        if (e1, e2) not in existing_entity_pairs and (e2, e1) not in existing_entity_pairs:
            new_disjoint.append(p)

    print(f"可用disjoint提示词（排除重复后）: {len(new_disjoint)}")

    # 按难度分布选择50条
    selected_disjoint = select_prompts_by_difficulty(new_disjoint, 50, DIFFICULTY_DISTRIBUTION)
    print(f"选择disjoint提示词: {len(selected_disjoint)}条")

    # 统计选中提示词的难度分布
    selected_diff = Counter(p.get("difficulty") for p in selected_disjoint)
    print(f"选中难度分布: {dict(selected_diff)}")

    print("\n" + "=" * 60)
    print("Step 4: 补充contains和overlap差额")
    print("=" * 60)

    # 需要补充的数量
    needs = {
        "disjoint": 50 - existing_by_subtype.get("disjoint", 0),
        "contains": max(0, 384 - existing_by_subtype.get("contains", 0)),
        "overlap": max(0, 521 - existing_by_subtype.get("overlap", 0))
    }

    # 补充contains
    if needs["contains"] > 0:
        contains_prompts = by_subtype.get("contains", [])
        new_contains = [p for p in contains_prompts
                       if (p.get("entity1", {}).get("name"), p.get("entity2", {}).get("name"))
                       not in existing_entity_pairs]
        selected_contains = select_prompts_by_difficulty(new_contains, needs["contains"], DIFFICULTY_DISTRIBUTION)
        print(f"补充contains: {len(selected_contains)}条")
        selected_disjoint.extend(selected_contains)

    # 补充overlap
    if needs["overlap"] > 0:
        overlap_prompts = by_subtype.get("overlap", [])
        new_overlap = [p for p in overlap_prompts
                      if (p.get("entity1", {}).get("name"), p.get("entity2", {}).get("name"))
                      not in existing_entity_pairs]
        selected_overlap = select_prompts_by_difficulty(new_overlap, needs["overlap"], DIFFICULTY_DISTRIBUTION)
        print(f"补充overlap: {len(selected_overlap)}条")
        selected_disjoint.extend(selected_overlap)

    print("\n" + "=" * 60)
    print("Step 5: 更新topology_supplement_prompts.json")
    print("=" * 60)

    # 添加新提示词
    new_ids = set(p.get("id") for p in existing_prompts)
    added_count = 0
    for p in selected_disjoint:
        if p.get("id") not in new_ids:
            # 确保提示词格式正确
            formatted_prompt = {
                "id": p.get("id"),
                "split": p.get("split", "train"),
                "relation_type": "topological",
                "difficulty": p.get("difficulty", "medium"),
                "topology_subtype": p.get("topology_subtype"),
                "entity1": p.get("entity1", {}),
                "entity2": p.get("entity2", {}),
                "prompt_text": p.get("prompt_text", ""),
                "expected_direction": p.get("expected_direction"),
                "expected_distance": p.get("expected_distance")
            }
            existing_prompts.append(formatted_prompt)
            added_count += 1

    # 更新元数据
    final_by_subtype = Counter(p.get("topology_subtype") for p in existing_prompts)
    supplement_data["metadata"]["total_count"] = len(existing_prompts)
    supplement_data["metadata"]["target_distribution"] = dict(final_by_subtype)
    supplement_data["metadata"]["disjoint_added"] = added_count
    supplement_data["prompts"] = existing_prompts

    # 保存
    save_json(TOPOLOGY_SUPPLEMENT_PROMPTS, supplement_data)
    print(f"添加新提示词: {added_count}条")
    print(f"更新后总数: {len(existing_prompts)}条")
    print(f"更新后子类型分布: {dict(final_by_subtype)}")

    print("\n" + "=" * 60)
    print("提示词补充完成!")
    print("=" * 60)

    return supplement_data

if __name__ == "__main__":
    supplement_disjoint_prompts()
