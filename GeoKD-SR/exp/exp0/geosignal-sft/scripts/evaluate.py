#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoSignal模型评估脚本

在GeoBench上评估训练好的模型

使用方法:
    python evaluate.py --config configs/eval.yaml --checkpoint outputs/final_model
"""

import os
import sys
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="GeoSignal模型评估")
    parser.add_argument("--config", type=str, required=True, help="评估配置文件")
    parser.add_argument("--checkpoint", type=str, required=True, help="模型检查点路径")
    parser.add_argument("--output", type=str, default=None, help="结果输出路径")
    parser.add_argument("--batch-size", type=int, default=8, help="评估批次大小")
    parser.add_argument("--max-samples", type=int, default=None, help="最大评估样本数")
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def evaluate_objective_tasks(model, tokenizer, data_path: str, args):
    """
    评估客观任务（选择题）

    使用类似于K2论文的方法：
    - 提示以"答案是"结尾
    - 计算选项标签的Softmax概率
    - 计算准确率
    """
    logger.info(f"评估客观任务: {data_path}")

    # TODO: 实现客观任务评估
    results = {
        "accuracy": 0.0,
        "total": 0,
        "correct": 0,
    }

    return results


def evaluate_subjective_tasks(model, tokenizer, data_path: str, args):
    """
    评估主观任务（开放问答）

    评估指标：
    - 困惑度 (Perplexity)
    - GPTScore
    - 人工评估（可选）
    """
    logger.info(f"评估主观任务: {data_path}")

    results = {
        "perplexity": 0.0,
        "gpt_score": 0.0,
        "samples": [],
    }

    # TODO: 实现主观任务评估

    return results


def run_evaluation(config: dict, args):
    """执行评估"""
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
    except ImportError as e:
        logger.error(f"缺少依赖: {e}")
        return

    logger.info("=" * 60)
    logger.info("GeoBench评估")
    logger.info("=" * 60)

    # 加载模型
    logger.info(f"\n加载模型: {args.checkpoint}")
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.checkpoint,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    eval_cfg = config.get("evaluation", {})
    results = {}

    # 评估客观任务
    if eval_cfg.get("geobench", {}).get("enabled", True):
        objective_tasks = eval_cfg.get("geobench", {}).get("objective_tasks", [])

        for task in objective_tasks:
            logger.info(f"\n评估任务: {task}")
            data_path = f"data/geobench/{task.lower()}.jsonl"

            if os.path.exists(os.path.join(PROJECT_ROOT, data_path)):
                task_results = evaluate_objective_tasks(model, tokenizer, data_path, args)
                results[task] = task_results
            else:
                logger.warning(f"数据文件不存在: {data_path}")

    # 评估主观任务
    subjective_tasks = eval_cfg.get("geobench", {}).get("subjective_tasks", [])
    for task in subjective_tasks:
        logger.info(f"\n评估任务: {task}")
        data_path = f"data/geobench/{task.lower()}.jsonl"

        if os.path.exists(os.path.join(PROJECT_ROOT, data_path)):
            task_results = evaluate_subjective_tasks(model, tokenizer, data_path, args)
            results[task] = task_results

    # 保存结果
    output_path = args.output or os.path.join(
        PROJECT_ROOT,
        config.get("output", {}).get("results_dir", "results"),
        f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"\n评估结果保存到: {output_path}")
    logger.info("=" * 60)
    logger.info("评估完成!")
    logger.info("=" * 60)

    return results


def main():
    args = parse_args()

    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.getcwd(), config_path)

    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)

    if not os.path.exists(args.checkpoint):
        logger.error(f"检查点不存在: {args.checkpoint}")
        sys.exit(1)

    config = load_config(config_path)
    run_evaluation(config, args)


if __name__ == "__main__":
    main()
