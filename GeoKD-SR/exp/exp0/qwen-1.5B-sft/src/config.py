# -*- coding: utf-8 -*-
"""
配置加载模块

支持从 YAML 文件加载训练和评测配置
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

import yaml


@dataclass
class LoRAConfig:
    """LoRA 配置"""
    r: int = 8
    alpha: int = 16
    dropout: float = 0.05
    target_modules: List[str] = field(default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj"])

    @property
    def scaling(self) -> float:
        """LoRA scaling factor"""
        return self.alpha / self.r


@dataclass
class ModelConfig:
    """模型配置"""
    name: str = "Qwen2.5-1.5B-Instruct"
    path: str = ""
    use_lora: bool = True
    lora: LoRAConfig = field(default_factory=LoRAConfig)


@dataclass
class TrainingConfig:
    """训练配置"""
    learning_rate: float = 5e-5
    batch_size: int = 1
    gradient_accumulation_steps: int = 128
    num_epochs: int = 3
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0
    lr_scheduler_type: str = "cosine"


@dataclass
class OptimizationConfig:
    """优化配置"""
    max_length: int = 1024
    gradient_checkpointing: bool = True
    mixed_precision: str = "fp16"  # "fp16" or "bf16"


@dataclass
class DataConfig:
    """数据配置"""
    train_file: str = ""
    dev_file: str = ""
    system_prompt: str = "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。请简洁准确地回答问题。"


@dataclass
class OutputConfig:
    """输出配置"""
    base_dir: str = "outputs"
    logging_dir: str = "logs"
    checkpoint_dir: str = "checkpoints"
    save_strategy: str = "epoch"
    save_total_limit: int = 3


@dataclass
class ExperimentConfig:
    """实验配置"""
    name: str = "qwen-1.5b-sft"
    type: str = "exp1_direct_sft"
    seed: int = 42
    seeds: Optional[List[int]] = None  # 用于多随机种子实验


@dataclass
class Config:
    """完整配置"""
    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    data: DataConfig = field(default_factory=DataConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @property
    def effective_batch_size(self) -> int:
        """计算有效批次大小"""
        return self.training.batch_size * self.training.gradient_accumulation_steps

    def get_output_path(self, dataset_name: str, seed: Optional[int] = None) -> Path:
        """获取输出路径"""
        seed = seed or self.experiment.seed
        return Path(self.output.base_dir) / dataset_name / f"seed_{seed}"


def load_config(config_path: str) -> Config:
    """
    从 YAML 文件加载配置

    Args:
        config_path: 配置文件路径

    Returns:
        Config 对象
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)

    # 解析嵌套配置
    config = Config()

    # 实验配置
    if 'experiment' in raw_config:
        exp_data = raw_config['experiment']
        config.experiment = ExperimentConfig(
            name=exp_data.get('name', config.experiment.name),
            type=exp_data.get('type', config.experiment.type),
            seed=exp_data.get('seed', config.experiment.seed),
            seeds=exp_data.get('seeds', None),
        )

    # 模型配置
    if 'model' in raw_config:
        model_data = raw_config['model']
        lora_config = LoRAConfig()
        if 'lora' in model_data:
            lora_data = model_data['lora']
            lora_config = LoRAConfig(
                r=lora_data.get('r', 8),
                alpha=lora_data.get('alpha', 16),
                dropout=lora_data.get('dropout', 0.05),
                target_modules=lora_data.get('target_modules', ["q_proj", "k_proj", "v_proj", "o_proj"]),
            )
        config.model = ModelConfig(
            name=model_data.get('name', config.model.name),
            path=model_data.get('path', config.model.path),
            use_lora=model_data.get('use_lora', True),
            lora=lora_config,
        )

    # 训练配置
    if 'training' in raw_config:
        train_data = raw_config['training']
        config.training = TrainingConfig(
            learning_rate=train_data.get('learning_rate', 5e-5),
            batch_size=train_data.get('batch_size', 1),
            gradient_accumulation_steps=train_data.get('gradient_accumulation_steps', 128),
            num_epochs=train_data.get('num_epochs', 3),
            warmup_ratio=train_data.get('warmup_ratio', 0.1),
            weight_decay=train_data.get('weight_decay', 0.01),
            max_grad_norm=train_data.get('max_grad_norm', 1.0),
            lr_scheduler_type=train_data.get('lr_scheduler_type', 'cosine'),
        )

    # 优化配置
    if 'optimization' in raw_config:
        opt_data = raw_config['optimization']
        config.optimization = OptimizationConfig(
            max_length=opt_data.get('max_length', 1024),
            gradient_checkpointing=opt_data.get('gradient_checkpointing', True),
            mixed_precision=opt_data.get('mixed_precision', 'fp16'),
        )

    # 数据配置
    if 'data' in raw_config:
        data_cfg = raw_config['data']
        config.data = DataConfig(
            train_file=data_cfg.get('train_file', ''),
            dev_file=data_cfg.get('dev_file', ''),
            system_prompt=data_cfg.get('system_prompt', config.data.system_prompt),
        )

    # 输出配置
    if 'output' in raw_config:
        out_data = raw_config['output']
        config.output = OutputConfig(
            base_dir=out_data.get('base_dir', 'outputs'),
            logging_dir=out_data.get('logging_dir', 'logs'),
            checkpoint_dir=out_data.get('checkpoint_dir', 'checkpoints'),
            save_strategy=out_data.get('save_strategy', 'epoch'),
            save_total_limit=out_data.get('save_total_limit', 3),
        )

    return config


def get_dataset_path(config: Config, dataset_name: str, base_dir: str = None) -> dict:
    """
    获取数据集路径

    Args:
        config: 配置对象
        dataset_name: 数据集名称 (splits 或 split_coords)
        base_dir: 基础目录（用于相对路径转换）

    Returns:
        包含 train_file 和 dev_file 的字典
    """
    base_dir = base_dir or os.getcwd()

    def resolve_path(path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(base_dir, path))

    # 如果配置中已有具体路径，直接使用
    if config.data.train_file:
        return {
            'train_file': resolve_path(config.data.train_file.replace('splits', dataset_name)),
            'dev_file': resolve_path(config.data.dev_file.replace('splits', dataset_name)),
        }

    # 否则使用默认路径
    return {
        'train_file': resolve_path(f"data/{dataset_name}/train.jsonl"),
        'dev_file': resolve_path(f"data/{dataset_name}/dev.jsonl"),
    }
