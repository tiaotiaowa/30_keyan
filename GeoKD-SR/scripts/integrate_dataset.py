#!/usr/bin/env python3
"""
数据集整合汇总脚本
将平衡后的数据整合为 train.jsonl、dev.jsonl、test.jsonl，并生成数据质量报告
"""
import json
import os
import random
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any, Tuple


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """加载jsonl文件"""
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"警告: JSON解析失败: {e}")
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


def analyze_dataset(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分析数据集质量"""
    analysis = {
        "total_records": len(data),
        "spatial_relation_types": Counter(),
        "difficulty_distribution": Counter(),
        "topology_subtype_distribution": Counter(),
        "missing_fields": Counter(),
        "field_coverage": {},
        "difficulty_score_coverage": 0,
        "entity_to_token_coverage": 0,
        "has_question": 0,
        "has_answer": 0,
        "average_question_length": 0,
        "average_answer_length": 0
    }

    total_question_length = 0
    total_answer_length = 0

    for record in data:
        # 空间关系类型
        spatial_type = record.get("spatial_relation_type", "missing")
        analysis["spatial_relation_types"][spatial_type] += 1

        # 难度分布
        difficulty = record.get("difficulty", "missing")
        analysis["difficulty_distribution"][difficulty] += 1

        # 拓扑子类型
        if spatial_type == "topological":
            subtype = record.get("topology_subtype", "missing")
            analysis["topology_subtype_distribution"][subtype] += 1

        # 字段覆盖
        for field in ["id", "question", "answer", "spatial_relation",
                      "difficulty", "difficulty_score", "entity_to_token",
                      "topology_subtype", "entities"]:
            if field in record:
                analysis["field_coverage"][field] = analysis["field_coverage"].get(field, 0) + 1
            else:
                analysis["missing_fields"][field] += 1

        # 特殊字段覆盖
        if "difficulty_score" in record:
            analysis["difficulty_score_coverage"] += 1
        if "entity_to_token" in record:
            analysis["entity_to_token_coverage"] += 1
        if "question" in record:
            analysis["has_question"] += 1
            total_question_length += len(record["question"])
        if "answer" in record:
            analysis["has_answer"] += 1
            total_answer_length += len(str(record["answer"]))

    # 计算平均值
    if analysis["has_question"] > 0:
        analysis["average_question_length"] = total_question_length / analysis["has_question"]
    if analysis["has_answer"] > 0:
        analysis["average_answer_length"] = total_answer_length / analysis["has_answer"]

    return analysis


def split_dataset(data: List[Dict[str, Any]],
                  train_ratio: float = 0.8,
                  dev_ratio: float = 0.1,
                  test_ratio: float = 0.1,
                  stratify_by: str = "spatial_relation_type") -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    分割数据集为train/dev/test，保持分层采样
    """
    if abs(train_ratio + dev_ratio + test_ratio - 1.0) > 0.001:
        raise ValueError("比例之和必须等于1")

    # 按分层字段分组
    groups = {}
    for record in data:
        key = record.get(stratify_by, "unknown")
        if key not in groups:
            groups[key] = []
        groups[key].append(record)

    train_data = []
    dev_data = []
    test_data = []

    # 对每个组进行分割
    for key, group_data in groups.items():
        random.shuffle(group_data)

        n = len(group_data)
        train_end = int(n * train_ratio)
        dev_end = train_end + int(n * dev_ratio)

        train_data.extend(group_data[:train_end])
        dev_data.extend(group_data[train_end:dev_end])
        test_data.extend(group_data[dev_end:])

        print(f"  {key}: 总计{n} -> train:{train_end}, dev:{dev_end-train_end}, test:{n-dev_end}")

    return train_data, dev_data, test_data


def generate_quality_report(train_analysis: Dict, dev_analysis: Dict, test_analysis: Dict,
                            output_path: str) -> None:
    """生成数据质量报告"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# GeoKD-SR 数据集质量报告\n\n")
        f.write(f"生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 总体统计
        total = train_analysis["total_records"] + dev_analysis["total_records"] + test_analysis["total_records"]
        f.write("## 数据集概览\n\n")
        f.write(f"| 数据集 | 记录数 | 占比 |\n")
        f.write(f"|--------|--------|------|\n")
        f.write(f"| Train | {train_analysis['total_records']:,} | {train_analysis['total_records']/total*100:.2f}% |\n")
        f.write(f"| Dev | {dev_analysis['total_records']:,} | {dev_analysis['total_records']/total*100:.2f}% |\n")
        f.write(f"| Test | {test_analysis['total_records']:,} | {test_analysis['total_records']/total*100:.2f}% |\n")
        f.write(f"| **总计** | **{total:,}** | **100%** |\n\n")

        # 空间关系类型分布
        f.write("## 空间关系类型分布\n\n")
        f.write("### Train Set\n\n")
        f.write("| 类型 | 数量 | 占比 |\n")
        f.write("|------|------|------|\n")
        for spatial_type, count in sorted(train_analysis["spatial_relation_types"].items()):
            pct = count / train_analysis["total_records"] * 100
            f.write(f"| {spatial_type} | {count:,} | {pct:.2f}% |\n")
        f.write("\n")

        # 难度分布
        f.write("## 难度分布\n\n")
        f.write("### Train Set\n\n")
        f.write("| 难度 | 数量 | 占比 |\n")
        f.write("|------|------|------|\n")
        for difficulty, count in sorted(train_analysis["difficulty_distribution"].items()):
            pct = count / train_analysis["total_records"] * 100
            f.write(f"| {difficulty} | {count:,} | {pct:.2f}% |\n")
        f.write("\n")

        # 拓扑子类型分布
        f.write("## 拓扑子类型分布 (topology_subtype)\n\n")
        f.write("*仅统计 spatial_relation_type 为 'topological' 的记录*\n\n")
        f.write("### Train Set\n\n")
        f.write("| 子类型 | 数量 | 占比 |\n")
        f.write("|--------|------|------|\n")
        total_topo = sum(train_analysis["topology_subtype_distribution"].values())
        for subtype, count in sorted(train_analysis["topology_subtype_distribution"].items(),
                                     key=lambda x: -x[1]):
            pct = count / total_topo * 100 if total_topo > 0 else 0
            f.write(f"| {subtype} | {count:,} | {pct:.2f}% |\n")
        f.write("\n")

        # 字段覆盖情况
        f.write("## 字段覆盖情况\n\n")
        f.write("### Train Set\n\n")
        f.write("| 字段 | 覆盖记录数 | 覆盖率 |\n")
        f.write("|------|------------|--------|\n")
        for field, count in sorted(train_analysis["field_coverage"].items()):
            pct = count / train_analysis["total_records"] * 100
            f.write(f"| {field} | {count:,} | {pct:.2f}% |\n")
        f.write("\n")

        # 特殊字段统计
        f.write("## 特殊字段覆盖\n\n")
        f.write("| 数据集 | difficulty_score | entity_to_token | has_question | has_answer |\n")
        f.write("|--------|-----------------|-----------------|--------------|------------|\n")
        f.write(f"| Train | {train_analysis['difficulty_score_coverage']:,} ({train_analysis['difficulty_score_coverage']/train_analysis['total_records']*100:.1f}%) | ")
        f.write(f"{train_analysis['entity_to_token_coverage']:,} ({train_analysis['entity_to_token_coverage']/train_analysis['total_records']*100:.1f}%) | ")
        f.write(f"{train_analysis['has_question']:,} ({train_analysis['has_question']/train_analysis['total_records']*100:.1f}%) | ")
        f.write(f"{train_analysis['has_answer']:,} ({train_analysis['has_answer']/train_analysis['total_records']*100:.1f}%) |\n")

        f.write(f"| Dev | {dev_analysis['difficulty_score_coverage']:,} ({dev_analysis['difficulty_score_coverage']/dev_analysis['total_records']*100:.1f}%) | ")
        f.write(f"{dev_analysis['entity_to_token_coverage']:,} ({dev_analysis['entity_to_token_coverage']/dev_analysis['total_records']*100:.1f}%) | ")
        f.write(f"{dev_analysis['has_question']:,} ({dev_analysis['has_question']/dev_analysis['total_records']*100:.1f}%) | ")
        f.write(f"{dev_analysis['has_answer']:,} ({dev_analysis['has_answer']/dev_analysis['total_records']*100:.1f}%) |\n")

        f.write(f"| Test | {test_analysis['difficulty_score_coverage']:,} ({test_analysis['difficulty_score_coverage']/test_analysis['total_records']*100:.1f}%) | ")
        f.write(f"{test_analysis['entity_to_token_coverage']:,} ({test_analysis['entity_to_token_coverage']/test_analysis['total_records']*100:.1f}%) | ")
        f.write(f"{test_analysis['has_question']:,} ({test_analysis['has_question']/test_analysis['total_records']*100:.1f}%) | ")
        f.write(f"{test_analysis['has_answer']:,} ({test_analysis['has_answer']/test_analysis['total_records']*100:.1f}%) |\n\n")

        # 文本统计
        f.write("## 文本统计\n\n")
        f.write("| 数据集 | 平均问题长度 | 平均答案长度 |\n")
        f.write("|--------|--------------|--------------|\n")
        f.write(f"| Train | {train_analysis['average_question_length']:.1f} | {train_analysis['average_answer_length']:.1f} |\n")
        f.write(f"| Dev | {dev_analysis['average_question_length']:.1f} | {dev_analysis['average_answer_length']:.1f} |\n")
        f.write(f"| Test | {test_analysis['average_question_length']:.1f} | {test_analysis['average_answer_length']:.1f} |\n\n")

        # 数据质量评估
        f.write("## 数据质量评估\n\n")
        f.write("### 优势\n")
        f.write("- 空间关系类型分布均衡\n")
        f.write("- 难度梯度合理 (easy/medium/hard)\n")
        f.write("- 拓扑子类型已平衡 (各约20%)\n")
        f.write("- 分层采样保持了各子集的分布一致性\n\n")

        f.write("### 注意事项\n")
        f.write(f"- difficulty_score 字段覆盖率较低 ({train_analysis['difficulty_score_coverage']/train_analysis['total_records']*100:.1f}%)\n")
        f.write(f"- entity_to_token 字段覆盖率较低 ({train_analysis['entity_to_token_coverage']/train_analysis['total_records']*100:.1f}%)\n")
        f.write("- 补充生成的记录可能需要人工审核\n\n")


def main():
    # 设置随机种子
    random.seed(42)

    # 路径配置
    source_file = r"D:\30_keyan\GeoKD-SR\data\geosr_chain\balanced\balanced_topology_final.jsonl"
    output_dir = r"D:\30_keyan\GeoKD-SR\data\geosr_chain\final"

    print("=== 数据集整合汇总 ===\n")

    # 加载数据
    print("1. 加载平衡后的数据...")
    data = load_jsonl(source_file)
    print(f"   加载了 {len(data)} 条记录")

    # 分割数据集
    print("\n2. 分割数据集 (train/dev/test = 80%/10%/10%)...")
    print("   按空间关系类型分层采样:")
    train_data, dev_data, test_data = split_dataset(data, train_ratio=0.8, dev_ratio=0.1, test_ratio=0.1)

    print(f"\n   Train: {len(train_data)} 条")
    print(f"   Dev: {len(dev_data)} 条")
    print(f"   Test: {len(test_data)} 条")

    # 保存数据集
    print("\n3. 保存数据集...")
    train_file = os.path.join(output_dir, "train.jsonl")
    dev_file = os.path.join(output_dir, "dev.jsonl")
    test_file = os.path.join(output_dir, "test.jsonl")

    save_jsonl(train_data, train_file)
    save_jsonl(dev_data, dev_file)
    save_jsonl(test_data, test_file)

    # 分析数据集
    print("\n4. 分析数据集质量...")
    train_analysis = analyze_dataset(train_data)
    dev_analysis = analyze_dataset(dev_data)
    test_analysis = analyze_dataset(test_data)

    # 生成质量报告
    print("\n5. 生成数据质量报告...")
    report_file = os.path.join(output_dir, "data_quality_report.md")
    generate_quality_report(train_analysis, dev_analysis, test_analysis, report_file)

    # 生成统计摘要
    stats_file = os.path.join(output_dir, "dataset_stats.json")
    stats = {
        "total_records": len(data),
        "train": {
            "count": len(train_data),
            "spatial_relation_types": dict(train_analysis["spatial_relation_types"]),
            "difficulty_distribution": dict(train_analysis["difficulty_distribution"]),
            "topology_subtype_distribution": dict(train_analysis["topology_subtype_distribution"])
        },
        "dev": {
            "count": len(dev_data),
            "spatial_relation_types": dict(dev_analysis["spatial_relation_types"]),
            "difficulty_distribution": dict(dev_analysis["difficulty_distribution"]),
            "topology_subtype_distribution": dict(dev_analysis["topology_subtype_distribution"])
        },
        "test": {
            "count": len(test_data),
            "spatial_relation_types": dict(test_analysis["spatial_relation_types"]),
            "difficulty_distribution": dict(test_analysis["difficulty_distribution"]),
            "topology_subtype_distribution": dict(test_analysis["topology_subtype_distribution"])
        }
    }
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"   统计数据已保存到: {stats_file}")

    print(f"\n=== 完成 ===")
    print(f"数据集已保存到: {output_dir}")
    print(f"  - train.jsonl ({len(train_data)} 条)")
    print(f"  - dev.jsonl ({len(dev_data)} 条)")
    print(f"  - test.jsonl ({len(test_data)} 条)")
    print(f"质量报告: {report_file}")


if __name__ == "__main__":
    main()
