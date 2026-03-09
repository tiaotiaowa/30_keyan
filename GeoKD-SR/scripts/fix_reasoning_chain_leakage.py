#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 推理链泄露修复脚本
修复推理链中的泄露问题，将暴露任务类型的字段通用化
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from collections import Counter


# 字段映射表 - 将具体类型改为通用"spatial"
RELATION_TYPE_MAPPING = {
    "directional": "spatial",
    "topological": "spatial",
    "metric": "spatial",
    "composite": "spatial"
}

# action通用化映射
ACTION_MAPPING = {
    "calculate_distance": "process_spatial",
    "determine_topology": "process_spatial",
    "calculate_direction": "process_spatial",
    "classify_relation": "analyze_spatial",
    "calculate_composite": "analyze_spatial"
}


class ReasoningChainLeakageFixer:
    """推理链泄露修复器"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.stats = {
            "total_records": 0,
            "total_steps": 0,
            "fixed_relation_type": 0,
            "fixed_action": 0,
            "relation_type_distribution": Counter(),
            "action_distribution": Counter()
        }

    def fix_step(self, step: Dict) -> Dict:
        """修复单个推理步骤"""
        step = step.copy()  # 避免修改原始数据

        # 修复step 2中的relation_type字段
        if step.get("step") == 2:
            original_type = step.get("relation_type", "")
            if original_type in RELATION_TYPE_MAPPING:
                step["relation_type"] = RELATION_TYPE_MAPPING[original_type]
                self.stats["fixed_relation_type"] += 1
                if self.verbose:
                    self.stats["relation_type_distribution"][original_type] += 1

        # 修复step 4中的action字段
        if step.get("step") == 4:
            original_action = step.get("action", "")
            if original_action in ACTION_MAPPING:
                step["action"] = ACTION_MAPPING[original_action]
                self.stats["fixed_action"] += 1
                if self.verbose:
                    self.stats["action_distribution"][original_action] += 1

        return step

    def fix_record(self, record: Dict) -> Dict:
        """修复单条记录的推理链"""
        record = record.copy()  # 避免修改原始数据

        if "reasoning_chain" not in record:
            return record

        # 修复推理链中的每个步骤
        fixed_chain = []
        for step in record["reasoning_chain"]:
            self.stats["total_steps"] += 1
            fixed_step = self.fix_step(step)
            fixed_chain.append(fixed_step)

        record["reasoning_chain"] = fixed_chain
        return record

    def process_file(self, input_file: Path, output_file: Path) -> Dict:
        """处理单个文件"""
        print(f"\n处理文件: {input_file.name}")
        print(f"输入路径: {input_file}")

        records = []
        local_stats = {
            "total": 0,
            "fixed_records": 0
        }

        with open(input_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  警告: 第{line_num}行JSON解析错误: {e}")
                    continue

                local_stats["total"] += 1
                self.stats["total_records"] += 1

                # 记录修复前的状态
                has_leakage = self._check_leakage(record)

                # 修复推理链
                fixed_record = self.fix_record(record)
                records.append(fixed_record)

                if has_leakage:
                    local_stats["fixed_records"] += 1

                # 进度显示
                if local_stats["total"] % 500 == 0:
                    print(f"  进度: {local_stats['total']} 条记录")

        # 确保输出目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        print(f"  完成: {local_stats['total']} 条记录")
        print(f"  修复记录: {local_stats['fixed_records']} 条")

        return local_stats

    def _check_leakage(self, record: Dict) -> bool:
        """检查记录是否存在泄露问题"""
        if "reasoning_chain" not in record:
            return False

        for step in record["reasoning_chain"]:
            # 检查step 2的relation_type
            if step.get("step") == 2:
                relation_type = step.get("relation_type", "")
                if relation_type in RELATION_TYPE_MAPPING:
                    return True

            # 检查step 4的action
            if step.get("step") == 4:
                action = step.get("action", "")
                if action in ACTION_MAPPING:
                    return True

        return False

    def generate_report(self) -> str:
        """生成修复报告"""
        report_lines = [
            "=" * 70,
            "推理链泄露修复报告",
            "=" * 70,
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "修复统计:",
            f"  总记录数: {self.stats['total_records']}",
            f"  总推理步骤数: {self.stats['total_steps']}",
            f"  修复relation_type字段: {self.stats['fixed_relation_type']} 处",
            f"  修复action字段: {self.stats['fixed_action']} 处",
            "",
            "relation_type分布 (修复前):"
        ]

        for rel_type, count in self.stats["relation_type_distribution"].most_common():
            report_lines.append(f"  - {rel_type}: {count}")

        report_lines.append("")
        report_lines.append("action分布 (修复前):")

        for action, count in self.stats["action_distribution"].most_common():
            report_lines.append(f"  - {action}: {count}")

        report_lines.extend([
            "",
            "修复映射:",
            "  relation_type: " + ", ".join([f"{k}→{v}" for k, v in RELATION_TYPE_MAPPING.items()]),
            "  action: " + ", ".join([f"{k}→{v}" for k, v in ACTION_MAPPING.items()]),
            "",
            "=" * 70
        ])

        return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(
        description="GeoKD-SR 推理链泄露修复脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 修复单个文件
  python fix_reasoning_chain_leakage.py --input data/geosr_chain/train.jsonl --output data/geosr_chain/train_fixed.jsonl

  # 修复并覆盖原文件
  python fix_reasoning_chain_leakage.py --input data/geosr_chain/train.jsonl

  # 处理多个文件
  python fix_reasoning_chain_leakage.py --input data/geosr_chain/train.jsonl --output data/geosr_chain/train_fixed.jsonl
  python fix_reasoning_chain_leakage.py --input data/geosr_chain/dev.jsonl --output data/geosr_chain/dev_fixed.jsonl
  python fix_reasoning_chain_leakage.py --input data/geosr_chain/test.jsonl --output data/geosr_chain/test_fixed.jsonl
        """
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="输入文件路径 (JSONL格式)"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件路径 (默认为输入文件名_fixed.jsonl)"
    )
    parser.add_argument(
        "--report", "-r",
        help="修复报告输出路径 (默认为输出文件名_report.md)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="安静模式，减少输出"
    )

    args = parser.parse_args()

    # 处理路径
    input_file = Path(args.input)
    if not input_file.exists():
        print(f"错误: 输入文件不存在: {input_file}")
        return 1

    # 默认输出路径
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = input_file.parent / f"{input_file.stem}_fixed{input_file.suffix}"

    # 默认报告路径
    if args.report:
        report_file = Path(args.report)
    else:
        report_file = output_file.parent / f"{output_file.stem}_report.md"

    # 创建修复器
    fixer = ReasoningChainLeakageFixer(verbose=not args.quiet)

    # 打印开始信息
    print("=" * 70)
    print("GeoKD-SR 推理链泄露修复脚本")
    print("=" * 70)
    print(f"\n输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"报告文件: {report_file}")

    # 处理文件
    fixer.process_file(input_file, output_file)

    # 生成报告
    report_content = fixer.generate_report()
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)

    # 打印摘要
    print("\n" + "=" * 70)
    print("修复完成!")
    print("=" * 70)
    print(f"\n修复摘要:")
    print(f"  处理记录: {fixer.stats['total_records']} 条")
    print(f"  修复relation_type: {fixer.stats['fixed_relation_type']} 处")
    print(f"  修复action: {fixer.stats['fixed_action']} 处")
    print(f"\n输出文件: {output_file}")
    print(f"修复报告: {report_file}")

    return 0


if __name__ == "__main__":
    exit(main())
