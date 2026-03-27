# Exp1: Direct-SFT（直接监督微调，无蒸馏）

> **实验定位**：GeoKD-SR 实验矩阵的**基线对照组**（B1）。
>
> 本实验使用**纯监督微调**，仅对标准答案计算交叉熵损失，**不引入任何蒸馏信号**。用于回答“蒸馏是否有效”的最小对照。

**组件标识**：B1（Direct-SFT）
**V5.2 依据**：§4.7.4（Exp1 定义），§4.7.6（对比关系）

---

## 1. 目的与假设

### 1.1 实验定位
- **对照组**：作为所有蒸馏实验的最低基准
- **验证假设**：蒸馏（Exp2）应显著优于纯 SFT（Exp1）

### 1.2 控制变量（与 Exp2–Exp9 完全相同）
- 数据：同一份数据（`final_1_final.jsonl` + manifest）
- 模型：同一学生模型（Qwen2.5-1.5B-Instruct）
- 模板：同一 ChatML chat_template 与 system_prompt
- 超参：同一训练超参（lr=1e-4, batch=8, accum=16, epochs=3, ...）

### 1.3 实验变量
- **唯一的差异**：不引入教师模型的 soft label，仅使用标准答案的 hard label

### 1.4 预期结果
- **Exp2 > Exp1**：蒸馏有效，预期提升 5-10%
- 若 Exp2 ≯ Exp1：说明蒸馏信号对该任务/数据不敏感，或教师噪声/风格不匹配

**V5.2 依据**：§4.7.6 对比表（Exp2 vs Exp1）

---

## 2. 理论依据

### 2.1 KD/LLM 蒸馏角度

#### 2.1.1 为什么需要无蒸馏基线？
在知识蒸馏研究中，**必须回答的第一个问题是“蒸馏是否真的有效”**。Exp1 作为对照组，提供以下参考：
- **能力上界**：纯 SFT 在该数据规模下的最佳性能
- **蒸馏增益**：Exp2 - Exp1 的差值即为“蒸馏的纯贡献”
- **方法论意义**：若蒸馏无增益，说明数据/任务/教师存在不匹配

#### 2.1.2 交叉熵损失的标准形式
```
L_SFT = CrossEntropy(student_logits, labels)
```
- **labels**：来自数据集的 `answer` 字段
- **监督范围**：仅对 assistant 段计算（system+user 段 masked 为 -100）

#### 2.1.3 相关工作定位
- **标准 SFT**：在指令微调文献中广泛使用（e.g., InstructGPT, Vicuna）
- **无蒸馏**：相当于“学生仅学习人类标注，未利用教师分布”

### 2.2 地理空间推理角度

#### 2.2.1 任务特点
- **输入**：地理空间问题（`question`）
- **输出**：结构化答案（`answer` + 隐含的空间关系类型）
- **挑战**：需要理解方向、拓扑、度量等空间关系

#### 2.2.2 纯 SFT 的局限性
- **答案稀疏**：仅监督最终答案，未显式监督推理过程
- **空间关系隐式**：空间关系类型（directional/topological/metric/composite）隐含在问题与答案中，未显式利用

#### 2.2.3 Exp1 作为 Geo 任务基线
- **最小假设**：仅假设标注答案正确
- **泛化能力**：测试学生在 10000 条数据上能否学会空间推理
- **后续对比**：Exp2 的蒸馏增益可理解为“教师分布提供了答案之外的暗知识”

---

## 3. 方法口径

### 3.1 使用哪些字段

| 字段 | Exp1 用途 | 说明 |
|-----|----------|-----|
| `question` | 输入 | 转为 user 消息 |
| `answer` | 监督目标 | 转为 assistant 消息，计算 CE |
| `spatial_relation_type` | ~~不使用~~ | 仅用于分层统计，不影响训练 |
| `reasoning_chain` | ~~不使用~~ | Exp1 不蒸馏推理过程 |
| `entities` | ~~不使用~~ | 不做实体级监督 |
| `entity_to_token` | ~~不使用~~ | 不做 token 对齐 |

**V5.2 依据**：§4.7.4 字段使用矩阵（Exp1 行）

### 3.2 输入格式（统一 ChatML）

```
System: 你是一个地理空间推理专家...（固定 system prompt）

User: {question}

Assistant: {answer}
```

- **构造方式**：使用 `tokenizer.apply_chat_template()`
- **监督范围**：仅 Assistant 段计算损失

**V5.2 依据**：§4.7.2 统一输入格式

### 3.3 损失函数

#### 3.3.1 总损失
```
L = L_SFT
```

#### 3.3.2 L_SFT（交叉熵）
```
L_SFT = CrossEntropy(student_logits, labels)
```
- **labels**：answer 文本的 token 序列
- **mask**：system+user 段为 -100，仅 assistant 段计算

#### 3.3.3 无蒸馏组件
- **无 KL 项**：不使用教师模型
- **无温度参数**：T 无意义
- **无额外权重**：α、λ 等均不适用

**V5.2 依据**：§4.7.4 Exp1 损失定义

### 3.4 训练流程要点

#### 3.4.1 前向传播
```
logits = student(input_ids)
loss = CrossEntropy(logits[mask], labels[mask])
```

#### 3.4.2 反向传播
```
loss.backward()
optimizer.step()
```

#### 3.4.3 无特殊处理
- 无教师模型前向
- 无 KL 计算
- 无 EMA 更新
- 无课程调度

---

## 4. 步骤建议

### 4.1 训练前准备

#### 4.1.1 数据准备
1. 确认数据文件：`data/final/final_1_final.jsonl`
2. 导出官方 splits（若未导出）：
   - `data/official_splits/geokd_sr_final_1_final_v1/train.jsonl`
   - `data/official_splits/geokd_sr_final_1_final_v1/dev.jsonl`
   - `data/official_splits/geokd_sr_final_1_final_v1/test.jsonl`
3. 生成 dataset_manifest.json（记录 sha256）

#### 4.1.2 环境配置
- 硬件：A10 24GB（单机单卡）
- 软件：Python 3.12.12, PyTorch 2.6.0+cu124, Transformers 4.48.3
- 混合精度：bf16
- 梯度检查点：gradient_checkpointing=True

#### 4.1.3 Seed 与目录
- Seeds：[42, 123, 456, 789, 1024]（5 次）
- 输出目录：
  ```
  checkpoints/exp01/{seed}/
  logs/exp01/{seed}/
  results/exp01/{seed}/
  ```

### 4.2 训练中监控

#### 4.2.1 关键指标
- **train_loss**：总损失（仅 CE）
- **eval_loss**：验证集损失
- **learning_rate**：当前学习率（cosine 调度）

#### 4.2.2 每 eval_steps（建议 500）
1. 在验证集上计算：
   - overall_accuracy
   - 分类型 accuracy（directional/topological/metric/composite）
   - format_valid_rate（测试时使用强制 JSON 输出）

#### 4.2.3 异常检测
- **loss 不收敛**：检查学习率、数据质量
- **format_valid_rate 过低**：检查 prompt 模板、输出约束

### 4.3 训练后处理

#### 4.3.1 Checkpoint 选择
- **best_model**：验证集准确率最高的 checkpoint
- **final_model**：最后一个 epoch 的 checkpoint

#### 4.3.2 评测执行
1. 在 test set 上生成预测
2. 使用统一评测协议：
   - 强制 JSON 块输出
   - 方向归一化、拓扑映射、距离容差
   - 分层统计、错误 taxonomy

#### 4.3.3 结果记录
- metrics.json（含 meta、overall、stratified、error_analysis）
- predictions.jsonl（逐样本预测与错误类型）
- report.md（汇总表 + Top-K 失败案例）

---

## 5. 诊断与失败模式

### 5.1 常见陷阱

#### 5.1.1 “看似提升但实际无效”
- **陷阱**：format_valid_rate 低，但只报告 overall_accuracy
- **诊断**：若 format_valid_rate < 0.9，需先修复输出格式，再对比性能

#### 5.1.2 数据泄露
- **陷阱**：answer 中包含提示信息（如“答案是东”）
- **诊断**：检查数据集，确保 answer 纯为结论，不含推理提示

### 5.2 典型错误类型

#### 5.2.1 方向错误（directional）
- **表现**：方向判断相反（如“东”误判为“西”）
- **可能原因**：
  - 学生未掌握相对方向概念
  - 训练数据中方向关系标注不一致

#### 5.2.2 拓扑混淆（topological）
- **表现**：within/contains 混淆，adjacent 误判为 disjoint
- **可能原因**：
  - 拓扑关系理解不足
  - 训练数据中样本不平衡

#### 5.2.3 距离偏差（metric）
- **表现**：距离估计数量级错误
- **可能原因**：
  - 数值推理能力弱
  - 坐标与地理距离的映射未学好

#### 5.2.4 格式错误（format）
- **表现**：无法解析 JSON 块
- **可能原因**：
  - 未训练强制 JSON 输出
  - prompt 缺少格式约束

### 5.3 与 Exp2 对比时的诊断

| 现象 | 可能原因 | 建议排查 |
|-----|---------|---------|
| Exp1 ≈ Exp2 | 教师无额外价值 | 检查教师质量、数据难度 |
| Exp1 > Exp2 | 蒸馏引入噪声 | 检查温度、权重、mask 范围 |
| Exp1 稳定性差 | 高方差？ | 增加重复次数、检查 seed 敏感性 |

---

## 6. 预期结果与论文写作

### 6.1 预期性能范围
- **overall_accuracy**：预期基线水平（具体需实验确定）
- **format_valid_rate**：应 > 0.95（训练充分时）

### 6.2 论文写作建议

#### 6.2.1 Methods 章节
```
Exp1 (Direct-SFT) 作为基线对照组，使用标准的监督微调方法，
仅对标准答案计算交叉熵损失，不引入任何蒸馏信号。
...
损失函数：L = CrossEntropy(student_logits, labels)
监督范围：仅对 assistant 段计算损失（system+user 段 masked）
```

#### 6.2.2 Experiments 章节
```
表X：各实验在 GeoKD-SR 测试集上的性能（均值±标准差）

| 实验 | Overall Acc | Direction Acc | Topology Acc | Metric Acc |
|-----|------------|--------------|--------------|------------|
| Exp1 (SFT) | XX.X±X.X | ... | ... | ... |
| Exp2 (KD) | YY.Y±Y.Y | ... | ... | ... |
...
```

#### 6.2.3 Ablation 讨论
```
Exp2 相比 Exp1 提升了 Z.Z%，表明教师模型的 soft label
提供了超越标准答案的暗知识，验证了蒸馏在该任务上的有效性。
```

---

## 7. V5.2 引用定位

| 内容 | V5.2 位置 |
|-----|-----------|
| Exp1 定义 | §4.7.4 表格（Exp1 行） |
| 损失函数 | §4.7.4 "L_SFT = CrossEntropyLoss..." |
| 公平性原则 | §4.7 "统一数据+字段可选+监督可控" |
| 字段使用矩阵 | §4.7.4 表格（Exp1 列） |
| 对比关系 Exp2 vs Exp1 | §4.7.6 "Exp2 vs Exp1...验证蒸馏有效性" |

---

*本文档由 Claude Code 生成，基于 GeoKD-SR 实验设计方案 V5.2。*
