#!/usr/bin/env python3
"""
分析 hibiki works 目录中的生成数据
"""
import json
import os
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Any


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


def analyze_files(directory: str) -> Dict[str, Any]:
    """分析所有jsonl文件"""
    base_path = Path(directory)
    jsonl_files = sorted(base_path.glob("*.jsonl"))

    if not jsonl_files:
        print(f"在 {directory} 中未找到jsonl文件")
        return {}

    # 统计数据
    total_records = 0
    file_stats = {}

    # 空间关系类型分布
    spatial_relation_types = Counter()

    # 难度分布
    difficulty_distribution = Counter()

    # 拓扑子类型分布
    topology_subtype_distribution = Counter()

    # 字段检查
    files_with_difficulty_score = []
    files_without_difficulty_score = []
    files_with_entity_to_token = []
    files_without_entity_to_token = []

    # 按文件统计
    for jsonl_file in jsonl_files:
        file_name = jsonl_file.name
        print(f"分析文件: {file_name}")

        data = load_jsonl(str(jsonl_file))
        record_count = len(data)
        total_records += record_count

        # 检查字段是否存在
        has_difficulty_score = False
        has_entity_to_token = False

        # 记录级统计
        file_spatial_types = Counter()
        file_difficulty = Counter()
        file_topology_subtype = Counter()

        for record in data:
            # 统计空间关系类型
            spatial_type = record.get("spatial_relation_type", "unknown")
            file_spatial_types[spatial_type] += 1
            spatial_relation_types[spatial_type] += 1

            # 统计难度
            difficulty = record.get("difficulty", "unknown")
            file_difficulty[difficulty] += 1
            difficulty_distribution[difficulty] += 1

            # 统计拓扑子类型（仅当类型为topological时）
            if spatial_type == "topological":
                topology_subtype = record.get("topology_subtype", "unknown")
                file_topology_subtype[topology_subtype] += 1
                topology_subtype_distribution[topology_subtype] += 1

            # 检查字段
            if "difficulty_score" in record:
                has_difficulty_score = True
            if "entity_to_token" in record:
                has_entity_to_token = True

        # 记录字段检查结果
        if has_difficulty_score:
            files_with_difficulty_score.append(file_name)
        else:
            files_without_difficulty_score.append(file_name)

        if has_entity_to_token:
            files_with_entity_to_token.append(file_name)
        else:
            files_without_entity_to_token.append(file_name)

        # 文件统计
        file_stats[file_name] = {
            "record_count": record_count,
            "spatial_relation_types": dict(file_spatial_types),
            "difficulty_distribution": dict(file_difficulty),
            "topology_subtype_distribution": dict(file_topology_subtype),
            "has_difficulty_score": has_difficulty_score,
            "has_entity_to_token": has_entity_to_token
        }

        print(f"  记录数: {record_count}")
        print(f"  空间关系类型: {dict(file_spatial_types)}")
        print(f"  难度分布: {dict(file_difficulty)}")
        print(f"  包含difficulty_score: {has_difficulty_score}")
        print(f"  包含entity_to_token: {has_entity_to_token}")

    return {
        "total_files": len(jsonl_files),
        "total_records": total_records,
        "file_stats": file_stats,
        "spatial_relation_types": dict(spatial_relation_types),
        "difficulty_distribution": dict(difficulty_distribution),
        "topology_subtype_distribution": dict(topology_subtype_distribution),
        "files_with_difficulty_score": files_with_difficulty_score,
        "files_without_difficulty_score": files_without_difficulty_score,
        "files_with_entity_to_token": files_with_entity_to_token,
        "files_without_entity_to_token": files_without_entity_to_token
    }


def generate_markdown_report(analysis: Dict[str, Any], output_path: str) -> None:
    """生成markdown报告"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Hibiki Works 数据分析报告\n\n")
        f.write(f"生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 总体统计
        f.write("## 总体统计\n\n")
        f.write(f"- **文件总数**: {analysis['total_files']}\n")
        f.write(f"- **记录总数**: {analysis['total_records']:,}\n\n")

        # 空间关系类型分布
        f.write("## 空间关系类型分布\n\n")
        f.write("| 类型 | 数量 | 占比 |\n")
        f.write("|------|------|------|\n")
        total = sum(analysis['spatial_relation_types'].values())
        for spatial_type, count in sorted(analysis['spatial_relation_types'].items(), key=lambda x: -x[1]):
            percentage = (count / total * 100) if total > 0 else 0
            f.write(f"| {spatial_type} | {count:,} | {percentage:.2f}% |\n")
        f.write("\n")

        # 难度分布
        f.write("## 难度分布\n\n")
        f.write("| 难度 | 数量 | 占比 |\n")
        f.write("|------|------|------|\n")
        total_diff = sum(analysis['difficulty_distribution'].values())
        for difficulty, count in sorted(analysis['difficulty_distribution'].items(), key=lambda x: -x[1]):
            percentage = (count / total_diff * 100) if total_diff > 0 else 0
            f.write(f"| {difficulty} | {count:,} | {percentage:.2f}% |\n")
        f.write("\n")

        # 拓扑子类型分布
        f.write("## 拓扑子类型分布 (topology_subtype)\n\n")
        f.write("*仅统计 spatial_relation_type 为 'topological' 的记录*\n\n")
        f.write("| 子类型 | 数量 | 占比 |\n")
        f.write("|--------|------|------|\n")
        total_topo = sum(analysis['topology_subtype_distribution'].values())
        for subtype, count in sorted(analysis['topology_subtype_distribution'].items(), key=lambda x: -x[1]):
            percentage = (count / total_topo * 100) if total_topo > 0 else 0
            f.write(f"| {subtype} | {count:,} | {percentage:.2f}% |\n")
        f.write("\n")

        # 字段检查
        f.write("## 字段检查\n\n")
        f.write("### difficulty_score 字段\n\n")
        f.write(f"- **包含该字段的文件** ({len(analysis['files_with_difficulty_score'])}个):\n")
        for file_name in analysis['files_with_difficulty_score']:
            f.write(f"  - {file_name}\n")
        f.write(f"\n- **不包含该字段的文件** ({len(analysis['files_without_difficulty_score'])}个):\n")
        for file_name in analysis['files_without_difficulty_score']:
            f.write(f"  - {file_name}\n")
        f.write("\n")

        f.write("### entity_to_token 字段\n\n")
        f.write(f"- **包含该字段的文件** ({len(analysis['files_with_entity_to_token'])}个):\n")
        for file_name in analysis['files_with_entity_to_token']:
            f.write(f"  - {file_name}\n")
        f.write(f"\n- **不包含该字段的文件** ({len(analysis['files_without_entity_to_token'])}个):\n")
        for file_name in analysis['files_without_entity_to_token']:
            f.write(f"  - {file_name}\n")
        f.write("\n")

        # 各文件详细统计
        f.write("## 各文件详细统计\n\n")
        for file_name, stats in sorted(analysis['file_stats'].items()):
            f.write(f"### {file_name}\n\n")
            f.write(f"- **记录数**: {stats['record_count']:,}\n")
            f.write(f"- **包含difficulty_score**: {stats['has_difficulty_score']}\n")
            f.write(f"- **包含entity_to_token**: {stats['has_entity_to_token']}\n\n")

            f.write("**空间关系类型分布**:\n\n")
            f.write("| 类型 | 数量 |\n")
            f.write("|------|------|\n")
            for spatial_type, count in sorted(stats['spatial_relation_types'].items(), key=lambda x: -x[1]):
                f.write(f"| {spatial_type} | {count:,} |\n")
            f.write("\n")

            f.write("**难度分布**:\n\n")
            f.write("| 难度 | 数量 |\n")
            f.write("|------|------|\n")
            for difficulty, count in sorted(stats['difficulty_distribution'].items()):
                f.write(f"| {difficulty} | {count:,} |\n")
            f.write("\n")

            if stats['topology_subtype_distribution']:
                f.write("**拓扑子类型分布**:\n\n")
                f.write("| 子类型 | 数量 |\n")
                f.write("|--------|------|\n")
                for subtype, count in sorted(stats['topology_subtype_distribution'].items(), key=lambda x: -x[1]):
                    f.write(f"| {subtype} | {count:,} |\n")
                f.write("\n")


def main():
    directory = r"c:\Users\60207\Documents\hibiki works"
    output_path = r"D:\30_keyan\GeoKD-SR\outputs\data_analysis_report.md"

    print("开始分析数据...")
    analysis = analyze_files(directory)

    if analysis:
        print("\n生成报告...")
        generate_markdown_report(analysis, output_path)
        print(f"报告已保存到: {output_path}")

        # 打印关键统计
        print("\n=== 关键统计 ===")
        print(f"文件总数: {analysis['total_files']}")
        print(f"记录总数: {analysis['total_records']:,}")
        print(f"\n空间关系类型分布: {analysis['spatial_relation_types']}")
        print(f"难度分布: {analysis['difficulty_distribution']}")
        print(f"拓扑子类型分布: {analysis['topology_subtype_distribution']}")


if __name__ == "__main__":
    main()
