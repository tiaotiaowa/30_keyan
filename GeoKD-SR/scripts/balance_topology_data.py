#!/usr/bin/env python3
"""
拓扑子类型分布改善脚本
目标：过滤contains类型数据至377条，生成补充数据使拓扑子类型分布均匀(各20%)
"""
import json
import os
import random
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any
import copy


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """加载jsonl文件"""
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"警告: {file_path} 第{line_num}行JSON解析失败: {e}")
        return data
    except Exception as e:
        print(f"错误: 无法读取文件 {file_path}: {e}")
        return []


def save_jsonl(data: List[Dict[str, Any]], file_path: str) -> None:
    """保存为jsonl文件"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        for record in data:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    print(f"已保存 {len(data)} 条记录到 {file_path}")


def count_topology_by_subtype(data: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计topological类型的子类型分布"""
    counter = Counter()
    for record in data:
        if record.get("spatial_relation_type") == "topological":
            subtype = record.get("topology_subtype", "unknown")
            counter[subtype] += 1
    return dict(counter)


def filter_contains_to_target(data: List[Dict[str, Any]], target_count: int = 377) -> List[Dict[str, Any]]:
    """
    过滤contains类型数据至目标数量
    保留策略：随机采样但尽量保持难度分布
    """
    contains_records = [r for r in data if r.get("spatial_relation_type") == "topological" and r.get("topology_subtype") == "contains"]

    if len(contains_records) <= target_count:
        print(f"contains记录数({len(contains_records)})已小于等于目标值({target_count})，无需过滤")
        return data

    # 按难度分层采样
    easy_records = [r for r in contains_records if r.get("difficulty") == "easy"]
    medium_records = [r for r in contains_records if r.get("difficulty") == "medium"]
    hard_records = [r for r in contains_records if r.get("difficulty") == "hard"]

    # 计算各难度应保留的数量（保持原有比例）
    total = len(contains_records)
    easy_target = int(len(easy_records) / total * target_count)
    medium_target = int(len(medium_records) / total * target_count)
    hard_target = target_count - easy_target - medium_target  # 剩余分配给hard

    sampled = random.sample(easy_records, min(easy_target, len(easy_records))) if easy_target > 0 else []
    sampled += random.sample(medium_records, min(medium_target, len(medium_records))) if medium_target > 0 else []
    sampled += random.sample(hard_records, min(hard_target, len(hard_records))) if hard_target > 0 else []

    # 如果还有缺口，从任意难度补充
    while len(sampled) < target_count:
        remaining = [r for r in contains_records if r not in sampled]
        if remaining:
            sampled.append(random.choice(remaining))
        else:
            break

    sampled_ids = {id(r) for r in sampled}

    # 构建过滤后的数据集
    filtered_data = []
    removed_count = 0
    for record in data:
        if record.get("spatial_relation_type") == "topological" and record.get("topology_subtype") == "contains":
            if id(record) in sampled_ids:
                filtered_data.append(record)
            else:
                removed_count += 1
        else:
            filtered_data.append(record)

    print(f"过滤contains: 移除 {removed_count} 条，保留 {len(sampled)} 条")
    return filtered_data


def generate_supplementary_data(current_data: List[Dict[str, Any]], target_per_type: int) -> List[Dict[str, Any]]:
    """
    生成补充数据使拓扑子类型分布均匀
    目标: within, adjacent, disjoint, overlap 各占20%
    """
    # 统计当前分布
    topology_records = [r for r in current_data if r.get("spatial_relation_type") == "topological"]
    current_counts = count_topology_by_subtype(current_data)

    # 目标子类型
    target_subtypes = ["within", "adjacent", "disjoint", "overlap"]
    total_topological = sum(current_counts.get(s, 0) for s in target_subtypes)

    # 计算每个子类型的目标数量
    target_count_per_type = int(total_topological * 0.25)  # 25%每个类型

    print(f"\n当前拓扑子类型分布:")
    for subtype in target_subtypes:
        current = current_counts.get(subtype, 0)
        print(f"  {subtype}: {current} (目标: {target_count_per_type})")

    supplementary = []

    for target_subtype in target_subtypes:
        current = current_counts.get(target_subtype, 0)
        needed = target_count_per_type - current

        if needed > 0:
            print(f"\n需要生成 {needed} 条 {target_subtype} 类型的补充数据")

            # 从现有topological记录中随机选择作为模板
            templates = random.choices(topology_records, k=min(needed * 2, len(topology_records)))

            for i in range(needed):
                template = templates[i % len(templates)]
                new_record = generate_modified_record(template, target_subtype)
                supplementary.append(new_record)

    return supplementary


def generate_modified_record(template: Dict[str, Any], new_subtype: str) -> Dict[str, Any]:
    """
    基于模板生成修改后的记录
    修改topology_subtype并调整相关字段
    """
    new_record = copy.deepcopy(template)

    # 更新子类型
    new_record["topology_subtype"] = new_subtype

    # 更新ID（确保唯一性）
    if "id" in new_record:
        original_id = new_record["id"]
        new_record["id"] = f"{original_id}_gen_{new_subtype}_{random.randint(10000, 99999)}"

    # 更新spatial_relation以反映新的拓扑关系
    if "spatial_relation" in new_record:
        new_record["spatial_relation"] = modify_relation_description(new_record["spatial_relation"], new_subtype)

    # 更新question以反映新的拓扑关系
    if "question" in new_record:
        new_record["question"] = modify_question(new_record["question"], new_subtype)

    # 清除可能不适用的字段
    if "difficulty_score" in new_record:
        del new_record["difficulty_score"]

    return new_record


def modify_relation_description(relation: str, new_subtype: str) -> str:
    """修改空间关系描述以匹配新的拓扑子类型"""
    subtype_keywords = {
        "within": ["在...内部", "被包含", "within", "inside"],
        "adjacent": ["相邻", "接壤", "adjacent", "next to", "beside"],
        "disjoint": ["不相交", "分离", "disjoint", "separate"],
        "overlap": ["重叠", "相交", "overlap", "intersect"]
    }

    # 简单替换策略
    # 移除已知的关系描述词
    result = relation
    for subtype, keywords in subtype_keywords.items():
        if subtype != new_subtype:
            for keyword in keywords:
                result = result.replace(keyword, "")

    # 添加新的关系描述
    new_keywords = subtype_keywords[new_subtype]
    new_keyword = new_keywords[0]  # 使用第一个关键词

    # 在合适的位置插入新关键词
    if result.startswith(("A", "The", "这个", "那")):
        result = result.replace("是", f"与新实体{new_keyword}", 1)
    else:
        result = f"{new_keyword}" + result

    return result


def modify_question(question: str, new_subtype: str) -> str:
    """修改问题以反映新的拓扑关系"""
    subtype_questions = {
        "within": "在什么内部？",
        "adjacent": "与什么相邻？",
        "disjoint": "与什么不相交？",
        "overlap": "与什么重叠？"
    }

    # 保持问题结构，但修改关键部分
    if "什么" in question or "which" in question.lower() or "what" in question.lower():
        return subtype_questions.get(new_subtype, question)

    return question


def main():
    # 设置随机种子以确保可复现性
    random.seed(42)

    # 数据目录
    source_dir = r"c:\Users\60207\Documents\hibiki works"
    output_dir = r"D:\30_keyan\GeoKD-SR\data\geosr_chain\balanced"
    os.makedirs(output_dir, exist_ok=True)

    # 收集所有jsonl文件
    source_files = sorted(Path(source_dir).glob("*.jsonl"))

    all_data = []
    for file_path in source_files:
        print(f"加载文件: {file_path.name}")
        data = load_jsonl(str(file_path))
        all_data.extend(data)
        print(f"  加载了 {len(data)} 条记录")

    print(f"\n总共加载了 {len(all_data)} 条记录")

    # 步骤1: 过滤contains类型至377条
    print("\n=== 步骤1: 过滤contains类型 ===")
    current_counts = count_topology_by_subtype(all_data)
    print(f"过滤前contains数量: {current_counts.get('contains', 0)}")

    filtered_data = filter_contains_to_target(all_data, target_count=377)

    after_counts = count_topology_by_subtype(filtered_data)
    print(f"过滤后contains数量: {after_counts.get('contains', 0)}")

    # 步骤2: 生成补充数据
    print("\n=== 步骤2: 生成补充数据 ===")
    supplementary = generate_supplementary_data(filtered_data, target_per_type=None)

    # 合并数据
    balanced_data = filtered_data + supplementary
    print(f"\n最终数据集大小: {len(balanced_data)}")

    # 最终统计
    final_counts = count_topology_by_subtype(balanced_data)
    print("\n=== 最终拓扑子类型分布 ===")
    total_topo = sum(final_counts.values())
    for subtype, count in sorted(final_counts.items(), key=lambda x: -x[1]):
        percentage = (count / total_topo * 100) if total_topo > 0 else 0
        print(f"  {subtype}: {count} ({percentage:.2f}%)")

    # 保存结果
    output_file = os.path.join(output_dir, "balanced_topology_7000.jsonl")
    save_jsonl(balanced_data, output_file)

    # 保存补充数据
    if supplementary:
        sup_file = os.path.join(output_dir, "supplementary_records.jsonl")
        save_jsonl(supplementary, sup_file)

    # 生成统计报告
    report_file = os.path.join(output_dir, "balance_report.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("拓扑子类型分布平衡报告\n")
        f.write("=" * 50 + "\n\n")

        f.write("原始统计:\n")
        for subtype, count in sorted(current_counts.items(), key=lambda x: -x[1]):
            f.write(f"  {subtype}: {count}\n")

        f.write("\n过滤后统计 (contains -> 377):\n")
        for subtype, count in sorted(after_counts.items(), key=lambda x: -x[1]):
            f.write(f"  {subtype}: {count}\n")

        f.write("\n最终统计:\n")
        for subtype, count in sorted(final_counts.items(), key=lambda x: -x[1]):
            percentage = (count / total_topo * 100) if total_topo > 0 else 0
            f.write(f"  {subtype}: {count} ({percentage:.2f}%)\n")

        f.write(f"\n总记录数: {len(balanced_data)}\n")
        f.write(f"补充记录数: {len(supplementary)}\n")

    print(f"\n报告已保存到: {report_file}")


if __name__ == "__main__":
    main()
