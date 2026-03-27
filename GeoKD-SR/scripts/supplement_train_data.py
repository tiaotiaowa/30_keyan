#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 训练集补充脚本

功能：
1. 从原始数据中补充训练集至8000条
2. 确保补充的实体对与dev/test不重叠
3. 保持空间关系类型分布平衡

使用方法：
    python scripts/supplement_train_data.py --raw data/geosr_chain/raw_merged.jsonl --v3 data/geosr_chain/v3/ --output data/geosr_chain/v3/
"""

import json
import argparse
import os
import random
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import Counter, defaultdict
from datetime import datetime


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
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def get_entity_pair_key(entities: List[Dict]) -> str:
    """获取实体对唯一标识"""
    if not entities or len(entities) < 2:
        return ""
    names = sorted([e.get('name', '') for e in entities[:2]])
    return f"{names[0]}|{names[1]}"


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 训练集补充脚本')
    parser.add_argument('--raw', '-r', default='D:/30_keyan/GeoKD-SR/data/geosr_chain/raw_merged.jsonl',
                        help='原始数据文件路径')
    parser.add_argument('--v3', default='D:/30_keyan/GeoKD-SR/data/geosr_chain/v3/',
                        help='v3目录路径')
    parser.add_argument('--output', '-o', default='D:/30_keyan/GeoKD-SR/data/geosr_chain/v3/',
                        help='输出目录')

    args = parser.parse_args()

    print("="*60)
    print("GeoKD-SR 训练集补充脚本")
    print("="*60)

    # 加载现有数据
    train_path = os.path.join(args.v3, 'train.jsonl')
    dev_path = os.path.join(args.v3, 'dev.jsonl')
    test_path = os.path.join(args.v3, 'test.jsonl')

    train_records = load_jsonl(train_path)
    dev_records = load_jsonl(dev_path)
    test_records = load_jsonl(test_path)

    print(f"现有数据: train={len(train_records)}, dev={len(dev_records)}, test={len(test_records)}")

    # 获取dev/test的实体对（需要排除）
    dev_test_pairs = set()
    for r in dev_records + test_records:
        pair = get_entity_pair_key(r.get('entities', []))
        if pair:
            dev_test_pairs.add(pair)

    print(f"dev/test实体对数: {len(dev_test_pairs)}")

    # 加载原始数据
    raw_records = load_jsonl(args.raw)
    print(f"原始数据: {len(raw_records)} 条")

    # 获取现有train的ID
    train_ids = set(r.get('id') for r in train_records)

    # 筛选可补充的记录（不与dev/test实体对重叠，且不在train中）
    available = []
    for r in raw_records:
        if r.get('id') in train_ids:
            continue
        pair = get_entity_pair_key(r.get('entities', []))
        if pair and pair not in dev_test_pairs:
            available.append(r)

    print(f"可补充记录: {len(available)} 条")

    # 计算需要补充的数量
    target_train = 8000
    need = target_train - len(train_records)
    print(f"需要补充: {need} 条")

    if need <= 0:
        print("训练集已满足目标数量")
        return 0

    # 按空间类型分层补充
    train_spatial = Counter(r.get('spatial_relation_type') for r in train_records)
    print(f"现有train分布: {dict(train_spatial)}")

    # 目标分布
    target_dist = {
        'directional': int(8000 * 0.25),
        'topological': int(8000 * 0.275),
        'metric': int(8000 * 0.275),
        'composite': int(8000 * 0.20)
    }

    # 按类型分组可用记录
    type_available = defaultdict(list)
    for r in available:
        stype = r.get('spatial_relation_type', 'unknown')
        type_available[stype].append(r)

    # 分层补充
    supplement = []
    for stype in ['directional', 'topological', 'metric', 'composite']:
        current = train_spatial.get(stype, 0)
        target = target_dist.get(stype, 0)
        need_type = max(0, target - current)

        type_available_list = type_available.get(stype, [])
        random.shuffle(type_available_list)

        take = min(need_type, len(type_available_list))
        supplement.extend(type_available_list[:take])
        print(f"  {stype}: 补充 {take} 条 (当前{current}, 目标{target})")

    # 如果还不够，从剩余记录中补充
    if len(supplement) < need:
        remaining_need = need - len(supplement)
        used_ids = set(r.get('id') for r in train_records + supplement)
        remaining = [r for r in available if r.get('id') not in used_ids]
        random.shuffle(remaining)
        supplement.extend(remaining[:remaining_need])
        print(f"  额外补充: {min(remaining_need, len(remaining))} 条")

    # 更新train
    train_records.extend(supplement)

    # 更新split字段
    for r in train_records:
        r['split'] = 'train'

    print(f"\n补充后train: {len(train_records)} 条")

    # 保存
    save_jsonl(train_records, os.path.join(args.output, 'train.jsonl'))
    print(f"保存到: {os.path.join(args.output, 'train.jsonl')}")

    # 统计最终分布
    final_spatial = Counter(r.get('spatial_relation_type') for r in train_records)
    print(f"\n最终train分布:")
    for stype in ['directional', 'topological', 'metric', 'composite']:
        count = final_spatial.get(stype, 0)
        target = target_dist.get(stype, 0)
        print(f"  {stype}: {count} (目标: {target})")

    # 验证实体对互斥
    train_pairs = set(get_entity_pair_key(r.get('entities', [])) for r in train_records)
    dev_pairs = set(get_entity_pair_key(r.get('entities', [])) for r in dev_records)
    test_pairs = set(get_entity_pair_key(r.get('entities', [])) for r in test_records)

    train_dev = train_pairs & dev_pairs
    train_test = train_pairs & test_pairs

    print(f"\n实体对互斥验证:")
    print(f"  train/dev重叠: {len(train_dev)}")
    print(f"  train/test重叠: {len(train_test)}")

    if len(train_dev) == 0 and len(train_test) == 0:
        print("  [OK] 实体对互斥验证通过")
    else:
        print("  [WARN] 存在实体对重叠")

    print("\n完成!")
    return 0


if __name__ == '__main__':
    exit(main())
