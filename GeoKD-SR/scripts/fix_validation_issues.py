#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR 数据修复脚本
修复验证报告中发现的所有问题
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

# 问题记录ID和修复方案
FIXES = {
    # Critical: 无效topology_subtype
    "geosr_topological_prompt_0034_5941": {
        "type": "topology_subtype",
        "old": "touch",
        "new": "adjacent"
    },

    # Important: entity_to_token缺少映射
    "geosr_metric_prompt_0923_1557": {
        "type": "entity_to_token",
        "add_mapping": {
            "鼓浪屿郑成功纪念馆": {
                "char_start": 5,
                "char_end": 13,
                "token_indices": [5, 6, 7, 8, 9, 10, 11, 12, 13]
            }
        }
    },

    # Warning: answer长度过长 - 简化答案
    "geosr_metric_prompt_0143_2503": {
        "type": "answer",
        "new_answer": "青岛与烟台之间的直线距离约为851.4公里。"
    },
    "geosr_topological_prompt_0191_1086": {
        "type": "answer",
        "new_answer": "北京与台北在空间上不相邻，两地直线距离超过1700公里。"
    },
    "geosr_topological_prompt_0244_1838": {
        "type": "answer",
        "new_answer": "茶卡盐湖位于青海省境内，属于包含关系。"
    },
    "geosr_topological_prompt_0274_2845": {
        "type": "answer",
        "new_answer": "克拉玛依与上海市不相邻，两地空间上没有直接接触。"
    },
    "geosr_topological_prompt_0421_8717": {
        "type": "answer",
        "new_answer": "开封市不在黄山市内，两省相距约一千公里。"
    },
    "geosr_topological_prompt_0471_6878": {
        "type": "answer",
        "new_answer": "武夷山与浙江省不相邻，两省边界无直接接触。"
    },
    "geosr_topological_prompt_0547_7112": {
        "type": "answer",
        "new_answer": "龙虎山在四川省内，属于包含关系。"
    },
    "geosr_topological_prompt_0566_1646": {
        "type": "answer",
        "new_answer": "莫高窟与大理在空间上不相邻，直线距离超过2800公里。"
    },
    "geosr_metric_prompt_0773_8054": {
        "type": "answer",
        "new_answer": "青海省与色达县直线距离约为2831.1公里。"
    },
    "geossr_topological_prompt_0810_3502": {
        "type": "answer",
        "new_answer": "福州市位于福建省境内，属于包含关系。"
    },
    "geosr_metric_prompt_0876_8304": {
        "type": "answer",
        "new_answer": "三亚与长城的直线距离约为1691.6公里。"
    },
    "geosr_metric_prompt_0977_1083": {
        "type": "answer",
        "new_answer": "三亚与火焰山直线距离约为922.8公里。"
    },
    "geosr_topological_prompt_0979_2361": {
        "type": "answer",
        "new_answer": "鄱阳湖与北京市不相邻，直线距离超过1000公里。"
    }
}


def fix_records(input_file: str, output_file: str) -> Tuple[int, List[str]]:
    """修复数据记录"""
    records = []
    fixed_count = 0
    fix_details = []

    # 读取所有记录
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # 修复问题记录
    for record in records:
        record_id = record.get("id")
        if record_id in FIXES:
            fix = FIXES[record_id]
            fix_type = fix["type"]

            if fix_type == "topology_subtype":
                # 修复无效的topology_subtype
                old_val = record.get("topology_subtype")
                record["topology_subtype"] = fix["new"]
                fix_details.append(f"[{record_id}] topology_subtype: {old_val} -> {fix['new']}")
                fixed_count += 1

            elif fix_type == "entity_to_token":
                # 补充缺失的entity_to_token映射
                for entity_name, mapping in fix["add_mapping"].items():
                    record["entity_to_token"][entity_name] = mapping
                fix_details.append(f"[{record_id}] 添加entity_to_token映射")
                fixed_count += 1

            elif fix_type == "answer":
                # 简化过长的answer
                old_len = len(record.get("answer", ""))
                record["answer"] = fix["new_answer"]
                new_len = len(fix["new_answer"])
                fix_details.append(f"[{record_id}] answer长度: {old_len} -> {new_len}")
                fixed_count += 1

    # 写入修复后的数据
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    return fixed_count, fix_details


def main():
    input_file = Path("D:/30_keyan/GeoKD-SR/data/geosr_chain/generated_1000.jsonl")
    output_file = Path("D:/30_keyan/GeoKD-SR/data/geosr_chain/generated_1000_fixed.jsonl")

    print("=" * 60)
    print("GeoKD-SR 数据修复脚本")
    print("=" * 60)

    print(f"\n输入文件: {input_file}")
    print(f"输出文件: {output_file}")

    print("\n[执行修复]")
    fixed_count, fix_details = fix_records(str(input_file), str(output_file))

    print(f"\n修复完成! 共修复 {fixed_count} 条记录")
    print("\n修复详情:")
    for detail in fix_details:
        print(f"  - {detail}")

    print(f"\n输出文件: {output_file}")
    print("\n请运行验证脚本确认修复结果:")
    print(f"  python scripts/validate_generated_data.py --input {output_file} --output outputs")


if __name__ == "__main__":
    main()
