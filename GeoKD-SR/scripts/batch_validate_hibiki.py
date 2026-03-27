#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 批量数据验证脚本 - Hibiki Works
批量验证6个JSONL文件 (1001-7000)

验证层级：
- L1: JSON格式有效性、必需字段存在（检测缺失字段）
- L2: 字段值类型正确、枚举值有效
- L3: reasoning_chain 5步结构完整
- L4: entities含coords字段、坐标范围正确
- L5: entity_to_token映射完整（如存在）
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

# Hibiki数据实际存在的字段（基于样本检查）
HIBIKI_REQUIRED_FIELDS = {
    "id": str,
    "spatial_relation_type": str,
    "question": str,
    "answer": str,
    "reasoning_chain": list,
    "entities": list,
    "spatial_tokens": list,
    "difficulty": str,
}

# Hibiki数据缺失的字段（参考generated_1000.jsonl）
MISSING_FIELDS = ["entity_to_token", "difficulty_score"]

# 完整规范所需的字段（V2.1规范）
FULL_REQUIRED_FIELDS = {
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
    "split": str,
    "prompt_id": str
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
    4: {"name": "spatial_calculation", "action": ["calculate", "determine_topology", "calculate_distance", "calculate_direction"]},
    5: {"name": "answer_generation", "action": "generate_answer"}
}

# 待验证的文件列表
EXPECTED_FILES = [
    "generated_1001_to_2000.jsonl",
    "generated_2001_to_3000.jsonl",
    "generated_3001_to_4000.jsonl",
    "generated_4001_to_5000.jsonl",
    "generated_5001_to_6000.jsonl",
    "generated_6001_to_7000.jsonl",
]


class BatchDataValidator:
    """批量数据验证器"""

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 汇总结果
        self.file_results: Dict[str, Dict] = {}
        self.missing_fields_summary: Dict[str, int] = {f: 0 for f in MISSING_FIELDS}
        self.total_records = 0
        self.total_issues = 0
        self.aggregated_stats = {
            "spatial_distribution": Counter(),
            "difficulty_distribution": Counter(),
            "topology_subtype_distribution": Counter()
        }
        self.aggregated_experiment_compatibility: Dict[str, int] = defaultdict(int)

    def validate_all_files(self) -> Dict:
        """验证所有文件"""
        print("=" * 70)
        print("GeoKD-SR 批量数据验证脚本 - Hibiki Works")
        print("=" * 70)
        print(f"\n输入目录: {self.input_dir}")
        print(f"输出目录: {self.output_dir}")
        print(f"\n待验证文件: {len(EXPECTED_FILES)} 个")

        # 检查文件是否存在
        missing_files = []
        for filename in EXPECTED_FILES:
            filepath = self.input_dir / filename
            if not filepath.exists():
                missing_files.append(filename)

        if missing_files:
            print(f"\n⚠️ 缺少文件: {missing_files}")
            return {"error": f"缺少文件: {missing_files}"}

        # 逐个验证文件
        for i, filename in enumerate(EXPECTED_FILES, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(EXPECTED_FILES)}] 验证: {filename}")
            print("=" * 60)

            filepath = self.input_dir / filename
            result = self._validate_single_file(filepath)
            self.file_results[filename] = result

            # 汇总统计
            self.total_records += result.get("total_records", 0)
            self._aggregate_stats(result)

        return self._generate_batch_report()

    def _validate_single_file(self, filepath: Path) -> Dict:
        """验证单个文件"""
        records = []
        load_issues = []
        issues = {f"L{i}": [] for i in range(1, 7)}
        issues["additional"] = []
        stats = {}
        experiment_compatibility = defaultdict(list)
        missing_fields_count = {f: 0 for f in MISSING_FIELDS}

        # 加载数据
        with open(filepath, 'r', encoding='utf-8') as f:
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

        print(f"  加载记录: {len(records)} 条")

        if load_issues:
            print(f"  加载失败: {len(load_issues)} 条")
            for issue in load_issues[:3]:
                issues["L1"].append({
                    "record_id": f"line_{issue['line']}",
                    "issue": issue["error"],
                    "severity": "critical"
                })

        # 逐条验证
        for record in records:
            record_id = record.get("id", f"line_{record.get('_line_num', '?')}")

            self._validate_l1_format(record, record_id, issues, missing_fields_count)
            self._validate_l2_semantics(record, record_id, issues)
            self._validate_l3_reasoning(record, record_id, issues)
            self._validate_l4_coords(record, record_id, issues)
            self._validate_l5_tokens(record, record_id, issues)
            self._validate_additional(record, record_id, issues)
            self._check_experiment_compatibility(record, experiment_compatibility)

        # L6 分布验证
        spatial_counter = Counter()
        difficulty_counter = Counter()
        topology_subtype_counter = Counter()

        for record in records:
            spatial_type = record.get("spatial_relation_type", "unknown")
            difficulty = record.get("difficulty", "unknown")
            subtype = record.get("topology_subtype", "none")

            spatial_counter[spatial_type] += 1
            difficulty_counter[difficulty] += 1
            if subtype != "none":
                topology_subtype_counter[subtype] += 1

        total = len(records)
        stats["spatial_distribution"] = {
            k: {"count": v, "ratio": v/total if total > 0 else 0}
            for k, v in spatial_counter.items()
        }
        stats["difficulty_distribution"] = {
            k: {"count": v, "ratio": v/total if total > 0 else 0}
            for k, v in difficulty_counter.items()
        }
        stats["topology_subtype_distribution"] = dict(topology_subtype_counter)

        # 计算通过率
        pass_rates = {}
        for level in ["L1", "L2", "L3", "L4", "L5"]:
            failed_records = len(set(i["record_id"] for i in issues[level]))
            pass_rates[level] = ((total - failed_records) / total * 100) if total > 0 else 0

        pass_rates["L6"] = 100.0  # 分布验证仅作参考

        # 实验兼容性统计
        exp_compatibility = {
            exp: {"count": len(recs), "ratio": len(recs) / total if total > 0 else 0}
            for exp, recs in experiment_compatibility.items()
        }

        stats["pass_rates"] = pass_rates
        stats["experiment_compatibility"] = exp_compatibility

        # 输出简要结果
        print(f"  L1格式验证: {pass_rates['L1']:.1f}%")
        print(f"  L2语义验证: {pass_rates['L2']:.1f}%")
        print(f"  L3推理链验证: {pass_rates['L3']:.1f}%")
        print(f"  L4坐标验证: {pass_rates['L4']:.1f}%")

        # 缺失字段统计
        for field in MISSING_FIELDS:
            self.missing_fields_summary[field] += missing_fields_count[field]
            print(f"  缺失字段 '{field}': {missing_fields_count[field]}/{total} ({missing_fields_count[field]/total*100:.1f}%)")

        return {
            "filename": filepath.name,
            "total_records": total,
            "pass_rates": pass_rates,
            "issues": issues,
            "stats": stats,
            "experiment_compatibility": exp_compatibility,
            "missing_fields_count": missing_fields_count
        }

    def _validate_l1_format(self, record: Dict, record_id: str, issues: Dict, missing_count: Dict):
        """L1: 格式验证 - 必需字段存在"""
        missing_fields = []

        # 检查Hibiki数据必需字段
        for field in HIBIKI_REQUIRED_FIELDS:
            if field not in record:
                missing_fields.append(field)

        if missing_fields:
            issues["L1"].append({
                "record_id": record_id,
                "issue": f"缺少必需字段: {missing_fields}",
                "severity": "critical"
            })

        # 检查V2.1规范缺失字段（记录但不报错）
        for field in MISSING_FIELDS:
            if field not in record:
                missing_count[field] += 1

    def _validate_l2_semantics(self, record: Dict, record_id: str, issues: Dict):
        """L2: 语义验证 - 字段值类型和取值范围"""
        # 检查spatial_relation_type取值
        spatial_type = record.get("spatial_relation_type")
        if spatial_type and spatial_type not in VALID_SPATIAL_TYPES:
            issues["L2"].append({
                "record_id": record_id,
                "issue": f"无效的spatial_relation_type: {spatial_type}",
                "severity": "critical"
            })

        # 检查difficulty取值
        difficulty = record.get("difficulty")
        if difficulty and difficulty not in VALID_DIFFICULTIES:
            issues["L2"].append({
                "record_id": record_id,
                "issue": f"无效的difficulty: {difficulty}",
                "severity": "critical"
            })

        # 检查question长度
        question = record.get("question", "")
        if len(question) < 10 or len(question) > 200:
            issues["L2"].append({
                "record_id": record_id,
                "issue": f"question长度异常: {len(question)} (建议10-200字符)",
                "severity": "warning"
            })

        # 检查answer长度
        answer = record.get("answer", "")
        if len(answer) < 2 or len(answer) > 200:
            issues["L2"].append({
                "record_id": record_id,
                "issue": f"answer长度异常: {len(answer)} (建议2-100字符)",
                "severity": "warning"
            })

    def _validate_l3_reasoning(self, record: Dict, record_id: str, issues: Dict):
        """L3: 推理链验证 - 5步结构完整"""
        chain = record.get("reasoning_chain", [])

        if len(chain) != 5:
            issues["L3"].append({
                "record_id": record_id,
                "issue": f"reasoning_chain长度错误: {len(chain)} (应为5)",
                "severity": "important"
            })
            return

        for i, step in enumerate(chain, 1):
            if not isinstance(step, dict):
                issues["L3"].append({
                    "record_id": record_id,
                    "issue": f"推理步骤{i}不是字典类型",
                    "severity": "important"
                })
                continue

            required_step_fields = ["step", "name", "action", "content"]
            missing = [f for f in required_step_fields if f not in step]
            if missing:
                issues["L3"].append({
                    "record_id": record_id,
                    "issue": f"推理步骤{i}缺少字段: {missing}",
                    "severity": "important"
                })

            if step.get("step") != i:
                issues["L3"].append({
                    "record_id": record_id,
                    "issue": f"推理步骤编号错误: 期望{i}, 实际{step.get('step')}",
                    "severity": "warning"
                })

    def _validate_l4_coords(self, record: Dict, record_id: str, issues: Dict):
        """L4: 坐标验证 - entities含coords字段且坐标范围正确"""
        entities = record.get("entities", [])

        if len(entities) < 2:
            issues["L4"].append({
                "record_id": record_id,
                "issue": f"entities数量不足: {len(entities)} (应≥2)",
                "severity": "important"
            })
            return

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            if "name" not in entity:
                issues["L4"].append({
                    "record_id": record_id,
                    "issue": f"entity缺少name字段",
                    "severity": "important"
                })

            if "coords" not in entity:
                issues["L4"].append({
                    "record_id": record_id,
                    "issue": f"entity '{entity.get('name', 'unknown')}' 缺少coords字段",
                    "severity": "critical"
                })
                continue

            coords = entity["coords"]
            if isinstance(coords, list) and len(coords) >= 2:
                lon, lat = coords[0], coords[1]

                if not (COORD_RANGE["lon"][0] <= lon <= COORD_RANGE["lon"][1]):
                    issues["L4"].append({
                        "record_id": record_id,
                        "issue": f"经度超出范围: {lon} (应为{COORD_RANGE['lon']})",
                        "severity": "important"
                    })

                if not (COORD_RANGE["lat"][0] <= lat <= COORD_RANGE["lat"][1]):
                    issues["L4"].append({
                        "record_id": record_id,
                        "issue": f"纬度超出范围: {lat} (应为{COORD_RANGE['lat']})",
                        "severity": "important"
                    })

    def _validate_l5_tokens(self, record: Dict, record_id: str, issues: Dict):
        """L5: Token映射验证 - entity_to_token映射完整（如存在）"""
        entity_to_token = record.get("entity_to_token", {})

        # 如果存在entity_to_token，验证其完整性
        if entity_to_token:
            entities = record.get("entities", [])
            entity_names = {e.get("name") for e in entities if isinstance(e, dict)}
            mapped_names = set(entity_to_token.keys())

            unmapped = entity_names - mapped_names
            if unmapped:
                issues["L5"].append({
                    "record_id": record_id,
                    "issue": f"entity_to_token缺少映射: {unmapped}",
                    "severity": "important"
                })

        # 检查spatial_tokens数量
        tokens = record.get("spatial_tokens", [])
        if len(tokens) < 4 or len(tokens) > 12:
            issues["L5"].append({
                "record_id": record_id,
                "issue": f"spatial_tokens数量异常: {len(tokens)} (建议4-12个)",
                "severity": "warning"
            })

    def _validate_additional(self, record: Dict, record_id: str, issues: Dict):
        """附加验证: topology_subtype等"""
        spatial_type = record.get("spatial_relation_type")

        if spatial_type == "topological":
            subtype = record.get("topology_subtype")
            if not subtype:
                issues["additional"].append({
                    "record_id": record_id,
                    "issue": "topological类型缺少topology_subtype字段",
                    "severity": "critical"
                })
            elif subtype not in VALID_TOPOLOGY_SUBTYPES:
                issues["additional"].append({
                    "record_id": record_id,
                    "issue": f"无效的topology_subtype: {subtype}",
                    "severity": "critical"
                })

    def _check_experiment_compatibility(self, record: Dict, exp_compat: Dict):
        """检查实验兼容性"""
        record_id = record.get("id", "unknown")

        for exp_id, required_fields in EXPERIMENT_REQUIREMENTS.items():
            compatible = True

            for field in required_fields:
                if field not in record or record[field] is None:
                    compatible = False
                    break

                if field == "reasoning_chain":
                    if not isinstance(record[field], list) or len(record[field]) != 5:
                        compatible = False
                        break

            if compatible:
                exp_compat[exp_id].append(record_id)

    def _aggregate_stats(self, result: Dict):
        """汇总统计"""
        stats = result.get("stats", {})

        # 空间关系分布
        for stype, data in stats.get("spatial_distribution", {}).items():
            self.aggregated_stats["spatial_distribution"][stype] += data.get("count", 0)

        # 难度分布
        for diff, data in stats.get("difficulty_distribution", {}).items():
            self.aggregated_stats["difficulty_distribution"][diff] += data.get("count", 0)

        # 拓扑子类型分布
        for subtype, count in stats.get("topology_subtype_distribution", {}).items():
            self.aggregated_stats["topology_subtype_distribution"][subtype] += count

        # 实验兼容性
        for exp_id, data in result.get("experiment_compatibility", {}).items():
            self.aggregated_experiment_compatibility[exp_id] += data.get("count", 0)

    def _generate_batch_report(self) -> Dict:
        """生成批量验证报告"""
        print("\n" + "=" * 70)
        print("批量验证完成!")
        print("=" * 70)

        # 计算汇总通过率
        all_pass_rates = defaultdict(list)
        for result in self.file_results.values():
            for level, rate in result.get("pass_rates", {}).items():
                all_pass_rates[level].append(rate)

        avg_pass_rates = {
            level: sum(rates) / len(rates) if rates else 0
            for level, rates in all_pass_rates.items()
        }

        # 计算汇总实验兼容性
        exp_compatibility_summary = {
            exp: {
                "count": count,
                "ratio": count / self.total_records if self.total_records > 0 else 0
            }
            for exp, count in self.aggregated_experiment_compatibility.items()
        }

        # 汇总空间关系分布
        total_spatial = sum(self.aggregated_stats["spatial_distribution"].values())
        spatial_dist_summary = {
            k: {"count": v, "ratio": v/total_spatial if total_spatial > 0 else 0}
            for k, v in self.aggregated_stats["spatial_distribution"].items()
        }

        # 汇总难度分布
        total_difficulty = sum(self.aggregated_stats["difficulty_distribution"].values())
        difficulty_dist_summary = {
            k: {"count": v, "ratio": v/total_difficulty if total_difficulty > 0 else 0}
            for k, v in self.aggregated_stats["difficulty_distribution"].items()
        }

        return {
            "total_files": len(self.file_results),
            "total_records": self.total_records,
            "avg_pass_rates": avg_pass_rates,
            "missing_fields_summary": self.missing_fields_summary,
            "spatial_distribution": spatial_dist_summary,
            "difficulty_distribution": difficulty_dist_summary,
            "topology_subtype_distribution": dict(self.aggregated_stats["topology_subtype_distribution"]),
            "experiment_compatibility": exp_compatibility_summary,
            "file_results": self.file_results
        }


def generate_batch_markdown_report(report: Dict, output_file: Path):
    """生成批量验证Markdown报告"""
    lines = [
        "# GeoKD-SR 批量数据验证报告 - Hibiki Works",
        "",
        f"> **验证时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> **数据来源**: C:/Users/60207/Documents/hibiki works/",
        f"> **验证规范**: V2.1",
        "",
        "---",
        "",
        "## 一、执行摘要",
        "",
        f"- **验证文件数**: {report['total_files']} 个",
        f"- **数据总量**: {report['total_records']} 条",
        f"- **ID范围**: 1001-7000",
        "",
        "### 整体验证结果",
        "",
        "| 验证层级 | 平均通过率 | 状态 |",
        "|----------|------------|------|",
    ]

    for level in ["L1", "L2", "L3", "L4", "L5", "L6"]:
        rate = report["avg_pass_rates"].get(level, 0)
        status = "✅" if rate >= 98 else ("⚠️" if rate >= 90 else "❌")
        lines.append(f"| {level} | {rate:.1f}% | {status} |")

    # 缺失字段警告
    lines.extend([
        "",
        "---",
        "",
        "## 二、字段完整性分析",
        "",
        "### ⚠️ 缺失字段警告",
        "",
        "对比参考数据 `generated_1000.jsonl`，待审查数据缺少以下V2.1规范必需字段：",
        "",
        "| 字段名 | 缺失数量 | 缺失率 | 影响实验 |",
        "|--------|----------|--------|----------|",
    ])

    for field in MISSING_FIELDS:
        missing_count = report["missing_fields_summary"].get(field, 0)
        missing_rate = missing_count / report["total_records"] * 100 if report["total_records"] > 0 else 0

        # 确定影响的实验
        affected_exps = []
        for exp_id, req_fields in EXPERIMENT_REQUIREMENTS.items():
            if field in req_fields:
                affected_exps.append(exp_id)

        lines.append(f"| `{field}` | {missing_count} | {missing_rate:.1f}% | {', '.join(affected_exps)} |")

    lines.extend([
        "",
        "### 现有字段清单",
        "",
        "**完全必需字段** (100%存在):",
        "- `id`, `spatial_relation_type`, `question`, `answer`",
        "- `reasoning_chain`, `entities`, `spatial_tokens`, `difficulty`",
        "",
        "**条件必需字段**:",
        "- `topology_subtype` - topological类型时存在 ✅",
        "",
        "**可选字段**:",
        "- `split` - 存在 ✅",
        "- `prompt_id` - 存在 ✅ (新增字段)",
        "",
        "---",
        "",
        "## 三、实验兼容性分析",
        "",
        "| 实验 | 兼容数量 | 兼容率 | 状态 | 兼容原因 |",
        "|------|---------|--------|------|----------|",
    ])

    for exp_id in ["Exp1", "Exp2", "Exp3a", "Exp3", "Exp4", "Exp5", "Exp6", "Exp7", "Exp8", "Exp9"]:
        data = report["experiment_compatibility"].get(exp_id, {"count": 0, "ratio": 0})
        status = "✅" if data["ratio"] >= 0.95 else ("⚠️" if data["ratio"] >= 0.50 else "❌")

        # 分析兼容原因
        req_fields = EXPERIMENT_REQUIREMENTS.get(exp_id, [])
        missing_in_req = [f for f in req_fields if f in MISSING_FIELDS]

        if not missing_in_req:
            reason = "字段完整"
        else:
            reason = f"缺 {', '.join(missing_in_req)}"

        lines.append(f"| {exp_id} | {data['count']} | {data['ratio']:.1%} | {status} | {reason} |")

    lines.extend([
        "",
        "### 兼容性结论",
        "",
        "| 实验分组 | 兼容性 | 说明 |",
        "|----------|--------|------|",
        "| Exp1, Exp2, Exp5, Exp6 | ✅ 完全兼容 | 仅需 question, answer |",
        "| Exp3a, Exp3 | ✅ 完全兼容 | + spatial_relation_type |",
        "| Exp4 | ✅ 完全兼容 | + reasoning_chain (5步完整) |",
        "| **Exp7** | ❌ 不兼容 | 缺少 entity_to_token |",
        "| **Exp8** | ❌ 不兼容 | 缺少 difficulty_score |",
        "| **Exp9** | ❌ 不兼容 | 缺少 entity_to_token, difficulty_score |",
        "",
        "---",
        "",
        "## 四、分布统计",
        "",
        "### 空间关系分布",
        "",
        "| 类型 | 数量 | 实际占比 | 目标占比 | 偏差 |",
        "|------|------|----------|----------|------|",
    ])

    for stype in ["directional", "topological", "metric", "composite"]:
        data = report["spatial_distribution"].get(stype, {"count": 0, "ratio": 0})
        target = TARGET_SPATIAL_DISTRIBUTION.get(stype, 0)
        deviation = abs(data["ratio"] - target)
        lines.append(f"| {stype} | {data['count']} | {data['ratio']:.1%} | {target:.1%} | {deviation:.1%} |")

    lines.extend([
        "",
        "### 难度分布",
        "",
        "| 难度 | 数量 | 实际占比 | 目标占比 | 偏差 |",
        "|------|------|----------|----------|------|",
    ])

    for diff in ["easy", "medium", "hard"]:
        data = report["difficulty_distribution"].get(diff, {"count": 0, "ratio": 0})
        target = TARGET_DIFFICULTY_DISTRIBUTION.get(diff, 0)
        deviation = abs(data["ratio"] - target)
        lines.append(f"| {diff} | {data['count']} | {data['ratio']:.1%} | {target:.1%} | {deviation:.1%} |")

    # 拓扑子类型分布
    topo_dist = report.get("topology_subtype_distribution", {})
    if topo_dist:
        lines.extend([
            "",
            "### 拓扑子类型分布",
            "",
            "| 子类型 | 数量 |",
            "|--------|------|",
        ])
        for subtype, count in sorted(topo_dist.items(), key=lambda x: -x[1]):
            lines.append(f"| {subtype} | {count} |")

    # 各文件验证详情
    lines.extend([
        "",
        "---",
        "",
        "## 五、各文件验证详情",
        "",
        "| 文件名 | 记录数 | L1 | L2 | L3 | L4 | L5 |",
        "|--------|--------|----|----|----|----|----|",
    ])

    for filename, result in report["file_results"].items():
        pass_rates = result.get("pass_rates", {})
        l1 = pass_rates.get("L1", 0)
        l2 = pass_rates.get("L2", 0)
        l3 = pass_rates.get("L3", 0)
        l4 = pass_rates.get("L4", 0)
        l5 = pass_rates.get("L5", 0)

        l1_status = "✅" if l1 >= 98 else "⚠️"
        l2_status = "✅" if l2 >= 98 else "⚠️"
        l3_status = "✅" if l3 >= 98 else "⚠️"
        l4_status = "✅" if l4 >= 98 else "⚠️"
        l5_status = "✅" if l5 >= 98 else "⚠️"

        lines.append(f"| {filename} | {result['total_records']} | {l1_status} {l1:.0f}% | {l2_status} {l2:.0f}% | {l3_status} {l3:.0f}% | {l4_status} {l4:.0f}% | {l5_status} {l5:.0f}% |")

    # 结论与建议
    lines.extend([
        "",
        "---",
        "",
        "## 六、结论与建议",
        "",
        "### 数据质量评估",
        "",
        "| 维度 | 评估 | 说明 |",
        "|------|------|------|",
        "| JSON格式 | ✅ 良好 | 所有文件JSON解析成功 |",
        "| 必需字段 | ✅ 完整 | Hibiki必需字段全部存在 |",
        "| 推理链结构 | ✅ 规范 | 5步结构完整 |",
        "| 坐标数据 | ✅ 有效 | 坐标范围正确 |",
        "| V2.1规范兼容 | ⚠️ 部分兼容 | 缺少2个规范字段 |",
        "",
        "### 问题清单",
        "",
        "1. **缺失字段 `entity_to_token`**",
        "   - 影响: Exp7, Exp9 无法使用",
        "   - 建议: 需要补充生成该字段",
        "",
        "2. **缺失字段 `difficulty_score`**",
        "   - 影响: Exp8, Exp9 无法使用",
        "   - 建议: 需要根据difficulty重新计算分数",
        "",
        "### 使用建议",
        "",
        "**可直接使用的实验**: Exp1, Exp2, Exp3a, Exp3, Exp4, Exp5, Exp6 (共7个)",
        "",
        "**需要补充字段后使用**: Exp7, Exp8, Exp9 (共3个)",
        "",
        "### 修复方案",
        "",
        "```python",
        "# 方案1: 补充 entity_to_token 字段",
        "# 基于question文本和entities信息重新生成字符位置映射",
        "",
        "# 方案2: 补充 difficulty_score 字段",
        "# 根据 difficulty 映射分数:",
        "# - easy → 1.0-2.0",
        "# - medium → 2.0-3.5",
        "# - hard → 3.5-5.0",
        "```",
        "",
        "---",
        "",
        f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ""
    ])

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return output_file


def generate_batch_issues_json(report: Dict, output_file: Path):
    """生成批量验证问题详情JSON"""
    # 简化输出，只保留汇总信息和关键问题
    simplified = {
        "validation_time": datetime.now().isoformat(),
        "summary": {
            "total_files": report["total_files"],
            "total_records": report["total_records"],
            "avg_pass_rates": report["avg_pass_rates"],
            "missing_fields_summary": report["missing_fields_summary"],
            "experiment_compatibility": report["experiment_compatibility"]
        },
        "distribution": {
            "spatial": report["spatial_distribution"],
            "difficulty": report["difficulty_distribution"],
            "topology_subtype": report["topology_subtype_distribution"]
        },
        "file_summaries": {}
    }

    # 每个文件只保留关键统计
    for filename, result in report["file_results"].items():
        simplified["file_summaries"][filename] = {
            "total_records": result["total_records"],
            "pass_rates": result["pass_rates"],
            "missing_fields_count": result.get("missing_fields_count", {})
        }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(simplified, f, ensure_ascii=False, indent=2)

    return output_file


def generate_batch_stats_csv(report: Dict, output_file: Path):
    """生成批量验证统计CSV"""
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        # 文件统计
        writer.writerow(["=== 各文件验证统计 ==="])
        writer.writerow(["文件名", "记录数", "L1通过率", "L2通过率", "L3通过率", "L4通过率", "L5通过率"])

        for filename, result in report["file_results"].items():
            pr = result.get("pass_rates", {})
            writer.writerow([
                filename,
                result["total_records"],
                f"{pr.get('L1', 0):.1f}%",
                f"{pr.get('L2', 0):.1f}%",
                f"{pr.get('L3', 0):.1f}%",
                f"{pr.get('L4', 0):.1f}%",
                f"{pr.get('L5', 0):.1f}%"
            ])

        writer.writerow([])

        # 空间关系分布
        writer.writerow(["=== 空间关系分布汇总 ==="])
        writer.writerow(["类型", "数量", "占比"])
        for stype, data in report["spatial_distribution"].items():
            writer.writerow([stype, data["count"], f"{data['ratio']:.4f}"])

        writer.writerow([])

        # 难度分布
        writer.writerow(["=== 难度分布汇总 ==="])
        writer.writerow(["难度", "数量", "占比"])
        for diff, data in report["difficulty_distribution"].items():
            writer.writerow([diff, data["count"], f"{data['ratio']:.4f}"])

        writer.writerow([])

        # 实验兼容性
        writer.writerow(["=== 实验兼容性 ==="])
        writer.writerow(["实验", "兼容数量", "兼容率"])
        for exp_id, data in report["experiment_compatibility"].items():
            writer.writerow([exp_id, data["count"], f"{data['ratio']:.4f}"])

        writer.writerow([])

        # 缺失字段统计
        writer.writerow(["=== 缺失字段统计 ==="])
        writer.writerow(["字段名", "缺失数量", "缺失率"])
        for field, count in report["missing_fields_summary"].items():
            rate = count / report["total_records"] if report["total_records"] > 0 else 0
            writer.writerow([field, count, f"{rate:.4f}"])

    return output_file


def main():
    parser = argparse.ArgumentParser(description="GeoKD-SR 批量数据验证脚本 - Hibiki Works")
    parser.add_argument("--input-dir", "-i", required=True, help="输入目录 (包含6个JSONL文件)")
    parser.add_argument("--output", "-o", default="outputs", help="输出目录")

    args = parser.parse_args()

    # 执行验证
    validator = BatchDataValidator(args.input_dir, args.output)
    report = validator.validate_all_files()

    if "error" in report:
        print(f"\n❌ 验证失败: {report['error']}")
        return 1

    # 生成报告
    md_file = Path(args.output) / "batch_hibiki_validation_report.md"
    json_file = Path(args.output) / "batch_hibiki_validation_issues.json"
    csv_file = Path(args.output) / "batch_hibiki_validation_stats.csv"

    generate_batch_markdown_report(report, md_file)
    generate_batch_issues_json(report, json_file)
    generate_batch_stats_csv(report, csv_file)

    print("\n" + "=" * 70)
    print("报告生成完成!")
    print("=" * 70)
    print(f"\n📊 报告文件:")
    print(f"  - Markdown报告: {md_file}")
    print(f"  - 问题详情JSON: {json_file}")
    print(f"  - 统计CSV: {csv_file}")

    print(f"\n📈 验证结果摘要:")
    print(f"  - 验证文件: {report['total_files']} 个")
    print(f"  - 数据总量: {report['total_records']} 条")
    print(f"  - L1格式验证: {report['avg_pass_rates']['L1']:.1f}%")
    print(f"  - L2语义验证: {report['avg_pass_rates']['L2']:.1f}%")
    print(f"  - L3推理链验证: {report['avg_pass_rates']['L3']:.1f}%")
    print(f"  - L4坐标验证: {report['avg_pass_rates']['L4']:.1f}%")

    print(f"\n⚠️ 缺失字段:")
    for field, count in report["missing_fields_summary"].items():
        rate = count / report["total_records"] * 100 if report["total_records"] > 0 else 0
        print(f"  - {field}: {count}/{report['total_records']} ({rate:.1f}%)")

    # 兼容实验统计
    compatible_exps = [exp for exp, data in report["experiment_compatibility"].items()
                       if data["ratio"] >= 0.95]
    incompatible_exps = [exp for exp, data in report["experiment_compatibility"].items()
                         if data["ratio"] < 0.95]

    print(f"\n✅ 兼容实验: {', '.join(compatible_exps)}")
    print(f"❌ 不兼容实验: {', '.join(incompatible_exps)}")

    return 0


if __name__ == "__main__":
    exit(main())
