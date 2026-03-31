# Qwen2.5-7B-Instruct 两阶段评测方案

本目录包含 Qwen2.5-7B-Instruct 模型的两阶段评测系统。

## 目录结构

```
qwen-7B/
├── stage1_generation/          # 第一阶段：答案生成
│   ├── config/
│   │   └── generation_config.yaml
│   ├── generate_answers.py     # 主生成脚本
│   ├── model_loader.py         # 模型加载工具
│   └── outputs/                # 生成的答案
│
├── stage2_evaluation/          # 第二阶段：评测计算
│   ├── config/
│   │   └── eval_config.yaml
│   ├── evaluate.py             # 主评测脚本
│   └── results/                # 评测结果
│       ├── splits/
│       └── split_coords/
│
└── README.md
```

## 环境要求

- Python 3.8+
- PyTorch 2.0+
- CUDA 11.x（GPU推理）
- 16GB+ 显存（7B 模型）

## 使用方法

### Stage 1: 答案生成

```bash
cd /mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/qwen-7B/stage1_generation

# 评测 splits 数据集
python generate_answers.py \
    --config config/generation_config.yaml \
    --input ../../data/splits/test.jsonl \
    --output ./outputs/splits_predictions.jsonl

# 评测 split_coords 数据集
python generate_answers.py \
    --config config/generation_config.yaml \
    --input ../../data/split_coords/test.jsonl \
    --output ./outputs/split_coords_predictions.jsonl
```

### Stage 2: 评测计算

```bash
cd /mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/qwen-7B/stage2_evaluation

# 评测 splits 预测结果
python evaluate.py \
    --predictions ../stage1_generation/outputs/splits_predictions.jsonl \
    --output ./results/splits

# 评测 split_coords 预测结果
python evaluate.py \
    --predictions ../stage1_generation/outputs/split_coords_predictions.jsonl \
    --output ./results/split_coords
```

## 评测指标

| 指标 | 说明 |
|------|------|
| Overall Accuracy | 整体准确率 |
| Directional Accuracy | 方向关系准确率 |
| Topological Accuracy | 拓扑关系准确率 |
| Metric Accuracy | 度量关系准确率 |
| Composite Accuracy | 组合推理准确率 |
| Format Valid Rate | 格式有效率 |
| BLEU-4 | 文本相似度 |
| ROUGE-L | 最长公共子序列 |
| Spatial F1 | 空间关键词 F1 |

## 输出文件

- **predictions.jsonl**: 模型预测结果
- **metrics.json**: 完整评测指标（JSON格式）
- **report.md**: 评测报告（Markdown格式）

## 与 1.5B 结果对比

评测完成后，可将结果与 `exp/exp0/exp0/stage2_evaluation/results/metrics.json` 中的 1.5B 结果进行对比。

## 注意事项

1. 7B 模型需要约 16GB 显存，请确保 GPU 资源充足
2. 生成过程可能需要较长时间，建议使用 nohup 后台运行
3. 如遇到显存不足，可在配置中调整 batch_size 或使用量化加载
