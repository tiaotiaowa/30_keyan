# -*- coding: utf-8 -*-
"""
模型加载工具模块
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Tuple, Optional


def load_model(
    model_path: str,
    quantization: Optional[str] = None,
    device: Optional[str] = None
) -> Tuple[AutoModelForCausalLM, AutoTokenizer]:
    """
    加载模型和分词器

    Args:
        model_path: 模型路径
        quantization: 量化方式 ("4bit", "8bit", None)
        device: 设备 (None表示自动选择)

    Returns:
        (model, tokenizer) 元组
    """
    # 确定设备
    if device is None:
        if torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

    # 加载分词器
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True
    )

    # 设置pad_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # 根据量化方式加载模型
    load_kwargs = {
        "torch_dtype": torch.float16,
        "trust_remote_code": True
    }

    if device == "cuda":
        load_kwargs["device_map"] = "auto"

    # 量化配置
    if quantization == "4bit":
        from transformers import BitsAndBytesConfig

        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4"
        )
        load_kwargs["quantization_config"] = quantization_config

    elif quantization == "8bit":
        from transformers import BitsAndBytesConfig

        quantization_config = BitsAndBytesConfig(
            load_in_8bit=True
        )
        load_kwargs["quantization_config"] = quantization_config

    # 加载模型
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        **load_kwargs
    )

    model.eval()

    return model, tokenizer


def get_model_size(model: AutoModelForCausalLM) -> int:
    """
    获取模型参数量

    Args:
        model: 模型

    Returns:
        参数量（单位：百万）
    """
    return sum(p.numel() for p in model.parameters()) / 1_000_000


def get_model_device(model: AutoModelForCausalLM) -> str:
    """
    获取模型所在设备

    Args:
        model: 模型

    Returns:
        设备字符串
    """
    return str(next(model.parameters()).device)
