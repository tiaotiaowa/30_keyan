#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp05 Stage2: 使用exp0统一评测框架计算指标
确保与基线(23.16%)和SFT(22.06%)及Standard-KD(26.37%)完全可比
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

import yaml

# 添加exp0评测模块路径
EXP0_STAGE2 = Path(__file__).resolve().parent.parent / "exp0" / "exp0" / "stage2_evaluation"
sys.path.insert(0, str(EXP0_STAGE2))

from evaluate import Evaluator


def main():
    parser = argparse.ArgumentParser(description="Exp05 Stage2: 评测")
    parser.add_argument("--predictions", type=str, default="./outputs/predictions.jsonl",
                        help="predictions.jsonl路径")
    parser.add_argument("--eval-config", type=str, default=None,
                        help="评测配置文件（默认使用exp0的eval_config.yaml）")
    parser.add_argument("--output", type=str, default="./results/", help="输出目录")
    args = parser.parse_args()

    # 加载评测配置（使用exp0的统一配置）
    if args.eval_config is None:
        args.eval_config = str(EXP0_STAGE2 / "config" / "eval_config.yaml")

    with open(args.eval_config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 覆盖路径
    config["data"]["predictions_file"] = args.predictions
    config["data"]["output_dir"] = args.output

    print("=" * 60)
    print("Exp05 Stage2: 逆向KL蒸馏评测")
    print("=" * 60)
    print(f"预测文件: {args.predictions}")
    print(f"评测配置: {args.eval_config}")
    print(f"输出目录: {args.output}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 创建评测器并运行
    evaluator = Evaluator(config)
    evaluator.load_predictions(args.predictions)
    results = evaluator.run_evaluation()
    json_path, report_path = evaluator.save_results(results, args.output)

    print(f"\n评测完成！")
    print(f"JSON结果: {json_path}")
    print(f"报告: {report_path}")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 打印关键指标
    det = results.get("deterministic", {})
    acc = det.get("accuracy", {}).get("overall", 0)
    print(f"\nOverall Accuracy: {acc:.4f} ({acc*100:.2f}%)")


if __name__ == "__main__":
    main()
