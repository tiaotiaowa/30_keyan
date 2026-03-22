# -*- coding: utf-8 -*-
"""
GeoSR SFT 主训练脚本

实验类型: Exp1 Direct-SFT 基线
设计文档: docs/superpowers/specs/2026-03-21-qwen-1.5b-sft-design.md

使用方法:
    python train.py --config configs/train_6gb.yaml --dataset splits
    python train.py --config configs/train_24gb.yaml --dataset split_coords --seed 123
    python train.py --config configs/train_6gb.yaml --dataset splits --dry-run
    python train.py --config configs/train_6gb.yaml --dataset splits --resume
"""

import os
import sys
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加 src 目录到 sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
GEOKD_ROOT = PROJECT_ROOT.parent.parent.parent  # GeoKD-SR 根目录

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# 导入配置模块
try:
    from config import Config, load_config, get_dataset_path
except ImportError:
    # 如果 src 下的模块还未创建，使用父级导入
    sys.path.insert(0, str(GEOKD_ROOT / "exp/exp0/qwen-1.5B-sft/src"))
    from config import Config, load_config, get_dataset_path

# 尝试导入其他模块（可能尚未创建）
try:
    from data_processor import GeoSRDataProcessor, ChatMLConverter
    from trainer import GeoSRSFTTrainer
    from utils import setup_seed, setup_logging, get_device_info
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    IMPORT_ERROR = str(e)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="GeoSR SFT 训练脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本训练
  python train.py --config configs/train_6gb.yaml --dataset splits

  # 指定随机种子
  python train.py --config configs/train_6gb.yaml --dataset split_coords --seed 123

  # 仅验证数据加载（不进行训练）
  python train.py --config configs/train_6gb.yaml --dataset splits --dry-run

  # 从 checkpoint 恢复训练
  python train.py --config configs/train_6gb.yaml --dataset splits --resume
        """
    )

    # 必需参数
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="配置文件路径 (YAML 格式)"
    )

    # 可选参数
    parser.add_argument(
        "--dataset",
        type=str,
        default="splits",
        choices=["splits", "split_coords"],
        help="数据集名称: splits (不含坐标) 或 split_coords (含坐标)，默认: splits"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子（覆盖配置文件中的设置）"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅验证数据加载，不进行实际训练"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="从 checkpoint 恢复训练"
    )

    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="指定恢复的 checkpoint 路径（如不指定则自动查找最新的）"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="输出目录（覆盖配置文件中的设置）"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细日志"
    )

    return parser.parse_args()


def resolve_path(path: str, base_dir: str = None) -> str:
    """
    解析路径，支持相对路径和绝对路径

    Args:
        path: 原始路径
        base_dir: 基础目录（用于相对路径转换）

    Returns:
        解析后的绝对路径
    """
    if os.path.isabs(path):
        return os.path.normpath(path)

    base_dir = base_dir or os.getcwd()
    resolved = os.path.normpath(os.path.join(base_dir, path))
    return resolved


def setup_environment(config: Config, args) -> dict:
    """
    设置训练环境

    Args:
        config: 配置对象
        args: 命令行参数

    Returns:
        环境信息字典
    """
    # 覆盖随机种子
    if args.seed is not None:
        config.experiment.seed = args.seed
        logger.info(f"随机种子已覆盖为: {args.seed}")

    # 设置随机种子
    if MODULES_AVAILABLE:
        setup_seed(config.experiment.seed)
    else:
        import random
        import numpy as np
        import torch
        random.seed(config.experiment.seed)
        np.random.seed(config.experiment.seed)
        torch.manual_seed(config.experiment.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(config.experiment.seed)
        logger.info(f"随机种子已设置: {config.experiment.seed}")

    # 获取设备信息
    device_info = {}
    if MODULES_AVAILABLE:
        device_info = get_device_info()
    else:
        import torch
        device_info = {
            "cuda_available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "current_device": torch.cuda.current_device() if torch.cuda.is_available() else None,
        }
        if device_info["cuda_available"]:
            device_info["device_name"] = torch.cuda.get_device_name(0)
            device_info["memory_allocated"] = torch.cuda.memory_allocated(0)
            device_info["memory_reserved"] = torch.cuda.memory_reserved(0)

    logger.info(f"设备信息: {device_info}")

    return device_info


def get_data_paths(config: Config, dataset_name: str, config_dir: str) -> dict:
    """
    获取数据路径

    Args:
        config: 配置对象
        dataset_name: 数据集名称
        config_dir: 配置文件所在目录

    Returns:
        包含数据路径的字典
    """
    # 使用 GeoKD-SR 根目录作为基础目录
    base_dir = str(GEOKD_ROOT)

    paths = get_dataset_path(config, dataset_name, base_dir)

    # 确保路径存在
    for key in ["train_file", "dev_file"]:
        if key in paths:
            paths[key] = resolve_path(paths[key], base_dir)

    return paths


def create_output_dirs(config: Config, args) -> dict:
    """
    创建输出目录

    Args:
        config: 配置对象
        args: 命令行参数

    Returns:
        输出目录路径字典
    """
    # 获取输出路径
    output_path = config.get_output_path(args.dataset, args.seed)

    # 如果命令行指定了输出目录，使用命令行的
    if args.output_dir:
        output_path = Path(args.output_dir)

    # 创建目录
    dirs = {
        "base": str(output_path),
        "logs": str(output_path / config.output.logging_dir),
        "checkpoints": str(output_path / config.output.checkpoint_dir),
    }

    for name, dir_path in dirs.items():
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"创建目录 [{name}]: {dir_path}")

    return dirs


def validate_data(data_paths: dict) -> bool:
    """
    验证数据文件

    Args:
        data_paths: 数据路径字典

    Returns:
        是否验证通过
    """
    for key, path in data_paths.items():
        if not os.path.exists(path):
            logger.error(f"数据文件不存在: {path}")
            return False

        # 检查文件是否可读
        try:
            with open(path, 'r', encoding='utf-8') as f:
                # 读取第一行验证格式
                first_line = f.readline().strip()
                if first_line:
                    json.loads(first_line)
                else:
                    logger.warning(f"数据文件为空: {path}")
        except json.JSONDecodeError as e:
            logger.error(f"数据文件 JSON 格式错误 [{path}]: {e}")
            return False
        except Exception as e:
            logger.error(f"无法读取数据文件 [{path}]: {e}")
            return False

    return True


def count_samples(file_path: str) -> int:
    """
    统计样本数量

    Args:
        file_path: 数据文件路径

    Returns:
        样本数量
    """
    count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        for _ in f:
            count += 1
    return count


def dry_run_validation(config: Config, data_paths: dict, output_dirs: dict):
    """
    Dry-run 模式：仅验证数据加载

    Args:
        config: 配置对象
        data_paths: 数据路径
        output_dirs: 输出目录
    """
    logger.info("=" * 60)
    logger.info("DRY-RUN 模式：验证数据加载")
    logger.info("=" * 60)

    # 验证配置
    logger.info("\n[配置信息]")
    logger.info(f"  实验名称: {config.experiment.name}")
    logger.info(f"  实验类型: {config.experiment.type}")
    logger.info(f"  随机种子: {config.experiment.seed}")
    logger.info(f"  模型名称: {config.model.name}")
    logger.info(f"  模型路径: {config.model.path}")
    logger.info(f"  使用 LoRA: {config.model.use_lora}")
    logger.info(f"  学习率: {config.training.learning_rate}")
    logger.info(f"  批次大小: {config.training.batch_size}")
    logger.info(f"  梯度累积: {config.training.gradient_accumulation_steps}")
    logger.info(f"  有效批次: {config.effective_batch_size}")
    logger.info(f"  训练轮数: {config.training.num_epochs}")
    logger.info(f"  最大长度: {config.optimization.max_length}")
    logger.info(f"  混合精度: {config.optimization.mixed_precision}")

    # 验证数据文件
    logger.info("\n[数据信息]")
    for key, path in data_paths.items():
        if os.path.exists(path):
            count = count_samples(path)
            logger.info(f"  {key}: {path}")
            logger.info(f"    样本数: {count}")
        else:
            logger.error(f"  {key}: {path} [不存在]")

    # 验证输出目录
    logger.info("\n[输出目录]")
    for key, path in output_dirs.items():
        logger.info(f"  {key}: {path}")

    # 验证模型路径
    logger.info("\n[模型信息]")
    model_path = config.model.path
    if os.path.exists(model_path):
        logger.info(f"  模型路径存在: {model_path}")
        # 检查关键文件
        required_files = ["config.json", "tokenizer.json", "tokenizer_config.json"]
        for f in required_files:
            file_path = os.path.join(model_path, f)
            if os.path.exists(file_path):
                logger.info(f"    {f}: OK")
            else:
                logger.warning(f"    {f}: 缺失")
    else:
        logger.error(f"  模型路径不存在: {model_path}")

    logger.info("\n" + "=" * 60)
    logger.info("DRY-RUN 验证完成")
    logger.info("=" * 60)


def save_training_config(config: Config, output_dirs: dict, args):
    """
    保存训练配置

    Args:
        config: 配置对象
        output_dirs: 输出目录
        args: 命令行参数
    """
    config_save_path = os.path.join(output_dirs["base"], "training_config.json")

    config_dict = {
        "experiment": {
            "name": config.experiment.name,
            "type": config.experiment.type,
            "seed": config.experiment.seed,
        },
        "model": {
            "name": config.model.name,
            "path": config.model.path,
            "use_lora": config.model.use_lora,
            "lora": {
                "r": config.model.lora.r,
                "alpha": config.model.lora.alpha,
                "dropout": config.model.lora.dropout,
                "target_modules": config.model.lora.target_modules,
            }
        },
        "training": {
            "learning_rate": config.training.learning_rate,
            "batch_size": config.training.batch_size,
            "gradient_accumulation_steps": config.training.gradient_accumulation_steps,
            "num_epochs": config.training.num_epochs,
            "warmup_ratio": config.training.warmup_ratio,
            "weight_decay": config.training.weight_decay,
            "max_grad_norm": config.training.max_grad_norm,
            "lr_scheduler_type": config.training.lr_scheduler_type,
        },
        "optimization": {
            "max_length": config.optimization.max_length,
            "gradient_checkpointing": config.optimization.gradient_checkpointing,
            "mixed_precision": config.optimization.mixed_precision,
        },
        "data": {
            "train_file": config.data.train_file,
            "dev_file": config.data.dev_file,
        },
        "runtime": {
            "dataset": args.dataset,
            "dry_run": args.dry_run,
            "resume": args.resume,
            "timestamp": datetime.now().isoformat(),
        }
    }

    with open(config_save_path, 'w', encoding='utf-8') as f:
        json.dump(config_dict, f, ensure_ascii=False, indent=2)

    logger.info(f"训练配置已保存: {config_save_path}")


def run_training(config: Config, data_paths: dict, output_dirs: dict, args):
    """
    执行训练

    Args:
        config: 配置对象
        data_paths: 数据路径
        output_dirs: 输出目录
        args: 命令行参数
    """
    logger.info("=" * 60)
    logger.info("开始训练")
    logger.info("=" * 60)

    if not MODULES_AVAILABLE:
        logger.error(f"必需模块未安装: {IMPORT_ERROR}")
        logger.error("请先创建 data_processor.py, trainer.py 和 utils.py")
        raise ImportError(f"必需模块未安装: {IMPORT_ERROR}")

    # [1/4] 初始化训练器（会加载模型和tokenizer）
    logger.info("\n[1/4] 初始化训练器...")
    trainer = GeoSRSFTTrainer(
        model_path=config.model.path,
        config=config,
    )
    trainer.setup_model_and_tokenizer()

    # [2/4] 加载数据 (使用 HF Dataset 格式)
    logger.info("\n[2/4] 加载数据...")

    # 获取数据目录和版本
    data_dir = str(GEOKD_ROOT / "data")
    data_version = args.dataset  # "splits" 或 "split_coords"

    # 使用新的静态方法创建 HF Dataset
    train_dataset = GeoSRDataProcessor.create_hf_dataset(
        data_path=data_dir,
        tokenizer=trainer.tokenizer,
        max_length=config.optimization.max_length,
        system_prompt=config.data.system_prompt,
        data_version=data_version,
        split="train"
    )

    dev_dataset = GeoSRDataProcessor.create_hf_dataset(
        data_path=data_dir,
        tokenizer=trainer.tokenizer,
        max_length=config.optimization.max_length,
        system_prompt=config.data.system_prompt,
        data_version=data_version,
        split="dev"
    )

    logger.info(f"  训练样本数: {len(train_dataset)}")
    logger.info(f"  验证样本数: {len(dev_dataset)}")
    logger.info(f"  数据集列: {train_dataset.column_names}")

    # [3/4] 设置 LoRA
    logger.info("\n[3/4] 设置 LoRA...")
    if config.model.use_lora:
        trainer.setup_lora()
        logger.info("LoRA 配置完成")

    # [4/4] 开始训练
    logger.info("\n[4/4] 开始训练...")
    try:
        result = trainer.train(
            train_dataset=train_dataset,
            eval_dataset=dev_dataset,
            output_dir=output_dirs["base"]
        )

        logger.info(f"\n训练结果: {result}")
        logger.info("\n" + "=" * 60)
        logger.info("训练完成")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"训练过程中发生错误: {e}")
        raise


def main():
    """主函数"""
    # 解析参数
    args = parse_args()

    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("GeoSR SFT 训练脚本")
    logger.info("=" * 60)

    # 验证配置文件
    config_path = resolve_path(args.config)
    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)

    logger.info(f"配置文件: {config_path}")
    logger.info(f"数据集: {args.dataset}")
    logger.info(f"工作目录: {os.getcwd()}")
    logger.info(f"项目根目录: {GEOKD_ROOT}")

    # 加载配置
    logger.info("\n加载配置...")
    config = load_config(config_path)

    # 设置环境
    logger.info("\n设置环境...")
    device_info = setup_environment(config, args)

    # 获取数据路径
    config_dir = os.path.dirname(config_path)
    data_paths = get_data_paths(config, args.dataset, config_dir)

    # 验证数据
    logger.info("\n验证数据...")
    if not validate_data(data_paths):
        logger.error("数据验证失败")
        sys.exit(1)

    logger.info("数据验证通过")

    # 创建输出目录
    logger.info("\n创建输出目录...")
    output_dirs = create_output_dirs(config, args)

    # 保存训练配置
    save_training_config(config, output_dirs, args)

    # Dry-run 模式
    if args.dry_run:
        dry_run_validation(config, data_paths, output_dirs)
        return

    # 执行训练
    run_training(config, data_paths, output_dirs, args)


if __name__ == "__main__":
    main()
