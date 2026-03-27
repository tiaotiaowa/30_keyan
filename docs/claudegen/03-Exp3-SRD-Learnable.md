# Exp3: 空间关系蒸馏（SRD）- 可学习权重

> **实验定位**：C1 组件的**完整实现**（B2 + C1-Learnable）。
>
> 本实验在 Exp3a 的基础上，将固定等权重改为**可学习权重**，通过 softmax 参数化和先验初始化，让学生自动学习不同空间关系类型的蒸馏强度。

**组件标识**：B2 + C1（Learnable Weights）
**V5.2 依据**：§4.7.4（Exp3 定义），§4.7.6（对比关系）

---

## 1. 目的与假设

### 1.1 实验定位
- **C1 组件完整实现**：验证可学习权重空间关系蒸馏
- **对比对象**：
  - **Exp3a**：验证可学习权重是否优于等权重
  - **Exp2**：验证空间关系蒸馏损失的独立贡献

### 1.2 控制变量（与 Exp3a/Exp2 相同）
- 数据、模型、模板、超参均相同
- 基础蒸馏框架（Forward KL + hard label）相同

### 1.3 实验变量（与 Exp3a 的差异）
- **权重**：从固定 1.0 改为**可学习参数**
- **参数化**：softmax 确保权重非负且归一
- **初始化**：基于 GIS 先验设定初始值

### 1.4 预期结果
- **Exp3 > Exp3a**：可学习权重优于等权重
- **Exp3 > Exp2**：空间关系蒸馏有独立贡献
- **预期提升**：相比 Exp2 提升 2-3%

**V5.2 依据**：§4.7.6 对比表 + "成功标准…Exp3 > Exp2…预期提升2-3%"

---

## 2. 理论依据

### 2.1 KD/LLM 蒸馏角度

#### 2.1.1 为什么需要可学习权重？
不同空间关系类型的**难度**与**信息量**不同：
- **directional**：相对简单，8 方向，离散空间
- **topological**：中等难度，5 类拓扑关系
- **metric**：较难，连续数值推理
- **composite**：最复杂，组合推理

**Exp3a 的等权重假设**：所有类型同等重要 → 可能次优
**Exp3 的可学习权重**：让模型自动发现最优权重分配

#### 2.1.2 权重学习的动机
1. **难度差异**：难类型（composite/metric）可能需要更强监督
2. **信息密度**：某些类型可能包含更多“暗知识”
3. **数据不平衡**：训练集中各类型样本数可能不同

#### 2.1.3 参数化方式（Softmax）
```
w(r) = exp(θ_r) / Σ_{r'} exp(θ_{r'})
```
- **θ_r**：可学习参数（logit）
- **w(r)**：最终权重（自动归一）
- **优势**：保证权重非负且和为 1（或固定缩放）

### 2.2 地理空间推理角度

#### 2.2.1 GIS 理论先验（初始化依据）

基于空间认知与任务难度，V5.2 给出以下初始化先验：

| 关系类型 | 初始权重 | 理由 |
|---------|---------|------|
| directional | 1.5 | 8 方向，相对简单 |
| topological | 1.3 | 5 类拓扑，中等难度 |
| metric | 1.0 | 数值推理，基准 |
| composite | 1.8 | 组合推理，最复杂 |

**V5.2 依据**：§4.7.4 "relation_weights…directional 1.5…topological 1.3…metric 1.0…composite 1.8"

#### 2.2.2 为什么 composite 权重最高？
- **组合推理**：需要同时考虑方向与距离
- **步骤更长**：推理链更复杂
- **错误更多**：教师与学生可能都有较高错误率

---

## 3. 方法口径

### 3.1 使用哪些字段

| 字段 | Exp3 用途 | 说明 |
|-----|----------|-----|
| `question` | 输入 | 转为 user 消息 |
| `answer` | 监督目标（L_hard） | 转为 assistant 消息 |
| **`spatial_relation_type`** | **分组依据** | **用于按类型加权 KL** |

**V5.2 依据**：§4.7.4 字段使用矩阵（Exp3 行）

### 3.2 输入格式（与 Exp3a/Exp2 相同）
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
- **α = 0.5**（与 Exp2/Exp3a 相同）

#### 3.3.2 L_SRD（空间关系蒸馏损失，可学习权重）
```
L_SRD = (1/N) × Σ_{i=1}^{N} w(r_i) × KL(P_T^i || P_S^i)
```
- **r_i**：样本 i 的 `spatial_relation_type`
- **w(r)**：关系类型权重，**可学习**

#### 3.3.3 权重参数化与初始化
```python
# 可学习参数（logits）
θ = {
    "directional": log(1.5),
    "topological": log(1.3),
    "metric": log(1.0),
    "composite": log(1.8)
}

# Softmax 归一
w(r) = exp(θ[r]) / (exp(θ[directional]) + exp(θ[topological]) + exp(θ[metric]) + exp(θ[composite]))
```

**V5.2 依据**：§4.7.4 "w(r)=softmax([w_dir,w_topo,w_metric,w_comp])…初始化权重"

### 3.4 训练流程要点

#### 3.4.1 前向传播
```
# 学生前向
student_logits = student(input_ids)

# 教师前向
with torch.no_grad():
    teacher_logits = teacher(input_ids)

# 计算 L_hard
loss_hard = CrossEntropy(student_logits[mask], labels[mask])

# 计算当前权重（softmax）
w = softmax(θ)  # θ 是可学习参数

# 计算 L_SRD（按关系类型分组，使用可学习权重）
soft_teacher = softmax(teacher_logits / T, dim=-1)
soft_student = softmax(student_logits / T, dim=-1)

kl_per_token = KL_div(soft_teacher, soft_student)
loss_srd = 0
count = 0
for r in ["directional", "topological", "metric", "composite"]:
    mask_r = (relation_type == r) & valid_mask
    if mask_r.any():
        loss_srd += w[r] * kl_per_token[mask_r].sum()
        count += mask_r.sum()
loss_srd = loss_srd / count

# 总损失
loss = α × loss_srd + (1-α) × loss_hard
```

#### 3.4.2 反向传播
```
loss.backward()
optimizer.step()  # 更新学生参数 + 权重参数 θ
```

#### 3.4.3 关键实现细节
- **权重优化器**：θ 与学生参数共同优化（或单独学习率）
- **权重约束**：softmax 自动保证非负归一
- **权重监控**：训练中记录 w(r) 的变化

---

## 4. 步骤建议

### 4.1 训练前准备

#### 4.1.1 数据准备（与 Exp3a 相同）
- 数据文件：`data/final/final_1_final.jsonl`
- 确认每条数据包含 `spatial_relation_type` 字段

#### 4.1.2 权重初始化
```python
# 建议初始化
initial_weights = {
    "directional": 1.5,
    "topological": 1.3,
    "metric": 1.0,
    "composite": 1.8
}
# 转为 logits（log 空间）
import math
θ = {k: math.log(v) for k, v in initial_weights.items()}
```

#### 4.1.3 Seed 与目录
- Seeds：[42, 123, 456, 789, 1024]（5 次）
- 输出目录：
  ```
  checkpoints/exp03/{seed}/
  logs/exp03/{seed}/
  results/exp03/{seed}/
  ```

### 4.2 训练中监控

#### 4.2.1 关键指标（与 Exp3a 对比）
- **loss_hard**：CE 损失
- **loss_srd**：加权 KL 损失
- **权重 w(r)**：**新增！记录每个 epoch 的权重值**

#### 4.2.2 每 eval_steps（建议 500）
1. 在验证集上计算：
   - overall_accuracy
   - 分类型 accuracy
   - format_valid_rate
2. 记录当前权重 w(r)，分析学习动态

#### 4.2.3 权重分析（关键诊断）
- **收敛趋势**：权重是否稳定？
- **最终值**：是否符合先验？（如 composite 最高）
- **异常情况**：某权重塌缩到 0 或主导

### 4.3 训练后处理

#### 4.3.1 Checkpoint 选择
- **best_model**：验证集准确率最高的 checkpoint
- **保存权重**：记录最佳权重配置

#### 4.3.2 评测执行
1. 在 test set 上生成预测
2. 使用统一评测协议
3. **重点分析**：分类型性能 vs Exp3a/Exp2

#### 4.3.3 权重可视化
建议绘制权重变化曲线：
- X 轴：training step
- Y 轴：权重值
- 4 条线：directional / topological / metric / composite

---

## 5. 诊断与失败模式

### 5.1 常见陷阱

#### 5.1.1 权重塌缩
- **陷阱**：某权重接近 1，其他接近 0
- **可能原因**：
  - 该类型样本主导训练
  - 学习率过高
  - 初始化偏差过大
- **后果**：模型退化为“单类型专家”

#### 5.1.2 权重震荡
- **陷阱**：权重在训练中剧烈波动
- **可能原因**：
  - 学习率过高
  - batch size 过小
  - 各类型样本分布不均
- **建议**：降低权重学习率或使用权重 EMA

#### 5.1.3 权重与先验偏离
- **陷阱**：权重与 GIS 先验相反（如 directional > composite）
- **可能原因**：
  - 先验设定错误
  - 数据分布异常（如 composite 样本噪声大）
- **诊断**：检查数据质量，分析是否合理

### 5.2 性能诊断

| 现象 | 可能原因 | 建议排查 |
|-----|---------|---------|
| Exp3 ≈ Exp3a | 权重学习无价值 | 检查权重变化幅度 |
| Exp3 < Exp3a | 权重学习引入噪声 | 检查学习率、初始化 |
| Exp3 >> Exp3a | 某类型显著改善 | 分析哪类权重主导 |
| Exp3 ≈ Exp2 | SRD 整体无效 | 检查关系类型标注质量 |

### 5.3 权重解释（论文写作）

| 权重排序 | 可能解释 | 论文写作角度 |
|---------|---------|------------|
| composite > metric > topo > dir | 符合难度先验 | "模型自动学习了任务难度层级" |
| metric > composite > ... | 数值推理更难 | "距离估计需要更强监督" |
| dir > topo > ... | 简单类型主导？ | 需分析数据分布 |

---

## 6. 预期结果与论文写作

### 6.1 预期性能范围
- **vs Exp2**：预期提升 2-3%
- **vs Exp3a**：预期提升 1-2%
- **权重收敛**：预期 composite/metric 权重较高

### 6.2 论文写作建议

#### 6.2.1 Methods 章节
```
Exp3 (SRD-Learnable) 在 Exp3a 的基础上引入可学习的关系类型权重。
我们使用 softmax 参数化权重：

w(r) = exp(θ_r) / Σ_{r'} exp(θ_{r'})

其中 θ_r 为可学习参数，基于 GIS 任务难度初始化：
θ_directional = log(1.5), θ_topological = log(1.3),
θ_metric = log(1.0), θ_composite = log(1.8)。

权重与学生参数联合优化，自动学习各类型的蒸馏强度。
```

#### 6.2.2 Experiments 章节
```
表X：各实验在 GeoKD-SR 测试集上的性能（均值±标准差）

| 实验 | Overall | Directional | Topological | Metric | Composite |
|-----|---------|------------|-------------|--------|-----------|
| Exp2 (KD) | XX.X±X.X | ... | ... | ... | ... |
| Exp3a (SRD-U) | YY.Y±Y.Y | ... | ... | ... | ... |
| Exp3 (SRD-L) | ZZ.Z±Z.Z | ... | ... | ... | ... |
...
```

#### 6.2.3 Ablation 讨论
```
Exp3 相比 Exp3a 提升了 W.W%（p < 0.05），表明可学习权重优于等权重。
训练收敛后，权重分布为 w(composite)=X.XX, w(metric)=Y.YY,
w(topological)=Z.ZZ, w(directional)=V.VV，符合任务难度先验：
复杂推理类型（composite）需要更强的蒸馏监督。
```

#### 6.2.4 权重可视化说明
```
图X：Exp3 训练过程中关系类型权重的变化曲线。权重在训练早期
快速调整，并在 epoch 2 后收敛。最终权重排序为 composite > metric
> topological > directional，与空间推理任务难度一致。
```

---

## 7. V5.2 引用定位

| 内容 | V5.2 位置 |
|-----|-----------|
| Exp3 定义 | §4.7.4 表格（Exp3 行） |
| 权重参数化 | §4.7.4 "w(r)=softmax([w_dir,w_topo,w_metric,w_comp])" |
| 初始化权重 | §4.7.4 "初始化权重…directional=1.5…composite=1.8" |
| 对比关系 Exp3 vs Exp3a | §4.7.6 "Exp3 vs Exp3a：可学习权重是否优于等权重" |
| 对比关系 Exp3 vs Exp2 | §4.7.6 "Exp3 vs Exp2：空间关系蒸馏损失的贡献" |
| 成功标准 | §4.7.6 "成功标准…Exp3 > Exp2…预期提升2-3%" |

---

## 8. 超参数敏感性

| 超参数 | 当前值 | 建议搜索空间 |
|-------|-------|------------|
| 初始权重 | GIS 先验 | 可尝试 uniform 初始化对比 |
| 权重学习率 | 与学生相同 | 可尝试降低 10× |
| 权重归一方式 | softmax | 可尝试 temperature-scaled softmax |

---

*本文档由 Claude Code 生成，基于 GeoKD-SR 实验设计方案 V5.2。*
