"""
工具模块 - GeoKD-SR 实验
提供随机种子设置、日志配置、设备信息获取等通用工具函数
"""

import os
import random
import logging
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional

import numpy as np
import torch


def setup_seed(seed: int = 42) -> None:
    """
    设置随机种子以确保实验可复现性

    Args:
        seed: 随机种子值，默认为42
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    # 设置 cudnn 的确定性模式（可能会影响性能）
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    # 设置 Python hash seed
    os.environ['PYTHONHASHSEED'] = str(seed)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    配置日志系统

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径，如果为 None 则只输出到控制台
        log_format: 自定义日志格式

    Returns:
        配置好的 logger 对象
    """
    # 日志级别映射
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    level = level_map.get(log_level.upper(), logging.INFO)

    # 默认日志格式
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 配置根日志记录器
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger = logging.getLogger("GeoKD-SR")

    # 如果指定了日志文件，添加文件处理器
    if log_file is not None:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(file_handler)

    return logger


def get_device_info() -> Dict[str, Any]:
    """
    获取设备信息（CPU/GPU）

    Returns:
        包含设备信息的字典
    """
    info = {
        "cpu_count": os.cpu_count(),
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "pytorch_version": torch.__version__,
        "gpu_count": 0,
        "gpus": []
    }

    if torch.cuda.is_available():
        info["gpu_count"] = torch.cuda.device_count()

        for i in range(info["gpu_count"]):
            gpu_info = {
                "index": i,
                "name": torch.cuda.get_device_name(i),
                "total_memory_gb": round(
                    torch.cuda.get_device_properties(i).total_memory / (1024**3), 2
                ),
                "compute_capability": torch.cuda.get_device_properties(i).major,
                "multi_processor_count": torch.cuda.get_device_properties(i).multi_processor_count
            }
            info["gpus"].append(gpu_info)

    return info


def format_time(seconds: float) -> str:
    """
    将秒数格式化为易读的时间字符串

    Args:
        seconds: 秒数

    Returns:
        格式化的时间字符串，如 "1h 23m 45s" 或 "45.23s"
    """
    if seconds < 0:
        return "0s"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")

    # 如果小于1分钟，显示更精确的秒数
    if hours == 0 and minutes == 0:
        parts.append(f"{secs:.2f}s")
    else:
        parts.append(f"{int(secs)}s")

    return " ".join(parts)


def count_parameters(model: torch.nn.Module, trainable_only: bool = False) -> Dict[str, int]:
    """
    计算模型参数量

    Args:
        model: PyTorch 模型
        trainable_only: 是否只计算可训练参数

    Returns:
        包含参数量信息的字典
    """
    total_params = sum(p.numel() for p in model.parameters())

    if trainable_only:
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        return {
            "total": total_params,
            "trainable": trainable_params,
            "frozen": total_params - trainable_params,
            "trainable_ratio": round(trainable_params / total_params * 100, 2) if total_params > 0 else 0
        }

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    return {
        "total": total_params,
        "total_m": round(total_params / 1e6, 2),  # 以百万为单位
        "total_b": round(total_params / 1e9, 4),  # 以十亿为单位
        "trainable": trainable_params,
        "trainable_m": round(trainable_params / 1e6, 2),
        "frozen": total_params - trainable_params,
        "trainable_ratio": round(trainable_params / total_params * 100, 2) if total_params > 0 else 0
    }


def get_gpu_memory_usage(device: Optional[int] = None) -> Dict[str, Any]:
    """
    获取 GPU 显存使用情况

    Args:
        device: GPU 设备索引，如果为 None 则返回所有 GPU 的信息

    Returns:
        包含显存使用信息的字典
    """
    if not torch.cuda.is_available():
        return {"error": "CUDA is not available"}

    result = {}

    if device is not None:
        devices = [device]
    else:
        devices = range(torch.cuda.device_count())

    for dev_idx in devices:
        try:
            allocated = torch.cuda.memory_allocated(dev_idx)
            reserved = torch.cuda.memory_reserved(dev_idx)
            total = torch.cuda.get_device_properties(dev_idx).total_memory
            free = total - reserved

            result[f"gpu_{dev_idx}"] = {
                "device_name": torch.cuda.get_device_name(dev_idx),
                "allocated_mb": round(allocated / (1024**2), 2),
                "reserved_mb": round(reserved / (1024**2), 2),
                "total_mb": round(total / (1024**2), 2),
                "free_mb": round(free / (1024**2), 2),
                "utilization_percent": round(allocated / total * 100, 2) if total > 0 else 0
            }
        except Exception as e:
            result[f"gpu_{dev_idx}"] = {"error": str(e)}

    return result


def save_training_config(
    config: Dict[str, Any],
    output_path: str,
    include_timestamp: bool = True
) -> str:
    """
    保存训练配置到 JSON 文件

    Args:
        config: 配置字典
        output_path: 输出文件路径
        include_timestamp: 是否在配置中包含时间戳

    Returns:
        实际保存的文件路径
    """
    # 复制配置以避免修改原始对象
    config_to_save = config.copy()

    # 添加时间戳
    if include_timestamp:
        config_to_save["_metadata"] = {
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time()
        }

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 保存配置
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config_to_save, f, indent=2, ensure_ascii=False)

    return output_path


def get_model_size_mb(model: torch.nn.Module) -> float:
    """
    获取模型大小（以 MB 为单位）

    Args:
        model: PyTorch 模型

    Returns:
        模型大小（MB）
    """
    param_size = 0
    for param in model.parameters():
        param_size += param.nelement() * param.element_size()

    buffer_size = 0
    for buffer in model.buffers():
        buffer_size += buffer.nelement() * buffer.element_size()

    total_size = param_size + buffer_size
    return round(total_size / (1024**2), 2)


def print_model_summary(model: torch.nn.Module, model_name: str = "Model") -> None:
    """
    打印模型摘要信息

    Args:
        model: PyTorch 模型
        model_name: 模型名称
    """
    params = count_parameters(model)
    size_mb = get_model_size_mb(model)

    print(f"\n{'='*50}")
    print(f" {model_name} Summary")
    print(f"{'='*50}")
    print(f" Total Parameters:     {params['total']:,}")
    print(f" Total Parameters (M): {params['total_m']} M")
    print(f" Trainable Parameters: {params['trainable']:,}")
    print(f" Frozen Parameters:    {params['frozen']:,}")
    print(f" Trainable Ratio:      {params['trainable_ratio']}%")
    print(f" Model Size:           {size_mb} MB")
    print(f"{'='*50}\n")


class AverageMeter:
    """
    计算并存储平均值和当前值
    用于跟踪训练过程中的指标
    """

    def __init__(self, name: str = ""):
        self.name = name
        self.reset()

    def reset(self) -> None:
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val: float, n: int = 1) -> None:
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count if self.count > 0 else 0

    def __str__(self) -> str:
        return f"{self.name}: {self.avg:.4f}"


class Timer:
    """
    计时器类，用于测量代码执行时间
    """

    def __init__(self, name: str = ""):
        self.name = name
        self.start_time = None
        self.elapsed = 0

    def start(self) -> "Timer":
        self.start_time = time.time()
        return self

    def stop(self) -> float:
        if self.start_time is not None:
            self.elapsed = time.time() - self.start_time
        return self.elapsed

    def __enter__(self) -> "Timer":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()
        if self.name:
            print(f"{self.name}: {format_time(self.elapsed)}")


# 便捷函数
def clear_cuda_cache() -> None:
    """清空 CUDA 缓存"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def set_grad_enabled(enabled: bool) -> None:
    """
    启用或禁用梯度计算

    Args:
        enabled: 是否启用梯度
    """
    torch.set_grad_enabled(enabled)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print(" GeoKD-SR Utils Module Test")
    print("=" * 60)

    # 测试设备信息
    print("\n[Device Info]")
    device_info = get_device_info()
    for key, value in device_info.items():
        if key != "gpus":
            print(f"  {key}: {value}")
        else:
            for gpu in value:
                print(f"  GPU {gpu['index']}: {gpu['name']} ({gpu['total_memory_gb']} GB)")

    # 测试显存使用
    print("\n[GPU Memory Usage]")
    memory_info = get_gpu_memory_usage()
    for key, value in memory_info.items():
        print(f"  {key}: {value}")

    # 测试时间格式化
    print("\n[Time Format Test]")
    test_times = [0.5, 30, 90, 3661, 7325]
    for t in test_times:
        print(f"  {t}s -> {format_time(t)}")

    # 测试随机种子
    print("\n[Random Seed Test]")
    setup_seed(42)
    print(f"  Random int: {random.randint(0, 100)}")
    print(f"  Numpy random: {np.random.rand(3)}")

    print("\n" + "=" * 60)
    print(" All tests passed!")
    print("=" * 60)
