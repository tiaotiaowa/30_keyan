# Exp3a: 空间关系蒸馏（SRD）- 等权重基线

> **实验定位**：C1 组件的**等权重基线**（B2 + C1-Uniform）。
>
> 本实验在 Exp2 的基础上引入**空间关系类型感知**，但使用**固定等权重 1.0**，用于解耦“权重学习”的影响，验证“仅引入空间关系类型这一结构”是否有收益。

**组件标识**：B2 + C1（Uniform Weights）
**V5.2 依据**：§4.7.4（Exp3a 定义），§4.7.6（对比关系）

---

## 1. 目的与假设

### 1.1 实验定位
- **C1 组件基线**：验证空间关系类型结构的独立价值
- **对比对象**：Exp2（标准 KD，无关系类型感知）
- **后续对比**：Exp3（可学习权重）需要对比 Exp3a

### 1.2 控制变量（与 Exp2 完全相同）
- 数据、模型、模板、超参均与 Exp2 相同
- 基础蒸馏框架（Forward KL + hard label）与 Exp2 相同

### 1.3 实验变量（与 Exp2 的差异）
- **新增**：引入 `spatial_relation_type` 字段
- **新增**：按关系类型分组计算 KL
- **差异**：权重固定为 1.0（等权重），不学习

### 1.4 预期结果
- **Exp3a vs Exp2**：验证等权重 C1 是否优于标准 KD
- **Exp3 vs Exp3a**：验证可学习权重是否优于等权重

**V5.2 依据**：§4.7.6 对比表

---

## 2. 理论依据

### 2.1 KD/LLM 蒸馏角度

#### 2.1.1 为什么需要关系类型感知？
空间推理任务中，不同关系类型的**难度**与**重要性**不同：
- **directional**：方向判断，相对简单（8 方向）
- **topological**：拓扑关系，中等难度（5 类）
- **metric**：距离估计，数值推理，较难
- **composite**：组合推理，最复杂

传统 KD 对所有样本一视同仁，未考虑这种**任务结构异质性**。

#### 2.1.2 Exp3a 的设计意图
- **引入结构**：让蒸馏损失“知道”样本属于哪种关系类型
- **等权重基线**：暂不学习权重，仅验证结构本身的价值
- **可解释性**：后续 Exp3 的权重学习可与 Exp3a 对比

### 2.2 地理空间推理角度

#### 2.2.1 GIS 理论依据

**空间关系类型分类**：
| 类型 | GIS 理论 | 典型问题 |
|-----|---------|---------|
| directional | 方向关系模型（如 8 方向） | A 在 B 的哪个方向？ |
| topological | 九交模型（9-Intersection） | A 是否在 B 内部？ |
| metric | 距离度量（欧氏、曼哈顿） | A 与 B 的距离？ |
| composite | 组合推理（方向+距离） | 从 A 到 B 的路线？ |

**V5.2 依据**：§4.7.4 "C1…根据空间关系类型（方向/拓扑/度量/组合）动态加权"

#### 2.2.2 为什么等权重仍有价值？
即使权重相等，**分组计算 KL** 本身带来：
1. **统计隔离**：不同类型的损失不再混淆
2. **诊断能力**：可分析各类型的训练动态
3. **扩展接口**：为 Exp3 的权重学习奠定基础

---

## 3. 方法口径

### 3.1 使用哪些字段

| 字段 | Exp3a 用途 | 说明 |
|-----|----------|-----|
| `question` | 输入 | 转为 user 消息 |
| `answer` | 监督目标（L_hard） | 转为 assistant 消息 |
| **`spatial_relation_type`** | **分组依据** | **新增**：用于按类型加权 KL |

**V5.2 依据**：§4.7.4 字段使用矩阵（Exp3a 行）

### 3.2 输入格式（与 Exp2 相同）
```
System: 你是一个地理空间推理专家...（固定）

User: {question}

Assistant: {answer}
```

### 3.3 损失函数

#### 3.3.1 总损失
```
L = α × L_SRD + (1-α) × L_hard
```
- **α = 0.5**（与 Exp2 相同）
- **差异**：L_SRD 替换 L_soft，按关系类型分组

#### 3.3.2 L_SRD（空间关系蒸馏损失）
```
L_SRD = (1/N) × Σ_{i=1}^{N} w(r_i) × KL(P_T^i || P_S^i)
```
- **r_i**：样本 i 的 `spatial_relation_type`
- **w(r)**：关系类型权重，Exp3a 中**固定为 1.0**
- **N**：batch 中有效 token 数

#### 3.3.3 等权重设定
```python
# Exp3a 等权重
w = {
    "directional": 1.0,
    "topological": 1.0,
    "metric": 1.0,
    "composite": 1.0
}
```

**V5.2 依据**：§4.7.4 "weight = 1.0  # 等权重基线"

### 3.4 训练流程要点

#### 3.4.1 前向传播
```
# 学生前向
student_logits = student(input_ids)

# 教师前向
with torch.no_grad():
    teacher_logits = teacher(input_ids)

# 计算 L_hard（与 Exp2 相同）
loss_hard = CrossEntropy(student_logits[mask], labels[mask])

# 计算 L_SRD（按关系类型分组）
soft_teacher = softmax(teacher_logits / T, dim=-1)
soft_student = softmax(student_logits / T, dim=-1)

# 按 spatial_relation_type 分组
kl_per_token = KL_div(soft_teacher, soft_student)  # [batch, seq_len]
loss_srd = 0
count = 0
for r in ["directional", "topological", "metric", "composite"]:
    mask_r = (relation_type == r) & valid_mask
    if mask_r.any():
        loss_srd += w[r] * kl_per_token[mask_r].sum()
        count += mask_r.sum()
loss_srd = loss_srd / count  # 平均

# 总损失
loss = α × loss_srd + (1-α) × loss_hard
```

#### 3.4.2 关键实现细节
- **relation_type 提取**：从数据集读取，或从 input_ids 推断
- **分组掩码**：对每个关系类型构造 mask
- **有效范围**：valid_mask = (labels != -100) & (attention_mask == 1)

---

## 4. 步骤建议

### 4.1 训练前准备

#### 4.1.1 数据准备（与 Exp2 相同）
- 数据文件：`data/final/final_1_final.jsonl`
- 官方 splits：train/dev/test
- **新增**：确认每条数据包含 `spatial_relation_type` 字段

#### 4.1.2 模型准备（与 Exp2 相同）
- 学生模型：Qwen2.5-1.5B-Instruct
- 教师模型：Qwen2.5-7B-Instruct（4-bit 量化）

#### 4.1.3 Seed 与目录
- Seeds：[42, 123, 456, 789, 1024]（5 次）
- 输出目录：
  ```
  checkpoints/exp03a/{seed}/
  logs/exp03a/{seed}/
  results/exp03a/{seed}/
  ```

### 4.2 训练中监控

#### 4.2.1 关键指标（与 Exp2 对比）
- **loss_hard**：CE 损失
- **loss_srd**：按关系类型加权的 KL 损失
- **loss_total**：总损失
- **各类型 KL**：可选记录 directional/topological/metric/composite 的 KL 分项

#### 4.2.2 每 eval_steps（建议 500）
1. 在验证集上计算：
   - overall_accuracy
   - **分类型 accuracy**（关键！用于诊断 C1 效果）
   - format_valid_rate

#### 4.2.3 异常检测
- **某类型 KL 异常**：可能该类型样本不足或难度异常
- **loss_srd ≈ loss_soft**：验证等权重是否生效（应接近 Exp2 的 loss_soft）

### 4.3 训练后处理

#### 4.3.1 Checkpoint 选择
- **best_model**：验证集准确率最高的 checkpoint

#### 4.3.2 评测执行
1. 在 test set 上生成预测
2. 使用统一评测协议
3. **重点分析**：分类型性能 vs Exp2

#### 4.3.3 与 Exp2 对比
- **主要指标**：overall_accuracy 增幅
- **分层指标**：各关系类型增幅（关键！）
- **统计显著性**：paired t-test / Wilcoxon

---

## 5. 诊断与失败模式

### 5.1 常见陷阱

#### 5.1.1 “关系类型提取错误”
- **陷阱**：`spatial_relation_type` 字段值与实际不匹配
- **诊断**：抽样检查数据的 relation_type 标注
- **后果**：分组错误，权重无效

#### 5.1.2 “等权重未生效”
- **陷阱**：代码中实际使用了可学习权重
- **诊断**：检查权重是否为固定 1.0
- **后果**：与 Exp3 混淆

#### 5.1.3 “某类型样本不足”
- **陷阱**：某类型样本数 < 100，统计不稳定
- **诊断**：检查各类型样本分布
- **后果**：该类型的 KL 估计不准确

### 5.2 性能诊断

| 现象 | 可能原因 | 建议排查 |
|-----|---------|---------|
| Exp3a ≈ Exp2 | 结构无额外价值 | 检查各类型难度是否确实不同 |
| Exp3a < Exp2 | 分组引入噪声 | 检查关系类型标注质量 |
| Exp3a >> Exp2 | 某类型显著改善 | 分析哪类提升最大 |

### 5.3 与 Exp3 的对比意义

| 对比 | 验证假设 |
|-----|---------|
| Exp3 vs Exp3a | 可学习权重是否优于等权重 |
| Exp3 > Exp3a | 权重学习有效，不同类型应不同权重 |
| Exp3 ≈ Exp3a | 权重学习无额外价值，等权重足够 |

---

## 6. 预期结果与论文写作

### 6.1 预期性能范围
- **vs Exp2**：预期小幅提升（1-2%），或不显著
- **分类型**：可能某些类型提升，某些持平

### 6.2 论文写作建议

#### 6.2.1 Methods 章节
```
Exp3a (SRD-Uniform) 在标准 KD 的基础上引入空间关系类型感知，
将 KL 损失按样本的 spatial_relation_type 分组计算：

L_SRD = (1/N) × Σ_{i} w(r_i) × KL(P_T^i || P_S^i)

其中 w(r) 为关系类型权重。在 Exp3a 中，我们设置等权重
w(directional) = w(topological) = w(metric) = w(composite) = 1.0，
作为 C1 组件的基线，用于解耦权重学习的影响。
```

#### 6.2.2 Experiments 章节
```
表X：各实验在 GeoKD-SR 测试集上的性能（均值±标准差）

| 实验 | Overall | Directional | Topological | Metric | Composite |
|-----|---------|------------|-------------|--------|-----------|
| Exp2 (KD) | XX.X±X.X | ... | ... | ... | ... |
| Exp3a (SRD-U) | YY.Y±Y.Y | ... | ... | ... | ... |
| Exp3 (SRD-L) | ... | ... | ... | ... | ... |
...
```

#### 6.2.3 Ablation 讨论
```
Exp3a 相比 Exp2 在 overall accuracy 上提升了 Z.Z%（p > 0.05），
表明等权重空间关系感知带来的收益有限。然而，分类型分析显示，
[某类型] 的性能有显著提升，说明空间关系类型结构确实有价值，
但需要更精细的权重分配（见 Exp3）。
```

---

## 7. V5.2 引用定位

| 内容 | V5.2 位置 |
|-----|-----------|
| Exp3a 定义 | §4.7.4 表格（Exp3a 行） |
| 等权重设定 | §4.7.4 "weight = 1.0  # 等权重基线" |
| C1 组件说明 | §4.7.4 "C1…根据空间关系类型动态加权" |
| 对比关系 Exp3a vs Exp2 | §4.7.6 "Exp3a vs Exp2：C1等权重是否优于标准KD" |
| 对比关系 Exp3 vs Exp3a | §4.7.6 "Exp3 vs Exp3a：可学习权重是否优于等权重" |

---

## 8. 与后续实验的关系

Exp3a 是以下实验的关键对照：
- **Exp3 vs Exp3a**：验证可学习权重的价值
- **Exp3a vs Exp2**：验证空间关系类型结构的价值

**设计意图**（V5.2 说明）：
> "为什么新增Exp3a…等权重[1.0,1.0,1.0,1.0]作为C1的基线…解耦权重影响"

**V5.2 依据**：约第1788–1794行

---

*本文档由 Claude Code 生成，基于 GeoKD-SR 实验设计方案 V5.2。*
