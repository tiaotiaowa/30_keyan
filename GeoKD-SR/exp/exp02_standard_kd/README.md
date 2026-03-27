# Exp02: Standard-KD（通用蒸馏基线）

## 实验概述

**实验名称**: B2-Standard-KD
**实验类型**: 知识蒸馏基线
**训练方法**: Hinton 2015 经典KL蒸馏（Forward KL）
**损失函数**: `L_KD = α × L_soft + (1-α) × L_hard`

### 实验目的
- 实现Hinton 2015经典知识蒸馏方法
- 作为蒸馏实验的基线对比
- 验证蒸馏相比直接SFT的提升效果

### 损失函数详解
```
L_KD = α × KL(P_T || P_S) × T² + (1-α) × CE(y, P_S)

其中:
- P_T: 教师模型的软标签分布
- P_S: 学生模型的软标签分布
- T: 温度参数（默认2.0）
- α: 蒸馏权重（默认0.5）
- CE: 交叉熵损失
```

## 目录结构

```
exp02_standard_kd/
├── config.yaml          # 实验配置文件
├── train.py             # 训练脚本（含DistillationTrainer）
├── evaluate.py          # 评估脚本
├── README.md            # 本说明文档
├── checkpoints/         # 模型检查点目录
│   └── final_model/     # 最终模型
├── logs/                # 训练日志目录
│   └── train_*.log      # 训练日志
└── results/             # 评估结果目录
    └── evaluation_*.json
```

## 模型配置

### 教师模型
- **基础模型**: Qwen2.5-7B-Instruct
- **本地路径**: `/mnt/workspace/models/Qwen2.5-7B-Instruct`
- **量化方式**: 4-bit量化（BitsAndBytes）
- **训练状态**: 冻结参数，仅用于推理

### 学生模型
- **基础模型**: Qwen2.5-1.5B-Instruct
- **本地路径**: `/mnt/workspace/models/Qwen2.5-1.5B-Instruct`
- **训练方式**: LoRA 微调

### LoRA 参数
| 参数 | 值 | 说明 |
|------|-----|------|
| r | 8 | LoRA秩 |
| lora_alpha | 16 | 缩放系数 |
| lora_dropout | 0.05 | Dropout率 |
| target_modules | q_proj, k_proj, v_proj, o_proj | 目标层 |

### 教师模型4-bit量化配置
```python
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)
```

## 训练配置

### 针对24GB显存优化

| 参数 | 值 | 说明 |
|------|-----|------|
| batch_size | 2 | 每设备批次大小（降低以容纳教师模型）|
| gradient_accumulation_steps | 16 | 梯度累积步数 |
| **有效batch_size** | **32** | 实际批次大小 |
| learning_rate | 1e-4 | 学习率 |
| num_epochs | 3 | 训练轮数 |
| max_length | 1024 | 最大序列长度 |
| fp16 | True | 混合精度训练 |
| gradient_checkpointing | True | 梯度检查点 |

### 蒸馏参数

| 参数 | 值 | 说明 |
|------|-----|------|
| temperature | 2.0 | 软标签温度 |
| alpha | 0.5 | 蒸馏权重 |
| method | standard_kd | Forward KL蒸馏 |

### 显存估算（24GB A10）

| 组件 | 显存占用 |
|------|---------|
| 教师模型 (7B, 4-bit) | ~4 GB |
| 学生模型 (1.5B, FP16) | ~3 GB |
| 梯度 + 优化器 | ~4 GB |
| 激活值 (batch=2) | ~8 GB |
| **总计** | **~19 GB** ✅ |

## 蒸馏原理

### KL散度损失
```python
def kl_divergence_loss(student_logits, teacher_logits, temperature=2.0):
    """
    Forward KL: KL(P_T || P_S)

    让学生的分布尽可能覆盖教师的分布
    """
    # 教师的软标签分布
    p_teacher = F.softmax(teacher_logits / temperature, dim=-1)

    # 学生的对数软标签分布
    log_p_student = F.log_softmax(student_logits / temperature, dim=-1)

    # KL散度
    kl_loss = F.kl_div(log_p_student, p_teacher, reduction='batchmean')

    # 温度缩放
    return kl_loss * (temperature ** 2)
```

### DistillationTrainer 核心逻辑
```python
class DistillationTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        # 学生前向传播
        student_outputs = model(**inputs)
        student_logits = student_outputs.logits

        # 教师前向传播（不计算梯度）
        with torch.no_grad():
            teacher_outputs = self.teacher_model(**inputs)
            teacher_logits = teacher_outputs.logits

        # 软标签损失（KL散度）
        soft_loss = kl_divergence_loss(student_logits, teacher_logits, T)

        # 硬标签损失（交叉熵）
        hard_loss = F.cross_entropy(shift_logits, shift_labels)

        # 组合损失
        return self.alpha * soft_loss + (1 - self.alpha) * hard_loss
```

## 数据格式

### 输入数据（JSONL格式）
```json
{
  "id": "unique_id",
  "question": "地理空间推理问题...",
  "answer": "标准答案...",
  "spatial_relation_type": "directional|topological|metric|composite",
  "reasoning_chain": [...],
  "entities": {...},
  "difficulty": "easy|medium|hard"
}
```

### ChatML 模板格式
```text
<|im_start|>system
你是一个地理空间推理专家，擅长分析和解决空间关系问题。<|im_end|>
<|im_start|>user
{question}<|im_end|>
<|im_start|>assistant
{answer}<|im_end|>
```

### Labels 生成
- 用户部分（system + user）设为 `-100`，不计算损失
- 助手部分（assistant）保留原始 token IDs，用于计算损失
- 蒸馏时仅对有效位置计算KL散度

## 使用方法

### 1. 环境检查
```bash
# 检查GPU、依赖、模型路径、数据路径
python ../../scripts/check_environment.py
```

### 2. 开始训练
```bash
# 方式1：直接运行
python train.py --config config.yaml

# 方式2：使用脚本
cd ../../
bash scripts/run_exp.sh exp02
```

### 3. 恢复训练
```bash
python train.py --config config.yaml --resume checkpoints/checkpoint-xxx
```

### 4. 模型评估
```bash
# 评估最终模型
python evaluate.py \
    --config config.yaml \
    --checkpoint checkpoints/final_model \
    --benchmark ../../data/geosr_chain/final/test.jsonl \
    --output results/evaluation_results.json
```

## 评估指标

| 指标 | 说明 | 计算方式 |
|------|------|---------|
| **Accuracy (RA)** | 推理准确率 | 答案语义匹配 |
| **SR-F1** | 空间关系F1 | 空间关键词提取+匹配 |
| **BLEU-4** | 文本质量 | n-gram匹配 |
| **ROUGE-L** | 长文本匹配 | LCS算法 |

## 预期结果

### 性能预期（相比Exp01）
| 指标 | Exp01 (SFT) | Exp02 (KD) | 预期提升 |
|------|------------|------------|---------|
| Reasoning Accuracy | ~0.50 | ~0.55 | +5-10% |
| Spatial F1 | ~0.55 | ~0.60 | +5-10% |
| BLEU-4 | ~0.35 | ~0.40 | +10-15% |
| ROUGE-L | ~0.45 | ~0.50 | +5-10% |

### 训练时间估算
- 数据量：~9,000条训练数据
- 单epoch时间：~45-60分钟（A10 GPU，含教师推理）
- 总训练时间：~3-4小时（3 epochs）

## 与其他实验对比

| 实验 | 方法 | 教师模型 | 损失函数 |
|------|------|---------|---------|
| **Exp01** | Direct-SFT | 无 | CE |
| **Exp02** | Standard-KD | 7B (4-bit) | KL + CE |
| Exp03 | SRD-KD | 7B (4-bit) | SR Loss + KL + CE |
| Exp04 | CoT-Distill | 7B (4-bit) | CoT Loss + KL + CE |

## 代码改进说明

### 相比原版本的改进

1. **教师模型4-bit量化**
   ```python
   # 节省显存，从FP16的~14GB降到4-bit的~4GB
   quantization_config = BitsAndBytesConfig(
       load_in_4bit=True,
       bnb_4bit_quant_type="nf4",
       bnb_4bit_compute_dtype=torch.float16,
   )
   ```

2. **ChatML模板格式**
   ```python
   messages = [
       {"role": "system", "content": system_prompt},
       {"role": "user", "content": question},
       {"role": "assistant", "content": answer}
   ]
   text = tokenizer.apply_chat_template(messages, tokenize=False)
   ```

3. **有效位置KL计算**
   ```python
   # 只对非-100的位置计算KL散度
   valid_mask = labels[..., 1:] != -100
   valid_student_logits = shift_student_logits[valid_mask]
   valid_teacher_logits = shift_teacher_logits[valid_mask]
   ```

4. **训练过程监控**
   ```python
   # 每10步打印损失详情
   if self._step % 10 == 0:
       print(f"[Step {self._step}] soft_loss: {soft_loss:.4f}, "
             f"hard_loss: {hard_loss:.4f}, total_loss: {total_loss:.4f}")
   ```

## 故障排除

### 常见问题

1. **显存不足 (OOM)**
   ```yaml
   # 进一步降低batch_size
   batch_size: 1
   gradient_accumulation_steps: 32

   # 或使用CPU offload
   device_map: "auto"
   ```

2. **教师模型加载失败**
   ```bash
   # 检查bitsandbytes安装
   pip install bitsandbytes>=0.41.0

   # 检查CUDA版本兼容性
   python -c "import bitsandbytes; print(bitsandbytes.__version__)"
   ```

3. **KL散度NaN**
   ```python
   # 检查温度参数
   temperature: 2.0  # 不要太小

   # 检查有效位置数量
   if valid_student_logits.numel() == 0:
       soft_loss = torch.tensor(0.0)
   ```

4. **教师推理速度慢**
   ```python
   # 确保教师模型在eval模式
   teacher.eval()

   # 使用torch.no_grad()
   with torch.no_grad():
       teacher_outputs = teacher_model(**inputs)
   ```

## 实验记录模板

```markdown
## Exp02 实验记录

**日期**: YYYY-MM-DD
**GPU**: A10 24GB
**数据量**: 9,000 训练 / 800 验证 / 3,000 测试

### 训练配置
- batch_size: 2
- gradient_accumulation_steps: 16
- learning_rate: 1e-4
- temperature: 2.0
- alpha: 0.5

### 训练日志
- Epoch 1 loss: X.XXXX
- Epoch 2 loss: X.XXXX
- Epoch 3 loss: X.XXXX
- 训练时长: X小时X分钟

### 评估结果
| 指标 | 值 |
|------|-----|
| Reasoning Accuracy | X.XXXX |
| Spatial F1 | X.XXXX |
| BLEU-4 | X.XXXX |
| ROUGE-L | X.XXXX |

### 分析
- 对比Exp01提升: +X%
- 主要改进点: ...
- 待优化: ...
```

## 相关文件

- [实验设计方案](../GeoKD-SR-实验设计方案-V5.2.md)
- [Exp01 对照组](../exp01_direct_sft/README.md)
- [环境检查脚本](../../scripts/check_environment.py)
- [运行脚本](../../scripts/run_exp.sh)

## 参考文献

1. Hinton, G., Vinyals, O., & Dean, J. (2015). Distilling the Knowledge in a Neural Network. *arXiv preprint arXiv:1503.02531*.

## 版本历史

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-03-08 | v1.0 | 初始版本，添加4-bit量化和ChatML支持 |

---

*最后更新: 2026-03-08*
