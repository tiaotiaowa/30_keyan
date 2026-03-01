"""
测试下载流程 - 验证环境和连接
不实际下载大文件，只测试网络连接和配置
"""

import os
import sys
import requests
from pathlib import Path

# 设置输出编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def test_environment():
    """测试Python环境"""
    print("测试Python环境...")

    # Python版本
    print(f"✓ Python版本: {sys.version.split()[0]}")

    # 检查依赖
    try:
        import torch
        print(f"✓ PyTorch版本: {torch.__version__}")
        print(f"✓ CUDA可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  GPU数量: {torch.cuda.device_count()}")
            print(f"  GPU名称: {torch.cuda.get_device_name(0)}")
    except ImportError:
        print("✗ PyTorch未安装")
        return False

    try:
        import transformers
        print(f"✓ Transformers版本: {transformers.__version__}")
    except ImportError:
        print("✗ Transformers未安装")
        return False

    try:
        import huggingface_hub
        print(f"✓ HuggingFace Hub版本: {huggingface_hub.__version__}")
    except ImportError:
        print("✗ HuggingFace Hub未安装")
        return False

    return True


def test_network_connection():
    """测试网络连接"""
    print("\n测试网络连接...")

    hf_endpoint = os.environ.get('HF_ENDPOINT', 'https://huggingface.co')
    print(f"使用端点: {hf_endpoint}")

    # 测试连接
    try:
        response = requests.get(f"{hf_endpoint}/", timeout=10)
        if response.status_code == 200:
            print(f"✓ 可以连接到 {hf_endpoint}")
        else:
            print(f"✗ 连接失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return False

    # 测试模型仓库访问
    try:
        response = requests.get(
            f"{hf_endpoint}/Qwen/Qwen2.5-1.5B-Instruct",
            timeout=10
        )
        if response.status_code == 200:
            print(f"✓ 可以访问Qwen模型仓库")
        else:
            print(f"✗ 无法访问模型仓库，状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 访问模型仓库失败: {e}")
        return False

    return True


def test_disk_space():
    """测试磁盘空间"""
    print("\n测试磁盘空间...")

    try:
        import shutil
        models_dir = Path(__file__).parent.parent / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        stat = shutil.disk_usage(models_dir)
        free_gb = stat.free / (1024**3)

        print(f"可用空间: {free_gb:.2f} GB")

        # 需要至少20GB（两个模型）
        required = 20
        if free_gb >= required:
            print(f"✓ 磁盘空间足够（需要至少{required}GB）")
            return True
        else:
            print(f"✗ 磁盘空间不足（需要至少{required}GB）")
            print("  建议：先下载1.5B模型（需要约3GB）")
            return False
    except Exception as e:
        print(f"✗ 无法检查磁盘空间: {e}")
        return True  # 如果无法检查，默认通过


def test_directory_structure():
    """测试目录结构"""
    print("\n测试目录结构...")

    base_dir = Path(__file__).parent.parent
    models_dir = base_dir / "models"

    print(f"项目根目录: {base_dir}")
    print(f"模型目录: {models_dir}")

    if not models_dir.exists():
        models_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ 已创建模型目录")

    print(f"✓ 目录结构正确")
    return True


def main():
    print("="*60)
    print("  Qwen2.5 模型下载环境测试")
    print("="*60)
    print()

    results = []

    # 运行所有测试
    results.append(("环境测试", test_environment()))
    results.append(("网络连接", test_network_connection()))
    results.append(("磁盘空间", test_disk_space()))
    results.append(("目录结构", test_directory_structure()))

    # 汇总结果
    print("\n" + "="*60)
    print("  测试结果汇总")
    print("="*60)

    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print()

    if all_passed:
        print("✓ 所有测试通过！可以开始下载模型。")
        print("\n运行以下命令开始下载:")
        print("  python scripts/download_models.py")
        print("\n或使用镜像加速:")
        print("  export HF_ENDPOINT=https://hf-mirror.com")
        print("  python scripts/download_models.py")
        return 0
    else:
        print("✗ 部分测试失败，请解决上述问题后再下载。")
        return 1


if __name__ == "__main__":
    exit(main())
