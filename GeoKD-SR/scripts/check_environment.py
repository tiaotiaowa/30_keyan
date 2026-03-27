#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境检查脚本

检查 GPU、依赖、模型路径等是否正确配置
用于在 PAI 平台上运行实验前验证环境
"""

import os
import sys
import subprocess
from pathlib import Path


def check_gpu():
    """检查GPU可用性"""
    print("\n" + "=" * 60)
    print("GPU 检查")
    print("=" * 60)

    try:
        import torch
        print(f"PyTorch 版本: {torch.__version__}")
        print(f"CUDA 可用: {torch.cuda.is_available()}")

        if torch.cuda.is_available():
            print(f"CUDA 版本: {torch.version.cuda}")
            print(f"GPU 数量: {torch.cuda.device_count()}")

            for i in range(torch.cuda.device_count()):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                print(f"  GPU {i}: {gpu_name} ({gpu_memory:.1f} GB)")

                # 检查显存是否足够
                if gpu_memory < 20:
                    print(f"  ⚠️  警告: GPU {i} 显存可能不足 (建议 >= 24GB)")

            return True
        else:
            print("❌ CUDA 不可用，请检查 GPU 驱动")
            return False

    except ImportError:
        print("❌ PyTorch 未安装")
        return False


def check_dependencies():
    """检查必要的依赖"""
    print("\n" + "=" * 60)
    print("依赖检查")
    print("=" * 60)

    required_packages = {
        "torch": "PyTorch",
        "transformers": "Transformers",
        "peft": "PEFT",
        "datasets": "Datasets",
        "accelerate": "Accelerate",
        "bitsandbytes": "BitsAndBytes (4-bit量化)",
        "numpy": "NumPy",
        "yaml": "PyYAML",
        "tqdm": "tqdm",
    }

    all_ok = True
    for package, name in required_packages.items():
        try:
            if package == "yaml":
                import yaml
                version = getattr(yaml, "__version__", "unknown")
            elif package == "bitsandbytes":
                import bitsandbytes
                version = getattr(bitsandbytes, "__version__", "unknown")
            else:
                module = __import__(package)
                version = getattr(module, "__version__", "unknown")

            print(f"✓ {name}: {version}")

        except ImportError:
            print(f"❌ {name}: 未安装")
            all_ok = False

    return all_ok


def check_model_paths():
    """检查模型路径"""
    print("\n" + "=" * 60)
    print("模型路径检查")
    print("=" * 60)

    # 检查可能的模型路径
    possible_paths = [
        "/mnt/workspace/models/Qwen2.5-1.5B-Instruct",
        "/mnt/workspace/models/Qwen2.5-7B-Instruct",
        "Qwen/Qwen2.5-1.5B-Instruct",  # HuggingFace 路径
        "Qwen/Qwen2.5-7B-Instruct",
    ]

    results = {}
    for path in possible_paths:
        if path.startswith("/mnt") or path.startswith("/"):
            # 本地路径
            exists = Path(path).exists()
            status = "✓" if exists else "❌"
            print(f"{status} {path}: {'存在' if exists else '不存在'}")

            if exists:
                # 检查关键文件
                required_files = ["config.json", "model.safetensors.index.json", "tokenizer.json"]
                for f in required_files:
                    file_path = Path(path) / f
                    if file_path.exists():
                        print(f"    ✓ {f}")
                    else:
                        print(f"    ⚠️  {f} 不存在")
        else:
            # HuggingFace 路径
            print(f"ℹ️  {path}: HuggingFace 路径 (需要联网下载)")

        results[path] = Path(path).exists() if not path.startswith("Qwen") else None

    return results


def check_data_paths():
    """检查数据路径"""
    print("\n" + "=" * 60)
    print("数据路径检查")
    print("=" * 60)

    # 相对于 exp 目录
    base_dir = Path(__file__).parent.parent
    data_paths = [
        base_dir / "data" / "geosr_chain" / "final" / "train.jsonl",
        base_dir / "data" / "geosr_chain" / "final" / "dev.jsonl",
        base_dir / "data" / "geosr_chain" / "final" / "test.jsonl",
    ]

    all_ok = True
    for path in data_paths:
        exists = path.exists()
        status = "✓" if exists else "❌"
        print(f"{status} {path}: {'存在' if exists else '不存在'}")

        if exists:
            # 统计数据行数
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = sum(1 for _ in f)
                print(f"    数据量: {lines} 条")
            except Exception as e:
                print(f"    ⚠️  无法读取: {e}")
                all_ok = False
        else:
            all_ok = False

    return all_ok


def check_memory_estimate():
    """估算显存使用"""
    print("\n" + "=" * 60)
    print("显存估算 (24GB A10)")
    print("=" * 60)

    estimates = {
        "教师模型 (7B, 4-bit)": "~4 GB",
        "学生模型 (1.5B, FP16)": "~3 GB",
        "梯度 + 优化器": "~4 GB",
        "激活值 (batch=2, grad_ckpt)": "~8 GB",
        "总计": "~19 GB",
    }

    print("Exp02 (Standard-KD) 显存估算:")
    for component, memory in estimates.items():
        print(f"  {component}: {memory}")

    print("\nExp01 (Direct-SFT) 显存估算:")
    print("  学生模型 (1.5B, FP16): ~3 GB")
    print("  梯度 + 优化器: ~4 GB")
    print("  激活值 (batch=4, grad_ckpt): ~6 GB")
    print("  总计: ~13 GB")

    print("\n✓ 24GB 显存足够运行实验")


def run_quick_test():
    """运行快速测试"""
    print("\n" + "=" * 60)
    print("快速功能测试")
    print("=" * 60)

    try:
        import torch
        from transformers import AutoTokenizer

        # 测试 tokenizer
        print("测试 tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen2.5-1.5B-Instruct",
            trust_remote_code=True,
        )

        # 测试 ChatML 格式
        messages = [
            {"role": "system", "content": "你是一个助手。"},
            {"role": "user", "content": "测试问题"},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        print(f"✓ ChatML 模板测试成功")
        print(f"  生成的文本长度: {len(text)} 字符")

        # 测试 GPU
        if torch.cuda.is_available():
            print("\n测试 GPU...")
            x = torch.randn(1000, 1000, device="cuda")
            y = torch.matmul(x, x)
            print(f"✓ GPU 计算测试成功")

        return True

    except Exception as e:
        print(f"❌ 快速测试失败: {e}")
        return False


def main():
    print("=" * 60)
    print("GeoKD-SR 实验环境检查")
    print("=" * 60)

    results = {
        "GPU": check_gpu(),
        "依赖": check_dependencies(),
        "模型路径": check_model_paths(),
        "数据路径": check_data_paths(),
    }

    check_memory_estimate()
    results["快速测试"] = run_quick_test()

    # 汇总
    print("\n" + "=" * 60)
    print("检查结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        if isinstance(passed, bool):
            status = "✓ 通过" if passed else "❌ 失败"
            print(f"{name}: {status}")
            if not passed:
                all_passed = False
        else:
            print(f"{name}: 见上方详情")

    if all_passed:
        print("\n✓ 所有检查通过，可以开始实验！")
    else:
        print("\n❌ 部分检查未通过，请先解决问题")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
