# -*- coding: utf-8 -*-
"""
GeoSR SFT 训练器模块

使用 TRL 的 SFTTrainer 进行监督微调，支持 LoRA 参数高效微调
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, Union

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    AutoConfig,
    BitsAndBytesConfig,
    PreTrainedModel,
    PreTrainedTokenizer,
)
from trl import SFTTrainer, SFTConfig

from config import Config, LoRAConfig as ConfigLoRAConfig

logger = logging.getLogger(__name__)


class GeoSRSFTTrainer:
    """
    GeoSR SFT 训练器

    封装 TRL 的 SFTTrainer，支持：
    - LoRA 参数高效微调
    - Gradient Checkpointing
    - FP16/BF16 混合精度训练
    - Trackio 日志记录
    - 自动保存 checkpoints

    Example:
        >>> from src.config import load_config
        >>> from src.trainer import GeoSRSFTTrainer
        >>>
        >>> config = load_config("config.yaml")
        >>> trainer = GeoSRSFTTrainer(model_path="Qwen/Qwen2.5-1.5B-Instruct", config=config)
        >>> trainer.train(train_dataset=train_data, eval_dataset=eval_data)
        >>> trainer.save_model("output/model")
    """

    def __init__(
        self,
        model_path: str,
        config: Config,
        tokenizer: Optional[PreTrainedTokenizer] = None,
        model: Optional[PreTrainedModel] = None,
    ):
        """
        初始化训练器

        Args:
            model_path: 模型路径（本地路径或 HuggingFace 模型ID）
            config: 训练配置对象
            tokenizer: 可选的预加载 tokenizer
            model: 可选的预加载模型
        """
        self.model_path = model_path
        self.config = config
        self._tokenizer = tokenizer
        self._model = model
        self._trainer: Optional[SFTTrainer] = None
        self._peft_config: Optional[LoraConfig] = None

        # 训练状态
        self._is_setup = False
        self._is_trained = False

        logger.info(f"初始化 GeoSRSFTTrainer: model_path={model_path}")
        logger.info(f"实验配置: {config.experiment.name}, type={config.experiment.type}")

    def setup_model_and_tokenizer(self) -> None:
        """
        设置模型和 tokenizer

        包括：
        - 加载模型和 tokenizer
        - 配置 gradient checkpointing
        - 设置混合精度
        """
        if self._is_setup:
            logger.warning("模型已设置，跳过重复初始化")
            return

        logger.info("开始加载模型和 tokenizer...")

        # 加载 tokenizer
        if self._tokenizer is None:
            self._tokenizer = self._load_tokenizer()

        # 加载模型
        if self._model is None:
            self._model = self._load_model()

        # 配置 gradient checkpointing
        if self.config.optimization.gradient_checkpointing:
            self._model.gradient_checkpointing_enable()
            logger.info("已启用 Gradient Checkpointing")

        # 如果使用 LoRA，准备模型
        if self.config.model.use_lora:
            self._model = prepare_model_for_kbit_training(self._model)
            logger.info("模型已准备进行 LoRA 训练")

        self._is_setup = True
        logger.info("模型和 tokenizer 设置完成")

    def _load_tokenizer(self) -> PreTrainedTokenizer:
        """加载 tokenizer"""
        logger.info(f"加载 tokenizer: {self.model_path}")

        tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            use_fast=True,
        )

        # 确保 pad_token 存在
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            logger.info(f"设置 pad_token = eos_token: {tokenizer.eos_token}")

        # Qwen 特殊设置
        if tokenizer.chat_template is None:
            logger.warning("Tokenizer 没有 chat_template，请确保数据处理正确")

        return tokenizer

    def _load_model(self) -> PreTrainedModel:
        """加载模型"""
        logger.info(f"加载模型: {self.model_path}")

        # 确定数据类型
        torch_dtype = self._get_torch_dtype()

        # 加载模型配置
        model_config = AutoConfig.from_pretrained(
            self.model_path,
            trust_remote_code=True,
        )

        # 加载模型
        model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            config=model_config,
            torch_dtype=torch_dtype,
            device_map="auto",
            trust_remote_code=True,
            quantization_config=None,  # 不使用量化，保持精度
        )

        logger.info(f"模型加载完成: {model.__class__.__name__}")
        logger.info(f"模型参数量: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")

        return model

    def _get_torch_dtype(self) -> torch.dtype:
        """根据配置获取 torch 数据类型"""
        mp = self.config.optimization.mixed_precision.lower()
        if mp == "bf16":
            if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
                logger.info("使用 BF16 混合精度")
                return torch.bfloat16
            else:
                logger.warning("BF16 不支持，回退到 FP16")
                return torch.float16
        elif mp == "fp16":
            logger.info("使用 FP16 混合精度")
            return torch.float16
        else:
            logger.info("使用 FP32 全精度")
            return torch.float32

    def setup_lora(self) -> LoraConfig:
        """
        设置 LoRA 配置

        Returns:
            PEFT LoRAConfig 对象
        """
        if not self.config.model.use_lora:
            logger.info("不使用 LoRA，跳过设置")
            return None

        lora_cfg = self.config.model.lora

        self._peft_config = LoraConfig(
            r=lora_cfg.r,
            lora_alpha=lora_cfg.alpha,
            lora_dropout=lora_cfg.dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            target_modules=lora_cfg.target_modules,
        )

        logger.info(f"LoRA 配置: r={lora_cfg.r}, alpha={lora_cfg.alpha}, "
                    f"dropout={lora_cfg.dropout}, scaling={lora_cfg.scaling:.2f}")
        logger.info(f"LoRA 目标模块: {lora_cfg.target_modules}")

        return self._peft_config

    def _build_sft_config(self, output_dir: str) -> SFTConfig:
        """
        构建 SFT 训练配置

        Args:
            output_dir: 输出目录

        Returns:
            SFTConfig 对象
        """
        train_cfg = self.config.training
        opt_cfg = self.config.optimization
        out_cfg = self.config.output
        exp_cfg = self.config.experiment

        # 确定混合精度
        use_bf16 = opt_cfg.mixed_precision.lower() == "bf16"
        use_fp16 = opt_cfg.mixed_precision.lower() == "fp16"

        # 如果 BF16 不可用，回退到 FP16
        if use_bf16 and not (torch.cuda.is_available() and torch.cuda.is_bf16_supported()):
            use_bf16 = False
            use_fp16 = True
            logger.warning("BF16 不可用，回退到 FP16")

        sft_config = SFTConfig(
            # 输出目录
            output_dir=output_dir,

            # 训练超参数
            num_train_epochs=train_cfg.num_epochs,
            per_device_train_batch_size=train_cfg.batch_size,
            per_device_eval_batch_size=train_cfg.batch_size,
            gradient_accumulation_steps=train_cfg.gradient_accumulation_steps,
            learning_rate=train_cfg.learning_rate,
            weight_decay=train_cfg.weight_decay,
            warmup_ratio=train_cfg.warmup_ratio,
            lr_scheduler_type=train_cfg.lr_scheduler_type,
            max_grad_norm=train_cfg.max_grad_norm,
            # 优化器使用默认 adamw（24GB显存环境）

            # 序列长度
            max_length=opt_cfg.max_length,

            # 优化
            gradient_checkpointing=opt_cfg.gradient_checkpointing,
            bf16=use_bf16,
            fp16=use_fp16,

            # 日志
            logging_dir=os.path.join(output_dir, out_cfg.logging_dir),
            logging_steps=10,
            report_to=["tensorboard"],  # 使用 tensorboard 代替 trackio

            # 保存策略
            save_strategy=out_cfg.save_strategy,
            save_total_limit=out_cfg.save_total_limit,
            save_only_model=True,  # 只保存模型，节省空间

            # 评估
            eval_strategy="epoch" if out_cfg.save_strategy == "epoch" else "steps",
            eval_steps=0.1,  # 如果使用 steps，每 10% 评估一次
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",

            # 其他
            seed=exp_cfg.seed,
            dataloader_num_workers=4,
            dataloader_pin_memory=True,
            remove_unused_columns=False,

            # 标签
            run_name=f"{exp_cfg.name}_{exp_cfg.seed}",
        )

        logger.info(f"SFT 配置:")
        logger.info(f"  - epochs: {train_cfg.num_epochs}")
        logger.info(f"  - batch_size: {train_cfg.batch_size}")
        logger.info(f"  - gradient_accumulation: {train_cfg.gradient_accumulation_steps}")
        logger.info(f"  - effective_batch_size: {self.config.effective_batch_size}")
        logger.info(f"  - learning_rate: {train_cfg.learning_rate}")
        logger.info(f"  - max_length: {opt_cfg.max_length}")
        logger.info(f"  - mixed_precision: {opt_cfg.mixed_precision}")
        logger.info(f"  - gradient_checkpointing: {opt_cfg.gradient_checkpointing}")
        logger.info(f"  - optimizer: adamw (标准优化器)")

        return sft_config

    def train(
        self,
        train_dataset: Dataset,
        eval_dataset: Optional[Dataset] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行训练

        Args:
            train_dataset: 训练数据集
            eval_dataset: 验证数据集（可选）
            output_dir: 输出目录（可选，默认使用配置中的路径）

        Returns:
            训练结果字典
        """
        # 确保模型已设置
        if not self._is_setup:
            self.setup_model_and_tokenizer()

        # 设置 LoRA
        if self.config.model.use_lora:
            self.setup_lora()

        # 确定输出目录
        if output_dir is None:
            output_dir = str(self.config.get_output_path("default"))

        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        logger.info(f"训练输出目录: {output_dir}")

        # 构建 SFT 配置
        sft_config = self._build_sft_config(output_dir)

        # 创建 SFT Trainer
        logger.info("创建 SFTTrainer...")
        self._trainer = SFTTrainer(
            model=self._model,
            args=sft_config,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            processing_class=self._tokenizer,
            peft_config=self._peft_config,
        )

        # 打印可训练参数
        self._log_trainable_parameters()

        # 开始训练
        logger.info("=" * 50)
        logger.info("开始训练...")
        logger.info("=" * 50)

        train_result = self._trainer.train()

        logger.info("=" * 50)
        logger.info("训练完成!")
        logger.info("=" * 50)

        # 记录训练结果
        metrics = train_result.metrics
        logger.info(f"训练指标: {metrics}")

        # 保存最终模型
        self.save_model(output_dir)

        self._is_trained = True

        return {
            "metrics": metrics,
            "output_dir": output_dir,
            "model_path": os.path.join(output_dir, "final_model"),
        }

    def _log_trainable_parameters(self) -> None:
        """打印可训练参数信息"""
        if self._trainer is None:
            return

        model = self._trainer.model
        trainable_params = 0
        all_params = 0

        for _, param in model.named_parameters():
            all_params += param.numel()
            if param.requires_grad:
                trainable_params += param.numel()

        trainable_pct = 100 * trainable_params / all_params

        logger.info(f"可训练参数: {trainable_params:,} / {all_params:,} ({trainable_pct:.4f}%)")

        if self.config.model.use_lora:
            logger.info(f"LoRA 参数占比: {trainable_pct:.4f}%")

    def save_model(self, output_path: str) -> None:
        """
        保存模型

        Args:
            output_path: 保存路径
        """
        if self._trainer is None:
            raise RuntimeError("训练器未初始化，无法保存模型")

        logger.info(f"保存模型到: {output_path}")

        # 创建输出目录
        save_path = Path(output_path) / "final_model"
        save_path.mkdir(parents=True, exist_ok=True)

        # 保存模型
        if self.config.model.use_lora:
            # LoRA 模型保存
            self._trainer.model.save_pretrained(str(save_path))
            logger.info(f"LoRA 适配器已保存到: {save_path}")
        else:
            # 完整模型保存
            self._trainer.model.save_pretrained(str(save_path))
            logger.info(f"完整模型已保存到: {save_path}")

        # 保存 tokenizer
        self._tokenizer.save_pretrained(str(save_path))
        logger.info(f"Tokenizer 已保存到: {save_path}")

        # 保存训练配置
        config_save_path = save_path / "training_config.yaml"
        self._save_training_config(config_save_path)
        logger.info(f"训练配置已保存到: {config_save_path}")

    def _save_training_config(self, config_path: Path) -> None:
        """保存训练配置到 YAML 文件"""
        import yaml
        from dataclasses import asdict

        config_dict = {
            "experiment": asdict(self.config.experiment),
            "model": {
                "name": self.config.model.name,
                "path": self.config.model.path,
                "use_lora": self.config.model.use_lora,
                "lora": asdict(self.config.model.lora),
            },
            "training": asdict(self.config.training),
            "optimization": asdict(self.config.optimization),
        }

        # 移除 None 值
        def remove_none(d):
            if isinstance(d, dict):
                return {k: remove_none(v) for k, v in d.items() if v is not None}
            return d

        config_dict = remove_none(config_dict)

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, allow_unicode=True, default_flow_style=False)

    @property
    def model(self) -> PreTrainedModel:
        """获取模型"""
        if self._model is None:
            raise RuntimeError("模型未加载，请先调用 setup_model_and_tokenizer()")
        return self._model

    @property
    def tokenizer(self) -> PreTrainedTokenizer:
        """获取 tokenizer"""
        if self._tokenizer is None:
            raise RuntimeError("Tokenizer 未加载，请先调用 setup_model_and_tokenizer()")
        return self._tokenizer

    @property
    def trainer(self) -> SFTTrainer:
        """获取 TRL trainer"""
        if self._trainer is None:
            raise RuntimeError("Trainer 未初始化，请先调用 train()")
        return self._trainer


def create_trainer(
    model_path: str,
    config: Config,
    **kwargs
) -> GeoSRSFTTrainer:
    """
    创建训练器的便捷函数

    Args:
        model_path: 模型路径
        config: 配置对象
        **kwargs: 额外参数传递给 GeoSRSFTTrainer

    Returns:
        GeoSRSFTTrainer 实例
    """
    trainer = GeoSRSFTTrainer(
        model_path=model_path,
        config=config,
        **kwargs
    )
    trainer.setup_model_and_tokenizer()
    return trainer
