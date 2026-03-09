# GeoKD-SR 实验目录

> **创建日期**: 2026-03-08
> **设计依据**: `docs/GeoKD-SR-实验设计方案-V5.2.md`

---

## 一、实验配置概览

本目录包含 GeoKD-SR 项目的所有实验配置，用于验证空间关系感知蒸馏方法的有效性。

| 配置 | 目录 | 方法名 | 说明 |
|------|------|--------|------|
| **Exp1** | `exp01_direct_sft` | B1-Direct-SFT | 对照组（无蒸馏） |
| **Exp2** | `exp02_standard_kd` | B2-Standard-KD | 通用蒸馏基线（Hinton 2015） |
| **Exp3a** | `exp03a_uniform_srd` | B2+C1(Uniform) | C1等权重基线 |
| **Exp3** | `exp03_srd` | B2+C1(Learnable) | 空间关系蒸馏损失（可学习权重） |
| **Exp4** | `exp04_cot_distill` | B2+C2 | 思维链蒸馏（ACL 2023） |
| **Exp5** | `exp05_reverse_kl` | B2+C3 | 逆向KL蒸馏（ICLR 2024） |
| **Exp6** | `exp06_self_distill` | B2+C4 | 自蒸馏损失 |
| **Exp7** | `exp07_attention` | B2+C5 | 空间关系注意力蒸馏 |
| **Exp8** | `exp08_progressive` | B2+C6 | 渐进式蒸馏 |
| **Exp9** | `exp09_geo_kd_sr` | GeoKD-SR(Full) | 完整方法 |

---

## 二、目录结构

每个实验目录包含以下结构：

```
expXX_name/
├── config.yaml          # 实验配置文件
├── train.py             # 训练脚本
├── evaluate.py          # 评估脚本
├── results/             # 实验结果目录
├── logs/                # 训练日志目录
├── checkpoints/         # 模型检查点目录
└── analysis/            # 分析报告目录
```

---

## 三、模型配置

### 教师模型
- **模型**: Qwen/Qwen2.5-7B-Instruct
- **量化**: 4-bit NF4量化（保持98.9%性能）
- **参考**: `docs/4bit量化教师模型合理性说明.md`

### 学生模型
- **模型**: Qwen/Qwen2.5-1.5B-Instruct
- **微调**: LoRA (r=8, alpha=16)

---

## 四、数据配置

所有实验使用相同的数据集以确保公平性：

- **训练集**: `data/geosr_chain/final/train.jsonl`
- **验证集**: `data/geosr_chain/final/dev.jsonl`
- **测试集**: `data/geosr_chain/final/test.jsonl`
- **基准测试**: `data/geosr_bench/benchmark.json`

---

## 五、评估指标

| 指标 | 说明 |
|------|------|
| **RA** | 推理准确率 (Reasoning Accuracy) |
| **SR-F1** | 空间关系F1分数 |
| **BLEU** | 生成文本质量 |
| **ROUGE-L** | 长文本匹配度 |

---

## 六、使用方法

### 训练实验

```bash
cd exp/expXX_name
python train.py --config config.yaml --seed 42
```

### 评估模型

```bash
cd exp/expXX_name
python evaluate.py --config config.yaml --checkpoint checkpoints/best_model
```

---

## 七、实验消融设计

| 实验 | 消融组件 | 验证目标 |
|------|----------|----------|
| Exp1 vs Exp2 | 无蒸馏 vs 标准蒸馏 | 验证蒸馏的有效性 |
| Exp2 vs Exp3 | 标准蒸馏 vs 空间关系蒸馏 | 验证SRD的增量贡献 |
| Exp3a vs Exp3 | 等权重 vs 可学习权重 | 验证动态加权的效果 |
| Exp3 vs Exp4-8 | 单组件 vs 多组件 | 验证各组件的独立贡献 |
| Exp9 vs Exp2-8 | 完整方法 vs 各消融 | 验证方法的整体效果 |

---

*创建时间: 2026-03-08*
