# GeoKD-SR 实验设计方案

> **设计日期**: 2026年3月2日
> **版本**: V5.2（统计分析优化版）
> **任务**: 为GeoKD-SR研究设计数据集、方法和实验设置
> **目标**: 验证空间关系感知蒸馏的有效性
> **投稿目标**: ISPRS IJGI特刊"LLM4GIS"
> **截止日期**: 2026年8月31日

---

## 一、Context（背景与目标）

### 1.1 问题背景

**当前状态**:
- 理论准备充分（95%），但工程实现严重滞后（30%）
- 训练数据仅5条（目标5,000-60,000条）
- baselines目录为空，无法进行任何实验
- 教师模型未下载

**用户需求**:
- 从实验设计出发，确定所需数据集
- 通过消融实验验证组件贡献，而非预设权重
- 设计高性价比的蒸馏方法组件
- 确保实验公平性，避免数据差异引入变量

### 1.2 目标

1. **设计清晰的实验方案**：验证每个空间化组件的独立贡献
2. **设计公平的数据集**：所有方法使用相同数据，避免数据偏差
3. **选择高性价比组件**：基于大模型时代的蒸馏方法，平衡权威性和实现难度
4. **确保学术说服力**：通过消融实验证明方法有效性

---

## 二、实验方案设计

### 2.1 基线方法（2个）

#### B1: Direct-SFT（对照组）
- **描述**: 直接监督微调，无蒸馏
- **用途**: 验证蒸馏的有效性
- **损失函数**: `L_SFT = CrossEntropy(student_logits, labels)`

#### B2: Standard-KD（通用蒸馏）
- **描述**: Hinton 2015经典KL蒸馏（Forward KL）
- **权威性**: NeurIPS 2015，所有蒸馏论文的基线
- **损失函数**: `L_KD = α × L_soft + (1-α) × L_hard`
  - α = 0.5
  - 温度参数 T = 2.0
- **实现难度**: ⭐ 简单

### 2.2 GeoKD-SR组件（6个）

#### 第一梯队：核心组件（3个）

**C1: 空间关系蒸馏损失（核心创新）**
- **思想**: 根据空间关系类型（方向/拓扑/度量/组合）动态加权
- **权威性**: ⭐⭐⭐（核心创新点）
- **实现难度**: ⭐ 简单
- **性价比**: ⭐⭐⭐⭐⭐

**GIS理论依据**:

空间关系是GIS空间推理的核心，本组件的设计基于以下经典理论：

1. **点集拓扑关系九交模型** (Egenhofer, 1991)
   - 提出用九交矩阵（9-Intersection Model）描述空间对象之间的拓扑关系
   - 定义了 disjoint, meet, overlap, cover, contained, inside, equal 等拓扑关系
   - **本应用**: 拓扑关系类型权重（w_topological = 1.3）参考此模型

2. **方向关系模型** (Clementini et al., 1993)
   - 提出基于投影的方向关系模型，定性描述空间对象的方向
   - 定义了东、西、南、北、东北、西北、东南、西南等8方向
   - **本应用**: 方向关系类型权重（w_directional = 1.5）参考此模型

3. **空间认知分类法** (Cohn & Hazarika, 1997)
   - 提出从空间认知角度对空间关系进行分类
   - 区分拓扑关系、方向关系、度量关系等不同认知层次
   - **本应用**: 关系类型分类框架采用此分类法

4. **度量关系定义** (Worboys, 1993)
   - 提出度量关系的数值化表示方法
   - 使用距离、面积、周长等定量指标描述空间关系
   - **本应用**: 度量关系类型权重（w_metric = 1.0）基于此基础

**参考文献**:
- Egenhofer, M. J. (1991). Reasoning about binary topological relations. In SSD.
- Clementini, E., Felice, P. D., & Hernandez, D. (1993). Qualitative representation of positional information. ARTIFICIAL INTELLIGENCE REVIEW.
- Cohn, A. G., & Hazarika, S. M. (1997). Qualitative spatial representation and reasoning. ERCIM NEWS.
- Worboys, M. F. (1993). Modeling spatial relationships. IJGIS.
- **公式**:
  ```
  L_SRD = Σ w(r_i) × KL(P_T^i || P_S^i)

  详细展开：
  - P_T = softmax(z_T / T), P_S = softmax(z_S / T)
  - KL(P_T || P_S) = Σ P_T(x) × log(P_T(x) / P_S(x))  # Forward KL (教师分布在前)
  - T = 2.0（温度参数）

  关系类型权重（可学习）：
  w(r) = softmax([w_dir, w_topo, w_metric, w_comp])

  初始化权重：
  - w(directional) = 1.5  # 方向关系：空间认知基础
  - w(topological) = 1.3  # 拓扑关系：空间推理核心
  - w(metric) = 1.0       # 度量关系：相对简单
  - w(composite) = 1.8    # 组合推理：最复杂

  实现代码：
  ```python
  def spatial_relation_distillation_loss(student_logits, teacher_logits,
                                          relation_type, temperature=2.0):
      # 计算软标签
      p_teacher = F.softmax(teacher_logits / temperature, dim=-1)
      p_student = F.log_softmax(student_logits / temperature, dim=-1)

      # 基础KL散度（Forward KL: KL(P_T || P_S)）
      kl_loss = F.kl_div(p_student, p_teacher, reduction='none')

      # 根据关系类型加权
      weights = get_relation_weights(relation_type)  # [batch]
      weighted_loss = kl_loss * weights.unsqueeze(-1)

      return weighted_loss.mean()
  ```
  ```

**C2: 思维链蒸馏**
- **思想**: 蒸馏推理过程，而非仅答案
- **权威性**: ⭐⭐⭐⭐⭐（ACL 2023）
- **实现难度**: ⭐⭐ 中等
- **性价比**: ⭐⭐⭐⭐⭐
- **公式**:
  ```
  L_SCOT = α × L_chain + (1-α) × L_answer

  详细展开：
  L_chain = (1/n) × Σ KL(P_T^step_i || P_S^step_i)  # 添加1/n归一化
  L_answer = KL(P_T^answer || P_S^answer)

  推理链分解：
  reasoning_chain = [step_1, step_2, ..., step_n]
  每步独立计算蒸馏损失，除以步骤数n进行归一化

  参数设置：
  α = 0.6（推理链权重更高）
  温度 T = 2.0

  实现代码：
  ```python
  def chain_of_thought_distillation_loss(student_outputs, teacher_outputs,
                                          reasoning_chains, alpha=0.6):
      # 推理链蒸馏（添加1/n归一化）
      chain_loss = 0
      n_steps = len(reasoning_chains)
      for step_i in reasoning_chains:
          step_teacher = teacher_outputs[step_i]
          step_student = student_outputs[step_i]
          chain_loss += kl_div_loss(step_student, step_teacher)

      # 归一化：除以步骤数
      chain_loss = chain_loss / n_steps

      # 答案蒸馏
      answer_loss = kl_div_loss(student_outputs['answer'],
                                teacher_outputs['answer'])

      return alpha * chain_loss + (1 - alpha) * answer_loss
  ```
  ```
- **参考**: Shridhar et al. "Distilling Reasoning Capabilities into Smaller Language Models" (ACL 2023)

**C3: 逆向KL蒸馏**
- **思想**: Reverse KL更适合生成任务，减少幻觉
- **权威性**: ⭐⭐⭐⭐⭐（ICLR 2024, Microsoft）
- **实现难度**: ⭐ 简单
- **性价比**: ⭐⭐⭐⭐⭐
- **公式**:
  ```
  L_RKL = KL(P_S || P_T)

  详细展开：
  KL(P_S || P_T) = Σ P_S(x) × log(P_S(x) / P_T(x))

  与Forward KL的区别：
  Forward KL: KL(P_T || P_S) - mode-covering
  Reverse KL: KL(P_S || P_T) - mode-seeking

  优势：
  - 避免 mode-covering问题
  - 聚焦教师的主要模式
  - 更适合生成任务
  - 减少学生模型的幻觉

  实现代码：
  ```python
  def reverse_kl_distillation_loss(student_logits, teacher_logits, temperature=2.0):
      # 注意：逆向KL需要学生分布在前
      p_student = F.softmax(student_logits / temperature, dim=-1)
      log_p_student = F.log_softmax(student_logits / temperature, dim=-1)
      log_p_teacher = F.log_softmax(teacher_logits / temperature, dim=-1)

      # 逆向KL: KL(P_S || P_T)
      reverse_kl = (p_student * (log_p_student - log_p_teacher)).sum(dim=-1)
      return reverse_kl.mean()
  ```
  ```
- **参考**: Gu et al. "MiniLLM: Knowledge Distillation of Large Language Models" (ICLR 2024)

#### 第二梯队：扩展组件（3个）

**C4: 自蒸馏损失**
- **思想**: 通过自蒸馏损失增强学生模型的空间推理能力
- **权威性**: ⭐⭐⭐（自蒸馏技术，ICLR 2020）
- **实现难度**: ⭐ 简单
- **性价比**: ⭐⭐⭐⭐
- **核心设计**:
  - 不改变训练数据，在损失函数层面增强模型
  - 使用学生模型自身的预测作为软目标
  - 通过时间一致性约束提升推理稳定性
- **公式**:
  ```
  L_SelfDistill = λ × L_consistency + (1-λ) × L_SFT

  详细展开：
  L_consistency = KL(P_S^current || P_S^ema)

  其中：
  - P_S^current: 当前学生模型的预测
  - P_S^ema: 指数移动平均的学生模型预测
  - λ = 0.3（自蒸馏权重）

  EMA更新：
  θ_ema = μ × θ_ema + (1-μ) × θ_current
  μ = 0.999（衰减率）

  实现代码：
  ```python
  def self_distillation_loss(student_model, student_ema_model, inputs,
                             labels, lambda_sd=0.3):
      # 当前学生模型预测
      logits_current = student_model(inputs)
      p_current = F.softmax(logits_current / T, dim=-1)

      # EMA学生模型预测
      logits_ema = student_ema_model(inputs)
      p_ema = F.softmax(logits_ema / T, dim=-1)

      # 一致性损失（自蒸馏）
      consistency_loss = F.kl_div(
          F.log_softmax(logits_current / T, dim=-1),
          p_ema,
          reduction='batchmean'
      )

      # 标准监督损失
      sft_loss = F.cross_entropy(logits_current, labels)

      # 组合损失
      total_loss = lambda_sd * consistency_loss + (1 - lambda_sd) * sft_loss

      # 更新EMA模型
      update_ema_model(student_model, student_ema_model)

      return total_loss

  def update_ema_model(model, ema_model, mu=0.999):
      for param, ema_param in zip(model.parameters(), ema_model.parameters()):
          ema_param.data.mul_(mu).add_(param.data, alpha=1-mu)
  ```
  ```
- **参考**: Zhang et al. "Self-training with Noisy Student improves ImageNet classification" (ICLR 2020)

**C5: 空间关系注意力蒸馏**
- **思想**: 在空间实体和空间关系token上做注意力对齐，关注空间关系抽象的注意力层
- **权威性**: ⭐⭐⭐⭐⭐（TinyBERT EMNLP 2020, DistilBERT NeurIPS 2019）
- **实现难度**: ⭐⭐ 中等
- **性价比**: ⭐⭐⭐⭐⭐
- **核心设计**:
  - 自适应层选择：自动选择最关注空间关系的层
  - 空间实体注意力：对齐地点实体（北京、上海）的注意力模式
  - 空间关系注意力：对齐关系词（方向、距离、相邻）的注意力模式
- **公式**:
  ```
  L_SRA = Σ λ_l × L_attn^(l)

  其中：
  L_attn^(l) = 1/h × Σ MSE(A_S^(l,j), A_T^(l,j))

  自适应层权重：
  λ_l = softmax(w_l), w_l 可学习

  空间实体掩码：
  M_entity = [1 if token in entities else 0]
  L_SRA = L_attn × M_entity
  ```
- **参考**: Jiao et al. "TinyBERT: Distilling BERT for Natural Language Understanding" (EMNLP 2020)

**C6: 渐进式蒸馏**
- **思想**: 从简单空间关系逐步过渡到复杂推理
- **权威性**: ⭐⭐⭐⭐（Curriculum Learning, Bengio 2009）
- **实现难度**: ⭐⭐ 中等
- **性价比**: ⭐⭐⭐⭐⭐
- **训练阶段**:
  ```
  阶段1: 方向关系（简单） - Epoch 1
  阶段2: 拓扑关系（中等） - Epoch 2
  阶段3: 度量+组合推理（复杂） - Epoch 3

  渐进式损失函数：
  L_prog(t) = Σ w_i(t) × L_i

  权重调度（3 epoch压缩版）：
  w_i(t) = {
    1.0,  if t in phase_i
    0.3,  if t in phase_{i-1} (复习)
    0.0,  otherwise
  }

  难度评估标准：
  - 方向关系：基础认知，不涉及复杂计算
  - 拓扑关系：需要理解空间关系概念
  - 度量关系：需要数值计算
  - 组合推理：多步推理，最复杂

  实现代码：
  ```python
  def progressive_distillation_loss(student_outputs, teacher_outputs,
                                     batch_data, current_epoch):
      # 确定当前阶段（压缩为3 epoch）
      phase = get_current_phase(current_epoch)

      # 计算各阶段权重
      weights = compute_progressive_weights(phase)

      # 加权损失
      total_loss = 0
      for rel_type in ['directional', 'topological', 'metric', 'composite']:
          mask = batch_data['relation_type'] == rel_type
          if mask.sum() > 0:
              loss = kd_loss(student_outputs[mask], teacher_outputs[mask])
              total_loss += weights[rel_type] * loss

      return total_loss

  def get_current_phase(epoch):
      # 3 epoch压缩版
      if epoch == 1: return 'directional'
      elif epoch == 2: return 'topological'
      else: return 'complex'  # metric + composite
  ```
  ```
- **参考**: Bengio et al. "Curriculum Learning" (ICML 2009)

---

## 三、消融实验设计

### 3.1 实验配置（10个）

| 配置 | 方法 | 使用的字段 | 验证目的 |
|------|------|----------|---------|
| **Exp1** | B1: Direct-SFT | question, answer | 基线（无蒸馏） |
| **Exp2** | B2: Standard-KD | question, answer | 基线（通用蒸馏） |
| **Exp3a** | B2 + C1 (Uniform Weights) | + spatial_relation_type | C1等权重基线 |
| **Exp3** | B2 + C1 (Learnable Weights) | + spatial_relation_type | 空间关系蒸馏损失贡献 |
| **Exp4** | B2 + C2 | + reasoning_chain | 思维链蒸馏贡献 |
| **Exp5** | B2 + C3 | question, answer | 逆向KL贡献 |
| **Exp6** | B2 + C4 | question, answer | 自蒸馏损失贡献 |
| **Exp7** | B2 + C5 | + entities, spatial_tokens | 空间关系注意力蒸馏贡献 |
| **Exp8** | B2 + C6 | 渐进式训练数据 | 渐进式蒸馏贡献 |
| **Exp9** | **GeoKD-SR（完整）** | 所有字段 | 完整方法 |

### 3.2 验证目标

| 对比 | 验证的假设 |
|------|-----------|
| Exp2 vs Exp1 | 蒸馏的有效性 |
| Exp3a vs Exp2 | C1等权重是否优于标准KD |
| Exp3 vs Exp3a | C1可学习权重是否优于等权重 |
| Exp3 vs Exp2 | 空间关系蒸馏损失的贡献 |
| Exp4 vs Exp2 | 思维链蒸馏的贡献 |
| Exp5 vs Exp2 | 逆向KL蒸馏的贡献 |
| Exp6 vs Exp2 | 自蒸馏损失的贡献 |
| Exp7 vs Exp2 | 空间关系注意力蒸馏的贡献 |
| Exp8 vs Exp2 | 渐进式蒸馏的贡献 |
| Exp9 vs Exp2 | 完整方法的优势 |
| Exp9 vs Exp3-Exp8 | 组件组合的协同效应 |

### 3.3 不设置预设权重

**核心原则**: 通过消融实验的精度来决定最终的蒸馏效果，而非预设组件权重

**实验流程**:
1. 分别测试每个组件（Exp3-Exp8）
2. 记录每个组件的性能提升
3. 根据实验结果决定最终配置
4. 组合有效组件（Exp9）

---

## 四、数据集设计

### 4.1 设计原则

**公平性原则**: 所有方法使用相同的数据，不同方法选择性使用字段

### 4.2 统一数据格式

```json
{
  "id": "geosr_001",
  "spatial_relation_type": "directional",

  // 基础字段（所有方法使用）
  "question": "北京在上海的什么方向？",
  "answer": "西北方向",

  // 扩展字段（特定组件使用）
  "reasoning_chain": [
    "步骤1: 确定北京坐标(116.4°E, 39.9°N)",
    "步骤2: 确定上海坐标(121.5°E, 31.2°N)",
    "步骤3: 计算方位角，北京位于上海的西北方向"
  ],

  "entities": [
    {"name": "北京", "type": "city", "coords": [116.4, 39.9]},
    {"name": "上海", "type": "city", "coords": [121.5, 31.2]}
  ],

  "spatial_tokens": ["北京", "上海", "西北", "方向"],

  "instruction": "请判断北京在上海的什么方向？",

  "difficulty": "easy"
}
```

### 4.3 方法-字段对应关系

| 方法 | 使用的字段 | 说明 |
|------|----------|------|
| B1, B2, Exp5 | question, answer | 基础字段 |
| Exp3a, Exp3 (B2+C1) | + spatial_relation_type | 用于空间关系加权 |
| Exp4 (B2+C2) | + reasoning_chain | 用于推理链蒸馏 |
| Exp6 (B2+C4) | question, answer | 用于自蒸馏损失 |
| Exp7 (B2+C5) | + entities, spatial_tokens | 用于空间实体注意力蒸馏 |
| Exp8 (B2+C6) | 渐进式训练数据 | 用于渐进式蒸馏 |
| Exp9 (GeoKD-SR) | 所有字段 | 完整方法 |

### 4.4 数据字段详细说明

| 字段名 | 类型 | 必需 | 使用组件 | 说明 |
|--------|------|------|---------|------|
| id | string | 是 | 所有 | 唯一标识符 |
| question | string | 是 | 所有 | 用户问题 |
| answer | string | 是 | 所有 | 标准答案 |
| spatial_relation_type | enum | 是 | C1, C6 | 关系类型(directional/topological/metric/composite) |
| reasoning_chain | list | 否 | C2 | 推理步骤列表 |
| entities | list | 否 | C5 | 空间实体及其坐标 |
| spatial_tokens | list | 否 | C5 | 空间相关token |
| difficulty | enum | 否 | C6 | 难度等级(easy/medium/hard) |

### 4.5 数据规模（科学计算确定）

#### 4.5.1 数据量选取的科学分析

**为什么选择8,000条？**

**1. 基于学习理论的分析**
```
样本复杂度下界（PAC学习理论）：
n ≥ O((VC_dim + log(1/δ)) / ε²)

对于LLM微调，经验法则：
n ≥ 100 × sqrt(参数量/压缩比)
  ≈ 100 × sqrt(1.5B / 1000)  # LoRA压缩比约1000x
  ≈ 12,250 条（理论上界）

但实际微调通常需要：5,000 ~ 20,000 条
```

**2. 参考文献数据量对比**
| 研究 | 任务类型 | 模型规模 | 数据量 | 效果 |
|------|---------|---------|--------|------|
| Alpaca (Stanford 2023) | 通用指令 | 7B | 52,000 | 良好 |
| MiniLLM (ICLR 2024) | 知识蒸馏 | 1.5B | 10,000 | 有效 |
| CoT-Distill (ACL 2023) | 推理蒸馏 | 1.5B | 8,000 | 有效 |

**3. 计算资源约束分析**
```
训练配置：
- 模型: Qwen2.5-1.5B (LoRA微调)
- GPU: A10 24GB
- Batch size: 8 × 16 = 128
- Epochs: 3

总计算量：
Total_tokens = 8000 × 512 × 3 = 12,288,000 tokens

预计训练时间：
Time ≈ 12M / (100K tokens/s × 0.7) ≈ 2.9小时

结论：8,000条数据在A10上约3小时可完成训练，资源消耗合理
```

**4. 选择8,000条的理由**
- **学术参考**：与CoT-Distill (ACL 2023)相同规模
- **计算效率**：3个epoch约3小时，可接受
- **覆盖充分**：4种关系类型 × 3种难度 = 12种组合，每组合约667条
- **质量可控**：8,000条可实现人工抽样10%验证
- **风险平衡**：避免欠拟合（<5000）和过拟合（>15000）

#### 4.5.2 最终数据规模

**训练集**: 8,000条

| 空间关系类型 | Easy (30%) | Medium (50%) | Hard (20%) | 小计 |
|-------------|-----------|-------------|-----------|------|
| Directional（方向） | 720 | 1,200 | 480 | **2,400** |
| Topological（拓扑） | 540 | 900 | 360 | **1,800** |
| Metric（度量） | 540 | 900 | 360 | **1,800** |
| Composite（组合） | 600 | 1,000 | 400 | **2,000** |
| **小计** | **2,400** | **4,000** | **1,600** | **8,000** |

**验证集**: 800条（训练集的10%）

| 空间关系类型 | Easy (30%) | Medium (50%) | Hard (20%) | 小计 |
|-------------|-----------|-------------|-----------|------|
| Directional（方向） | 72 | 120 | 48 | **240** |
| Topological（拓扑） | 54 | 90 | 36 | **180** |
| Metric（度量） | 54 | 90 | 36 | **180** |
| Composite（组合） | 60 | 100 | 40 | **200** |
| **小计** | **240** | **400** | **160** | **800** |

### 4.6 数据生成与质量控制（详细）

#### 4.6.1 种子数据来源

**策略**: GLM-5 API单独生成 + 人工验证

**数据生成流程**:
```
阶段1: 种子问题设计
├── 定义空间关系类型关键词库
│   ├── 方向词: 东、西、南、北、东北、西南、东南、西北
│   ├── 拓扑词: 包含、位于、相邻、接壤、穿过、流经
│   └── 度量词: 距离、远、近、公里、千米
│
├── 地理实体库构建
│   ├── 中国省会城市（34个）
│   ├── 主要地级市（100+个）
│   ├── 著名山脉、河流
│   └── 省份、区域
│
└── 问题模板设计
    ├── 方向关系模板: "{A}在{B}的什么方向？"
    ├── 拓扑关系模板: "{A}是否位于{B}内？"
    ├── 度量关系模板: "{A}距离{B}约多少公里？"
    └── 组合推理模板: "从{A}到{B}经过哪些省份？"

阶段2: GLM-5 API生成
├── 使用GLM-5-Plus API生成问题-答案对
├── 生成推理链（Chain-of-Thought）
├── 标注空间关系类型
└── 提取地理实体

阶段3: 质量控制
├── 自动验证（规则检查）
├── 地理坐标验证（经纬度合理性）
├── 逻辑一致性检查
└── 人工抽样验证（≥10%）
```

**GLM-5 API配置**:
```python
# GLM-5 API调用配置
GLM5_CONFIG = {
    "model": "glm-5-plus",  # 使用GLM-5-Plus模型
    "api_base": "https://open.bigmodel.cn/api/paas/v4/",
    "temperature": 0.7,  # 生成温度
    "max_tokens": 2048,  # 最大生成长度
    "top_p": 0.9
}
```

#### 4.6.2 质量控制标准

| 验证环节 | 验证内容 | 通过标准 |
|---------|---------|---------|
| **格式验证** | JSON格式完整性 | 100%通过 |
| **空间关系验证** | 关系类型标注正确性 | ≥95%正确 |
| **推理链验证** | 推理步骤逻辑正确性 | ≥90%正确 |
| **答案一致性验证** | 答案与问题一致性 | ≥98%正确 |
| **地理坐标验证** | 经纬度在合理范围内 | 100%通过 |
| **实体识别验证** | 实体名称与类型匹配 | ≥95%正确 |
| **去重验证** | 相似度去重 | 余弦相似度<0.9 |

#### 4.6.3 数据生成Prompt模板

**方向关系问题生成**:
```
你是一个地理空间推理专家。请根据以下要求生成一道方向关系推理题：

地理实体: {entity_A}, {entity_B}
实体坐标: A({lat_A}, {lon_A}), B({lat_B}, {lon_B})

要求：
1. 问题形式: "{A}在{B}的什么方向？"
2. 提供详细的推理步骤，包括：
   - 确定两点的经纬度坐标
   - 计算方位角
   - 判断方向（八方位）
3. 最终答案简洁明确

输出JSON格式：
{
  "question": "问题",
  "answer": "答案",
  "reasoning_chain": ["步骤1", "步骤2", ...],
  "entities": [...],
  "spatial_relation_type": "directional"
}
```

### 4.7 数据公平性设计（核心）

#### 4.7.1 设计原则

**统一数据+选择性字段使用**

| 原则 | 说明 |
|------|------|
| **数据统一** | 所有实验使用完全相同的数据文件 |
| **字段可选** | 不同方法选择性使用不同字段 |
| **监督可控** | 通过掩码机制控制监督范围 |
| **统计可比** | 所有方法在相同测试集上评估 |

#### 4.7.2 输入输出格式设计

**统一输入+选择性监督**

所有方法使用相同的输入格式，但监督时选择性使用字段：

```python
# 统一输入格式
input_text = f"问题：{sample['question']}\n请逐步分析："

# 选择性监督（不同实验监督不同部分）
# Exp1/Exp2/Exp5: 只监督答案
target_text = sample['answer']

# Exp4 (C2思维链蒸馏): 监督推理链+答案
reasoning_text = "\n".join(sample['reasoning_chain'])
target_text = f"{reasoning_text}\n最终答案：{sample['answer']}"
```

#### 4.7.3 数据使用矩阵

| 字段 | Exp1 | Exp2 | Exp3a | Exp3 | Exp4 | Exp5 | Exp6 | Exp7 | Exp8 | Exp9 |
|------|------|------|------|------|------|------|------|------|------|------|
| question | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| answer | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| spatial_relation_type | - | - | ✓ | ✓ | - | - | - | - | ✓ | ✓ |
| reasoning_chain | - | - | - | - | ✓ | - | - | - | - | ✓ |
| entities | - | - | - | - | - | - | - | ✓ | - | ✓ |
| spatial_tokens | - | - | - | - | - | - | - | ✓ | - | ✓ |
| difficulty | - | - | - | - | - | - | - | - | ✓ | ✓ |

#### 4.7.4 各实验输入监督详细设计

**Exp1: B1-Direct-SFT（对照组）**
```python
input_text = f"问题：{sample['question']}\n答案："
target_text = sample['answer']
loss = CrossEntropyLoss(student_logits, target_ids)
# 公平性：仅使用question和answer字段，无任何蒸馏信号
```

**Exp2: B2-Standard-KD（通用蒸馏基线）**
```python
input_text = f"问题：{sample['question']}\n答案："
target_text = sample['answer']
loss_hard = CrossEntropyLoss(student_logits, target_ids)
loss_soft = KLLoss(teacher_soft_labels, student_soft_labels)
loss = alpha * loss_soft + (1-alpha) * loss_hard
# 公平性：使用相同数据，添加通用蒸馏信号
```

**Exp3a: B2+C1（等权重空间关系蒸馏）**
```python
input_text = f"问题：{sample['question']}\n答案："
relation_type = sample['spatial_relation_type']
weight = 1.0  # 等权重基线
loss_soft = weight * KLLoss(teacher_soft_labels, student_soft_labels)
# 公平性：数据相同，使用等权重验证C1基础效果
```

**Exp3: B2+C1（可学习权重空间关系蒸馏）**
```python
input_text = f"问题：{sample['question']}\n答案："
relation_type = sample['spatial_relation_type']
weight = relation_weights[relation_type]  # 可学习权重
loss_soft = weight * KLLoss(teacher_soft_labels, student_soft_labels)
# 公平性：数据相同，仅损失计算时根据关系类型加权
```

**Exp4: B2+C2（思维链蒸馏）**
```python
input_text = f"问题：{sample['question']}\n请逐步分析："
reasoning_text = "\n".join(sample['reasoning_chain'])
target_text = f"{reasoning_text}\n最终答案：{sample['answer']}"
# 分步蒸馏：推理链+答案
# 公平性：输入相同数据，监督时使用reasoning_chain字段
```

**Exp5: B2+C3（逆向KL蒸馏）**
```python
input_text = f"问题：{sample['question']}\n答案："
target_text = sample['answer']
loss_soft = ReverseKLLoss(student_soft_labels, teacher_soft_labels)
# KL(P_S || P_T) 而非 KL(P_T || P_S)
# 公平性：数据和输入完全相同，仅KL方向改变
```

**Exp6: B2+C4（自蒸馏损失）**
```python
input_text = f"问题：{sample['question']}\n答案："
target_text = sample['answer']
# 自蒸馏：使用EMA学生模型作为软目标
loss_self = SelfDistillationLoss(student_model, student_ema_model)
# 公平性：数据和输入完全相同，添加自蒸馏损失
```

**Exp7: B2+C5（空间关系注意力蒸馏）**
```python
input_text = f"问题：{sample['question']}\n答案："
entities = sample['entities']
spatial_tokens = sample['spatial_tokens']
# 额外监督注意力模式（使用entities和spatial_tokens）
loss_attn = MSELoss(teacher_attn, student_attn)
# 公平性：数据相同，额外监督注意力模式
```

**Exp8: B2+C6（渐进式蒸馏）**
```python
# 根据训练阶段筛选数据
current_phase = get_phase(epoch)  # directional -> topological -> complex
# 使用相同数据全集，训练时分阶段采样
# 公平性：使用相同数据全集，仅训练顺序不同
```

#### 4.7.5 消融实验公平性保证机制

```python
class FairExperimentManager:
    """公平实验管理器"""

    def __init__(self, data_path):
        # 所有实验加载相同数据
        self.full_data = self.load_data(data_path)
        self.train_data = self.full_data['train']  # 8000条
        self.dev_data = self.full_data['dev']      # 800条

    def get_experiment_data(self, exp_id):
        """获取实验数据（所有实验返回相同数据引用）"""
        return {
            'train': self.train_data,  # 相同引用
            'dev': self.dev_data       # 相同引用
        }

    def get_field_selector(self, exp_id):
        """获取字段选择器（控制使用哪些字段）"""
        field_configs = {
            'Exp1': ['question', 'answer'],
            'Exp2': ['question', 'answer'],
            'Exp3a': ['question', 'answer', 'spatial_relation_type'],
            'Exp3': ['question', 'answer', 'spatial_relation_type'],
            'Exp4': ['question', 'answer', 'reasoning_chain'],
            'Exp5': ['question', 'answer'],
            'Exp6': ['question', 'answer'],
            'Exp7': ['question', 'answer', 'entities', 'spatial_tokens'],
            'Exp8': ['question', 'answer', 'spatial_relation_type', 'difficulty'],
            'Exp9': ['all']  # 使用所有字段
        }
        return FieldSelector(field_configs[exp_id])
```

#### 4.7.6 消融实验对比说明

| 对比 | 验证假设 | 控制变量 | 实验变量 |
|------|---------|---------|---------|
| Exp2 vs Exp1 | 蒸馏有效性 | 数据、输入格式 | 蒸馏信号 |
| Exp3a vs Exp2 | C1等权重效果 | 数据、基础蒸馏 | 等权重空间关系 |
| Exp3 vs Exp3a | C1可学习权重效果 | 数据、等权重 | 可学习权重 |
| Exp3 vs Exp2 | C1贡献 | 数据、基础蒸馏 | 空间关系加权 |
| Exp4 vs Exp2 | C2贡献 | 数据、基础蒸馏 | 推理链监督 |
| Exp5 vs Exp2 | C3贡献 | 数据、基础蒸馏 | KL方向 |
| Exp6 vs Exp2 | C4贡献 | 数据、基础蒸馏 | 自蒸馏损失 |
| Exp7 vs Exp2 | C5贡献 | 数据、基础蒸馏 | 注意力监督 |
| Exp8 vs Exp2 | C6贡献 | 数据、基础蒸馏 | 渐进式训练 |
| Exp9 vs Exp2 | 完整方法 | 数据 | 所有组件 |
| Exp9 vs Exp3-8 | 协同效应 | 各组件单独 | 组件组合 |

---

## 五、模型与环境配置

### 5.1 模型配置

| 配置项 | 教师模型 | 学生模型 |
|--------|---------|---------|
| **模型名称** | GLM-5-Plus | Qwen2.5-1.5B-Instruct |
| **参数量** | - | 1.5B |
| **量化方式** | - | 全精度 |
| **推理框架** | API | transformers |
| **上下文长度** | 128K | 32K |

### 5.2 硬件环境

| 配置项 | 规格 |
|--------|------|
| **平台** | 阿里云PAI |
| **GPU** | NVIDIA A10 24GB |
| **CPU** | 8核 |
| **内存** | 32GB |
| **存储** | 100GB SSD |

### 5.3 软件环境

| 软件 | 版本 |
|------|------|
| Python | 3.12.12 |
| PyTorch | 2.6.0+cu124 |
| Transformers | 4.48.3 |
| PEFT | 0.14.0 |
| bitsandbytes | 0.45.0 |
| vLLM | 0.6.3 |

### 5.4 训练超参数配置

#### 5.4.1 模型量化策略

| 配置项 | 教师模型 | 学生模型 |
|--------|---------|---------|
| **模型名称** | GLM-5-Plus | Qwen2.5-1.5B-Instruct |
| **参数量** | - | 1.5B |
| **量化方式** | - | 全精度/4-bit量化 |
| **推理框架** | API | transformers |

**量化选择理由**:

1. **4-bit量化选择理由**（显存受限场景）:
   - **显存限制**: A10 GPU 24GB显存，使用4-bit量化后模型显存占用约2-3GB，为训练梯度、优化器状态预留足够空间
   - **推理速度**: 4-bit量化可提升推理速度约2-3倍，加速教师模型软标签生成
   - **实现便捷**: 使用bitsandbytes库可轻松加载4-bit量化模型
   - **适用场景**: 当显存紧张或需要快速迭代实验时

2. **全精度选择理由**（质量优先场景）:
   - **避免量化损失**: 全精度模型可避免量化带来的精度损失，保持蒸馏质量
   - **数值稳定性**: 全精度训练在梯度计算和更新时更稳定
   - **学术严谨性**: 论文实验应使用全精度模型，确保结果可复现
   - **适用场景**: 最终实验和结果报告时使用

**量化切换策略**:
```python
# 4-bit量化（开发调试阶段）
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-1.5B-Instruct",
    load_in_4bit=True,
    device_map="auto"
)

# 全精度（最终实验阶段）
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-1.5B-Instruct",
    torch_dtype=torch.float32,
    device_map="auto"
)
```

#### 5.4.2 训练超参数

```yaml
# 基础训练配置
training:
  learning_rate: 1e-4
  batch_size: 8
  gradient_accumulation_steps: 16
  effective_batch_size: 128
  num_epochs: 3
  warmup_ratio: 0.1
  weight_decay: 0.01
  max_grad_norm: 1.0

# 蒸馏配置
distillation:
  temperature: 2.0
  alpha: 0.5  # 软标签权重

# LoRA配置
lora:
  r: 8
  lora_alpha: 16
  lora_dropout: 0.05
  target_modules: ["q_proj", "k_proj", "v_proj", "o_proj"]
  bias: "none"

# 优化器配置
optimizer:
  type: "adamw_torch"
  betas: [0.9, 0.999]
  eps: 1e-8

# 学习率调度
scheduler:
  type: "cosine"
  min_lr: 1e-6
```

### 5.5 组件权重配置

```yaml
# 损失函数权重（Exp9完整方法）
loss_weights:
  hard_label: 0.3      # 硬标签损失
  srd: 0.25            # C1: 空间关系蒸馏
  scot: 0.20           # C2: 思维链蒸馏
  rkl: 0.15            # C3: 逆向KL蒸馏
  self_distill: 0.05   # C4: 自蒸馏损失
  attention: 0.03      # C5: 空间关系注意力蒸馏
  progressive: 0.02    # C6: 渐进式蒸馏

# 空间关系类型权重
relation_weights:
  directional: 1.5     # 方向关系：空间认知基础
  topological: 1.3     # 拓扑关系：空间推理核心
  metric: 1.0          # 度量关系：相对简单
  composite: 1.8       # 组合推理：最复杂

# Exp3a等权重配置（用于对比）
uniform_relation_weights:
  directional: 1.0
  topological: 1.0
  metric: 1.0
  composite: 1.0
```

---

## 六、实验流程规范

### 6.1 实验重复性与统计规范

#### 6.1.1 运行次数与随机种子

| 配置项 | 设置 |
|--------|------|
| **运行次数** | 5次 |
| **报告方式** | 平均值 ± 标准差 |
| **随机种子集** | [42, 123, 456, 789, 1024] |

**种子使用规范**:
```python
# 每次实验开始前设置
import random
import numpy as np
import torch

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

# 使用示例
SEEDS = [42, 123, 456, 789, 1024]
for seed in SEEDS:
    set_seed(seed)
    # 运行实验...
```

#### 6.1.2 统计显著性检验

| 检验类型 | 使用场景 | 显著性水平 |
|---------|---------|-----------|
| **配对t检验** | 同一方法不同配置对比 | p < 0.05 |
| **Wilcoxon检验** | 非正态分布数据 | p < 0.05 |
| **效应量(Cohen's d)** | 评估提升幅度 | d > 0.8为大效应 |

#### 6.1.3 多重比较校正

**问题**: 当进行多组对比时，若不进行校正，整体犯错概率会显著增加。

对于8组对比（Exp3-Exp8 vs Exp2），在α=0.05水平下：
- 不校正时整体犯错概率：1 - (1-0.05)^8 ≈ 34%
- 这意味着约1/3的概率出现至少一次假阳性

**解决方案**: Holm-Bonferroni校正

Holm-Bonferroni是一种逐步拒绝的多重比较校正方法，相比传统Bonferroni校正具有更高的统计效力，同时仍能控制家族错误率(FWER)。

**算法步骤**:
1. 对所有p值进行升序排序：p₁ ≤ p₂ ≤ ... ≤ pₘ
2. 从最小的p值开始，依次检验：
   - 如果 p₁ ≤ α/m，拒绝H₁，继续
   - 如果 p₂ ≤ α/(m-1)，拒绝H₂，继续
   - 直到首次出现 pᵢ > α/(m-i+1)，停止检验
3. 所有满足条件的假设都拒绝，后续假设保留

**优势**:
- 控制FWER在α水平以内
- 比传统Bonferroni校正更强大（higher power）
- 适合本实验的8组对比场景

**实现**:
```python
from experiments.statistical_analysis import holm_bonferroni_correction

# 假设有8组对比的p值
p_values = np.array([p1, p2, p3, p4, p5, p6, p7, p8])

# 应用Holm-Bonferroni校正
rejected, adjusted_p = holm_bonferroni_correction(p_values, alpha=0.05)

# rejected: 布尔数组，指示哪些假设被拒绝
# adjusted_p: 校正后的p值数组
```

**参考文献**:
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 6, 65-70.

### 6.2 实验流程

```
实验流程规范
│
├── 1. 环境准备
│   ├── 检查GPU可用性
│   ├── 加载预训练模型
│   └── 设置随机种子
│
├── 2. 数据加载
│   ├── 加载训练/验证数据
│   ├── 数据预处理
│   └── 创建DataLoader
│
├── 3. 模型训练（每个配置3次）
│   ├── 训练循环
│   ├── 验证评估
│   ├── 模型保存
│   └── 训练日志记录
│
├── 4. 测试评估
│   ├── 加载最佳checkpoint
│   ├── 在GeoSR-Bench上评估
│   └── 记录各项指标
│
└── 5. 结果汇总
    ├── 计算均值和标准差
    ├── 统计显著性检验
    └── 生成结果表格
```

### 6.3 Checkpoint管理

| 配置项 | 设置 |
|--------|------|
| **保存策略** | 每epoch保存最佳模型 |
| **评估指标** | 验证集准确率 |
| **保存路径** | `checkpoints/{method}/{seed}/` |
| **命名规则** | `checkpoint-epoch{N}-acc{X.XX}.pt` |

---

## 七、评测体系设计

### 7.1 评测基准（GeoSR-Bench）

**规模**: 1,000题（已完成）

**评测维度**:
- D1: 空间关系理解（40%，400题）
- D2: 空间推理能力（40%，400题）
- D3: 地理知识融合（20%，200题）

### 7.2 评测指标体系（完整）

#### 7.2.1 性能指标

| 指标 | 计算方式 | 说明 |
|------|---------|------|
| **答案准确率(Acc)** | 完全匹配比例 | 主要评估指标 |
| **空间关系F1** | 关系提取F1值 | 评估关系识别能力 |
| **推理准确率** | 步骤正确比例 | 评估推理链质量 |
| **BLEU** | n-gram重叠 | 文本生成质量 |
| **ROUGE-L** | 最长公共子序列 | 摘要质量 |
| **Perplexity↓** | 困惑度 | 语言流畅性 |

#### 7.2.2 效率指标

| 指标 | 计算方式 | 目标 |
|------|---------|------|
| **推理延迟↓** | ms/query | <50ms |
| **吞吐量↑** | tokens/s | >100 |
| **显存占用↓** | GB | <4GB |
| **压缩比↑** | 参数量比 | 4.7x (7B→1.5B) |

#### 7.2.3 质量指标

| 指标 | 计算方式 | 说明 |
|------|---------|------|
| **多样性** | Distinct-n | 生成多样性 |
| **一致性** | 多次运行一致率 | 稳定性评估 |
| **鲁棒性** | 对抗样本准确率 | 抗干扰能力 |

#### 7.2.4 综合指标

| 指标 | 计算方式 | 说明 |
|------|---------|------|
| **性能-参数比** | Acc/参数量 | 效率评估 |
| **知识保留率** | Student/Teacher Acc | 蒸馏效果 |
| **空间推理增益** | (GeoKD-SR - B2) / B2 | 方法增益 |

### 7.3 LLM辅助评测

#### 7.3.1 GLM-5 API评估设置

```python
# GLM-5 API评估配置
GLM5_EVAL_CONFIG = {
    "model": "glm-5-plus",
    "api_base": "https://open.bigmodel.cn/api/paas/v4/",
    "temperature": 0.3,  # 评估时使用较低温度
    "max_tokens": 1024
}

# GLM-5评估Prompt
EVALUATION_PROMPT = """
你是一个地理空间推理专家。请评估以下答案的质量。

问题: {question}
标准答案: {reference}
模型答案: {prediction}

请从以下维度评分（1-5分）：
1. 准确性：答案是否正确
2. 完整性：是否包含所有必要信息
3. 推理质量：推理过程是否合理
4. 语言流畅性：表达是否清晰

输出JSON格式：
{
  "accuracy": <1-5>,
  "completeness": <1-5>,
  "reasoning_quality": <1-5>,
  "fluency": <1-5>,
  "overall": <1-5>,
  "explanation": "<简要说明>"
}
"""
```

#### 7.3.2 评估采样策略

| 数据类型 | 采样比例 | 数量 |
|---------|---------|------|
| 方向关系 | 10% | 100题 |
| 拓扑关系 | 10% | 80题 |
| 度量关系 | 10% | 60题 |
| 组合推理 | 15% | 60题 |
| **总计** | - | **300题** |

### 7.4 错误案例分析

#### 7.4.1 错误类型分类

| 错误类型 | 描述 | 分析方法 |
|---------|------|---------|
| **空间关系错误** | 方向/拓扑判断错误 | 坐标验证 |
| **实体识别错误** | 地理实体识别错误 | NER评估 |
| **推理链断裂** | 推理步骤逻辑错误 | 逐步验证 |
| **幻觉错误** | 编造不存在的信息 | 事实核查 |
| **格式错误** | 输出格式不规范 | 规则检查 |

#### 7.4.2 案例分析模板

```markdown
### 错误案例 #{id}

**问题**: {question}
**标准答案**: {reference}
**模型输出**: {prediction}
**错误类型**: {error_type}
**错误分析**: {analysis}
**改进建议**: {suggestion}
```

### 7.5 评测脚本设计

```bash
# 完整评测流程
python scripts/evaluate.py \
    --model_path checkpoints/geo_kd_sr/best \
    --benchmark data/geosr_bench/benchmark.json \
    --output_dir results/geo_kd_sr \
    --metrics acc,f1,bleu,rouge \
    --llm_eval glm5  # 启用GLM-5评估
    --error_analysis  # 启用错误分析
    --num_samples 130  # LLM评估采样数
```

---

## 八、实现计划与时间线

### 8.1 文件结构

```
GeoKD-SR/
├── baselines/
│   ├── __init__.py
│   ├── direct_sft.py          # B1: Direct-SFT
│   └── standard_kd.py          # B2: Standard-KD
│
├── models/
│   └── losses/
│       ├── __init__.py
│       ├── spatial_relation_loss.py    # C1: 空间关系蒸馏
│       ├── spatial_cot_loss.py         # C2: 思维链蒸馏
│       ├── spatial_reverse_kl.py       # C3: 逆向KL
│       ├── self_distillation_loss.py   # C4: 自蒸馏损失
│       ├── spatial_attention_distill.py # C5: 空间关系注意力蒸馏
│       ├── progressive_distill.py      # C6: 渐进式蒸馏
│       └── geo_kd_sr_loss.py           # 整合损失
│
├── data/
│   └── geosr_chain/
│       ├── train.jsonl         # 训练数据
│       └── dev.jsonl           # 验证数据
│
└── experiments/
    ├── run_ablation.py         # 消融实验
    └── evaluate.py             # 评测脚本
```

### 8.2 实现优先级

| 优先级 | 组件 | 预计时间 | 对应实验 |
|--------|------|---------|---------|
| P0 | B1: Direct-SFT | 0.5天 | Exp1 |
| P0 | B2: Standard-KD | 0.5天 | Exp2 |
| P0 | C1: 空间关系蒸馏损失 | 0.5天 | Exp3/Exp3a |
| P0 | C2: 思维链蒸馏 | 1天 | Exp4 |
| P0 | C3: 逆向KL蒸馏 | 0.5天 | Exp5 |
| P1 | C4: 自蒸馏损失 | 0.5天 | Exp6 |
| P1 | C5: 空间关系注意力蒸馏 | 0.5天 | Exp7 |
| P1 | C6: 渐进式蒸馏 | 1天 | Exp8 |
| P1 | 整合损失函数 | 0.5天 | Exp9 |

---

### 8.3 实施时间线

```
阶段1: 数据准备 (3月1-2日)
├── GeoSR-Train生成 (8,000条)
├── GeoSR-Dev生成 (800条)
└── 数据质量验证

阶段2: 基线实现 (3月3-5日)
├── B1: Direct-SFT
└── B2: Standard-KD

阶段3: GeoKD-SR组件实现 (3月6-10日)
├── C1: 空间关系蒸馏损失 (0.5天)
├── C2: 思维链蒸馏 (1天)
├── C3: 逆向KL蒸馏 (0.5天)
├── C4: 自蒸馏损失 (0.5天)
├── C5: 空间关系注意力蒸馏 (0.5天)
├── C6: 渐进式蒸馏 (0.5天)
└── 整合损失函数 (0.5天)

阶段4: 实验与消融 (3月11-13日)
├── 基线对比实验 (2组×3次)
├── 消融实验 (10配置×3次)
└── 结果分析与统计检验

阶段5: 论文撰写 (3月14日-8月31日)
├── 实验完善
├── 论文撰写
└── 投稿准备
```

---

## 九、验证方法

### 9.1 代码验证

```bash
# 单元测试
pytest tests/test_losses.py

# 训练验证
python scripts/train.py --method direct_sft --epochs 1
python scripts/train.py --method standard_kd --epochs 1
python scripts/train.py --method geo_kd_sr --epochs 1

# 评测验证
python scripts/evaluate.py --model checkpoints/xxx --benchmark data/geosr_bench/geosr_bench_v1.json
```

### 9.2 实验验证

**成功标准**:
- Exp2 > Exp1: 证明蒸馏有效（预期提升5-10%）
- Exp3a vs Exp2: 验证等权重C1效果
- Exp3 > Exp3a: 验证可学习权重优势
- Exp3 > Exp2: 空间关系蒸馏贡献（预期提升2-3%）
- Exp4 > Exp2: 思维链蒸馏贡献（预期提升3-5%）
- Exp5 > Exp2: 逆向KL贡献（预期提升2-4%）
- Exp6 > Exp2: 自蒸馏损失贡献（预期提升1-2%）
- Exp9 > Exp2: 完整方法优势（预期提升5-8%）

---

## 十、关键决策总结

### 10.1 为什么选择这些组件？

| 组件 | 选择理由 |
|------|---------|
| C1 空间关系蒸馏 | **核心创新**，首次将空间关系类型融入蒸馏 |
| C2 思维链蒸馏 | ACL 2023成熟方法，直接提升推理能力 |
| C3 逆向KL蒸馏 | ICLR 2024权威方法，更适合生成任务 |
| C4 自蒸馏损失 | ICLR 2020自蒸馏技术，不改变训练数据 |
| C5 空间关系注意力蒸馏 | TinyBERT方法，蒸馏空间推理的注意力模式 |
| C6 渐进式蒸馏 | Curriculum Learning经典方法，训练更稳定 |

### 10.2 为什么C4从"合成数据蒸馏"改为"自蒸馏损失"？

| 原C4合成数据蒸馏 | 新C4自蒸馏损失 |
|-------------|----------------------|
| 改变训练数据 | 不改变训练数据，仅改变损失函数 |
| 可能引入数据偏差 | 保持数据公平性 |
| 需要额外数据生成步骤 | 无需额外数据生成 |
| 难以控制数据质量 | 通过EMA保证稳定性 |
| 与数据公平性原则冲突 | 符合消融实验公平性设计 |

### 10.3 为什么新增Exp3a等权重实验？

| 目的 | 说明 |
|------|------|
| 验证C1基础效果 | 等权重[1.0, 1.0, 1.0, 1.0]作为C1的基线 |
| 解耦权重影响 | 对比等权重vs可学习权重的效果差异 |
| 增强消融说服力 | 证明C1的提升来自空间关系类型本身，而非权重调整 |
| 简化实现 | 等权重实现更简单，可作为快速验证 |

### 10.4 为什么不使用其他组件？

| 组件 | 不使用的原因 |
|------|------------|
| 全层注意力蒸馏 | 显存占用大，实现复杂 |
| 对比蒸馏 | 需要构建样本对，复杂度高 |
| Token加权蒸馏 | 缺乏权威支撑，效果不确定 |

### 10.5 实验设计的核心原则

1. **公平性**: 所有方法使用相同数据，避免数据偏差
2. **可控性**: 通过消融实验验证每个组件的独立贡献
3. **科学性**: 不预设权重，通过实验结果决定最终配置
4. **权威性**: 选择有顶会论文支撑的方法

---

## 十一、预期贡献

### 11.1 学术贡献

1. **方法贡献**: 提出6组件的空间关系感知蒸馏框架
2. **核心创新点**:
   - 首次将空间关系类型（方向/拓扑/度量/组合）融入知识蒸馏损失
   - 提出空间关系注意力蒸馏，针对空间实体和关系词的注意力对齐
   - 设计渐进式蒸馏策略，适应空间推理的复杂度层次
3. **实证贡献**: 通过消融实验证明每个组件的独立贡献
4. **应用价值**: 为地理信息领域的知识蒸馏提供参考范式

### 11.2 数据贡献

1. **GeoSR-Chain数据集**: 高质量空间推理蒸馏数据集
2. **GeoSR-Bench评测基准**: 系统的空间推理能力评测框架

---

## 十二、Data and Code Availability

### 12.1 数据可用性声明

为促进学术交流和研究可复现性，本研究将公开以下数据资源：

| 数据集 | 内容 | 规模 | 许可证 | 发布状态 |
|--------|------|------|--------|----------|
| **GeoSR-Chain** | 空间关系推理训练数据集 | 8,000条训练数据 + 800条验证数据 | CC BY-NC 4.0 | 论文接受后公开 |
| **GeoSR-Bench** | 空间推理能力评测基准 | 1,000题测试数据 | CC BY 4.0 | 已公开 |

**数据获取方式**:
- GitHub仓库: `https://github.com/GeoKD-SR/data`
- HuggingFace Dataset: `https://huggingface.co/datasets/GeoKD-SR/GeoSR-Chain`

**数据格式**:
```json
{
  "id": "geosr_xxx",
  "spatial_relation_type": "directional|topological|metric|composite",
  "question": "...",
  "answer": "...",
  "reasoning_chain": [...],
  "entities": [...],
  "spatial_tokens": [...],
  "difficulty": "easy|medium|hard"
}
```

### 12.2 代码可用性声明

| 组件 | 内容 | 许可证 | 发布状态 |
|------|------|--------|----------|
| **GeoKD-SR训练代码** | 完整的训练和蒸馏代码 | MIT | 论文接受后公开 |
| **评测脚本** | GeoSR-Bench评测工具 | MIT | 已公开 |
| **统计分析代码** | 统计检验和多重比较校正 | MIT | 已公开 |

**代码仓库**: `https://github.com/GeoKD-SR/GeoKD-SR`

**环境配置**:
```bash
# 环境依赖
python>=3.12
torch>=2.6.0
transformers>=4.48.0
peft>=0.14.0

# 快速开始
git clone https://github.com/GeoKD-SR/GeoKD-SR.git
cd GeoKD-SR
pip install -r requirements.txt
```

### 12.3 模型权重

| 模型 | 描述 | 发布状态 |
|------|------|----------|
| **GeoKD-SR-1.5B** | 完整训练的GeoKD-SR模型 | 论文接受后公开 |
| **消融实验模型** | Exp1-Exp9各配置的模型 | 论文接受后公开 |

**模型获取**: HuggingFace Hub `https://huggingface.co/GeoKD-SR`

---

## 十三、GIS领域相关工作

### 13.1 空间关系理论基础

空间关系理论是地理信息科学(GIScience)的核心研究领域，主要研究地理实体之间的空间关系形式化表示和推理方法。

**经典理论模型**:

1. **九交模型** (Egenhofer, 1991)
   - 使用九交矩阵描述两个空间对象的拓扑关系
   - 定义了8种基本拓扑关系
   - **应用**: 本研究的C1组件中的拓扑关系权重设计参考此模型

2. **方向关系模型** (Clementini, 1993)
   - 基于投影的方向关系定性描述
   - **应用**: 方向关系权重设计

3. **度量关系** (Worboys, 1993)
   - 距离、面积、周长等定量度量
   - **应用**: 度量关系权重设计

### 13.2 大语言模型与GIS交叉研究

近年来，LLM在地理信息科学领域的应用逐渐成为研究热点：

| 方向 | 代表工作 | 核心贡献 | 相关性 |
|------|---------|---------|--------|
| **空间推理** | GeoLLM (2023) | 使用LLM进行空间关系推理 | 高 |
| **地理问答** | GeoQA (2022) | 地理知识问答数据集 | 中 |
| **地图理解** | MapGPT (2023) | 理解地图图像的LLM | 中 |
| **位置嵌入** | SpaBERT (2021) | 空间感知的预训练模型 | 高 |

### 13.3 知识蒸馏在NLP/GIS中的应用

知识蒸馏技术已广泛应用于自然语言处理和地理信息科学领域：

| 类别 | 代表工作 | 蒸馏策略 | 相关技术 |
|------|---------|---------|---------|
| **通用蒸馏** | DistilBERT (2019) | 蒸馏注意力、隐藏状态 | C5组件 |
| **推理蒸馏** | CoT-Distill (2023) | 蒸馏思维链 | C2组件 |
| **逆向KL** | MiniLLM (2024) | Reverse KL | C3组件 |
| **自蒸馏** | Noisy Student (2020) | 自训练 | C4组件 |

### 13.4 本研究的定位

本研究在相关研究中的定位：

```
GIS空间关系理论 (Egenhofer 1991, Clementini 1993)
                ↓
    空间关系形式化表示与分类
                ↓
    LLM空间推理应用 (GeoLLM 2023, MapGPT 2023)
                ↓
        本工作: GeoKD-SR
    首次将空间关系类型融入知识蒸馏
                ↓
    高效空间推理模型的构建方法
```

**核心创新**:
- 首次将GIS经典空间关系理论（九交模型、方向关系模型等）与知识蒸馏技术结合
- 设计空间关系感知的蒸馏损失，针对不同类型空间关系使用不同权重
- 构建完整的空间关系蒸馏数据集和评测基准

**参考文献**:
- Egenhofer, M. J., & Franzosa, R. D. (1991). Point-set topological spatial relations. IJGIS.
- Clementini, E., Felice, P. D., & Hernandez, D. (1997). Qualitative representation of positional information. AI.
- Cohn, A. G., & Hazarika, S. M. (2001). Qualitative spatial representation and reasoning. ACM TOG.
- Worboys, M. F. (1993). Modeling spatial relationships. IJGIS.
- Jiao, Z., et al. (2020). TinyBERT: Distilling BERT for NLP. EMNLP.
- Gu, A., et al. (2024). MiniLLM: Knowledge Distillation of Large Language Models. ICLR.
- Shridhar, K., et al. (2023). Distilling Reasoning Capabilities into Smaller Models. ACL.

---

**设计版本**: V5.2（统计分析优化版）
**最后更新**: 2026年3月3日
**状态**: 已完成

## 更新日志

### V5.2 (2026-03-03)
- **统计分析优化**:
  - 运行次数从3次扩展到5次，种子集扩展为[42, 123, 456, 789, 1024]
  - 新增6.1.3节：Holm-Bonferroni多重比较校正说明
  - 添加Holm-Bonferroni算法详细说明和实现代码
  - 添加FWER控制原理和算法步骤
- **C1组件GIS理论依据**:
  - 新增GIS理论依据小节
  - 添加Egenhofer 1991九交模型引用
  - 添加Clementini 1993方向关系模型引用
  - 添加Cohn 1997空间认知分类法引用
  - 添加Worboys 1993度量关系定义引用
- **评测方案更新**:
  - LLM评估采样量从130题扩展到300题
  - 更新各类型数据的采样比例和数量
- **模型量化策略**:
  - 新增5.4.1节：模型量化策略
  - 添加4-bit量化选择理由（显存限制、推理速度）
  - 添加全精度选择理由（避免量化损失，保持蒸馏质量）
  - 提供量化切换策略代码示例
- **新增章节**:
  - 十二、Data and Code Availability
  - 十三、GIS领域相关工作
  - 添加空间关系理论基础介绍
  - 添加LLM与GIS交叉研究现状
  - 添加知识蒸馏在NLP/GIS中的应用
  - 明确本研究在相关工作中的定位

### V5.1 (2026-03-03)
- **C1公式优化**:
  - 明确标注为Forward KL（KL(P_T || P_S)，教师分布在前）
  - 添加详细的Forward KL注释说明
- **C2归一化优化**:
  - 添加1/n归一化到思维链蒸馏公式
  - 更新实现代码中的归一化逻辑
- **C4组件重新设计**:
  - 从"合成数据蒸馏"改为"自蒸馏损失"
  - 新设计改变损失函数而非训练数据
  - 添加自蒸馏损失公式和EMA实现
  - 符合数据公平性设计原则
- **C6渐进式蒸馏优化**:
  - 训练阶段从12 epoch压缩为3 epoch
  - 合并度量关系和组合推理为complex阶段
  - 更新阶段映射函数
- **数据生成策略更新**:
  - 明确使用GLM-5 API单独生成数据
  - 添加GLM-5 API配置说明
- **评测方案更新**:
  - 从GPT-4评估改为GLM-5 API评测
  - 添加GLM-5评估配置
- **实验配置扩展**:
  - 新增Exp3a: B2 + C1 (Uniform Weights [1.0, 1.0, 1.0, 1.0])
  - 扩展实验配置表从9个到10个
  - 添加Exp3a相关的验证目标和对比说明
- **教师模型配置更新**:
  - 从Qwen2.5-7B-Instruct改为GLM-5-Plus API

### V5.0 (2026-03-02)
- **数据公平性设计**:
  - 新增4.7节：数据公平性设计（核心）
  - 设计统一数据+选择性字段使用策略
  - 设计统一输入+选择性监督机制
  - 添加数据使用矩阵（9个实验的字段使用情况）
  - 添加各实验输入监督详细设计
  - 添加消融实验公平性保证机制
- **数据规模更新**:
  - 从建议性数据规模改为科学计算确定的8,000条
  - 添加数据量选取的科学分析过程
  - 添加参考文献数据量对比
  - 添加计算资源约束分析
  - 更新数据分配矩阵（按关系类型和难度）
- **验证集更新**: 800条（训练集的10%）

### V4.0 (2026-03-02)
- **新增章节**:
  - 五、模型与环境配置（教师/学生模型、硬件、软件、超参数）
  - 六、实验流程规范（统计规范、随机种子、显著性检验）
  - 七、评测体系设计（完整指标体系、LLM辅助评测、错误分析）
  - 4.6 数据生成与质量控制（种子数据、质量标准、Prompt模板）
- **细化内容**:
  - 训练超参数配置（YAML格式）
  - 组件权重配置
  - 实验重复性规范（3次运行、固定种子集）
  - 评测指标体系（性能/效率/质量/综合）
  - LLM辅助评测设计（GPT-4评估Prompt）
  - 错误案例分析模板
  - 实施时间线
- **章节重组**: 原五-九章顺延为八-十一章

### V3.0 (2026-03-02)
- **C5更新**: 从"指令蒸馏"更改为"空间关系注意力蒸馏"
  - 采用自适应层选择
  - 关注空间实体和空间关系token的注意力对齐
- **公式完善**: 为所有6个组件添加详细的数学公式和实现代码
- **实验配置更新**: 更新Exp7的描述和验证目标
- **数据字段完善**: 添加数据字段详细说明表

### V2.0 (2026-03-02)
- 初始框架设计
- 2个基线方法 + 6个组件
- 9个消融实验配置
