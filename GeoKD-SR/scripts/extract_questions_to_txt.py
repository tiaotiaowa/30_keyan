#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
提取问题为纯文本格式（TXT）

输入：eval_questions 目录下的 JSONL 文件
输出：只包含问题的 TXT 文件
"""

import json
import sys
import io
from pathlib import Path

# Windows UTF-8 输出支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = Path(__file__).parent.parent

def extract_to_txt(input_file, output_file):
    """提取问题到TXT文件"""
    count = 0
    with open(input_file, 'r', encoding='utf-8') as f_in:
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for line in f_in:
                if line.strip():
                    record = json.loads(line)
                    # 只写入问题，每行一个问题
                    f_out.write(record["question"] + '\n')
                    count += 1
    return count

def main():
    input_dir = BASE_DIR / 'data' / 'eval_questions'

    # 1. 原始问题（无坐标）
    input1 = input_dir / 'test_questions_original.jsonl'
    output1 = input_dir / 'test_questions_original.txt'

    print("提取原始问题（无坐标）...")
    count1 = extract_to_txt(input1, output1)
    print(f"  ✓ 提取 {count1} 条问题")
    print(f"  ✓ 输出: {output1}")

    # 2. 带坐标的问题
    input2 = input_dir / 'test_questions_with_coords.jsonl'
    output2 = input_dir / 'test_questions_with_coords.txt'

    print("\n提取带坐标问题...")
    count2 = extract_to_txt(input2, output2)
    print(f"  ✓ 提取 {count2} 条问题")
    print(f"  ✓ 输出: {output2}")

    print("\n" + "=" * 50)
    print("提取完成!")
    print(f"原始问题: {output1}")
    print(f"带坐标问题: {output2}")

if __name__ == '__main__':
    main()
