# Exp5: 逆向 KL 蒸馏（Reverse KL Distillation）

> **实验定位**：C3 组件的实现（B2 + C3）。
>
> 本实验在 Exp2 的基础上将 **Forward KL 改为 Reverse KL**，即 `KL(学生分布 || 教师分布)`，目标是验证 mode-seeking 对生成任务的适用性，并减少幻觉。

**组件标识**：B2 + C3（Reverse KL）
**V5.2 依据**：§4.7.4（Exp5 定义），§4.7.6（对比关系）

---

## 1. 目的与假设

### 1.1 实验定位
- **C3 组件实现**：验证逆向 KL 在空间推理生成任务中的价值
- **对比对象**：Exp2（标准 KD，Forward KL）

### 1.2 控制变量（与 Exp2 完全相同）
- 数据、模型、模板、超参均相同
- **唯一差异**：KL 方向改变

### 1.3 实验变量（与 Exp2 的唯一差异）
- **KL 方向**：从 `KL(P_T || P_S)` 改为 `KL(P_S || P_T)`

### 1.4 预期结果
- **Exp5 > Exp2**：逆向 KL 更适合生成任务，幻觉更少
- **预期提升**：相比 Exp2 提升 2-4%

**V5.2 依据**：§4.7.6 "成功标准…Exp5 > Exp2…预期提升2-4%"

---

## 2. 理论依据

### 2.1 KD/LLM 蒸馏角度

#### 2.1.1 Forward KL vs Reverse KL

| 属性 | Forward KL | Reverse KL |
|-----|-----------|-----------|
| 公式 | KL(P_T \|\| P_S) | KL(P_S \|\| P_T) |
| 行为 | mode-covering | mode-seeking |
| 目标 | 覆盖教师的所有模式 | 聚焦教师的高概率模式 |
| 适用 | 分类任务 | 生成任务 |

**Forward KL（mode-covering）**：
```
KL(P_T || P_S) = Σ P_T(x) log(P_T(x) / P_S(x))
```
- **鼓励**：学生覆盖教师的所有概率模式
- **风险**：可能过度拟合教师的低概率模式（噪声）

**Reverse KL（mode-seeking）**：
```
KL(P_S || P_T) = Σ P_S(x) log(P_S(x) / P_T(x))
```
- **鼓励**：学生聚焦教师的高概率模式（mode）
- **优势**：减少对教师噪声的拟合，降低幻觉

#### 2.1.2 为什么生成任务更适合 Reverse KL？

**生成任务的特点**：
- **输出空间大**：词汇表数万 tokens，大部分低概率
- **长尾噪声**：教师的低概率区域可能包含噪声
- **幻觉风险**：mode-covering 可能放大幻觉模式

**Reverse KL 的优势**：
- **聚焦高置信度**：只学习教师“确定”的模式
- **抑制幻觉**：避免学习教师的低概率噪声
- **稳定性**：训练更稳定，不容易受离群值影响

**V5.2 依据**：§4.7.4 "C3: 逆向KL蒸馏…Reverse KL更适合生成任务，减少幻觉"

### 2.2 地理空间推理角度

#### 2.2.1 Geo 任务中的幻觉类型

| 幻觉类型 | 示例 | Forward KL 风险 | Reverse KL 优势 |
|---------|------|---------------|--------------|
| 方向幻觉 | "东北"→"正北" | 学习错误模式 | 聚焦高置信方向 |
| 拓扑幻觉 | "contains"→"overlaps" | 学习模糊边界 | 聚焦典型拓扑 |
| 距离幻觉 | 距离数量级错误 | 学习数值噪声 | 聚焦典型距离 |
| 实体幻觉 | 生成不存在实体 | 学习教师幻觉 | 抑制低概率实体 |

#### 2.2.2 空间推理的高置信度模式
- **方向**：8 个主方向（东/南/西/北/东北/...）是高置信度
- **拓扑**：5 类拓扑关系（within/contains/...）是典型模式
- **距离**：常见距离范围（如城市间 10-1000km）是高概率区域

Reverse KL 聚焦这些**典型模式**，避免学习噪声。

---

## 3. 方法口径

### 3.1 使用哪些字段

| 字段 | Exp5 用途 | 说明 |
|-----|----------|-----|
| `question` | 输入 | 转为 user 消息 |
| `answer` | 监督目标（L_hard） | 转为 assistant 消息 |

**与 Exp2 完全相同**

**V5.2 依据**：§4.7.4 字段使用矩阵（Exp5 行）

### 3.2 输入格式（与 Exp2 相同）
```
System: 你是一个地理空间推理专家...（固定）

User: {question}

Assistant: {answer}
```

### 3.3 损失函数

#### 3.3.1 总损失
```
L = α × L_RKL + (1-α) × L_hard
```
- **α = 0.5**（与 Exp2 相同）
- **差异**：L_RKL 替换 L_soft

#### 3.3.2 L_RKL（逆向 KL 损失）
```
L_RKL = T² × KL(P_S^T || P_T^T)
      = T² × Σ P_S^T(x) log(P_S^T(x) / P_T^T(x))
```
- **P_S^T**：学生 logit 除以 T 后的 softmax
- **P_T^T**：教师 logit 除以 T 后的 softmax
- **关键差异**：学生分布在前，教师分布在后
- **T² 因子**：补偿梯度缩放

**V5.2 依据**：§4.7.4 "L_RKL = KL(P_S || P_S)…仅KL方向改变"

#### 3.3.3 梯度方向对比

| KL 方向 | 梯度主要受 | 优化目标 |
|--------|----------|---------|
| Forward KL | 教师高概率区域 | 让学生在教师“可能”的地方也高概率 |
| Reverse KL | 学生高概率区域 | 让学生在自己“高概率”的地方更接近教师 |

### 3.4 训练流程要点

#### 3.4.1 前向传播
```python
# 学生前向
student_logits = student(input_ids)  # [batch, seq_len, vocab]

# 教师前向
with torch.no_grad():
    teacher_logits = teacher(input_ids)

# 计算 L_hard
loss_hard = CrossEntropy(student_logits[mask], labels[mask])

# 计算 L_RKL（Reverse KL）
soft_student = softmax(student_logits / T, dim=-1)
soft_teacher = softmax(teacher_logits / T, dim=-1)

# Reverse KL：学生分布在前
loss_rkl = T² × (soft_student[mask] * (log(soft_student[mask]) - log(soft_teacher[mask]))).sum() / mask.sum()

# 总损失
loss = α × loss_rkl + (1-α) × loss_hard
```

#### 3.4.2 关键实现细节
- **梯度计算**：Reverse KL 对学生梯度的计算与 Forward KL 不同
- **数值稳定**：log(soft_teacher) 可能有 -inf（teacher 概率=0），需要 clamp
- **mask 范围**：valid_mask = (labels != -100) & (attention_mask == 1)

#### 4.4.3 数值稳定性处理
```python
# 防止 log(0)
eps = 1e-8
soft_teacher = soft_teacher.clamp(min=eps)
soft_student = soft_student.clamp(min=eps)

# Reverse KL
loss_rkl = T² × (soft_student * (log(soft_student) - log(soft_teacher))).sum() / N
```

---

## 4. 步骤建议

### 4.1 训练前准备

#### 4.1.1 数据准备（与 Exp2 相同）
- 数据文件：`data/final/final_1_final.jsonl`
- 官方 splits：train/dev/test

#### 4.1.2 模型准备（与 Exp2 相同）
- 学生模型：Qwen2.5-1.5B-Instruct
- 教师模型：Qwen2.5-7B-Instruct（4-bit 量化）

#### 4.1.3 Seed 与目录
- Seeds：[42, 123, 456, 789, 1024]（5 次）
- 输出目录：
  ```
  checkpoints/exp05/{seed}/
  logs/exp05/{seed}/
  results/exp05/{seed}/
  ```

### 4.2 训练中监控

#### 4.2.1 关键指标（与 Exp2 对比）
- **loss_hard**：CE 损失
- **loss_rkl**：Reverse KL 损失
- **loss_total**：总损失

#### 4.2.2 每 eval_steps（建议 500）
1. 在验证集上计算：
   - overall_accuracy
   - 分类型 accuracy
   - format_valid_rate
   - **幻觉率**（可选）：统计生成中的实体幻觉、方向幻觉等

#### 4.2.3 异常检测
- **loss_rkl 爆炸**：检查数值稳定性（log(0) 问题）
- **loss_rkl ≈ 0**：可能学生已经完美匹配教师（过拟合）
- **生成质量下降**：检查温度设置

### 4.3 训练后处理

#### 4.3.1 Checkpoint 选择
- **best_model**：验证集准确率最高的 checkpoint

#### 4.3.2 评测执行
1. 在 test set 上生成预测
2. 使用统一评测协议
3. **新增**：幻觉分析
   - 实体幻觉率
   - 方向幻觉率
   - 拓扑混淆率

#### 4.3.3 与 Exp2 对比
- **主要指标**：overall_accuracy 增幅
- **幻觉指标**：幻觉率降低幅度
- **分类型**：各关系类型的幻觉变化

---

## 5. 诊断与失败模式

### 5.1 常见陷阱

#### 5.1.1 "数值不稳定"
- **陷阱**：Reverse KL 中 log(soft_teacher) 可能有 -inf
- **诊断**：检查是否有 NaN 损失
- **解决**：添加 epsilon clamp

#### 5.1.2 "mode 塌缩"
- **陷阱**：学生分布塌缩到单一 mode
- **可能原因**：
  - Reverse KL 的 mode-seeking 特性
  - 温度过低
- **后果**：输出多样性下降

#### 5.1.3 "与 Exp2 差异不大"
- **陷阱**：Reverse KL 与 Forward KL 结果相似
- **可能原因**：
  - 教师分布已经很集中
  - 任务本身不需要 mode-seeking
- **诊断**：分析教师分布的熵

### 5.2 性能诊断

| 现象 | 可能原因 | 建议排查 |
|-----|---------|---------|
| Exp5 > Exp2 | Reverse KL 有效 | 分析幻觉率下降 |
| Exp5 ≈ Exp2 | KL 方向影响小 | 检查任务特点 |
| Exp5 < Exp2 | mode-seeking 不适用 | 检查温度、权重 |
| Exp5 准确率高但多样性低 | mode 塌缩 | 增加温度或调整 α |

### 5.3 幻觉分析

| 幻觉类型 | Exp5 vs Exp2 预期 | 诊断方法 |
|---------|------------------|---------|
| 实体幻觉 | ↓（减少） | 统计生成中不存在实体 |
| 方向幻觉 | ↓ | 统计非 8 方向输出 |
| 拓扑幻觉 | ↓ | 统计非 5 类拓扑输出 |
| 距离幻觉 | ↓ | 统计极端距离值 |

---

## 6. 预期结果与论文写作

### 6.1 预期性能范围
- **vs Exp2**：预期提升 2-4%
- **幻觉率**：预期降低 10-20%

### 6.2 论文写作建议

#### 6.2.1 Methods 章节
```
Exp5 (Reverse KL) 在标准 KD 的基础上将 Forward KL 改为 Reverse KL：

L_RKL = T² × KL(P_S^T || P_T^T)

与 Forward KL（mode-covering）不同，Reverse KL（mode-seeking）聚焦
教师的高置信度模式，避免学习教师的低概率噪声。我们在空间推理
任务中假设 Reverse KL 能减少幻觉（如错误实体、方向混淆等），
因为生成任务的输出空间大，教师的低概率区域可能包含噪声。
```

#### 6.2.2 Experiments 章节
```
表X：各实验在 GeoKD-SR 测试集上的性能（均值±标准差）

| 实验 | Overall Acc | 幻觉率 | Direction Acc | Topology Acc |
|-----|------------|-------|--------------|--------------|
| Exp2 (Forward KL) | XX.X±X.X | A.A% | ... | ... |
| Exp5 (Reverse KL) | YY.Y±Y.Y | B.B% | ... | ... |
...
```

#### 6.2.3 Ablation 讨论
```
Exp5 相比 Exp2 提升了 Z.Z%（p < 0.05），同时幻觉率降低了 W.W%，
验证了 Reverse KL 在空间推理生成任务中的有效性。我们分析发现，
Reverse KL 聚焦教师的高置信度模式（如 8 个主方向、5 类拓扑关系），
避免学习教师的低概率噪声（如方向细微差异、拓扑边界模糊），从而
减少了幻觉生成。特别是在 composite 类型中，Exp5 的幻觉率降低
最显著（X.X% → Y.Y%），说明复杂推理任务最受益于 mode-seeking。
```

#### 6.2.4 案例分析（建议）
```
表Y：Exp2 与 Exp5 的幻觉案例对比

| 问题 | Exp2 输出 | Exp5 输出 | 分析 |
|-----|----------|----------|------|
| A相对B的方向？ | "正北偏东5°" | "东北" | Exp2 产生细粒度幻觉 |
| A与B的关系？ | "部分重叠" | "相邻" | Exp2 产生拓扑幻觉 |
```

---

## 7. V5.2 引用定位

| 内容 | V5.2 位置 |
|-----|-----------|
| Exp5 定义 | §4.7.4 表格（Exp5 行） |
| C3 组件说明 | §4.7.4 "C3: 逆向KL蒸馏…Reverse KL更适合生成任务" |
| 损失函数 | §4.7.4 "L_RKL = KL(P_S || P_T)" |
| mode-covering vs mode-seeking | §4.7.4 "Forward KL vs Reverse KL" |
| 对比关系 Exp5 vs Exp2 | §4.7.6 "Exp5 vs Exp2：逆向KL蒸馏的贡献" |
| 成功标准 | §4.7.6 "成功标准…Exp5 > Exp2…预期提升2-4%" |

---

## 8. 理论补充：Forward vs Reverse KL 的几何直觉

### 8.1 概率分布视角

```
教师分布 P_T：
  高概率：东、南、西、北、东北、东南、西北、西南
  低概率：其他所有方向（噪声）

Forward KL KL(P_T || P_S)：
  目标：让 P_S 在所有 P_T > 0 的地方都 > 0
  风险：学习 P_T 的低概率噪声

Reverse KL KL(P_S || P_T)：
  目标：让 P_S 的高概率区域与 P_T 的高概率区域对齐
  优势：忽略 P_T 的低概率噪声
```

### 8.2 优化动态

| 优化阶段 | Forward KL | Reverse KL |
|---------|-----------|-----------|
| 早期 | 学生快速覆盖教师模式 | 学生快速聚焦教师主 mode |
| 中期 | 继续覆盖教师长尾 | 精细调整 mode 位置 |
| 后期 | 可能过拟合噪声 | 稳定在高概率 mode |

---

*本文档由 Claude Code 生成，基于 GeoKD-SR 实验设计方案 V5.2。*
