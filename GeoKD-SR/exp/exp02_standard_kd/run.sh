#!/bin/bash
set -e

echo "=========================================="
echo "  Exp02: Standard-KD（标准知识蒸馏基线）"
echo "=========================================="
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 配置
SEED=${1:-42}
CHECKPOINT_DIR="checkpoints"
OUTPUT_DIR="outputs"
RESULT_DIR="results"

# Step 1: 训练
echo "[1/3] 开始蒸馏训练 (seed=${SEED})..."
python train.py --config config.yaml --seed ${SEED}
echo "训练完成: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Step 2: 生成预测
echo "[2/3] 生成预测结果..."
python stage1_generate.py --config stage1_config.yaml \
    --checkpoint ${CHECKPOINT_DIR}/final_model
echo "生成完成: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Step 3: 评测
echo "[3/3] 评测..."
python stage2_evaluate.py \
    --predictions ${OUTPUT_DIR}/predictions.jsonl \
    --output ${RESULT_DIR}/
echo ""

echo "=========================================="
echo "  全部完成！"
echo "  训练checkpoint: ${CHECKPOINT_DIR}/"
echo "  预测结果: ${OUTPUT_DIR}/predictions.jsonl"
echo "  评测报告: ${RESULT_DIR}/report.md"
echo "  完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
