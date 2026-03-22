# Exp7: 注意力对齐蒸馏（Spatial Attention Alignment）

> **实验定位**：C5 组件的实现（B2 + C5）。
>
> 本实验在 Exp2 的基础上引入**空间注意力对齐**，在空间实体与空间关系 token 上做注意力蒸馏，让学生学习教师“关注哪里”的模式。

**组件标识**：B2 + C5（Spatial Attention Alignment）
**V5.2 依据**：§4.7.4（Exp7 定义），§4.7.6（对比关系）

---

## 1. 目的与假设

### 1.1 实验定位
- **C5 组件实现**：验证中间特征（注意力）蒸馏的价值
- **对比对象**：Exp2（标准 KD，无注意力对齐）

### 1.2 控制变量（与 Exp2 相同）
- 数据、模型、模板、超参均相同
- 基础蒸馏框架相同

### 1.3 实验变量（与 Exp2 的差异）
- **新增**：注意力对齐损失（L_attn）
- **聚焦**：仅对空间实体和空间关系 token 计算注意力损失

### 1.4 预期结果
- **Exp7 > Exp2**：注意力对齐能提升空间推理
- **预期提升**：相比 Exp2 提升一定幅度

**V5.2 依据**：§4.7.6 "Exp7 vs Exp2：空间注意力蒸馏的贡献"

---

## 2. 理论依据

### 2.1 KD/LLM 蒸馏角度

#### 2.1.1 注意力蒸馏的动机
**传统 KD**：只蒸馏输出层（logits）
**注意力蒸馏**：蒸馏中间层（注意力模式）

**为什么注意力有价值？**
- **可解释性**：注意力反映模型“关注什么”
- **结构知识**：注意力模式编码了实体关系
- **层次化**：不同层捕获不同抽象级别的模式

#### 2.1.2 相关工作
- **TinyBERT**：蒸馏注意力与隐藏状态
- **DistilBERT**：蒸馏嵌入与注意力
- **FitBERT**：只在实体 token 上蒸馏

**V5.2 依据**：§4.7.4 "C5…在空间实体和空间关系token上做注意力对齐"

### 2.2 地理空间推理角度

#### 2.2.1 空间推理中的注意力模式

**方向推理的注意力**：
```
问题："北京相对天津的方向？"
注意力聚焦：
  - "北京" → 坐标查询
  - "天津" → 坐标查询
  - "相对" → 方向计算
```

**拓扑推理的注意力**：
```
问题："A 是否包含 B？"
注意力聚焦：
  - "A" → 边界查询
  - "B" → 边界查询
  - "包含" → 九交模型计算
```

**组合推理的注意力**：
```
问题："从 A 到 B 的路线？"
注意力聚焦：
  - 多实体交替关注
  - "从" → 起点
  - "到" → 终点
  - 中间步骤 → 路径规划
```

#### 2.2.2 实体级注意力的 Geo 价值
- **实体定位**：学习识别问题中的空间实体
- **关系聚焦**：学习关注关键的关系词（方向、拓扑、距离）
- **推理步骤**：学习多步推理中的注意力转移

---

## 3. 方法口径

### 3.1 使用哪些字段

| 字段 | Exp7 用途 | 说明 |
|-----|----------|-----|
| `question` | 输入 | 转为 user 消息 |
| `answer` | 监督目标（L_hard） | 转为 assistant 消息 |
| **`entities`** | **注意力掩码** | **新增**：用于识别实体 token |
| **`entity_to_token`** | **注意力掩码** | **新增**：token 级对齐 |

**V5.2 依据**：§4.7.4 字段使用矩阵（Exp7 行）

### 3.2 输入格式（与 Exp2 相同）
```
System: 你是一个地理空间推理专家...（固定）

User: {question}

Assistant: {answer}
```

### 3.3 损失函数

#### 3.3.1 总损失
```
L = α × L_soft + (1-α) × L_hard + β × L_attn
```
- **α = 0.5**：KD 权重
- **β**：注意力权重（V5.2 未明确，建议 0.1）

#### 3.3.2 L_attn（注意力对齐损失）
```
L_attn = Σ_{l∈layers} λ_l × L_attn^(l)

L_attn^(l) = MSE(A_S^(l), A_T^(l)) ⊙ M_entity
```
- **A_S^(l), A_T^(l)**：第 l 层学生/教师的注意力矩阵
- **M_entity**：实体掩码（只在实体/空间 token 上计算）
- **λ_l**：层权重

**V5.2 依据**：§4.7.4 "L_attn^(l)=...MSE(A_S, A_T)…M_entity 掩码"

#### 3.3.3 层选择策略
- **蒸馏最后 6 层**：Layer 23–28（假设模型共 28 层）
- **层权重**：均匀初始化 `λ_l = 1/6`，可学习（softmax）

**V5.2 依据**：§4.7.4 "蒸馏最后6层…均匀初始化…λ_l = 1/6"

### 3.4 实体掩码构造

#### 3.4.1 基于 entity_to_token
```python
# 数据中的 entity_to_token
entity_to_token = [
    {"entity": "北京", "token_indices": [10, 11]},
    {"entity": "天津", "token_indices": [15, 16]},
    ...
]

# 构造掩码
M_entity = torch.zeros(seq_len, dtype=bool)
for et in entity_to_token:
    M_entity[et["token_indices"]] = True
```

#### 3.4.2 基于 entities 列表（简化）
```python
# 如果没有 entity_to_token，可以基于实体列表
entities = ["北京", "天津", ...]

# 构造掩码（字符串匹配）
M_entity = is_entity_token(input_ids, entities, tokenizer)
```

### 3.5 训练流程要点

#### 3.5.1 前向传播
```python
# 学生前向（输出注意力）
student_outputs = student(
    input_ids,
    attention_mask=attention_mask,
    output_attentions=True  # 返回注意力
)
student_logits = student_outputs.logits
student_attentions = student_outputs.attentions  # tuple of [batch, heads, seq, seq]

# 教师前向
with torch.no_grad():
    teacher_outputs = teacher(
        input_ids,
        attention_mask=attention_mask,
        output_attentions=True
    )
teacher_logits = teacher_outputs.logits
teacher_attentions = teacher_outputs.attentions

# 计算 L_hard
loss_hard = CrossEntropy(student_logits[mask], labels[mask])

# 计算 L_soft
loss_soft = KL_div(soft_teacher, soft_student)

# 计算 L_attn
loss_attn = 0
for l in target_layers:  # 如最后 6 层
    A_S = student_attentions[l]  # [batch, heads, seq, seq]
    A_T = teacher_attentions[l]

    # 平均多头
    A_S = A_S.mean(dim=1)  # [batch, seq, seq]
    A_T = A_T.mean(dim=1)

    # 应用实体掩码
    M_entity_expanded = M_entity.unsqueeze(1).expand(-1, seq_len, -1)
    A_S_masked = A_S * M_entity_expanded
    A_T_masked = A_T * M_entity_expanded

    # MSE
    loss_attn += F.mse_loss(A_S_masked, A_T_masked)

loss_attn = loss_attn / len(target_layers)

# 总损失
loss = α × loss_soft + (1-α) × loss_hard + β × loss_attn
```

#### 3.5.2 关键实现细节
- **output_attentions=True**：模型必须输出注意力
- **显存优化**：注意力矩阵较大，可能需要梯度检查点
- **实体掩码**：确保只在相关 token 上计算

---

## 4. 步骤建议

### 4.1 训练前准备

#### 4.1.1 数据准备（与 Exp2 不同）
- **新增**：确认数据包含 `entities` 和 `entity_to_token` 字段
- **验证**：检查 entity_to_token 的 token_indices 是否正确

#### 4.1.2 层选择
- 确定模型层数（Qwen2.5-1.5B 为 28 层）
- 选择蒸馏最后 6 层（Layer 23–28）

#### 4.1.3 Seed 与目录
- Seeds：[42, 123, 456, 789, 1024]（5 次）
- 输出目录：
  ```
  checkpoints/exp07/{seed}/
  logs/exp07/{seed}/
  results/exp07/{seed}/
  ```

### 4.2 训练中监控

#### 4.2.1 关键指标（与 Exp2 对比）
- **loss_hard**：CE 损失
- **loss_soft**：KL 损失
- **loss_attn**：注意力 MSE 损失
- **loss_total**：总损失

#### 4.2.2 每 eval_steps（建议 500）
1. 在验证集上计算：
   - overall_accuracy
   - 分类型 accuracy
   - format_valid_rate

#### 4.2.3 异常检测
- **loss_attn 过大**：注意力差异太大，检查掩码
- **loss_attn ≈ 0**：掩码可能无效，检查实体识别
- **显存不足**：注意力矩阵较大，考虑梯度检查点

### 4.3 训练后处理

#### 4.3.1 Checkpoint 选择
- **best_model**：验证集准确率最高的 checkpoint

#### 4.3.2 评测执行
1. 在 test set 上生成预测
2. 使用统一评测协议

#### 4.3.3 注意力可视化（建议）
- 可视化学生与教师的注意力模式
- 对比实体聚焦的差异

---

## 5. 诊断与失败模式

### 5.1 常见陷阱

#### 5.1.1 "实体掩码无效"
- **陷阱**：entity_to_token 的 token_indices 不准
- **诊断**：打印掩码，验证实体 token 是否正确
- **后果**：注意力蒸馏退化到全序列

#### 5.1.2 "注意力不对齐"
- **陷阱**：学生与教师的注意力矩阵维度不一致
- **可能原因**：
  - 层数不匹配
  - 序列长度不一致
- **诊断**：检查注意力矩阵形状

#### 5.1.3 "显存不足"
- **陷阱**：存储所有层的注意力矩阵
- **解决**：
  - 只存储蒸馏的层
  - 使用梯度检查点
  - 减少批大小

### 5.2 性能诊断

| 现象 | 可能原因 | 建议排查 |
|-----|---------|---------|
| Exp7 > Exp2 | 注意力对齐有效 | 分析实体聚焦改善 |
| Exp7 ≈ Exp2 | 注意力对齐无额外价值 | 检查掩码质量 |
| Exp7 < Exp2 | 注意力对齐引入噪声 | 降低 β 或检查层选择 |

### 5.3 注意力质量分析

| 指标 | 评估方法 |
|-----|---------|
| 实体聚焦度 | 实体 token 上的注意力权重和 |
| 层级一致性 | 不同层的注意力模式相关性 |
| 学生-教师相似度 | 余弦相似度、MSE |

---

## 6. 预期结果与论文写作

### 6.1 预期性能范围
- **vs Exp2**：预期有提升
- **分类型**：complex 类型可能提升更大

### 6.2 论文写作建议

#### 6.2.1 Methods 章节
```
Exp7 (Attention Alignment) 在标准 KD 的基础上引入空间注意力对齐。
我们在空间实体和空间关系 token 上计算注意力 MSE 损失：

L_attn = Σ_{l∈layers} λ_l × MSE(A_S^(l), A_T^(l)) ⊙ M_entity

其中 A_S^(l) 和 A_T^(l) 分别为第 l 层学生和教师的注意力矩阵，
M_entity 为实体掩码（基于 entity_to_token 构造）。我们蒸馏
最后 6 层（Layer 23–28）的注意力，层权重 λ_l 均匀初始化为 1/6，
并在训练中自适应调整。
```

#### 6.2.2 Experiments 章节
```
表X：各实验在 GeoKD-SR 测试集上的性能（均值±标准差）

| 实验 | Overall | Directional | Topological | Metric | Composite |
|-----|---------|------------|-------------|--------|-----------|
| Exp2 (KD) | XX.X±X.X | ... | ... | ... | ... |
| Exp7 (Attn) | YY.Y±Y.Y | ... | ... | ... | ... |
...
```

#### 6.2.3 Ablation 讨论
```
Exp7 相比 Exp2 提升了 Z.Z%（p < 0.05），表明空间注意力对齐有效。
注意力可视化显示，Exp7 学会了在空间实体 token 上聚焦注意力，
而 Exp2 的注意力分布较为分散。特别是在 composite 类型中，
Exp7 的注意力模式更接近教师，表现出清晰的多实体交替关注模式，
说明注意力蒸馏帮助学生学习到了空间推理的结构知识。
```

#### 6.2.4 注意力可视化说明
```
图X：Exp2 与 Exp7 的注意力热图对比。上图为教师注意力，
中图为 Exp2 注意力，下图为 Exp7 注意力。Exp7 的注意力模式
更接近教师，在实体 token（"北京"、"天津"）上有更高的聚焦。
```

---

## 7. V5.2 引用定位

| 内容 | V5.2 位置 |
|-----|-----------|
| Exp7 定义 | §4.7.4 表格（Exp7 行） |
| C5 组件说明 | §4.7.4 "C5…在空间实体和空间关系token上做注意力对齐" |
| 损失函数 | §4.7.4 "L_SRA = Σ λ_l × L_attn^(l)" |
| 层选择 | §4.7.4 "蒸馏最后6层…均匀初始化…λ_l = 1/6" |
| 对比关系 Exp7 vs Exp2 | §4.7.6 "Exp7 vs Exp2：空间注意力蒸馏的贡献" |

---

## 8. 超参数敏感性

| 超参数 | 当前值 | 建议搜索空间 |
|-------|-------|------------|
| β（注意力权重） | 未明确 | {0.05, 0.1, 0.2, 0.3} |
| 蒸馏层数 | 6 | {3, 6, 9, 12} |
| 蒸馏层位置 | 最后 6 层 | 前 6 层 / 中间 6 层 / 最后 6 层 |
| 层权重初始化 | 均匀 1/6 | 均匀 / 可学习 |

---

*本文档由 Claude Code 生成，基于 GeoKD-SR 实验设计方案 V5.2。*
