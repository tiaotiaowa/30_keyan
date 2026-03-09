#!/usr/bin/env python3
"""
GeoKD-SR 分层数据集划分模块

支持按分层采样方式将数据集划分为train/dev/test三部分，确保：
1. 空间关系类型分布符合目标比例
2. 难度分布符合目标比例
3. 实体对在train/dev/test中互不重叠

作者: GeoKD-SR Team
日期: 2026-03-08
"""

import os
import sys
import json
import io
import random
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import Counter, defaultdict
from datetime import datetime
import itertools

# 设置标准输出为UTF-8编码（修复Windows控制台编码问题）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ================================
# 目标分布配置
# ================================

# 空间关系类型目标分布（百分比）
TARGET_SPATIAL_DISTRIBUTION = {
    'directional': 0.25,    # 25%
    'topological': 0.275,   # 27.5%
    'metric': 0.275,        # 27.5%
    'composite': 0.20,      # 20%
}

# 难度目标分布（百分比）
TARGET_DIFFICULTY_DISTRIBUTION = {
    'easy': 0.30,     # 30%
    'medium': 0.50,   # 50%
    'hard': 0.20,     # 20%
}

# 数据集划分比例
DEFAULT_SPLIT_RATIO = {
    'train': 0.8,
    'dev': 0.1,
    'test': 0.1,
}


# ================================
# 实用工具函数
# ================================

def extract_entity_pair(record: Dict) -> Optional[Tuple[str, str]]:
    """
    提取实体对

    Args:
        record: 数据记录

    Returns:
        排序后的实体对元组 (entity1, entity2)，如果无法提取则返回None
    """
    entities = record.get('entities', [])
    if not isinstance(entities, list) or len(entities) < 2:
        return None

    # 提取实体名称
    entity_names = []
    for entity in entities[:2]:  # 只取前两个实体
        if isinstance(entity, dict):
            name = entity.get('name', '')
        else:
            name = str(entity)
        if name:
            entity_names.append(name)

    if len(entity_names) < 2:
        return None

    # 排序以确保一致性
    entity_names.sort()
    return (entity_names[0], entity_names[1])


def calculate_ks_statistic(dist1: Dict[str, int], dist2: Dict[str, int]) -> float:
    """
    计算两个分布之间的Kolmogorov-Smirnov统计量

    Args:
        dist1: 分布1
        dist2: 分布2

    Returns:
        KS统计量（0-1之间，越小越相似）
    """
    all_keys = set(dist1.keys()) | set(dist2.keys())

    # 归一化分布
    total1 = sum(dist1.values()) or 1
    total2 = sum(dist2.values()) or 1

    max_diff = 0.0
    cum1 = 0.0
    cum2 = 0.0

    for key in sorted(all_keys):
        cum1 += dist1.get(key, 0) / total1
        cum2 += dist2.get(key, 0) / total2
        max_diff = max(max_diff, abs(cum1 - cum2))

    return max_diff


# ================================
# 分层数据集划分器
# ================================

class StratifiedDatasetSplitter:
    """分层数据集划分器 - 支持实体对互斥和分布均衡"""

    def __init__(self, seed: Optional[int] = None):
        """
        初始化划分器

        Args:
            seed: 随机种子
        """
        self.seed = seed or 42
        random.seed(self.seed)

        # 统计信息
        self.stats = {
            'total_records': 0,
            'total_entity_pairs': 0,
            'assigned_pairs': defaultdict(int),
        }

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
                                records.append(record)
                            except json.JSONDecodeError as e:
                                print(f"[警告] 跳过无效JSON行: {e}")
            elif input_path.suffix == '.json':
                with open(input_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict) and 'data' in data:
                        records = data['data']
            else:
                raise ValueError(f"不支持的文件格式: {input_path.suffix}")

        except Exception as e:
            raise RuntimeError(f"加载数据失败: {e}")

        print(f"[OK] 加载了 {len(records)} 条记录")
        return records

    def analyze_dataset(self, records: List[Dict]) -> Dict[str, Any]:
        """
        分析数据集分布

        Args:
            records: 数据记录列表

        Returns:
            分析报告字典
        """
        analysis = {
            'total_records': len(records),
            'by_relation_type': Counter(),
            'by_difficulty': Counter(),
            'by_both': defaultdict(Counter),
            'entity_pairs': defaultdict(list),  # entity_pair -> [records]
            'records_without_entities': [],
        }

        for idx, record in enumerate(records):
            # 空间关系类型
            relation_type = record.get('spatial_relation_type', 'unknown')
            analysis['by_relation_type'][relation_type] += 1

            # 难度
            difficulty = record.get('difficulty', 'unknown')
            analysis['by_difficulty'][difficulty] += 1

            # 组合分布
            analysis['by_both'][relation_type][difficulty] += 1

            # 实体对
            entity_pair = extract_entity_pair(record)
            if entity_pair:
                analysis['entity_pairs'][entity_pair].append(record)
            else:
                analysis['records_without_entities'].append(idx)

        analysis['total_entity_pairs'] = len(analysis['entity_pairs'])

        return analysis

    def calculate_target_counts(self, total: int,
                               split_ratio: Dict[str, float]) -> Dict[str, int]:
        """
        计算各数据集的目标数量

        Args:
            total: 总记录数
            split_ratio: 划分比例

        Returns:
            各数据集的目标数量
        """
        target_counts = {}
        for split_name, ratio in split_ratio.items():
            target_counts[split_name] = max(1, int(total * ratio))

        # 确保总和不超过总数
        total_target = sum(target_counts.values())
        if total_target > total:
            scale = total / total_target
            for split_name in target_counts:
                target_counts[split_name] = max(1, int(target_counts[split_name] * scale))

        return target_counts

    def calculate_stratified_targets(self, total: int,
                                    split_ratio: Dict[str, float]) -> Dict[str, Dict[str, Dict[str, int]]]:
        """
        计算分层数量目标

        Args:
            total: 总记录数
            split_ratio: 划分比例

        Returns:
            分层目标 {split: {relation_type: {difficulty: count}}}
        """
        # 首先计算总体各层的目标数量
        layer_targets = {}
        for relation_type, rel_ratio in TARGET_SPATIAL_DISTRIBUTION.items():
            layer_targets[relation_type] = {}
            for difficulty, diff_ratio in TARGET_DIFFICULTY_DISTRIBUTION.items():
                combined_ratio = rel_ratio * diff_ratio
                layer_targets[relation_type][difficulty] = max(1, int(total * combined_ratio))

        # 然后分配到各个数据集
        stratified_targets = {}
        for split_name, split_prop in split_ratio.items():
            stratified_targets[split_name] = {}
            for relation_type, difficulty_targets in layer_targets.items():
                stratified_targets[split_name][relation_type] = {}
                for difficulty, count in difficulty_targets.items():
                    stratified_targets[split_name][relation_type][difficulty] = max(
                        1, int(count * split_prop)
                    )

        return stratified_targets

    def select_entity_pairs_for_split(self,
                                     available_pairs: Dict[Tuple[str, str], List[Dict]],
                                     target_count: int,
                                     relation_type: str,
                                     difficulty: str,
                                     exclude_pairs: Set[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        为特定数据集选择实体对

        Args:
            available_pairs: 可用的实体对字典
            target_count: 目标数量
            relation_type: 空间关系类型
            difficulty: 难度
            exclude_pairs: 要排除的实体对集合

        Returns:
            选中的实体对列表
        """
        # 筛选符合条件的实体对
        candidates = []
        for entity_pair, records in available_pairs.items():
            if entity_pair in exclude_pairs:
                continue
            # 检查记录中是否有符合条件的
            for record in records:
                if (record.get('spatial_relation_type') == relation_type and
                    record.get('difficulty') == difficulty):
                    candidates.append((entity_pair, records))
                    break

        # 按记录数量排序（优先选择记录多的实体对，以便更好地利用数据）
        candidates.sort(key=lambda x: len(x[1]), reverse=True)

        # 贪心选择实体对直到达到目标数量
        selected_pairs = []
        selected_count = 0

        for entity_pair, records in candidates:
            if selected_count >= target_count:
                break
            selected_pairs.append(entity_pair)
            # 计算这个实体对中有多少符合条件的记录
            matching_records = [
                r for r in records
                if r.get('spatial_relation_type') == relation_type
                and r.get('difficulty') == difficulty
            ]
            selected_count += len(matching_records)

        return selected_pairs

    def stratified_split_with_entity_pairs(self,
                                         records: List[Dict],
                                         total: int = 10000,
                                         split_ratio: Dict[str, float] = None) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        执行分层划分，确保实体对互斥

        Args:
            records: 数据记录列表
            total: 目标总记录数
            split_ratio: 划分比例

        Returns:
            (train_records, dev_records, test_records)
        """
        if split_ratio is None:
            split_ratio = DEFAULT_SPLIT_RATIO.copy()

        print(f"\n[分层划分] 目标总记录数: {total}")
        print(f"  划分比例: train={split_ratio['train']:.1%}, "
              f"dev={split_ratio['dev']:.1%}, test={split_ratio['test']:.1%}")

        # 分析数据集
        print(f"\n[1/5] 分析数据集...")
        analysis = self.analyze_dataset(records)

        print(f"  总记录数: {analysis['total_records']}")
        print(f"  总实体对数: {analysis['total_entity_pairs']}")
        print(f"  无实体对的记录数: {len(analysis['records_without_entities'])}")

        print(f"\n  空间关系类型分布:")
        for rel_type, count in sorted(analysis['by_relation_type'].items()):
            percentage = count / analysis['total_records'] * 100
            print(f"    {rel_type}: {count} ({percentage:.2f}%)")

        print(f"\n  难度分布:")
        for difficulty, count in sorted(analysis['by_difficulty'].items()):
            percentage = count / analysis['total_records'] * 100
            print(f"    {difficulty}: {count} ({percentage:.2f}%)")

        # 计算分层数量目标
        print(f"\n[2/5] 计算分层数量目标...")
        stratified_targets = self.calculate_stratified_targets(total, split_ratio)

        # 打印目标
        for split_name in ['train', 'dev', 'test']:
            print(f"\n  {split_name}集目标:")
            for relation_type in ['directional', 'topological', 'metric', 'composite']:
                for difficulty in ['easy', 'medium', 'hard']:
                    target = stratified_targets[split_name][relation_type][difficulty]
                    if target > 0:
                        print(f"    {relation_type:12s} + {difficulty:8s}: {target:4d} 条")

        # 执行划分
        print(f"\n[3/5] 执行分层划分...")
        print(f"  使用实体对互斥策略...")

        # 按实体对分组
        entity_pair_groups = analysis['entity_pairs']

        # 为每个数据集分配实体对
        splits = {
            'train': {'records': [], 'assigned_pairs': set()},
            'dev': {'records': [], 'assigned_pairs': set()},
            'test': {'records': [], 'assigned_pairs': set()},
        }

        # 按层分配实体对
        for relation_type in ['directional', 'topological', 'metric', 'composite']:
            for difficulty in ['easy', 'medium', 'hard']:
                # 首先处理train
                train_target = stratified_targets['train'][relation_type][difficulty]
                if train_target > 0:
                    selected = self.select_entity_pairs_for_split(
                        entity_pair_groups,
                        train_target,
                        relation_type,
                        difficulty,
                        splits['train']['assigned_pairs'] | splits['dev']['assigned_pairs'] | splits['test']['assigned_pairs']
                    )
                    splits['train']['assigned_pairs'].update(selected)
                    # 收集记录
                    for pair in selected:
                        for record in entity_pair_groups[pair]:
                            if (record.get('spatial_relation_type') == relation_type and
                                record.get('difficulty') == difficulty):
                                splits['train']['records'].append(record)

                # 然后处理dev
                dev_target = stratified_targets['dev'][relation_type][difficulty]
                if dev_target > 0:
                    selected = self.select_entity_pairs_for_split(
                        entity_pair_groups,
                        dev_target,
                        relation_type,
                        difficulty,
                        splits['train']['assigned_pairs'] | splits['dev']['assigned_pairs'] | splits['test']['assigned_pairs']
                    )
                    splits['dev']['assigned_pairs'].update(selected)
                    for pair in selected:
                        for record in entity_pair_groups[pair]:
                            if (record.get('spatial_relation_type') == relation_type and
                                record.get('difficulty') == difficulty):
                                splits['dev']['records'].append(record)

                # 最后处理test
                test_target = stratified_targets['test'][relation_type][difficulty]
                if test_target > 0:
                    selected = self.select_entity_pairs_for_split(
                        entity_pair_groups,
                        test_target,
                        relation_type,
                        difficulty,
                        splits['train']['assigned_pairs'] | splits['dev']['assigned_pairs'] | splits['test']['assigned_pairs']
                    )
                    splits['test']['assigned_pairs'].update(selected)
                    for pair in selected:
                        for record in entity_pair_groups[pair]:
                            if (record.get('spatial_relation_type') == relation_type and
                                record.get('difficulty') == difficulty):
                                splits['test']['records'].append(record)

        # 处理无实体对的记录（按比例分配）
        if analysis['records_without_entities']:
            no_entity_records = [records[i] for i in analysis['records_without_entities']]
            random.shuffle(no_entity_records)

            train_count = int(len(no_entity_records) * split_ratio['train'])
            dev_count = int(len(no_entity_records) * split_ratio['dev'])

            splits['train']['records'].extend(no_entity_records[:train_count])
            splits['dev']['records'].extend(no_entity_records[train_count:train_count + dev_count])
            splits['test']['records'].extend(no_entity_records[train_count + dev_count:])

        # 打乱结果
        random.shuffle(splits['train']['records'])
        random.shuffle(splits['dev']['records'])
        random.shuffle(splits['test']['records'])

        print(f"\n[4/5] 划分完成:")
        print(f"  训练集: {len(splits['train']['records'])} 条 "
              f"({len(splits['train']['assigned_pairs'])} 个实体对)")
        print(f"  验证集: {len(splits['dev']['records'])} 条 "
              f"({len(splits['dev']['assigned_pairs'])} 个实体对)")
        print(f"  测试集: {len(splits['test']['records'])} 条 "
              f"({len(splits['test']['assigned_pairs'])} 个实体对)")

        return splits['train']['records'], splits['dev']['records'], splits['test']['records']

    def save_records(self, records: List[Dict], output_path: str):
        """
        保存数据记录

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

    def validate_split(self, train_records: List[Dict],
                      dev_records: List[Dict],
                      test_records: List[Dict]) -> Dict[str, Any]:
        """
        验证划分结果

        Args:
            train_records: 训练集记录
            dev_records: 验证集记录
            test_records: 测试集记录

        Returns:
            验证报告
        """
        validation = {
            'is_valid': True,
            'issues': [],
            'warnings': [],
            'entity_pair_overlap': False,
            'distribution_similarity': {},
        }

        # 检查实体对重叠
        print(f"\n[5/5] 验证划分结果...")

        train_pairs = set()
        dev_pairs = set()
        test_pairs = set()

        for record in train_records:
            pair = extract_entity_pair(record)
            if pair:
                train_pairs.add(pair)

        for record in dev_records:
            pair = extract_entity_pair(record)
            if pair:
                dev_pairs.add(pair)

        for record in test_records:
            pair = extract_entity_pair(record)
            if pair:
                test_pairs.add(pair)

        # 检查重叠
        train_dev_overlap = train_pairs & dev_pairs
        train_test_overlap = train_pairs & test_pairs
        dev_test_overlap = dev_pairs & test_pairs

        if train_dev_overlap:
            validation['is_valid'] = False
            validation['entity_pair_overlap'] = True
            validation['issues'].append(f"train和dev有 {len(train_dev_overlap)} 个重叠实体对")

        if train_test_overlap:
            validation['is_valid'] = False
            validation['entity_pair_overlap'] = True
            validation['issues'].append(f"train和test有 {len(train_test_overlap)} 个重叠实体对")

        if dev_test_overlap:
            validation['is_valid'] = False
            validation['entity_pair_overlap'] = True
            validation['issues'].append(f"dev和test有 {len(dev_test_overlap)} 个重叠实体对")

        if not validation['entity_pair_overlap']:
            print(f"  ✓ 实体对互斥检查通过")

        # 检查分布相似性
        all_records = train_records + dev_records + test_records
        overall_dist = self._get_distribution(all_records)
        train_dist = self._get_distribution(train_records)
        dev_dist = self._get_distribution(dev_records)
        test_dist = self._get_distribution(test_records)

        # 计算KS统计量
        for split_name, split_dist in [('train', train_dist), ('dev', dev_dist), ('test', test_dist)]:
            ks_value = calculate_ks_statistic(overall_dist, split_dist)
            validation['distribution_similarity'][split_name] = ks_value
            if ks_value < 0.1:
                print(f"  ✓ {split_name}分布与整体分布相似 (KS={ks_value:.4f})")
            elif ks_value < 0.2:
                validation['warnings'].append(f"{split_name}分布与整体分布有差异 (KS={ks_value:.4f})")
                print(f"  ! {split_name}分布与整体分布有差异 (KS={ks_value:.4f})")
            else:
                validation['is_valid'] = False
                validation['issues'].append(f"{split_name}分布与整体分布差异较大 (KS={ks_value:.4f})")
                print(f"  ✗ {split_name}分布与整体分布差异较大 (KS={ks_value:.4f})")

        return validation

    def _get_distribution(self, records: List[Dict]) -> Dict[str, int]:
        """获取记录的（关系类型，难度）分布"""
        dist = Counter()
        for record in records:
            key = (
                record.get('spatial_relation_type', 'unknown'),
                record.get('difficulty', 'unknown')
            )
            dist[key] += 1
        return dist

    def generate_report(self, train_records: List[Dict],
                       dev_records: List[Dict],
                       test_records: List[Dict],
                       validation: Dict[str, Any]) -> str:
        """
        生成划分报告

        Args:
            train_records: 训练集记录
            dev_records: 验证集记录
            test_records: 测试集记录
            validation: 验证结果

        Returns:
            Markdown格式的报告字符串
        """
        lines = []
        lines.append("# 数据集分层划分报告")
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"随机种子: {self.seed}")
        lines.append("")

        # 总体统计
        total = len(train_records) + len(dev_records) + len(test_records)
        lines.append("## 总体统计")
        lines.append("")
        lines.append(f"| 数据集 | 记录数 | 占比 |")
        lines.append(f"|--------|--------|------|")
        lines.append(f"| train  | {len(train_records):6d} | {len(train_records)/total*100:.1f}% |")
        lines.append(f"| dev    | {len(dev_records):6d} | {len(dev_records)/total*100:.1f}% |")
        lines.append(f"| test   | {len(test_records):6d} | {len(test_records)/total*100:.1f}% |")
        lines.append(f"| 总计   | {total:6d} | 100.0% |")
        lines.append("")

        # 空间关系类型分布
        lines.append("## 空间关系类型分布")
        lines.append("")
        lines.append("| 数据集 | directional | topological | metric | composite |")
        lines.append("|--------|-------------|-------------|--------|-----------|")

        for split_name, records in [('train', train_records), ('dev', dev_records), ('test', test_records)]:
            dist = Counter(r.get('spatial_relation_type', 'unknown') for r in records)
            split_total = len(records)
            lines.append(f"| {split_name:6s} | "
                        f"{dist['directional']:5d} ({dist['directional']/split_total*100:.1f}%) | "
                        f"{dist['topological']:5d} ({dist['topological']/split_total*100:.1f}%) | "
                        f"{dist['metric']:5d} ({dist['metric']/split_total*100:.1f}%) | "
                        f"{dist['composite']:5d} ({dist['composite']/split_total*100:.1f}%) |")
        lines.append("")

        # 难度分布
        lines.append("## 难度分布")
        lines.append("")
        lines.append("| 数据集 | easy | medium | hard |")
        lines.append("|--------|------|--------|------|")

        for split_name, records in [('train', train_records), ('dev', dev_records), ('test', test_records)]:
            dist = Counter(r.get('difficulty', 'unknown') for r in records)
            split_total = len(records)
            lines.append(f"| {split_name:6s} | "
                        f"{dist['easy']:5d} ({dist['easy']/split_total*100:.1f}%) | "
                        f"{dist['medium']:5d} ({dist['medium']/split_total*100:.1f}%) | "
                        f"{dist['hard']:5d} ({dist['hard']/split_total*100:.1f}%) |")
        lines.append("")

        # 详细分布
        lines.append("## 详细分布（关系类型 × 难度）")
        lines.append("")

        for split_name, records in [('train', train_records), ('dev', dev_records), ('test', test_records)]:
            lines.append(f"### {split_name.upper()}")
            lines.append("")
            lines.append("| 关系类型 | easy | medium | hard | 小计 |")
            lines.append("|----------|------|--------|------|------|")

            for relation_type in ['directional', 'topological', 'metric', 'composite']:
                dist_by_diff = defaultdict(int)
                for r in records:
                    if r.get('spatial_relation_type') == relation_type:
                        dist_by_diff[r.get('difficulty', 'unknown')] += 1

                total = sum(dist_by_diff.values())
                lines.append(f"| {relation_type:12s} | "
                            f"{dist_by_diff['easy']:5d} | "
                            f"{dist_by_diff['medium']:5d} | "
                            f"{dist_by_diff['hard']:5d} | "
                            f"{total:5d} |")
            lines.append("")

        # 验证结果
        lines.append("## 验证结果")
        lines.append("")

        if validation['is_valid']:
            lines.append("✓ **划分验证通过**")
        else:
            lines.append("✗ **划分验证失败**")

        lines.append("")

        if validation['entity_pair_overlap']:
            lines.append("### 实体对互斥检查")
            lines.append("")
            for issue in validation['issues']:
                if '实体对' in issue:
                    lines.append(f"- {issue}")
            lines.append("")
        else:
            lines.append("### 实体对互斥检查")
            lines.append("")
            lines.append("✓ train/dev/test中的实体对完全互斥")
            lines.append("")

        lines.append("### 分布相似性检查")
        lines.append("")
        lines.append("| 数据集 | KS统计量 | 评价 |")
        lines.append("|--------|----------|------|")

        for split_name, ks_value in validation['distribution_similarity'].items():
            if ks_value < 0.1:
                status = "优秀"
            elif ks_value < 0.2:
                status = "良好"
            else:
                status = "需改进"
            lines.append(f"| {split_name:6s} | {ks_value:.4f} | {status} |")
        lines.append("")

        # 警告和问题
        if validation['warnings']:
            lines.append("### 警告")
            lines.append("")
            for warning in validation['warnings']:
                lines.append(f"- ! {warning}")
            lines.append("")

        if validation['issues']:
            lines.append("### 问题")
            lines.append("")
            for issue in validation['issues']:
                lines.append(f"- ✗ {issue}")
            lines.append("")

        return "\n".join(lines)

    def save_report(self, report: str, output_path: str):
        """
        保存报告

        Args:
            report: 报告内容
            output_path: 输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"[OK] 报告已保存到: {output_path}")


# ================================
# 命令行接口
# ================================

def parse_ratio(ratio_str: str) -> Tuple[float, float, float]:
    """
    解析比例字符串

    Args:
        ratio_str: 比例字符串，格式为 "0.8:0.1:0.1"

    Returns:
        (train_ratio, dev_ratio, test_ratio)
    """
    parts = ratio_str.split(':')
    if len(parts) != 3:
        raise ValueError(f"比例格式错误: {ratio_str}，应为 'train:dev:test'")

    ratios = tuple(float(p.strip()) for p in parts)
    if abs(sum(ratios) - 1.0) > 0.001:
        raise ValueError(f"比例之和必须等于1: {sum(ratios)}")

    return ratios


def main():
    """命令行接口"""
    parser = argparse.ArgumentParser(
        description='GeoKD-SR 分层数据集划分工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法（默认10000条，8:1:1划分）
  python split_dataset_stratified.py --input data/geosr_chain/all_data.jsonl --output data/geosr_chain/

  # 指定总记录数和划分比例
  python split_dataset_stratified.py --input data/geosr_chain/all_data.jsonl --output data/geosr_chain/ --total 8000 --ratio 0.7:0.15:0.15

  # 使用自定义随机种子
  python split_dataset_stratified.py --input data/geosr_chain/all_data.jsonl --output data/geosr_chain/ --seed 123
        """
    )

    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='输入jsonl文件路径'
    )

    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='输出目录'
    )

    parser.add_argument(
        '--total',
        type=int,
        default=10000,
        help='目标总记录数（默认10000）'
    )

    parser.add_argument(
        '--ratio',
        type=str,
        default='0.8:0.1:0.1',
        help='划分比例，格式为train:dev:test（默认0.8:0.1:0.1）'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='随机种子（默认42）'
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("GeoKD-SR 分层数据集划分工具")
    print("="*80)

    # 解析比例
    try:
        train_ratio, dev_ratio, test_ratio = parse_ratio(args.ratio)
        split_ratio = {
            'train': train_ratio,
            'dev': dev_ratio,
            'test': test_ratio,
        }
    except ValueError as e:
        print(f"[错误] {e}")
        sys.exit(1)

    # 创建划分器
    splitter = StratifiedDatasetSplitter(seed=args.seed)

    # 加载数据
    print(f"\n[0/5] 加载数据...")
    print(f"  输入文件: {args.input}")
    print(f"  目标总数: {args.total}")
    print(f"  划分比例: train={train_ratio:.1%}, dev={dev_ratio:.1%}, test={test_ratio:.1%}")

    try:
        records = splitter.load_records(args.input)
    except Exception as e:
        print(f"[错误] {e}")
        sys.exit(1)

    if len(records) < args.total:
        print(f"[警告] 输入数据只有 {len(records)} 条，少于目标 {args.total} 条")
        print(f"[警告] 将使用全部数据")
        args.total = len(records)

    # 执行划分
    try:
        train_records, dev_records, test_records = splitter.stratified_split_with_entity_pairs(
            records,
            total=args.total,
            split_ratio=split_ratio
        )
    except Exception as e:
        print(f"[错误] 划分失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存数据集
    print(f"\n[保存] 保存数据集...")
    train_path = output_dir / 'train.jsonl'
    dev_path = output_dir / 'dev.jsonl'
    test_path = output_dir / 'test.jsonl'

    splitter.save_records(train_records, str(train_path))
    splitter.save_records(dev_records, str(dev_path))
    splitter.save_records(test_records, str(test_path))

    # 验证
    validation = splitter.validate_split(train_records, dev_records, test_records)

    # 生成报告
    print(f"\n[报告] 生成划分报告...")
    report = splitter.generate_report(train_records, dev_records, test_records, validation)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = output_dir / f'split_report_{timestamp}.md'
    splitter.save_report(report, str(report_path))

    # 总结
    print("\n" + "="*80)
    print("[完成] 数据集分层划分完成！")
    print("="*80)

    if validation['is_valid']:
        print(f"\n✓ 划分验证通过")
    else:
        print(f"\n✗ 划分验证失败，请查看报告了解详情")

    print(f"\n输出文件:")
    print(f"  训练集: {train_path} ({len(train_records)} 条)")
    print(f"  验证集: {dev_path} ({len(dev_records)} 条)")
    print(f"  测试集: {test_path} ({len(test_records)} 条)")
    print(f"  报告: {report_path}")
    print()


if __name__ == '__main__':
    main()
