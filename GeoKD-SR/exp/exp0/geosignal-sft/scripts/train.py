#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoSignal SFT 训练脚本

基于K2论文的GeoSignal数据集，训练Qwen2.5-1.5B地球科学指令遵循能力

使用方法:
    python train.py --config configs/train_24gb.yaml --seed 42
    python train.py --config configs/train_6gb.yaml --dry-run
"""

import os
import sys
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加路径
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent  # GeoKD-SR根目录
SRC_DIR = SCRIPT_DIR.parent / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入模块
from data_processor import GeoSignalDataProcessor, GeoSignalSample

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="GeoSignal SFT 训练")
    parser.add_argument("--config", type=str, required=True, help="配置文件路径")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--dry-run", action="store_true", help="仅验证配置")
    parser.add_argument("--resume", type=str, default=None, help="恢复训练的检查点")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    """加载YAML配置"""
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def setup_seed(seed: int):
    """设置随机种子"""
    import random
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    logger.info(f"随机种子设置为: {seed}")


def get_device_info() -> dict:
    """获取设备信息"""
    import torch

    info = {
        "cuda_available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
    }

    if info["cuda_available"]:
        info["device_name"] = torch.cuda.get_device_name(0)
        info["memory_allocated"] = torch.cuda.memory_allocated(0)
        info["memory_reserved"] = torch.cuda.memory_reserved(0)

    return info


def validate_data(config: dict, config_dir: str) -> bool:
    """验证数据文件"""
    data_cfg = config.get("data", {})

    for key in ["train_file", "dev_file"]:
        path = data_cfg.get(key, "")
        if not path:
            logger.error(f"配置中缺少 {key}")
            return False

        # 处理相对路径
        if not os.path.isabs(path):
            path = os.path.join(PROJECT_ROOT, path)

        if not os.path.exists(path):
            logger.warning(f"数据文件不存在: {path}")
            # 不返回False，因为数据可能还未下载

    return True


def dry_run(config: dict, config_dir: str):
    """Dry-run模式验证"""
    logger.info("=" * 60)
    logger.info("DRY-RUN 模式：验证配置")
    logger.info("=" * 60)

    exp_cfg = config.get("experiment", {})
    model_cfg = config.get("model", {})
    train_cfg = config.get("training", {})

    logger.info("\n[实验配置]")
    logger.info(f"  名称: {exp_cfg.get('name')}")
    logger.info(f"  类型: {exp_cfg.get('type')}")
    logger.info(f"  描述: {exp_cfg.get('description')}")

    logger.info("\n[模型配置]")
    logger.info(f"  名称: {model_cfg.get('name')}")
    logger.info(f"  路径: {model_cfg.get('path')}")
    logger.info(f"  使用LoRA: {model_cfg.get('use_lora')}")
    lora = model_cfg.get("lora", {})
    logger.info(f"  LoRA r={lora.get('r')}, alpha={lora.get('alpha')}")

    logger.info("\n[训练配置]")
    logger.info(f"  学习率: {train_cfg.get('learning_rate')}")
    logger.info(f"  批次大小: {train_cfg.get('batch_size')}")
    logger.info(f"  梯度累积: {train_cfg.get('gradient_accumulation_steps')}")
    eff_batch = train_cfg.get('batch_size', 1) * train_cfg.get('gradient_accumulation_steps', 1)
    logger.info(f"  有效批次: {eff_batch}")
    logger.info(f"  训练轮数: {train_cfg.get('num_epochs')}")

    # 设备信息
    logger.info("\n[设备信息]")
    device_info = get_device_info()
    for k, v in device_info.items():
        logger.info(f"  {k}: {v}")

    # 数据信息
    geosignal_info = config.get("geosignal_info", {})
    if geosignal_info:
        logger.info("\n[GeoSignal信息]")
        logger.info(f"  总样本数: {geosignal_info.get('total_samples')}")
        logger.info(f"  来源: {geosignal_info.get('source')}")

    logger.info("\n" + "=" * 60)
    logger.info("DRY-RUN 验证完成")
    logger.info("=" * 60)


def run_training(config: dict, config_dir: str, args):
    """执行训练"""
    try:
        from trl import SFTTrainer, SFTConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model, TaskType
        from datasets import Dataset
        import torch
    except ImportError as e:
        logger.error(f"缺少依赖: {e}")
        logger.error("请安装: pip install trl transformers peft datasets torch")
        return

    logger.info("=" * 60)
    logger.info("开始训练")
    logger.info("=" * 60)

    # 设置随机种子
    seed = args.seed or config.get("experiment", {}).get("seed", 42)
    setup_seed(seed)

    # 加载模型和tokenizer
    model_cfg = config.get("model", {})
    model_path = model_cfg.get("path", model_cfg.get("name"))

    logger.info(f"\n[1/4] 加载模型: {model_path}")

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 确定精度
    opt_cfg = config.get("optimization", {})
    mp = opt_cfg.get("mixed_precision", "fp16")
    torch_dtype = torch.bfloat16 if mp == "bf16" else torch.float16

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch_dtype,
        device_map="auto",
        trust_remote_code=True,
    )

    # 启用gradient checkpointing
    if opt_cfg.get("gradient_checkpointing", True):
        model.gradient_checkpointing_enable()

    # 配置LoRA
    if model_cfg.get("use_lora", True):
        logger.info("\n[2/4] 配置LoRA")
        lora_cfg = model_cfg.get("lora", {})
        peft_config = LoraConfig(
            r=lora_cfg.get("r", 8),
            lora_alpha=lora_cfg.get("alpha", 16),
            lora_dropout=lora_cfg.get("dropout", 0.05),
            target_modules=lora_cfg.get("target_modules", ["q_proj", "k_proj", "v_proj", "o_proj"]),
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()

    # 加载数据
    logger.info("\n[3/4] 加载数据")
    data_cfg = config.get("data", {})
    train_path = data_cfg.get("train_file", "")
    dev_path = data_cfg.get("dev_file", "")

    # 处理路径
    if not os.path.isabs(train_path):
        train_path = os.path.join(PROJECT_ROOT, train_path)
    if not os.path.isabs(dev_path):
        dev_path = os.path.join(PROJECT_ROOT, dev_path)

    system_prompt = data_cfg.get("system_prompt", "You are an expert in geoscience knowledge.")
    max_length = opt_cfg.get("max_length", 2048)

    processor = GeoSignalDataProcessor(
        tokenizer=tokenizer,
        max_length=max_length,
        system_prompt=system_prompt,
    )

    # 加载训练数据
    train_samples = processor.load_geosignal_jsonl(train_path)
    train_dataset = processor.create_hf_dataset(train_samples)

    # 加载验证数据
    dev_samples = processor.load_geosignal_jsonl(dev_path)
    dev_dataset = processor.create_hf_dataset(dev_samples)

    logger.info(f"训练样本: {len(train_dataset)}")
    logger.info(f"验证样本: {len(dev_dataset)}")

    # 配置训练参数
    logger.info("\n[4/4] 开始训练")
    train_cfg = config.get("training", {})
    out_cfg = config.get("output", {})

    # 确定输出目录
    output_dir = args.output_dir or os.path.join(
        PROJECT_ROOT,
        out_cfg.get("base_dir", "outputs"),
        f"seed_{seed}"
    )
    os.makedirs(output_dir, exist_ok=True)

    # 确定混合精度
    use_bf16 = mp == "bf16" and torch.cuda.is_bf16_supported()
    use_fp16 = mp == "fp16" or (mp == "bf16" and not torch.cuda.is_bf16_supported())

    sft_config = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=train_cfg.get("num_epochs", 3),
        per_device_train_batch_size=train_cfg.get("batch_size", 1),
        per_device_eval_batch_size=train_cfg.get("batch_size", 1),
        gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 128),
        learning_rate=train_cfg.get("learning_rate", 1e-4),
        weight_decay=train_cfg.get("weight_decay", 0.01),
        warmup_ratio=train_cfg.get("warmup_ratio", 0.1),
        max_grad_norm=train_cfg.get("max_grad_norm", 1.0),
        lr_scheduler_type=train_cfg.get("lr_scheduler_type", "cosine"),
        max_length=max_length,
        gradient_checkpointing=opt_cfg.get("gradient_checkpointing", True),
        bf16=use_bf16,
        fp16=use_fp16,
        logging_dir=os.path.join(output_dir, "logs"),
        logging_steps=10,
        report_to=["tensorboard"],
        save_strategy=out_cfg.get("save_strategy", "epoch"),
        save_total_limit=out_cfg.get("save_total_limit", 3),
        eval_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        seed=seed,
        remove_unused_columns=False,
    )

    # 创建trainer
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_dataset,
        eval_dataset=dev_dataset,
        processing_class=tokenizer,
    )

    # 开始训练
    logger.info(f"训练开始时间: {datetime.now()}")
    trainer.train(resume_from_checkpoint=args.resume)
    logger.info(f"训练结束时间: {datetime.now()}")

    # 保存模型
    final_path = os.path.join(output_dir, "final_model")
    trainer.save_model(final_path)
    tokenizer.save_pretrained(final_path)
    logger.info(f"模型保存到: {final_path}")

    # 保存训练配置
    config_save_path = os.path.join(output_dir, "training_config.json")
    save_config = {
        "experiment": config.get("experiment", {}),
        "model": {
            "name": model_cfg.get("name"),
            "path": model_cfg.get("path"),
            "lora": model_cfg.get("lora", {}),
        },
        "training": train_cfg,
        "optimization": opt_cfg,
        "runtime": {
            "seed": seed,
            "timestamp": datetime.now().isoformat(),
        }
    }
    with open(config_save_path, 'w', encoding='utf-8') as f:
        json.dump(save_config, f, ensure_ascii=False, indent=2)

    logger.info("=" * 60)
    logger.info("训练完成!")
    logger.info("=" * 60)


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 加载配置
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.getcwd(), config_path)

    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)

    config = load_config(config_path)
    config_dir = os.path.dirname(config_path)

    logger.info(f"配置文件: {config_path}")
    logger.info(f"项目根目录: {PROJECT_ROOT}")

    # Dry-run模式
    if args.dry_run:
        dry_run(config, config_dir)
        return

    # 验证数据
    if not validate_data(config, config_dir):
        logger.warning("数据验证存在问题，请确保数据已下载")

    # 执行训练
    run_training(config, config_dir, args)


if __name__ == "__main__":
    main()
