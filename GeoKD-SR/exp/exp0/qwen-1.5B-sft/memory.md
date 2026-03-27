# Qwen2.5-1.5B SFT微调实验记录

## 2026-03-22 训练与评估完成

### 实验配置
- 模型: Qwen2.5-1.5B-Instruct
- 训练方法: LoRA (r=16, alpha=32, dropout=0.05)
- 数据集: splits (不含坐标)
- 训练样本: 9463
- 验证样本: 1124
- 测试样本: 1183
- 显存: 24GB
- Seed: 42

### 训练配置
- Learning rate: 5e-5
- Batch size: 8
- Gradient accumulation: 16
- Effective batch size: 128
- Max length: 1024
- Epochs: 3
- Mixed precision: BF16
- Gradient checkpointing: True

### 训练结果

| Epoch | Step | eval_loss | token_accuracy |
|-------|------|-----------|----------------|
| 1/3   | 74   | 0.9385    | 78.89%         |
| 2/3   | 148  | 0.8390    | 80.38%         |
| 3/3   | 222  | **0.8252**| **80.63%**     |

最优模型: Epoch 3 (eval_loss=0.8252)

### 评估结果

**整体指标**
- Overall Accuracy: 5.16%
- Format Valid Rate: 42.69%
- BLEU-4: 0.0222
- ROUGE-L: 0.1390
- Spatial F1: 0.3527

**按空间类型分层**
| 类型 | 数量 | 准确率 | BLEU-4 | ROUGE-L | Spatial F1 |
|------|------|--------|--------|---------|------------|
| directional | 292 | 13.01% | 0.0395 | 0.1440 | 0.1147 |
| metric | 307 | 2.93% | 0.0045 | 0.1088 | 0.1686 |
| composite | 246 | 1.22% | 0.0307 | 0.1751 | 1.0000 |
| topological | 338 | 3.25% | 0.0171 | 0.1360 | 0.2544 |

**按难度分层**
| 难度 | 数量 | 准确率 |
|------|------|--------|
| easy | 372 | 6.99% |
| medium | 520 | 5.77% |
| hard | 291 | 1.72% |

### 输出文件
- 最优模型: `outputs/splits/seed_42/final_model/best_model/`
- 最后模型: `outputs/splits/seed_42/final_model/last_model/`
- 预测结果: `results/splits/seed_42/predictions.jsonl`
- 评测指标: `results/splits/seed_42/metrics.json`

### 观察
1. 训练损失持续下降，从初始3.22降至0.80
2. Token准确率从43.66%提升至81.25%
3. 方向类问题准确率最高(13.01%)，复合类最低(1.22%)
4. 简单问题准确率高于困难问题(6.99% vs 1.72%)
