#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 数据集整合脚本
将hibiki works目录的数据整合为train.jsonl、dev.jsonl、test.jsonl
并生成数据质量报告

数据集划分策略：
- train: 80% (约5528条)
- dev: 10% (约691条)
- test: 10% (约691条)

分层采样：确保各个spatial_relation_type和difficulty在各个划分中分布一致
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter, defaultdict
from datetime import datetime
import random


class DatasetConsolidator:
    """数据集整合器"""

    def __init__(self, input_dir: str, output_dir: str, train_ratio: float = 0.8,
                 dev_ratio: float = 0.1, test_ratio: float = 0.1, seed: int = 42):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.train_ratio = train_ratio
        self.dev_ratio = dev_ratio
        self.test_ratio = test_ratio
        self.seed = seed

        # 设置随机种子
        random.seed(self.seed)

        # 统计信息
        self.stats = {
            "total_records": 0,
            "train_count": 0,
            "dev_count": 0,
            "test_count": 0,
            "spatial_distribution": defaultdict(lambda: {"train": 0, "dev": 0, "test": 0}),
            "difficulty_distribution": defaultdict(lambda: {"train": 0, "dev": 0, "test": 0}),
            "topology_subtype_distribution": defaultdict(lambda: {"train": 0, "dev": 0, "test": 0}),
        }

    def load_all_records(self) -> List[Dict]:
        """加载所有输入文件"""
        all_records = []
        jsonl_files = sorted(self.input_dir.glob("*.jsonl"))

        print(f"找到 {len(jsonl_files)} 个文件")

        for file_path in jsonl_files:
            print(f"  加载: {file_path.name}")
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            record = json.loads(line)
                            all_records.append(record)
                        except json.JSONDecodeError as e:
                            print(f"    警告: JSON解析失败: {e}")

        print(f"\n总共加载: {len(all_records)} 条记录")
        return all_records

    def stratified_split(self, records: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """分层采样划分数据集

        首先按照spatial_relation_type和difficulty进行分组
        然后在每个组内进行随机划分
        """
        # 按spatial_type和difficulty分组
        groups = defaultdict(list)

        for record in records:
            spatial_type = record.get("spatial_relation_type", "unknown")
            difficulty = record.get("difficulty", "unknown")
            key = f"{spatial_type}_{difficulty}"
            groups[key].append(record)

        print(f"\n分为 {len(groups)} 个层")

        train_records = []
        dev_records = []
        test_records = []

        for key, group_records in groups.items():
            random.shuffle(group_records)

            n = len(group_records)
            n_train = int(n * self.train_ratio)
            n_dev = int(n * self.dev_ratio)
            # 剩余的给test

            train_records.extend(group_records[:n_train])
            dev_records.extend(group_records[n_train:n_train + n_dev])
            test_records.extend(group_records[n_train + n_dev:])

        print(f"划分完成:")
        print(f"  train: {len(train_records)} 条")
        print(f"  dev: {len(dev_records)} 条")
        print(f"  test: {len(test_records)} 条")

        return train_records, dev_records, test_records

    def update_split_field(self, records: List[Dict], split_name: str):
        """更新记录的split字段"""
        for record in records:
            record["split"] = split_name

    def write_records(self, records: List[Dict], split_name: str):
        """写入记录到文件"""
        output_file = self.output_dir / f"{split_name}.jsonl"

        with open(output_file, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        print(f"写入: {output_file} ({len(records)} 条)")
        return len(records)

    def collect_statistics(self, train: List[Dict], dev: List[Dict], test: List[Dict]):
        """收集统计信息"""
        self.stats["total_records"] = len(train) + len(dev) + len(test)
        self.stats["train_count"] = len(train)
        self.stats["dev_count"] = len(dev)
        self.stats["test_count"] = len(test)

        for split_name, records in [("train", train), ("dev", dev), ("test", test)]:
            for record in records:
                spatial_type = record.get("spatial_relation_type", "unknown")
                difficulty = record.get("difficulty", "unknown")
                topology_subtype = record.get("topology_subtype", "none")

                self.stats["spatial_distribution"][spatial_type][split_name] += 1
                self.stats["difficulty_distribution"][difficulty][split_name] += 1

                if topology_subtype != "none":
                    self.stats["topology_subtype_distribution"][topology_subtype][split_name] += 1

    def generate_quality_report(self) -> str:
        """生成数据质量报告"""
        lines = [
            "# GeoKD-SR 数据集质量报告",
            "",
            f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> **数据来源**: {self.input_dir}",
            f"> **输出目录**: {self.output_dir}",
            "",
            "---",
            "",
            "## 一、数据集概览",
            "",
            f"- **总记录数**: {self.stats['total_records']}",
            f"- **训练集**: {self.stats['train_count']} 条 ({self.stats['train_count']/self.stats['total_records']*100:.1f}%)",
            f"- **验证集**: {self.stats['dev_count']} 条 ({self.stats['dev_count']/self.stats['total_records']*100:.1f}%)",
            f"- **测试集**: {self.stats['test_count']} 条 ({self.stats['test_count']/self.stats['total_records']*100:.1f}%)",
            "",
            "---",
            "",
            "## 二、空间关系类型分布",
            "",
            "| 空间关系类型 | 训练集 | 验证集 | 测试集 | 合计 |",
            "|-------------|--------|--------|--------|------|",
        ]

        for spatial_type in ["directional", "topological", "metric", "composite"]:
            dist = self.stats["spatial_distribution"][spatial_type]
            total = dist["train"] + dist["dev"] + dist["test"]
            lines.append(
                f"| {spatial_type} | {dist['train']} | {dist['dev']} | {dist['test']} | {total} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 三、难度分布",
            "",
            "| 难度 | 训练集 | 验证集 | 测试集 | 合计 |",
            "|------|--------|--------|--------|------|",
        ])

        for difficulty in ["easy", "medium", "hard"]:
            dist = self.stats["difficulty_distribution"][difficulty]
            total = dist["train"] + dist["dev"] + dist["test"]
            lines.append(
                f"| {difficulty} | {dist['train']} | {dist['dev']} | {dist['test']} | {total} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 四、拓扑子类型分布",
            "",
            "| 子类型 | 训练集 | 验证集 | 测试集 | 合计 |",
            "|--------|--------|--------|--------|------|",
        ])

        # 按总数排序
        sorted_subtypes = sorted(
            self.stats["topology_subtype_distribution"].items(),
            key=lambda x: sum(x[1].values()),
            reverse=True
        )

        for subtype, dist in sorted_subtypes:
            total = dist["train"] + dist["dev"] + dist["test"]
            lines.append(
                f"| {subtype} | {dist['train']} | {dist['dev']} | {dist['test']} | {total} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 五、字段完整性",
            "",
            "所有记录包含以下必需字段：",
            "",
            "- `id`: 唯一标识符",
            "- `spatial_relation_type`: 空间关系类型",
            "- `question`: 问题文本",
            "- `answer`: 答案文本",
            "- `reasoning_chain`: 5步推理链",
            "- `entities`: 实体列表（含坐标）",
            "- `spatial_tokens`: 空间token列表",
            "- `difficulty`: 难度级别",
            "- `difficulty_score`: 难度分数",
            "- `entity_to_token`: 实体到token的映射",
            "- `split`: 数据集划分",
            "",
            "---",
            "",
            "## 六、使用建议",
            "",
            "1. **训练集 (train.jsonl)**: 用于模型训练",
            "2. **验证集 (dev.jsonl)**: 用于超参数调优和模型选择",
            "3. **测试集 (test.jsonl)**: 用于最终模型评估",
            "",
            "数据集已按照空间关系类型和难度进行分层采样，确保各分布一致。",
            "",
            "---",
            "",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ""
        ])

        return '\n'.join(lines)

    def run(self):
        """执行整合流程"""
        print("=" * 60)
        print("GeoKD-SR 数据集整合脚本")
        print("=" * 60)
        print(f"\n输入目录: {self.input_dir}")
        print(f"输出目录: {self.output_dir}")
        print(f"划分比例: train={self.train_ratio}, dev={self.dev_ratio}, test={self.test_ratio}")
        print(f"随机种子: {self.seed}")

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1. 加载所有记录
        print("\n" + "=" * 60)
        print("[步骤1] 加载数据")
        print("=" * 60)
        all_records = self.load_all_records()

        # 2. 分层划分
        print("\n" + "=" * 60)
        print("[步骤2] 分层划分数据集")
        print("=" * 60)
        train, dev, test = self.stratified_split(all_records)

        # 3. 更新split字段
        print("\n" + "=" * 60)
        print("[步骤3] 更新split字段")
        print("=" * 60)
        self.update_split_field(train, "train")
        self.update_split_field(dev, "dev")
        self.update_split_field(test, "test")
        print("split字段更新完成")

        # 4. 写入文件
        print("\n" + "=" * 60)
        print("[步骤4] 写入文件")
        print("=" * 60)
        self.write_records(train, "train")
        self.write_records(dev, "dev")
        self.write_records(test, "test")

        # 5. 收集统计信息
        print("\n" + "=" * 60)
        print("[步骤5] 收集统计信息")
        print("=" * 60)
        self.collect_statistics(train, dev, test)

        # 6. 生成质量报告
        print("\n" + "=" * 60)
        print("[步骤6] 生成质量报告")
        print("=" * 60)
        report = self.generate_quality_report()
        report_file = self.output_dir / "dataset_quality_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"质量报告: {report_file}")

        # 完成
        print("\n" + "=" * 60)
        print("整合完成!")
        print("=" * 60)
        print(f"\n输出文件:")
        print(f"  - {self.output_dir / 'train.jsonl'} ({len(train)} 条)")
        print(f"  - {self.output_dir / 'dev.jsonl'} ({len(dev)} 条)")
        print(f"  - {self.output_dir / 'test.jsonl'} ({len(test)} 条)")
        print(f"  - {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description="GeoKD-SR 数据集整合脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python consolidate_dataset.py --input "C:/Users/60207/Documents/hibiki works/" --output data/geosr_chain/
  python consolidate_dataset.py --input ./data/hibiki/ --output ./data/final/ --train-ratio 0.7 --dev-ratio 0.15 --test-ratio 0.15
        """
    )

    parser.add_argument(
        "--input", "-i",
        default="C:/Users/60207/Documents/hibiki works/",
        help="输入目录路径（包含jsonl文件）"
    )
    parser.add_argument(
        "--output", "-o",
        default="D:/30_keyan/GeoKD-SR/data/geosr_chain/",
        help="输出目录路径"
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="训练集比例（默认: 0.8）"
    )
    parser.add_argument(
        "--dev-ratio",
        type=float,
        default=0.1,
        help="验证集比例（默认: 0.1）"
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.1,
        help="测试集比例（默认: 0.1）"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子（默认: 42）"
    )

    args = parser.parse_args()

    # 验证比例
    if abs(args.train_ratio + args.dev_ratio + args.test_ratio - 1.0) > 0.01:
        print(f"错误: 比例之和应为1.0，当前为{args.train_ratio + args.dev_ratio + args.test_ratio}")
        return 1

    consolidator = DatasetConsolidator(
        args.input,
        args.output,
        args.train_ratio,
        args.dev_ratio,
        args.test_ratio,
        args.seed
    )
    consolidator.run()

    return 0


if __name__ == "__main__":
    exit(main())
