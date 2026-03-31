#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp02 Stage1: 加载LoRA微调后的模型，使用与exp0完全相同的prompt模板和生成参数生成预测结果
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

import torch
from tqdm import tqdm
import yaml


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_predictions(config: dict, checkpoint_path: str) -> List[Dict]:
    """
    加载base模型 + LoRA adapter，生成预测结果
    使用与exp0完全相同的prompt模板和生成参数
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    # 加载base模型
    model_config = config.get("model", {})
    base_name = model_config.get("base_name", "")
    device = model_config.get("device", "cuda")
    dtype_str = model_config.get("dtype", "float16")
    dtype = torch.float16 if dtype_str == "float16" else torch.bfloat16

    print(f"加载base模型: {base_name}")
    tokenizer = AutoTokenizer.from_pretrained(base_name, trust_remote_code=True, use_fast=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_name,
        torch_dtype=dtype,
        device_map=device,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )

    # 加载LoRA adapter并合并
    if checkpoint_path:
        print(f"加载LoRA adapter: {checkpoint_path}")
        model = PeftModel.from_pretrained(model, checkpoint_path)
        model = model.merge_and_unload()
        print("LoRA权重已合并")

    model.eval()

    # 加载测试数据
    data_config = config.get("data", {})
    test_path = data_config.get("input_file", "")
    print(f"加载测试数据: {test_path}")

    test_data = []
    with open(test_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                test_data.append(json.loads(line))
    print(f"共 {len(test_data)} 条测试数据")

    # 获取prompt模板（与exp0完全一致）
    prompt_template = config.get("prompt_template", "问题：{question}\n答案：")

    # 生成参数
    gen_config = config.get("generation", {})

    predictions = []
    save_interval = config.get("logging", {}).get("save_interval", 50)
    output_file = data_config.get("output_file", "./outputs/predictions.jsonl")

    print("开始生成预测...")
    for i, item in enumerate(tqdm(test_data, desc="生成中")):
        question = item.get("question", "")
        reference = item.get("answer", "")

        if not question:
            continue

        # 使用与exp0相同的prompt格式
        prompt = prompt_template.format(question=question)

        # ChatML格式
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=gen_config.get("max_new_tokens", 256),
                temperature=gen_config.get("temperature", 0.1),
                top_p=gen_config.get("top_p", 0.9),
                top_k=gen_config.get("top_k", 50),
                do_sample=gen_config.get("do_sample", True),
                repetition_penalty=gen_config.get("repetition_penalty", 1.1),
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        generated = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )

        result = {
            "id": item.get("id", f"item_{i}"),
            "question": item.get("question", ""),
            "reference": reference,
            "prediction": generated.strip(),
            "spatial_type": item.get("spatial_relation_type", "unknown"),
            "difficulty": item.get("difficulty", "unknown"),
        }
        predictions.append(result)

        if (i + 1) % save_interval == 0:
            _save_predictions(predictions, output_file)
            print(f"已处理 {i + 1}/{len(test_data)} 条")

    _save_predictions(predictions, output_file)
    print(f"生成完成！共 {len(predictions)} 条，保存至: {output_file}")
    return predictions


def _save_predictions(predictions: List[Dict], output_file: str):
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for item in predictions:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Exp02 Stage1: 生成预测结果")
    parser.add_argument("--config", type=str, default="stage1_config.yaml")
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="LoRA checkpoint路径")
    args = parser.parse_args()

    config = load_config(args.config)

    print("=" * 60)
    print("Exp02 Stage1: 生成预测结果")
    print("=" * 60)
    print(f"配置文件: {args.config}")
    print(f"LoRA checkpoint: {args.checkpoint}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    generate_predictions(config, args.checkpoint)

    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
