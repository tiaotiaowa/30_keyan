#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 创建split版本脚本

功能：
1. 从v3目录读取train/dev/test.jsonl
2. 生成with_coords版本（保留坐标）
3. 生成without_coords版本（移除坐标）
4. 每个split单独保存为train.jsonl, dev.jsonl, test.jsonl

使用方法：
    python scripts/create_split_versions.py --input data/geosr_chain/v3/ --output data/geosr_chain/v3/
"""

import json
import argparse
import os
import re
from pathlib import Path
from typing import Dict, List, Any


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """加载JSONL文件"""
    records = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"警告: JSON解析失败: {e}")
    return records


def save_jsonl(records: List[Dict[str, Any]], output_path: str) -> None:
    """保存为JSONL文件"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def has_coords_in_question(question: str) -> bool:
    """检测问题中是否包含坐标信息"""
    patterns = [
        r'\d+\.?\d*\s*[°度]\s*[NSEW北南东西]',
        r'[北南]纬\s*\d+\.?\d*',
        r'[东西]经\s*\d+\.?\d*',
        r'[NS]\s*\d+\.?\d*[°度]?',
        r'[EW]\s*\d+\.?\d*[°度]?',
        r'\(\s*\d+\.?\d*\s*[°]?\s*,\s*\d+\.?\d*\s*[°]?\s*\)',
        r'\d+\.?\d*[°度]\s*[NS北南]',
        r'\d+\.?\d*[°度]\s*[EW东西]',
    ]
    return any(re.search(p, question) for p in patterns)


def remove_coords_from_question(question: str) -> str:
    """从问题中移除坐标表述"""
    result = question
    patterns = [
        r'已知[^。]+?位于[^。]+?[度°][^。]+?，',
        r'已知[^。]+?地理坐标[^。]+?，',
        r'已知[^。]+?纬度[^。]+?经度[^。]+?，',
        r'^[^(]*?\([^)]*?\)[^。，]*?[，。]?',
    ]
    for pattern in patterns:
        result = re.sub(pattern, '', result)
    result = re.sub(r'^[，。]+', '', result)
    return result


def fix_prompt_bias(text: str) -> str:
    """修正提示词中的偏差表述"""
    corrections = [
        (r'请判断(.+?)是否', r'\1是否'),
        (r'请逐步推理[。，]?', ''),
        (r'从拓扑关系来看，?', ''),
        (r'从空间关系来看，?', ''),
        (r'从[^，。]{1,10}关系来看，?', ''),
        (r'请估算', '估算'),
        (r'请问', ''),
        (r'，,+', ','),
        (r'。。+', '。'),
        (r'^[，。]+', ''),
        (r'[，。]+$', ''),
    ]
    result = text
    for pattern, replacement in corrections:
        result = re.sub(pattern, replacement, result)
    result = re.sub(r'\s+', '', result)
    return result


def add_coords_to_question(question: str, entities: List[Dict]) -> str:
    """为问题添加坐标信息"""
    entities_with_coords = [e for e in entities if 'coords' in e and e['coords']]
    if len(entities_with_coords) < 2:
        return question
    entity1 = entities_with_coords[0]
    entity2 = entities_with_coords[1]
    coords1 = entity1['coords']
    coords2 = entity2['coords']
    prefix = f"已知{entity1['name']}位于北纬{coords1[1]}度、东经{coords1[0]}度，{entity2['name']}位于北纬{coords2[1]}度、东经{coords2[0]}度。"
    return prefix + question


def process_with_coords(record: Dict[str, Any]) -> Dict[str, Any]:
    """处理with_coords版本"""
    result = record.copy()
    result['question'] = fix_prompt_bias(record.get('question', ''))
    if not has_coords_in_question(result['question']):
        entities = record.get('entities', [])
        if entities and len(entities) >= 2:
            result['question'] = add_coords_to_question(result['question'], entities)
    return result


def process_without_coords(record: Dict[str, Any]) -> Dict[str, Any]:
    """处理without_coords版本"""
    result = record.copy()
    result['question'] = fix_prompt_bias(record.get('question', ''))
    if has_coords_in_question(result['question']):
        result['question'] = remove_coords_from_question(result['question'])
    # 移除entities中的coords字段
    if 'entities' in result:
        result['entities'] = [
            {k: v for k, v in e.items() if k != 'coords'}
            for e in result['entities']
        ]
    return result


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 创建split版本脚本')
    parser.add_argument('--input', '-i', default='D:/30_keyan/GeoKD-SR/data/geosr_chain/v3',
                        help='输入目录（包含train.jsonl, dev.jsonl, test.jsonl）')
    parser.add_argument('--output', '-o', default='D:/30_keyan/GeoKD-SR/data/geosr_chain/v3',
                        help='输出目录')
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    # 创建输出目录
    with_coords_dir = output_dir / 'with_coords'
    without_coords_dir = output_dir / 'without_coords'
    with_coords_dir.mkdir(parents=True, exist_ok=True)
    without_coords_dir.mkdir(parents=True, exist_ok=True)

    # 处理每个split
    for split_name in ['train', 'dev', 'test']:
        input_file = input_dir / f'{split_name}.jsonl'
        if not input_file.exists():
            print(f"警告: {input_file} 不存在，跳过")
            continue

        print(f"\n处理 {split_name}...")
        records = load_jsonl(str(input_file))
        print(f"  加载 {len(records)} 条记录")

        # 生成with_coords版本
        with_coords_records = [process_with_coords(r) for r in records]
        with_coords_file = with_coords_dir / f'{split_name}.jsonl'
        save_jsonl(with_coords_records, str(with_coords_file))
        print(f"  with_coords: {len(with_coords_records)} 条 -> {with_coords_file}")

        # 生成without_coords版本
        without_coords_records = [process_without_coords(r) for r in records]
        without_coords_file = without_coords_dir / f'{split_name}.jsonl'
        save_jsonl(without_coords_records, str(without_coords_file))
        print(f"  without_coords: {len(without_coords_records)} 条 -> {without_coords_file}")

    print("\n完成!")
    return 0


if __name__ == '__main__':
    exit(main())
