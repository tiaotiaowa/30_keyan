# Exp8: 渐进式蒸馏（Progressive/Curriculum Distillation）

> **实验定位**：C6 组件的实现（B2 + C6）。
>
> 本实验在 Exp2 的基础上引入**渐进式训练**（课程学习），从简单的空间关系（directional）逐步过渡到复杂的组合推理（composite），让模型按难度递增学习。

**组件标识**：B2 + C6（Progressive/Curriculum）
**V5.2 依据**：§4.7.4（Exp8 定义），§4.7.6（对比关系）

---

## 1. 目的与假设

### 1.1 实验定位
- **C6 组件实现**：验证课程学习在空间推理任务中的价值
- **对比对象**：Exp2（标准 KD，无课程调度）

### 1.2 控制变量（与 Exp2 相同）
- 数据、模型、模板、超参均相同
- **数据全集相同**（不新增数据，仅改变训练顺序）
- 基础蒸馏框架相同

### 1.3 实验变量（与 Exp2 的差异）
- **新增**：课程调度（按关系类型分阶段训练）
- **修改**：训练过程中采样权重动态变化

### 1.4 预期结果
- **Exp8 > Exp2**：渐进式训练更稳定、最终更好
- **预期提升**：相比 Exp2 有提升

**V5.2 依据**：§4.7.6 "Exp8 vs Exp2：渐进式蒸馏的贡献"

---

## 2. 理论依据

### 2.1 KD/LLM 蒸馏角度

#### 2.1.1 课程学习（Curriculum Learning）
**核心思想**：从简单到渐进学习
- **简单样本**：帮助模型建立基础能力
- **困难样本**：在基础能力上提升

**优势**：
1. **优化平滑**：避免早期陷入困难样本的局部最优
2. **训练稳定**：梯度更稳定
3. **最终性能**：通常优于随机训练

#### 2.1.2 相关工作
- **Bengio 2009**： Curriculum Learning
- **Progressive Neural Networks**：逐步增加能力
- **Teacher-Student Curriculum**：教师选择课程

**V5.2 依据**：§4.7.4 "C6…从简单空间关系逐步过渡到复杂推理"

### 2.2 地理空间推理角度

#### 2.2.1 空间关系难度层次

| 难度 | 关系类型 | 理由 |
|-----|---------|------|
| 简单 | directional | 离散、8 方向、直观 |
| 中等 | topological | 5 类、需要九交模型 |
| 中等 | metric | 连续、数值计算 |
| 复杂 | composite | 多步骤、组合推理 |

**难度递增关系**：
```
directional → topological → metric/composite
```

#### 2.2.2 渐进学习的 Geo 价值
1. **方向基础**：先学会基本方向判断
2. **拓扑扩展**：在方向基础上学习空间关系
3. **数值推理**：引入距离计算
4. **组合推理**：综合运用前述能力

---

## 3. 方法口径

### 3.1 使用哪些字段

| 字段 | Exp8 用途 | 说明 |
|-----|----------|-----|
| `question` | 输入 | 转为 user 消息 |
| `answer` | 监督目标（L_hard） | 转为 assistant 消息 |
| **`spatial_relation_type`** | **课程分组** | **用于按难度分阶段** |

**V5.2 依据**：§4.7.4 字段使用矩阵（Exp8 行）

### 3.2 输入格式（与 Exp2 相同）
```
System: 你是一个地理空间推理专家...（固定）

User: {question}

Assistant: {answer}
```

### 3.3 课程调度设计

#### 3.3.1 阶段划分（V5.2 压缩版：3 epochs）

```
Epoch 1: 阶段1 - 方向关系
  - 采样权重：directional=1.0, 其他=0.0
  - 目标：建立方向判断基础

Epoch 2: 阶段2 - 拓扑关系
  - 采样权重：directional=0.3, topological=1.0, 其他=0.0
  - 目标：扩展到拓扑关系（保留方向复习）

Epoch 3: 阶段3 - 度量与组合
  - 采样权重：metric=1.0, composite=1.0
  - 目标：学习数值与组合推理
```

**V5.2 依据**：§4.7.4 "渐进式损失函数…权重调度（3 epoch压缩版）"

#### 3.3.2 权重调度函数
```python
def get_sampling_weights(epoch, total_epochs=3):
    if epoch == 0:  # 阶段1
        return {"directional": 1.0, "topological": 0.0, "metric": 0.0, "composite": 0.0}
    elif epoch == 1:  # 阶段2
        return {"directional": 0.3, "topological": 1.0, "metric": 0.0, "composite": 0.0}
    else:  # 阶段3
        return {"directional": 0.0, "topological": 0.0, "metric": 1.0, "composite": 1.0}
```

### 3.4 损失函数

#### 3.4.1 总损失（与 Exp2 相同）
```
L = α × L_soft + (1-α) × L_hard
```

#### 3.4.2 差异：采样策略
- **Exp2**：均匀采样所有类型
- **Exp8**：按课程调度采样

### 3.5 训练流程要点

#### 3.5.1 数据加载器（按权重采样）
```python
class CurriculumSampler:
    def __init__(self, dataset, weights):
        self.dataset = dataset
        self.weights = weights
        # 按 relation_type 分组索引
        self.groups = self._group_by_relation()

    def _group_by_relation(self):
        groups = {"directional": [], "topological": [], "metric": [], "composite": []}
        for idx, item in enumerate(self.dataset):
            groups[item["spatial_relation_type"]].append(idx)
        return groups

    def sample_batch(self, batch_size):
        # 按权重采样
        batch = []
        for r, w in self.weights.items():
            if w > 0:
                n = int(batch_size * w / sum(self.weights.values()))
                sampled = random.sample(self.groups[r], min(n, len(self.groups[r])))
                batch.extend(sampled)
        return [self.dataset[i] for i in batch]
```

#### 3.5.2 训练循环
```python
for epoch in range(num_epochs):
    # 获取当前 epoch 的采样权重
    weights = get_sampling_weights(epoch)

    # 更新数据加载器
    sampler = CurriculumSampler(train_dataset, weights)
    dataloader = DataLoader(sampler, ...)

    # 训练一个 epoch
    for batch in dataloader:
        loss = compute_loss(batch)
        loss.backward()
        optimizer.step()
```

---

## 4. 步骤建议

### 4.1 训练前准备

#### 4.1.1 数据准备（与 Exp2 相同）
- 数据文件：`data/final/final_1_final.jsonl`
- 确认每条数据包含 `spatial_relation_type` 字段

#### 4.1.2 课程设计
- 确认阶段划分（3 epochs，V5.2 压缩版）
- 确认每个阶段的采样权重

#### 4.1.3 Seed 与目录
- Seeds：[42, 123, 456, 789, 1024]（5 次）
- 输出目录：
  ```
  checkpoints/exp08/{seed}/
  logs/exp08/{seed}/
  results/exp08/{seed}/
  ```

### 4.2 训练中监控

#### 4.2.1 关键指标（与 Exp2 对比）
- **loss_hard**：CE 损失
- **loss_soft**：KL 损失
- **loss_total**：总损失
- **分类型 loss**：记录各类型的损失（监控课程进展）

#### 4.2.2 每 eval_steps（建议 500）
1. 在验证集上计算：
   - overall_accuracy
   - **分类型 accuracy**（关键！监控各阶段学习效果）
   - format_valid_rate

#### 4.2.3 阶段转换监控
- **Epoch 1 → 2**：检查 directional 性能是否稳固
- **Epoch 2 → 3**：检查 directional/topological 是否遗忘

### 4.3 训练后处理

#### 4.3.1 Checkpoint 选择
- **best_model**：验证集准确率最高的 checkpoint
- **final_model**：最后一个 epoch（学完所有阶段）

#### 4.3.2 评测执行
1. 在 test set 上生成预测
2. 使用统一评测协议
3. **分阶段分析**：对比各阶段类型的学习效果

#### 4.3.3 与 Exp2 对比
- **主要指标**：overall_accuracy 增幅
- **分层指标**：各关系类型的性能变化
- **遗忘分析**：早期类型的性能是否保持

---

## 5. 诊断与失败模式

### 5.1 常见陷阱

#### 5.1.1 "灾难性遗忘"
- **陷阱**：学习新阶段后，旧阶段性能下降
- **表现**：Epoch 3 时 directional 性能大幅下降
- **解决**：增加复习权重（如 directional=0.3）

#### 5.1.2 "难度划分不当"
- **陷阱**：metric 比 topological 更简单（数据分布问题）
- **表现**：课程顺序不合理
- **诊断**：分析各类型的单独性能

#### 5.1.3 "阶段过短"
- **陷阱**：每个阶段只有 1 epoch，学习不充分
- **表现**：早期类型性能不稳定
- **建议**：增加每个阶段的 epoch 数

### 5.2 性能诊断

| 现象 | 可能原因 | 建议排查 |
|-----|---------|---------|
| Exp8 > Exp2 | 课程学习有效 | 分析各阶段学习曲线 |
| Exp8 ≈ Exp2 | 课程学习无额外价值 | 检查难度划分 |
| Exp8 < Exp2 | 课程顺序不当 | 检查遗忘情况 |
| 遗忘严重 | 复习权重不足 | 增加旧类型权重 |

### 5.3 阶段学习曲线

| 类型 | Epoch 1 | Epoch 2 | Epoch 3 | 预期 |
|-----|---------|---------|---------|------|
| directional | ↑↑ | ↑（保持） | →（稳定） | 稳定 |
| topological | - | ↑↑ | →（稳定） | 学会 |
| metric | - | - | ↑↑ | 学会 |
| composite | - | - | ↑↑ | 学会 |

---

## 6. 预期结果与论文写作

### 6.1 预期性能范围
- **vs Exp2**：预期有提升
- **分类型**：早期类型（directional）可能持平或略低，但整体提升

### 6.2 论文写作建议

#### 6.2.1 Methods 章节
```
Exp8 (Progressive) 在标准 KD 的基础上引入课程学习调度。
我们按空间关系难度将训练分为 3 个阶段：

阶段1（Epoch 1）：仅训练 directional 类型，建立方向判断基础
阶段2（Epoch 2）：训练 topological 类型，保留 directional 复习（权重0.3）
阶段3（Epoch 3）：训练 metric 和 composite 类型

各阶段通过动态采样权重实现，使模型从简单到复杂渐进学习。
课程设计基于空间认知难度：directional（离散8方向）< topological（5类）
< metric（数值计算）< composite（多步推理）。
```

#### 6.2.2 Experiments 章节
```
表X：各实验在 GeoKD-SR 测试集上的性能（均值±标准差）

| 实验 | Overall | Directional | Topological | Metric | Composite |
|-----|---------|------------|-------------|--------|-----------|
| Exp2 (KD) | XX.X±X.X | ... | ... | ... | ... |
| Exp8 (Prog) | YY.Y±Y.Y | ... | ... | ... | ... |
...
```

#### 6.2.3 Ablation 讨论
```
Exp8 相比 Exp2 提升了 Z.Z%（p < 0.05），表明课程学习有效。
分阶段分析显示，Exp8 在所有类型上均有提升，特别是 composite
类型提升最大（X.X% → Y.Y%），说明渐进式学习为复杂推理任务
打下了更好的基础。我们还观察到，Exp8 的训练曲线更平滑，
验证集损失波动更小，说明课程学习提高了训练稳定性。
```

#### 6.2.4 学习曲线（建议）
```
图X：Exp2 与 Exp8 的训练曲线对比。上图为 overall accuracy，
下图为各关系类型的分阶段学习曲线。Exp8 的 directional 性能
在 Epoch 1 快速上升，topological 在 Epoch 2 上升，metric/composite
在 Epoch 3 上升，验证了课程设计的有效性。
```

---

## 7. V5.2 引用定位

| 内容 | V5.2 位置 |
|-----|-----------|
| Exp8 定义 | §4.7.4 表格（Exp8 行） |
| C6 组件说明 | §4.7.4 "C6…从简单空间关系逐步过渡到复杂推理" |
| 权重调度 | §4.7.4 "渐进式损失函数…权重调度（3 epoch压缩版）" |
| 阶段划分 | §4.7.4 "阶段1方向…阶段2拓扑…阶段3度量+组合" |
| 对比关系 Exp8 vs Exp2 | §4.7.6 "Exp8 vs Exp2：渐进式蒸馏的贡献" |
| Epoch 压缩说明 | 约2198–2200行 "训练阶段从12 epoch压缩为3 epoch" |

---

## 8. 课程设计变体（可选）

### 8.1 更细粒度阶段
```
Epoch 1-2: directional
Epoch 3-4: topological
Epoch 5-6: metric
Epoch 7-8: composite
```

### 8.2 连续权重调度
```python
def get_sampling_weights(epoch, total_epochs):
    # 线性插值
    p = epoch / total_epochs
    return {
        "directional": 1.0 - 0.5 * p,
        "topological": min(1.0, 2 * p),
        "metric": max(0, 2 * (p - 0.5)),
        "composite": max(0, 2 * (p - 0.5))
    }
```

### 8.3 自适应课程
根据验证集性能动态调整：
```python
if directional_acc > threshold:
    # 进入下一阶段
    ...
```

---

*本文档由 Claude Code 生成，基于 GeoKD-SR 实验设计方案 V5.2。*
