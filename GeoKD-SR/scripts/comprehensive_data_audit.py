#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GeoKD-SR 数据全面多维深度审查脚本

功能：
1. L1-L6 格式验证
2. difficulty_score 计算验证
3. difficulty 映射验证
4. 数据分布验证
5. 问句类型统计
6. 内容质量验证
7. 实验兼容性验证

版本: V1.0
日期: 2026-03-13
"""

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import argparse


class GeoKDDataAuditor:
    """GeoKD-SR 数据审查器"""

    # 中国境内坐标范围
    CHINA_LON_RANGE = (73.0, 135.0)
    CHINA_LAT_RANGE = (18.0, 54.0)

    # 空间关系类型
    SPATIAL_TYPES = ["directional", "topological", "metric", "composite"]

    # 拓扑子类型
    TOPOLOGY_SUBTYPES = ["within", "contains", "adjacent", "disjoint", "overlap"]

    # 难度级别
    DIFFICULTY_LEVELS = ["easy", "medium", "hard"]

    # 实体类型
    ENTITY_TYPES = ["city", "province", "landmark", "river", "mountain", "lake", "region"]

    # 必需字段
    REQUIRED_FIELDS = [
        "id", "spatial_relation_type", "question", "answer",
        "reasoning_chain", "entities", "spatial_tokens",
        "difficulty", "difficulty_score", "split"
    ]

    # 条件必需字段
    CONDITIONAL_FIELDS = {
        "topology_subtype": lambda r: r.get("spatial_relation_type") == "topological",
        "entity_to_token": lambda r: "reasoning_chain" in r
    }

    # 难度评分基础分
    BASE_SCORES = {
        "directional": 1.2,
        "topological": 2.2,
        "metric": 1.3,
        "composite": 3.2
    }

    # 拓扑子类型加成
    TOPOLOGY_BONUS = {
        "within": 0.0,
        "contains": 0.1,
        "adjacent": 0.3,
        "disjoint": 0.4,
        "overlap": 0.6
    }

    # 实体类型对加成
    ENTITY_BONUS = {
        ("city", "city"): 0.0,
        ("city", "landmark"): 0.2,
        ("landmark", "landmark"): 0.3,
        ("province", "city"): 0.4,
        ("city", "province"): 0.4,
        ("river", "city"): 0.7,
        ("mountain", "city"): 0.7,
        ("region", "city"): 0.9,
    }

    def __init__(self, data_path: str):
        """初始化审查器"""
        self.data_path = data_path
        self.data: List[Dict] = []
        self.issues: Dict[str, List[Dict]] = defaultdict(list)
        self.stats: Dict[str, Any] = {}

    def load_data(self) -> int:
        """加载数据"""
        print(f"[INFO] 正在加载数据: {self.data_path}")
        errors = []
        with open(self.data_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    record['_line_num'] = line_num
                    self.data.append(record)
                except json.JSONDecodeError as e:
                    errors.append({
                        "line": line_num,
                        "error": str(e),
                        "content_preview": line[:100]
                    })

        if errors:
            self.issues["L1_JSON_PARSE_ERROR"] = errors

        print(f"[INFO] 成功加载 {len(self.data)} 条记录")
        if errors:
            print(f"[WARN] JSON解析失败 {len(errors)} 条")
        return len(self.data)

    # ==================== L1-L2 格式验证 ====================

    def validate_l1_required_fields(self) -> Dict:
        """L1: 必需字段完整性验证"""
        results = {
            "total": len(self.data),
            "pass": 0,
            "fail": 0,
            "missing_fields": defaultdict(list)
        }

        for record in self.data:
            missing = []
            for field in self.REQUIRED_FIELDS:
                if field not in record:
                    missing.append(field)

            # 检查条件必需字段
            for field, condition in self.CONDITIONAL_FIELDS.items():
                if condition(record) and field not in record:
                    missing.append(field)

            if missing:
                results["fail"] += 1
                for field in missing:
                    results["missing_fields"][field].append({
                        "id": record.get("id", "unknown"),
                        "line": record.get("_line_num", 0)
                    })
            else:
                results["pass"] += 1

        results["pass_rate"] = results["pass"] / results["total"] * 100 if results["total"] > 0 else 0
        return results

    def validate_l2_field_types(self) -> Dict:
        """L2: 字段类型验证"""
        results = {
            "total": len(self.data),
            "pass": 0,
            "fail": 0,
            "type_errors": defaultdict(list)
        }

        type_specs = {
            "id": str,
            "spatial_relation_type": str,
            "topology_subtype": str,
            "question": str,
            "answer": str,
            "reasoning_chain": list,
            "entities": list,
            "spatial_tokens": list,
            "entity_to_token": dict,
            "difficulty": str,
            "difficulty_score": (int, float),
            "split": str
        }

        for record in self.data:
            errors = []
            for field, expected_type in type_specs.items():
                if field in record and record[field] is not None:
                    if not isinstance(record[field], expected_type):
                        errors.append(f"{field}: expected {expected_type}, got {type(record[field]).__name__}")

            if errors:
                results["fail"] += 1
                results["type_errors"][record.get("id", "unknown")] = errors
            else:
                results["pass"] += 1

        results["pass_rate"] = results["pass"] / results["total"] * 100 if results["total"] > 0 else 0
        return results

    # ==================== L3 推理链验证 ====================

    def validate_l3_reasoning_chain(self) -> Dict:
        """L3: 推理链5步结构验证"""
        results = {
            "total": len(self.data),
            "pass": 0,
            "fail": 0,
            "issues": []
        }

        required_keys = ["step", "name", "action", "content"]
        step_names = [
            "entity_identification",
            "spatial_relation_extraction",
            "coordinate_retrieval",
            "spatial_calculation",
            "answer_generation"
        ]

        for record in self.data:
            chain = record.get("reasoning_chain", [])
            issues = []

            # 检查是否为5步
            if not isinstance(chain, list):
                issues.append("reasoning_chain不是列表")
            elif len(chain) != 5:
                issues.append(f"推理链长度为{len(chain)}，应为5")
            else:
                # 检查每步结构
                for i, step in enumerate(chain):
                    if not isinstance(step, dict):
                        issues.append(f"步骤{i+1}不是字典")
                        continue

                    # 检查必需字段
                    missing_keys = [k for k in required_keys if k not in step]
                    if missing_keys:
                        issues.append(f"步骤{i+1}缺少字段: {missing_keys}")

                    # 检查step序号
                    if step.get("step") != i + 1:
                        issues.append(f"步骤{i+1}的step值不正确: {step.get('step')}")

            if issues:
                results["fail"] += 1
                results["issues"].append({
                    "id": record.get("id", "unknown"),
                    "line": record.get("_line_num", 0),
                    "issues": issues
                })
            else:
                results["pass"] += 1

        results["pass_rate"] = results["pass"] / results["total"] * 100 if results["total"] > 0 else 0
        return results

    # ==================== L4 坐标验证 ====================

    def validate_l4_coordinates(self) -> Dict:
        """L4: 实体坐标验证"""
        results = {
            "total": len(self.data),
            "pass": 0,
            "fail": 0,
            "issues": [],
            "out_of_range": []
        }

        for record in self.data:
            entities = record.get("entities", [])
            issues = []

            if not isinstance(entities, list):
                issues.append("entities不是列表")
            elif len(entities) < 2:
                issues.append(f"实体数量为{len(entities)}，应≥2")
            else:
                for entity in entities:
                    if not isinstance(entity, dict):
                        issues.append(f"实体不是字典: {entity}")
                        continue

                    # 检查必需字段
                    if "name" not in entity:
                        issues.append("实体缺少name字段")
                    if "type" not in entity:
                        issues.append(f"实体{entity.get('name', 'unknown')}缺少type字段")

                    # 检查坐标
                    coords = entity.get("coords")
                    if coords is None:
                        issues.append(f"实体{entity.get('name', 'unknown')}缺少coords")
                    elif not isinstance(coords, list) or len(coords) != 2:
                        issues.append(f"实体{entity.get('name', 'unknown')}坐标格式错误: {coords}")
                    else:
                        lon, lat = coords[0], coords[1]
                        # 验证是否在中国境内
                        if not (self.CHINA_LON_RANGE[0] <= lon <= self.CHINA_LON_RANGE[1]):
                            issues.append(f"实体{entity.get('name', 'unknown')}经度{lon}超出中国范围")
                            results["out_of_range"].append({
                                "id": record.get("id"),
                                "entity": entity.get("name"),
                                "coords": coords,
                                "issue": "经度超出范围"
                            })
                        if not (self.CHINA_LAT_RANGE[0] <= lat <= self.CHINA_LAT_RANGE[1]):
                            issues.append(f"实体{entity.get('name', 'unknown')}纬度{lat}超出中国范围")
                            results["out_of_range"].append({
                                "id": record.get("id"),
                                "entity": entity.get("name"),
                                "coords": coords,
                                "issue": "纬度超出范围"
                            })

            if issues:
                results["fail"] += 1
                results["issues"].append({
                    "id": record.get("id", "unknown"),
                    "line": record.get("_line_num", 0),
                    "issues": issues
                })
            else:
                results["pass"] += 1

        results["pass_rate"] = results["pass"] / results["total"] * 100 if results["total"] > 0 else 0
        return results

    # ==================== L5 Token映射验证 ====================

    def validate_l5_entity_to_token(self) -> Dict:
        """L5: entity_to_token映射验证"""
        results = {
            "total": len(self.data),
            "pass": 0,
            "fail": 0,
            "issues": []
        }

        for record in self.data:
            mapping = record.get("entity_to_token", {})
            entities = record.get("entities", [])
            question = record.get("question", "")
            issues = []

            if not isinstance(mapping, dict):
                issues.append("entity_to_token不是字典")
            elif not mapping:
                issues.append("entity_to_token为空")
            else:
                for entity in entities:
                    name = entity.get("name")
                    if name and name not in mapping:
                        issues.append(f"实体'{name}'未在entity_to_token中")
                    elif name in mapping:
                        token_info = mapping[name]
                        if not isinstance(token_info, dict):
                            issues.append(f"实体'{name}'的映射信息不是字典")
                        else:
                            # 检查必需字段
                            for field in ["char_start", "char_end", "token_indices"]:
                                if field not in token_info:
                                    issues.append(f"实体'{name}'缺少{field}字段")

                            # 验证字符位置是否正确
                            char_start = token_info.get("char_start", 0)
                            char_end = token_info.get("char_end", 0)
                            if char_start < 0 or char_end > len(question):
                                issues.append(f"实体'{name}'字符位置超出范围")
                            elif char_end <= char_start:
                                issues.append(f"实体'{name}'char_end<=char_start")

            if issues:
                results["fail"] += 1
                results["issues"].append({
                    "id": record.get("id", "unknown"),
                    "line": record.get("_line_num", 0),
                    "issues": issues
                })
            else:
                results["pass"] += 1

        results["pass_rate"] = results["pass"] / results["total"] * 100 if results["total"] > 0 else 0
        return results

    # ==================== difficulty_score 计算验证 ====================

    def calculate_theoretical_score(self, record: Dict) -> float:
        """根据规范V2.0计算理论difficulty_score"""
        spatial_type = record.get("spatial_relation_type")
        topology_subtype = record.get("topology_subtype")
        entities = record.get("entities", [])

        # 获取基础分
        score = self.BASE_SCORES.get(spatial_type, 2.0)

        # 拓扑子类型加成
        if topology_subtype and topology_subtype in self.TOPOLOGY_BONUS:
            score += self.TOPOLOGY_BONUS[topology_subtype]

        # 实体类型加成
        if len(entities) >= 2:
            types = sorted([e.get("type", "city") for e in entities[:2]])
            type_key = tuple(types)
            score += self.ENTITY_BONUS.get(type_key, 0.5)

        # 实体数量加成
        entity_count = len(entities)
        score += max(0, (entity_count - 2) * 0.3)

        return min(max(score, 1.0), 5.0)

    def validate_difficulty_score(self) -> Dict:
        """验证difficulty_score计算正确性"""
        results = {
            "total": len(self.data),
            "pass": 0,
            "fail": 0,
            "deviations": [],
            "stats": {
                "mean_deviation": 0,
                "max_deviation": 0,
                "within_tolerance": 0
            }
        }

        tolerance = 0.5  # 允许误差范围
        deviations = []

        for record in self.data:
            actual_score = record.get("difficulty_score")
            theoretical_score = self.calculate_theoretical_score(record)

            if actual_score is None:
                results["fail"] += 1
                results["deviations"].append({
                    "id": record.get("id"),
                    "actual": None,
                    "theoretical": round(theoretical_score, 2),
                    "deviation": None,
                    "issue": "缺少difficulty_score"
                })
                continue

            deviation = abs(actual_score - theoretical_score)
            deviations.append(deviation)

            if deviation > tolerance:
                results["fail"] += 1
                results["deviations"].append({
                    "id": record.get("id"),
                    "actual": actual_score,
                    "theoretical": round(theoretical_score, 2),
                    "deviation": round(deviation, 2),
                    "issue": f"偏差{round(deviation, 2)}超过容忍度{tolerance}"
                })
            else:
                results["pass"] += 1

        if deviations:
            results["stats"]["mean_deviation"] = round(sum(deviations) / len(deviations), 3)
            results["stats"]["max_deviation"] = round(max(deviations), 3)
            results["stats"]["within_tolerance"] = sum(1 for d in deviations if d <= tolerance)

        results["pass_rate"] = results["pass"] / results["total"] * 100 if results["total"] > 0 else 0
        return results

    # ==================== difficulty 映射验证 ====================

    def validate_difficulty_mapping(self) -> Dict:
        """验证difficulty与difficulty_score的对应关系"""
        results = {
            "total": len(self.data),
            "pass": 0,
            "fail": 0,
            "mismatches": []
        }

        # 难度范围定义
        difficulty_ranges = {
            "easy": (1.0, 2.0),
            "medium": (2.0, 3.5),
            "hard": (3.5, 5.0)
        }

        for record in self.data:
            difficulty = record.get("difficulty")
            score = record.get("difficulty_score")

            if difficulty not in self.DIFFICULTY_LEVELS:
                results["fail"] += 1
                results["mismatches"].append({
                    "id": record.get("id"),
                    "difficulty": difficulty,
                    "score": score,
                    "issue": f"无效的difficulty值: {difficulty}"
                })
                continue

            if score is None:
                continue

            range_min, range_max = difficulty_ranges.get(difficulty, (1.0, 5.0))

            # 特殊处理边界情况
            if difficulty == "easy" and score > 2.0:
                results["fail"] += 1
                results["mismatches"].append({
                    "id": record.get("id"),
                    "difficulty": difficulty,
                    "score": score,
                    "expected_range": f"{range_min}-{range_max}",
                    "issue": "easy的score应≤2.0"
                })
            elif difficulty == "medium" and (score <= 2.0 or score > 3.5):
                results["fail"] += 1
                results["mismatches"].append({
                    "id": record.get("id"),
                    "difficulty": difficulty,
                    "score": score,
                    "expected_range": f"{range_min}-{range_max}",
                    "issue": "medium的score应在(2.0, 3.5]"
                })
            elif difficulty == "hard" and score <= 3.5:
                results["fail"] += 1
                results["mismatches"].append({
                    "id": record.get("id"),
                    "difficulty": difficulty,
                    "score": score,
                    "expected_range": f"{range_min}-{range_max}",
                    "issue": "hard的score应>3.5"
                })
            else:
                results["pass"] += 1

        results["pass_rate"] = results["pass"] / results["total"] * 100 if results["total"] > 0 else 0
        return results

    # ==================== L6 分布验证 ====================

    def validate_distribution(self) -> Dict:
        """验证数据分布"""
        results = {
            "spatial_relation_type": {},
            "difficulty": {},
            "topology_subtype": {},
            "pass": True
        }

        # 目标分布
        targets = {
            "spatial_relation_type": {
                "directional": (25, 5),  # (目标%, 允许偏差%)
                "topological": (27.5, 5),
                "metric": (27.5, 5),
                "composite": (20, 5)
            },
            "difficulty": {
                "easy": (30, 5),
                "medium": (50, 5),
                "hard": (20, 5)
            },
            "topology_subtype": {
                "within": (20, 5),
                "contains": (20, 5),
                "adjacent": (20, 5),
                "disjoint": (20, 5),
                "overlap": (20, 5)
            }
        }

        # 统计空间关系类型分布
        type_counts = Counter(r.get("spatial_relation_type") for r in self.data)
        total = len(self.data)
        for rel_type, count in type_counts.items():
            actual_pct = count / total * 100
            target, tolerance = targets["spatial_relation_type"].get(rel_type, (25, 10))
            deviation = abs(actual_pct - target)
            results["spatial_relation_type"][rel_type] = {
                "count": count,
                "actual_pct": round(actual_pct, 2),
                "target_pct": target,
                "deviation": round(deviation, 2),
                "pass": deviation <= tolerance
            }
            if deviation > tolerance:
                results["pass"] = False

        # 统计难度分布
        diff_counts = Counter(r.get("difficulty") for r in self.data)
        for diff, count in diff_counts.items():
            actual_pct = count / total * 100
            target, tolerance = targets["difficulty"].get(diff, (30, 10))
            deviation = abs(actual_pct - target)
            results["difficulty"][diff] = {
                "count": count,
                "actual_pct": round(actual_pct, 2),
                "target_pct": target,
                "deviation": round(deviation, 2),
                "pass": deviation <= tolerance
            }
            if deviation > tolerance:
                results["pass"] = False

        # 统计拓扑子类型分布（仅topological类型）
        topo_records = [r for r in self.data if r.get("spatial_relation_type") == "topological"]
        if topo_records:
            topo_counts = Counter(r.get("topology_subtype") for r in topo_records)
            topo_total = len(topo_records)
            for subtype, count in topo_counts.items():
                actual_pct = count / topo_total * 100
                target, tolerance = targets["topology_subtype"].get(subtype, (20, 10))
                deviation = abs(actual_pct - target)
                results["topology_subtype"][subtype] = {
                    "count": count,
                    "actual_pct": round(actual_pct, 2),
                    "target_pct": target,
                    "deviation": round(deviation, 2),
                    "pass": deviation <= tolerance
                }
                if deviation > tolerance:
                    results["pass"] = False

        return results

    # ==================== 问句类型统计 ====================

    def analyze_question_types(self) -> Dict:
        """分析问句类型分布"""
        # 使用普通dict存储，结构为 {"问句类型": {"count": 0, "examples": []}}
        by_type: Dict[str, Dict] = {}
        by_spatial_type: Dict[str, Dict[str, int]] = {}

        # 问句类型特征词
        patterns = {
            "是非问句": [r"是否", r"是不是", r"有没有", r"吗[？?]$"],
            "特指问句": [r"什么", r"哪里", r"哪个", r"多少", r"多远", r"如何"],
            "选择问句": [r"还是", r"A还是B", r"或者"],
            "正反问句": [r"是不是", r"有没有"],
            "描述问句": [r"描述", r"说明", r"解释", r"分析"]
        }

        # 初始化所有类型
        for q_type in list(patterns.keys()) + ["其他"]:
            by_type[q_type] = {"count": 0, "examples": []}

        anomalies = []

        for record in self.data:
            question = record.get("question", "")
            spatial_type = record.get("spatial_relation_type", "unknown")

            # 初始化spatial_type的dict
            if spatial_type not in by_spatial_type:
                by_spatial_type[spatial_type] = {}

            matched = False
            for q_type, pattern_list in patterns.items():
                for pattern in pattern_list:
                    if re.search(pattern, question):
                        by_type[q_type]["count"] += 1
                        if len(by_type[q_type]["examples"]) < 5:  # 只保留5个示例
                            by_type[q_type]["examples"].append(question[:50])
                        by_spatial_type[spatial_type][q_type] = by_spatial_type[spatial_type].get(q_type, 0) + 1
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                by_type["其他"]["count"] += 1
                if len(by_type["其他"]["examples"]) < 5:
                    by_type["其他"]["examples"].append(question[:50])
                by_spatial_type[spatial_type]["其他"] = by_spatial_type[spatial_type].get("其他", 0) + 1

            # 检查异常问句（太短或太长）
            if len(question) < 10:
                anomalies.append({
                    "id": record.get("id"),
                    "question": question,
                    "issue": "问句过短(<10字符)"
                })
            elif len(question) > 150:
                anomalies.append({
                    "id": record.get("id"),
                    "question": question[:100],
                    "issue": "问句过长(>150字符)"
                })

        return {
            "total": len(self.data),
            "by_type": by_type,
            "by_spatial_type": by_spatial_type,
            "anomalies": anomalies[:100]  # 只保留前100个异常
        }

    # ==================== 实验兼容性验证 ====================

    def validate_experiment_compatibility(self) -> Dict:
        """验证数据对各实验的兼容性"""
        results = {
            "total": len(self.data),
            "experiments": {}
        }

        # 实验字段需求
        exp_requirements = {
            "Exp1_Direct_SFT": ["question", "answer"],
            "Exp2_Standard_KD": ["question", "answer"],
            "Exp3a_Uniform_KD": ["question", "answer", "spatial_relation_type"],
            "Exp3_Learnable_KD": ["question", "answer", "spatial_relation_type"],
            "Exp4_Reasoning_KD": ["question", "answer", "reasoning_chain"],
            "Exp5_Reverse_KL": ["question", "answer"],
            "Exp6_Self_Distill": ["question", "answer"],
            "Exp7_Attention_KD": ["question", "answer", "entities", "spatial_tokens", "entity_to_token"],
            "Exp8_Progressive_KD": ["question", "answer", "spatial_relation_type", "difficulty", "difficulty_score"],
            "Exp9_GeoKD_SR": ["question", "answer", "spatial_relation_type", "reasoning_chain",
                            "entities", "spatial_tokens", "entity_to_token", "difficulty", "difficulty_score"]
        }

        for exp_name, required_fields in exp_requirements.items():
            compatible = 0
            incompatible_records = []

            for record in self.data:
                is_compatible = True
                missing = []
                for field in required_fields:
                    if field not in record or record[field] is None:
                        is_compatible = False
                        missing.append(field)
                    elif field == "reasoning_chain" and len(record.get("reasoning_chain", [])) != 5:
                        is_compatible = False
                        missing.append(f"{field}(非5步)")

                if is_compatible:
                    compatible += 1
                else:
                    if len(incompatible_records) < 10:  # 只保存前10条不兼容记录
                        incompatible_records.append({
                            "id": record.get("id"),
                            "missing_fields": missing
                        })

            results["experiments"][exp_name] = {
                "compatible": compatible,
                "incompatible": len(self.data) - compatible,
                "compatibility_rate": round(compatible / len(self.data) * 100, 2) if self.data else 0,
                "sample_incompatible": incompatible_records
            }

        return results

    # ==================== 内容质量验证 ====================

    def validate_content_quality(self) -> Dict:
        """验证内容质量"""
        results = {
            "total": len(self.data),
            "entity_consistency": {"pass": 0, "fail": 0, "issues": []},
            "answer_quality": {"pass": 0, "fail": 0, "issues": []},
            "coordinate_accuracy": {"pass": 0, "fail": 0, "issues": []}
        }

        for record in self.data:
            # 1. 实体一致性检查
            entities = record.get("entities", [])
            chain = record.get("reasoning_chain", [])

            entity_names = set(e.get("name") for e in entities if isinstance(e, dict))

            # 从推理链中提取实体
            chain_entities = set()
            for step in chain:
                involved = step.get("entities_involved", [])
                if isinstance(involved, list):
                    chain_entities.update(involved)

            if entity_names != chain_entities and chain_entities:
                results["entity_consistency"]["fail"] += 1
                if len(results["entity_consistency"]["issues"]) < 20:
                    results["entity_consistency"]["issues"].append({
                        "id": record.get("id"),
                        "entities": list(entity_names),
                        "chain_entities": list(chain_entities),
                        "issue": "entities与reasoning_chain中的实体不一致"
                    })
            else:
                results["entity_consistency"]["pass"] += 1

            # 2. 答案质量检查
            answer = record.get("answer", "")
            if len(answer) < 2 or len(answer) > 100:
                results["answer_quality"]["fail"] += 1
                if len(results["answer_quality"]["issues"]) < 20:
                    results["answer_quality"]["issues"].append({
                        "id": record.get("id"),
                        "answer": answer[:50],
                        "issue": f"答案长度异常({len(answer)}字符)"
                    })
            else:
                results["answer_quality"]["pass"] += 1

            # 3. 坐标准确性检查（已在中国范围内）
            coords_valid = True
            for entity in entities:
                coords = entity.get("coords")
                if coords and isinstance(coords, list) and len(coords) == 2:
                    lon, lat = coords[0], coords[1]
                    if not (self.CHINA_LON_RANGE[0] <= lon <= self.CHINA_LON_RANGE[1] and
                            self.CHINA_LAT_RANGE[0] <= lat <= self.CHINA_LAT_RANGE[1]):
                        coords_valid = False
                        break

            if coords_valid:
                results["coordinate_accuracy"]["pass"] += 1
            else:
                results["coordinate_accuracy"]["fail"] += 1

        return results

    # ==================== 生成报告 ====================

    def generate_report(self, output_dir: str) -> Tuple[str, str]:
        """生成审查报告"""
        os.makedirs(output_dir, exist_ok=True)

        # 执行所有验证
        print("\n[INFO] 开始执行验证...")

        print("  - L1: 必需字段验证...")
        l1_results = self.validate_l1_required_fields()

        print("  - L2: 字段类型验证...")
        l2_results = self.validate_l2_field_types()

        print("  - L3: 推理链验证...")
        l3_results = self.validate_l3_reasoning_chain()

        print("  - L4: 坐标验证...")
        l4_results = self.validate_l4_coordinates()

        print("  - L5: Token映射验证...")
        l5_results = self.validate_l5_entity_to_token()

        print("  - difficulty_score验证...")
        score_results = self.validate_difficulty_score()

        print("  - difficulty映射验证...")
        mapping_results = self.validate_difficulty_mapping()

        print("  - L6: 分布验证...")
        dist_results = self.validate_distribution()

        print("  - 问句类型统计...")
        question_results = self.analyze_question_types()

        print("  - 实验兼容性验证...")
        exp_results = self.validate_experiment_compatibility()

        print("  - 内容质量验证...")
        quality_results = self.validate_content_quality()

        # 生成Markdown报告
        report_path = os.path.join(output_dir, "data_audit_report_final_1_v4.md")
        md_content = self._generate_markdown_report(
            l1_results, l2_results, l3_results, l4_results, l5_results,
            score_results, mapping_results, dist_results, question_results,
            exp_results, quality_results
        )

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        # 生成问题清单JSON
        issues_path = os.path.join(output_dir, "data_audit_issues_final_1_v4.json")
        all_issues = {
            "metadata": {
                "data_file": self.data_path,
                "total_records": len(self.data),
                "audit_time": datetime.now().isoformat(),
                "script_version": "V1.0"
            },
            "L1_required_fields": l1_results.get("missing_fields", {}),
            "L2_type_errors": l2_results.get("type_errors", {}),
            "L3_reasoning_chain": l3_results.get("issues", [])[:100],  # 限制数量
            "L4_coordinates": l4_results.get("issues", [])[:100],
            "L4_out_of_range": l4_results.get("out_of_range", [])[:50],
            "L5_entity_to_token": l5_results.get("issues", [])[:100],
            "difficulty_score_deviations": score_results.get("deviations", [])[:100],
            "difficulty_mapping_mismatches": mapping_results.get("mismatches", [])[:100],
            "question_anomalies": question_results.get("anomalies", [])[:50],
            "entity_consistency_issues": quality_results.get("entity_consistency", {}).get("issues", [])[:50]
        }

        with open(issues_path, 'w', encoding='utf-8') as f:
            json.dump(all_issues, f, ensure_ascii=False, indent=2)

        print(f"\n[INFO] 报告已生成:")
        print(f"  - Markdown报告: {report_path}")
        print(f"  - 问题清单JSON: {issues_path}")

        return report_path, issues_path

    def _generate_markdown_report(self, l1, l2, l3, l4, l5, score, mapping,
                                   dist, question, exp, quality) -> str:
        """生成Markdown格式报告"""
        md = f"""# GeoKD-SR 数据深度审查报告

> **审查文件**: `{os.path.basename(self.data_path)}`
> **审查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **记录总数**: {len(self.data)}
> **脚本版本**: V1.0

---

## 1. 数据概览

| 指标 | 值 |
|------|-----|
| 总记录数 | {len(self.data)} |
| 文件大小 | {os.path.getsize(self.data_path) / 1024 / 1024:.2f} MB |

---

## 2. 格式验证结果（L1-L6）

### 2.1 L1 必需字段验证

| 指标 | 结果 |
|------|------|
| 通过/总数 | {l1['pass']}/{l1['total']} |
| 通过率 | {l1['pass_rate']:.2f}% |
| 失败数 | {l1['fail']} |

"""
        if l1['missing_fields']:
            md += "**缺失字段统计**:\n\n"
            for field, records in l1['missing_fields'].items():
                md += f"- `{field}`: {len(records)}条记录缺失\n"

        md += f"""
### 2.2 L2 字段类型验证

| 指标 | 结果 |
|------|------|
| 通过/总数 | {l2['pass']}/{l2['total']} |
| 通过率 | {l2['pass_rate']:.2f}% |
| 失败数 | {l2['fail']} |

### 2.3 L3 推理链结构验证

| 指标 | 结果 |
|------|------|
| 通过/总数 | {l3['pass']}/{l3['total']} |
| 通过率 | {l3['pass_rate']:.2f}% |
| 失败数 | {l3['fail']} |

### 2.4 L4 坐标验证

| 指标 | 结果 |
|------|------|
| 通过/总数 | {l4['pass']}/{l4['total']} |
| 通过率 | {l4['pass_rate']:.2f}% |
| 失败数 | {l4['fail']} |
| 坐标超出范围 | {len(l4['out_of_range'])} |

### 2.5 L5 Token映射验证

| 指标 | 结果 |
|------|------|
| 通过/总数 | {l5['pass']}/{l5['total']} |
| 通过率 | {l5['pass_rate']:.2f}% |
| 失败数 | {l5['fail']} |

---

## 3. difficulty_score 验证

| 指标 | 结果 |
|------|------|
| 通过/总数 | {score['pass']}/{score['total']} |
| 通过率 | {score['pass_rate']:.2f}% |
| 平均偏差 | {score['stats']['mean_deviation']} |
| 最大偏差 | {score['stats']['max_deviation']} |
| 容忍范围内 | {score['stats']['within_tolerance']}/{score['total']} |

---

## 4. difficulty 映射验证

| 指标 | 结果 |
|------|------|
| 通过/总数 | {mapping['pass']}/{mapping['total']} |
| 通过率 | {mapping['pass_rate']:.2f}% |
| 不匹配数 | {mapping['fail']} |

**映射规则**:
- easy: difficulty_score ≤ 2.0
- medium: 2.0 < difficulty_score ≤ 3.5
- hard: difficulty_score > 3.5

---

## 5. 分布分析

### 5.1 空间关系类型分布

| 类型 | 数量 | 实际占比 | 目标占比 | 偏差 | 状态 |
|------|------|---------|---------|------|------|
"""
        for rel_type, stats in dist['spatial_relation_type'].items():
            status = "✅" if stats['pass'] else "❌"
            md += f"| {rel_type} | {stats['count']} | {stats['actual_pct']}% | {stats['target_pct']}% | {stats['deviation']}% | {status} |\n"

        md += """
### 5.2 难度分布

| 难度 | 数量 | 实际占比 | 目标占比 | 偏差 | 状态 |
|------|------|---------|---------|------|------|
"""
        for diff, stats in dist['difficulty'].items():
            status = "✅" if stats['pass'] else "❌"
            md += f"| {diff} | {stats['count']} | {stats['actual_pct']}% | {stats['target_pct']}% | {stats['deviation']}% | {status} |\n"

        md += """
### 5.3 拓扑子类型分布（仅topological类型）

| 子类型 | 数量 | 实际占比 | 目标占比 | 偏差 | 状态 |
|------|------|---------|---------|------|------|
"""
        for subtype, stats in dist['topology_subtype'].items():
            status = "✅" if stats['pass'] else "❌"
            md += f"| {subtype} | {stats['count']} | {stats['actual_pct']}% | {stats['target_pct']}% | {stats['deviation']}% | {status} |\n"

        md += f"""
**分布验证结果**: {"✅ 通过" if dist['pass'] else "❌ 存在偏差"}

---

## 6. 问句类型统计

### 6.1 问句类型分布

| 问句类型 | 数量 |
|---------|------|
"""
        for q_type, stats in question['by_type'].items():
            count = stats.get('count', stats) if isinstance(stats, dict) else stats
            md += f"| {q_type} | {count} |\n"

        md += f"""
### 6.2 按空间关系类型分类

| 空间关系类型 | 主要问句类型 |
|-------------|-------------|
"""
        for spatial_type, type_dist in question['by_spatial_type'].items():
            sorted_types = sorted(type_dist.items(), key=lambda x: x[1], reverse=True)[:3]
            types_str = ", ".join([f"{t}({c})" for t, c in sorted_types])
            md += f"| {spatial_type} | {types_str} |\n"

        md += f"""
### 6.3 异常问句

共发现 {len(question['anomalies'])} 条异常问句。

---

## 7. 内容质量评估

### 7.1 实体一致性

| 指标 | 结果 |
|------|------|
| 通过 | {quality['entity_consistency']['pass']} |
| 失败 | {quality['entity_consistency']['fail']} |

### 7.2 答案质量

| 指标 | 结果 |
|------|------|
| 通过 | {quality['answer_quality']['pass']} |
| 失败 | {quality['answer_quality']['fail']} |

### 7.3 坐标准确性

| 指标 | 结果 |
|------|------|
| 通过 | {quality['coordinate_accuracy']['pass']} |
| 失败 | {quality['coordinate_accuracy']['fail']} |

---

## 8. 实验兼容性

| 实验 | 兼容数 | 不兼容数 | 兼容率 | 状态 |
|------|--------|---------|--------|------|
"""
        for exp_name, stats in exp['experiments'].items():
            status = "✅" if stats['compatibility_rate'] >= 95 else ("⚠️" if stats['compatibility_rate'] >= 80 else "❌")
            md += f"| {exp_name} | {stats['compatible']} | {stats['incompatible']} | {stats['compatibility_rate']}% | {status} |\n"

        # 总结
        md += """
---

## 9. 问题清单与修复建议

### 9.1 严重问题（需立即修复）

"""
        critical_issues = []
        if l1['fail'] > 0:
            critical_issues.append(f"- **L1必需字段缺失**: {l1['fail']}条记录")
        if l3['fail'] > len(self.data) * 0.02:
            critical_issues.append(f"- **L3推理链结构错误**: {l3['fail']}条记录（超过2%）")
        if l4['fail'] > 0:
            critical_issues.append(f"- **L4坐标问题**: {l4['fail']}条记录")

        if critical_issues:
            md += "\n".join(critical_issues)
        else:
            md += "*无严重问题*\n"

        md += """
### 9.2 中等问题（建议修复）

"""
        medium_issues = []
        if score['fail'] > 0:
            medium_issues.append(f"- **difficulty_score偏差过大**: {score['fail']}条记录")
        if mapping['fail'] > 0:
            medium_issues.append(f"- **difficulty映射不匹配**: {mapping['fail']}条记录")
        if not dist['pass']:
            medium_issues.append("- **数据分布偏差超过5%**")

        if medium_issues:
            md += "\n".join(medium_issues)
        else:
            md += "*无中等问题*\n"

        md += """
### 9.3 轻微问题（可选修复）

"""
        minor_issues = []
        if len(question['anomalies']) > 0:
            minor_issues.append(f"- **异常问句**: {len(question['anomalies'])}条")
        if quality['entity_consistency']['fail'] > 0:
            minor_issues.append(f"- **实体一致性问题**: {quality['entity_consistency']['fail']}条")

        if minor_issues:
            md += "\n".join(minor_issues)
        else:
            md += "*无轻微问题*\n"

        md += """
---

## 10. 总结与建议

### 10.1 总体评估

"""
        # 计算总体通过率
        total_pass = all([
            l1['pass_rate'] >= 95,
            l2['pass_rate'] >= 95,
            l3['pass_rate'] >= 95,
            l4['pass_rate'] >= 95,
            l5['pass_rate'] >= 90,
            dist['pass']
        ])

        if total_pass:
            md += "**✅ 数据质量良好**，满足实验要求。\n\n"
        else:
            md += "**⚠️ 数据存在质量问题**，建议在修复后重新验证。\n\n"

        md += """### 10.2 下一步建议

1. **优先修复严重问题**：确保所有必需字段完整、推理链结构正确
2. **验证修复效果**：修复后重新运行审查脚本
3. **数据备份**：修复前备份原始数据

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*审查脚本版本: V1.0*
"""

        return md


def main():
    parser = argparse.ArgumentParser(description="GeoKD-SR 数据全面多维深度审查")
    parser.add_argument("--data", "-d", required=True, help="数据文件路径 (JSONL格式)")
    parser.add_argument("--output", "-o", default="reports", help="输出目录 (默认: reports)")

    args = parser.parse_args()

    print("=" * 60)
    print("GeoKD-SR 数据全面多维深度审查")
    print("=" * 60)

    # 创建审查器
    auditor = GeoKDDataAuditor(args.data)

    # 加载数据
    total = auditor.load_data()
    if total == 0:
        print("[ERROR] 未加载任何数据，退出")
        return

    # 生成报告
    auditor.generate_report(args.output)

    print("\n" + "=" * 60)
    print("审查完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
