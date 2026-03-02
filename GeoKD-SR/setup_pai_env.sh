#!/bin/bash
# ===========================================
# GeoKD-SR 阿里云PAI环境配置脚本
# 最后更新: 2026年3月1日
# ===========================================

set -e  # 遇错即停

echo "=================================="
echo "GeoKD-SR 环境配置"
echo "=================================="

# 1. 设置HuggingFace镜像（国内加速）
export HF_ENDPOINT=https://hf-mirror.com
echo "✓ HuggingFace镜像已设置: $HF_ENDPOINT"

# 2. 升级pip
echo ""
echo "[1/8] 升级pip..."
pip install --upgrade pip -q

# 3. 安装核心依赖
echo ""
echo "[2/8] 安装核心依赖 (transformers, accelerate等)..."
pip install "transformers>=4.37.0" "huggingface-hub>=0.20.0" "accelerate>=0.25.0" "safetensors>=0.4.0" "tqdm>=4.66.0" -q

# 4. 安装训练依赖
echo ""
echo "[3/8] 安装训练依赖 (peft, datasets, bitsandbytes)..."
pip install peft datasets bitsandbytes -q

# 5. 安装数据处理
echo ""
echo "[4/8] 安装数据处理库 (pandas, scipy, scikit-learn)..."
pip install pandas scipy scikit-learn -q

# 6. 安装空间计算
echo ""
echo "[5/8] 安装空间计算库 (shapely, geopy, pyproj)..."
pip install shapely geopy pyproj -q

# 7. 安装可视化
echo ""
echo "[6/8] 安装可视化库 (matplotlib, seaborn)..."
pip install matplotlib seaborn -q

# 8. 安装实验跟踪
echo ""
echo "[7/8] 安装实验跟踪工具 (wandb, tensorboard)..."
pip install wandb tensorboard pyyaml -q

# 9. 安装其他工具
echo ""
echo "[8/8] 安装其他工具..."
pip install requests -q

echo ""
echo "=================================="
echo "✓ 环境配置完成！"
echo ""
echo "运行以下命令验证环境:"
echo "  python verify_env.py"
echo "=================================="
