# exp0: 基线评估实验

## 实验概述
评估原始模型（无微调）在地理空间推理任务上的表现。

## 三模型基线
| 实验ID | 模型 | 配置 |
|--------|------|------|
| exp0a | Qwen2.5-1.5B-Instruct | 全精度 |
| exp0b | Qwen2.5-7B-Instruct | 全精度 |
| exp0c | Qwen2.5-7B-Instruct | 4bit量化 |

## 快速开始
```bash
python evaluate.py --config config/config_1.5b.yaml --seed 42
python batch_evaluate.py --all
```

## 评测指标
- **确定性指标**：Overall Accuracy, Format Valid Rate, BLEU-4, ROUGE-L, Perplexity, Spatial F1
- **语义指标**：BERTScore (P/R/F1)

## 目录结构
```
exp0/
├── config/           # 配置文件
├── metrics/          # 指标模块
├── utils/            # 工具模块
├── results/          # 评估结果
└── README.md
```
