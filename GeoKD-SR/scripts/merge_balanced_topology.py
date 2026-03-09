#!/usr/bin/env python3
"""
合并原始数据和补充数据，创建平衡的拓扑子类型数据集。

功能：
1. 读取 raw_merged.jsonl
2. 过滤出 topological 类型的数据
3. 处理非标准拓扑子类型
4. 下采样确保平衡分布
5. 合并补充数据
6. 输出平衡后的数据集
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 拓扑子类型映射：将非标准类型映射到标准类型
TOPOLOGY_SUBTYPE_MAPPING = {
    'touch': 'adjacent',
    'inside': 'within',
    'crosses': 'overlap',
    'covers': 'contains',
    'coveredby': 'within',
    'intersects': 'overlap',
    'equals': 'overlap'
}

# 标准拓扑子类型
STANDARD_TOPOLOGY_TYPES = ['disjoint', 'overlap', 'contains', 'adjacent', 'within']


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """加载 JSONL 文件"""
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"跳过无效行: {e}")
        logger.info(f"从 {file_path} 加载了 {len(data)} 条数据")
    except FileNotFoundError:
        logger.warning(f"文件不存在: {file_path}")
    return data


def normalize_topology_subtype(subtype: str) -> str:
    """标准化拓扑子类型"""
    subtype_lower = subtype.lower().strip()
    return TOPOLOGY_SUBTYPE_MAPPING.get(subtype_lower, subtype_lower)


def is_valid_topology_subtype(subtype: str) -> bool:
    """检查是否为有效的标准拓扑子类型"""
    return normalize_topology_subtype(subtype) in STANDARD_TOPOLOGY_TYPES


def split_topology_data(data: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """分离拓扑和非拓扑数据"""
    topology_data = []
    non_topology_data = []

    for item in data:
        # 检查 spatial_relation_type 字段（兼容旧版 relation_type）
        relation_type = item.get('spatial_relation_type', item.get('relation_type', ''))
        if relation_type.lower() == 'topological':
            # 标准化子类型（兼容 topology_subtype 和 relation_subtype）
            subtype_key = 'topology_subtype' if 'topology_subtype' in item else 'relation_subtype'
            original_subtype = item.get(subtype_key, '')
            normalized_subtype = normalize_topology_subtype(original_subtype)
            item['topology_subtype'] = normalized_subtype
            # 保留原始子类型信息
            if normalized_subtype != original_subtype:
                item['original_subtype'] = original_subtype

            # 只保留标准拓扑子类型
            if is_valid_topology_subtype(normalized_subtype):
                topology_data.append(item)
            else:
                logger.debug(f"跳过非标准拓扑子类型: {original_subtype}")
        else:
            non_topology_data.append(item)

    logger.info(f"拓扑数据: {len(topology_data)} 条, 非拓扑数据: {len(non_topology_data)} 条")
    return topology_data, non_topology_data


def downsample_topology_data(topology_data: List[Dict[str, Any]], target_per_type: int, random_seed: int = 42) -> Dict[str, List[Dict[str, Any]]]:
    """下采样拓扑数据，确保每个子类型不超过目标数量"""
    # 按子类型分组
    type_to_data = defaultdict(list)
    for item in topology_data:
        # 兼容两种字段名
        subtype = item.get('topology_subtype') or item.get('relation_subtype', 'unknown')
        type_to_data[subtype].append(item)

    # 打印原始分布
    logger.info("原始拓扑子类型分布:")
    for subtype in STANDARD_TOPOLOGY_TYPES:
        count = len(type_to_data.get(subtype, []))
        logger.info(f"  {subtype}: {count} 条")

    # 下采样
    random.seed(random_seed)
    sampled_data = {}

    for subtype in STANDARD_TOPOLOGY_TYPES:
        data_list = type_to_data.get(subtype, [])
        if len(data_list) > target_per_type:
            sampled_data[subtype] = random.sample(data_list, target_per_type)
            logger.info(f"{subtype}: 下采样从 {len(data_list)} 到 {target_per_type}")
        else:
            sampled_data[subtype] = data_list
            logger.info(f"{subtype}: 保留全部 {len(data_list)} 条 (目标: {target_per_type})")

    return sampled_data


def merge_supplement_data(sampled_data: Dict[str, List[Dict[str, Any]]],
                          supplement_data: List[Dict[str, Any]],
                          target_per_type: int) -> Dict[str, List[Dict[str, Any]]]:
    """合并补充数据，确保每个子类型达到目标数量"""
    if not supplement_data:
        logger.info("没有补充数据，跳过合并步骤")
        return sampled_data

    # 按子类型分组补充数据
    supplement_by_type = defaultdict(list)
    for item in supplement_data:
        subtype = item.get('relation_subtype', '')
        if subtype in STANDARD_TOPOLOGY_TYPES:
            supplement_by_type[subtype].append(item)

    logger.info("补充数据分布:")
    for subtype in STANDARD_TOPOLOGY_TYPES:
        count = len(supplement_by_type.get(subtype, []))
        logger.info(f"  {subtype}: {count} 条")

    # 合并数据
    merged_data = {}
    for subtype in STANDARD_TOPOLOGY_TYPES:
        current = list(sampled_data.get(subtype, []))
        supplement = supplement_by_type.get(subtype, [])
        needed = target_per_type - len(current)

        if needed > 0 and supplement:
            # 随机选择补充数据
            take = min(needed, len(supplement))
            current.extend(random.sample(supplement, take))
            logger.info(f"{subtype}: 添加了 {take} 条补充数据 (当前: {len(current)})")

        merged_data[subtype] = current

    return merged_data


def save_jsonl(data: List[Dict[str, Any]], file_path: str):
    """保存数据到 JSONL 文件"""
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    logger.info(f"已保存 {len(data)} 条数据到 {file_path}")


def generate_report(original_counts: Dict[str, int],
                    final_counts: Dict[str, int],
                    target_per_type: int,
                    supplement_counts: Dict[str, int],
                    report_path: str):
    """生成平衡报告"""
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 拓扑子类型平衡报告\n\n")
        f.write(f"生成时间: {Path(__file__).stat().st_mtime}\n\n")

        f.write("## 配置\n\n")
        f.write(f"- 每个子类型目标数量: {target_per_type}\n")
        f.write(f"- 标准拓扑子类型: {', '.join(STANDARD_TOPOLOGY_TYPES)}\n\n")

        f.write("## 原始分布\n\n")
        f.write("| 子类型 | 数量 |\n")
        f.write("|--------|------|\n")
        for subtype in STANDARD_TOPOLOGY_TYPES:
            count = original_counts.get(subtype, 0)
            f.write(f"| {subtype} | {count} |\n")

        f.write("\n## 补充数据分布\n\n")
        f.write("| 子类型 | 数量 |\n")
        f.write("|--------|------|\n")
        for subtype in STANDARD_TOPOLOGY_TYPES:
            count = supplement_counts.get(subtype, 0)
            f.write(f"| {subtype} | {count} |\n")

        f.write("\n## 最终分布\n\n")
        f.write("| 子类型 | 数量 | 状态 |\n")
        f.write("|--------|------|------|\n")
        for subtype in STANDARD_TOPOLOGY_TYPES:
            count = final_counts.get(subtype, 0)
            status = "✓" if count == target_per_type else "✗"
            f.write(f"| {subtype} | {count} | {status} |\n")

        f.write("\n## 统计摘要\n\n")
        total_original = sum(original_counts.values())
        total_final = sum(final_counts.values())
        f.write(f"- 原始拓扑数据总数: {total_original}\n")
        f.write(f"- 最终拓扑数据总数: {total_final}\n")
        f.write(f"- 目标总数: {target_per_type * len(STANDARD_TOPOLOGY_TYPES)}\n")
        f.write(f"- 达成率: {total_final / (target_per_type * len(STANDARD_TOPOLOGY_TYPES)) * 100:.1f}%\n")

        f.write("\n## 下采样操作\n\n")
        for subtype in STANDARD_TOPOLOGY_TYPES:
            original = original_counts.get(subtype, 0)
            final = final_counts.get(subtype, 0)
            if original > final:
                removed = original - final
                f.write(f"- {subtype}: 移除了 {removed} 条 ({removed/original*100:.1f}%)\n")
            elif original < final:
                added = final - original
                f.write(f"- {subtype}: 添加了 {added} 条补充数据\n")
            else:
                f.write(f"- {subtype}: 无变化\n")

    logger.info(f"报告已生成: {report_path}")


def main():
    parser = argparse.ArgumentParser(description='合并和平衡拓扑子类型数据')
    parser.add_argument('--input', required=True, help='原始合并数据文件路径')
    parser.add_argument('--supplement', default='', help='补充数据文件路径（可选）')
    parser.add_argument('--output', required=True, help='输出文件路径')
    parser.add_argument('--target-per-type', type=int, default=600, help='每个子类型的目标数量')
    parser.add_argument('--report', default='outputs/topology_balance_report_v2.md', help='报告输出路径')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')

    args = parser.parse_args()

    # 加载原始数据
    logger.info(f"加载原始数据: {args.input}")
    raw_data = load_jsonl(args.input)

    # 分离拓扑和非拓扑数据
    topology_data, non_topology_data = split_topology_data(raw_data)

    # 保存原始分布统计
    original_counts = {}
    for item in topology_data:
        subtype = item.get('relation_subtype', 'unknown')
        original_counts[subtype] = original_counts.get(subtype, 0) + 1

    # 下采样
    sampled_data = downsample_topology_data(topology_data, args.target_per_type, args.seed)

    # 加载补充数据
    supplement_counts = {subtype: 0 for subtype in STANDARD_TOPOLOGY_TYPES}
    if args.supplement and Path(args.supplement).exists():
        logger.info(f"加载补充数据: {args.supplement}")
        supplement_data = load_jsonl(args.supplement)

        # 统计补充数据
        for item in supplement_data:
            subtype = item.get('relation_subtype', '')
            if subtype in STANDARD_TOPOLOGY_TYPES:
                supplement_counts[subtype] += 1

        # 合并补充数据
        merged_data = merge_supplement_data(sampled_data, supplement_data, args.target_per_type)
    else:
        logger.info("没有补充数据或文件不存在")
        merged_data = sampled_data

    # 展平数据
    final_topology_data = []
    for subtype in STANDARD_TOPOLOGY_TYPES:
        final_topology_data.extend(merged_data.get(subtype, []))

    # 合并非拓扑数据
    final_data = final_topology_data + non_topology_data

    # 保存结果
    save_jsonl(final_data, args.output)

    # 生成报告
    final_counts = {}
    for item in final_topology_data:
        subtype = item.get('relation_subtype', 'unknown')
        final_counts[subtype] = final_counts.get(subtype, 0) + 1

    generate_report(original_counts, final_counts, args.target_per_type, supplement_counts, args.report)

    logger.info("=" * 50)
    logger.info("处理完成!")
    logger.info(f"输出文件: {args.output}")
    logger.info(f"报告文件: {args.report}")
    logger.info(f"总数据量: {len(final_data)} (拓扑: {len(final_topology_data)}, 非拓扑: {len(non_topology_data)})")
    logger.info("=" * 50)


if __name__ == '__main__':
    main()
