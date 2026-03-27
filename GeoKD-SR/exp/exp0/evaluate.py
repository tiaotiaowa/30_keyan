#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp0 基线评估脚本
用法: python evaluate.py --config config/config_1.5b.yaml --seed 42
"""

import argparse
import json
import os
import sys
import yaml
from datetime import datetime
from pathlib import Path

import torch
import numpy as np

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from utils.data_loader import load_test_data
from utils.model_loader import load_model
from utils.report import generate_report
from metrics import (
    calculate_overall_accuracy,
    calculate_format_valid_rate,
    calculate_corpus_bleu_4,
    calculate_corpus_rouge_l,
    calculate_perplexity,
    calculate_corpus_spatial_f1,
    BERTScoreCalculator
)


def set_seed(seed: int):
    """设置随机种子"""
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def generate_predictions(model, tokenizer, data, config):
    """生成预测结果"""
    predictions = []
    model.eval()

    for item in data:
        # 构建prompt
        prompt = item['question']

        # 生成
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                temperature=config['generation']['temperature'],
                top_p=config['generation']['top_p'],
                do_sample=config['generation']['do_sample'],
                max_new_tokens=config['generation']['max_new_tokens'],
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id
            )

        prediction = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # 只保留生成的部分
        prediction = prediction[len(prompt):].strip()
        predictions.append(prediction)

    return predictions


def evaluate(config_path: str, seed: int):
    """执行评估"""
    # 加载配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 设置随机种子
    set_seed(seed)

    # 加载模型
    model, tokenizer = load_model(
        config['model']['path'],
        config['model'].get('quantization'),
        config['model']['device']
    )

    # 加载数据
    data = load_test_data(
        config['data']['test_file'],
        config['data'].get('max_samples')
    )

    # 生成预测
    predictions = generate_predictions(model, tokenizer, data, config)
    references = [item['answer'] for item in data]
    spatial_types = [item.get('spatial_relation_type', item.get('relation_type', 'unknown')) for item in data]
    difficulties = [item.get('difficulty', 'unknown') for item in data]

    # 计算确定性指标
    metrics = {
        "meta": {
            "experiment": config['experiment']['name'],
            "model": config['model']['name'],
            "quantization": config['model'].get('quantization'),
            "seed": seed,
            "timestamp": datetime.now().isoformat(),
            "test_samples": len(data)
        },
        "deterministic": {
            "overall_accuracy": calculate_overall_accuracy(predictions, references, spatial_types),
            "format_valid_rate": calculate_format_valid_rate(predictions),
            "bleu_4": calculate_corpus_bleu_4(predictions, references),
            "rouge_l": calculate_corpus_rouge_l(predictions, references),
            "spatial_f1": calculate_corpus_spatial_f1(predictions, references, spatial_types)
        }
    }

    # 计算困惑度
    try:
        metrics["deterministic"]["perplexity"] = calculate_perplexity(
            model, tokenizer, references, config['model']['device']
        )
    except Exception as e:
        metrics["deterministic"]["perplexity"] = None
        print(f"Warning: Failed to calculate perplexity: {e}")

    # 计算语义指标 (BERTScore)
    if config['evaluation']['metrics'].get('semantic', False):
        try:
            bertscore_calc = BERTScoreCalculator(device=config['model']['device'])
            bertscore = bertscore_calc.calculate_corpus_bertscore(predictions, references)
            metrics["semantic"] = {
                "bertscore_precision": bertscore["precision"],
                "bertscore_recall": bertscore["recall"],
                "bertscore_f1": bertscore["f1"]
            }
        except Exception as e:
            metrics["semantic"] = {}
            print(f"Warning: Failed to calculate BERTScore: {e}")

    # 分层分析
    metrics["stratified"] = calculate_stratified_metrics(
        predictions, references, spatial_types, difficulties
    )

    # 保存结果
    output_dir = Path(config['output']['results_dir']) / f"seed_{seed}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存metrics.json
    with open(output_dir / "metrics.json", 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    # 保存predictions.jsonl
    if config['output'].get('save_predictions', False):
        with open(output_dir / "predictions.jsonl", 'w', encoding='utf-8') as f:
            for item, pred in zip(data, predictions):
                f.write(json.dumps({
                    'id': item.get('id', ''),
                    'question': item['question'],
                    'reference': item['answer'],
                    'prediction': pred,
                    'spatial_type': item.get('spatial_relation_type', item.get('relation_type', 'unknown')),
                    'difficulty': item.get('difficulty', 'unknown')
                }, ensure_ascii=False) + '\n')

    # 生成报告
    generate_report(metrics, str(output_dir / "report.md"))

    print(f"Results saved to {output_dir}")
    return metrics


def calculate_stratified_metrics(predictions, references, spatial_types, difficulties):
    """计算分层指标"""
    stratified = {"by_spatial_type": {}, "by_difficulty": {}}

    # 按空间类型分组
    type_groups = {}
    for i, st in enumerate(spatial_types):
        if st not in type_groups:
            type_groups[st] = {"preds": [], "refs": [], "types": []}
        type_groups[st]["preds"].append(predictions[i])
        type_groups[st]["refs"].append(references[i])
        type_groups[st]["types"].append(st)

    for st, group in type_groups.items():
        acc = calculate_overall_accuracy(group["preds"], group["refs"], group["types"])
        stratified["by_spatial_type"][st] = {"accuracy": acc, "count": len(group["preds"])}

    # 按难度分组
    diff_groups = {}
    for i, diff in enumerate(difficulties):
        if diff not in diff_groups:
            diff_groups[diff] = {"preds": [], "refs": [], "types": []}
        diff_groups[diff]["preds"].append(predictions[i])
        diff_groups[diff]["refs"].append(references[i])
        diff_groups[diff]["types"].append(spatial_types[i])

    for diff, group in diff_groups.items():
        acc = calculate_overall_accuracy(group["preds"], group["refs"], group["types"])
        stratified["by_difficulty"][diff] = {"accuracy": acc, "count": len(group["preds"])}

    return stratified


def main():
    parser = argparse.ArgumentParser(description="exp0 基线评估")
    parser.add_argument("--config", type=str, required=True, help="配置文件路径")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    # 切换到脚本所在目录
    os.chdir(Path(__file__).parent)

    evaluate(args.config, args.seed)


if __name__ == "__main__":
    main()
