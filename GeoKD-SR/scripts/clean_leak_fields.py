#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清除 reasoning_chain 中的泄露字段

移除字段:
- relation_type (step 2) - 直接暴露 spatial_relation_type 标签
- calculation_result (step 4) - 直接暴露 topology_subtype 标签

使用方法:
    python scripts/clean_leak_fields.py \
        --input data/final/final_1.jsonl \
        --output data/final/final_1_cleaned.jsonl
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# 泄露字段列表
LEAK_FIELDS = ["relation_type", "calculation_result"]

def clean_reasoning_chain(chain: List[Dict]) -> List[Dict]:
    """清洗推理链中的泄露字段"""
    cleaned = []
    for step in chain:
        clean_step = {}
        for key, value in step.items():
            if key not in LEAK_FIELDS:
                clean_step[key] = value
        cleaned.append(clean_step)
    return cleaned

def clean_record(record: Dict) -> Dict:
    """清洗单条记录"""
    cleaned = record.copy()
    if "reasoning_chain" in cleaned:
        cleaned["reasoning_chain"] = clean_reasoning_chain(cleaned["reasoning_chain"])
    return cleaned

def verify_no_leak(filepath: str) -> Tuple[bool, str]:
    """验证数据中不再包含泄露字段"""
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            record = json.loads(line)
            for step in record.get("reasoning_chain", []):
                if "relation_type" in step:
                    return False, f"行 {i+1} 仍包含 relation_type"
                if "calculation_result" in step:
                    return False, f"行 {i+1} 仍包含 calculation_result"
    return True, "验证通过：无泄露字段"

def verify_chain_integrity(filepath: str) -> Tuple[bool, str]:
    """验证推理链结构完整"""
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            record = json.loads(line)
            chain = record.get("reasoning_chain", [])
            if len(chain) != 5:
                return False, f"行 {i+1} 推理链长度异常: {len(chain)}"
            for step in chain:
                required = ["step", "name", "action", "content"]
                for field in required:
                    if field not in step:
                        return False, f"行 {i+1} 缺少字段: {field}"
    return True, "推理链结构完整"

def main():
    parser = argparse.ArgumentParser(description="清除推理链中的泄露字段")
    parser.add_argument("--input", "-i", required=True, help="输入文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出文件路径")
    parser.add_argument("--verify", "-v", action="store_true", help="清洗后验证")
    args = parser.parse_args()

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始处理...")
    print(f"输入文件: {args.input}")
    print(f"输出文件: {args.output}")

    # 读取数据
    records = []
    with open(args.input, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print(f"读取 {len(records)} 条记录")

    # 统计泄露字段
    leak_stats = {"relation_type": 0, "calculation_result": 0}
    for r in records:
        for step in r.get("reasoning_chain", []):
            if "relation_type" in step:
                leak_stats["relation_type"] += 1
            if "calculation_result" in step:
                leak_stats["calculation_result"] += 1

    print(f"\n泄露字段统计:")
    print(f"  - relation_type: {leak_stats['relation_type']} 处")
    print(f"  - calculation_result: {leak_stats['calculation_result']} 处")

    # 清洗数据
    cleaned_records = [clean_record(r) for r in records]

    # 确保输出目录存在
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # 写入清洗后的数据
    with open(args.output, "w", encoding="utf-8") as f:
        for r in cleaned_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n输出到 {args.output}")
    print(f"清洗完成: {len(cleaned_records)} 条记录")

    # 验证
    if args.verify:
        print(f"\n{'='*50}")
        print("验证清洗结果...")
        print(f"{'='*50}")

        ok1, msg1 = verify_no_leak(args.output)
        print(f"[泄露检查] {msg1}")

        ok2, msg2 = verify_chain_integrity(args.output)
        print(f"[完整性检查] {msg2}")

        if ok1 and ok2:
            print("\n✓ 所有验证通过!")
        else:
            print("\n✗ 验证失败，请检查!")

if __name__ == "__main__":
    main()
