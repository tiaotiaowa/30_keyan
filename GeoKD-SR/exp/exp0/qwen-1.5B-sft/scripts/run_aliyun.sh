#!/bin/bash
# Qwen2.5-1.5B SFT Training Script for Aliyun 24GB
# Usage: bash run_aliyun.sh [splits|split_coords] [seed]

set -e  # Exit on error

# 默认参数
DATASET="${1:-splits}"
SEED="${2:-42}"

echo "========================================"
echo "Qwen2.5-1.5B SFT Training (Aliyun 24GB)"
echo "========================================"
echo "Dataset: $DATASET"
echo "Seed: $SEED"
echo "========================================"

# 设置项目根目录
PROJECT_ROOT="/mnt/data/GeoKD-SR"
cd "$PROJECT_ROOT/exp/exp0/qwen-1.5B-sft"

# 检查 Python 环境
if ! command -v python &> /dev/null; then
    echo "Error: Python not found. Please install Python 3.9+"
    exit 1
fi

# 检查 GPU
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU count: {torch.cuda.device_count()}'); [print(f'GPU {i}: {torch.cuda.get_device_name(i)}') for i in range(torch.cuda.device_count())]" 2>/dev/null || true

# 运行训练
echo ""
echo "Starting training..."
python scripts/train.py \
    --config configs/train_24gb.yaml \
    --dataset "$DATASET" \
    --seed "$SEED"

echo ""
echo "========================================"
echo "Training completed successfully!"
echo "========================================"

# 运行评测（可选）
if [ "$3" == "--eval" ]; then
    echo ""
    echo "Running evaluation..."
    python scripts/evaluate.py \
        --checkpoint "outputs/$DATASET/seed_$SEED/checkpoint-final" \
        --test-file "data/$DATASET/test.jsonl" \
        --output "outputs/$DATASET/seed_$SEED"
fi
