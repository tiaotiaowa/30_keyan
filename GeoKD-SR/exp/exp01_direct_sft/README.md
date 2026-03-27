# Exp01: Direct-SFT（对照组）

## 实验概述

**实验名称**: B1-Direct-SFT
**实验类型**: 对照组基线
**训练方法**: 直接监督微调（Supervised Fine-Tuning）
**损失函数**: `L_SFT = CrossEntropy(student_logits, labels)`

### 实验目的
- 作为对照组验证知识蒸馏的有效性
- 提供无蒸馏的基线性能指标
- 与后续蒸馏实验进行对比分析

## 目录结构

```
exp01_direct_sft/
├── config.yaml          # 实验配置文件
├── train.py             # 训练脚本
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

## 训练配置

### 针对24GB显存优化

| 参数 | 值 | 说明 |
|------|-----|------|
| batch_size | 4 | 每设备批次大小 |
| gradient_accumulation_steps | 8 | 梯度累积步数 |
| **有效batch_size** | **32** | 实际批次大小 |
| learning_rate | 2e-4 | 学习率 |
| num_epochs | 3 | 训练轮数 |
| max_length | 1024 | 最大序列长度 |
| fp16 | True | 混合精度训练 |
| gradient_checkpointing | True | 梯度检查点 |

### 显存估算（24GB A10）

| 组件 | 显存占用 |
|------|---------|
| 学生模型 (1.5B, FP16) | ~3 GB |
| 梯度 + 优化器 | ~4 GB |
| 激活值 (batch=4) | ~6 GB |
| **总计** | **~13 GB** ✅ |

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
bash scripts/run_exp.sh exp01
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

### 空间关系关键词
```python
SPATIAL_KEYWORDS = [
    # 方向关系
    "东", "西", "南", "北", "东北", "西北", "东南", "西南",
    # 拓扑关系
    "相邻", "包含", "相交", "相离", "重叠", "邻接",
    # 度量关系
    "距离", "米", "公里", "千米", "远", "近",
]
```

## 预期结果

### 性能基线（参考）
| 指标 | 预期范围 |
|------|---------|
| Reasoning Accuracy | 0.45 - 0.55 |
| Spatial F1 | 0.50 - 0.60 |
| BLEU-4 | 0.30 - 0.40 |
| ROUGE-L | 0.40 - 0.50 |

### 训练时间估算
- 数据量：~9,000条训练数据
- 单epoch时间：~30-45分钟（A10 GPU）
- 总训练时间：~2-3小时（3 epochs）

## 代码改进说明

### 相比原版本的改进

1. **数据加载安全**
   ```python
   # 旧版本（不安全）
   item = eval(line.strip())

   # 新版本（安全）
   item = json.loads(line.strip())
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

3. **Labels正确生成**
   ```python
   # 计算用户部分长度
   user_text = tokenizer.apply_chat_template(
       [{"role": "system", ...}, {"role": "user", ...}],
       tokenize=False, add_generation_prompt=True
   )
   user_len = len(tokenizer.encode(user_text))

   # 用户部分设为 -100
   labels = [-100] * user_len + input_ids[user_len:]
   ```

## 故障排除

### 常见问题

1. **显存不足 (OOM)**
   ```yaml
   # 降低batch_size
   batch_size: 2
   gradient_accumulation_steps: 16

   # 或减少序列长度
   max_length: 512
   ```

2. **模型路径找不到**
   ```bash
   # 检查模型是否存在
   ls /mnt/workspace/models/Qwen2.5-1.5B-Instruct/

   # 或使用HuggingFace路径（需要联网）
   name: "Qwen/Qwen2.5-1.5B-Instruct"
   ```

3. **ChatML模板警告**
   ```python
   # 确保使用最新版本的transformers
   pip install transformers>=4.37.0
   ```

## 相关文件

- [实验设计方案](../GeoKD-SR-实验设计方案-V5.2.md)
- [环境检查脚本](../../scripts/check_environment.py)
- [运行脚本](../../scripts/run_exp.sh)
- [数据验证脚本](../../scripts/validate_dataset_v2.py)

## 版本历史

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-03-08 | v1.0 | 初始版本，添加ChatML支持和labels生成 |

---

*最后更新: 2026-03-08*
