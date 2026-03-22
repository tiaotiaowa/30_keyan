#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
提取测试集问题用于大模型评估

输入：data/final/splits/test.jsonl 和 data/final/split_coords/test.jsonl
输出：只包含 id 和 question 的 jsonl 文件
"""

import json
import sys
import io
from pathlib import Path

# Windows UTF-8 输出支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = Path(__file__).parent.parent

def extract_questions(input_file, output_file):
    """提取问题和ID"""
    count = 0
    with open(input_file, 'r', encoding='utf-8') as f_in:
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for line in f_in:
                if line.strip():
                    record = json.loads(line)
                    # 只保留 id 和 question
                    question_record = {
                        "id": record["id"],
                        "question": record["question"]
                    }
                    f_out.write(json.dumps(question_record, ensure_ascii=False) + '\n')
                    count += 1
    return count

def main():
    # 输出目录
    output_dir = BASE_DIR / 'data' / 'eval_questions'
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 提取原始问题（无坐标）
    input1 = BASE_DIR / 'data' / 'final' / 'splits' / 'test.jsonl'
    output1 = output_dir / 'test_questions_original.jsonl'

    print("提取原始问题（无坐标）...")
    count1 = extract_questions(input1, output1)
    print(f"  ✓ 提取 {count1} 条问题")
    print(f"  ✓ 输出: {output1}")

    # 2. 提取带坐标的问题
    input2 = BASE_DIR / 'data' / 'final' / 'split_coords' / 'test.jsonl'
    output2 = output_dir / 'test_questions_with_coords.jsonl'

    print("\n提取带坐标问题...")
    count2 = extract_questions(input2, output2)
    print(f"  ✓ 提取 {count2} 条问题")
    print(f"  ✓ 输出: {output2}")

    print("\n" + "=" * 50)
    print("提取完成!")
    print(f"原始问题: {output1}")
    print(f"带坐标问题: {output2}")

if __name__ == '__main__':
    main()
