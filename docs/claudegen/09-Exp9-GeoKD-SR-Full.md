# Exp9: GeoKD-SR 完整方法（Full Method）

> **实验定位**：完整方法，组合所有有效组件（B2 + C1 + C2 + C3 + C4 + C5 + C6）。
>
> 本实验组合所有组件（空间关系蒸馏、思维链蒸馏、逆向 KL、自蒸馏、注意力对齐、渐进式训练），验证完整方法的优势与组件协同效应。

**组件标识**：B2 + C1 + C2 + C3 + C4 + C5 + C6（Full GeoKD-SR）
**V5.2 依据**：§4.7.4（Exp9 定义），§4.7.6（对比关系）

---

## 1. 目的与假设

### 1.1 实验定位
- **完整方法**：GeoKD-SR 的最终实现
- **对比对象**：
  - **Exp2**：验证完整方法 vs 标准KD
  - **Exp3–Exp8**：验证组件组合的协同效应

### 1.2 控制变量（与 Exp2 相同）
- 数据、模型、模板、基础超参均相同

### 1.3 实验变量（与 Exp2 的差异）
- **同时启用**：C1（SRD）、C2（CoT）、C3（Reverse KL）、C4（Self-distill）、C5（Attention）、C6（Progressive）

### 1.4 预期结果
- **Exp9 > Exp2**：完整方法整体优势
- **Exp9 > Exp3–Exp8**：存在协同效应而非简单叠加
- **预期提升**：相比 Exp2 提升 5-8%

**V5.2 依据**：§4.7.6 "成功标准…Exp9 > Exp2…预期提升5-8%"

---

## 2. 理论依据

### 2.1 KD/LLM 蒸馏角度

#### 2.1.1 为什么组合多个组件？
**不同组件的互补性**：

| 组件 | 主要贡献 | 解决的问题 |
|-----|---------|-----------|
| C1 (SRD) | 关系类型感知 | 不同难度类型需要不同监督强度 |
| C2 (CoT) | 推理过程监督 | 学会推理步骤而非仅答案 |
| C3 (Reverse KL) | mode-seeking | 减少幻觉，聚焦高置信度模式 |
| C4 (Self-distill) | 时间一致性 | 稳定预测，减少波动 |
| C5 (Attention) | 中间特征对齐 | 学习空间推理的结构知识 |
| C6 (Progressive) | 课程学习 | 从简单到复杂渐进学习 |

#### 2.1.2 协同效应假设
**正向协同**：
- C1 + C6：按难度渐进 + 按类型加权 = 更精细的课程
- C2 + C5：推理链监督 + 注意力对齐 = 更完整的中间信号
- C3 + C4：mode-seeking + 时间一致性 = 更稳定的预测

**潜在风险**：
- 过度正则：多个损失可能拉扯优化方向
- 超参敏感：需要精细调参

### 2.2 地理空间推理角度

#### 2.2.1 完整空间推理 pipeline

```
输入：问题（包含空间实体）
  ↓
[C6] 课程调度：按难度分配样本
  ↓
[C1] 关系类型识别：directional/topological/metric/composite
  ↓
[C2] 推理链生成：
  - 步骤1：识别实体 [C5 注意力聚焦]
  - 步骤2：获取坐标/关系
  - 步骤3：计算/推理
  - 步骤4：综合判断
  - 步骤5：得出结论
  ↓
[C3] 生成预测：mode-seeking（聚焦高置信度）
  ↓
[C4] 时间一致性：EMA 约束
  ↓
输出：结构化答案 + 推理链
```

#### 2.2.2 各组件的 Geo 协同

| 组件组合 | Geo 协同效应 |
|---------|-------------|
| C1 + C6 | 按难度渐进 + 按类型加权 = 精细化课程 |
| C2 + C5 | 推理链 + 注意力 = 完整中间信号 |
| C3 + C4 | mode-seeking + 一致性 = 低幻觉高稳定 |
| C1 + C2 | 类型感知 + 推理链 = 分类型推理学习 |

---

## 3. 方法口径

### 3.1 使用哪些字段

| 字段 | Exp9 用途 | 使用组件 |
|-----|----------|---------|
| `question` | 输入 | 全部 |
| `answer` | 监督目标（L_hard） | 全部 |
| **`reasoning_chain`** | **推理链监督（L_chain）** | C2 |
| **`spatial_relation_type`** | **关系类型加权（L_SRD）** | C1, C6 |
| **`entities`** | **注意力掩码（L_attn）** | C5 |
| **`entity_to_token`** | **token 对齐** | C5 |

**V5.2 依据**：§4.7.4 字段使用矩阵（Exp9 行："所有字段"）

### 3.2 输入格式
```
System: 你是一个地理空间推理专家...（固定）

User: 请逐步分析以下地理问题：{question}

Assistant: {reasoning_chain}

最终答案：{answer}
```

**整合了 C2 的 CoT 指令**

### 3.3 损失函数（完整公式）

#### 3.3.1 总损失
```
L = w_hard × L_hard
  + w_srd × L_SRD
  + w_scot × L_SCOT
  + w_rkl × L_RKL
  + w_self × L_consistency
  + w_attn × L_attn
```

**V5.2 依据**：§4.7.4 "loss_weights: hard_label 0.3, srd 0.25, scot 0.20, rkl 0.15, self_distill 0.05, attention 0.03, progressive 0.02"

#### 3.3.2 权重配置（Exp9）

| 损失项 | 权重 | 组件 | 说明 |
|-------|------|------|------|
| L_hard | 0.30 | B2 | 硬标签监督（锚定） |
| L_SRD | 0.25 | C1 | 空间关系蒸馏（可学习权重） |
| L_SCOT | 0.20 | C2 | 思维链蒸馏 |
| L_RKL | 0.15 | C3 | 逆向 KL |
| L_consistency | 0.05 | C4 | 自蒸馏一致性 |
| L_attn | 0.03 | C5 | 注意力对齐 |
| **总计** | **1.00** | - | **归一化** |

**V5.2 依据**：§4.7.4 约第1101-1110行

#### 3.3.3 各损失项定义

**L_hard**：
```
L_hard = CrossEntropy(student_logits, labels)
```

**L_SRD**（C1）：
```
L_SRD = (1/N) × Σ_i w(r_i) × KL(P_T^i || P_S^i)
```
- w(r)：可学习关系类型权重

**L_SCOT**（C2）：
```
L_SCOT = α × L_chain + (1-α) × L_answer
```
- α = 0.6

**L_RKL**（C3）：
```
L_RKL = T² × KL(P_S^T || P_T^T)
```
- Reverse KL

**L_consistency**（C4）：
```
L_consistency = KL(P_S^current || P_S^EMA)
```

**L_attn**（C5）：
```
L_attn = Σ_{l∈layers} λ_l × MSE(A_S^(l), A_T^(l)) ⊙ M_entity
```

#### 3.3.4 课程调度（C6）
```
Epoch 1: directional（权重1.0）
Epoch 2: topological（权重1.0）+ directional复习（权重0.3）
Epoch 3: metric（权重1.0）+ composite（权重1.0）
```

### 3.4 训练流程要点

#### 3.4.1 初始化
```python
# 模型
student = StudentModel()
teacher = TeacherModel()  # 冻结
ema_student = StudentModel()  # EMA
ema_student.load_state_dict(student.state_dict())

# C1 可学习权重
θ = {"directional": log(1.5), "topological": log(1.3), ...}

# C5 层权重
λ_layers = [1/6] * 6  # 最后 6 层
```

#### 3.4.2 前向传播
```python
# 学生前向
student_outputs = student(input_ids, output_attentions=True)
student_logits = student_outputs.logits
student_attentions = student_outputs.attentions

# 教师前向
with torch.no_grad():
    teacher_outputs = teacher(input_ids)
    teacher_logits = teacher_outputs.logits

# EMA 学生前向
with torch.no_grad():
    ema_outputs = ema_student(input_ids)
    ema_logits = ema_outputs.logits

# 计算各项损失
L_hard = CrossEntropy(student_logits[mask], labels[mask])
L_SRD = compute_srd_loss(...)
L_SCOT = compute_scot_loss(...)
L_RKL = compute_rkl_loss(...)
L_consistency = KL(soft_student, soft_ema)
L_attn = compute_attn_loss(...)

# 总损失
L = (w_hard × L_hard
   + w_srd × L_SRD
   + w_scot × L_SCOT
   + w_rkl × L_RKL
   + w_self × L_consistency
   + w_attn × L_attn)
```

#### 3.4.3 反向传播与更新
```python
# 反向传播
L.backward()
optimizer.step()

# EMA 更新
for param, ema_param in zip(student.parameters(), ema_student.parameters()):
    ema_param.data = μ × ema_param.data + (1-μ) × param.data
```

---

## 4. 步骤建议

### 4.1 训练前准备

#### 4.1.1 数据准备（完整字段）
- 数据文件：`data/final/final_1_final.jsonl`
- 确认包含所有必需字段：
  - `question`, `answer`
  - `reasoning_chain`
  - `spatial_relation_type`
  - `entities`, `entity_to_token`

#### 4.1.2 权重配置
```python
loss_weights = {
    "hard_label": 0.30,
    "srd": 0.25,
    "scot": 0.20,
    "rkl": 0.15,
    "self_distill": 0.05,
    "attention": 0.03
}
```

#### 4.1.3 Seed 与目录
- Seeds：[42, 123, 456, 789, 1024]（5 次）
- 输出目录：
  ```
  checkpoints/exp09/{seed}/
  logs/exp09/{seed}/
  results/exp09/{seed}/
  ```

### 4.2 训练中监控

#### 4.2.1 关键指标（多损失分项）
- **L_hard**：硬标签损失
- **L_SRD**：空间关系蒸馏损失
- **L_SCOT**：思维链损失
- **L_RKL**：逆向 KL 损失
- **L_consistency**：自蒸馏一致性损失
- **L_attn**：注意力对齐损失
- **L_total**：总损失

#### 4.2.2 每 eval_steps（建议 500）
1. 在验证集上计算：
   - overall_accuracy
   - 分类型 accuracy
   - format_valid_rate
2. 记录各损失项，诊断平衡

#### 4.2.3 异常检测
- **某损失项主导**：检查权重设置
- **损失项震荡**：检查学习率
- **显存不足**：考虑梯度检查点或减少批大小

### 4.3 训练后处理

#### 4.3.1 Checkpoint 选择
- **best_model**：验证集准确率最高的 checkpoint

#### 4.3.2 评测执行
1. 在 test set 上生成预测
2. 使用统一评测协议
3. **消融分析**：对比各组件的贡献

#### 4.3.3 与 Exp2–Exp8 对比
- **主指标**：overall_accuracy 增幅
- **协同分析**：是否大于各组件单独提升之和
- **分类型**：各关系类型的性能变化

---

## 5. 诊断与失败模式

### 5.1 常见陷阱

#### 5.1.1 "过度正则"
- **陷阱**：多个损失项拉扯优化方向
- **表现**：训练缓慢或收敛差
- **解决**：调整权重，减少次要项

#### 5.1.2 "组件冲突"
- **陷阱**：某些组件的效应相互抵消
- **表现**：Exp9 < ExpX（某个单组件）
- **诊断**：逐个添加组件，定位冲突

#### 5.1.3 "超参敏感"
- **陷阱**：权重配置不优
- **表现**：性能波动大
- **建议**：网格搜索或贝叶斯优化

### 5.2 性能诊断

| 现象 | 可能原因 | 建议排查 |
|-----|---------|---------|
| Exp9 >> Exp2 | 强协同效应 | 分析各组件贡献 |
| Exp9 ≈ max(Exp3-8) | 无协同，最好组件主导 | 检查是否有负协同 |
| Exp9 < max(Exp3-8) | 负协同，组件冲突 | 逐个消融定位 |
| Exp9 ≈ Exp2 | 所有组件无效 | 检查实现正确性 |

### 5.3 消融分析

| 移除组件 | 预期影响 | 诊断 |
|---------|---------|------|
| 移除 C1 | 关系类型性能下降 | 验证 C1 贡献 |
| 移除 C2 | 复杂推理性能下降 | 验证 C2 贡献 |
| 移除 C3 | 幻觉率上升 | 验证 C3 贡献 |
| 移除 C4 | 稳定性下降 | 验证 C4 贡献 |
| 移除 C5 | 中间特征性能下降 | 验证 C5 贡献 |
| 移除 C6 | 早期性能下降 | 验证 C6 贡献 |

---

## 6. 预期结果与论文写作

### 6.1 预期性能范围
- **vs Exp2**：预期提升 5-8%
- **vs Exp3–Exp8**：预期大于任何单组件

### 6.2 论文写作建议

#### 6.2.1 Methods 章节
```
Exp9 (GeoKD-SR Full) 组合了所有有效组件：

L = w_hard × L_hard
  + w_srd × L_SRD         [C1: 空间关系蒸馏]
  + w_scot × L_SCOT        [C2: 思维链蒸馏]
  + w_rkl × L_RKL          [C3: 逆向 KL]
  + w_self × L_consistency [C4: 自蒸馏]
  + w_attn × L_attn        [C5: 注意力对齐]

并采用渐进式训练调度 [C6]。权重配置为：
hard_label=0.30, srd=0.25, scot=0.20, rkl=0.15,
self_distill=0.05, attention=0.03。

各组件协同作用：C1+C6 提供精细化课程，C2+C5 提供完整中间信号，
C3+C4 保证低幻觉高稳定。
```

#### 6.2.2 Experiments 章节
```
表X：各实验在 GeoKD-SR 测试集上的性能（均值±标准差）

| 实验 | Overall | Directional | Topological | Metric | Composite |
|-----|---------|------------|-------------|--------|-----------|
| Exp2 (KD) | XX.X±X.X | ... | ... | ... | ... |
| Exp3 (SRD) | ... | ... | ... | ... | ... |
| Exp4 (CoT) | ... | ... | ... | ... | ... |
| Exp5 (RKL) | ... | ... | ... | ... | ... |
| Exp6 (Self) | ... | ... | ... | ... | ... |
| Exp7 (Attn) | ... | ... | ... | ... | ... |
| Exp8 (Prog) | ... | ... | ... | ... | ... |
| Exp9 (Full) | ZZ.Z±Z.Z | ... | ... | ... | ... |
```

#### 6.2.3 Ablation 讨论
```
Exp9 相比 Exp2 提升了 Y.Y%（p < 0.001），优于任何单组件实验
（Exp3-Exp8 最高提升 X.X%），验证了组件间的协同效应。
消融分析显示：
- 移除 C1 导致 overall accuracy 下降 A.A%
- 移除 C2 导致 composite 类型下降 B.B%
- 移除 C3 导致幻觉率上升 C.C%
...

协同效应主要体现在：C1（关系类型感知）与 C6（课程学习）结合，
实现了按难度和类型的精细化课程；C2（推理链）与 C5（注意力）结合，
提供了完整的中间信号监督。
```

#### 6.2.4 组件贡献排序
```
图X：Exp9 各组件的消融分析。X 轴为移除组件，Y 轴为性能下降。
C1（SRD）和 C2（CoT）的贡献最大，C3（RKL）次之，C4-C6 的
贡献较小但稳定。这表明空间关系感知和推理链学习是 GeoKD-SR
的核心，而其他组件提供了必要的正则化和稳定性。
```

---

## 7. V5.2 引用定位

| 内容 | V5.2 位置 |
|-----|-----------|
| Exp9 定义 | §4.7.4 表格（Exp9 行） |
| 损失权重配置 | §4.7.4 "loss_weights: hard_label 0.3, srd 0.25, ..." |
| 关系权重 | §4.7.4 "relation_weights…directional 1.5…" |
| 对比关系 Exp9 vs Exp2 | §4.7.6 "Exp9 vs Exp2：完整方法整体优势" |
| 对比关系 Exp9 vs Exp3-8 | §4.7.6 "Exp9 vs Exp3-8：组件组合的协同效应" |
| 成功标准 | §4.7.6 "成功标准…Exp9 > Exp2…预期提升5-8%" |

---

## 8. 超参数敏感性

| 超参数 | 当前值 | 建议搜索空间 |
|-------|-------|------------|
| w_hard | 0.30 | {0.2, 0.3, 0.4} |
| w_srd | 0.25 | {0.15, 0.25, 0.35} |
| w_scot | 0.20 | {0.1, 0.2, 0.3} |
| w_rkl | 0.15 | {0.1, 0.15, 0.2} |
| w_self | 0.05 | {0.03, 0.05, 0.1} |
| w_attn | 0.03 | {0.01, 0.03, 0.05} |

---

## 9. 实现检查清单

### 9.1 数据完整性
- [ ] `question`, `answer` 字段存在
- [ ] `reasoning_chain` 字段存在（5 步）
- [ ] `spatial_relation_type` 字段存在
- [ ] `entities`, `entity_to_token` 字段存在

### 9.2 组件实现
- [ ] C1: 可学习权重 w(r) 实现并优化
- [ ] C2: L_chain 分步计算正确
- [ ] C3: Reverse KL 方向正确
- [ ] C4: EMA 更新正确
- [ ] C5: 注意力输出启用
- [ ] C6: 课程采样实现

### 9.3 损失平衡
- [ ] 各损失项权重和为 1
- [ ] 各损失项数量级相近（避免某项主导）
- [ ] 梯度检查（各项梯度正常）

### 9.4 评测准备
- [ ] 统一评测协议（强制 JSON 块）
- [ ] 分层统计（按 relation/difficulty/subtype）
- [ ] 错误 taxonomy 记录

---

*本文档由 Claude Code 生成，基于 GeoKD-SR 实验设计方案 V5.2。*
