#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量评估脚本（三模型×5seeds）
用法: python batch_evaluate.py --all
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

CONFIGS = {
    "1.5b": "config/config_1.5b.yaml",
    "7b": "config/config_7b.yaml",
    "7b_4bit": "config/config_7b_4bit.yaml"
}

SEEDS = [42, 123, 456, 789, 1024]


def run_evaluation(config_name: str, seed: int):
    """运行单个评估"""
    config_path = CONFIGS[config_name]
    cmd = [sys.executable, "evaluate.py", "--config", config_path, "--seed", str(seed)]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="批量评估")
    parser.add_argument("--all", action="store_true", help="运行全部评估")
    parser.add_argument("--model", type=str, choices=list(CONFIGS.keys()), help="指定模型")
    parser.add_argument("--seed", type=int, help="指定种子")
    args = parser.parse_args()

    # 切换到脚本所在目录
    os.chdir(Path(__file__).parent)

    if args.all:
        # 运行全部
        for config_name in CONFIGS:
            for seed in SEEDS:
                run_evaluation(config_name, seed)
    elif args.model:
        if args.seed:
            run_evaluation(args.model, args.seed)
        else:
            for seed in SEEDS:
                run_evaluation(args.model, seed)
    else:
        print("请指定 --all 或 --model")


if __name__ == "__main__":
    main()
