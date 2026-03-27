# Exp2: Standard-KD（通用知识蒸馏基线）

> **实验定位**：GeoKD-SR 实验矩阵的**蒸馏基线**（B2）。
>
> 本实验使用经典 **Hinton 2015 知识蒸馏**方法，结合 Forward KL 散度与 hard label，作为所有后续组件实验（Exp3–Exp9）的**共同对比基准**。

**组件标识**：B2（Standard-KD）
**V5.2 依据**：§4.7.4（Exp2 定义），§4.7.6（对比关系）

---

## 1. 目的与假设

### 1.1 实验定位
- **蒸馏基线**：所有组件实验（C1–C6）的对照基准
- **验证假设**：蒸馏（Exp2）应显著优于纯 SFT（Exp1）

### 1.2 控制变量（与 Exp1 完全相同）
- 数据：同一份数据（`final_1_final.jsonl` + manifest）
- 模型：同一学生模型（Qwen2.5-1.5B-Instruct）
- 模板：同一 ChatML chat_template 与 system_prompt
- 超参：同一训练超参（lr=1e-4, batch=8, accum=16, epochs=3, ...）

### 1.3 实验变量（与 Exp1 的唯一差异）
- **新增**：引入教师模型（Qwen2.5-7B-Instruct）的 soft label
- **新增**：KL 散度损失（Forward KL）

### 1.4 预期结果
- **Exp2 > Exp1**：蒸馏有效，预期提升 5-10%
- **Exp2 作为基准**：后续组件实验均需证明 ExpX > Exp2

**V5.2 依据**：§4.7.6 对比表

---

## 2. 理论依据

### 2.1 KD/LLM 蒸馏角度

#### 2.1.1 经典知识蒸馏（Hinton 2015）
核心思想：**让学生学习教师的输出分布，而非仅学习 hard label**

```
L_KD = α × L_soft + (1-α) × L_hard
```
- **L_soft**：KL(教师分布 || 学生分布)，捕获“暗知识”
- **L_hard**：CrossEntropy(学生分布, hard label)，保证任务对齐
- **α**：混合权重，V5.2 设为 0.5

#### 2.1.2 Forward KL（Mode-Covering）
```
L_soft = KL(P_T || P_S) = Σ P_T(x) log(P_T(x) / P_S(x))
```
- **性质**：mode-covering，鼓励学生覆盖教师的所有概率模式
- **适用场景**：分类任务、生成任务的蒸馏基线

#### 2.1.3 温度参数 T
```
P_T^T(x) = softmax(z_T(x) / T)
P_S^T(x) = softmax(z_S(x) / T)
```
- **T > 1**：平滑分布，突出暗知识（类间相似性）
- **V5.2 设定**：T = 2.0

#### 2.1.4 为什么需要 L_hard？
- **锚定作用**：防止学生过度模仿教师的错误模式
- **任务对齐**：保证学生仍能学会正确答案

**V5.2 依据**：§4.7.4 "B2: Standard-KD...Hinton 2015经典KL蒸馏"

### 2.2 地理空间推理角度

#### 2.2.1 Geo 任务中的“暗知识”
在空间推理任务中，教师分布可能编码：
- **空间关系相似性**：如“东北”与“东”的相似度高于“东北”与“西”
- **推理不确定性**：教师对复杂样本（如 composite 推理）的不确定性分布
- **候选答案合理性**：即使答案错误，教师的次优选择可能仍有价值

#### 2.2.2 Forward KL 的 Geo 适用性
- **mode-covering**：鼓励学生覆盖教师的所有空间关系模式
- **风险**：若教师存在系统性偏差（如方向判断倾向），Forward KL 会放大

---

## 3. 方法口径

### 3.1 使用哪些字段

| 字段 | Exp2 用途 | 说明 |
|-----|----------|-----|
| `question` | 输入 | 转为 user 消息 |
| `answer` | 监督目标（L_hard） | 转为 assistant 消息，计算 CE |
| ~~`reasoning_chain`~~ | ~~不使用~~ | Exp2 不蒸馏推理过程 |
| ~~`spatial_relation_type`~~ | ~~不用于损失~~ | 仅用于分层统计 |

**V5.2 依据**：§4.7.4 字段使用矩阵（Exp2 行）

### 3.2 输入格式（与 Exp1 相同）
```
System: 你是一个地理空间推理专家...（固定）

User: {question}

Assistant: {answer}
```

### 3.3 损失函数

#### 3.3.1 总损失
```
L = α × L_soft + (1-α) × L_hard
```
- **α = 0.5**：soft/hard 均衡

#### 3.3.2 L_hard（交叉熵）
```
L_hard = CrossEntropy(student_logits, labels)
```
- **labels**：answer 文本的 token 序列
- **mask**：仅 assistant 段

#### 3.3.3 L_soft（Forward KL）
```
L_soft = T² × KL(P_T^T || P_S^T)
        = T² × Σ P_T^T(x) log(P_T^T(x) / P_S^T(x))
```
- **P_T^T**：教师 logit 除以 T 后的 softmax
- **P_S^T**：学生 logit 除以 T 后的 softmax
- **T² 因子**：补偿梯度缩放（Hinton 2015 原始设定）
- **mask**：使用 valid_mask = (labels != -100) & (attention_mask == 1)

**V5.2 依据**：§4.7.4 "L_KD = α × L_soft + (1-α) × L_hard"

### 3.4 训练流程要点

#### 3.4.1 前向传播
```
# 学生前向
student_logits = student(input_ids)  # [batch, seq_len, vocab]

# 教师前向（eval 模式）
with torch.no_grad():
    teacher_logits = teacher(input_ids)  # [batch, seq_len, vocab]

# 计算 L_hard
loss_hard = CrossEntropy(student_logits[mask], labels[mask])

# 计算 L_soft
soft_teacher = softmax(teacher_logits / T, dim=-1)
soft_student = softmax(student_logits / T, dim=-1)
loss_soft = T² × KL_div(soft_teacher[mask], soft_student[mask])

# 总损失
loss = α × loss_soft + (1-α) × loss_hard
```

#### 3.4.2 反向传播
```
loss.backward()  # 仅学生参数更新，教师冻结
optimizer.step()
```

#### 3.4.3 关键实现细节
- **教师冻结**：`teacher.requires_grad_(False)`
- **教师模式**：`teacher.eval()`（关闭 dropout）
- **显存优化**：教师可用 4-bit 量化（NF4）

---

## 4. 步骤建议

### 4.1 训练前准备

#### 4.1.1 数据准备（与 Exp1 相同）
- 数据文件：`data/final/final_1_final.jsonl`
- 官方 splits：train/dev/test
- dataset_manifest.json

#### 4.1.2 模型准备
- **学生模型**：Qwen2.5-1.5B-Instruct
- **教师模型**：Qwen2.5-7B-Instruct（建议 4-bit 量化）
- **Tokenizer**：使用学生模型的 tokenizer（二者兼容）

#### 4.1.3 Seed 与目录
- Seeds：[42, 123, 456, 789, 1024]（5 次）
- 输出目录：
  ```
  checkpoints/exp02/{seed}/
  logs/exp02/{seed}/
  results/exp02/{seed}/
  ```

### 4.2 训练中监控

#### 4.2.1 关键指标（与 Exp1 对比）
- **loss_hard**：CE 损失
- **loss_soft**：KL 损失（×T²）
- **loss_total**：总损失
- **learning_rate**：cosine 调度

#### 4.2.2 每 eval_steps（建议 500）
1. 在验证集上计算：
   - overall_accuracy
   - 分类型 accuracy
   - format_valid_rate
2. 记录 loss 分项，诊断软硬损失平衡

#### 4.2.3 异常检测
- **loss_soft 占主导**：可能温度过高或 α 过大
- **loss_hard 占主导**：可能温度过低或 α 过小
- **loss 震荡**：检查 mask 是否正确

### 4.3 训练后处理

#### 4.3.1 Checkpoint 选择
- **best_model**：验证集准确率最高的 checkpoint
- **final_model**：最后一个 epoch

#### 4.3.2 评测执行
1. 在 test set 上生成预测
2. 使用统一评测协议（与 Exp1 相同）

#### 4.3.3 与 Exp1 对比
- **主要指标**：overall_accuracy 增幅
- **分层指标**：各关系类型增幅
- **统计显著性**：paired t-test / Wilcoxon

---

## 5. 诊断与失败模式

### 5.1 常见陷阱

#### 5.1.1 “蒸馏无效”的假象
- **陷阱**：Exp2 ≈ Exp1，看似蒸馏无效
- **可能原因**：
  - 教师质量不足（检查教师 baseline）
  - 温度不合适（尝试 T ∈ {1.0, 1.5, 2.5, 3.0}）
  - α 不合适（尝试 α ∈ {0.3, 0.5, 0.7}）

#### 5.1.2 KL 计算范围错误
- **陷阱**：对 prompt 段计算 KL
- **诊断**：检查 valid_mask = (labels != -100) & (attention_mask == 1)
- **后果**：违反公平性，与后续实验不可比

#### 5.1.3 教师模式错误
- **陷阱**：教师使用 train 模式（dropout 开启）
- **诊断**：检查 `teacher.eval()` 是否调用
- **后果**：教师分布不稳定，蒸馏效果差

### 5.2 典型错误类型（与 Exp1 相比）

| 错误类型 | Exp1→Exp2 变化 | 可能原因 |
|---------|---------------|---------|
| 方向错误 | ↓（改善） | 教师分布编码了方向相似性 |
| 拓扑混淆 | ↓（改善） | 教师对拓扑关系有更好的模式 |
| 距离偏差 | ↓（改善） | 教师数值推理更稳定 |
| 格式错误 | 相近 | 格式主要受模板影响 |

### 5.3 性能诊断

| 现象 | 可能原因 | 建议排查 |
|-----|---------|---------|
| Exp2 < Exp1 | 蒸馏引入噪声 | 检查教师质量、降低 α |
| Exp2 ≈ Exp1 | 蒸馏无额外价值 | 检查温度、教师与学生能力差距 |
| Exp2 >> Exp1 | 异常优秀 | 检查是否公平（数据、超参） |

---

## 6. 预期结果与论文写作

### 6.1 预期性能范围
- **overall_accuracy**：Exp1 + 5-10%
- **format_valid_rate**：与 Exp1 相近（> 0.95）

### 6.2 论文写作建议

#### 6.2.1 Methods 章节
```
Exp2 (Standard-KD) 采用 Hinton (2015) 的经典知识蒸馏方法，
结合教师模型的 soft label 与标准答案的 hard label：

L_KD = α × L_soft + (1-α) × L_hard

其中 L_soft 为 Forward KL 散度（KL(P_T || P_S)），L_hard 为交叉熵损失。
我们设置 α = 0.5，温度 T = 2.0，监督范围限定于 assistant 段。
```

#### 6.2.2 Experiments 章节
```
表X：各实验在 GeoKD-SR 测试集上的性能（均值±标准差）

| 实验 | Overall Acc | Direction Acc | Topology Acc | Metric Acc |
|-----|------------|--------------|--------------|------------|
| Exp1 (SFT) | XX.X±X.X | ... | ... | ... |
| Exp2 (KD) | YY.Y±Y.Y | ... | ... | ... |
| Exp3a (SRD-Uniform) | ... | ... | ... | ... |
...
```

#### 6.2.3 Ablation 讨论
```
Exp2 相比 Exp1 提升了 Z.Z%（p < 0.05），表明教师模型的 soft label
提供了超越标准答案的暗知识。具体而言，教师分布编码了空间关系
的相似性结构（如方向间的角度关系），帮助学生更好地学习地理空间推理。
```

---

## 7. 超参数敏感性（未来工作）

V5.2 明确以下超参数敏感性分析为未来工作：

| 超参数 | 当前值 | 建议搜索空间 |
|-------|-------|------------|
| T（温度） | 2.0 | {1.0, 1.5, 2.0, 2.5, 3.0} |
| α（soft权重） | 0.5 | {0.3, 0.5, 0.7} |

**V5.2 依据**：§4.7.4 "敏感性分析（如T ∈ {1.0, 1.5, 2.0, 3.0}）将作为未来工作"

---

## 8. V5.2 引用定位

| 内容 | V5.2 位置 |
|-----|-----------|
| Exp2 定义 | §4.7.4 表格（Exp2 行） |
| 损失函数 | §4.7.4 "L_KD = α × L_soft + (1-α) × L_hard" |
| Forward KL 说明 | §4.7.4 "Forward KL...mode-covering" |
| 温度设定 | §4.7.4 "T = 2.0" |
| 对比关系 Exp2 vs Exp1 | §4.7.6 "Exp2 vs Exp1...验证蒸馏有效性" |

---

## 9. 与后续实验的关系

Exp2 是以下实验的共同对照：
- **Exp3a vs Exp2**：验证等权重空间关系感知是否有收益
- **Exp3 vs Exp2**：验证可学习权重空间关系蒸馏的贡献
- **Exp4 vs Exp2**：验证思维链蒸馏的贡献
- **Exp5 vs Exp2**：验证逆向 KL 的贡献
- **Exp6 vs Exp2**：验证自蒸馏的贡献
- **Exp7 vs Exp2**：验证注意力对齐的贡献
- **Exp8 vs Exp2**：验证渐进式训练的贡献
- **Exp9 vs Exp2**：验证完整方法的整体优势

**V5.2 依据**：§4.7.6 对比表

---

*本文档由 Claude Code 生成，基于 GeoKD-SR 实验设计方案 V5.2。*
