#!/usr/bin/env python3
"""
GeoKD-SR 数据集划分模块

支持按比例和指定数量划分train/dev/test，确保空间关系类型和难度分布均衡。

作者: GeoKD-SR Team
日期: 2026-03-04
"""

import os
import sys
import json
import io
import random
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter, defaultdict
from datetime import datetime
import hashlib

# 设置标准输出为UTF-8编码（修复Windows控制台编码问题）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ================================
# 数据类型映射
# ================================

# 空间关系类型到子类型的映射
SPATIAL_RELATION_TYPE_MAP = {
    # D1: 方向关系
    'north_of': 'directional',
    'south_of': 'directional',
    'east_of': 'directional',
    'west_of': 'directional',
    'northeast_of': 'directional',
    'northwest_of': 'directional',
    'southeast_of': 'directional',
    'southwest_of': 'directional',
    'direction': 'directional',
    '方位': 'directional',
    '方向': 'directional',

    # D2: 拓扑关系
    'within': 'topological',
    'contains': 'topological',
    'intersects': 'topological',
    'overlaps': 'topological',
    'touches': 'topological',
    'disjoint': 'topological',
    'crosses': 'topological',
    'adjacent': 'topological',
    'near': 'topological',
    '包含': 'topological',
    '位于': 'topological',
    '相交': 'topological',
    '相邻': 'topological',

    # D3: 度量关系
    'distance': 'metric',
    'far': 'metric',
    'close': 'metric',
    '距离': 'metric',
    '远近': 'metric',
    '公里': 'metric',
    '千米': 'metric',
}

# 复合关系关键词
COMPOSITE_KEYWORDS = [
    '并且', '同时', '而且', '另外', '此外',
    'and', 'also', 'both', 'combined', 'composite'
]


# ================================
# 数据集划分器
# ================================

class DatasetSplitter:
    """数据集划分器 - 支持分层采样确保分布均衡"""

    def __init__(self, seed: Optional[int] = None):
        """
        初始化数据集划分器

        Args:
            seed: 随机种子，确保可复现性
        """
        self.seed = seed or 42
        random.seed(self.seed)

        # 统计信息
        self.stats = {
            'total': 0,
            'train': 0,
            'dev': 0,
            'test': 0,
            'train_distribution': defaultdict(Counter),
            'dev_distribution': defaultdict(Counter),
            'test_distribution': defaultdict(Counter),
        }

    def infer_relation_type(self, record: Dict) -> str:
        """
        推断空间关系类型

        Args:
            record: 数据记录

        Returns:
            空间关系类型 (directional/topological/metric/composite)
        """
        # 首先检查是否已有spatial_relation_type字段
        if 'spatial_relation_type' in record:
            return record['spatial_relation_type']

        # 检查spatial_relation字段
        spatial_relation = record.get('spatial_relation', '').lower()

        # 检查是否是复合关系
        question = record.get('question', '').lower()
        answer = record.get('answer', '').lower()
        reasoning = record.get('reasoning', '').lower()

        combined_text = f"{question} {answer} {reasoning}"
        if any(kw in combined_text for kw in COMPOSITE_KEYWORDS):
            return 'composite'

        # 根据spatial_relation映射
        for relation, relation_type in SPATIAL_RELATION_TYPE_MAP.items():
            if relation.lower() in spatial_relation:
                return relation_type

        # 默认返回composite（如果无法确定）
        return 'composite'

    def infer_difficulty(self, record: Dict) -> str:
        """
        推断难度级别

        Args:
            record: 数据记录

        Returns:
            难度级别 (easy/medium/hard)
        """
        # 如果已有difficulty字段
        if 'difficulty' in record:
            return record['difficulty']

        question = record.get('question', '')
        answer = record.get('answer', '')
        reasoning = record.get('reasoning', '')

        # 统计文本长度
        total_length = len(question) + len(answer) + len(reasoning)

        # 统计实体数量
        entities = record.get('entities', [])
        entity_count = len(entities) if isinstance(entities, list) else 0

        # 判断难度
        if entity_count >= 3 or total_length > 300:
            return 'hard'
        elif entity_count == 2 and total_length > 150:
            return 'medium'
        else:
            return 'easy'

    def add_metadata_fields(self, record: Dict) -> Dict:
        """
        添加元数据字段到记录

        Args:
            record: 原始记录

        Returns:
            添加了元数据的记录
        """
        record = record.copy()

        # 添加spatial_relation_type
        if 'spatial_relation_type' not in record:
            record['spatial_relation_type'] = self.infer_relation_type(record)

        # 添加difficulty
        if 'difficulty' not in record:
            record['difficulty'] = self.infer_difficulty(record)

        return record

    def load_records(self, input_path: str) -> List[Dict]:
        """
        加载数据记录

        Args:
            input_path: 输入文件路径

        Returns:
            数据记录列表
        """
        input_path = Path(input_path)
        records = []

        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        try:
            if input_path.suffix == '.jsonl':
                with open(input_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                record = json.loads(line)
                                # 添加元数据字段
                                record = self.add_metadata_fields(record)
                                records.append(record)
                            except json.JSONDecodeError as e:
                                print(f"[警告] 跳过无效JSON行: {e}")
            elif input_path.suffix == '.json':
                with open(input_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for record in data:
                            record = self.add_metadata_fields(record)
                            records.append(record)
                    elif isinstance(data, dict) and 'data' in data:
                        for record in data['data']:
                            record = self.add_metadata_fields(record)
                            records.append(record)
            else:
                raise ValueError(f"不支持的文件格式: {input_path.suffix}")

        except Exception as e:
            raise RuntimeError(f"加载数据失败: {e}")

        print(f"[OK] 加载了 {len(records)} 条记录")
        return records

    def verify_distribution(self, records: List[Dict]) -> Dict[str, Any]:
        """
        验证数据分布

        Args:
            records: 数据记录列表

        Returns:
            分布统计字典
        """
        distribution = {
            'total': len(records),
            'by_relation_type': Counter(),
            'by_difficulty': Counter(),
            'by_relation_and_difficulty': defaultdict(Counter),
        }

        for record in records:
            relation_type = record.get('spatial_relation_type', 'unknown')
            difficulty = record.get('difficulty', 'unknown')

            distribution['by_relation_type'][relation_type] += 1
            distribution['by_difficulty'][difficulty] += 1
            distribution['by_relation_and_difficulty'][relation_type][difficulty] += 1

        return distribution

    def stratified_split(self, records: List[Dict],
                        train_size: int = 8000,
                        dev_size: int = 800,
                        test_size: int = 3000) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        分层划分数据集，确保各子集的空间关系类型和难度分布均衡

        Args:
            records: 数据记录列表
            train_size: 训练集大小
            dev_size: 验证集大小
            test_size: 测试集大小

        Returns:
            (train_records, dev_records, test_records)
        """
        # 按空间关系类型和难度分组
        groups = defaultdict(list)
        for record in records:
            relation_type = record.get('spatial_relation_type', 'composite')
            difficulty = record.get('difficulty', 'medium')
            key = (relation_type, difficulty)
            groups[key].append(record)

        print(f"\n[分组] 数据已分为 {len(groups)} 个组:")
        for (relation_type, difficulty), group_records in sorted(groups.items()):
            print(f"  {relation_type:12s} + {difficulty:8s}: {len(group_records):4d} 条")

        # 计算每个组的分配比例
        total_needed = train_size + dev_size + test_size
        train_ratio = train_size / total_needed
        dev_ratio = dev_size / total_needed
        test_ratio = test_size / total_needed

        train_records = []
        dev_records = []
        test_records = []

        # 从每个组按比例抽取
        for key, group_records in groups.items():
            random.shuffle(group_records)

            group_size = len(group_records)
            train_count = max(1, int(group_size * train_ratio))
            dev_count = max(1, int(group_size * dev_ratio))
            test_count = max(1, int(group_size * test_ratio))

            # 调整以确保总数不超过组大小
            total_count = train_count + dev_count + test_count
            if total_count > group_size:
                scale = group_size / total_count
                train_count = max(1, int(train_count * scale))
                dev_count = max(1, int(dev_count * scale))
                test_count = group_size - train_count - dev_count

            # 分配记录
            train_records.extend(group_records[:train_count])
            dev_records.extend(group_records[train_count:train_count + dev_count])
            test_records.extend(group_records[train_count + dev_count:train_count + dev_count + test_count])

        # 打乱最终结果
        random.shuffle(train_records)
        random.shuffle(dev_records)
        random.shuffle(test_records)

        print(f"\n[划分结果]")
        print(f"  训练集: {len(train_records)} 条")
        print(f"  验证集: {len(dev_records)} 条")
        print(f"  测试集: {len(test_records)} 条")

        return train_records, dev_records, test_records

    def split_by_ratio(self, records: List[Dict],
                      train_ratio: float = 0.667,
                      dev_ratio: float = 0.067,
                      test_ratio: float = 0.267) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        按比例划分数据集

        Args:
            records: 数据记录列表
            train_ratio: 训练集比例
            dev_ratio: 验证集比例
            test_ratio: 测试集比例

        Returns:
            (train_records, dev_records, test_records)
        """
        # 验证比例
        if abs(train_ratio + dev_ratio + test_ratio - 1.0) > 0.001:
            raise ValueError("比例之和必须等于1")

        # 打乱记录
        shuffled = records.copy()
        random.shuffle(shuffled)

        # 计算划分点
        total = len(shuffled)
        train_end = int(total * train_ratio)
        dev_end = train_end + int(total * dev_ratio)

        train_records = shuffled[:train_end]
        dev_records = shuffled[train_end:dev_end]
        test_records = shuffled[dev_end:]

        print(f"\n[按比例划分]")
        print(f"  训练集: {len(train_records)} 条 ({len(train_records)/total*100:.1f}%)")
        print(f"  验证集: {len(dev_records)} 条 ({len(dev_records)/total*100:.1f}%)")
        print(f"  测试集: {len(test_records)} 条 ({len(test_records)/total*100:.1f}%)")

        return train_records, dev_records, test_records

    def ensure_target_distribution(self, records: List[Dict],
                                  target_distribution: Dict[str, Dict[str, int]]) -> List[Dict]:
        """
        确保数据集符合目标分布

        Args:
            records: 数据记录列表
            target_distribution: 目标分布 {relation_type: {difficulty: count}}

        Returns:
            符合目标分布的数据列表
        """
        selected = []

        for relation_type, difficulty_dist in target_distribution.items():
            for difficulty, count in difficulty_dist.items():
                # 从记录中筛选符合条件的
                matching = [
                    r for r in records
                    if r.get('spatial_relation_type') == relation_type
                    and r.get('difficulty') == difficulty
                    and r not in selected  # 避免重复
                ]

                # 如果数量不足，打乱后全部取走
                random.shuffle(matching)
                needed = min(count, len(matching))
                selected.extend(matching[:needed])

                print(f"  {relation_type:12s} + {difficulty:8s}: 需要 {count:4d}, 实际 {needed:4d}")

        return selected

    def save_records(self, records: List[Dict], output_path: str):
        """
        保存数据记录到文件

        Args:
            records: 数据记录列表
            output_path: 输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        print(f"[OK] 已保存到: {output_path}")

    def generate_split_report(self, train_records: List[Dict],
                             dev_records: List[Dict],
                             test_records: List[Dict]) -> Dict[str, Any]:
        """
        生成划分统计报告

        Args:
            train_records: 训练集记录
            dev_records: 验证集记录
            test_records: 测试集记录

        Returns:
            统计报告字典
        """
        report = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'seed': self.seed,
            'train': {
                'total': len(train_records),
                'by_relation_type': Counter(),
                'by_difficulty': Counter(),
                'by_relation_and_difficulty': defaultdict(Counter),
            },
            'dev': {
                'total': len(dev_records),
                'by_relation_type': Counter(),
                'by_difficulty': Counter(),
                'by_relation_and_difficulty': defaultdict(Counter),
            },
            'test': {
                'total': len(test_records),
                'by_relation_type': Counter(),
                'by_difficulty': Counter(),
                'by_relation_and_difficulty': defaultdict(Counter),
            },
        }

        # 统计训练集
        for record in train_records:
            relation_type = record.get('spatial_relation_type', 'unknown')
            difficulty = record.get('difficulty', 'unknown')
            report['train']['by_relation_type'][relation_type] += 1
            report['train']['by_difficulty'][difficulty] += 1
            report['train']['by_relation_and_difficulty'][relation_type][difficulty] += 1

        # 统计验证集
        for record in dev_records:
            relation_type = record.get('spatial_relation_type', 'unknown')
            difficulty = record.get('difficulty', 'unknown')
            report['dev']['by_relation_type'][relation_type] += 1
            report['dev']['by_difficulty'][difficulty] += 1
            report['dev']['by_relation_and_difficulty'][relation_type][difficulty] += 1

        # 统计测试集
        for record in test_records:
            relation_type = record.get('spatial_relation_type', 'unknown')
            difficulty = record.get('difficulty', 'unknown')
            report['test']['by_relation_type'][relation_type] += 1
            report['test']['by_difficulty'][difficulty] += 1
            report['test']['by_relation_and_difficulty'][relation_type][difficulty] += 1

        return report

    def print_split_report(self, report: Dict[str, Any]):
        """
        打印划分统计报告

        Args:
            report: 统计报告字典
        """
        print("\n" + "="*80)
        print("数据集划分统计报告")
        print("="*80)

        for split_name in ['train', 'dev', 'test']:
            split_data = report[split_name]
            split_cn = {'train': '训练集', 'dev': '验证集', 'test': '测试集'}[split_name]

            print(f"\n{split_cn} ({split_data['total']} 条)")
            print("-" * 80)

            # 按空间关系类型和难度的详细分布
            print(f"\n{'空间关系类型':<15} {'难度':<10} {'数量':<10} {'占比'}")
            print("-" * 80)

            for relation_type in ['directional', 'topological', 'metric', 'composite']:
                for difficulty in ['easy', 'medium', 'hard']:
                    count = split_data['by_relation_and_difficulty'][relation_type][difficulty]
                    if count > 0:
                        percentage = (count / split_data['total']) * 100
                        print(f"{relation_type:<15} {difficulty:<10} {count:<10} {percentage:.2f}%")

        print("\n" + "="*80)

    def save_split_report(self, report: Dict[str, Any], output_path: str):
        """
        保存划分统计报告

        Args:
            report: 统计报告字典
            output_path: 输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 转换defaultdict为普通dict以便JSON序列化
        report_copy = {}
        for key, value in report.items():
            if isinstance(value, dict):
                report_copy[key] = {}
                for k2, v2 in value.items():
                    if isinstance(v2, Counter):
                        report_copy[key][k2] = dict(v2)
                    elif isinstance(v2, defaultdict):
                        report_copy[key][k2] = {k3: dict(v3) for k3, v3 in v2.items()}
                    else:
                        report_copy[key][k2] = v2
            else:
                report_copy[key] = value

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_copy, f, ensure_ascii=False, indent=2)

        print(f"[OK] 报告已保存到: {output_path}")


# ================================
# 命令行接口
# ================================

def main():
    """命令行接口"""
    parser = argparse.ArgumentParser(
        description='GeoKD-SR 数据集划分工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 按指定数量划分
  python split_dataset.py --input data/geosr_chain/all_data.jsonl --output data/geosr_chain/ --train 8000 --dev 800 --test 3000

  # 按比例划分
  python split_dataset.py --input data/geosr_chain/all_data.jsonl --output data/geosr_chain/ --ratio --train_ratio 0.667 --dev_ratio 0.067 --test_ratio 0.267

  # 使用目标分布
  python split_dataset.py --input data/geosr_chain/all_data.jsonl --output data/geosr_chain/ --target_distribution

  # 指定随机种子
  python split_dataset.py --input data/geosr_chain/all_data.jsonl --output data/geosr_chain/ --train 8000 --seed 123
        """
    )

    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='输入数据文件路径 (.jsonl 或 .json)'
    )

    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='输出目录路径'
    )

    parser.add_argument(
        '--train',
        type=int,
        default=8000,
        help='训练集大小（默认8000）'
    )

    parser.add_argument(
        '--dev',
        type=int,
        default=800,
        help='验证集大小（默认800）'
    )

    parser.add_argument(
        '--test',
        type=int,
        default=3000,
        help='测试集大小（默认3000）'
    )

    parser.add_argument(
        '--ratio',
        action='store_true',
        help='使用比例模式而非绝对数量'
    )

    parser.add_argument(
        '--train_ratio',
        type=float,
        default=0.667,
        help='训练集比例（默认0.667）'
    )

    parser.add_argument(
        '--dev_ratio',
        type=float,
        default=0.067,
        help='验证集比例（默认0.067）'
    )

    parser.add_argument(
        '--test_ratio',
        type=float,
        default=0.267,
        help='测试集比例（默认0.267）'
    )

    parser.add_argument(
        '--target_distribution',
        action='store_true',
        help='使用目标分布模式'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='随机种子（默认42）'
    )

    parser.add_argument(
        '--no_report',
        action='store_true',
        help='不生成统计报告'
    )

    parser.add_argument(
        '--train_output',
        type=str,
        default='train.jsonl',
        help='训练集输出文件名（默认train.jsonl）'
    )

    parser.add_argument(
        '--dev_output',
        type=str,
        default='dev.jsonl',
        help='验证集输出文件名（默认dev.jsonl）'
    )

    parser.add_argument(
        '--test_output',
        type=str,
        default='test.jsonl',
        help='测试集输出文件名（默认test.jsonl）'
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("GeoKD-SR 数据集划分工具")
    print("="*80)

    # 创建划分器
    splitter = DatasetSplitter(seed=args.seed)

    # 加载数据
    print(f"\n[1/5] 加载数据...")
    print(f"  输入文件: {args.input}")
    try:
        records = splitter.load_records(args.input)
    except Exception as e:
        print(f"[错误] {e}")
        sys.exit(1)

    # 验证分布
    print(f"\n[2/5] 验证数据分布...")
    distribution = splitter.verify_distribution(records)
    print(f"  总记录数: {distribution['total']}")
    print(f"\n  按空间关系类型:")
    for rel_type, count in sorted(distribution['by_relation_type'].items()):
        percentage = (count / distribution['total']) * 100
        print(f"    {rel_type}: {count} ({percentage:.2f}%)")
    print(f"\n  按难度:")
    for difficulty, count in sorted(distribution['by_difficulty'].items()):
        percentage = (count / distribution['total']) * 100
        print(f"    {difficulty}: {count} ({percentage:.2f}%)")

    # 划分数据集
    print(f"\n[3/5] 划分数据集...")

    if args.ratio:
        # 按比例划分
        train_records, dev_records, test_records = splitter.split_by_ratio(
            records,
            train_ratio=args.train_ratio,
            dev_ratio=args.dev_ratio,
            test_ratio=args.test_ratio
        )
    else:
        # 按数量划分（使用分层采样）
        train_records, dev_records, test_records = splitter.stratified_split(
            records,
            train_size=args.train,
            dev_size=args.dev,
            test_size=args.test
        )

    # 保存数据集
    print(f"\n[4/5] 保存数据集...")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_path = output_dir / args.train_output
    dev_path = output_dir / args.dev_output
    test_path = output_dir / args.test_output

    splitter.save_records(train_records, str(train_path))
    splitter.save_records(dev_records, str(dev_path))
    splitter.save_records(test_records, str(test_path))

    # 生成报告
    if not args.no_report:
        print(f"\n[5/5] 生成统计报告...")
        report = splitter.generate_split_report(train_records, dev_records, test_records)
        splitter.print_split_report(report)

        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = output_dir / f"split_report_{timestamp}.json"
        splitter.save_split_report(report, str(report_path))

    print("\n" + "="*80)
    print("[完成] 数据集划分完成！")
    print("="*80)
    print(f"\n输出文件:")
    print(f"  训练集: {train_path} ({len(train_records)} 条)")
    print(f"  验证集: {dev_path} ({len(dev_records)} 条)")
    print(f"  测试集: {test_path} ({len(test_records)} 条)")
    print()


if __name__ == '__main__':
    main()
