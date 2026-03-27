#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GeoKD-SR 综合字段校验脚本
基于三份规范文档对 final_1_v6.jsonl 进行逐字段校验

规范文档:
1. 1.1-数据生成规范.md - V2.1 数据格式规范
2. GeoKD-SR-实验设计方案-V5.2.md - 实验需求
3. GeoKD-SR-数据字段标准详解-V1.0.md - 字段验证标准

校验层级:
- L1: 基础字段格式校验
- L2: 推理链结构校验
- L3: 实体数组校验
- L4: Token映射校验
- L4.5: Answer与推理链一致性校验 (核心)
- L5: 难度评分校验
- L6: 分布校验

作者: Claude Code
日期: 2026-03-13
"""

import json
import re
import math
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


# ============== 常量定义 ==============

# 标准字段集（所有记录必须包含且仅包含这些字段，除条件字段外）
STANDARD_FIELDS = {
    'id', 'spatial_relation_type', 'question', 'answer',
    'difficulty', 'difficulty_score', 'reasoning_chain',
    'entities', 'spatial_tokens', 'entity_to_token'
}

# 条件字段
CONDITIONAL_FIELDS = {'topology_subtype'}

# L1: 基础字段校验常量
VALID_RELATION_TYPES = {'directional', 'topological', 'metric', 'composite'}
VALID_TOPOLOGY_SUBTYPES = {'within', 'contains', 'adjacent', 'disjoint', 'overlap'}
VALID_DIFFICULTIES = {'easy', 'medium', 'hard'}
VALID_ENTITY_TYPES = {'province', 'city', 'landmark', 'mountain', 'river', 'lake', 'region'}

# 中国坐标范围
CHINA_LON_RANGE = (73.0, 135.0)
CHINA_LAT_RANGE = (18.0, 54.0)

# 难度映射阈值 (用户调整后)
EASY_THRESHOLD = 1.3
HARD_THRESHOLD = 3.1

# 推理链步骤名称
EXPECTED_STEP_NAMES = [
    'entity_identification',
    'spatial_relation_extraction',
    'coordinate_retrieval',
    'spatial_calculation',
    'answer_generation'
]

# 方向词映射
DIRECTION_WORDS = {
    '东': 'east', '西': 'west', '南': 'south', '北': 'north',
    '东北': 'northeast', '东南': 'southeast', '西北': 'northwest', '西南': 'southwest',
    '东偏北': 'northeast', '东偏南': 'southeast', '西偏北': 'northwest', '西偏南': 'southwest',
    '北偏东': 'northeast', '北偏西': 'northwest', '南偏东': 'southeast', '南偏西': 'southwest'
}


# ============== 数据类定义 ==============

@dataclass
class ValidationError:
    """校验错误记录"""
    record_id: str
    level: str  # L1, L2, L3, L4, L4.5, L5, L6
    field: str
    issue: str
    severity: str  # critical, warning, info
    original_value: Any = None
    suggested_fix: Any = None

    def to_dict(self) -> dict:
        return {
            'record_id': self.record_id,
            'level': self.level,
            'field': self.field,
            'issue': self.issue,
            'severity': self.severity,
            'original_value': self.original_value,
            'suggested_fix': self.suggested_fix
        }


@dataclass
class ValidationStats:
    """校验统计"""
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    fixed_records: int = 0
    errors_by_level: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_field: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_severity: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


# ============== 工具函数 ==============

def calculate_bearing(coord1: List[float], coord2: List[float]) -> float:
    """
    计算从coord1到coord2的方位角（度）
    coord格式: [经度, 纬度]
    """
    lon1, lat1 = math.radians(coord1[0]), math.radians(coord1[1])
    lon2, lat2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    bearing = math.atan2(x, y)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360

    return bearing


def bearing_to_direction(bearing: float) -> str:
    """将方位角转换为方向词"""
    directions = [
        (22.5, '北'), (67.5, '东北'), (112.5, '东'), (157.5, '东南'),
        (202.5, '南'), (247.5, '西南'), (292.5, '西'), (337.5, '西北'), (360, '北')
    ]

    for threshold, direction in directions:
        if bearing < threshold:
            return direction
    return '北'


def calculate_haversine_distance(coord1: List[float], coord2: List[float]) -> float:
    """
    使用Haversine公式计算两点间的大圆距离（公里）
    coord格式: [经度, 纬度]
    """
    lat1, lon1 = math.radians(coord1[1]), math.radians(coord1[0])
    lat2, lon2 = math.radians(coord2[1]), math.radians(coord2[0])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    R = 6371  # 地球半径（公里）
    return R * c


def extract_direction_from_text(text: str) -> Optional[str]:
    """从文本中提取方向词"""
    # 按长度降序匹配（先匹配"东北"再匹配"东"）
    sorted_directions = sorted(DIRECTION_WORDS.keys(), key=len, reverse=True)
    for direction in sorted_directions:
        if direction in text:
            return direction
    return None


def extract_distance_from_text(text: str) -> Optional[float]:
    """从文本中提取距离数值"""
    patterns = [
        r'约(\d+\.?\d*)\s*公里',
        r'(\d+\.?\d*)\s*公里',
        r'约(\d+\.?\d*)\s*km',
        r'(\d+\.?\d*)\s*km',
        r'距离[约为\s]*(\d+\.?\d*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def normalize_direction(direction: str) -> str:
    """标准化方向词"""
    direction = direction.strip()
    # 处理"XX方向"格式
    if direction.endswith('方向'):
        direction = direction[:-2]
    return direction


def directions_match(dir1: str, dir2: str) -> bool:
    """判断两个方向词是否匹配"""
    dir1 = normalize_direction(dir1)
    dir2 = normalize_direction(dir2)

    if dir1 == dir2:
        return True

    # 检查是否是同义词
    english1 = DIRECTION_WORDS.get(dir1, dir1)
    english2 = DIRECTION_WORDS.get(dir2, dir2)

    return english1 == english2


def semantic_match(answer: str, final_answer: str) -> bool:
    """判断answer与final_answer是否语义匹配"""
    # 去除标点和空格
    clean_answer = re.sub(r'[，。！？、\s]', '', answer)
    clean_final = re.sub(r'[，。！？、\s]', '', final_answer)

    # 完全匹配
    if clean_answer == clean_final:
        return True

    # 包含匹配（final_answer可能是answer的一部分或反之）
    if clean_final in clean_answer or clean_answer in clean_final:
        return True

    return False


def calculate_expected_difficulty_score(
    spatial_type: str,
    topology_subtype: Optional[str] = None,
    entity_types: Optional[List[str]] = None
) -> float:
    """
    计算预期的difficulty_score (V2.0算法)
    """
    # 基础分
    base_scores = {
        "directional": 1.2,
        "topological": 2.2,
        "metric": 1.3,
        "composite": 3.2
    }

    # 拓扑子类型加成
    topology_bonus = {
        "within": 0.0,
        "contains": 0.1,
        "adjacent": 0.3,
        "disjoint": 0.4,
        "overlap": 0.6
    }

    # 实体类型对加成
    entity_bonus = {
        ("city", "city"): 0.0,
        ("city", "landmark"): 0.2,
        ("province", "city"): 0.4,
        ("river", "city"): 0.7,
        ("mountain", "city"): 0.7,
        ("region", "city"): 0.9
    }

    score = base_scores.get(spatial_type, 2.0)

    if topology_subtype and topology_subtype in topology_bonus:
        score += topology_bonus[topology_subtype]

    if entity_types and len(entity_types) >= 2:
        sorted_types = tuple(sorted(entity_types[:2]))
        score += entity_bonus.get(sorted_types, 0.5)

    return min(max(score, 1.0), 5.0)


def map_difficulty_score(score: float) -> str:
    """根据difficulty_score映射difficulty"""
    if score <= EASY_THRESHOLD:
        return 'easy'
    elif score <= HARD_THRESHOLD:
        return 'medium'
    else:
        return 'hard'


# ============== 校验函数 ==============

def validate_basic_fields(record: dict) -> List[ValidationError]:
    """L1: 基础字段格式校验"""
    errors = []
    record_id = record.get('id', 'unknown')

    # 1. id格式校验
    if 'id' not in record:
        errors.append(ValidationError(record_id, 'L1', 'id', '缺失id字段', 'critical'))
    elif not isinstance(record['id'], str):
        errors.append(ValidationError(record_id, 'L1', 'id', 'id字段类型错误', 'critical',
                                      record['id'], str(record['id'])))
    elif not re.match(r'^geosr_[a-z]+_\d+$', record['id']):
        errors.append(ValidationError(record_id, 'L1', 'id', 'id格式不符合规范', 'warning',
                                      record['id'], 'geosr_{type}_{序号}'))

    # 2. spatial_relation_type校验
    if 'spatial_relation_type' not in record:
        errors.append(ValidationError(record_id, 'L1', 'spatial_relation_type', '缺失spatial_relation_type字段', 'critical'))
    elif record['spatial_relation_type'] not in VALID_RELATION_TYPES:
        errors.append(ValidationError(record_id, 'L1', 'spatial_relation_type',
                                      f'spatial_relation_type值无效: {record["spatial_relation_type"]}', 'critical',
                                      record['spatial_relation_type'], list(VALID_RELATION_TYPES)))

    # 3. topology_subtype条件校验
    spatial_type = record.get('spatial_relation_type')
    if spatial_type == 'topological':
        if 'topology_subtype' not in record:
            errors.append(ValidationError(record_id, 'L1', 'topology_subtype',
                                          'topological类型缺失topology_subtype字段', 'critical'))
        elif record.get('topology_subtype') not in VALID_TOPOLOGY_SUBTYPES:
            errors.append(ValidationError(record_id, 'L1', 'topology_subtype',
                                          f'topology_subtype值无效: {record.get("topology_subtype")}', 'critical',
                                          record.get('topology_subtype'), list(VALID_TOPOLOGY_SUBTYPES)))
    else:
        # 非topological类型不应有topology_subtype
        if 'topology_subtype' in record:
            errors.append(ValidationError(record_id, 'L1', 'topology_subtype',
                                          f'{spatial_type}类型不应有topology_subtype字段', 'warning',
                                          record['topology_subtype'], None))

    # 4. question校验
    if 'question' not in record:
        errors.append(ValidationError(record_id, 'L1', 'question', '缺失question字段', 'critical'))
    elif not isinstance(record['question'], str):
        errors.append(ValidationError(record_id, 'L1', 'question', 'question字段类型错误', 'critical'))
    elif len(record['question']) < 10:
        errors.append(ValidationError(record_id, 'L1', 'question', 'question长度过短(<10字符)', 'warning'))
    elif len(record['question']) > 200:
        errors.append(ValidationError(record_id, 'L1', 'question', 'question长度过长(>200字符)', 'warning'))

    # 5. answer校验
    if 'answer' not in record:
        errors.append(ValidationError(record_id, 'L1', 'answer', '缺失answer字段', 'critical'))
    elif not isinstance(record['answer'], str):
        errors.append(ValidationError(record_id, 'L1', 'answer', 'answer字段类型错误', 'critical'))
    elif len(record['answer']) < 2:
        errors.append(ValidationError(record_id, 'L1', 'answer', 'answer长度过短(<2字符)', 'warning'))
    elif len(record['answer']) > 100:
        errors.append(ValidationError(record_id, 'L1', 'answer', 'answer长度过长(>100字符)', 'warning'))

    # 6. difficulty校验
    if 'difficulty' not in record:
        errors.append(ValidationError(record_id, 'L1', 'difficulty', '缺失difficulty字段', 'critical'))
    elif record['difficulty'] not in VALID_DIFFICULTIES:
        errors.append(ValidationError(record_id, 'L1', 'difficulty',
                                      f'difficulty值无效: {record["difficulty"]}', 'critical',
                                      record['difficulty'], list(VALID_DIFFICULTIES)))

    # 7. difficulty_score校验
    if 'difficulty_score' not in record:
        errors.append(ValidationError(record_id, 'L1', 'difficulty_score', '缺失difficulty_score字段', 'critical'))
    elif not isinstance(record['difficulty_score'], (int, float)):
        errors.append(ValidationError(record_id, 'L1', 'difficulty_score', 'difficulty_score字段类型错误', 'critical'))
    elif not (1.0 <= record['difficulty_score'] <= 5.0):
        errors.append(ValidationError(record_id, 'L1', 'difficulty_score',
                                      f'difficulty_score超出范围: {record["difficulty_score"]}', 'warning',
                                      record['difficulty_score'], '1.0-5.0'))

    return errors


def validate_reasoning_chain(record: dict) -> List[ValidationError]:
    """L2: 推理链结构校验"""
    errors = []
    record_id = record.get('id', 'unknown')

    if 'reasoning_chain' not in record:
        errors.append(ValidationError(record_id, 'L2', 'reasoning_chain', '缺失reasoning_chain字段', 'critical'))
        return errors

    rc = record['reasoning_chain']

    # 1. 必须是列表
    if not isinstance(rc, list):
        errors.append(ValidationError(record_id, 'L2', 'reasoning_chain', 'reasoning_chain必须是数组', 'critical'))
        return errors

    # 2. 必须有5步
    if len(rc) != 5:
        errors.append(ValidationError(record_id, 'L2', 'reasoning_chain',
                                      f'reasoning_chain步骤数量错误: {len(rc)}步', 'critical',
                                      len(rc), 5))
        return errors

    # 3. 检查每步的字段
    required_fields = ['step', 'name', 'action', 'content']
    for i, step in enumerate(rc):
        if not isinstance(step, dict):
            errors.append(ValidationError(record_id, 'L2', f'reasoning_chain[{i}]',
                                          f'步骤{i}不是对象', 'critical'))
            continue

        # 检查step序号
        if step.get('step') != i + 1:
            errors.append(ValidationError(record_id, 'L2', f'reasoning_chain[{i}].step',
                                          f'步骤序号错误: {step.get("step")}', 'warning',
                                          step.get('step'), i + 1))

        # 检查必需字段
        for field in required_fields:
            if field not in step:
                errors.append(ValidationError(record_id, 'L2', f'reasoning_chain[{i}].{field}',
                                              f'步骤{i}缺失{field}字段', 'critical'))

        # 检查name是否正确
        if step.get('name') != EXPECTED_STEP_NAMES[i]:
            errors.append(ValidationError(record_id, 'L2', f'reasoning_chain[{i}].name',
                                          f'步骤名称错误: {step.get("name")}', 'warning',
                                          step.get('name'), EXPECTED_STEP_NAMES[i]))

    return errors


def validate_entities(record: dict) -> List[ValidationError]:
    """L3: 实体数组校验"""
    errors = []
    record_id = record.get('id', 'unknown')

    if 'entities' not in record:
        errors.append(ValidationError(record_id, 'L3', 'entities', '缺失entities字段', 'critical'))
        return errors

    entities = record['entities']

    # 1. 必须是列表
    if not isinstance(entities, list):
        errors.append(ValidationError(record_id, 'L3', 'entities', 'entities必须是数组', 'critical'))
        return errors

    # 2. 必须有至少2个实体
    if len(entities) < 2:
        errors.append(ValidationError(record_id, 'L3', 'entities',
                                      f'实体数量不足: {len(entities)}个', 'critical',
                                      len(entities), '>=2'))
        return errors

    # 3. 检查每个实体
    for i, entity in enumerate(entities):
        if not isinstance(entity, dict):
            errors.append(ValidationError(record_id, 'L3', f'entities[{i}]',
                                          f'实体{i}不是对象', 'critical'))
            continue

        # 检查name
        if 'name' not in entity:
            errors.append(ValidationError(record_id, 'L3', f'entities[{i}].name',
                                          f'实体{i}缺失name字段', 'critical'))

        # 检查type
        if 'type' not in entity:
            errors.append(ValidationError(record_id, 'L3', f'entities[{i}].type',
                                          f'实体{i}缺失type字段', 'critical'))
        elif entity['type'] not in VALID_ENTITY_TYPES:
            errors.append(ValidationError(record_id, 'L3', f'entities[{i}].type',
                                          f'实体{i}类型无效: {entity["type"]}', 'critical',
                                          entity['type'], list(VALID_ENTITY_TYPES)))

        # 检查coords
        if 'coords' not in entity:
            errors.append(ValidationError(record_id, 'L3', f'entities[{i}].coords',
                                          f'实体{i}缺失coords字段', 'critical'))
        else:
            coords = entity['coords']
            if not isinstance(coords, list) or len(coords) != 2:
                errors.append(ValidationError(record_id, 'L3', f'entities[{i}].coords',
                                              f'实体{i}坐标格式错误', 'critical'))
            else:
                lon, lat = coords
                # 检查坐标范围
                if not (CHINA_LON_RANGE[0] <= lon <= CHINA_LON_RANGE[1]):
                    errors.append(ValidationError(record_id, 'L3', f'entities[{i}].coords',
                                                  f'实体{i}经度超出中国范围: {lon}', 'warning',
                                                  lon, f'{CHINA_LON_RANGE[0]}-{CHINA_LON_RANGE[1]}'))
                if not (CHINA_LAT_RANGE[0] <= lat <= CHINA_LAT_RANGE[1]):
                    errors.append(ValidationError(record_id, 'L3', f'entities[{i}].coords',
                                                  f'实体{i}纬度超出中国范围: {lat}', 'warning',
                                                  lat, f'{CHINA_LAT_RANGE[0]}-{CHINA_LAT_RANGE[1]}'))

    return errors


def validate_tokens(record: dict) -> List[ValidationError]:
    """L4: Token映射校验"""
    errors = []
    record_id = record.get('id', 'unknown')

    # 1. spatial_tokens校验
    if 'spatial_tokens' not in record:
        errors.append(ValidationError(record_id, 'L4', 'spatial_tokens', '缺失spatial_tokens字段', 'critical'))
    else:
        tokens = record['spatial_tokens']
        if not isinstance(tokens, list):
            errors.append(ValidationError(record_id, 'L4', 'spatial_tokens', 'spatial_tokens必须是数组', 'critical'))
        elif len(tokens) < 3:
            errors.append(ValidationError(record_id, 'L4', 'spatial_tokens',
                                          f'spatial_tokens数量过少: {len(tokens)}个', 'warning'))
        elif len(tokens) > 9:
            errors.append(ValidationError(record_id, 'L4', 'spatial_tokens',
                                          f'spatial_tokens数量过多: {len(tokens)}个', 'info'))

    # 2. entity_to_token校验
    if 'entity_to_token' not in record:
        errors.append(ValidationError(record_id, 'L4', 'entity_to_token', '缺失entity_to_token字段', 'critical'))
    else:
        e2t = record['entity_to_token']
        if not isinstance(e2t, dict):
            errors.append(ValidationError(record_id, 'L4', 'entity_to_token', 'entity_to_token必须是对象', 'critical'))
        else:
            # 检查实体是否都有映射
            entities = record.get('entities', [])
            for entity in entities:
                if isinstance(entity, dict) and 'name' in entity:
                    name = entity['name']
                    if name not in e2t:
                        errors.append(ValidationError(record_id, 'L4', 'entity_to_token',
                                                      f'实体"{name}"在entity_to_token中缺失', 'warning'))
                    else:
                        # 检查映射字段
                        mapping = e2t[name]
                        required = ['char_start', 'char_end', 'token_indices']
                        for field in required:
                            if field not in mapping:
                                errors.append(ValidationError(record_id, 'L4', f'entity_to_token.{name}.{field}',
                                                              f'实体"{name}"的映射缺失{field}字段', 'warning'))

    return errors


def validate_answer_reasoning_consistency(record: dict) -> List[ValidationError]:
    """L4.5: Answer与推理链一致性校验（核心）"""
    errors = []
    record_id = record.get('id', 'unknown')

    answer = record.get('answer', '')
    rc = record.get('reasoning_chain', [])
    spatial_type = record.get('spatial_relation_type', '')
    entities = record.get('entities', [])

    if len(rc) < 5:
        errors.append(ValidationError(record_id, 'L4.5', 'reasoning_chain', '推理链不足5步，无法进行一致性校验', 'critical'))
        return errors

    step4 = rc[3]  # spatial_calculation
    step5 = rc[4]  # answer_generation

    calculation_result = step4.get('calculation_result', '')
    final_answer = step5.get('final_answer', '')

    # 1. final_answer与answer语义一致性
    if not semantic_match(answer, final_answer):
        errors.append(ValidationError(record_id, 'L4.5', 'final_answer',
                                      f'answer与final_answer不匹配', 'critical',
                                      {'answer': answer, 'final_answer': final_answer},
                                      answer))

    # 2. 根据空间类型进行特定校验
    if len(entities) >= 2 and 'coords' in entities[0] and 'coords' in entities[1]:
        coord1 = entities[0]['coords']
        coord2 = entities[1]['coords']

        if spatial_type == 'directional':
            # 方向关系校验
            actual_bearing = calculate_bearing(coord2, coord1)  # 从实体2到实体1
            actual_direction = bearing_to_direction(actual_bearing)

            # 从answer中提取方向
            answer_direction = extract_direction_from_text(answer)
            calc_direction = extract_direction_from_text(str(calculation_result))

            if answer_direction and not directions_match(answer_direction, actual_direction):
                errors.append(ValidationError(record_id, 'L4.5', 'answer',
                                              f'方向关系不一致: answer="{answer_direction}", 实际="{actual_direction}"',
                                              'critical',
                                              {'answer': answer, 'calculated': actual_direction},
                                              actual_direction))

            if calc_direction and not directions_match(calc_direction, actual_direction):
                errors.append(ValidationError(record_id, 'L4.5', 'calculation_result',
                                              f'calculation_result方向错误: "{calc_direction}", 实际="{actual_direction}"',
                                              'warning',
                                              {'calculation_result': calculation_result, 'calculated': actual_direction},
                                              actual_direction))

        elif spatial_type == 'metric':
            # 度量关系校验
            actual_distance = calculate_haversine_distance(coord1, coord2)

            answer_distance = extract_distance_from_text(answer)
            calc_distance = extract_distance_from_text(str(calculation_result))

            if answer_distance:
                error_rate = abs(answer_distance - actual_distance) / actual_distance
                if error_rate > 0.1:  # 10%误差
                    errors.append(ValidationError(record_id, 'L4.5', 'answer',
                                                  f'距离误差过大: answer={answer_distance}km, 实际={actual_distance:.1f}km, 误差={error_rate*100:.1f}%',
                                                  'critical',
                                                  {'answer_distance': answer_distance, 'actual_distance': round(actual_distance, 1)},
                                                  round(actual_distance)))

            if calc_distance:
                error_rate = abs(calc_distance - actual_distance) / actual_distance
                if error_rate > 0.1:
                    errors.append(ValidationError(record_id, 'L4.5', 'calculation_result',
                                                  f'calculation_result距离误差过大: {calc_distance}km, 实际={actual_distance:.1f}km',
                                                  'warning',
                                                  {'calc_distance': calc_distance, 'actual_distance': round(actual_distance, 1)},
                                                  round(actual_distance)))

        elif spatial_type == 'topological':
            # 拓扑关系校验
            topology_subtype = record.get('topology_subtype', '')

            # 检查answer的肯定/否定与topology_subtype是否一致
            is_affirmative = any(w in answer for w in ['是的', '在', '位于', '包含', '相邻', '有', '确实'])
            is_negative = any(w in answer for w in ['不是', '不在', '不位于', '不包含', '不相邻', '没有'])

            # disjoint通常需要否定回答
            if topology_subtype == 'disjoint' and is_affirmative and not is_negative:
                # 检查是否是"不相邻"等否定形式的肯定
                if '不' not in answer:
                    errors.append(ValidationError(record_id, 'L4.5', 'answer',
                                                  f'disjoint关系但answer是肯定形式: "{answer}"',
                                                  'warning'))

            if topology_subtype in ['within', 'contains', 'adjacent', 'overlap'] and is_negative and not is_affirmative:
                errors.append(ValidationError(record_id, 'L4.5', 'answer',
                                              f'{topology_subtype}关系但answer是否定形式: "{answer}"',
                                              'warning'))

    return errors


def validate_difficulty(record: dict) -> List[ValidationError]:
    """L5: 难度评分校验"""
    errors = []
    record_id = record.get('id', 'unknown')

    difficulty = record.get('difficulty')
    difficulty_score = record.get('difficulty_score')

    if difficulty is None or difficulty_score is None:
        return errors  # 已在L1校验

    # 1. 检查difficulty与difficulty_score的映射是否一致
    expected_difficulty = map_difficulty_score(difficulty_score)

    if difficulty != expected_difficulty:
        errors.append(ValidationError(record_id, 'L5', 'difficulty',
                                      f'difficulty与difficulty_score不匹配: difficulty={difficulty}, score={difficulty_score}, 期望difficulty={expected_difficulty}',
                                      'warning',
                                      {'difficulty': difficulty, 'difficulty_score': difficulty_score},
                                      expected_difficulty))

    # 2. 计算预期difficulty_score并与实际比较
    spatial_type = record.get('spatial_relation_type', '')
    topology_subtype = record.get('topology_subtype')
    entities = record.get('entities', [])
    entity_types = [e.get('type') for e in entities if isinstance(e, dict) and 'type' in e]

    expected_score = calculate_expected_difficulty_score(spatial_type, topology_subtype, entity_types)

    # 允许一定误差（因为可能有其他因素影响）
    if abs(difficulty_score - expected_score) > 1.0:
        errors.append(ValidationError(record_id, 'L5', 'difficulty_score',
                                      f'difficulty_score与预期差异较大: 实际={difficulty_score}, 预期≈{expected_score:.1f}',
                                      'info',
                                      difficulty_score, round(expected_score, 1)))

    return errors


def validate_distribution(records: List[dict]) -> Dict[str, Any]:
    """L6: 分布校验"""
    results = {
        'spatial_relation_type': {},
        'difficulty': {},
        'topology_subtype': {},
        'total_records': len(records)
    }

    total = len(records)
    if total == 0:
        return results

    # 1. 空间关系类型分布
    type_counts = Counter(r.get('spatial_relation_type', 'unknown') for r in records)
    type_targets = {
        'directional': 0.25,
        'topological': 0.275,
        'metric': 0.275,
        'composite': 0.20
    }

    for rel_type, target in type_targets.items():
        actual = type_counts.get(rel_type, 0) / total
        deviation = abs(actual - target)
        results['spatial_relation_type'][rel_type] = {
            'count': type_counts.get(rel_type, 0),
            'actual_ratio': round(actual, 4),
            'target_ratio': target,
            'deviation': round(deviation, 4),
            'pass': deviation < 0.05
        }

    # 2. 难度分布
    diff_counts = Counter(r.get('difficulty', 'unknown') for r in records)
    diff_targets = {'easy': 0.30, 'medium': 0.50, 'hard': 0.20}

    for diff, target in diff_targets.items():
        actual = diff_counts.get(diff, 0) / total
        deviation = abs(actual - target)
        results['difficulty'][diff] = {
            'count': diff_counts.get(diff, 0),
            'actual_ratio': round(actual, 4),
            'target_ratio': target,
            'deviation': round(deviation, 4),
            'pass': deviation < 0.05
        }

    # 3. 拓扑子类型分布
    topo_records = [r for r in records if r.get('spatial_relation_type') == 'topological']
    topo_total = len(topo_records)

    if topo_total > 0:
        subtype_counts = Counter(r.get('topology_subtype', 'unknown') for r in topo_records)
        subtype_targets = {'within': 0.20, 'contains': 0.20, 'adjacent': 0.20, 'disjoint': 0.20, 'overlap': 0.20}

        for subtype, target in subtype_targets.items():
            actual = subtype_counts.get(subtype, 0) / topo_total
            deviation = abs(actual - target)
            results['topology_subtype'][subtype] = {
                'count': subtype_counts.get(subtype, 0),
                'actual_ratio': round(actual, 4),
                'target_ratio': target,
                'deviation': round(deviation, 4),
                'pass': deviation < 0.05
            }

    return results


def validate_extra_fields(record: dict) -> List[ValidationError]:
    """检查多余字段"""
    errors = []
    record_id = record.get('id', 'unknown')

    all_allowed = STANDARD_FIELDS | CONDITIONAL_FIELDS
    extra_fields = set(record.keys()) - all_allowed

    for field in extra_fields:
        errors.append(ValidationError(record_id, 'L1', field,
                                      f'多余字段: {field}', 'warning',
                                      field, None))

    return errors


# ============== 修复函数 ==============

def fix_record(record: dict, errors: List[ValidationError]) -> Tuple[dict, List[str]]:
    """
    自动修复记录中的问题
    返回: (修复后的记录, 修复说明列表)
    """
    fixed = record.copy()
    fixes = []

    # 1. 移除多余字段
    all_allowed = STANDARD_FIELDS | CONDITIONAL_FIELDS
    extra_fields = set(fixed.keys()) - all_allowed
    for field in extra_fields:
        del fixed[field]
        fixes.append(f'移除多余字段: {field}')

    # 2. 修复final_answer不一致
    answer = fixed.get('answer', '')
    rc = fixed.get('reasoning_chain', [])

    if len(rc) >= 5 and 'final_answer' in rc[4]:
        final_answer = rc[4]['final_answer']
        if not semantic_match(answer, final_answer):
            rc[4]['final_answer'] = answer
            fixes.append(f'修复final_answer: "{final_answer}" -> "{answer}"')

    # 3. 根据空间类型修复
    spatial_type = fixed.get('spatial_relation_type', '')
    entities = fixed.get('entities', [])

    if len(entities) >= 2:
        e1 = entities[0]
        e2 = entities[1]

        if 'coords' in e1 and 'coords' in e2:
            coord1 = e1['coords']
            coord2 = e2['coords']
            name1 = e1.get('name', '实体1')
            name2 = e2.get('name', '实体2')

            if spatial_type == 'directional':
                # 重新计算方向
                actual_bearing = calculate_bearing(coord2, coord1)
                actual_direction = bearing_to_direction(actual_bearing)

                # 更新calculation_result
                if len(rc) >= 4:
                    old_calc = rc[3].get('calculation_result', '')
                    rc[3]['calculation_result'] = actual_direction
                    if old_calc != actual_direction:
                        fixes.append(f'修复方向calculation_result: "{old_calc}" -> "{actual_direction}"')

                # 更新answer
                new_answer = f'{name1}在{name2}的{actual_direction}方向。'
                if not directions_match(answer, actual_direction):
                    fixed['answer'] = new_answer
                    fixes.append(f'修复answer: "{answer}" -> "{new_answer}"')

            elif spatial_type == 'metric':
                # 重新计算距离
                actual_distance = calculate_haversine_distance(coord1, coord2)

                # 更新calculation_result
                if len(rc) >= 4:
                    old_calc = rc[3].get('calculation_result', '')
                    new_calc = str(int(round(actual_distance)))
                    rc[3]['calculation_result'] = new_calc
                    if old_calc != new_calc:
                        fixes.append(f'修复距离calculation_result: "{old_calc}" -> "{new_calc}"')

                # 更新answer
                new_answer = f'直线距离约为{int(round(actual_distance))}公里。'
                answer_distance = extract_distance_from_text(answer)
                if answer_distance and abs(answer_distance - actual_distance) / actual_distance > 0.1:
                    fixed['answer'] = new_answer
                    fixes.append(f'修复answer: "{answer}" -> "{new_answer}"')

    # 4. 修复difficulty映射不一致
    difficulty_score = fixed.get('difficulty_score')
    if difficulty_score is not None:
        expected_difficulty = map_difficulty_score(difficulty_score)
        if fixed.get('difficulty') != expected_difficulty:
            old_diff = fixed.get('difficulty')
            fixed['difficulty'] = expected_difficulty
            fixes.append(f'修复difficulty: "{old_diff}" -> "{expected_difficulty}"')

    # 5. 确保topology_subtype正确
    if spatial_type != 'topological' and 'topology_subtype' in fixed:
        del fixed['topology_subtype']
        fixes.append('移除非topological类型的topology_subtype字段')

    return fixed, fixes


# ============== 主函数 ==============

def validate_record(record: dict) -> Tuple[List[ValidationError], bool]:
    """校验单条记录"""
    errors = []

    # L0: 字段标准化检查
    errors.extend(validate_extra_fields(record))

    # L1: 基础字段
    errors.extend(validate_basic_fields(record))

    # L2: 推理链
    errors.extend(validate_reasoning_chain(record))

    # L3: 实体
    errors.extend(validate_entities(record))

    # L4: Token映射
    errors.extend(validate_tokens(record))

    # L4.5: Answer与推理链一致性
    errors.extend(validate_answer_reasoning_consistency(record))

    # L5: 难度评分
    errors.extend(validate_difficulty(record))

    # 判断是否需要修复
    has_critical = any(e.severity == 'critical' for e in errors)

    return errors, has_critical


def validate_dataset(
    input_file: str,
    output_file: str,
    issues_file: str,
    report_file: str,
    auto_fix: bool = True
) -> Dict[str, Any]:
    """
    校验整个数据集

    Args:
        input_file: 输入JSONL文件路径
        output_file: 输出JSONL文件路径（修复后）
        issues_file: 问题清单JSONL文件路径
        report_file: 校验报告Markdown文件路径
        auto_fix: 是否自动修复

    Returns:
        校验统计信息
    """
    stats = ValidationStats()
    all_errors = []
    fixed_records = []
    issues_records = []

    print(f"开始校验: {input_file}")

    # 读取数据
    with open(input_file, 'r', encoding='utf-8') as f:
        records = [json.loads(line) for line in f if line.strip()]

    stats.total_records = len(records)
    print(f"总记录数: {stats.total_records}")

    # 逐条校验
    for i, record in enumerate(records):
        if (i + 1) % 1000 == 0:
            print(f"校验进度: {i + 1}/{stats.total_records}")

        errors, has_critical = validate_record(record)

        if errors:
            all_errors.extend(errors)
            stats.invalid_records += 1

            # 记录问题
            issues_records.append({
                'record_id': record.get('id', f'line_{i+1}'),
                'error_count': len(errors),
                'critical_count': sum(1 for e in errors if e.severity == 'critical'),
                'errors': [e.to_dict() for e in errors]
            })

            # 尝试修复
            if auto_fix and (has_critical or any(e.severity == 'warning' for e in errors)):
                fixed_record, fixes = fix_record(record, errors)
                if fixes:
                    fixed_records.append(fixed_record)
                    stats.fixed_records += 1
                    issues_records[-1]['fixes'] = fixes
                else:
                    fixed_records.append(record)
            else:
                fixed_records.append(record)
        else:
            stats.valid_records += 1
            fixed_records.append(record)

        # 统计错误
        for error in errors:
            stats.errors_by_level[error.level] += 1
            stats.errors_by_field[error.field] += 1
            stats.errors_by_severity[error.severity] += 1

    # L6: 分布校验
    distribution = validate_distribution(fixed_records)

    # 计算有效记录数（修复后）
    if auto_fix:
        stats.valid_records = stats.total_records - stats.invalid_records + stats.fixed_records

    # 写入输出文件
    print(f"写入修复后数据: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in fixed_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    # 写入问题清单
    print(f"写入问题清单: {issues_file}")
    with open(issues_file, 'w', encoding='utf-8') as f:
        for issue in issues_records:
            f.write(json.dumps(issue, ensure_ascii=False) + '\n')

    # 生成报告
    report = generate_report(stats, distribution, all_errors, input_file, output_file)
    print(f"写入校验报告: {report_file}")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    return {
        'stats': {
            'total_records': stats.total_records,
            'valid_records': stats.valid_records,
            'invalid_records': stats.invalid_records,
            'fixed_records': stats.fixed_records,
            'errors_by_level': dict(stats.errors_by_level),
            'errors_by_severity': dict(stats.errors_by_severity)
        },
        'distribution': distribution
    }


def generate_report(
    stats: ValidationStats,
    distribution: Dict,
    errors: List[ValidationError],
    input_file: str,
    output_file: str
) -> str:
    """生成Markdown格式校验报告"""

    report = f"""# GeoKD-SR 数据校验报告

> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **输入文件**: {input_file}
> **输出文件**: {output_file}

---

## 一、校验概览

| 指标 | 值 |
|------|-----|
| **总记录数** | {stats.total_records:,} |
| **有效记录** | {stats.valid_records:,} ({stats.valid_records/stats.total_records*100:.1f}%) |
| **无效记录** | {stats.invalid_records:,} ({stats.invalid_records/stats.total_records*100:.1f}%) |
| **修复记录** | {stats.fixed_records:,} |

---

## 二、错误统计

### 2.1 按校验层级

| 层级 | 错误数 | 说明 |
|------|--------|------|
"""

    for level in ['L1', 'L2', 'L3', 'L4', 'L4.5', 'L5', 'L6']:
        count = stats.errors_by_level.get(level, 0)
        descriptions = {
            'L1': '基础字段格式',
            'L2': '推理链结构',
            'L3': '实体数组',
            'L4': 'Token映射',
            'L4.5': 'Answer与推理链一致性',
            'L5': '难度评分',
            'L6': '分布校验'
        }
        report += f"| {level} | {count:,} | {descriptions.get(level, '')} |\n"

    report += f"""
### 2.2 按严重程度

| 严重程度 | 错误数 |
|---------|--------|
| 🔴 Critical | {stats.errors_by_severity.get('critical', 0):,} |
| 🟡 Warning | {stats.errors_by_severity.get('warning', 0):,} |
| ℹ️ Info | {stats.errors_by_severity.get('info', 0):,} |

### 2.3 按字段统计 (Top 10)

| 字段 | 错误数 |
|------|--------|
"""

    sorted_fields = sorted(stats.errors_by_field.items(), key=lambda x: -x[1])[:10]
    for field, count in sorted_fields:
        report += f"| {field} | {count:,} |\n"

    report += """
---

## 三、分布校验

### 3.1 空间关系类型分布

| 类型 | 数量 | 实际占比 | 目标占比 | 偏差 | 状态 |
|------|------|---------|---------|------|------|
"""

    for rel_type in ['directional', 'topological', 'metric', 'composite']:
        info = distribution['spatial_relation_type'].get(rel_type, {})
        status = '✅' if info.get('pass', True) else '⚠️'
        report += f"| {rel_type} | {info.get('count', 0):,} | {info.get('actual_ratio', 0)*100:.1f}% | {info.get('target_ratio', 0)*100:.1f}% | {info.get('deviation', 0)*100:.1f}% | {status} |\n"

    report += """
### 3.2 难度分布

| 难度 | 数量 | 实际占比 | 目标占比 | 偏差 | 状态 |
|------|------|---------|---------|------|------|
"""

    for diff in ['easy', 'medium', 'hard']:
        info = distribution['difficulty'].get(diff, {})
        status = '✅' if info.get('pass', True) else '⚠️'
        report += f"| {diff} | {info.get('count', 0):,} | {info.get('actual_ratio', 0)*100:.1f}% | {info.get('target_ratio', 0)*100:.1f}% | {info.get('deviation', 0)*100:.1f}% | {status} |\n"

    if distribution['topology_subtype']:
        report += """
### 3.3 拓扑子类型分布 (仅topological类型)

| 子类型 | 数量 | 实际占比 | 目标占比 | 偏差 | 状态 |
|--------|------|---------|---------|------|------|
"""
        for subtype in ['within', 'contains', 'adjacent', 'disjoint', 'overlap']:
            info = distribution['topology_subtype'].get(subtype, {})
            status = '✅' if info.get('pass', True) else '⚠️'
            report += f"| {subtype} | {info.get('count', 0):,} | {info.get('actual_ratio', 0)*100:.1f}% | {info.get('target_ratio', 0)*100:.1f}% | {info.get('deviation', 0)*100:.1f}% | {status} |\n"

    report += """
---

## 四、修复说明

本次校验执行了以下自动修复操作：

1. **字段标准化**: 移除所有非标准字段（如 `_validation_errors`, `_fixed` 等）
2. **final_answer一致性**: 使用answer覆盖final_answer
3. **方向关系修复**: 根据坐标重新计算方向，更新answer和calculation_result
4. **度量关系修复**: 根据坐标重新计算距离，更新answer和calculation_result
5. **difficulty映射修复**: 根据difficulty_score重新映射difficulty

---

## 五、后续建议

"""

    # 根据错误情况给出建议
    if stats.errors_by_severity.get('critical', 0) > 0:
        report += "⚠️ **存在严重错误**: 建议优先修复critical级别的问题\n\n"

    if stats.errors_by_level.get('L4.5', 0) > 100:
        report += "⚠️ **Answer与推理链一致性问题较多**: 建议检查数据生成逻辑\n\n"

    if not all(distribution['spatial_relation_type'].get(t, {}).get('pass', True) for t in ['directional', 'topological', 'metric', 'composite']):
        report += "⚠️ **空间关系类型分布偏差**: 建议调整数据采样策略\n\n"

    report += f"""
---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    return report


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 数据字段综合校验')
    parser.add_argument('--input', '-i', required=True, help='输入JSONL文件路径')
    parser.add_argument('--output', '-o', required=True, help='输出JSONL文件路径')
    parser.add_argument('--issues', default=None, help='问题清单输出路径')
    parser.add_argument('--report', '-r', default=None, help='校验报告输出路径')
    parser.add_argument('--no-fix', action='store_true', help='不执行自动修复')

    args = parser.parse_args()

    # 设置默认路径
    input_path = Path(args.input)
    output_dir = input_path.parent

    if args.output is None:
        args.output = str(output_dir / f"{input_path.stem}_validated.jsonl")
    if args.issues is None:
        args.issues = str(output_dir / f"{input_path.stem}_issues.jsonl")
    if args.report is None:
        args.report = str(output_dir.parent / 'reports' / f"{input_path.stem}_validation_report.md")

    # 确保输出目录存在
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.issues).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)

    # 执行校验
    result = validate_dataset(
        input_file=args.input,
        output_file=args.output,
        issues_file=args.issues,
        report_file=args.report,
        auto_fix=not args.no_fix
    )

    print("\n" + "="*50)
    print("校验完成!")
    print(f"  总记录数: {result['stats']['total_records']:,}")
    print(f"  有效记录: {result['stats']['valid_records']:,}")
    print(f"  无效记录: {result['stats']['invalid_records']:,}")
    print(f"  修复记录: {result['stats']['fixed_records']:,}")
    print(f"\n输出文件:")
    print(f"  修复后数据: {args.output}")
    print(f"  问题清单: {args.issues}")
    print(f"  校验报告: {args.report}")
    print("="*50)


if __name__ == '__main__':
    main()
