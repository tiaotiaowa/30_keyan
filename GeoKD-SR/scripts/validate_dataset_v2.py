#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 四级审查脚本 V2.0
实现完整的四级审查体系：L1格式、L2逻辑、L3分布、L4语义

审查项目（共30项）:
L1 格式审查 (4项): 字段完整性、数据类型、ID唯一性、JSON格式
L2 逻辑审查 (8项): 推理链步数、推理链字段、坐标有效性、坐标一致性、difficulty一致性、答案逻辑、距离准确性、entity_to_token
L3 分布审查 (8项): 四类空间关系分布、三类难度分布、实体分布CV
L4 语义审查 (10项): 各拓扑关系关键词、方向表达统一、spatial_tokens覆盖、提示词分布、省份覆盖、问题多样性
"""

import json
import csv
import argparse
import re
import math
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import statistics


# ==================== 配置常量 ====================

# L1: 必需字段（11个）
REQUIRED_FIELDS = {
    "id": str,
    "spatial_relation_type": str,
    "question": str,
    "answer": str,
    "reasoning_chain": list,
    "entities": list,
    "spatial_tokens": list,
    "entity_to_token": dict,
    "difficulty": str,
    "difficulty_score": (int, float),
    "topology_subtype": str  # 对于topological类型必需
}

# 有效枚举值
VALID_SPATIAL_TYPES = ["directional", "topological", "metric", "composite"]
VALID_TOPOLOGY_SUBTYPES = ["within", "contains", "adjacent", "disjoint", "overlap"]
VALID_DIFFICULTIES = ["easy", "medium", "hard"]

# 难度与分数映射
DIFFICULTY_SCORE_RANGE = {
    "easy": (1.0, 2.0),
    "medium": (2.0, 3.5),
    "hard": (3.5, 5.0)
}

# 中国坐标范围
COORD_RANGE = {
    "lon": (73.0, 135.0),
    "lat": (18.0, 54.0)
}

# L3: 目标分布（允许5%偏差）
TARGET_DISTRIBUTION = {
    # 空间关系分布
    "directional": (0.25, 0.05),  # (目标值, 允许偏差)
    "topological": (0.275, 0.05),
    "metric": (0.275, 0.05),
    "composite": (0.20, 0.05),
    # 难度分布
    "easy": (0.30, 0.05),
    "medium": (0.50, 0.05),
    "hard": (0.20, 0.05)
}

# L4: 拓扑关系关键词
TOPOLOGY_KEYWORDS = {
    "within": ["位于", "内", "境内", "在...里面"],
    "contains": ["包含", "含有", "有...在里面", "管辖"],
    "adjacent": ["相邻", "接壤", "毗邻", "交界"],
    "disjoint": ["不相邻", "分离", "相离", "不接壤"],
    "overlap": ["流经", "贯穿", "跨越", "穿过"]
}

# 方向表达（8方向）
DIRECTIONS = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
DIRECTION_PATTERNS = [
    r"北偏东", r"东偏北", r"南偏东", r"东偏南",
    r"南偏西", r"西偏南", r"北偏西", r"西偏北",
    r"正北", r"正东", r"正南", r"正西"
]

# 中国34省级行政区
PROVINCES = [
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "海南",
    "四川", "贵州", "云南", "陕西", "甘肃", "青海",
    "广西", "西藏", "宁夏", "新疆", "内蒙古",
    "香港", "澳门", "台湾"
]

# 5步推理链结构
REASONING_STEPS = {
    1: {"name": "entity_identification", "action": "extract_entities"},
    2: {"name": "spatial_relation_extraction", "action": "classify_relation"},
    3: {"name": "coordinate_retrieval", "action": "infer_entity_to_token"},
    4: {"name": "spatial_calculation", "action": ["calculate", "determine_topology", "calculate_distance", "calculate_direction"]},
    5: {"name": "answer_generation", "action": "generate_answer"}
}


# ==================== 数据类 ====================

@dataclass
class AuditIssue:
    """审查问题项"""
    check_id: str  # 检查项编号 (1-30)
    check_name: str  # 检查项名称
    level: int  # 审查层级 (1-4)
    record_id: str  # 记录ID
    severity: str  # 严重程度: critical, important, warning, info
    description: str  # 问题描述
    actual_value: Any = None  # 实际值
    expected_value: Any = None  # 期望值


@dataclass
class LevelReport:
    """层级报告"""
    level: int
    name: str
    total_checks: int
    passed_checks: int
    issues: List[AuditIssue] = field(default_factory=list)
    pass_rate: float = 0.0

    def __post_init__(self):
        self.pass_rate = (self.passed_checks / self.total_checks * 100) if self.total_checks > 0 else 0


@dataclass
class AuditReport:
    """完整审查报告"""
    data_file: str
    total_records: int
    validation_time: str = field(default_factory=lambda: datetime.now().isoformat())
    level_reports: Dict[int, LevelReport] = field(default_factory=dict)
    all_issues: List[AuditIssue] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)

    @property
    def overall_pass_rate(self) -> float:
        """整体通过率"""
        if not self.level_reports:
            return 0.0
        return sum(r.pass_rate for r in self.level_reports.values()) / len(self.level_reports)

    @property
    def critical_issues(self) -> List[AuditIssue]:
        """严重问题"""
        return [i for i in self.all_issues if i.severity == "critical"]

    @property
    def important_issues(self) -> List[AuditIssue]:
        """重要问题"""
        return [i for i in self.all_issues if i.severity == "important"]


# ==================== 核心审查类 ====================

class DatasetAuditor:
    """数据集审查器"""

    def __init__(self, data_path: str, config_path: str = None):
        self.data_path = Path(data_path)
        self.config_path = config_path
        self.records: List[Dict] = []
        self.all_issues: List[AuditIssue] = []
        self.statistics: Dict[str, Any] = {}

    def run_audit(self, levels: List[int] = None) -> AuditReport:
        """执行审查"""
        if levels is None:
            levels = [1, 2, 3, 4]

        print("=" * 70)
        print("GeoKD-SR 四级审查脚本 V2.0")
        print("=" * 70)
        print(f"\n数据文件: {self.data_path}")
        print(f"审查层级: L{', L'.join(map(str, levels))}")

        # 加载数据
        print("\n[1/6] 加载数据...")
        self._load_data()
        print(f"  成功加载: {len(self.records)} 条记录")

        if not self.records:
            return AuditReport(
                data_file=str(self.data_path),
                total_records=0,
                all_issues=[AuditIssue(
                    check_id="L1-1",
                    check_name="数据加载",
                    level=1,
                    record_id="N/A",
                    severity="critical",
                    description="未找到有效数据记录"
                )]
            )

        # 执行各级审查
        level_reports = {}
        total_checks = 0
        total_passed = 0

        if 1 in levels:
            print("\n[2/6] L1 格式审查 (4项)...")
            report = self._check_level1_format()
            level_reports[1] = report
            total_checks += report.total_checks
            total_passed += report.passed_checks

        if 2 in levels:
            print("\n[3/6] L2 逻辑审查 (8项)...")
            report = self._check_level2_logic()
            level_reports[2] = report
            total_checks += report.total_checks
            total_passed += report.passed_checks

        if 3 in levels:
            print("\n[4/6] L3 分布审查 (8项)...")
            report = self._check_level3_distribution()
            level_reports[3] = report
            total_checks += report.total_checks
            total_passed += report.passed_checks

        if 4 in levels:
            print("\n[5/6] L4 语义审查 (10项)...")
            report = self._check_level4_semantic()
            level_reports[4] = report
            total_checks += report.total_checks
            total_passed += report.passed_checks

        print("\n[6/6] 生成报告...")

        # 汇总所有问题
        all_issues = []
        for report in level_reports.values():
            all_issues.extend(report.issues)

        return AuditReport(
            data_file=str(self.data_path),
            total_records=len(self.records),
            level_reports=level_reports,
            all_issues=all_issues,
            statistics=self.statistics
        )

    def _load_data(self):
        """加载数据文件"""
        if not self.data_path.exists():
            raise FileNotFoundError(f"数据文件不存在: {self.data_path}")

        self.records = []
        with open(self.data_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    record['_line_num'] = line_num
                    self.records.append(record)
                except json.JSONDecodeError as e:
                    self.all_issues.append(AuditIssue(
                        check_id="L1-4",
                        check_name="JSON格式",
                        level=1,
                        record_id=f"line_{line_num}",
                        severity="critical",
                        description=f"JSON解析失败: {str(e)[:100]}"
                    ))

    def _add_issue(self, check_id: str, check_name: str, level: int,
                   record_id: str, severity: str, description: str,
                   actual_value=None, expected_value=None):
        """添加问题"""
        self.all_issues.append(AuditIssue(
            check_id=check_id,
            check_name=check_name,
            level=level,
            record_id=record_id,
            severity=severity,
            description=description,
            actual_value=actual_value,
            expected_value=expected_value
        ))

    # ==================== L1: 格式审查 ====================

    def _check_level1_format(self) -> LevelReport:
        """L1 格式审查 (4项)"""
        issues = []
        passed = 0
        total = 4

        # 1. 字段完整性检查
        print("  检查1: 字段完整性...")
        missing_field_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            missing = []

            for field, field_type in REQUIRED_FIELDS.items():
                if field == "topology_subtype":
                    # 只在topological类型时检查
                    if record.get("spatial_relation_type") == "topological":
                        if field not in record:
                            missing.append(field)
                else:
                    if field not in record:
                        missing.append(field)

            if missing:
                missing_field_count += 1
                issues.append(AuditIssue(
                    check_id="L1-1",
                    check_name="字段完整性",
                    level=1,
                    record_id=record_id,
                    severity="critical",
                    description=f"缺少必需字段: {missing}",
                    actual_value=len(record.keys()),
                    expected_value=len(REQUIRED_FIELDS)
                ))

        coverage_rate = (len(self.records) - missing_field_count) / len(self.records) * 100
        if coverage_rate >= 99:
            passed += 1
            print(f"    通过: {coverage_rate:.1f}% 记录字段完整")
        else:
            print(f"    未通过: {coverage_rate:.1f}% 记录字段完整 (目标>=99%)")

        # 2. 数据类型检查
        print("  检查2: 数据类型...")
        type_error_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")

            for field, expected_type in REQUIRED_FIELDS.items():
                if field == "topology_subtype":
                    continue
                if field in record:
                    value = record[field]
                    if expected_type == (int, float):
                        if not isinstance(value, (int, float)):
                            type_error_count += 1
                            issues.append(AuditIssue(
                                check_id="L1-2",
                                check_name="数据类型",
                                level=1,
                                record_id=record_id,
                                severity="critical",
                                description=f"字段'{field}'类型错误",
                                actual_value=type(value).__name__,
                                expected_value="int或float"
                            ))
                            break
                    else:
                        if not isinstance(value, expected_type):
                            type_error_count += 1
                            issues.append(AuditIssue(
                                check_id="L1-2",
                                check_name="数据类型",
                                level=1,
                                record_id=record_id,
                                severity="critical",
                                description=f"字段'{field}'类型错误",
                                actual_value=type(value).__name__,
                                expected_value=expected_type.__name__
                            ))
                            break

        type_correct_rate = (len(self.records) - type_error_count) / len(self.records) * 100
        if type_correct_rate >= 99:
            passed += 1
            print(f"    通过: {type_correct_rate:.1f}% 记录数据类型正确")
        else:
            print(f"    未通过: {type_correct_rate:.1f}% 记录数据类型正确 (目标>=99%)")

        # 3. ID唯一性检查
        print("  检查3: ID唯一性...")
        id_counter = Counter(r.get("id", f"line_{r.get('_line_num', '?')}") for r in self.records)
        duplicates = [(id_val, count) for id_val, count in id_counter.items() if count > 1]

        if not duplicates:
            passed += 1
            print(f"    通过: 所有ID唯一")
        else:
            for dup_id, count in duplicates[:5]:
                issues.append(AuditIssue(
                    check_id="L1-3",
                    check_name="ID唯一性",
                    level=1,
                    record_id=dup_id,
                    severity="critical",
                    description=f"ID重复{count}次",
                    actual_value=count,
                    expected_value=1
                ))
            print(f"    未通过: 发现{len(duplicates)}个重复ID")

        # 4. JSON格式检查（已在加载时完成）
        json_error_count = sum(1 for i in self.all_issues if i.check_id == "L1-4")
        if json_error_count == 0:
            passed += 1
            print(f"    通过: 所有记录JSON格式有效")
        else:
            print(f"    未通过: {json_error_count}条记录JSON格式错误")

        # 保存统计
        self.statistics["L1"] = {
            "field_coverage_rate": coverage_rate,
            "type_correct_rate": type_correct_rate,
            "duplicate_ids": len(duplicates),
            "json_errors": json_error_count
        }

        return LevelReport(
            level=1,
            name="格式审查",
            total_checks=total,
            passed_checks=passed,
            issues=issues
        )

    # ==================== L2: 逻辑审查 ====================

    def _check_level2_logic(self) -> LevelReport:
        """L2 逻辑审查 (8项)"""
        issues = []
        passed = 0
        total = 8

        # 5. 推理链步数检查
        print("  检查5: 推理链步数...")
        chain_error_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            chain = record.get("reasoning_chain", [])

            if len(chain) != 5:
                chain_error_count += 1
                issues.append(AuditIssue(
                    check_id="L2-5",
                    check_name="推理链步数",
                    level=2,
                    record_id=record_id,
                    severity="important",
                    description=f"reasoning_chain应为5步，实际{len(chain)}步",
                    actual_value=len(chain),
                    expected_value=5
                ))

        chain_correct_rate = (len(self.records) - chain_error_count) / len(self.records) * 100
        if chain_correct_rate >= 95:
            passed += 1
            print(f"    通过: {chain_correct_rate:.1f}% 记录推理链步数正确")
        else:
            print(f"    未通过: {chain_correct_rate:.1f}% 记录推理链步数正确 (目标>=95%)")

        # 6. 推理链字段检查
        print("  检查6: 推理链字段...")
        field_error_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            chain = record.get("reasoning_chain", [])

            for i, step in enumerate(chain, 1):
                required_fields = ["step", "name", "action", "content"]
                missing = [f for f in required_fields if f not in step]

                if missing:
                    field_error_count += 1
                    issues.append(AuditIssue(
                        check_id="L2-6",
                        check_name="推理链字段",
                        level=2,
                        record_id=record_id,
                        severity="important",
                        description=f"步骤{i}缺少字段: {missing}"
                    ))
                    break

                # 检查特定字段
                if i == 1 and "entities_involved" not in step:
                    field_error_count += 1
                    issues.append(AuditIssue(
                        check_id="L2-6",
                        check_name="推理链字段",
                        level=2,
                        record_id=record_id,
                        severity="warning",
                        description="步骤1缺少entities_involved字段"
                    ))
                    break

                if i == 2 and "relation_type" not in step:
                    field_error_count += 1
                    issues.append(AuditIssue(
                        check_id="L2-6",
                        check_name="推理链字段",
                        level=2,
                        record_id=record_id,
                        severity="warning",
                        description="步骤2缺少relation_type字段"
                    ))
                    break

                if i == 3 and "coordinates" not in step:
                    field_error_count += 1
                    issues.append(AuditIssue(
                        check_id="L2-6",
                        check_name="推理链字段",
                        level=2,
                        record_id=record_id,
                        severity="warning",
                        description="步骤3缺少coordinates字段"
                    ))
                    break

                if i == 4 and "calculation_result" not in step:
                    field_error_count += 1
                    issues.append(AuditIssue(
                        check_id="L2-6",
                        check_name="推理链字段",
                        level=2,
                        record_id=record_id,
                        severity="warning",
                        description="步骤4缺少calculation_result字段"
                    ))
                    break

        if field_error_count <= len(self.records) * 0.05:
            passed += 1
            print(f"    通过: 推理链字段结构完整")
        else:
            print(f"    未通过: {field_error_count}条记录推理链字段不完整")

        # 7. 坐标有效性检查
        print("  检查7: 坐标有效性...")
        coord_error_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            entities = record.get("entities", [])

            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                coords = entity.get("coords")
                if coords and isinstance(coords, list) and len(coords) >= 2:
                    lon, lat = coords[0], coords[1]

                    if not (COORD_RANGE["lon"][0] <= lon <= COORD_RANGE["lon"][1]):
                        coord_error_count += 1
                        issues.append(AuditIssue(
                            check_id="L2-7",
                            check_name="坐标有效性",
                            level=2,
                            record_id=record_id,
                            severity="critical",
                            description=f"{entity.get('name', 'Unknown')}经度超出中国范围",
                            actual_value=lon,
                            expected_value=f"{COORD_RANGE['lon'][0]}-{COORD_RANGE['lon'][1]}"
                        ))

                    if not (COORD_RANGE["lat"][0] <= lat <= COORD_RANGE["lat"][1]):
                        coord_error_count += 1
                        issues.append(AuditIssue(
                            check_id="L2-7",
                            check_name="坐标有效性",
                            level=2,
                            record_id=record_id,
                            severity="critical",
                            description=f"{entity.get('name', 'Unknown')}纬度超出中国范围",
                            actual_value=lat,
                            expected_value=f"{COORD_RANGE['lat'][0]}-{COORD_RANGE['lat'][1]}"
                        ))

        coord_valid_rate = (len(self.records) - coord_error_count) / len(self.records) * 100
        if coord_valid_rate >= 98:
            passed += 1
            print(f"    通过: {coord_valid_rate:.1f}% 记录坐标有效")
        else:
            print(f"    未通过: {coord_valid_rate:.1f}% 记录坐标有效 (目标>=98%)")

        # 8. 坐标一致性检查
        print("  检查8: 坐标一致性...")
        consistency_error_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            chain = record.get("reasoning_chain", [])
            entities = record.get("entities", [])

            # 从entities获取坐标
            entity_coords = {}
            for entity in entities:
                if isinstance(entity, dict) and "name" in entity and "coords" in entity:
                    coord = entity["coords"]
                    # 确保坐标是数值列表
                    if isinstance(coord, list) and all(isinstance(c, (int, float)) for c in coord):
                        entity_coords[entity["name"]] = coord

            # 检查推理链中的坐标
            for step in chain:
                if step.get("step") == 3 and "coordinates" in step:
                    chain_coords = step["coordinates"]

                    for name, coords in chain_coords.items():
                        if name in entity_coords:
                            entity_coord = entity_coords[name]
                            # 确保坐标是数值类型
                            try:
                                coords_num = [float(c) for c in coords]
                                entity_coord_num = [float(c) for c in entity_coord]
                                # 允许小数点误差
                                if not all(abs(c - ec) < 0.01 for c, ec in zip(coords_num, entity_coord_num)):
                                    consistency_error_count += 1
                                    issues.append(AuditIssue(
                                        check_id="L2-8",
                                        check_name="坐标一致性",
                                        level=2,
                                        record_id=record_id,
                                        severity="warning",
                                        description=f"{name}的坐标在推理链和entities中不一致"
                                    ))
                                    break
                            except (ValueError, TypeError):
                                # 坐标转换失败，跳过此检查
                                pass

        if consistency_error_count <= len(self.records) * 0.1:
            passed += 1
            print(f"    通过: 推理链与实体坐标一致")
        else:
            print(f"    未通过: {consistency_error_count}条记录坐标不一致")

        # 9. difficulty一致性检查
        print("  检查9: difficulty一致性...")
        diff_error_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            difficulty = record.get("difficulty")
            score = record.get("difficulty_score")

            if difficulty and score is not None:
                min_score, max_score = DIFFICULTY_SCORE_RANGE.get(difficulty, (0, 5))
                if not (min_score <= score <= max_score):
                    diff_error_count += 1
                    issues.append(AuditIssue(
                        check_id="L2-9",
                        check_name="difficulty一致性",
                        level=2,
                        record_id=record_id,
                        severity="important",
                        description=f"difficulty={difficulty}与score={score}不匹配",
                        actual_value=score,
                        expected_value=f"{min_score}-{max_score}"
                    ))

        if diff_error_count <= len(self.records) * 0.05:
            passed += 1
            print(f"    通过: difficulty与score映射正确")
        else:
            print(f"    未通过: {diff_error_count}条记录difficulty与score不匹配")

        # 10. 答案逻辑检查
        print("  检查10: 答案逻辑...")
        logic_error_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            question = record.get("question", "")
            answer = record.get("answer", "")

            # 是否类问题检查
            if any(kw in question for kw in ["是否", "是否为", "是否是", "是否属于"]):
                # 答案应该包含明确判断
                if not any(kw in answer for kw in ["是", "不是", "否", "属于", "不属于"]):
                    logic_error_count += 1
                    issues.append(AuditIssue(
                        check_id="L2-10",
                        check_name="答案逻辑",
                        level=2,
                        record_id=record_id,
                        severity="warning",
                        description="是否类问题答案缺少明确判断"
                    ))

        if logic_error_count <= len(self.records) * 0.05:
            passed += 1
            print(f"    通过: 答案逻辑正确")
        else:
            print(f"    未通过: {logic_error_count}条记录答案逻辑有问题")

        # 11. 距离准确性检查
        print("  检查11: 距离准确性...")
        distance_error_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")

            if record.get("spatial_relation_type") == "metric":
                chain = record.get("reasoning_chain", [])
                entities = record.get("entities", [])

                if len(entities) >= 2:
                    coords1 = entities[0].get("coords")
                    coords2 = entities[1].get("coords")

                    if coords1 and coords2 and len(coords1) >= 2 and len(coords2) >= 2:
                        # 计算理论距离
                        lon1, lat1 = coords1[0], coords1[1]
                        lon2, lat2 = coords2[0], coords2[1]

                        # Haversine公式
                        R = 6371
                        phi1, phi2 = math.radians(lat1), math.radians(lat2)
                        dphi = math.radians(lat2 - lat1)
                        dlambda = math.radians(lon2 - lon1)

                        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
                        theoretical_distance = R * 2 * math.asin(math.sqrt(a))

                        # 从答案或推理链提取距离
                        answer = record.get("answer", "")
                        distance_match = re.search(r'(\d+\.?\d*)\s*公里', answer)
                        reported_distance = None

                        if distance_match:
                            reported_distance = float(distance_match.group(1))
                        else:
                            for step in chain:
                                if "calculation_result" in step:
                                    dist_match = re.search(r'(\d+\.?\d*)\s*公里', str(step["calculation_result"]))
                                    if dist_match:
                                        reported_distance = float(dist_match.group(1))
                                        break

                        if reported_distance:
                            error_rate = abs(reported_distance - theoretical_distance) / theoretical_distance
                            if error_rate > 0.1:  # 10%误差
                                distance_error_count += 1
                                issues.append(AuditIssue(
                                    check_id="L2-11",
                                    check_name="距离准确性",
                                    level=2,
                                    record_id=record_id,
                                    severity="warning",
                                    description=f"距离误差{error_rate*100:.1f}%超过10%",
                                    actual_value=f"{reported_distance}km",
                                    expected_value=f"{theoretical_distance:.1f}km"
                                ))

        if distance_error_count <= len(self.records) * 0.1:
            passed += 1
            print(f"    通过: 距离计算准确")
        else:
            print(f"    未通过: {distance_error_count}条记录距离误差过大")

        # 12. entity_to_token映射检查
        print("  检查12: entity_to_token映射...")
        mapping_error_count = 0
        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            entity_to_token = record.get("entity_to_token", {})
            entities = record.get("entities", [])

            # 检查映射覆盖
            entity_names = {e.get("name") for e in entities if isinstance(e, dict)}
            mapped_names = set(entity_to_token.keys())

            unmapped = entity_names - mapped_names
            if unmapped:
                mapping_error_count += 1
                issues.append(AuditIssue(
                    check_id="L2-12",
                    check_name="entity_to_token",
                    level=2,
                    record_id=record_id,
                    severity="important",
                    description=f"entity_to_token缺少映射: {unmapped}"
                ))

            # 检查映射字段
            for name, mapping in entity_to_token.items():
                required_keys = ["char_start", "char_end", "token_indices"]
                missing = [k for k in required_keys if k not in mapping]
                if missing:
                    mapping_error_count += 1
                    issues.append(AuditIssue(
                        check_id="L2-12",
                        check_name="entity_to_token",
                        level=2,
                        record_id=record_id,
                        severity="important",
                        description=f"{name}的entity_to_token缺少字段: {missing}"
                    ))

        mapping_complete_rate = (len(self.records) - mapping_error_count) / len(self.records) * 100
        if mapping_complete_rate >= 95:
            passed += 1
            print(f"    通过: {mapping_complete_rate:.1f}% 记录entity_to_token完整")
        else:
            print(f"    未通过: {mapping_complete_rate:.1f}% 记录entity_to_token完整 (目标>=95%)")

        # 保存统计
        self.statistics["L2"] = {
            "chain_correct_rate": chain_correct_rate,
            "coord_valid_rate": coord_valid_rate,
            "diff_consistency_rate": (len(self.records) - diff_error_count) / len(self.records) * 100,
            "mapping_complete_rate": mapping_complete_rate
        }

        return LevelReport(
            level=2,
            name="逻辑审查",
            total_checks=total,
            passed_checks=passed,
            issues=issues
        )

    # ==================== L3: 分布审查 ====================

    def _check_level3_distribution(self) -> LevelReport:
        """L3 分布审查 (8项)"""
        issues = []
        passed = 0
        total = 8

        # 统计分布
        spatial_counter = Counter()
        difficulty_counter = Counter()
        entity_counter = Counter()
        province_counter = Counter()

        for record in self.records:
            spatial_type = record.get("spatial_relation_type", "unknown")
            difficulty = record.get("difficulty", "unknown")

            spatial_counter[spatial_type] += 1
            difficulty_counter[difficulty] += 1

            # 统计实体出现频率
            for entity in record.get("entities", []):
                if isinstance(entity, dict) and "name" in entity:
                    entity_counter[entity["name"]] += 1

            # 统计省份覆盖
            question = record.get("question", "")
            for province in PROVINCES:
                if province in question:
                    province_counter[province] += 1

        total_records = len(self.records)

        # 13-16. 空间关系分布检查
        print("  检查13-16: 空间关系分布...")
        spatial_checks_passed = 0
        for spatial_type, (target, tolerance) in [
            ("directional", TARGET_DISTRIBUTION["directional"]),
            ("topological", TARGET_DISTRIBUTION["topological"]),
            ("metric", TARGET_DISTRIBUTION["metric"]),
            ("composite", TARGET_DISTRIBUTION["composite"])
        ]:
            actual = spatial_counter.get(spatial_type, 0) / total_records
            deviation = abs(actual - target)

            if deviation <= tolerance:
                spatial_checks_passed += 1
                print(f"    {spatial_type}: {actual:.1%} (目标{target:.1%}) 通过")
            else:
                issues.append(AuditIssue(
                    check_id=f"L3-1{['3', '4', '5', '6'][['directional', 'topological', 'metric', 'composite'].index(spatial_type)]}",
                    check_name=f"{spatial_type}分布",
                    level=3,
                    record_id="distribution",
                    severity="important",
                    description=f"{spatial_type}分布偏差{deviation*100:.1f}%超过{tolerance*100:.0f}%",
                    actual_value=f"{actual:.1%}",
                    expected_value=f"{target:.1%}±{tolerance:.1%}"
                ))
                print(f"    {spatial_type}: {actual:.1%} (目标{target:.1%}) 偏差{deviation*100:.1f}%")

        if spatial_checks_passed == 4:
            passed += 1
            print("    通过: 空间关系分布符合要求")
        else:
            print(f"    未通过: {4 - spatial_checks_passed}个空间类型分布偏差过大")

        # 17-19. 难度分布检查
        print("  检查17-19: 难度分布...")
        difficulty_checks_passed = 0
        for difficulty, (target, tolerance) in [
            ("easy", TARGET_DISTRIBUTION["easy"]),
            ("medium", TARGET_DISTRIBUTION["medium"]),
            ("hard", TARGET_DISTRIBUTION["hard"])
        ]:
            actual = difficulty_counter.get(difficulty, 0) / total_records
            deviation = abs(actual - target)

            if deviation <= tolerance:
                difficulty_checks_passed += 1
                print(f"    {difficulty}: {actual:.1%} (目标{target:.1%}) 通过")
            else:
                issues.append(AuditIssue(
                    check_id=f"L3-1{['7', '8', '9'][['easy', 'medium', 'hard'].index(difficulty)]}",
                    check_name=f"{difficulty}难度分布",
                    level=3,
                    record_id="distribution",
                    severity="important",
                    description=f"{difficulty}难度分布偏差{deviation*100:.1f}%超过{tolerance*100:.0f}%",
                    actual_value=f"{actual:.1%}",
                    expected_value=f"{target:.1%}±{tolerance:.1%}"
                ))
                print(f"    {difficulty}: {actual:.1%} (目标{target:.1%}) 偏差{deviation*100:.1f}%")

        if difficulty_checks_passed == 3:
            passed += 1
            print("    通过: 难度分布符合要求")
        else:
            print(f"    未通过: {3 - difficulty_checks_passed}个难度分布偏差过大")

        # 20. 实体分布CV检查
        print("  检查20: 实体分布CV...")
        entity_frequencies = list(entity_counter.values())
        if entity_frequencies:
            mean_freq = statistics.mean(entity_frequencies)
            stdev_freq = statistics.stdev(entity_frequencies) if len(entity_frequencies) > 1 else 0
            cv = stdev_freq / mean_freq if mean_freq > 0 else 0

            if cv < 0.7:
                passed += 1
                print(f"    通过: 实体分布CV={cv:.3f} < 0.7")
            else:
                issues.append(AuditIssue(
                    check_id="L3-20",
                    check_name="实体分布CV",
                    level=3,
                    record_id="distribution",
                    severity="warning",
                    description=f"实体分布变异系数{cv:.3f}超过0.7",
                    actual_value=f"{cv:.3f}",
                    expected_value="<0.7"
                ))
                print(f"    未通过: 实体分布CV={cv:.3f} >= 0.7")

        # 保存统计
        self.statistics["L3"] = {
            "spatial_distribution": {k: v/total_records for k, v in spatial_counter.items()},
            "difficulty_distribution": {k: v/total_records for k, v in difficulty_counter.items()},
            "entity_cv": cv if entity_frequencies else 0,
            "province_coverage": len(province_counter)
        }

        return LevelReport(
            level=3,
            name="分布审查",
            total_checks=total,
            passed_checks=passed,
            issues=issues
        )

    # ==================== L4: 语义审查 ====================

    def _check_level4_semantic(self) -> LevelReport:
        """L4 语义审查 (10项)"""
        issues = []
        passed = 0
        total = 10

        # 21-25. 拓扑关系关键词检查
        print("  检查21-25: 拓扑关系关键词...")
        keyword_checks_passed = 0

        for subtype, keywords in TOPOLOGY_KEYWORDS.items():
            # 找到对应类型的记录
            records_with_subtype = [
                r for r in self.records
                if r.get("spatial_relation_type") == "topological" and
                r.get("topology_subtype") == subtype
            ]

            if not records_with_subtype:
                continue

            keyword_present_count = 0
            for record in records_with_subtype:
                question = record.get("question", "")
                answer = record.get("answer", "")
                text = question + " " + answer

                if any(kw in text for kw in keywords):
                    keyword_present_count += 1
                else:
                    issues.append(AuditIssue(
                        check_id=f"L4-2{['1', '2', '3', '4', '5'][['within', 'contains', 'adjacent', 'disjoint', 'overlap'].index(subtype)]}",
                        check_name=f"{subtype}关键词",
                        level=4,
                        record_id=record.get("id", "?"),
                        severity="warning",
                        description=f"{subtype}关系缺少关键词: {keywords}",
                        expected_value=f"包含{keywords[0]}"
                    ))

            coverage_rate = keyword_present_count / len(records_with_subtype) if records_with_subtype else 1
            if coverage_rate >= 0.8:
                keyword_checks_passed += 1
                print(f"    {subtype}: {coverage_rate:.1%}记录包含关键词 通过")
            else:
                print(f"    {subtype}: {coverage_rate:.1%}记录包含关键词")

        if keyword_checks_passed >= 4:  # 至少4种类型通过
            passed += 1
            print("    通过: 拓扑关系关键词覆盖充分")
        else:
            print(f"    未通过: 部分拓扑关系关键词缺失")

        # 26. 方向表达统一性检查
        print("  检查26: 方向表达统一性...")
        directional_records = [r for r in self.records if r.get("spatial_relation_type") == "directional"]
        direction_format_error = 0

        for record in directional_records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            question = record.get("question", "")
            answer = record.get("answer", "")
            text = question + " " + answer

            # 检查是否包含标准方向
            has_standard_dir = any(dir in text for dir in DIRECTIONS)
            has_non_standard = any(bool(re.search(pattern, text)) for pattern in DIRECTION_PATTERNS)

            if has_non_standard and not has_standard_dir:
                direction_format_error += 1
                issues.append(AuditIssue(
                    check_id="L4-26",
                    check_name="方向表达统一",
                    level=4,
                    record_id=record_id,
                    severity="warning",
                    description="使用非标准方向表达",
                    expected_value=f"标准8方向: {', '.join(DIRECTIONS)}"
                ))

        if direction_format_error <= len(directional_records) * 0.1 if directional_records else True:
            passed += 1
            print("    通过: 方向表达统一")
        else:
            print(f"    未通过: {direction_format_count}条记录使用非标准方向表达")

        # 27. spatial_tokens覆盖检查
        print("  检查27: spatial_tokens覆盖...")
        token_coverage_error = 0

        for record in self.records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")
            question = record.get("question", "")
            spatial_tokens = record.get("spatial_tokens", [])

            for token in spatial_tokens:
                if token not in question:
                    token_coverage_error += 1
                    issues.append(AuditIssue(
                        check_id="L4-27",
                        check_name="spatial_tokens覆盖",
                        level=4,
                        record_id=record_id,
                        severity="warning",
                        description=f"spatial_token '{token}' 未在问题中出现"
                    ))
                    break

        if token_coverage_error <= len(self.records) * 0.1:
            passed += 1
            print("    通过: spatial_tokens覆盖良好")
        else:
            print(f"    未通过: {token_coverage_error}条记录spatial_tokens未完全覆盖")

        # 28. 提示词分布检查
        print("  检查28: 提示词分布...")
        prompt_id_counter = Counter(r.get("prompt_id", "unknown") for r in self.records)

        # 检查是否有过度集中的提示词
        max_prompt_count = max(prompt_id_counter.values())
        max_prompt_ratio = max_prompt_count / len(self.records)

        if max_prompt_ratio < 0.3:  # 单个提示词不超过30%
            passed += 1
            print(f"    通过: 提示词分布均衡 (最高{max_prompt_ratio:.1%})")
        else:
            issues.append(AuditIssue(
                check_id="L4-28",
                check_name="提示词分布",
                level=4,
                record_id="distribution",
                severity="warning",
                description=f"提示词过度集中，最高占比{max_prompt_ratio:.1%}",
                expected_value="<30%"
            ))
            print(f"    未通过: 提示词过度集中 (最高{max_prompt_ratio:.1%})")

        # 29. 省份覆盖检查
        print("  检查29: 省份覆盖...")
        province_coverage = len(set(p for r in self.records for p in PROVINCES if p in r.get("question", "")))

        if province_coverage >= 30:  # 至少覆盖30个省份
            passed += 1
            print(f"    通过: 省份覆盖{province_coverage}/34")
        else:
            issues.append(AuditIssue(
                check_id="L4-29",
                check_name="省份覆盖",
                level=4,
                record_id="distribution",
                severity="warning",
                description=f"省份覆盖不足{province_coverage}/34",
                actual_value=province_coverage,
                expected_value=">=30"
            ))
            print(f"    未通过: 省份覆盖{province_coverage}/34不足")

        # 30. 问题多样性检查
        print("  检查30: 问题多样性...")
        # 使用问题模板相似度检查
        question_templates = []
        for record in self.records:
            question = record.get("question", "")
            # 提取模板（替换实体为占位符）
            template = re.sub(r'[一二三四五六七八九十百千万亿]+市?|[a-zA-Z]+', '[ENTITY]', question)
            question_templates.append(template)

        template_counter = Counter(question_templates)
        max_template_count = max(template_counter.values())
        max_template_ratio = max_template_count / len(self.records)

        if max_template_ratio < 0.1:  # 单一模板不超过10%
            passed += 1
            print(f"    通过: 问题模板多样 (最高{max_template_ratio:.1%})")
        else:
            issues.append(AuditIssue(
                check_id="L4-30",
                check_name="问题多样性",
                level=4,
                record_id="distribution",
                severity="warning",
                description=f"问题模板重复率过高，最高{max_template_ratio:.1%}",
                actual_value=f"{max_template_ratio:.1%}",
                expected_value="<10%"
            ))
            print(f"    未通过: 问题模板重复率过高 (最高{max_template_ratio:.1%})")

        # 保存统计
        self.statistics["L4"] = {
            "keyword_coverage": keyword_checks_passed / 5,
            "direction_format_error": direction_format_error,
            "token_coverage_error": token_coverage_error,
            "province_coverage": province_coverage,
            "template_diversity": max_template_ratio
        }

        return LevelReport(
            level=4,
            name="语义审查",
            total_checks=total,
            passed_checks=passed,
            issues=issues
        )

    # ==================== 报告生成 ====================

    def generate_report(self, report: AuditReport, output_format: str = 'markdown') -> str:
        """生成审查报告"""
        if output_format == 'markdown':
            return self._generate_markdown_report(report)
        elif output_format == 'json':
            return self._generate_json_report(report)
        elif output_format == 'csv':
            return self._generate_csv_report(report)
        else:
            raise ValueError(f"不支持的报告格式: {output_format}")

    def _generate_markdown_report(self, report: AuditReport) -> str:
        """生成Markdown格式报告"""
        lines = [
            "# GeoKD-SR 四级审查报告",
            "",
            f"> **审查时间**: {report.validation_time}",
            f"> **数据文件**: {report.data_file}",
            f"> **数据总量**: {report.total_records} 条",
            "",
            "---",
            "",
            "## 一、执行摘要",
            "",
            f"- **整体通过率**: {report.overall_pass_rate:.1f}%",
            f"- **严重问题**: {len(report.critical_issues)} 个",
            f"- **重要问题**: {len(report.important_issues)} 个",
            "",
            "### 审查层级概览",
            "",
            "| 层级 | 名称 | 检查项 | 通过项 | 通过率 | 状态 |",
            "|------|------|--------|--------|--------|------|",
        ]

        for level in [1, 2, 3, 4]:
            lr = report.level_reports.get(level)
            if lr:
                status = "✅" if lr.pass_rate >= 80 else ("⚠️" if lr.pass_rate >= 60 else "❌")
                lines.append(f"| L{level} | {lr.name} | {lr.total_checks} | {lr.passed_checks} | {lr.pass_rate:.0f}% | {status} |")

        lines.extend([
            "",
            "---",
            "",
            "## 二、L1 格式审查",
            "",
            "### 检查项详情",
            "",
            "| ID | 检查项 | 通过率 | 状态 |",
            "|----|--------|--------|------|",
            "| L1-1 | 字段完整性 | - | - |",
            "| L1-2 | 数据类型 | - | - |",
            "| L1-3 | ID唯一性 | - | - |",
            "| L1-4 | JSON格式 | - | - |",
            "",
        ])

        # 问题详情
        l1_issues = [i for i in report.all_issues if i.level == 1]
        if l1_issues:
            lines.extend([
                "### 问题详情",
                "",
            ])
            for issue in l1_issues[:20]:
                severity_icon = {"critical": "🔴", "important": "🟡", "warning": "🟢", "info": "⚪"}.get(issue.severity, "")
                lines.append(f"- {severity_icon} **{issue.record_id}**: {issue.description}")
            if len(l1_issues) > 20:
                lines.append(f"- ... 共 {len(l1_issues)} 个问题")

        lines.extend([
            "",
            "---",
            "",
            "## 三、L2 逻辑审查",
            "",
            "### 检查项详情",
            "",
            "| ID | 检查项 | 通过率 | 状态 |",
            "|----|--------|--------|------|",
            "| L2-5 | 推理链步数 | - | - |",
            "| L2-6 | 推理链字段 | - | - |",
            "| L2-7 | 坐标有效性 | - | - |",
            "| L2-8 | 坐标一致性 | - | - |",
            "| L2-9 | difficulty一致性 | - | - |",
            "| L2-10 | 答案逻辑 | - | - |",
            "| L2-11 | 距离准确性 | - | - |",
            "| L2-12 | entity_to_token | - | - |",
            "",
        ])

        l2_issues = [i for i in report.all_issues if i.level == 2]
        if l2_issues:
            lines.extend([
                "### 问题详情",
                "",
            ])
            for issue in l2_issues[:20]:
                severity_icon = {"critical": "🔴", "important": "🟡", "warning": "🟢", "info": "⚪"}.get(issue.severity, "")
                lines.append(f"- {severity_icon} **{issue.record_id}**: {issue.description}")
            if len(l2_issues) > 20:
                lines.append(f"- ... 共 {len(l2_issues)} 个问题")

        lines.extend([
            "",
            "---",
            "",
            "## 四、L3 分布审查",
            "",
            "### 检查项详情",
            "",
            "| ID | 检查项 | 通过率 | 状态 |",
            "|----|--------|--------|------|",
            "| L3-13 | directional分布 | - | - |",
            "| L3-14 | topological分布 | - | - |",
            "| L3-15 | metric分布 | - | - |",
            "| L3-16 | composite分布 | - | - |",
            "| L3-17 | easy难度分布 | - | - |",
            "| L3-18 | medium难度分布 | - | - |",
            "| L3-19 | hard难度分布 | - | - |",
            "| L3-20 | 实体分布CV | - | - |",
            "",
        ])

        l3_issues = [i for i in report.all_issues if i.level == 3]
        if l3_issues:
            lines.extend([
                "### 问题详情",
                "",
            ])
            for issue in l3_issues[:10]:
                severity_icon = {"critical": "🔴", "important": "🟡", "warning": "🟢", "info": "⚪"}.get(issue.severity, "")
                lines.append(f"- {severity_icon} **{issue.record_id}**: {issue.description}")
            if len(l3_issues) > 10:
                lines.append(f"- ... 共 {len(l3_issues)} 个问题")

        lines.extend([
            "",
            "---",
            "",
            "## 五、L4 语义审查",
            "",
            "### 检查项详情",
            "",
            "| ID | 检查项 | 通过率 | 状态 |",
            "|----|--------|--------|------|",
            "| L4-21 | Within关键词 | - | - |",
            "| L4-22 | Contains关键词 | - | - |",
            "| L4-23 | Adjacent关键词 | - | - |",
            "| L4-24 | Disjoint关键词 | - | - |",
            "| L4-25 | Overlap关键词 | - | - |",
            "| L4-26 | 方向表达统一 | - | - |",
            "| L4-27 | spatial_tokens覆盖 | - | - |",
            "| L4-28 | 提示词分布 | - | - |",
            "| L4-29 | 省份覆盖 | - | - |",
            "| L4-30 | 问题多样性 | - | - |",
            "",
        ])

        l4_issues = [i for i in report.all_issues if i.level == 4]
        if l4_issues:
            lines.extend([
                "### 问题详情",
                "",
            ])
            for issue in l4_issues[:10]:
                severity_icon = {"critical": "🔴", "important": "🟡", "warning": "🟢", "info": "⚪"}.get(issue.severity, "")
                lines.append(f"- {severity_icon} **{issue.record_id}**: {issue.description}")
            if len(l4_issues) > 10:
                lines.append(f"- ... 共 {len(l4_issues)} 个问题")

        lines.extend([
            "",
            "---",
            "",
            "## 六、结论与建议",
            "",
        ])

        # 生成结论
        if report.critical_issues:
            lines.append("❌ **数据需要修复**: 存在严重问题，必须修复后才能使用。")
        elif report.important_issues:
            lines.append("⚠️ **数据质量可接受**: 存在重要问题，建议修复后使用。")
        else:
            lines.append("✅ **数据质量良好**: 所有检查项通过，可直接使用。")

        lines.extend([
            "",
            "**改进建议**:",
            "",
        ])

        # 按层级汇总问题
        for level in [1, 2, 3, 4]:
            level_issues = [i for i in report.all_issues if i.level == level]
            if level_issues:
                severity_count = Counter(i.severity for i in level_issues)
                lines.append(f"- **L{level}**: {len(level_issues)}个问题 (Critical: {severity_count['critical']}, Important: {severity_count['important']})")

        lines.extend([
            "",
            "---",
            "",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ""
        ])

        return '\n'.join(lines)

    def _generate_json_report(self, report: AuditReport) -> str:
        """生成JSON格式报告"""
        output = {
            "validation_time": report.validation_time,
            "data_file": report.data_file,
            "total_records": report.total_records,
            "overall_pass_rate": report.overall_pass_rate,
            "level_reports": {},
            "statistics": report.statistics,
            "issues": []
        }

        for level, lr in report.level_reports.items():
            output["level_reports"][f"L{level}"] = {
                "name": lr.name,
                "total_checks": lr.total_checks,
                "passed_checks": lr.passed_checks,
                "pass_rate": lr.pass_rate
            }

        for issue in report.all_issues:
            output["issues"].append({
                "check_id": issue.check_id,
                "check_name": issue.check_name,
                "level": issue.level,
                "record_id": issue.record_id,
                "severity": issue.severity,
                "description": issue.description,
                "actual_value": str(issue.actual_value) if issue.actual_value is not None else None,
                "expected_value": str(issue.expected_value) if issue.expected_value is not None else None
            })

        return json.dumps(output, ensure_ascii=False, indent=2)

    def _generate_csv_report(self, report: AuditReport) -> str:
        """生成CSV格式报告"""
        lines = [
            "check_id,check_name,level,record_id,severity,description,actual_value,expected_value"
        ]

        for issue in report.all_issues:
            actual = str(issue.actual_value).replace(',', ';') if issue.actual_value is not None else ""
            expected = str(issue.expected_value).replace(',', ';') if issue.expected_value is not None else ""
            lines.append(f"{issue.check_id},{issue.check_name},{issue.level},{issue.record_id},{issue.severity},\"{issue.description}\",\"{actual}\",\"{expected}\"")

        return '\n'.join(lines)


# ==================== 命令行接口 ====================

def main():
    parser = argparse.ArgumentParser(
        description="GeoKD-SR 四级审查脚本 V2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
审查层级:
  L1: 格式审查 (字段完整性、数据类型、ID唯一性、JSON格式)
  L2: 逻辑审查 (推理链、坐标、难度、答案逻辑等)
  L3: 分布审查 (空间关系分布、难度分布、实体分布)
  L4: 语义审查 (关键词、方向表达、spatial_tokens等)

输出格式:
  markdown: Markdown格式报告 (默认)
  json: JSON格式详细报告
  csv: CSV格式问题列表

示例:
  python scripts/validate_dataset_v2.py --input data/geosr_chain/balanced_topology.jsonl
  python scripts/validate_dataset_v2.py -i data.jsonl --levels 1,2 --format json
        """
    )

    parser.add_argument("--input", "-i", required=True, help="输入JSONL文件路径")
    parser.add_argument("--output", "-o", default="outputs", help="输出目录")
    parser.add_argument("--levels", "-l", default="1,2,3,4", help="审查层级 (逗号分隔: 1,2,3,4)")
    parser.add_argument("--format", "-f", default="markdown", choices=["markdown", "json", "csv"], help="输出格式")
    parser.add_argument("--config", "-c", help="配置文件路径 (YAML)")

    args = parser.parse_args()

    # 解析审查层级
    levels = [int(l.strip()) for l in args.levels.split(',') if l.strip().isdigit()]

    # 确保输出目录存在
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 执行审查
    auditor = DatasetAuditor(args.input, args.config)
    report = auditor.run_audit(levels=levels)

    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = Path(args.input).stem

    if args.format == "markdown":
        output_file = output_dir / f"{base_name}_v2_audit_{timestamp}.md"
        content = auditor.generate_report(report, "markdown")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
    elif args.format == "json":
        output_file = output_dir / f"{base_name}_v2_audit_{timestamp}.json"
        content = auditor.generate_report(report, "json")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
    else:  # csv
        output_file = output_dir / f"{base_name}_v2_audit_{timestamp}.csv"
        content = auditor.generate_report(report, "csv")
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            f.write(content)

    # 输出摘要
    print("\n" + "=" * 70)
    print("审查完成!")
    print("=" * 70)
    print(f"\n报告文件: {output_file}")
    print(f"\n审查结果摘要:")
    print(f"  - 数据总量: {report.total_records} 条")
    print(f"  - 整体通过率: {report.overall_pass_rate:.1f}%")
    print(f"  - 严重问题: {len(report.critical_issues)} 个")
    print(f"  - 重要问题: {len(report.important_issues)} 个")

    for level, lr in report.level_reports.items():
        print(f"  - L{level} {lr.name}: {lr.passed_checks}/{lr.total_checks}项通过 ({lr.pass_rate:.0f}%)")

    # 返回码
    if report.critical_issues:
        return 2
    elif report.important_issues:
        return 1
    else:
        return 0


if __name__ == "__main__":
    exit(main())
