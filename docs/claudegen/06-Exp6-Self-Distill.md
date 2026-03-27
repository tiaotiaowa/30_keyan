# Exp6: 自蒸馏（Self-Distillation with EMA）

> **实验定位**：C4 组件的实现（B2 + C4）。
>
> 本实验在 Exp2 的基础上引入**自蒸馏**，使用学生模型自身的 EMA（Exponential Moving Average）版本作为软目标，通过时间一致性约束提升推理稳定性。

**组件标识**：B2 + C4（Self-Distillation）
**V5.2 依据**：§4.7.4（Exp6 定义），§4.7.6（对比关系）

---

## 1. 目的与假设

### 1.1 实验定位
- **C4 组件实现**：验证自蒸馏在空间推理任务中的价值
- **对比对象**：Exp2（标准 KD，无自蒸馏）

### 1.2 控制变量（与 Exp2 相同）
- 数据、模型、模板、超参均相同
- 基础蒸馏框架相同

### 1.3 实验变量（与 Exp2 的差异）
- **新增**：EMA 学生模型作为软目标
- **新增**：一致性损失（L_consistency）

### 1.4 预期结果
- **Exp6 > Exp2**：自蒸馏提升稳定性与最终效果
- **预期提升**：相比 Exp2 提升 1-2%

**V5.2 依据**：§4.7.6 "成功标准…Exp6 > Exp2…预期提升1-2%"

---

## 2. 理论依据

### 2.1 KD/LLM 蒸馏角度

#### 2.1.1 自蒸馏的核心思想
**传统 KD**：使用外部教师模型
**自蒸馏**：使用学生自身的过去版本作为“教师”

```
当前学生 (t)  -->  EMA 更新  -->  EMA学生 (t-1)
     ↓                              ↓
  L_SFT                        L_consistency
```

**优势**：
1. **无需额外教师**：不增加推理成本
2. **时间一致性**：约束模型在不同时刻的预测一致
3. **正则化效果**：EMA 目标更平滑，提供正则信号

#### 2.1.2 相关工作
- **Noisy Student (ICLR 2020)**：学生模型自我训练
- **Mean Teacher**：EMA 教师用于一致性正则
- **Self-Training with Distillation**：模型自身作为教师

**V5.2 依据**：§4.7.4 "C4…使用学生模型自身的预测作为软目标…时间一致性约束"

### 2.2 地理空间推理角度

#### 2.2.1 空间推理的一致性需求
**空间推理的特点**：
- **确定性高**：同一实体对的空间关系是客观事实
- **步骤敏感**：推理链中任何一步错误会导致结论错误
- **稳定性重要**：模型应给出一致的判断，而非随机摇摆

**自蒸馏的 Geo 价值**：
1. **稳定方向判断**：避免同一问题在不同时刻给出不同方向
2. **稳定拓扑分类**：避免拓扑关系随机摇摆
3. **稳定距离估计**：避免数值估计剧烈波动

#### 2.2.2 EMA 的平滑作用
```
EMA学生(t) = μ × EMA学生(t-1) + (1-μ) × 学生(t)
```
- **μ = 0.999**：EMA 衰减系数
- **效果**：EMA 模型是历史模型的加权平均，更平滑、更稳定

---

## 3. 方法口径

### 3.1 使用哪些字段

| 字段 | Exp6 用途 | 说明 |
|-----|----------|-----|
| `question` | 输入 | 转为 user 消息 |
| `answer` | 监督目标（L_SFT） | 转为 assistant 消息 |

**与 Exp2 相同**

**V5.2 依据**：§4.7.4 字段使用矩阵（Exp6 行）

### 3.2 输入格式（与 Exp2 相同）
```
System: 你是一个地理空间推理专家...（固定）

User: {question}

Assistant: {answer}
```

### 3.3 损失函数

#### 3.3.1 总损失
```
L_SelfDistill = λ × L_consistency + (1-λ) × L_SFT
```
- **λ = 0.3**：自蒸馏权重
- **1-λ = 0.7**：SFT 权重

**V5.2 依据**：§4.7.4 "L_SelfDistill = λ × L_consistency + (1-λ) × L_SFT…λ=0.3"

#### 3.3.2 L_SFT（标准 SFT 损失）
```
L_SFT = CrossEntropy(student_logits, labels)
```
- **监督范围**：仅 assistant 段

#### 3.3.3 L_consistency（一致性损失）
```
L_consistency = KL(P_S^current || P_S^EMA)
```
- **P_S^current**：当前学生分布
- **P_S^EMA**：EMA 学生分布（冻结）
- **mask**：valid_mask = (labels != -100) & (attention_mask == 1)

**V5.2 依据**：§4.7.4 "L_consistency = KL(P_S^current || P_S^EMA)"

#### 3.3.4 EMA 更新规则
```
EMA学生 = μ × EMA学生 + (1-μ) × 学生
```
- **μ = 0.999**：衰减系数
- **初始状态**：EMA学生(0) = 学生(0)

**V5.2 依据**：§4.7.4 "μ=0.999"

### 3.4 训练流程要点

#### 3.4.1 初始化
```python
# 初始时刻
student = StudentModel()
ema_student = StudentModel()
ema_student.load_state_dict(student.state_dict())  # 深拷贝
```

#### 3.4.2 前向传播
```python
# 当前学生前向
student_logits = student(input_ids)

# EMA 学生前向（eval 模式）
with torch.no_grad():
    ema_logits = ema_student(input_ids)

# 计算 L_SFT
loss_sft = CrossEntropy(student_logits[mask], labels[mask])

# 计算 L_consistency
soft_student = softmax(student_logits / T, dim=-1)
soft_ema = softmax(ema_logits / T, dim=-1)
loss_consistency = KL_div(soft_student[mask], soft_ema[mask])

# 总损失
loss = λ × loss_consistency + (1-λ) × loss_sft
```

#### 3.4.3 EMA 更新（每个 step）
```python
# 反向传播
loss.backward()
optimizer.step()

# 更新 EMA 学生
for param, ema_param in zip(student.parameters(), ema_student.parameters()):
    ema_param.data = μ × ema_param.data + (1-μ) × param.data
```

#### 3.4.4 关键实现细节
- **EMA 不求梯度**：`with torch.no_grad()`
- **EMA 不更新**：不调用 `ema_optimizer.step()`
- **EMA 评估**：评估时可用 EMA 模型（更稳定）

---

## 4. 步骤建议

### 4.1 训练前准备

#### 4.1.1 数据准备（与 Exp2 相同）
- 数据文件：`data/final/final_1_final.jsonl`
- 官方 splits：train/dev/test

#### 4.1.2 模型准备
- 学生模型：Qwen2.5-1.5B-Instruct
- **新增**：EMA 学生模型（参数相同，独立副本）

#### 4.1.3 Seed 与目录
- Seeds：[42, 123, 456, 789, 1024]（5 次）
- 输出目录：
  ```
  checkpoints/exp06/{seed}/
  logs/exp06/{seed}/
  results/exp06/{seed}/
  ```

### 4.2 训练中监控

#### 4.2.1 关键指标（与 Exp2 对比）
- **loss_sft**：CE 损失
- **loss_consistency**：一致性 KL 损失
- **loss_total**：总损失
- **ema_distance**（可选）：学生与 EMA 的参数距离

#### 4.2.2 每 eval_steps（建议 500）
1. 在验证集上计算：
   - overall_accuracy（使用当前学生）
   - **overall_accuracy_ema**（使用 EMA 学生，可选）
   - 分类型 accuracy
   - format_valid_rate

#### 4.2.3 异常检测
- **loss_consistency 过高**：学生偏离 EMA 太远，可能 λ 过大
- **loss_consistency ≈ 0**：学生与 EMA 过度接近，可能 λ 过小
- **ema_distance 不收敛**：检查 μ 设置

### 4.3 训练后处理

#### 4.3.1 Checkpoint 选择
- **best_model**：验证集准确率最高的 checkpoint（当前学生）
- **best_ema_model**（可选）：对应时刻的 EMA 模型

#### 4.3.2 评测执行
1. 在 test set 上生成预测
   - **对比**：当前学生 vs EMA 学生
2. 使用统一评测协议
3. **稳定性分析**：同一问题多次生成，计算一致性

#### 4.3.3 与 Exp2 对比
- **主要指标**：overall_accuracy 增幅
- **稳定性指标**：生成一致性提升
- **分类型**：各关系类型的稳定性变化

---

## 5. 诊断与失败模式

### 5.1 常见陷阱

#### 5.1.1 "确认偏差"（Confirmation Bias）
- **陷阱**：EMA 学生与当前学生互相强化错误
- **表现**：训练后期 loss 不下降但错误累积
- **诊断**：检查验证集性能是否持续下降

#### 5.1.2 "EMA 更新过慢"
- **陷阱**：μ 过高（如 0.9999），EMA 几乎不变
- **表现**：L_consistency 无效
- **建议**：尝试 μ ∈ {0.99, 0.999, 0.9995}

#### 5.1.3 "λ 设置不当"
- **陷阱**：λ 过大（>0.5），学生过度依赖 EMA
- **表现**：训练初期收敛慢
- **建议**：λ ∈ {0.1, 0.2, 0.3, 0.4}

### 5.2 性能诊断

| 现象 | 可能原因 | 建议排查 |
|-----|---------|---------|
| Exp6 > Exp2 | 自蒸馏有效 | 分析一致性提升 |
| Exp6 ≈ Exp2 | 自蒸馏无额外价值 | 检查 λ、μ 设置 |
| Exp6 < Exp2 | 自蒸馏引入噪声 | 降低 λ 或检查数据 |
| EMA >> 当前 | EMA 更稳定 | 考虑用 EMA 做最终模型 |

### 5.3 稳定性分析（关键指标）

#### 5.3.1 生成一致性
```python
# 同一问题生成 N 次
predictions = [model.generate(question) for _ in range(N)]

# 计算一致性（多数投票准确率）
consistency = mode(predictions) == ground_truth
```

#### 5.3.2 参数稳定性
```python
# 计算学生与 EMA 的参数距离
param_distance = 0
for p, ema_p in zip(student.parameters(), ema_student.parameters()):
    param_distance += (p - ema_p).pow(2).sum().item()
```

---

## 6. 预期结果与论文写作

### 6.1 预期性能范围
- **vs Exp2**：预期提升 1-2%
- **稳定性**：生成一致性提升 5-10%

### 6.2 论文写作建议

#### 6.2.1 Methods 章节
```
Exp6 (Self-Distillation) 在标准 KD 的基础上引入自蒸馏机制，
使用学生模型的 EMA 版本作为一致性目标：

L_SelfDistill = λ × L_consistency + (1-λ) × L_SFT

其中 L_consistency = KL(P_S^current || P_S^EMA)，λ = 0.3。
EMA 模型按 EMA(t) = μ × EMA(t-1) + (1-μ) × Student(t) 更新，
μ = 0.999。自蒸馏通过时间一致性约束鼓励模型给出稳定的预测，
这对空间推理任务尤为重要，因为空间关系具有客观确定性。
```

#### 6.2.2 Experiments 章节
```
表X：各实验在 GeoKD-SR 测试集上的性能（均值±标准差）

| 实验 | Overall Acc | 生成一致性 | Direction Acc | Topology Acc |
|-----|------------|-----------|--------------|--------------|
| Exp2 (KD) | XX.X±X.X | C.C% | ... | ... |
| Exp6 (Self) | YY.Y±Y.Y | D.D% | ... | ... |
...
```

#### 6.2.3 Ablation 讨论
```
Exp6 相比 Exp2 提升了 Z.Z%（p < 0.05），虽然提升幅度较小（1-2%），
但生成一致性提升了 W.W%，验证了自蒸馏的稳定性价值。我们分析发现，
自蒸馏通过时间一致性约束减少了模型预测的随机波动，特别是在
metric 类型（距离估计）中，Exp6 的预测方差显著降低。此外，
EMA 模型在验证集上的性能略优于当前模型（X.X% vs Y.Y%），
说明 EMA 平滑了训练噪声，提供了更稳定的指导信号。
```

#### 6.2.4 案例分析（建议）
```
表Y：Exp2 与 Exp6 的生成稳定性对比

| 问题 | Exp2 多次生成 | Exp6 多次生成 | 一致性 |
|-----|-------------|--------------|-------|
| A相对B的方向？ | {东北, 东, 正北} | {东北, 东北, 东北} | Exp6 更稳定 |
| A与B的距离？ | {120km, 135km, 98km} | {122km, 123km, 121km} | Exp6 更稳定 |
```

---

## 7. V5.2 引用定位

| 内容 | V5.2 位置 |
|-----|-----------|
| Exp6 定义 | §4.7.4 表格（Exp6 行） |
| C4 组件说明 | §4.7.4 "C4…使用学生模型自身的预测作为软目标" |
| 损失函数 | §4.7.4 "L_SelfDistill = λ × L_consistency + (1-λ) × L_SFT" |
| λ 和 μ 设定 | §4.7.4 "λ=0.3…μ=0.999" |
| 对比关系 Exp6 vs Exp2 | §4.7.6 "Exp6 vs Exp2：自蒸馏的贡献" |
| 成功标准 | §4.7.6 "成功标准…Exp6 > Exp2…预期提升1-2%" |

---

## 8. 超参数敏感性

| 超参数 | 当前值 | 建议搜索空间 |
|-------|-------|------------|
| λ（自蒸馏权重） | 0.3 | {0.1, 0.2, 0.3, 0.4, 0.5} |
| μ（EMA衰减） | 0.999 | {0.99, 0.999, 0.9995} |
| T（温度） | 2.0 | {1.5, 2.0, 2.5} |

---

## 9. 实现变体（可选）

### 9.1 无 EMA 变体
直接使用历史检查点作为教师：
```python
# 每隔 K 个 step 保存 checkpoint
if step % K == 0:
    teacher = load_checkpoint(step - K)
# 用历史 checkpoint 作为教师
```

### 9.2 双 EMA 变体
维护两个 EMA：
- **EMA-fast**：μ = 0.99（快速适应）
- **EMA-slow**：μ = 0.9995（长期平滑）

---

*本文档由 Claude Code 生成，基于 GeoKD-SR 实验设计方案 V5.2。*
