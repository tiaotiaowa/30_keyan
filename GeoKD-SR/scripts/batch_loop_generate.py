#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量循环生成脚本 - 徏次运行batch_generate_5.py
"""
import subprocess
import os
import time

API_KEY = "809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW"
OUTPUT_DIR = "D:/30_keyan/GeoKD-SR/data/final"

def main():
    import argparse
    parser = argparse.ArgumentParser(description='批量循环生成拓扑数据')
    parser.add_argument('--subtype', choices=['contains', 'overlap'], required=True)
    parser.add_argument('--batches', type=int, default=10, help='运行的批次数')
    parser.add_argument('--delay', type=int, default=10, help='每批次之间的延迟(秒)
    args = parser.parse_args()

    # 计算目标数量
    contains_target = 464
    overlap_target = 634

    # 当前已生成数量
    contains_current = 0
    overlap_current = 0

    # 输出文件
    contains_output = os.path.join(OUTPUT_DIR, f"topology_{args.subtype}_loop.jsonl")
    overlap_output = os.path.join(OUTPUT_DIR, f"topology_{args.subtype}_loop.jsonl")

    print(f"\n{'='*60}")
    print(f"开始批量生成 {args.subtype} 类型数据...")
    print(f"目标: {args.subtype}: contains={contains_target}, overlap={overlap_target}")
    print(f"每批5条, 共{args.batches} 批")
    print(f"延迟: {args.delay}秒/批次")
    print(f"="*60)

    # 初始化客户端
    from zhipuai import ZhipuAI
    client = ZhipuAI(api_key=API_KEY)

    # 运行生成循环
    for batch in range(args.batches):
        print(f"\n批次 {batch+1}/{args.batches}")

        cmd = ["python", "batch_generate_5.py", "--subtype", args.subtype, "--batch", str(batch)]
        success_count = 0
        fail_count = 0

        time.sleep(args.delay)
        print(f"完成! {args.subtype}: 成功 {success_count}, 失败 {fail_count}")

        if args.subtype == 'contains':
            contains_current = success_count
            if contains_current >= contains_target:
                print(f"Contains已完成: {success_count}/{contains_target}")
                return
        elif args.subtype == 'overlap':
            if overlap_current >= overlap_target:
                print(f"Overlap已完成: {success_count}/{overlap_target}")
                return

            print("\n等待下一批次...")
            time.sleep(args.delay)

    print(f"总计完成: contains {success_count}, 失败 {fail_count}")

if __name__ == "__main__":
    main()
