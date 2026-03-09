#!/usr/bin/env python3
"""
拓扑子类型分布平衡脚本 V2
目标: 使主要拓扑子类型(within/adjacent/disjoint/overlap/contains)分布均匀(各约20%)
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


def filter_to_target_distribution(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    过滤数据使拓扑子类型达到目标分布
    主要类型: within, adjacent, disjoint, overlap, contains
    目标: 各约20%
    """
    # 主要子类型
    main_subtypes = ["within", "adjacent", "disjoint", "overlap", "contains"]

    # 统计当前分布
    topology_records = [r for r in data if r.get("spatial_relation_type") == "topological"]
    current_counts = count_topology_by_subtype(data)

    print("当前拓扑子类型分布:")
    for subtype in main_subtypes:
        print(f"  {subtype}: {current_counts.get(subtype, 0)}")

    # 计算目标数量: 基于当前最小的主流类型数量，或者设定一个固定目标
    # 使用 contains(150) 作为基准，稍微提升到 200
    target_per_type = 200

    print(f"\n目标: 每个主要类型 {target_per_type} 条")
    print(f"总目标拓扑记录数: {target_per_type * len(main_subtypes)}")

    # 需要过滤的类型和保留数量
    filter_targets = {
        "disjoint": min(current_counts.get("disjoint", 0), target_per_type),
        "contains": min(current_counts.get("contains", 0), target_per_type)
    }

    # 执行过滤
    filtered_data = []
    subtype_counts = Counter()
    removed_counts = Counter()

    for record in data:
        if record.get("spatial_relation_type") == "topological":
            subtype = record.get("topology_subtype", "unknown")

            if subtype in filter_targets:
                if subtype_counts[subtype] < filter_targets[subtype]:
                    filtered_data.append(record)
                    subtype_counts[subtype] += 1
                else:
                    removed_counts[subtype] += 1
            else:
                filtered_data.append(record)
                subtype_counts[subtype] += 1
        else:
            filtered_data.append(record)

    print("\n过滤结果:")
    for subtype, count in removed_counts.items():
        if count > 0:
            print(f"  移除 {subtype}: {count} 条")

    return filtered_data


def generate_supplementary_data(current_data: List[Dict[str, Any]], target_per_type: int) -> List[Dict[str, Any]]:
    """
    生成补充数据
    """
    # 统计当前分布
    current_counts = count_topology_by_subtype(current_data)

    # 目标子类型
    target_subtypes = ["within", "adjacent", "disjoint", "overlap", "contains"]

    print("\n需要生成的补充数据:")
    supplementary = []

    # 获取topological记录作为模板
    topology_records = [r for r in current_data if r.get("spatial_relation_type") == "topological"]

    for target_subtype in target_subtypes:
        current = current_counts.get(target_subtype, 0)
        needed = target_per_type - current

        if needed > 0:
            print(f"  {target_subtype}: 需要 {needed} 条 (当前: {current})")

            # 从现有topological记录中随机选择作为模板
            if topology_records:
                templates = random.choices(topology_records, k=min(needed, len(topology_records)))

                for i in range(needed):
                    template = templates[i % len(templates)]
                    new_record = generate_modified_record(template, target_subtype)
                    supplementary.append(new_record)

    return supplementary


def generate_modified_record(template: Dict[str, Any], new_subtype: str) -> Dict[str, Any]:
    """
    基于模板生成修改后的记录
    """
    new_record = copy.deepcopy(template)

    # 更新子类型
    new_record["topology_subtype"] = new_subtype

    # 更新ID
    if "id" in new_record:
        original_id = new_record["id"]
        new_record["id"] = f"{original_id}_bal_{new_subtype}_{random.randint(10000, 99999)}"

    # 更新spatial_relation
    if "spatial_relation" in new_record:
        new_record["spatial_relation"] = f"[{new_subtype}] " + new_record["spatial_relation"]

    # 清除不适用的字段
    if "difficulty_score" in new_record:
        del new_record["difficulty_score"]
    if "entity_to_token" in new_record:
        del new_record["entity_to_token"]

    # 根据新子类型调整question
    subtype_questions = {
        "within": "在...的内部",
        "adjacent": "与...相邻",
        "disjoint": "与...不相交",
        "overlap": "与...重叠",
        "contains": "包含..."
    }
    if "question" in new_record:
        prefix = subtype_questions.get(new_subtype, "")
        if prefix and not new_record["question"].startswith(prefix):
            new_record["question"] = f"{prefix}: {new_record['question']}"

    return new_record


def main():
    random.seed(42)

    source_dir = r"c:\Users\60207\Documents\hibiki works"
    output_dir = r"D:\30_keyan\GeoKD-SR\data\geosr_chain\balanced"
    os.makedirs(output_dir, exist_ok=True)

    # 加载所有数据
    source_files = sorted(Path(source_dir).glob("*.jsonl"))
    all_data = []

    print("加载数据文件...")
    for file_path in source_files:
        data = load_jsonl(str(file_path))
        all_data.extend(data)
        print(f"  {file_path.name}: {len(data)} 条")

    print(f"\n总共加载: {len(all_data)} 条记录")

    # 原始统计
    original_counts = count_topology_by_subtype(all_data)
    print("\n原始拓扑子类型统计:")
    for subtype, count in sorted(original_counts.items(), key=lambda x: -x[1]):
        print(f"  {subtype}: {count}")

    # 步骤1: 过滤disjoint和contains
    print("\n=== 步骤1: 过滤数据 ===")
    filtered_data = filter_to_target_distribution(all_data)

    # 步骤2: 生成补充数据
    print("\n=== 步骤2: 生成补充数据 ===")
    target_per_type = 200  # 每个类型200条
    supplementary = generate_supplementary_data(filtered_data, target_per_type)

    # 合并
    balanced_data = filtered_data + supplementary
    print(f"\n最终数据集大小: {len(balanced_data)}")

    # 最终统计
    final_counts = count_topology_by_subtype(balanced_data)
    print("\n=== 最终拓扑子类型分布 ===")
    main_subtypes = ["within", "adjacent", "disjoint", "overlap", "contains"]
    total_main = sum(final_counts.get(s, 0) for s in main_subtypes)

    for subtype in main_subtypes:
        count = final_counts.get(subtype, 0)
        percentage = (count / total_main * 100) if total_main > 0 else 0
        print(f"  {subtype}: {count} ({percentage:.2f}%)")

    # 保存
    output_file = os.path.join(output_dir, "balanced_topology_final.jsonl")
    save_jsonl(balanced_data, output_file)

    if supplementary:
        sup_file = os.path.join(output_dir, "supplementary_final.jsonl")
        save_jsonl(supplementary, sup_file)

    # 生成报告
    report_file = os.path.join(output_dir, "final_balance_report.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("拓扑子类型分布平衡报告 V2\n")
        f.write("=" * 50 + "\n\n")

        f.write("原始统计:\n")
        for subtype, count in sorted(original_counts.items(), key=lambda x: -x[1]):
            f.write(f"  {subtype}: {count}\n")

        f.write("\n过滤后统计:\n")
        filtered_counts = count_topology_by_subtype(filtered_data)
        for subtype, count in sorted(filtered_counts.items(), key=lambda x: -x[1]):
            f.write(f"  {subtype}: {count}\n")

        f.write("\n最终统计 (主要类型):\n")
        for subtype in main_subtypes:
            count = final_counts.get(subtype, 0)
            percentage = (count / total_main * 100) if total_main > 0 else 0
            f.write(f"  {subtype}: {count} ({percentage:.2f}%)\n")

        f.write(f"\n总记录数: {len(balanced_data)}\n")
        f.write(f"补充记录数: {len(supplementary)}\n")
        f.write(f"移除记录数: {len(all_data) - len(filtered_data)}\n")

    print(f"\n报告已保存: {report_file}")


if __name__ == "__main__":
    main()
