"""
自动下载Qwen模型
使用HuggingFace技术栈
"""
import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download
import shutil


# 配置
MODELS = {
    "qwen-1.5b": {
        "repo_id": "Qwen/Qwen2.5-1.5B-Instruct",
        "name": "Qwen2.5-1.5B-Instruct",
        "size_gb": 3
    },
    "qwen-7b": {
        "repo_id": "Qwen/Qwen2.5-7B-Instruct",
        "name": "Qwen2.5-7B-Instruct",
        "size_gb": 14
    }
}

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"


def check_disk_space(required_gb):
    """检查磁盘空间"""
    stat = shutil.disk_usage(MODELS_DIR)
    free_gb = stat.free / (1024**3)
    print(f"可用磁盘空间: {free_gb:.1f} GB")
    return free_gb >= required_gb * 1.2


def download_model(model_key):
    """下载单个模型"""
    config = MODELS[model_key]
    repo_id = config["repo_id"]
    model_name = config["name"]
    size_gb = config["size_gb"]

    model_path = MODELS_DIR / model_name

    print(f"\n{'='*70}")
    print(f"下载模型: {model_name}")
    print(f"{'='*70}")
    print(f"仓库ID: {repo_id}")
    print(f"预期大小: {size_gb} GB")

    # 检查是否已存在
    if model_path.exists():
        config_file = model_path / "config.json"
        if config_file.exists():
            print(f"[OK] 模型已存在且完整")
            return str(model_path)
        else:
            print(f"[WARN] 模型目录存在但不完整，重新下载")

    # 检查磁盘空间
    if not check_disk_space(size_gb):
        print(f"[ERROR] 磁盘空间不足")
        return None

    # 检查镜像设置
    hf_endpoint = os.environ.get('HF_ENDPOINT', 'https://huggingface.co')
    print(f"下载源: {hf_endpoint}")

    if hf_endpoint != 'https://huggingface.co':
        print(f"[INFO] 使用镜像加速")

    try:
        # 下载模型
        print(f"\n[DOWNLOAD] 开始下载...")
        print(f"[INFO] 这可能需要几分钟到几十分钟，取决于网速")

        download_path = snapshot_download(
            repo_id=repo_id,
            local_dir=str(model_path),
            local_dir_use_symlinks=False,
            resume_download=True,
            endpoint=hf_endpoint if hf_endpoint != 'https://huggingface.co' else None
        )

        # 计算实际大小
        total_size = sum(
            f.stat().st_size
            for f in model_path.rglob('*')
            if f.is_file()
        ) / (1024**3)

        print(f"\n[OK] {model_name} 下载完成!")
        print(f"     保存位置: {download_path}")
        print(f"     实际大小: {total_size:.2f} GB")

        return download_path

    except Exception as e:
        print(f"\n[ERROR] 下载失败: {e}")
        print("\n建议:")
        print("1. 检查网络连接")
        print("2. 设置镜像加速:")
        print("   set HF_ENDPOINT=https://hf-mirror.com")
        print("3. 重试下载")
        return None


def main():
    """主函数"""
    print("="*70)
    print("GeoKD-SR - Qwen模型自动下载工具")
    print("="*70)

    # 创建目录
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 下载1.5B模型（先下载小的）
    print("\n[1/2] 下载Qwen2.5-1.5B-Instruct (学生模型)")
    path_1_5b = download_model("qwen-1.5b")

    if not path_1_5b:
        print("\n[ERROR] 1.5B模型下载失败")
        return

    # 询问是否继续下载7B模型
    print(f"\n{'='*70}")
    print("1.5B模型下载完成！")
    print(f"{'='*70}")

    choice = input("\n是否继续下载7B模型 (教师模型, ~14GB)? (y/N): ").strip().lower()

    if choice == 'y' or choice == 'yes':
        print("\n[2/2] 下载Qwen2.5-7B-Instruct (教师模型)")
        path_7b = download_model("qwen-7b")

        if path_7b:
            print(f"\n{'='*70}")
            print("✅ 所有模型下载完成!")
            print(f"{'='*70}")
            print(f"\n1.5B模型: {path_1_5b}")
            print(f"7B模型:   {path_7b}")
    else:
        print("\n跳过7B模型下载")

    print(f"\n{'='*70}")
    print("下载任务完成!")
    print(f"{'='*70}\n")

    print("下一步:")
    print("1. 运行示例: python examples/hf_quickstart.py")
    print("2. 开始训练: python scripts/train_baseline.py")
    print("3. 查看文档: docs/HUGGINGFACE_GUIDE.md")


if __name__ == "__main__":
    main()
