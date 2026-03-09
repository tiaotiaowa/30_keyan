#!/usr/bin/env python3
"""
GeoKD-SR 数据集版本生成脚本

功能：
1. 修正提示词偏差
2. 生成 with_coords 版本：确保问题中包含坐标信息
3. 生成 without_coords 版本：移除问题中的坐标信息
"""

import argparse
import json
import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional


def fix_prompt_bias(text: str) -> str:
    """
    修正提示词中的偏差表述

    Args:
        text: 原始文本

    Returns:
        修正后的文本
    """
    # 定义修正规则列表
    corrections = [
        # "请判断XX是否..." -> "XX是否..."
        (r'请判断(.+?)是否', r'\1是否'),

        # "请逐步推理" -> 删除
        (r'请逐步推理[。，]?', ''),

        # "从拓扑关系来看，" -> 删除
        (r'从拓扑关系来看，?', ''),

        # "从空间关系来看，" -> 删除
        (r'从空间关系来看，?', ''),

        # "从XX关系来看，" -> 删除 (通用模式)
        (r'从[^，。]{1,10}关系来看，?', ''),

        # "请估算" -> "估算"
        (r'请估算', '估算'),

        # "请问" -> 删除
        (r'请问', ''),

        # 额外清理：删除可能产生的多余标点
        (r'，,+', ','),
        (r'。。+', '。'),
        (r'^[，。]+', ''),  # 开头的多余标点
        (r'[，。]+$', ''),  # 结尾的多余标点
    ]

    result = text
    for pattern, replacement in corrections:
        result = re.sub(pattern, replacement, result)

    # 清理可能产生的空格问题
    result = re.sub(r'\s+', '', result)  # 删除所有空格

    return result


def has_coords_in_question(question: str) -> bool:
    """
    检测问题中是否包含坐标信息

    Args:
        question: 问题文本

    Returns:
        True 如果问题中包含坐标信息
    """
    patterns = [
        # 度数格式：25.04°N 或 25.04度
        r'\d+\.?\d*\s*[°度]\s*[NSEW北南东西]',

        # 北纬/南纬 + 数字
        r'[北南]纬\s*\d+\.?\d*',
        r'[北南]纬\s*\d+\.?\d*[°度]',

        # 东经/西经 + 数字
        r'[东西]经\s*\d+\.?\d*',
        r'[东西]经\s*\d+\.?\d*[°度]',

        # N/E/S/W + 数字
        r'[NS]\s*\d+\.?\d*[°度]?',
        r'[EW]\s*\d+\.?\d*[°度]?',
        r'[NS]\s*\d+\.?\d*°',
        r'[EW]\s*\d+\.?\d*°',

        # 坐标对格式：(x, y) 或 (x°, y°)
        r'\(\s*\d+\.?\d*\s*[°]?\s*,\s*\d+\.?\d*\s*[°]?\s*\)',

        # 纬度经度格式：30.5928°N，114.3055°E
        r'\d+\.?\d*[°度]\s*[NS北南]',
        r'\d+\.?\d*[°度]\s*[EW东西]',
    ]

    return any(re.search(p, question) for p in patterns)


def remove_coords_from_question(question: str) -> str:
    """
    从问题中移除坐标表述

    Args:
        question: 原始问题

    Returns:
        移除坐标后的问题
    """
    result = question

    # 移除 "已知XX位于北纬X度、东经Y度，" 这类前缀
    patterns = [
        # 匹配 "已知...位于...度...，" 到下一个问题
        r'已知[^。]+?位于[^。]+?[度°][^。]+?，',

        # 匹配 "已知...的地理坐标约为(...)，"
        r'已知[^。]+?地理坐标[^。]+?，',

        # 匹配 "已知...位于纬度...经度...，"
        r'已知[^。]+?纬度[^。]+?经度[^。]+?，',

        # 匹配坐标对在开头的模式
        r'^[^(]*?\([^)]*?\)[^。，]*?[，。]?',
    ]

    for pattern in patterns:
        result = re.sub(pattern, '', result)

    # 清理开头的标点
    result = re.sub(r'^[，。]+', '', result)

    return result


def add_coords_to_question(question: str, entities: List[Dict[str, Any]]) -> str:
    """
    为问题添加坐标信息

    Args:
        question: 原始问题
        entities: 实体列表

    Returns:
        添加坐标后的问题
    """
    # 过滤出有坐标的实体
    entities_with_coords = [e for e in entities if 'coords' in e and e['coords']]

    if len(entities_with_coords) < 2:
        # 如果实体少于2个或有坐标的实体少于2个，返回原问题
        return question

    # 取前两个有坐标的实体
    entity1 = entities_with_coords[0]
    entity2 = entities_with_coords[1]

    # 获取坐标（注意：数据中coords格式可能是[lon, lat]或[lat, lon]）
    # 根据数据样本，格式是[lon, lat]
    coords1 = entity1['coords']
    coords2 = entity2['coords']

    # 构建坐标前缀
    # 格式: "已知{entity1}位于北纬{lat1}度、东经{lon1}度，{entity2}位于北纬{lat2}度、东经{lon2}度。{原问题}"
    prefix = f"已知{entity1['name']}位于北纬{coords1[1]}度、东经{coords1[0]}度，{entity2['name']}位于北纬{coords2[1]}度、东经{coords2[0]}度。"

    return prefix + question


def process_with_coords(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 with_coords 模式：确保问题中包含坐标

    Args:
        record: 原始数据记录

    Returns:
        处理后的记录
    """
    result = record.copy()

    # 修正提示词偏差
    result['question'] = fix_prompt_bias(record['question'])

    # 如果问题中没有坐标，添加坐标
    if not has_coords_in_question(result['question']):
        entities = record.get('entities', [])
        if entities and len(entities) >= 2:
            result['question'] = add_coords_to_question(result['question'], entities)

    return result


def process_without_coords(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 without_coords 模式：移除问题中的坐标

    Args:
        record: 原始数据记录

    Returns:
        处理后的记录
    """
    result = record.copy()

    # 修正提示词偏差
    result['question'] = fix_prompt_bias(record['question'])

    # 如果问题中有坐标，移除坐标
    if has_coords_in_question(result['question']):
        result['question'] = remove_coords_from_question(result['question'])

    return result


def load_jsonl(input_path: str) -> List[Dict[str, Any]]:
    """
    加载 JSONL 文件

    Args:
        input_path: 输入文件路径

    Returns:
        数据记录列表
    """
    records = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"警告: 无法解析JSON行: {e}")
    return records


def save_jsonl(records: List[Dict[str, Any]], output_path: str) -> None:
    """
    保存为 JSONL 文件

    Args:
        records: 数据记录列表
        output_path: 输出文件路径
    """
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 数据集版本生成脚本')
    parser.add_argument('--input', type=str, required=True, help='输入文件路径')
    parser.add_argument('--mode', type=str, required=True, choices=['with_coords', 'without_coords'],
                        help='处理模式: with_coords 或 without_coords')
    parser.add_argument('--output', type=str, required=True, help='输出目录')

    args = parser.parse_args()

    print(f"加载数据: {args.input}")
    records = load_jsonl(args.input)
    print(f"加载了 {len(records)} 条记录")

    # 根据模式处理数据
    if args.mode == 'with_coords':
        print("处理模式: with_coords (添加坐标)")
        processed_records = [process_with_coords(r) for r in records]

        # 统计
        added_coords = sum(1 for r, p in zip(records, processed_records)
                          if not has_coords_in_question(r['question']) and has_coords_in_question(p['question']))
        print(f"添加了坐标的记录: {added_coords}")

        output_file = os.path.join(args.output, 'geosr_chain_with_coords.jsonl')

    else:  # without_coords
        print("处理模式: without_coords (移除坐标)")
        processed_records = [process_without_coords(r) for r in records]

        # 统计
        removed_coords = sum(1 for r, p in zip(records, processed_records)
                           if has_coords_in_question(r['question']) and not has_coords_in_question(p['question']))
        print(f"移除了坐标的记录: {removed_coords}")

        output_file = os.path.join(args.output, 'geosr_chain_without_coords.jsonl')

    # 保存结果
    print(f"保存到: {output_file}")
    save_jsonl(processed_records, output_file)
    print(f"完成! 共处理 {len(processed_records)} 条记录")


if __name__ == '__main__':
    main()
