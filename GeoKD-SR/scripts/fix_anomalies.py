#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 数据异常修复脚本

修复项目：
1. invalid_entity_type: 映射非法实体类型到合法类型
2. chain_length_error: 修复推理链长度

使用方法：
    python scripts/fix_anomalies.py --input data/final/final_1_cleaned.jsonl --output data/final/final_1_fixed.jsonl
"""

import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict


class AnomalyFixer:
    """数据异常修复器"""

    # 实体类型映射
    TYPE_MAPPING = {
        'country': 'region',
        'historical': 'landmark',
        'district': 'city',
        'town': 'city',
        'village': 'city',
        'county': 'city',
        'state': 'region',
        'prefecture': 'city',
        'municipality': 'province',  # 直辖市映射为province
        'autonomous_region': 'province',  # 自治区映射为province
        'special_administrative_region': 'province',  # 特别行政区映射为province
        'scenic': 'landmark',  # 景区映射为landmark
        'park': 'landmark',  # 公园映射为landmark
        'building': 'landmark',  # 建筑映射为landmark
        'location': 'region',  # 位置映射为region
        'place': 'region'  # 地点映射为region
    }

    def __init__(self, input_file: str, output_file: str):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)

        self.stats = {
            'total_records': 0,
            'fixed_records': 0,
            'type_fixes': defaultdict(int),
            'chain_fixes': 0,
            'removed_records': 0
        }

        # 设置日志
        self._setup_logging()

    def _setup_logging(self):
        """设置日志"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'fix_anomalies.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def fix_all(self):
        """执行所有修复"""
        self.logger.info(f"开始修复: {self.input_file}")

        records = []
        with open(self.input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

        self.stats['total_records'] = len(records)
        self.logger.info(f"加载 {len(records)} 条记录")

        fixed_records = []
        for record in records:
            fixed_record, was_fixed = self._fix_record(record)
            if fixed_record:
                fixed_records.append(fixed_record)
                if was_fixed:
                    self.stats['fixed_records'] += 1
            else:
                self.stats['removed_records'] += 1

        # 保存修复后的数据
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, 'w', encoding='utf-8') as f:
            for record in fixed_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        self.logger.info(f"修复完成: {self.output_file}")
        self._print_summary()

    def _fix_record(self, record: Dict) -> tuple:
        """修复单条记录"""
        was_fixed = False

        # 1. 修复实体类型
        for entity in record.get('entities', []):
            old_type = entity.get('type')
            if old_type in self.TYPE_MAPPING:
                new_type = self.TYPE_MAPPING[old_type]
                entity['type'] = new_type
                self.stats['type_fixes'][old_type] += 1
                self.logger.debug(f"修复实体类型: {entity.get('name')} {old_type} -> {new_type}")
                was_fixed = True

        # 2. 检查推理链长度
        chain = record.get('reasoning_chain', [])
        if isinstance(chain, list) and len(chain) != 5:
            # 尝试修复：只保留前5个步骤
            if len(chain) > 5:
                record['reasoning_chain'] = chain[:5]
                self.stats['chain_fixes'] += 1
                self.logger.info(f"修复推理链长度: {record.get('id')} {len(chain)} -> 5")
                was_fixed = True
            elif len(chain) < 5:
                # 推理链太短，删除该记录
                self.logger.warning(f"删除记录（推理链太短）: {record.get('id')} 长度={len(chain)}")
                return None, True

        return record, was_fixed

    def _print_summary(self):
        """打印修复摘要"""
        print("\n" + "=" * 60)
        print("GeoKD-SR 数据异常修复报告")
        print("=" * 60)
        print(f"输入文件: {self.input_file}")
        print(f"输出文件: {self.output_file}")
        print(f"\n总记录数: {self.stats['total_records']}")
        print(f"修复记录数: {self.stats['fixed_records']}")
        print(f"删除记录数: {self.stats['removed_records']}")

        print(f"\n实体类型修复统计:")
        for old_type, count in sorted(self.stats['type_fixes'].items()):
            new_type = self.TYPE_MAPPING.get(old_type, 'unknown')
            print(f"  {old_type} -> {new_type}: {count} 条")

        print(f"\n推理链修复: {self.stats['chain_fixes']} 条")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 数据异常修复脚本')
    parser.add_argument(
        '--input', '-i',
        default='D:/30_keyan/GeoKD-SR/data/final/final_1_cleaned.jsonl',
        help='输入文件路径'
    )
    parser.add_argument(
        '--output', '-o',
        default='D:/30_keyan/GeoKD-SR/data/final/final_1_fixed.jsonl',
        help='输出文件路径'
    )

    args = parser.parse_args()

    fixer = AnomalyFixer(args.input, args.output)
    fixer.fix_all()

    return 0


if __name__ == '__main__':
    exit(main())
