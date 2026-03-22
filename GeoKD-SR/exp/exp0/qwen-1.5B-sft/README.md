# Qwen2.5-1.5B SFT 微调训练系统

> **实验类型**: Exp1 Direct-SFT 基线
> **设计文档**: `docs/superpowers/specs/2026-03-21-qwen-1.5b-sft-design.md`

## 概述

本项目实现 Qwen2.5-1.5B-Instruct 的 LoRA 微调训练系统，用于 GeoKD-SR 项目的地理空间推理能力增强。

### 核心特性

- ✅ 支持 LoRA 高效微调
- ✅ 适配 6GB (Windows) 和 24GB (阿里云) 显存环境
- ✅ ChatML 格式数据处理
- ✅ 完整的评测指标体系
- ✅ Trackio 训练监控

## 目录结构

```
qwen-1.5B-sft/
├── configs/
│   ├── train_6gb.yaml      # Windows 6GB 配置
│   ├── train_24gb.yaml     # 阿里云 24GB 配置
│   └── eval.yaml           # 评测配置
├── scripts/
│   ├── train.py            # 主训练脚本
│   ├── evaluate.py         # 评测脚本
│   ├── run_windows.bat     # Windows 启动脚本
│   └── run_aliyun.sh       # 阿里云启动脚本
├── src/
│   ├── __init__.py
│   ├── config.py           # 配置加载
│   ├── data_processor.py   # 数据处理
│   ├── trainer.py          # 训练器
│   └── utils.py            # 工具函数
├── outputs/                # 训练输出
├── logs/                   # 训练日志
├── checkpoints/            # 模型检查点
└── README.md
```

## 环境配置

### 依赖安装

```bash
pip install torch transformers trl peft datasets accelerate trackio pyyaml
```

### 模型准备

将 Qwen2.5-1.5B-Instruct 模型下载到本地：

```bash
# Windows
models/Qwen2.5-1.5B-Instruct/

# 阿里云
/mnt/data/models/Qwen2.5-1.5B-Instruct/
```

### 数据准备

训练数据位于 `data/` 目录：
- `splits/` - 无坐标版本 (train/dev/test.jsonl)
- `split_coords/` - 有坐标版本 (train/dev/test.jsonl)

## 快速开始

### Windows 6GB 环境

```cmd
# 无坐标版本
scripts\run_windows.bat splits 42

# 有坐标版本
scripts\run_windows.bat split_coords 42

# 或直接使用 Python
python scripts/train.py --config configs/train_6gb.yaml --dataset splits --seed 42
```

### 阿里云 24GB 环境

```bash
# 无坐标版本
bash scripts/run_aliyun.sh splits 42

# 有坐标版本
bash scripts/run_aliyun.sh split_coords 42

# 带评测
bash scripts/run_aliyun.sh splits 42 --eval
```

## 配置说明

### 6GB 配置 (train_6gb.yaml)

| 参数 | 值 | 说明 |
|------|-----|------|
| batch_size | 1 | 受显存限制 |
| gradient_accumulation_steps | 128 | 有效批次=128 |
| max_length | 1024 | 降低显存占用 |
| mixed_precision | fp16 | 6GB不支持bf16 |
| LoRA r | 8 | LoRA秩 |
| LoRA alpha | 16 | LoRA缩放因子 |

### 24GB 配置 (train_24gb.yaml)

| 参数 | 值 | 说明 |
|------|-----|------|
| batch_size | 8 | 充足显存 |
| gradient_accumulation_steps | 16 | 有效批次=128 |
| max_length | 2048 | 完整上下文 |
| mixed_precision | bf16 | 更高精度 |
| LoRA r | 16 | 更大容量 |
| LoRA alpha | 32 | LoRA缩放因子 |

### 关键超参数

- **学习率**: 5e-5 (LoRA推荐值)
- **训练轮数**: 3
- **预热比例**: 0.1 (10%)
- **权重衰减**: 0.01
- **LR调度**: cosine (余弦退火)

## 评测

### 评测指标

| 指标 | 说明 |
|------|------|
| Overall Accuracy | 按空间类型分层的整体准确率 |
| Format Valid Rate | 输出格式有效率 |
| BLEU-4 | 文本相似度 |
| ROUGE-L | 最长公共子序列 |
| Spatial F1 | 空间关键词F1 |

### 运行评测

```bash
python scripts/evaluate.py \
    --checkpoint outputs/splits/seed_42/checkpoint-final \
    --test-file data/splits/test.jsonl \
    --output outputs/splits/seed_42
```

### 验收标准

| 指标 | 基线 | 目标 | 说明 |
|------|------|------|------|
| 总体准确率 | 23.16% | >30% | 提升30%+ |
| directional | 43.49% | >50% | 方向任务 |
| topological | 24.85% | >35% | 拓扑任务 |
| metric | 17.59% | >25% | 距离任务 |
| composite | 3.66% | >10% | 复合任务 |

## 实验矩阵

| 环境 | 数据集 | Seeds | 实验数 |
|------|--------|-------|--------|
| Windows 6GB | splits | 42 | 1 (验证) |
| Windows 6GB | split_coords | 42 | 1 (验证) |
| 阿里云 24GB | splits | 42,123,456,789,1024 | 5 |
| 阿里云 24GB | split_coords | 42,123,456,789,1024 | 5 |
| **总计** | - | - | **12次** |

## 输出产物

```
outputs/splits/seed_42/
├── checkpoint-xxx/         # LoRA权重
├── metrics.json            # 评测指标
├── predictions.jsonl       # 预测结果
├── training_config.yaml    # 训练配置备份
└── report.md               # 实验报告
```

## 故障排除

### 显存不足 (OOM)

1. 减小 `batch_size` 至 1
2. 减小 `max_length` 至 512
3. 启用 `gradient_checkpointing: true`
4. 使用 4-bit 量化加载模型

### 训练超时

1. 增加 `timeout` 参数
2. 减少 `num_epochs`
3. 启用 `max_steps` 限制

### 模型加载失败

1. 检查模型路径是否正确
2. 确保有足够的磁盘空间
3. 验证模型文件完整性

## 代码复用

本项目复用 `exp/exp0` 已有组件：
- `exp/exp0/utils/model_loader.py` - 模型加载参考
- `exp/exp0/utils/data_loader.py` - 数据加载参考
- `exp/exp0/metrics/deterministic.py` - 评测指标

## 许可证

MIT License

---

*本 README 由 Claude Code 生成，基于 GeoKD-SR V5.2 实验设计方案。*
