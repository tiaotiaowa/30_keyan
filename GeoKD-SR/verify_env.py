#!/usr/bin/env python3
"""
GeoKD-SR 环境验证脚本
检查所有必需依赖是否正确安装
"""

import sys

def check_python():
    """检查Python版本"""
    version = sys.version_info
    print(f"  版本: {sys.version.split()[0]}")
    if version.major == 3 and version.minor >= 8:
        print("  ✓ Python版本满足要求 (>=3.8)")
        return True
    else:
        print("  ✗ Python版本过低，需要 >=3.8")
        return False

def check_torch():
    """检查PyTorch和CUDA"""
    try:
        import torch
        print(f"  PyTorch版本: {torch.__version__}")
        print(f"  CUDA可用: {torch.cuda.is_available()}")

        if torch.cuda.is_available():
            print(f"  CUDA版本: {torch.version.cuda}")
            print(f"  cuDNN版本: {torch.backends.cudnn.version()}")
            print(f"  GPU数量: {torch.cuda.device_count()}")

            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"  GPU {i}: {props.name}")
                print(f"    显存: {props.total_memory / 1e9:.1f} GB")
                print(f"    计算能力: {props.major}.{props.minor}")

            # 测试GPU运算
            try:
                x = torch.randn(1000, 1000, device='cuda')
                y = torch.matmul(x, x)
                print("  ✓ GPU运算测试通过")
            except Exception as e:
                print(f"  ✗ GPU运算测试失败: {e}")
                return False
        else:
            print("  ⚠ CUDA不可用，将使用CPU训练")
        return True
    except ImportError:
        print("  ✗ PyTorch未安装")
        return False

def check_transformers():
    """检查Transformers"""
    try:
        import transformers
        print(f"  版本: {transformers.__version__}")

        if transformers.__version__ >= '4.37.0':
            print("  ✓ Transformers版本满足要求")
            return True
        else:
            print("  ⚠ Transformers版本较低，建议升级到 >=4.37.0")
            return True
    except ImportError:
        print("  ✗ Transformers未安装")
        return False

def check_all_dependencies():
    """检查所有依赖包"""
    packages = {
        # 核心依赖
        "transformers": "核心-模型",
        "huggingface_hub": "核心-Hub",
        "accelerate": "核心-加速",
        "safetensors": "核心-安全张量",
        "tqdm": "核心-进度条",

        # 训练依赖
        "peft": "训练-LoRA",
        "datasets": "训练-数据集",
        "bitsandbytes": "训练-量化",

        # 数据处理
        "pandas": "数据-处理",
        "scipy": "数据-科学计算",
        "sklearn": "数据-机器学习",

        # 空间计算
        "shapely": "空间-几何",
        "geopy": "空间-地理",

        # 可视化
        "matplotlib": "可视化-绘图",
        "seaborn": "可视化-统计图",

        # 实验跟踪
        "wandb": "实验-跟踪",
    }

    all_ok = True
    missing = []

    print("\n  包名                    类别          状态")
    print("  " + "-" * 50)

    for pkg, category in packages.items():
        try:
            mod = __import__(pkg)
            version = getattr(mod, '__version__', 'unknown')
            print(f"  {pkg:<20} {category:<12} ✓ v{version}")
        except ImportError:
            print(f"  {pkg:<20} {category:<12} ✗ 未安装")
            missing.append(pkg)
            all_ok = False

    if missing:
        print(f"\n  ⚠ 缺少 {len(missing)} 个包: {', '.join(missing)}")
        print("  运行: pip install " + " ".join(missing))

    return all_ok

def check_model_loading():
    """测试模型加载（可选）"""
    try:
        from transformers import AutoTokenizer
        print("\n  测试Tokenizer加载...")

        # 使用HF镜像
        import os
        os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')

        tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen2.5-1.5B-Instruct",
            trust_remote_code=True
        )
        print("  ✓ Tokenizer加载成功")
        return True
    except Exception as e:
        print(f"  ⚠ Tokenizer加载测试跳过: {e}")
        return True  # 不阻止环境验证

def main():
    print("=" * 60)
    print("GeoKD-SR 环境验证")
    print("=" * 60)

    # 设置HF镜像
    import os
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

    checks = [
        ("Python环境", check_python),
        ("PyTorch & CUDA", check_torch),
        ("Transformers", check_transformers),
        ("依赖包检查", check_all_dependencies),
        ("模型加载测试", check_model_loading),
    ]

    failed = []

    for name, func in checks:
        print(f"\n[{name}]")
        if not func():
            failed.append(name)

    print("\n" + "=" * 60)
    if failed:
        print(f"❌ 环境验证未通过，失败项: {', '.join(failed)}")
        print("请运行: bash setup_pai_env.sh")
        return 1
    else:
        print("✅ 环境验证通过！可以开始训练。")
        print("=" * 60)
        return 0

if __name__ == "__main__":
    sys.exit(main())
