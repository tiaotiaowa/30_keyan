# -*- coding: utf-8 -*-
"""
Qwen2.5-1.5B LoRA微调模型评测脚本

功能：
1. 加载LoRA微调后的模型
2. 生成预测结果
3. 计算评测指标（复用 exp0/metrics/deterministic.py）
4. 按空间类型分层统计
5. 输出 predictions.jsonl 和 metrics.json

使用方法：
    python evaluate.py --checkpoint ./checkpoints/checkpoint-xxx --test-file ../../data/splits/test.jsonl --output ./results

作者：GeoKD-SR项目组
日期：2026-03-21
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict

import torch
from tqdm import tqdm

# 添加项目路径以导入评测模块
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # 回到 GeoKD-SR 目录
sys.path.insert(0, str(PROJECT_ROOT))

# 导入评测指标模块
from exp.exp0.metrics.deterministic import (
    calculate_overall_accuracy,
    calculate_format_valid_rate,
    calculate_corpus_bleu_4,
    calculate_corpus_rouge_l,
    calculate_corpus_spatial_f1,
    match_direction,
    match_topology,
    match_distance,
    match_composite,
    calculate_bleu_4,
    calculate_rouge_l,
    calculate_spatial_f1,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_test_data(test_file: str) -> List[Dict[str, Any]]:
    """
    加载测试数据

    Args:
        test_file: 测试数据文件路径

    Returns:
        测试数据列表
    """
    data = []
    with open(test_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    logger.info(f"加载测试数据: {len(data)} 条")
    return data


def load_model_and_tokenizer(
    base_model_path: str,
    checkpoint_path: str,
    device: str = "cuda"
):
    """
    加载LoRA微调后的模型和分词器

    Args:
        base_model_path: 基础模型路径
        checkpoint_path: LoRA checkpoint路径
        device: 计算设备

    Returns:
        model, tokenizer
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    logger.info(f"加载基础模型: {base_model_path}")
    logger.info(f"加载LoRA权重: {checkpoint_path}")

    # 加载分词器
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_path,
        trust_remote_code=True,
        use_fast=False
    )

    # 确保有pad_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

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
        checkpoint_path,
        torch_dtype=torch.float16
    )

    # 合并LoRA权重到基础模型（可选，提高推理速度）
    try:
        model = model.merge_and_unload()
        logger.info("LoRA权重已合并到基础模型")
    except Exception as e:
        logger.warning(f"无法合并LoRA权重: {e}，将使用原始方式")

    model.eval()

    return model, tokenizer


def generate_predictions(
    model,
    tokenizer,
    test_data: List[Dict[str, Any]],
    batch_size: int = 8,
    max_new_tokens: int = 256,
    temperature: float = 0.1,
    top_p: float = 0.9,
    do_sample: bool = False,
    system_prompt: str = "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。请简洁准确地回答问题。"
) -> List[Dict[str, Any]]:
    """
    批量生成预测结果

    Args:
        model: 模型
        tokenizer: 分词器
        test_data: 测试数据
        batch_size: 批次大小
        max_new_tokens: 最大生成token数
        temperature: 温度参数
        top_p: nucleus采样参数
        do_sample: 是否采样
        system_prompt: 系统提示词

    Returns:
        预测结果列表
    """
    predictions = []

    # 准备所有输入
    all_inputs = []
    for item in test_data:
        question = item.get("question", "")
        # 构建对话格式
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        all_inputs.append({
            "id": item.get("id", ""),
            "question": question,
            "text": text,
            "reference": item.get("answer", ""),
            "spatial_type": item.get("spatial_relation_type", ""),
            "original_item": item
        })

    # 批量推理
    logger.info(f"开始生成预测，共 {len(all_inputs)} 条，批次大小 {batch_size}")

    with torch.no_grad():
        for i in tqdm(range(0, len(all_inputs), batch_size), desc="生成预测"):
            batch_items = all_inputs[i:i+batch_size]

            # 编码
            inputs = tokenizer(
                [item["text"] for item in batch_items],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=1024
            ).to(model.device)

            # 生成
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature if do_sample else 1.0,
                top_p=top_p if do_sample else 1.0,
                do_sample=do_sample,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

            # 解码
            for j, output in enumerate(outputs):
                input_len = inputs["input_ids"][j].shape[0]
                generated = output[input_len:]
                prediction_text = tokenizer.decode(
                    generated,
                    skip_special_tokens=True
                ).strip()

                item = batch_items[j]
                predictions.append({
                    "id": item["id"],
                    "question": item["question"],
                    "prediction": prediction_text,
                    "reference": item["reference"],
                    "spatial_type": item["spatial_type"],
                    "original_item": item["original_item"]
                })

    logger.info(f"预测完成，共 {len(predictions)} 条")
    return predictions


def calculate_metrics(
    predictions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    计算评测指标

    Args:
        predictions: 预测结果列表

    Returns:
        指标字典
    """
    logger.info("开始计算评测指标...")

    # 提取预测和参考
    pred_texts = [p["prediction"] for p in predictions]
    ref_texts = [p["reference"] for p in predictions]
    spatial_types = [p["spatial_type"] for p in predictions]

    # 整体指标
    metrics = {
        "overall": {
            "total_samples": len(predictions),
            "overall_accuracy": calculate_overall_accuracy(pred_texts, ref_texts, spatial_types),
            "format_valid_rate": calculate_format_valid_rate(pred_texts),
            "bleu_4": calculate_corpus_bleu_4(pred_texts, ref_texts),
            "rouge_l": calculate_corpus_rouge_l(pred_texts, ref_texts),
            "spatial_f1": calculate_corpus_spatial_f1(pred_texts, ref_texts, spatial_types),
        }
    }

    # 按空间类型分层统计
    spatial_type_metrics = defaultdict(lambda: {
        "predictions": [],
        "references": [],
        "spatial_types": []
    })

    for p in predictions:
        stype = p["spatial_type"]
        spatial_type_metrics[stype]["predictions"].append(p["prediction"])
        spatial_type_metrics[stype]["references"].append(p["reference"])
        spatial_type_metrics[stype]["spatial_types"].append(stype)

    metrics["by_spatial_type"] = {}

    for stype, data in spatial_type_metrics.items():
        if not data["predictions"]:
            continue

        preds = data["predictions"]
        refs = data["references"]
        types = data["spatial_types"]

        # 计算该类型的准确率
        correct = 0
        for pred, ref in zip(preds, refs):
            if stype == "directional":
                correct += match_direction(pred, ref)
            elif stype == "topological":
                correct += match_topology(pred, ref)
            elif stype == "metric":
                correct += match_distance(pred, ref)
            elif stype == "composite":
                correct += match_composite(pred, ref)

        accuracy = correct / len(preds) if preds else 0.0

        metrics["by_spatial_type"][stype] = {
            "count": len(preds),
            "accuracy": accuracy,
            "bleu_4": calculate_corpus_bleu_4(preds, refs),
            "rouge_l": calculate_corpus_rouge_l(preds, refs),
            "spatial_f1": calculate_corpus_spatial_f1(preds, refs, types),
        }

    # 添加难度分层统计（如果数据包含difficulty字段）
    difficulty_metrics = defaultdict(lambda: {
        "predictions": [],
        "references": [],
        "spatial_types": [],
        "count": 0
    })

    for p in predictions:
        difficulty = p.get("original_item", {}).get("difficulty", "unknown")
        difficulty_metrics[difficulty]["predictions"].append(p["prediction"])
        difficulty_metrics[difficulty]["references"].append(p["reference"])
        difficulty_metrics[difficulty]["spatial_types"].append(p["spatial_type"])
        difficulty_metrics[difficulty]["count"] += 1

    metrics["by_difficulty"] = {}
    for diff, data in difficulty_metrics.items():
        if data["count"] > 0:
            metrics["by_difficulty"][diff] = {
                "count": data["count"],
                "accuracy": calculate_overall_accuracy(
                    data["predictions"],
                    data["references"],
                    data["spatial_types"]
                )
            }

    logger.info("指标计算完成")
    return metrics


def save_predictions(
    predictions: List[Dict[str, Any]],
    output_file: str
):
    """
    保存预测结果

    Args:
        predictions: 预测结果列表
        output_file: 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for pred in predictions:
            output_item = {
                "id": pred["id"],
                "question": pred["question"],
                "prediction": pred["prediction"],
                "reference": pred["reference"],
                "spatial_type": pred["spatial_type"],
            }
            f.write(json.dumps(output_item, ensure_ascii=False) + '\n')

    logger.info(f"预测结果已保存: {output_file}")


def save_metrics(
    metrics: Dict[str, Any],
    output_file: str
):
    """
    保存指标结果

    Args:
        metrics: 指标字典
        output_file: 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    logger.info(f"指标结果已保存: {output_file}")


def print_metrics_summary(metrics: Dict[str, Any]):
    """
    打印指标摘要

    Args:
        metrics: 指标字典
    """
    print("\n" + "="*60)
    print("评测结果摘要")
    print("="*60)

    overall = metrics.get("overall", {})
    print(f"\n【整体指标】")
    print(f"  样本数量: {overall.get('total_samples', 0)}")
    print(f"  Overall Accuracy: {overall.get('overall_accuracy', 0):.4f}")
    print(f"  Format Valid Rate: {overall.get('format_valid_rate', 0):.4f}")
    print(f"  BLEU-4: {overall.get('bleu_4', 0):.4f}")
    print(f"  ROUGE-L: {overall.get('rouge_l', 0):.4f}")
    print(f"  Spatial F1: {overall.get('spatial_f1', 0):.4f}")

    by_type = metrics.get("by_spatial_type", {})
    if by_type:
        print(f"\n【按空间类型分层】")
        print(f"  {'类型':<12} {'数量':>6} {'准确率':>10} {'BLEU-4':>10} {'ROUGE-L':>10} {'Spatial F1':>12}")
        print(f"  {'-'*60}")
        for stype, data in sorted(by_type.items()):
            print(f"  {stype:<12} {data.get('count', 0):>6} {data.get('accuracy', 0):>10.4f} "
                  f"{data.get('bleu_4', 0):>10.4f} {data.get('rouge_l', 0):>10.4f} "
                  f"{data.get('spatial_f1', 0):>12.4f}")

    by_diff = metrics.get("by_difficulty", {})
    if by_diff:
        print(f"\n【按难度分层】")
        print(f"  {'难度':<10} {'数量':>6} {'准确率':>10}")
        print(f"  {'-'*30}")
        for diff, data in sorted(by_diff.items()):
            print(f"  {diff:<10} {data.get('count', 0):>6} {data.get('accuracy', 0):>10.4f}")

    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description="Qwen2.5-1.5B LoRA微调模型评测脚本")

    # 必需参数
    parser.add_argument(
        "--checkpoint",
        type=str,
        required=True,
        help="LoRA checkpoint路径"
    )
    parser.add_argument(
        "--test-file",
        type=str,
        required=True,
        help="测试数据文件路径"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="输出目录"
    )

    # 可选参数
    parser.add_argument(
        "--base-model",
        type=str,
        default=None,
        help="基础模型路径（如不指定，将使用默认路径）"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="批次大小（默认: 8）"
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=256,
        help="最大生成token数（默认: 256）"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="温度参数（默认: 0.1）"
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=0.9,
        help="Nucleus采样参数（默认: 0.9）"
    )
    parser.add_argument(
        "--do-sample",
        action="store_true",
        help="是否使用采样（默认关闭，使用贪婪解码）"
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        default="你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。请简洁准确地回答问题。",
        help="系统提示词"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="计算设备（默认: cuda）"
    )

    args = parser.parse_args()

    # 设置基础模型路径
    if args.base_model is None:
        args.base_model = str(PROJECT_ROOT / "models" / "Qwen2.5-1.5B-Instruct")

    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 记录配置
    logger.info(f"评测配置:")
    logger.info(f"  Checkpoint: {args.checkpoint}")
    logger.info(f"  测试文件: {args.test_file}")
    logger.info(f"  输出目录: {args.output}")
    logger.info(f"  基础模型: {args.base_model}")
    logger.info(f"  批次大小: {args.batch_size}")
    logger.info(f"  最大生成token数: {args.max_new_tokens}")

    # 检查设备
    if args.device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA不可用，切换到CPU")
        args.device = "cpu"

    # 加载测试数据
    test_data = load_test_data(args.test_file)

    # 加载模型
    model, tokenizer = load_model_and_tokenizer(
        args.base_model,
        args.checkpoint,
        args.device
    )

    # 生成预测
    predictions = generate_predictions(
        model,
        tokenizer,
        test_data,
        batch_size=args.batch_size,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        do_sample=args.do_sample,
        system_prompt=args.system_prompt
    )

    # 计算指标
    metrics = calculate_metrics(predictions)

    # 添加评测元信息
    metrics["metadata"] = {
        "checkpoint": args.checkpoint,
        "test_file": args.test_file,
        "base_model": args.base_model,
        "batch_size": args.batch_size,
        "max_new_tokens": args.max_new_tokens,
        "temperature": args.temperature,
        "do_sample": args.do_sample,
        "timestamp": datetime.now().isoformat(),
    }

    # 保存结果
    predictions_file = output_dir / "predictions.jsonl"
    metrics_file = output_dir / "metrics.json"

    save_predictions(predictions, str(predictions_file))
    save_metrics(metrics, str(metrics_file))

    # 打印摘要
    print_metrics_summary(metrics)

    logger.info("评测完成！")

    return metrics


if __name__ == "__main__":
    main()
