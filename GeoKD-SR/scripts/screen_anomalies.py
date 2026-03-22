#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 数据异常筛查脚本

筛查项目：
1. 必需字段检查
2. 推理链结构检查（长度=5）
3. 实体数量检查（≥2）
4. 拓扑子类型检查
5. 难度/难度分数检查
6. spatial_tokens检查
7. 答案一致性检查
8. 坐标范围检查（中国范围）
9. 泄露字段检查

使用方法：
    python scripts/screen_anomalies.py --input data/final/final_1_cleaned.jsonl --output reports/anomaly_report.json
"""

import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter
from datetime import datetime
import copy


class AnomalyScreener:
    """数据异常筛查器"""

    # 必需字段
    REQUIRED_FIELDS = [
        'id', 'question', 'answer', 'reasoning_chain', 'entities',
        'spatial_relation_type', 'difficulty', 'difficulty_score',
        'spatial_tokens', 'entity_to_token'
    ]

    # 有效的空间关系类型
    VALID_SPATIAL_TYPES = ['directional', 'topological', 'metric', 'composite']

    # 有效的拓扑子类型
    VALID_TOPOLOGY_SUBTYPES = ['within', 'contains', 'adjacent', 'disjoint', 'overlap']

    # 有效的难度级别
    VALID_DIFFICULTIES = ['easy', 'medium', 'hard']

    # 有效的实体类型
    VALID_ENTITY_TYPES = ['province', 'city', 'landmark', 'river', 'mountain', 'lake', 'region']

    # 有效的推理链步骤名称
    VALID_STEP_NAMES = [
        'entity_identification', 'spatial_relation_extraction',
        'coordinate_retrieval', 'spatial_calculation', 'answer_generation'
    ]

    # 中国坐标范围（大致）
    CHINA_LON_RANGE = (73.0, 135.0)
    CHINA_LAT_RANGE = (18.0, 54.0)

    def __init__(self, input_file: str, output_file: str, verbose: bool = True):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.verbose = verbose

        self.records = []
        self.anomalies = defaultdict(list)  # 按异常类型分组
        self.stats = {
            'total_records': 0,
            'records_with_anomalies': 0,
            'anomaly_counts': defaultdict(int),
            'by_spatial_type': defaultdict(lambda: defaultdict(int)),
            'by_split': defaultdict(lambda: defaultdict(int)),
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
                logging.FileHandler(log_dir / 'screen_anomalies.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_data(self):
        """加载数据"""
        self.logger.info(f"加载数据: {self.input_file}")

        with open(self.input_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    record['_line_num'] = line_num
                    self.records.append(record)
                except json.JSONDecodeError as e:
                    self._add_anomaly('json_parse_error', line_num, {
                        'error': str(e),
                        'line_preview': line[:100]
                    })

        self.stats['total_records'] = len(self.records)
        self.logger.info(f"加载完成: {len(self.records)} 条记录")

    def _add_anomaly(self, anomaly_type: str, line_num: int, details: Dict):
        """添加异常记录"""
        anomaly = {
            'line': line_num,
            'type': anomaly_type,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.anomalies[anomaly_type].append(anomaly)
        self.stats['anomaly_counts'][anomaly_type] += 1

    def screen_all(self):
        """执行所有筛查"""
        self.logger.info("开始异常筛查...")

        for i, record in enumerate(self.records):
            if self.verbose and (i + 1) % 1000 == 0:
                self.logger.info(f"  进度: {i+1}/{len(self.records)} ({(i+1)/len(self.records)*100:.1f}%)")

            has_anomaly = self._screen_record(record)

            if has_anomaly:
                self.stats['records_with_anomalies'] += 1

        self.logger.info(f"筛查完成: {self.stats['records_with_anomalies']}/{self.stats['total_records']} 条记录有异常")

    def _screen_record(self, record: Dict) -> bool:
        """筛查单条记录"""
        line_num = record.get('_line_num', 0)
        has_anomaly = False

        # 1. 必需字段检查
        for field in self.REQUIRED_FIELDS:
            if field not in record:
                self._add_anomaly('missing_field', line_num, {
                    'field': field,
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True

        # 2. 空间关系类型检查
        spatial_type = record.get('spatial_relation_type')
        if spatial_type and spatial_type not in self.VALID_SPATIAL_TYPES:
            self._add_anomaly('invalid_spatial_type', line_num, {
                'value': spatial_type,
                'record_id': record.get('id', 'unknown')
            })
            has_anomaly = True

        # 3. 拓扑子类型检查（仅topological类型）
        if spatial_type == 'topological':
            topology_subtype = record.get('topology_subtype')
            if not topology_subtype:
                self._add_anomaly('missing_topology_subtype', line_num, {
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True
            elif topology_subtype not in self.VALID_TOPOLOGY_SUBTYPES:
                self._add_anomaly('invalid_topology_subtype', line_num, {
                    'value': topology_subtype,
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True

        # 4. 难度检查
        difficulty = record.get('difficulty')
        if difficulty and difficulty not in self.VALID_DIFFICULTIES:
            self._add_anomaly('invalid_difficulty', line_num, {
                'value': difficulty,
                'record_id': record.get('id', 'unknown')
            })
            has_anomaly = True

        # 5. 难度分数范围检查
        difficulty_score = record.get('difficulty_score')
        if difficulty_score is not None:
            if not isinstance(difficulty_score, (int, float)) or not (1.0 <= difficulty_score <= 5.0):
                self._add_anomaly('difficulty_score_out_of_range', line_num, {
                    'value': difficulty_score,
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True

        # 6. 推理链结构检查
        chain = record.get('reasoning_chain', [])
        chain_anomaly = self._check_reasoning_chain(record, chain, line_num)
        if chain_anomaly:
            has_anomaly = True

        # 7. 实体检查
        entities = record.get('entities', [])
        entity_anomaly = self._check_entities(record, entities, line_num)
        if entity_anomaly:
            has_anomaly = True

        # 8. spatial_tokens检查
        spatial_tokens = record.get('spatial_tokens')
        if not spatial_tokens or not isinstance(spatial_tokens, list):
            self._add_anomaly('invalid_spatial_tokens', line_num, {
                'value': spatial_tokens,
                'record_id': record.get('id', 'unknown')
            })
            has_anomaly = True

        # 9. 答案一致性检查
        answer_anomaly = self._check_answer_consistency(record, line_num)
        if answer_anomaly:
            has_anomaly = True

        # 10. 泄露字段检查
        leak_anomaly = self._check_leak_fields(record, line_num)
        if leak_anomaly:
            has_anomaly = True

        # 记录按spatial_type和split的异常分布
        if has_anomaly:
            spatial_type = record.get('spatial_relation_type', 'unknown')
            split = record.get('split', 'unknown')
            self.stats['by_spatial_type'][spatial_type]['total'] += 1
            self.stats['by_split'][split]['total'] += 1

        return has_anomaly

    def _check_reasoning_chain(self, record: Dict, chain: List, line_num: int) -> bool:
        """检查推理链结构"""
        has_anomaly = False

        # 检查长度
        if not isinstance(chain, list):
            self._add_anomaly('chain_not_list', line_num, {
                'record_id': record.get('id', 'unknown'),
                'type': type(chain).__name__
            })
            return True

        if len(chain) != 5:
            self._add_anomaly('chain_length_error', line_num, {
                'length': len(chain),
                'expected': 5,
                'record_id': record.get('id', 'unknown')
            })
            has_anomaly = True

        # 检查每个步骤
        entities_in_record = set()
        for e in record.get('entities', []):
            if isinstance(e, dict) and 'name' in e:
                entities_in_record.add(e['name'])

        for step in chain:
            if not isinstance(step, dict):
                continue

            # 检查必需字段
            required_step_fields = ['step', 'name', 'action', 'content']
            for field in required_step_fields:
                if field not in step:
                    self._add_anomaly('step_missing_field', line_num, {
                        'step': step.get('step', 'unknown'),
                        'missing_field': field,
                        'record_id': record.get('id', 'unknown')
                    })
                    has_anomaly = True

            # 检查步骤名称
            step_name = step.get('name')
            if step_name and step_name not in self.VALID_STEP_NAMES:
                self._add_anomaly('invalid_step_name', line_num, {
                    'step_name': step_name,
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True

            # 检查entities_involved
            entities_involved = step.get('entities_involved', [])
            if isinstance(entities_involved, list):
                for entity in entities_involved:
                    if entity not in entities_in_record:
                        self._add_anomaly('entity_not_in_entities', line_num, {
                            'entity': entity,
                            'step': step.get('step', 'unknown'),
                            'record_id': record.get('id', 'unknown')
                        })
                        has_anomaly = True

        return has_anomaly

    def _check_entities(self, record: Dict, entities: List, line_num: int) -> bool:
        """检查实体"""
        has_anomaly = False

        # 检查实体数量
        if not isinstance(entities, list) or len(entities) < 2:
            self._add_anomaly('insufficient_entities', line_num, {
                'count': len(entities) if isinstance(entities, list) else 0,
                'record_id': record.get('id', 'unknown')
            })
            return True

        for entity in entities:
            if not isinstance(entity, dict):
                self._add_anomaly('invalid_entity_format', line_num, {
                    'entity': str(entity)[:50],
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True
                continue

            # 检查name字段
            if 'name' not in entity:
                self._add_anomaly('missing_entity_name', line_num, {
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True

            # 检查type字段
            entity_type = entity.get('type')
            if entity_type and entity_type not in self.VALID_ENTITY_TYPES:
                self._add_anomaly('invalid_entity_type', line_num, {
                    'entity_name': entity.get('name', 'unknown'),
                    'type': entity_type,
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True

            # 检查坐标
            coords = entity.get('coords')
            if coords:
                if not isinstance(coords, list) or len(coords) != 2:
                    self._add_anomaly('coord_format_error', line_num, {
                        'entity_name': entity.get('name', 'unknown'),
                        'coords': coords,
                        'record_id': record.get('id', 'unknown')
                    })
                    has_anomaly = True
                else:
                    lon, lat = coords
                    try:
                        lon = float(lon)
                        lat = float(lat)
                        if not (self.CHINA_LON_RANGE[0] <= lon <= self.CHINA_LON_RANGE[1]) or \
                           not (self.CHINA_LAT_RANGE[0] <= lat <= self.CHINA_LAT_RANGE[1]):
                            self._add_anomaly('coord_out_of_range', line_num, {
                                'entity_name': entity.get('name', 'unknown'),
                                'coords': [lon, lat],
                                'record_id': record.get('id', 'unknown')
                            })
                            has_anomaly = True
                    except (ValueError, TypeError):
                        self._add_anomaly('coord_format_error', line_num, {
                            'entity_name': entity.get('name', 'unknown'),
                            'coords': coords,
                            'record_id': record.get('id', 'unknown')
                        })
                        has_anomaly = True

        return has_anomaly

    def _check_answer_consistency(self, record: Dict, line_num: int) -> bool:
        """检查答案一致性"""
        answer = record.get('answer', '')
        chain = record.get('reasoning_chain', [])

        if not chain or not isinstance(chain, list):
            return False

        # 获取final_answer
        final_step = chain[-1] if chain else {}
        final_answer = final_step.get('final_answer', '') if isinstance(final_step, dict) else ''

        if not answer or not final_answer:
            return False

        # 简单一致性检查
        answer_lower = answer.lower().strip()
        final_lower = final_answer.lower().strip()

        # 检查明显的矛盾
        contradictions = [
            ('是', '否'), ('存在', '不存在'), ('包含', '不包含'),
            ('位于', '不位于'), ('相邻', '不相邻'), ('在', '不在'),
            ('yes', 'no'), ('true', 'false')
        ]

        for pos, neg in contradictions:
            if pos in answer_lower and neg in final_lower:
                self._add_anomaly('answer_mismatch', line_num, {
                    'answer': answer[:100],
                    'final_answer': final_answer[:100],
                    'record_id': record.get('id', 'unknown')
                })
                return True
            if neg in answer_lower and pos in final_lower:
                self._add_anomaly('answer_mismatch', line_num, {
                    'answer': answer[:100],
                    'final_answer': final_answer[:100],
                    'record_id': record.get('id', 'unknown')
                })
                return True

        return False

    def _check_leak_fields(self, record: Dict, line_num: int) -> bool:
        """检查泄露字段（relation_type, calculation_result）"""
        has_anomaly = False
        chain = record.get('reasoning_chain', [])

        for step in chain:
            if not isinstance(step, dict):
                continue

            # 检查relation_type泄露
            if 'relation_type' in step:
                self._add_anomaly('leak_field_relation_type', line_num, {
                    'step': step.get('step', 'unknown'),
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True

            # 检查calculation_result泄露
            if 'calculation_result' in step:
                self._add_anomaly('leak_field_calculation_result', line_num, {
                    'step': step.get('step', 'unknown'),
                    'record_id': record.get('id', 'unknown')
                })
                has_anomaly = True

        return has_anomaly

    def generate_report(self) -> Dict:
        """生成报告"""
        report = {
            'meta': {
                'input_file': str(self.input_file),
                'output_file': str(self.output_file),
                'generated_at': datetime.now().isoformat(),
                'total_records': self.stats['total_records'],
                'records_with_anomalies': self.stats['records_with_anomalies'],
                'anomaly_rate': f"{self.stats['records_with_anomalies'] / max(self.stats['total_records'], 1) * 100:.2f}%"
            },
            'summary': {
                'total_anomalies': sum(len(v) for v in self.anomalies.values()),
                'anomaly_types': len(self.anomalies),
                'by_type': {k: len(v) for k, v in sorted(self.anomalies.items(), key=lambda x: -len(x[1]))}
            },
            'anomalies': dict(self.anomalies),
            'examples': {}
        }

        # 每种异常类型提取最多3个示例
        for anomaly_type, anomaly_list in self.anomalies.items():
            report['examples'][anomaly_type] = anomaly_list[:3]

        return report

    def save_report(self):
        """保存报告"""
        # 确保输出目录存在
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        report = self.generate_report()

        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.logger.info(f"报告已保存: {self.output_file}")

    def print_summary(self):
        """打印摘要"""
        print("\n" + "=" * 60)
        print("GeoKD-SR 数据异常筛查报告")
        print("=" * 60)
        print(f"数据文件: {self.input_file}")
        print(f"总记录数: {self.stats['total_records']}")
        print(f"异常记录数: {self.stats['records_with_anomalies']}")
        print(f"异常率: {self.stats['records_with_anomalies'] / max(self.stats['total_records'], 1) * 100:.2f}%")

        print(f"\n按异常类型分布:")
        print("-" * 60)

        sorted_anomalies = sorted(self.anomalies.items(), key=lambda x: -len(x[1]))
        for anomaly_type, anomaly_list in sorted_anomalies:
            count = len(anomaly_list)
            pct = count / max(self.stats['total_records'], 1) * 100
            print(f"  {anomaly_type}: {count} 条 ({pct:.2f}%)")

        # 打印示例
        print(f"\n异常示例（每类最多3个）:")
        print("-" * 60)

        for anomaly_type, anomaly_list in sorted_anomalies[:5]:  # 只显示前5种类型
            print(f"\n[{anomaly_type}]")
            for i, anomaly in enumerate(anomaly_list[:3]):
                print(f"  示例 {i+1}: 行 {anomaly['line']}")
                details = anomaly.get('details', {})
                for key, value in list(details.items())[:3]:
                    value_str = str(value)[:80]
                    print(f"    - {key}: {value_str}")

        print("\n" + "=" * 60)
        print("建议:")
        print("1. 结构完整性异常: 修复或移除异常数据")
        print("2. 格式异常: 修复坐标格式、实体类型等")
        print("3. 内容一致性异常: 人工审核后决定")
        print("4. 泄露字段: 从reasoning_chain中移除泄露字段")
        print(f"\n详细报告已保存至: {self.output_file}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 数据异常筛查脚本')
    parser.add_argument(
        '--input', '-i',
        default='D:/30_keyan/GeoKD-SR/data/final/final_1_cleaned.jsonl',
        help='输入文件路径'
    )
    parser.add_argument(
        '--output', '-o',
        default='D:/30_keyan/GeoKD-SR/reports/anomaly_report.json',
        help='输出报告路径'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        default=True,
        help='显示详细输出'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("GeoKD-SR 数据异常筛查脚本")
    print("=" * 60)
    print(f"输入文件: {args.input}")
    print(f"输出报告: {args.output}")
    print()

    # 创建筛查器
    screener = AnomalyScreener(args.input, args.output, args.verbose)

    # 加载数据
    screener.load_data()

    # 执行筛查
    screener.screen_all()

    # 保存报告
    screener.save_report()

    # 打印摘要
    screener.print_summary()

    return 0


if __name__ == '__main__':
    exit(main())
