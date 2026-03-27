#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp6: B2+C4（自蒸馏）评估脚本
"""

import os
import sys
import json
import yaml
import argparse
import torch
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import numpy as np


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_model(checkpoint_path: str, base_model_name: str):
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, checkpoint_path)
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
    return model, tokenizer


def load_benchmark(benchmark_path: str):
    data = []
    with open(benchmark_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line.strip()) if line.strip().startswith("{") else eval(line.strip())
                data.append(item)
    return data


def calculate_bleu(prediction: str, reference: str) -> float:
    from collections import Counter
    pred_tokens, ref_tokens = prediction.split(), reference.split()
    if not pred_tokens or not ref_tokens:
        return 0.0
    scores = []
    for n in range(1, 5):
        pred_ngrams = Counter(tuple(pred_tokens[i:i+n]) for i in range(len(pred_tokens)-n+1))
        ref_ngrams = Counter(tuple(ref_tokens[i:i+n]) for i in range(len(ref_tokens)-n+1))
        matches = sum((pred_ngrams & ref_ngrams).values())
        total = sum(pred_ngrams.values())
        scores.append(matches / total if total > 0 else 0)
    return np.mean(scores) if scores else 0.0


def calculate_rouge_l(prediction: str, reference: str) -> float:
    pred_tokens, ref_tokens = prediction.split(), reference.split()
    if not pred_tokens or not ref_tokens:
        return 0.0
    m, n = len(pred_tokens), len(ref_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pred_tokens[i-1] == ref_tokens[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    lcs = dp[m][n]
    precision = lcs / m if m > 0 else 0
    recall = lcs / n if n > 0 else 0
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def extract_spatial_relations(text: str) -> list:
    spatial_keywords = [
        "东", "西", "南", "北", "东北", "西北", "东南", "西南",
        "左侧", "右侧", "上方", "下方", "左边", "右边",
        "相邻", "包含", "相交", "相离", "重叠", "邻接", "内部", "外部", "边界",
        "距离", "米", "公里", "千米", "远", "近",
    ]
    return [kw for kw in spatial_keywords if kw in text]


def calculate_spatial_f1(prediction: str, reference: str) -> float:
    pred_relations = set(extract_spatial_relations(prediction))
    ref_relations = set(extract_spatial_relations(reference))
    if not pred_relations and not ref_relations:
        return 1.0
    if not pred_relations or not ref_relations:
        return 0.0
    common = pred_relations & ref_relations
    precision = len(common) / len(pred_relations)
    recall = len(common) / len(ref_relations)
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def evaluate_reasoning_accuracy(prediction: str, reference: str) -> bool:
    pred_lower, ref_lower = prediction.lower().strip(), reference.lower().strip()
    if pred_lower == ref_lower or ref_lower in pred_lower:
        return True
    import re
    pred_numbers = re.findall(r'-?\d+\.?\d*', prediction)
    ref_numbers = re.findall(r'-?\d+\.?\d*', reference)
    return bool(pred_numbers and ref_numbers and set(pred_numbers) == set(ref_numbers))


def generate_response(model, tokenizer, question: str, max_length: int = 512) -> str:
    prompt = f"问题：{question}\n答案："
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=max_length, do_sample=False,
            pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id,
        )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response.split("答案：")[-1].strip() if "答案：" in response else response


def main():
    parser = argparse.ArgumentParser(description="Exp6: B2+C4（自蒸馏）评估")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--benchmark", type=str, default="data/geosr_bench/benchmark.json")
    parser.add_argument("--output", type=str, default="results/evaluation_results.json")
    args = parser.parse_args()

    work_dir = Path(__file__).parent
    os.chdir(work_dir)
    config = load_config(args.config)

    print("=" * 60)
    print("Exp6: B2+C4（自蒸馏） - 评估")
    print("=" * 60)

    model, tokenizer = load_model(args.checkpoint, config['model']['student']['name'])
    benchmark = load_benchmark(args.benchmark)
    print(f"共 {len(benchmark)} 条测试数据")

    results = {"reasoning_accuracy": [], "spatial_f1": [], "bleu": [], "rouge_l": [], "details": []}

    for item in tqdm(benchmark, desc="评估中"):
        question = item.get("question", "")
        reference = item.get("answer", "")
        prediction = generate_response(model, tokenizer, question)

        ra = evaluate_reasoning_accuracy(prediction, reference)
        sf1 = calculate_spatial_f1(prediction, reference)
        bleu = calculate_bleu(prediction, reference)
        rouge = calculate_rouge_l(prediction, reference)

        results["reasoning_accuracy"].append(float(ra))
        results["spatial_f1"].append(sf1)
        results["bleu"].append(bleu)
        results["rouge_l"].append(rouge)
        results["details"].append({
            "question": question, "reference": reference, "prediction": prediction,
            "reasoning_accuracy": ra, "spatial_f1": sf1, "bleu": bleu, "rouge_l": rouge,
        })

    summary = {
        "experiment": "Exp6: B2+C4（自蒸馏）",
        "checkpoint": args.checkpoint,
        "timestamp": datetime.now().isoformat(),
        "num_samples": len(benchmark),
        "metrics": {
            "reasoning_accuracy": np.mean(results["reasoning_accuracy"]),
            "spatial_f1": np.mean(results["spatial_f1"]),
            "bleu": np.mean(results["bleu"]),
            "rouge_l": np.mean(results["rouge_l"]),
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "details": results["details"]}, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("评估结果")
    print("=" * 60)
    print(f"推理准确率 (RA): {summary['metrics']['reasoning_accuracy']:.4f}")
    print(f"空间关系F1 (SR-F1): {summary['metrics']['spatial_f1']:.4f}")
    print(f"BLEU: {summary['metrics']['bleu']:.4f}")
    print(f"ROUGE-L: {summary['metrics']['rouge_l']:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
