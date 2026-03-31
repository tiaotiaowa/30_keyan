# -*- coding: utf-8 -*-
"""
LoRA微调模型评测脚本 - 使用exp0评测模式

功能：
1. 正确加载LoRA权重（使用PeftModel）
2. 使用与exp0完全相同的提示词格式
3. 单条推理模式（batch_size=1）
4. 输出与exp0相同格式的predictions.jsonl

使用方法：
    python evaluate_lora_exp0.py \
        --base-model /path/to/Qwen2.5-1.5B-Instruct \
        --lora-path /path/to/lora/checkpoint \
        --test-file /path/to/test.jsonl \
        --output-file /path/to/predictions.jsonl

作者：GeoKD-SR项目组
日期：2026-03-27
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

import torch
from tqdm import tqdm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# 使用与 exp0 完全相同的 Prompt 模板
# 来源: exp/exp0/exp0/stage1_generation/config/generation_config.yaml
# ============================================================
PROMPT_TEMPLATE = """你是一个地理空间推理专家。请根据问题给出准确、简洁的答案。

问题: {question}

请直接给出答案，不需要解释过程。答案格式要求：
- 方向问题：直接说明方向，如"东南方向"
- 距离问题：给出具体数值，如"约1200公里"
- 拓扑问题：明确说明关系，如"是的，XX位于YY内部"
- 复合问题：同时给出最终结果

答案:"""


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


def load_lora_model(base_model_path: str, lora_path: str):
    """
    加载LoRA微调后的模型和分词器

    Args:
        base_model_path: 基础模型路径
        lora_path: LoRA权重路径

    Returns:
        model, tokenizer
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    logger.info(f"加载基础模型: {base_model_path}")
    logger.info(f"加载LoRA权重: {lora_path}")

    # 1. 加载分词器
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_path,
        trust_remote_code=True,
        use_fast=False
    )

    # 确保有pad_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. 加载基础模型
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )

    # 3. 加载LoRA权重
    model = PeftModel.from_pretrained(
        model,
        lora_path,
        torch_dtype=torch.float16
    )

    # 4. 合并LoRA权重到基础模型（提高推理速度）
    try:
        model = model.merge_and_unload()
        logger.info("LoRA权重已合并到基础模型")
    except Exception as e:
        logger.warning(f"无法合并LoRA权重: {e}，将使用原始方式")

    model.eval()

    return model, tokenizer


def generate_answer(
    model,
    tokenizer,
    question: str,
    max_new_tokens: int = 256,
    temperature: float = 0.1,
    top_p: float = 0.9,
    top_k: int = 50,
    do_sample: bool = True,
    repetition_penalty: float = 1.1
) -> str:
    """
    生成单个问题的答案（单条推理模式）

    使用与 exp0 完全相同的推理方式：
    1. 使用 prompt_template 格式化问题
    2. 使用 chat template
    3. 单条推理（batch_size=1）

    Args:
        model: 模型
        tokenizer: 分词器
        question: 问题文本
        max_new_tokens: 最大生成token数
        temperature: 温度参数
        top_p: nucleus采样参数
        top_k: top-k采样参数
        do_sample: 是否采样
        repetition_penalty: 重复惩罚

    Returns:
        生成的答案
    """
    # 1. 使用 prompt_template 格式化问题（与 exp0 一致）
    prompt = PROMPT_TEMPLATE.format(question=question)

    # 2. 使用 chat template（与 exp0 一致）
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    # 3. Tokenize（单条推理）
    inputs = tokenizer(text, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    # 4. 生成（与 exp0 一致的参数）
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            do_sample=do_sample,
            repetition_penalty=repetition_penalty,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id
        )

    # 5. 解码（只保留生成部分）
    generated_text = tokenizer.decode(
        outputs[0][inputs['input_ids'].shape[1]:],
        skip_special_tokens=True
    )

    return generated_text.strip()


def save_predictions(predictions: List[Dict], output_file: str):
    """保存预测结果"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        for item in predictions:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description="LoRA微调模型评测 - 使用exp0评测模式")

    # 必需参数
    parser.add_argument(
        "--base-model",
        type=str,
        required=True,
        help="基础模型路径"
    )
    parser.add_argument(
        "--lora-path",
        type=str,
        required=True,
        help="LoRA权重路径"
    )
    parser.add_argument(
        "--test-file",
        type=str,
        required=True,
        help="测试数据文件路径"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        required=True,
        help="输出文件路径"
    )

    # 可选参数（与 exp0 的 generation_config.yaml 保持一致）
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
        "--top-k",
        type=int,
        default=50,
        help="Top-K采样参数（默认: 50）"
    )
    parser.add_argument(
        "--do-sample",
        action="store_true",
        default=True,
        help="是否使用采样（默认: True）"
    )
    parser.add_argument(
        "--repetition-penalty",
        type=float,
        default=1.1,
        help="重复惩罚（默认: 1.1）"
    )
    parser.add_argument(
        "--save-interval",
        type=int,
        default=50,
        help="保存间隔（默认: 50）"
    )

    args = parser.parse_args()

    # 记录配置
    logger.info("="*60)
    logger.info("LoRA模型评测 - 使用exp0评测模式")
    logger.info("="*60)
    logger.info(f"基础模型: {args.base_model}")
    logger.info(f"LoRA权重: {args.lora_path}")
    logger.info(f"测试文件: {args.test_file}")
    logger.info(f"输出文件: {args.output_file}")
    logger.info(f"生成参数: max_new_tokens={args.max_new_tokens}, temperature={args.temperature}")
    logger.info("="*60)

    # 检查CUDA
    if not torch.cuda.is_available():
        logger.warning("CUDA不可用，将使用CPU")
    else:
        logger.info(f"CUDA可用: {torch.cuda.get_device_name(0)}")

    # 加载模型
    logger.info("加载模型...")
    model, tokenizer = load_lora_model(args.base_model, args.lora_path)
    logger.info("模型加载完成")

    # 加载测试数据
    test_data = load_test_data(args.test_file)

    # 生成预测
    predictions = []
    logger.info(f"开始生成预测，共 {len(test_data)} 条（单条推理模式）")

    for i, item in enumerate(tqdm(test_data, desc="生成中")):
        try:
            prediction = generate_answer(
                model,
                tokenizer,
                item['question'],
                max_new_tokens=args.max_new_tokens,
                temperature=args.temperature,
                top_p=args.top_p,
                top_k=args.top_k,
                do_sample=args.do_sample,
                repetition_penalty=args.repetition_penalty
            )

            result = {
                "id": item.get('id', f'item_{i}'),
                "question": item['question'],
                "reference": item.get('answer', ''),
                "prediction": prediction,
                "spatial_type": item.get('spatial_relation_type', 'unknown'),
                "difficulty": item.get('difficulty', 'unknown')
            }
            predictions.append(result)

            # 定期保存
            if (i + 1) % args.save_interval == 0:
                save_predictions(predictions, args.output_file)
                logger.info(f"已处理 {i + 1}/{len(test_data)} 条，已保存")

        except Exception as e:
            logger.error(f"处理第 {i} 条数据时出错: {e}")
            predictions.append({
                "id": item.get('id', f'item_{i}'),
                "question": item['question'],
                "reference": item.get('answer', ''),
                "prediction": f"ERROR: {str(e)}",
                "spatial_type": item.get('spatial_relation_type', 'unknown'),
                "difficulty": item.get('difficulty', 'unknown')
            })

    # 最终保存
    save_predictions(predictions, args.output_file)
    logger.info(f"预测完成！共 {len(predictions)} 条，保存至: {args.output_file}")

    # 打印示例
    logger.info("\n" + "="*60)
    logger.info("预测示例（前3条）:")
    logger.info("="*60)
    for i, pred in enumerate(predictions[:3]):
        logger.info(f"\n[{i+1}] ID: {pred['id']}")
        logger.info(f"    问题: {pred['question'][:50]}...")
        logger.info(f"    参考: {pred['reference']}")
        logger.info(f"    预测: {pred['prediction'][:100]}...")

    return predictions


if __name__ == "__main__":
    main()
