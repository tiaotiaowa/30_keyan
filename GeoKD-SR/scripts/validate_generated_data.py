#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 数据验证脚本
验证生成的数据是否符合V2.1规范

验证层级：
- L1: JSON格式有效性、必需字段存在
- L2: 字段值类型正确
- L3: reasoning_chain 5步结构完整
- L4: entities含coords字段
- L5: entity_to_token映射完整
- L6: 空间关系/难度分布合理
- 附加: 实验兼容性检查
"""

import json
import csv
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import re


# ==================== 配置常量 ====================

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
    "difficulty_score": (int, float)
}

OPTIONAL_FIELDS = {
    "topology_subtype": str,
    "split": str
}

VALID_SPATIAL_TYPES = ["directional", "topological", "metric", "composite"]
VALID_TOPOLOGY_SUBTYPES = ["within", "contains", "adjacent", "disjoint", "overlap"]
VALID_DIFFICULTIES = ["easy", "medium", "hard"]

# 中国坐标范围
COORD_RANGE = {
    "lon": (73.0, 135.0),
    "lat": (18.0, 54.0)
}

# 目标分布 (V2.0)
TARGET_SPATIAL_DISTRIBUTION = {
    "directional": 0.25,
    "topological": 0.275,
    "metric": 0.275,
    "composite": 0.20
}

TARGET_DIFFICULTY_DISTRIBUTION = {
    "easy": 0.30,
    "medium": 0.50,
    "hard": 0.20
}

# 10个实验的字段需求
EXPERIMENT_REQUIREMENTS = {
    "Exp1": ["question", "answer"],
    "Exp2": ["question", "answer"],
    "Exp3a": ["question", "answer", "spatial_relation_type"],
    "Exp3": ["question", "answer", "spatial_relation_type"],
    "Exp4": ["question", "answer", "reasoning_chain"],
    "Exp5": ["question", "answer"],
    "Exp6": ["question", "answer"],
    "Exp7": ["question", "answer", "entities", "spatial_tokens", "entity_to_token"],
    "Exp8": ["question", "answer", "spatial_relation_type", "difficulty", "difficulty_score"],
    "Exp9": ["question", "answer", "spatial_relation_type", "topology_subtype",
             "reasoning_chain", "entities", "spatial_tokens", "entity_to_token",
             "difficulty", "difficulty_score"]
}

# 5步推理链结构
REASONING_STEPS = {
    1: {"name": "entity_identification", "action": "extract_entities"},
    2: {"name": "spatial_relation_extraction", "action": "classify_relation"},
    3: {"name": "coordinate_retrieval", "action": "infer_entity_to_token"},
    4: {"name": "spatial_calculation", "action": ["calculate", "determine_topology", "calculate_distance"]},
    5: {"name": "answer_generation", "action": "generate_answer"}
}


class DataValidator:
    """数据验证器"""

    def __init__(self, data_file: str):
        self.data_file = Path(data_file)
        self.records: List[Dict] = []
        self.issues: Dict[str, List[Dict]] = {f"L{i}": [] for i in range(1, 7)}
        self.issues["additional"] = []
        self.stats: Dict[str, Any] = {}
        self.experiment_compatibility: Dict[str, List[int]] = defaultdict(list)

    def _load_data(self) -> Tuple[List[Dict], List[Dict]]:
        """加载数据文件"""
        records = []
        load_issues = []

        if not self.data_file.exists():
            raise FileNotFoundError(f"数据文件不存在: {self.data_file}")

        with open(self.data_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    record['_line_num'] = i
                    records.append(record)
                except json.JSONDecodeError as e:
                    load_issues.append({
                        "line": i,
                        "error": f"JSON解析失败: {str(e)}",
                        "content_preview": line[:100]
                    })

        return records, load_issues

    def validate_all(self) -> Dict:
        """执行所有验证"""
        print("=" * 60)
        print("GeoKD-SR 数据验证脚本 V2.1")
        print("=" * 60)

        # 加载数据
        print("\n[加载数据]")
        try:
            self.records, load_issues = self._load_data()
            print(f"  成功加载: {len(self.records)} 条记录")

            if load_issues:
                print(f"  加载失败: {len(load_issues)} 条")
                for issue in load_issues[:5]:
                    self.issues["L1"].append({
                        "record_id": f"line_{issue['line']}",
                        "issue": issue["error"],
                        "severity": "critical"
                    })
        except FileNotFoundError as e:
            return {"error": str(e)}

        # 逐条验证
        print("\n[执行验证]")
        total = len(self.records)

        for i, record in enumerate(self.records):
            if (i + 1) % 200 == 0:
                print(f"  进度: {i+1}/{total} ({(i+1)/total*100:.1f}%)")

            record_id = record.get("id", f"line_{record.get('_line_num', i)}")

            self._validate_l1_format(record, record_id)
            self._validate_l2_semantics(record, record_id)
            self._validate_l3_reasoning(record, record_id)
            self._validate_l4_coords(record, record_id)
            self._validate_l5_tokens(record, record_id)
            self._validate_additional(record, record_id)
            self._check_experiment_compatibility(record)

        # L6 分布验证
        self._validate_l6_distribution()

        print(f"  完成: {total}/{total} (100%)")

        return self._generate_report()

    def _validate_l1_format(self, record: Dict, record_id: str):
        """L1: 格式验证 - 必需字段存在"""
        missing_fields = []

        for field, expected_type in REQUIRED_FIELDS.items():
            if field not in record:
                missing_fields.append(field)

        if missing_fields:
            self.issues["L1"].append({
                "record_id": record_id,
                "issue": f"缺少必需字段: {missing_fields}",
                "severity": "critical"
            })

    def _validate_l2_semantics(self, record: Dict, record_id: str):
        """L2: 语义验证 - 字段值类型和取值范围"""
        # 检查字段类型
        for field, expected_type in REQUIRED_FIELDS.items():
            if field in record:
                value = record[field]
                if not isinstance(value, expected_type):
                    self.issues["L2"].append({
                        "record_id": record_id,
                        "issue": f"字段 '{field}' 类型错误: 期望 {expected_type.__name__}, 实际 {type(value).__name__}",
                        "severity": "critical"
                    })

        # 检查spatial_relation_type取值
        spatial_type = record.get("spatial_relation_type")
        if spatial_type and spatial_type not in VALID_SPATIAL_TYPES:
            self.issues["L2"].append({
                "record_id": record_id,
                "issue": f"无效的spatial_relation_type: {spatial_type}",
                "severity": "critical"
            })

        # 检查difficulty取值
        difficulty = record.get("difficulty")
        if difficulty and difficulty not in VALID_DIFFICULTIES:
            self.issues["L2"].append({
                "record_id": record_id,
                "issue": f"无效的difficulty: {difficulty}",
                "severity": "critical"
            })

        # 检查difficulty_score范围
        score = record.get("difficulty_score")
        if score is not None:
            if not (1.0 <= score <= 5.0):
                self.issues["L2"].append({
                    "record_id": record_id,
                    "issue": f"difficulty_score超出范围: {score} (应为1.0-5.0)",
                    "severity": "important"
                })

        # 检查question长度
        question = record.get("question", "")
        if not (10 <= len(question) <= 200):
            self.issues["L2"].append({
                "record_id": record_id,
                "issue": f"question长度异常: {len(question)} (建议10-100字符)",
                "severity": "warning"
            })

        # 检查answer长度
        answer = record.get("answer", "")
        if not (2 <= len(answer) <= 100):
            self.issues["L2"].append({
                "record_id": record_id,
                "issue": f"answer长度异常: {len(answer)} (建议2-50字符)",
                "severity": "warning"
            })

    def _validate_l3_reasoning(self, record: Dict, record_id: str):
        """L3: 推理链验证 - 5步结构完整"""
        chain = record.get("reasoning_chain", [])

        # 检查是否为5步
        if len(chain) != 5:
            self.issues["L3"].append({
                "record_id": record_id,
                "issue": f"reasoning_chain长度错误: {len(chain)} (应为5)",
                "severity": "important"
            })
            return

        # 检查每步结构
        for i, step in enumerate(chain, 1):
            if not isinstance(step, dict):
                self.issues["L3"].append({
                    "record_id": record_id,
                    "issue": f"推理步骤{i}不是字典类型",
                    "severity": "important"
                })
                continue

            # 检查必需字段
            required_step_fields = ["step", "name", "action", "content"]
            missing = [f for f in required_step_fields if f not in step]
            if missing:
                self.issues["L3"].append({
                    "record_id": record_id,
                    "issue": f"推理步骤{i}缺少字段: {missing}",
                    "severity": "important"
                })

            # 检查step编号
            if step.get("step") != i:
                self.issues["L3"].append({
                    "record_id": record_id,
                    "issue": f"推理步骤编号错误: 期望{i}, 实际{step.get('step')}",
                    "severity": "warning"
                })

            # 检查name和action是否符合规范
            expected = REASONING_STEPS.get(i, {})
            if expected.get("name") and step.get("name") != expected["name"]:
                self.issues["L3"].append({
                    "record_id": record_id,
                    "issue": f"推理步骤{i} name错误: 期望'{expected['name']}', 实际'{step.get('name')}'",
                    "severity": "warning"
                })

    def _validate_l4_coords(self, record: Dict, record_id: str):
        """L4: 坐标验证 - entities含coords字段且坐标范围正确"""
        entities = record.get("entities", [])

        if len(entities) < 2:
            self.issues["L4"].append({
                "record_id": record_id,
                "issue": f"entities数量不足: {len(entities)} (应≥2)",
                "severity": "important"
            })
            return

        for entity in entities:
            if not isinstance(entity, dict):
                self.issues["L4"].append({
                    "record_id": record_id,
                    "issue": f"entity不是字典类型: {entity}",
                    "severity": "important"
                })
                continue

            # 检查必需字段
            if "name" not in entity:
                self.issues["L4"].append({
                    "record_id": record_id,
                    "issue": f"entity缺少name字段",
                    "severity": "important"
                })

            if "coords" not in entity:
                self.issues["L4"].append({
                    "record_id": record_id,
                    "issue": f"entity '{entity.get('name', 'unknown')}' 缺少coords字段",
                    "severity": "critical"
                })
                continue

            # 检查坐标范围
            coords = entity["coords"]
            if isinstance(coords, list) and len(coords) >= 2:
                lon, lat = coords[0], coords[1]

                if not (COORD_RANGE["lon"][0] <= lon <= COORD_RANGE["lon"][1]):
                    self.issues["L4"].append({
                        "record_id": record_id,
                        "issue": f"经度超出范围: {lon} (应为{COORD_RANGE['lon']})",
                        "severity": "important"
                    })

                if not (COORD_RANGE["lat"][0] <= lat <= COORD_RANGE["lat"][1]):
                    self.issues["L4"].append({
                        "record_id": record_id,
                        "issue": f"纬度超出范围: {lat} (应为{COORD_RANGE['lat']})",
                        "severity": "important"
                    })

    def _validate_l5_tokens(self, record: Dict, record_id: str):
        """L5: Token映射验证 - entity_to_token映射完整"""
        entity_to_token = record.get("entity_to_token", {})
        entities = record.get("entities", [])

        # 检查映射覆盖
        entity_names = {e.get("name") for e in entities if isinstance(e, dict)}
        mapped_names = set(entity_to_token.keys())

        unmapped = entity_names - mapped_names
        if unmapped:
            self.issues["L5"].append({
                "record_id": record_id,
                "issue": f"entity_to_token缺少映射: {unmapped}",
                "severity": "important"
            })

        # 检查映射结构
        for name, mapping in entity_to_token.items():
            if not isinstance(mapping, dict):
                self.issues["L5"].append({
                    "record_id": record_id,
                    "issue": f"entity_to_token['{name}'] 不是字典类型",
                    "severity": "important"
                })
                continue

            required_keys = ["char_start", "char_end", "token_indices"]
            missing = [k for k in required_keys if k not in mapping]
            if missing:
                self.issues["L5"].append({
                    "record_id": record_id,
                    "issue": f"entity_to_token['{name}'] 缺少字段: {missing}",
                    "severity": "important"
                })

        # 检查spatial_tokens数量
        tokens = record.get("spatial_tokens", [])
        if not (4 <= len(tokens) <= 8):
            self.issues["L5"].append({
                "record_id": record_id,
                "issue": f"spatial_tokens数量异常: {len(tokens)} (建议4-8个)",
                "severity": "warning"
            })

    def _validate_additional(self, record: Dict, record_id: str):
        """附加验证: topology_subtype等"""
        spatial_type = record.get("spatial_relation_type")

        # topological类型必须有topology_subtype
        if spatial_type == "topological":
            subtype = record.get("topology_subtype")
            if not subtype:
                self.issues["additional"].append({
                    "record_id": record_id,
                    "issue": "topological类型缺少topology_subtype字段",
                    "severity": "critical"
                })
            elif subtype not in VALID_TOPOLOGY_SUBTYPES:
                self.issues["additional"].append({
                    "record_id": record_id,
                    "issue": f"无效的topology_subtype: {subtype}",
                    "severity": "critical"
                })

    def _validate_l6_distribution(self):
        """L6: 分布验证 - 空间关系和难度分布"""
        spatial_counter = Counter()
        difficulty_counter = Counter()
        topology_subtype_counter = Counter()

        for record in self.records:
            spatial_type = record.get("spatial_relation_type", "unknown")
            difficulty = record.get("difficulty", "unknown")
            subtype = record.get("topology_subtype", "none")

            spatial_counter[spatial_type] += 1
            difficulty_counter[difficulty] += 1
            if subtype != "none":
                topology_subtype_counter[subtype] += 1

        total = len(self.records)

        self.stats["spatial_distribution"] = {
            k: {"count": v, "ratio": v/total if total > 0 else 0}
            for k, v in spatial_counter.items()
        }

        self.stats["difficulty_distribution"] = {
            k: {"count": v, "ratio": v/total if total > 0 else 0}
            for k, v in difficulty_counter.items()
        }

        self.stats["topology_subtype_distribution"] = dict(topology_subtype_counter)

        # 检查分布偏差
        for spatial_type, target_ratio in TARGET_SPATIAL_DISTRIBUTION.items():
            actual = self.stats["spatial_distribution"].get(spatial_type, {}).get("ratio", 0)
            deviation = abs(actual - target_ratio)
            if deviation > 0.05:
                self.issues["L6"].append({
                    "record_id": "distribution",
                    "issue": f"{spatial_type}分布偏差: 实际{actual:.1%}, 目标{target_ratio:.1%}, 偏差{deviation:.1%}",
                    "severity": "reference"
                })

        for difficulty, target_ratio in TARGET_DIFFICULTY_DISTRIBUTION.items():
            actual = self.stats["difficulty_distribution"].get(difficulty, {}).get("ratio", 0)
            deviation = abs(actual - target_ratio)
            if deviation > 0.05:
                self.issues["L6"].append({
                    "record_id": "distribution",
                    "issue": f"{difficulty}难度分布偏差: 实际{actual:.1%}, 目标{target_ratio:.1%}, 偏差{deviation:.1%}",
                    "severity": "reference"
                })

    def _check_experiment_compatibility(self, record: Dict):
        """检查实验兼容性"""
        record_id = record.get("id", "unknown")

        for exp_id, required_fields in EXPERIMENT_REQUIREMENTS.items():
            compatible = True

            for field in required_fields:
                if field not in record or record[field] is None:
                    compatible = False
                    break

                # 特殊检查：reasoning_chain必须5步
                if field == "reasoning_chain":
                    if not isinstance(record[field], list) or len(record[field]) != 5:
                        compatible = False
                        break

            if compatible:
                self.experiment_compatibility[exp_id].append(record_id)

    def _generate_report(self) -> Dict:
        """生成验证报告"""
        total = len(self.records)

        # 计算各层级通过率
        pass_rates = {}
        for level in ["L1", "L2", "L3", "L4", "L5", "L6"]:
            issues = self.issues[level]
            if level == "L6":
                # L6是分布验证，只有参考性问题
                pass_rates[level] = 100.0 if not issues else 90.0
            else:
                # 其他层级计算实际通过率
                failed_records = len(set(i["record_id"] for i in issues))
                pass_rates[level] = ((total - failed_records) / total * 100) if total > 0 else 0

        # 附加验证通过率
        additional_failed = len(set(i["record_id"] for i in self.issues["additional"]))
        pass_rates["additional"] = ((total - additional_failed) / total * 100) if total > 0 else 0

        # 实验兼容性统计
        exp_compatibility = {
            exp: {
                "count": len(records),
                "ratio": len(records) / total if total > 0 else 0
            }
            for exp, records in self.experiment_compatibility.items()
        }

        self.stats["pass_rates"] = pass_rates
        self.stats["experiment_compatibility"] = exp_compatibility

        return {
            "total_records": total,
            "pass_rates": pass_rates,
            "issues": self.issues,
            "stats": self.stats,
            "experiment_compatibility": exp_compatibility
        }


def generate_markdown_report(report: Dict, output_file: Path):
    """生成Markdown格式的验证报告"""
    total = report["total_records"]
    pass_rates = report["pass_rates"]
    issues = report["issues"]
    stats = report["stats"]

    lines = [
        "# GeoKD-SR 数据验证报告",
        "",
        f"> **验证时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%SS')}",
        f"> **数据文件**: generated_1000.jsonl",
        f"> **验证规范**: V2.1",
        "",
        "---",
        "",
        "## 一、执行摘要",
        "",
        f"- **数据总量**: {total}条",
        f"- **整体通过率**: {sum(pass_rates.values())/len(pass_rates):.1f}%",
        "",
        "| 验证层级 | 通过率 | 状态 |",
        "|----------|--------|------|",
    ]

    for level in ["L1", "L2", "L3", "L4", "L5", "L6"]:
        rate = pass_rates[level]
        status = "✅" if rate >= 98 else ("⚠️" if rate >= 90 else "❌")
        lines.append(f"| {level} | {rate:.1f}% | {status} |")

    lines.extend([
        "",
        "---",
        "",
        "## 二、分层验证详情",
        "",
        "### L1 格式验证 (JSON格式/必需字段)",
        f"- **通过率**: {pass_rates['L1']:.1f}%",
        f"- **问题数量**: {len(issues['L1'])}",
        "",
    ])

    if issues["L1"]:
        lines.append("**问题示例**:")
        for issue in issues["L1"][:3]:
            lines.append(f"- `{issue['record_id']}`: {issue['issue']}")
        if len(issues["L1"]) > 3:
            lines.append(f"- ... 共 {len(issues['L1'])} 个问题")

    lines.extend([
        "",
        "### L2 语义验证 (字段类型/取值范围)",
        f"- **通过率**: {pass_rates['L2']:.1f}%",
        f"- **问题数量**: {len(issues['L2'])}",
        "",
    ])

    if issues["L2"]:
        lines.append("**问题示例**:")
        for issue in issues["L2"][:3]:
            lines.append(f"- `{issue['record_id']}`: {issue['issue']}")

    lines.extend([
        "",
        "### L3 推理链验证 (5步结构)",
        f"- **通过率**: {pass_rates['L3']:.1f}%",
        f"- **问题数量**: {len(issues['L3'])}",
        "",
    ])

    if issues["L3"]:
        lines.append("**问题示例**:")
        for issue in issues["L3"][:3]:
            lines.append(f"- `{issue['record_id']}`: {issue['issue']}")

    lines.extend([
        "",
        "### L4 坐标验证 (entities/coords)",
        f"- **通过率**: {pass_rates['L4']:.1f}%",
        f"- **问题数量**: {len(issues['L4'])}",
        "",
    ])

    if issues["L4"]:
        lines.append("**问题示例**:")
        for issue in issues["L4"][:3]:
            lines.append(f"- `{issue['record_id']}`: {issue['issue']}")

    lines.extend([
        "",
        "### L5 Token映射验证 (entity_to_token)",
        f"- **通过率**: {pass_rates['L5']:.1f}%",
        f"- **问题数量**: {len(issues['L5'])}",
        "",
    ])

    if issues["L5"]:
        lines.append("**问题示例**:")
        for issue in issues["L5"][:3]:
            lines.append(f"- `{issue['record_id']}`: {issue['issue']}")

    lines.extend([
        "",
        "### L6 分布验证 (空间关系/难度)",
        f"- **参考状态**: {'✅ 合理' if len(issues['L6']) < 5 else '⚠️ 有偏差'}",
        "",
        "**空间关系分布**:",
        "",
        "| 类型 | 数量 | 实际占比 | 目标占比 | 偏差 |",
        "|------|------|----------|----------|------|",
    ])

    spatial_dist = stats.get("spatial_distribution", {})
    for stype in ["directional", "topological", "metric", "composite"]:
        d = spatial_dist.get(stype, {"count": 0, "ratio": 0})
        target = TARGET_SPATIAL_DISTRIBUTION.get(stype, 0)
        deviation = abs(d["ratio"] - target)
        lines.append(f"| {stype} | {d['count']} | {d['ratio']:.1%} | {target:.1%} | {deviation:.1%} |")

    lines.extend([
        "",
        "**难度分布**:",
        "",
        "| 难度 | 数量 | 实际占比 | 目标占比 | 偏差 |",
        "|------|------|----------|----------|------|",
    ])

    diff_dist = stats.get("difficulty_distribution", {})
    for diff in ["easy", "medium", "hard"]:
        d = diff_dist.get(diff, {"count": 0, "ratio": 0})
        target = TARGET_DIFFICULTY_DISTRIBUTION.get(diff, 0)
        deviation = abs(d["ratio"] - target)
        lines.append(f"| {diff} | {d['count']} | {d['ratio']:.1%} | {target:.1%} | {deviation:.1%} |")

    lines.extend([
        "",
        "---",
        "",
        "## 三、附加验证结果",
        "",
        "### 拓扑子类型验证",
        f"- **问题数量**: {len([i for i in issues['additional'] if 'topology_subtype' in i.get('issue', '')])}",
        "",
        "**topology_subtype分布**:",
        "",
    ])

    topo_dist = stats.get("topology_subtype_distribution", {})
    if topo_dist:
        for subtype, count in sorted(topo_dist.items(), key=lambda x: -x[1]):
            lines.append(f"- `{subtype}`: {count}条")
    else:
        lines.append("- 无topological类型数据")

    lines.extend([
        "",
        "---",
        "",
        "## 四、实验兼容性矩阵",
        "",
        "| 实验 | 兼容数量 | 兼容率 | 状态 |",
        "|------|---------|--------|------|",
    ])

    for exp_id in ["Exp1", "Exp2", "Exp3a", "Exp3", "Exp4", "Exp5", "Exp6", "Exp7", "Exp8", "Exp9"]:
        d = report["experiment_compatibility"].get(exp_id, {"count": 0, "ratio": 0})
        status = "✅" if d["ratio"] >= 0.95 else ("⚠️" if d["ratio"] >= 0.80 else "❌")
        lines.append(f"| {exp_id} | {d['count']} | {d['ratio']:.1%} | {status} |")

    lines.extend([
        "",
        "---",
        "",
        "## 五、问题汇总",
        "",
    ])

    # 按严重性统计
    severity_count = Counter()
    for level_issues in issues.values():
        for issue in level_issues:
            severity_count[issue.get("severity", "unknown")] += 1

    lines.extend([
        f"**问题统计** (共{sum(severity_count.values())}个):",
        "",
        f"- 🔴 Critical: {severity_count.get('critical', 0)}个",
        f"- 🟡 Important: {severity_count.get('important', 0)}个",
        f"- 🟢 Warning: {severity_count.get('warning', 0)}个",
        f"- ⚪ Reference: {severity_count.get('reference', 0)}个",
        "",
        "**Top 10 问题样本**:",
        "",
    ])

    # 收集所有问题并按严重性排序
    all_issues = []
    for level, level_issues in issues.items():
        for issue in level_issues:
            issue["level"] = level
            all_issues.append(issue)

    severity_order = {"critical": 0, "important": 1, "warning": 2, "reference": 3}
    all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "unknown"), 99))

    for i, issue in enumerate(all_issues[:10], 1):
        severity = issue.get("severity", "unknown")
        emoji = {"critical": "🔴", "important": "🟡", "warning": "🟢", "reference": "⚪"}.get(severity, "❓")
        lines.append(f"{i}. {emoji} `{issue['record_id']}` [{issue['level']}]: {issue['issue']}")

    lines.extend([
        "",
        "---",
        "",
        "## 六、结论与建议",
        "",
    ])

    # 生成结论
    critical_count = severity_count.get("critical", 0)
    important_count = severity_count.get("important", 0)

    if critical_count == 0 and important_count == 0:
        lines.append("✅ **数据质量良好**: 所有记录符合V2.1规范要求，可直接用于实验。")
    elif critical_count == 0:
        lines.append(f"⚠️ **数据质量可接受**: 存在{important_count}个重要问题，建议修复后使用。")
    else:
        lines.append(f"❌ **数据需要修复**: 存在{critical_count}个严重问题和{important_count}个重要问题，必须修复后才能使用。")

    lines.extend([
        "",
        "**改进建议**:",
        "",
    ])

    if critical_count > 0:
        lines.append("1. 优先修复所有critical级别问题")
    if important_count > 0:
        lines.append("2. 处理important级别问题以提高数据质量")

    # 检查实验兼容性
    exp9_ratio = report["experiment_compatibility"].get("Exp9", {}).get("ratio", 0)
    if exp9_ratio < 0.95:
        lines.append(f"3. Exp9兼容率为{exp9_ratio:.1%}，部分记录缺少完整字段")

    lines.extend([
        "",
        "---",
        "",
        f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%SS')}*",
        ""
    ])

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return output_file


def generate_issues_json(report: Dict, output_file: Path):
    """生成问题详情JSON"""
    output_data = {
        "validation_time": datetime.now().isoformat(),
        "total_records": report["total_records"],
        "pass_rates": report["pass_rates"],
        "issues": report["issues"],
        "stats": report["stats"]
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    return output_file


def generate_distribution_csv(report: Dict, output_file: Path):
    """生成分布统计CSV"""
    stats = report["stats"]

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        # 空间关系分布
        writer.writerow(["=== 空间关系分布 ==="])
        writer.writerow(["类型", "数量", "占比"])
        for stype, data in stats.get("spatial_distribution", {}).items():
            writer.writerow([stype, data["count"], f"{data['ratio']:.4f}"])

        writer.writerow([])

        # 难度分布
        writer.writerow(["=== 难度分布 ==="])
        writer.writerow(["难度", "数量", "占比"])
        for diff, data in stats.get("difficulty_distribution", {}).items():
            writer.writerow([diff, data["count"], f"{data['ratio']:.4f}"])

        writer.writerow([])

        # 拓扑子类型分布
        writer.writerow(["=== 拓扑子类型分布 ==="])
        writer.writerow(["子类型", "数量"])
        for subtype, count in stats.get("topology_subtype_distribution", {}).items():
            writer.writerow([subtype, count])

        writer.writerow([])

        # 实验兼容性
        writer.writerow(["=== 实验兼容性 ==="])
        writer.writerow(["实验", "兼容数量", "兼容率"])
        for exp_id, data in report.get("experiment_compatibility", {}).items():
            writer.writerow([exp_id, data["count"], f"{data['ratio']:.4f}"])

    return output_file


def main():
    parser = argparse.ArgumentParser(description="GeoKD-SR 数据验证脚本")
    parser.add_argument("--input", "-i", required=True, help="输入JSONL文件路径")
    parser.add_argument("--output", "-o", default="outputs", help="输出目录")

    args = parser.parse_args()

    # 确保输出目录存在
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 执行验证
    validator = DataValidator(args.input)
    report = validator.validate_all()

    if "error" in report:
        print(f"\n❌ 验证失败: {report['error']}")
        return 1

    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = "validation_1000"

    md_file = output_dir / f"{base_name}_report.md"
    json_file = output_dir / f"{base_name}_issues.json"
    csv_file = output_dir / f"{base_name}_stats.csv"

    generate_markdown_report(report, md_file)
    generate_issues_json(report, json_file)
    generate_distribution_csv(report, csv_file)

    print("\n" + "=" * 60)
    print("验证完成!")
    print("=" * 60)
    print(f"\n📊 报告文件:")
    print(f"  - Markdown报告: {md_file}")
    print(f"  - 问题详情JSON: {json_file}")
    print(f"  - 分布统计CSV: {csv_file}")

    print(f"\n📈 验证结果摘要:")
    print(f"  - 数据总量: {report['total_records']}条")
    print(f"  - L1格式验证: {report['pass_rates']['L1']:.1f}%")
    print(f"  - L2语义验证: {report['pass_rates']['L2']:.1f}%")
    print(f"  - L3推理链验证: {report['pass_rates']['L3']:.1f}%")
    print(f"  - L4坐标验证: {report['pass_rates']['L4']:.1f}%")
    print(f"  - L5 Token映射: {report['pass_rates']['L5']:.1f}%")

    total_issues = sum(len(issues) for issues in report["issues"].values())
    critical = sum(1 for level in report["issues"].values() for i in level if i.get("severity") == "critical")

    print(f"\n⚠️ 问题统计:")
    print(f"  - 总问题数: {total_issues}")
    print(f"  - 严重问题: {critical}")

    if critical == 0:
        print("\n✅ 数据质量良好，可用于实验!")
    else:
        print(f"\n❌ 发现{critical}个严重问题，需要修复!")

    return 0 if critical == 0 else 1


if __name__ == "__main__":
    exit(main())
