# -*- coding: utf-8 -*-
"""
LoRA微调模型评测脚本 - 原始问题格式
=====================================

使用与训练一致的格式：直接使用原始问题，不添加prompt_template

使用方法:
    python evaluate_raw.py \
        --base-model /path/to/base/model \
        --lora-path /path/to/lora/weights \
        --test-file /path/to/test.jsonl \
        --output-dir ./results/raw_format

作者: GeoKD-SR Project
日期: 2026-03-27
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

import torch
from tqdm import tqdm

# 添加项目路径
# eval_comparison -> qwen-1.5B-sft -> exp0 -> exp -> GeoKD-SR (4级)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

# 导入评测指标模块
from exp.exp0.metrics.deterministic import (
    calculate_overall_accuracy,
    calculate_format_valid_rate,
    match_direction,
    match_topology,
    match_distance,
    match_composite,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_test_data(test_file: str) -> List[Dict[str, Any]]:
    """加载测试数据"""
    data = []
    with open(test_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    logger.info(f"加载测试数据: {len(data)} 条")
    return data


def load_lora_model(base_model_path: str, lora_path: str):
    """加载LoRA微调后的模型"""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    logger.info(f"加载基础模型: {base_model_path}")
    logger.info(f"加载LoRA权重: {lora_path}")

    # 加载分词器
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_path,
        trust_remote_code=True,
        use_fast=False
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    # 加载基础模型
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )

    # 加载LoRA权重
    model = PeftModel.from_pretrained(
        model,
        lora_path,
        torch_dtype=torch.float16
    )

    # 合并LoRA权重
    try:
        model = model.merge_and_unload()
        logger.info("LoRA权重已合并到基础模型")
    except Exception as e:
        logger.warning(f"无法合并LoRA权重: {e}")

    model.eval()
    return model, tokenizer


def generate_single(model, tokenizer, question: str) -> str:
    """
    单条推理 - 使用原始问题格式（与训练一致）

    Args:
        model: 模型
        tokenizer: 分词器
        question: 原始问题

    Returns:
        生成的答案
    """
    # 直接使用原始问题，不添加prompt_template（与训练一致）
    messages = [{"role": "user", "content": question}]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.1,
            top_p=0.9,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id
        )

    # 只保留生成部分
    input_len = inputs["input_ids"].shape[1]
    generated = outputs[0][input_len:]
    response = tokenizer.decode(generated, skip_special_tokens=True).strip()

    return response


def calculate_metrics(predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算评测指标"""
    logger.info("计算评测指标...")

    # 按空间类型分组
    by_type = defaultdict(list)
    for pred in predictions:
        spatial_type = pred.get("spatial_type", "unknown")
        by_type[spatial_type].append(pred)

    results = {
        "total_samples": len(predictions),
        "by_type": {},
        "overall": {}
    }

    # 计算各类型的指标
    for spatial_type, preds in by_type.items():
        type_results = {}

        # 准确率计算
        if spatial_type == "directional":
            correct = sum(1 for p in preds if match_direction(p.get("prediction", ""), p.get("reference", "")))
            type_results["accuracy"] = correct / len(preds) if preds else 0
        elif spatial_type == "topological":
            correct = sum(1 for p in preds if match_topology(p.get("prediction", ""), p.get("reference", "")))
            type_results["accuracy"] = correct / len(preds) if preds else 0
        elif spatial_type == "metric":
            correct = sum(1 for p in preds if match_distance(p.get("prediction", ""), p.get("reference", "")))
            type_results["accuracy"] = correct / len(preds) if preds else 0
        elif spatial_type == "composite":
            correct = sum(1 for p in preds if match_composite(p.get("prediction", ""), p.get("reference", "")))
            type_results["accuracy"] = correct / len(preds) if preds else 0

        type_results["count"] = len(preds)
        results["by_type"][spatial_type] = type_results

    # 计算总体指标
    total_correct = 0
    for pred in predictions:
        spatial_type = pred.get("spatial_type", "")
        if spatial_type == "directional" and match_direction(pred.get("prediction", ""), pred.get("reference", "")):
            total_correct += 1
        elif spatial_type == "topological" and match_topology(pred.get("prediction", ""), pred.get("reference", "")):
            total_correct += 1
        elif spatial_type == "metric" and match_distance(pred.get("prediction", ""), pred.get("reference", "")):
            total_correct += 1
        elif spatial_type == "composite" and match_composite(pred.get("prediction", ""), pred.get("reference", "")):
            total_correct += 1

    results["overall"]["accuracy"] = total_correct / len(predictions) if predictions else 0

    # 格式有效率
    valid_count = sum(1 for p in predictions if p.get("prediction", "").strip())
    results["overall"]["format_valid_rate"] = valid_count / len(predictions) if predictions else 0

    return results


def main():
    parser = argparse.ArgumentParser(description="LoRA模型评测 - 原始问题格式")
    parser.add_argument("--base-model", type=str, required=True, help="基础模型路径")
    parser.add_argument("--lora-path", type=str, required=True, help="LoRA权重路径")
    parser.add_argument("--test-file", type=str, required=True, help="测试数据文件")
    parser.add_argument("--output-dir", type=str, default="./results/raw_format", help="输出目录")

    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载模型
    model, tokenizer = load_lora_model(args.base_model, args.lora_path)

    # 加载测试数据
    test_data = load_test_data(args.test_file)

    # 生成预测
    predictions = []
    logger.info(f"开始生成预测，共 {len(test_data)} 条")

    for item in tqdm(test_data, desc="生成预测"):
        question = item.get("question", "")
        reference = item.get("answer", "")
        spatial_type = item.get("spatial_relation_type", "unknown")

        prediction = generate_single(model, tokenizer, question)

        predictions.append({
            "id": item.get("id", ""),
            "question": question,
            "reference": reference,
            "prediction": prediction,
            "spatial_type": spatial_type,
            "difficulty": item.get("difficulty", "")
        })

    # 保存预测结果
    predictions_file = output_dir / "predictions.jsonl"
    with open(predictions_file, 'w', encoding='utf-8') as f:
        for pred in predictions:
            f.write(json.dumps(pred, ensure_ascii=False) + '\n')
    logger.info(f"预测结果已保存到: {predictions_file}")

    # 计算指标
    metrics = calculate_metrics(predictions)
    metrics["metadata"] = {
        "base_model": args.base_model,
        "lora_path": args.lora_path,
        "test_file": args.test_file,
        "format": "raw_question",
        "timestamp": datetime.now().isoformat()
    }

    # 保存指标
    metrics_file = output_dir / "metrics.json"
    with open(metrics_file, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    logger.info(f"评测指标已保存到: {metrics_file}")

    # 打印摘要
    print("\n" + "="*50)
    print("评测结果摘要 (原始问题格式)")
    print("="*50)
    print(f"总样本数: {metrics['total_samples']}")
    print(f"总体准确率: {metrics['overall']['accuracy']:.4f}")
    print(f"格式有效率: {metrics['overall']['format_valid_rate']:.4f}")
    print("\n按空间类型:")
    for stype, sdata in metrics['by_type'].items():
        print(f"  {stype}: {sdata['count']}条, 准确率: {sdata['accuracy']:.4f}")


if __name__ == "__main__":
    main()
