# GeoSignal SFT 训练配置

> **创建日期**: 2026-03-25
> **数据来源**: K2: A Foundation Language Model for Geoscience (WSDM 2024)
> **GitHub**: https://github.com/davendw49/k2

---

## 一、概述

本目录包含基于GeoSignal数据集训练Qwen2.5-1.5B地球科学指令遵循能力的配置和脚本。

GeoSignal是K2论文中构建的地球科学指令微调数据集，包含39,749条指令数据，涵盖8种任务类型。

## 二、目录结构

```
geosignal-sft/
├── configs/
│   ├── train_24gb.yaml    # 24GB显存训练配置
│   ├── train_6gb.yaml     # 6GB显存训练配置
│   └── eval.yaml          # 评估配置
├── src/
│   └── data_processor.py  # 数据处理模块
├── scripts/
│   └── train.py           # 训练脚本
├── outputs/               # 训练输出
├── logs/                  # 训练日志
└── checkpoints/           # 模型检查点
```

## 三、数据集信息

### GeoSignal统计

| 任务类型 | 样本数 | 信号类型 |
|---------|--------|---------|
| 命名实体识别 | 2,400 | G5 |
| 推理 | 600 | G6 |
| 事实核查 | 8,000 | G8 |
| 摘要 | 800 | G1,G9 |
| 文本分类 | 2,000 | G2 |
| 词语义 | 6,400 | G8 |
| 解释 | 4,200 | G7 |
| 问答 | 15,349 | G10 |
| **总计** | **39,749** | - |

### 数据格式

标准JSONL格式：
```json
{
  "instruction": "问题或指令文本",
  "input": "可选的输入文本",
  "output": "期望的输出文本"
}
```

## 四、使用方法

### 1. 准备数据

从K2项目下载数据：
```bash
# 从 https://github.com/davendw49/k2 下载GeoSignal数据
# 放置到 data/geosignal/ 目录
```

### 2. 训练模型

```bash
# 24GB显存环境
python scripts/train.py --config configs/train_24gb.yaml --seed 42

# 6GB显存环境
python scripts/train.py --config configs/train_6gb.yaml --seed 42

# 验证配置（不实际训练）
python scripts/train.py --config configs/train_24gb.yaml --dry-run

# 恢复训练
python scripts/train.py --config configs/train_24gb.yaml --resume outputs/checkpoint-xxx
```

### 3. 多随机种子实验

```bash
# 运行5个不同种子
for seed in 42 123 456 789 1024; do
    python scripts/train.py --config configs/train_24gb.yaml --seed $seed
done
```

## 五、配置说明

### 模型配置

基于K2论文验证的配置：
- **LoRA rank**: 8
- **LoRA alpha**: 16
- **目标模块**: q_proj, k_proj, v_proj, o_proj

### 训练配置

| 参数 | 24GB版本 | 6GB版本 |
|-----|---------|---------|
| 学习率 | 1e-4 | 1e-4 |
| 批次大小 | 8 | 1 |
| 梯度累积 | 16 | 128 |
| 有效批次 | 128 | 128 |
| 最大长度 | 2048 | 1024 |
| 混合精度 | bf16 | fp16 |
| 训练轮数 | 3 | 3 |

## 六、评估

### GeoBench评估

GeoBench是K2论文构建的地球科学评估基准：

**客观任务（选择题）**
- NPEE: 182道（全国硕士研究生入学考试）
- AP Test: 1,395道（美国大学先修课程考试）

**主观任务（开放问答）**
- NPEE主观题: 939道

### 评估脚本

```bash
# 评估模型
python scripts/evaluate.py --config configs/eval.yaml --checkpoint outputs/final_model
```

## 七、参考

- K2论文: [K2: A Foundation Language Model for Geoscience](https://dl.acm.org/doi/10.1145/3616855.3635772)
- K2 GitHub: https://github.com/davendw49/k2
- GeoSignal数据: 包含在K2项目中

---

*创建时间: 2026-03-25*
