# -*- coding: utf-8 -*-
"""
Qwen2.5-1.5B SFT 微调模块

实验类型: Exp1 Direct-SFT 基线
设计文档: docs/superpowers/specs/2026-03-21-qwen-1.5b-sft-design.md
"""

from .config import Config, load_config
from .data_processor import GeoSRDataProcessor, ChatMLConverter
from .trainer import GeoSRSFTTrainer
from .utils import setup_seed, setup_logging, get_device_info

__version__ = "1.0.0"
__all__ = [
    "Config",
    "load_config",
    "GeoSRDataProcessor",
    "ChatMLConverter",
    "GeoSRSFTTrainer",
    "setup_seed",
    "setup_logging",
    "get_device_info",
]
