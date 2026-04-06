# -*- coding: utf-8 -*-
"""
K2数据集探索脚本
分析GeoSignal和GeoBench的数据结构和内容
"""

import os
import sys
import json
from pathlib import Path
from collections import Counter

def explore_geosignal(data_path):
    """探索GeoSignal训练数据"""
    print("\n" + "=" * 60)
    print("GeoSignal 训练数据分析")
    print("=" * 60)

    try:
        from datasets import load_from_disk
        dataset = load_from_disk(data_path)
    except Exception as e:
        print(f"加载数据集失败: {e}")
        return None

    print(f"\n数据集大小: {len(dataset['train'])} 条")
    print(f"数据集列: {dataset['train'].column_names}")

    # 分析样本
    print("\n样本示例:")
    sample = dataset['train'][0]
    for key, value in sample.items():
        if isinstance(value, str) and len(value) > 100:
            print(f"  {key}: {value[:100]}...")
        else:
            print(f"  {key}: {value}")

    # 统计任务类型（如果有）
    if 'task' in dataset['train'].column_names:
        tasks = Counter(dataset['train']['task'])
        print("\n任务类型分布:")
        for task, count in tasks.most_common():
            print(f"  {task}: {count}")

    return dataset


def explore_geobench_json(json_path):
    """探索GeoBench JSON数据"""
    print(f"\n加载: {json_path}")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"加载失败: {e}")
        return None

    # 分析数据结构
    if isinstance(data, list):
        print(f"  数据类型: 列表")
        print(f"  样本数量: {len(data)}")

        if len(data) > 0:
            sample = data[0]
            print(f"  样本字段: {list(sample.keys())}")
            print("\n  样本示例:")
            for key, value in sample.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"    {key}: {value[:100]}...")
                else:
                    print(f"    {key}: {value}")

    elif isinstance(data, dict):
        print(f"  数据类型: 字典")
        print(f"  顶层键: {list(data.keys())}")

    return data


def main():
    script_dir = Path(__file__).resolve().parent

    # 1. 探索GeoSignal
    geosignal_path = script_dir / "geosignal"
    if geosignal_path.exists():
        geosignal = explore_geosignal(str(geosignal_path))
    else:
        print("GeoSignal数据未找到")
        geosignal = None

    # 2. 探索GeoBench
    print("\n" + "=" * 60)
    print("GeoBench 评测数据分析")
    print("=" * 60)

    # NPEE数据
    npee_json = script_dir / "geobench" / "geobenchmark_npee.json"
    if npee_json.exists():
        npee_data = explore_geobench_json(str(npee_json))
    else:
        print("NPEE数据未找到")

    # AP Study数据
    ap_json = script_dir / "geobench" / "geobenchmark_apstudy.json"
    if ap_json.exists():
        ap_data = explore_geobench_json(str(ap_json))
    else:
        print("AP Study数据未找到")

    # 3. 总结
    print("\n" + "=" * 60)
    print("数据集总结")
    print("=" * 60)

    if geosignal:
        print(f"\nGeoSignal (训练数据):")
        print(f"  样本数: {len(geosignal['train'])}")
        print(f"  用途: SFT指令微调训练")

    print(f"\nGeoBench (评测数据):")
    print(f"  NPEE: 研究生入学考试题目")
    print(f"  AP Study: 美国先修考试题目")
    print(f"  用途: 模型地理知识评测")

    return True


if __name__ == "__main__":
    main()
