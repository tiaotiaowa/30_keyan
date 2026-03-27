#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp2: B2-Standard-KD 评估脚本

评估指标: 推理准确率(RA)、空间关系F1、BLEU、ROUGE-L

改进:
1. 使用 json.loads() 替代 eval() 安全加载数据
2. 使用 ChatML 模板格式生成
"""

import os
import sys
import json
import yaml
import argparse
import torch
import re
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import numpy as np
from collections import Counter


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_model(checkpoint_path: str, base_model_name: str):
    """加载训练好的模型"""
    # 加载基础模型
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    # 加载LoRA权重
    model = PeftModel.from_pretrained(base_model, checkpoint_path)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(
        base_model_name,
        trust_remote_code=True,
    )

    # 确保有 pad_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    return model, tokenizer


def load_benchmark(benchmark_path: str):
    """加载基准测试数据 - 使用 json.loads() 安全加载"""
    data = []
    with open(benchmark_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    item = json.loads(line)
                    data.append(item)
                except json.JSONDecodeError as e:
                    print(f"警告: 跳过无效JSON行: {e}")
                    continue
    return data


def calculate_bleu(prediction: str, reference: str) -> float:
    """计算BLEU-4分数"""
    pred_tokens = list(prediction)  # 中文按字符分词
    ref_tokens = list(reference)

    if not pred_tokens or not ref_tokens:
        return 0.0

    # 计算n-gram匹配 (n=1,2,3,4)
    scores = []
    for n in range(1, 5):
        pred_ngrams = Counter(tuple(pred_tokens[i:i+n]) for i in range(len(pred_tokens)-n+1))
        ref_ngrams = Counter(tuple(ref_tokens[i:i+n]) for i in range(len(ref_tokens)-n+1))

        matches = sum((pred_ngrams & ref_ngrams).values())
        total = sum(pred_ngrams.values())

        if total == 0:
            scores.append(0)
        else:
            scores.append(matches / total)

    # 简化的BLEU计算 (几何平均)
    if all(s > 0 for s in scores):
        return np.exp(np.mean(np.log(scores)))
    return np.mean(scores) if scores else 0.0


def calculate_rouge_l(prediction: str, reference: str) -> float:
    """计算ROUGE-L分数"""
    pred_tokens = list(prediction)
    ref_tokens = list(reference)

    if not pred_tokens or not ref_tokens:
        return 0.0

    # LCS计算
    m, n = len(pred_tokens), len(ref_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pred_tokens[i-1] == ref_tokens[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    lcs = dp[m][n]

    # F1分数
    precision = lcs / m if m > 0 else 0
    recall = lcs / n if n > 0 else 0

    if precision + recall == 0:
        return 0.0

    f1 = 2 * precision * recall / (precision + recall)
    return f1


def extract_spatial_relations(text: str) -> list:
    """提取空间关系关键词"""
    spatial_keywords = [
        # 方向关系
        "东", "西", "南", "北", "东北", "西北", "东南", "西南",
        "左侧", "右侧", "上方", "下方", "左边", "右边", "上", "下",
        # 拓扑关系
        "相邻", "包含", "相交", "相离", "重叠", "邻接",
        "内部", "外部", "边界", "包围", "被包含",
        # 度量关系
        "距离", "米", "公里", "千米", "远", "近", "中间", "之间",
        # 相对位置
        "前面", "后面", "前面", "后面", "中央", "中心",
    ]
    found = []
    for kw in spatial_keywords:
        if kw in text:
            found.append(kw)
    return found


def calculate_spatial_f1(prediction: str, reference: str) -> float:
    """计算空间关系F1分数"""
    pred_relations = set(extract_spatial_relations(prediction))
    ref_relations = set(extract_spatial_relations(reference))

    if not pred_relations and not ref_relations:
        return 1.0
    if not pred_relations or not ref_relations:
        return 0.0

    common = pred_relations & ref_relations
    precision = len(common) / len(pred_relations)
    recall = len(common) / len(ref_relations)

    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall)


def evaluate_reasoning_accuracy(prediction: str, reference: str) -> bool:
    """评估推理准确率"""
    # 提取答案关键词
    pred_lower = prediction.strip()
    ref_lower = reference.strip()

    # 完全匹配
    if pred_lower == ref_lower:
        return True

    # 包含关系（答案在预测中）
    if ref_lower in pred_lower:
        return True

    # 数值匹配（提取数字）
    pred_numbers = re.findall(r'-?\d+\.?\d*', prediction)
    ref_numbers = re.findall(r'-?\d+\.?\d*', reference)

    if pred_numbers and ref_numbers:
        if set(pred_numbers) == set(ref_numbers):
            return True

    # 方向词匹配
    directions = ["东", "西", "南", "北", "东北", "西北", "东南", "西南",
                  "左", "右", "上", "下", "前", "后"]
    pred_dirs = [d for d in directions if d in prediction]
    ref_dirs = [d for d in directions if d in reference]
    if pred_dirs and ref_dirs and set(pred_dirs) == set(ref_dirs):
        return True

    return False


def generate_response(model, tokenizer, question: str, system_prompt: str, max_length: int = 512) -> str:
    """生成回答 - 使用 ChatML 格式"""
    # 构建 ChatML 格式消息
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    # 使用 apply_chat_template 生成 prompt
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_length,
            do_sample=False,
            temperature=1.0,
            top_p=1.0,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # 提取助手回复部分
    # ChatML 格式: <|im_start|>assistant\n...<|im_end|>
    if "<|im_start|>assistant" in response:
        response = response.split("<|im_start|>assistant")[-1]
        if "<|im_end|>" in response:
            response = response.split("<|im_end|>")[0]
        response = response.strip()

    return response


def main():
    parser = argparse.ArgumentParser(description="Exp2: B2-Standard-KD 评估")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--benchmark", type=str, default="../../data/geosr_chain/final/test.jsonl")
    parser.add_argument("--output", type=str, default="results/evaluation_results.json")
    args = parser.parse_args()

    work_dir = Path(__file__).parent
    os.chdir(work_dir)
    config = load_config(args.config)

    # 获取系统提示
    system_prompt = config.get('chat_template', {}).get(
        'system_prompt',
        "你是一个地理空间推理专家，擅长分析和解决空间关系问题。"
    )

    print("=" * 60)
    print("Exp2: B2-Standard-KD - 评估")
    print("=" * 60)
    print(f"检查点: {args.checkpoint}")
    print(f"基准测试: {args.benchmark}")
    print("=" * 60)

    print("\n[1/3] 加载模型...")
    model, tokenizer = load_model(args.checkpoint, config['model']['student']['name'])

    print("\n[2/3] 加载基准测试数据...")
    benchmark = load_benchmark(args.benchmark)
    print(f"共 {len(benchmark)} 条测试数据")

    print("\n[3/3] 开始评估...")
    results = {"reasoning_accuracy": [], "spatial_f1": [], "bleu": [], "rouge_l": [], "details": []}

    for item in tqdm(benchmark, desc="评估中"):
        question = item.get("question", "")
        reference = item.get("answer", "")

        if not question or not reference:
            continue

        prediction = generate_response(model, tokenizer, question, system_prompt)

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
        "experiment": "Exp2: B2-Standard-KD",
        "checkpoint": args.checkpoint,
        "benchmark": args.benchmark,
        "timestamp": datetime.now().isoformat(),
        "num_samples": len(benchmark),
        "metrics": {
            "reasoning_accuracy": np.mean(results["reasoning_accuracy"]) if results["reasoning_accuracy"] else 0,
            "spatial_f1": np.mean(results["spatial_f1"]) if results["spatial_f1"] else 0,
            "bleu": np.mean(results["bleu"]) if results["bleu"] else 0,
            "rouge_l": np.mean(results["rouge_l"]) if results["rouge_l"] else 0,
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
    print(f"BLEU-4: {summary['metrics']['bleu']:.4f}")
    print(f"ROUGE-L: {summary['metrics']['rouge_l']:.4f}")
    print("=" * 60)
    print(f"结果保存至: {output_path}")


if __name__ == "__main__":
    main()
