# GeoKD-SR 逐实验细化说明文档索引

> 本目录包含基于《GeoKD-SR实验设计方案-V5.2.md》的逐实验细化说明文档，每实验一文件，供论文写作与实验复现参考。

**文档生成日期**：2026-03-11
**主依据文档**：`D:/30_keyan/docs/GeoKD-SR-实验设计方案-V5.2.md`
**数据规模**：约 10,000 条合格数据（已通过数据质量验收）

---

## 文档导航

### 00. 统一前言与训练环境（必读）
- 文件：`00-统一前言与训练环境.md`
- 内容：
  - 控制变量清单（所有实验必须一致）
  - V5.2 训练环境口径（硬件/软件/超参）
  - Seeds 与重复次数（5 seeds 统计规范）
  - 目录结构与产物协议
  - 评测统一协议引用

### 逐实验细化说明

| 实验编号 | 实验名称 | 文件名 | 核心组件 |
|---------|---------|--------|---------|
| **Exp1** | Direct-SFT（无蒸馏） | `01-Exp1-Direct-SFT.md` | B1 基线：仅 CE |
| **Exp2** | Standard-KD（通用蒸馏） | `02-Exp2-Standard-KD.md` | B2 基线：Forward KL + hard label |
| **Exp3a** | 空间关系蒸馏（等权重） | `03a-Exp3a-SRD-Uniform.md` | B2 + C1：等权重 1.0 |
| **Exp3** | 空间关系蒸馏（可学习权重） | `03-Exp3-SRD-Learnable.md` | B2 + C1：可学习权重 |
| **Exp4** | 思维链蒸馏 | `04-Exp4-CoT-Distill.md` | B2 + C2：推理链蒸馏 |
| **Exp5** | 逆向KL蒸馏 | `05-Exp5-Reverse-KL.md` | B2 + C3：Reverse KL |
| **Exp6** | 自蒸馏 | `06-Exp6-Self-Distill.md` | B2 + C4：EMA consistency |
| **Exp7** | 注意力对齐蒸馏 | `07-Exp7-Attention-Align.md` | B2 + C5：空间注意力蒸馏 |
| **Exp8** | 渐进式蒸馏 | `08-Exp8-Progressive.md` | B2 + C6：课程学习 |
| **Exp9** | GeoKD-SR 完整方法 | `09-Exp9-GeoKD-SR-Full.md` | B2 + C1..C6 组合 |

### Ablation 对比关系

V5.2 定义的对比集合（用于论文 ablation study 写作）：

```
Exp2 vs Exp1  → 验证通用蒸馏有效性
Exp3a vs Exp2 → 验证等权重空间关系感知是否有收益
Exp3 vs Exp3a → 验证可学习权重是否优于等权重
Exp3 vs Exp2  → 验证空间关系蒸馏损失的独立贡献
Exp4 vs Exp2  → 验证思维链蒸馏的贡献
Exp5 vs Exp2  → 验证逆向KL的贡献
Exp6 vs Exp2  → 验证自蒸馏的贡献
Exp7 vs Exp2  → 验证注意力对齐的贡献
Exp8 vs Exp2  → 验证渐进式训练的贡献
Exp9 vs Exp3-8 → 验证组件组合的协同效应
Exp9 vs Exp2  → 验证完整方法整体优势
```

---

## 使用说明

### 论文写作建议
1. **Methods 章节**：引用 `00-统一前言与训练环境.md` 的控制变量与环境口径
2. **每个实验的描述**：直接引用对应实验文档的“理论依据”与“方法口径”小节
3. **Ablation 讨论**：按上方对比关系引用相关实验的“诊断与失败模式”

### 实验复现建议
1. 首先阅读 `00-统一前言与训练环境.md` 确认训练环境
2. 按实验顺序 Exp1 → Exp2 → Exp3a → Exp3 → ... → Exp9 执行
3. 每个实验文档包含“步骤建议”小节，可按步骤执行训练与评测

### 术语对照表
| 术语 | 英文 | 说明 |
|-----|------|-----|
| 交叉熵损失 | CE / CrossEntropy | 硬标签监督损失 |
| 前向KL散度 | Forward KL | KL(教师\|\|学生)，mode-covering |
| 逆向KL散度 | Reverse KL | KL(学生\|\|教师)，mode-seeking |
| 空间关系蒸馏 | SRD / Spatial Relation Distillation | 按关系类型动态加权的蒸馏 |
| 思维链蒸馏 | CoT Distillation | 推理链蒸馏 |
| 自蒸馏 | Self-Distillation | 使用EMA学生模型作为软目标 |
| 注意力对齐 | Attention Alignment | 中间特征蒸馏（注意力模式） |
| 渐进式蒸馏 | Progressive Distillation | 课程学习式训练调度 |

---

## 参考文献定位

本文档中引用的理论依据主要来自 V5.2 以下章节：

| 主题 | V5.2 章节位置 |
|-----|--------------|
| 实验矩阵与对比关系 | §4.7.4 - §4.7.6 |
| 公平性原则（统一数据+字段可选+监督可控） | §4.7 |
| 训练环境与硬件 | §5.2 - §5.4 |
| 统计分析与显著性检验 | §6.1 - §6.2 |
| 评测体系与指标 | §7.2 - §7.4 |
