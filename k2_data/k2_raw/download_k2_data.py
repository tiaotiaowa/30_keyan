# -*- coding: utf-8 -*-
"""
K2数据集下载脚本
下载GeoSignal（训练数据）和GeoBench（评测数据）
"""

import os
import sys
from pathlib import Path

def main():
    # 设置数据目录
    script_dir = Path(__file__).resolve().parent
    os.makedirs(script_dir, exist_ok=True)

    print("=" * 60)
    print("K2数据集下载脚本")
    print("=" * 60)

    # 检查是否安装了datasets库
    try:
        from datasets import load_dataset, DatasetDict
    except ImportError:
        print("错误: 请先安装datasets库")
        print("  pip install datasets")
        sys.exit(1)

    # 1. 下载GeoSignal训练数据
    print("\n[1/2] 下载GeoSignal（训练数据）...")
    print("  HuggingFace: daven3/geosignal")

    try:
        geosignal = load_dataset("daven3/geosignal")
        print(f"  训练样本: {len(geosignal['train'])}条")

        # 保存到本地
        geosignal_path = script_dir / "geosignal"
        geosignal.save_to_disk(str(geosignal_path))
        print(f"  保存路径: {geosignal_path}")
        print("  GeoSignal下载完成!")

    except Exception as e:
        print(f"  下载GeoSignal失败: {e}")
        return False

    # 2. 下载GeoBench评测数据（有多个配置）
    print("\n[2/2] 下载GeoBench（评测数据）...")
    print("  HuggingFace: daven3/geobench")

    geobench_configs = ["npee", "ap"]  # 两种考试类型
    all_geobench = {}

    for config in geobench_configs:
        try:
            print(f"  下载配置: {config}")
            dataset = load_dataset("daven3/geobench", config)
            print(f"    {config}: {len(dataset['train'])}条")
            all_geobench[config] = dataset

            # 保存到本地
            config_path = script_dir / f"geobench_{config}"
            dataset.save_to_disk(str(config_path))
            print(f"    保存路径: {config_path}")

        except Exception as e:
            print(f"    下载 {config} 失败: {e}")
            # 尝试直接下载原始文件
            continue

    if all_geobench:
        print("  GeoBench下载完成!")
    else:
        print("  警告: GeoBench下载部分失败，尝试备用方法...")
        # 备用方法：直接下载原始JSON文件
        try:
            import requests
            from huggingface_hub import hf_hub_download

            # 下载原始文件
            files_to_download = [
                "geobenchmark_npee.json",
                "geobenchmark_ap.json"
            ]

            for filename in files_to_download:
                try:
                    file_path = hf_hub_download(
                        repo_id="daven3/geobench",
                        filename=filename,
                        repo_type="dataset",
                        local_dir=str(script_dir / "geobench_raw")
                    )
                    print(f"    下载: {filename} -> {file_path}")
                except Exception as e:
                    print(f"    下载 {filename} 失败: {e}")

        except Exception as e:
            print(f"  备用下载也失败: {e}")

    print("\n" + "=" * 60)
    print("所有数据集下载完成!")
    print("=" * 60)

    # 显示下载结果
    print("\n下载文件列表:")
    for item in script_dir.iterdir():
        if item.is_dir():
            print(f"  📁 {item.name}/")
        else:
            print(f"  📄 {item.name}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
