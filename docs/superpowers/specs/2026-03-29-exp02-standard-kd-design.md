# Exp02 Standard-KD 蒸馏实验设计规格书

> 日期: 2026-03-29
> 状态: 待实现
> 目标: 验证Qwen2.5-7B教师能否通过标准知识蒸馏(Hinton 2015 Forward KL)有效提升Qwen2.5-1.5B学生的地理空间推理能力

## 1. 背景与动机

### 1.1 当前实验现状

| 模型 | Overall Acc | Dir | Topo | Metric | Composite |
|------|------------|-----|------|--------|-----------|
| GLM-4.7 (教师级别) | 72.87% | 85.62% | 55.62% | 88.93% | 61.38% |
| Qwen2.5-7B (教师) | 36.77% | 50.00% | 56.51% | 25.41% | 8.13% |
| Qwen2.5-1.5B (基线) | 23.16% | 43.49% | 24.85% | 17.59% | 3.66% |
| Qwen2.5-1.5B-SFT | 22.06% | 41.44% | 21.01% | 15.64% | 8.54% |

### 1.2 SFT失败的原因

直接SFT微调导致性能下降4.74%（23.16% → 22.06%），主要表现为：
- 拓扑关系偏见加剧（"位于内部"偏见从218增至250样本）
- 距离偏向加剧（"约1200公里"从436增至509样本）
- 灾难性遗忘（拓扑推理退化15.48%）

### 1.3 KD有望成功的理论依据

1. **软标签提供更丰富监督**：KD通过教师模型完整logits分布提供"暗知识"，而非仅one-hot标签
2. **7B有可迁移知识**：教师比基线高13.61pp（尤其topological高31.66pp）
3. **中间层知识迁移**：KL散度让学生学习教师的概率分布模式，**降学习率**

## 2. 实验设计

### 2.1 蒸馏方法

**Standard-KD (Hinton 2015)**：经典Forward KL蒸馏

```
L_KD = α × KL(P_T || P_S) × T² + (1-α) × CE(y, P_S)
```

- α = 0.5（软硬标签权重各半）
- T = 2.0（温度参数）
- KL散度仅计算assistant段（labels != -100的位置）

### 2.2 模型配置

| 角色 | 模型 | 配置 |
|------|------|------|
| 教师 | Qwen2.5-7B-Instruct | 4bit量化(NF4), 冻结参数, 仅推理 |
| 学生 | Qwen2.5-1.5B-Instruct | LoRA微调, **r=16, alpha=32**, 目标=[q,k,v,o]_proj |

> **参数审查说明**：LoRA秩从r=8调整为r=16（对齐SFT实际训练配置）。SFT用r=16有更多可训练参数，KD中同样需要足够的容量来吸收教师知识。scaling factor均为2.0（alpha/r）。

### 2.3 训练参数（经三方对比审查确认）

**审查依据**：V5.2实验设计方案 + SFT实际训练配置 + 当前exp02代码

| 参数 | V5.2方案 | SFT实际 | exp02修改后 | 说明 |
|------|---------|---------|-----------|------|
| learning_rate | 1e-4 | 5e-5 | **1e-4** | V5.2标准，KD有大batch(128)稳定梯度 |
| batch_size | 8 | 8 | **2** | 教师+学生同时加载A10，显存受限 |
| gradient_accumulation | 16 | 16 | **64** | effective=128，对齐V5.2和SFT |
| effective_batch | 128 | 128 | **128** | 三方一致 |
| num_epochs | 3 | 3 | **3** | 三方一致 |
| warmup_ratio | 0.1 | 0.1 | **0.1** | 三方一致 |
| weight_decay | 0.01 | 0.01 | **0.01** | 三方一致 |
| max_grad_norm | 1.0 | 1.0 | **1.0** | 三方一致 |
| max_length | 2048 | 1024 | **1024** | 对齐SFT实际，显存友好 |
| LoRA r | 8 | **16** | **16** | 对齐SFT，更多容量吸收教师知识 |
| LoRA alpha | 16 | **32** | **32** | 随r调整，scaling=2.0 |
| LoRA dropout | 0.05 | 0.05 | **0.05** | 三方一致 |
| 混合精度 | bf16 | bf16 | **bf16** | A10原生支持，比fp16更稳定 |
| lr_scheduler | cosine | cosine | **cosine** | 三方一致 |
| temperature | 2.0 | - | **2.0** | V5.2标准 |
| alpha (KD) | 0.5 | - | **0.5** | V5.2标准 |
| save_steps | - | epoch | **200** | 1 epoch≈74步，200步≈2.7 epoch保存一次 |
| eval_steps | - | epoch | **200** | 与save_steps对齐 |

> **核心修改项（7处）**：
> 1. 数据路径：`geosr_chain/final/` → `data/splits/`
> 2. System Prompt：有长prompt → `""`（空，对齐SFT）
> 3. LoRA r：8 → 16（对齐SFT）
> 4. LoRA alpha：16 → 32（随r调整）
> 5. gradient_accumulation：16 → 64（effective batch=128）
> 6. 混合精度：fp16 → bf16
> 7. save/eval_steps：500 → 200

### 2.4 显存预估 (A10 24GB)

| 组件 | 显存 |
|------|------|
| 教师 (7B, 4bit) | ~4 GB |
| 学生 (1.5B, FP16 + LoRA r=16) | ~3.5 GB |
| 梯度 + 优化器 (r=16更多参数) | ~5 GB |
| 激活值 (batch=2, max_len=1024) | ~8 GB |
| 总计 | ~20.5 GB |

> gradient_accumulation_steps=64不额外占用显存，只增加训练时间。预估训练步数：9463/128 ≈ 74步/epoch × 3 epochs = **222步总计**，每步含教师推理，预计15-25分钟。

### 2.5 训练数据格式

与之前SFT保持一致：**无system prompt**，简单ChatML格式。

```python
messages = [
    {"role": "user", "content": question},
    {"role": "assistant", "content": answer}
]
```

Labels生成：user段设为-100，仅assistant段计算损失。

### 2.6 评测方式

复用exp0两阶段评测框架：
1. **Stage1 生成**：加载LoRA模型，使用exp0的generation_config.yaml生成predictions.jsonl
2. **Stage2 评测**：调用exp0的DeterministicMetrics计算完整指标

确保评测结果与基线(23.16%)和SFT(22.06%)完全可比。

## 3. 文件结构与修改清单

### 3.1 目录结构

```
exp/exp02_standard_kd/
├── config.yaml              # [修改] 修正路径、LoRA参数、accumulation、混合精度、save_steps
├── train.py                 # [修改] 移除system prompt，统一为user+assistant格式，fp16→bf16
├── stage1_generate.py       # [新建] 加载LoRA模型，调用exp0生成框架
├── stage1_config.yaml       # [新建] 生成配置，复用exp0的prompt模板
├── stage2_evaluate.py       # [新建] 调用exp0评测框架计算指标
├── run.sh                   # [新建] 一键运行脚本
├── evaluate.py              # [保留] 旧版备用
└── README.md                # [更新]
```

### 3.2 修改详情

#### config.yaml（7项修改）

```yaml
# 修改项：
data:
  train_path: "../../data/splits/train.jsonl"   # [改1] 路径修正
  dev_path: "../../data/splits/dev.jsonl"       # [改1]
  test_path: "../../data/splits/test.jsonl"     # [改1]

model:
  teacher:
    name: "/mnt/workspace/models/Qwen2.5-7B-Instruct"
  student:
    name: "/mnt/workspace/models/Qwen2.5-1.5B-Instruct"
    lora:
      r: 16              # [改3] 从8改为16（对齐SFT）
      lora_alpha: 32      # [改4] 从16改为32（随r调整）
      lora_dropout: 0.05
      target_modules: ["q_proj", "k_proj", "v_proj", "o_proj"]

training:
  batch_size: 2
  gradient_accumulation_steps: 64  # [改5] 从16改为64，effective=128
  learning_rate: 1e-4
  num_epochs: 3
  warmup_ratio: 0.1
  weight_decay: 0.01
  max_grad_norm: 1.0
  max_length: 1024
  save_steps: 200   # [改7] 从500改为200
  eval_steps: 200   # [改7] 从500改为200

distillation:
  temperature: 2.0
  alpha: 0.5

# [改2] 删除 chat_template 节（不使用system prompt）
```

#### train.py（3项修改）

修改点：
1. `load_dataset` 函数：移除system_prompt参数，messages中不添加system角色
2. 构建messages时：直接用 `[{"role": "user", "content": question}, {"role": "assistant", "content": answer}]`
3. 移除main函数中获取system_prompt的逻辑
4. fp16=True → bf16=True [改6]
5. 其他蒸馏逻辑保持不变（KL散度、labels掩码、DataCollatorForSeq2Seq）

#### stage1_generate.py (新建)

基于exp0的 `stage1_generation/generate_answers.py`，关键修改：
- 加载模型时支持LoRA adapter (`PeftModel.from_pretrained`)
- 复用exp0的prompt模板和生成参数
- 输出格式与exp0完全一致的predictions.jsonl

```python
# 核心逻辑
base_model = AutoModelForCausalLM.from_pretrained(base_model_name, ...)
model = PeftModel.from_pretrained(base_model, lora_path)
model.merge_and_unload()  # 合并LoRA权重
# 然后使用与exp0完全相同的生成逻辑
```

#### stage1_config.yaml (新建)

复用exp0的generation_config.yaml，添加LoRA路径配置：

```yaml
model:
  base_name: "/mnt/workspace/models/Qwen2.5-1.5B-Instruct"
  lora_path: "checkpoints/final_model"
  device: "cuda"
  dtype: "float16"

# 以下与exp0完全相同
generation: ...
data: ...
prompt_template: ...  # 复用exp0的prompt模板
```

#### stage2_evaluate.py (新建)

直接调用exp0的评测模块：

```python
import sys
sys.path.insert(0, "../../exp0/exp0/stage2_evaluation")
from evaluate import Evaluator
# 使用与基线相同的eval_config.yaml
```

#### run.sh (新建)

```bash
#!/bin/bash
set -e
echo "=== Exp02 Standard-KD ==="

# Step 1: 训练
echo "[1/3] 开始蒸馏训练..."
python train.py --config config.yaml --seed 42

# Step 2: 生成
echo "[2/3] 生成预测结果..."
python stage1_generate.py --config stage1_config.yaml \
  --checkpoint checkpoints/final_model

# Step 3: 评测
echo "[3/3] 评测..."
python stage2_evaluate.py \
  --predictions outputs/predictions.jsonl \
  --output results/

echo "=== 完成 ==="
```

## 4. 验证方案

### 4.1 训练过程验证

- 监控soft_loss和hard_loss的下降趋势
- 每个epoch结束时检查eval_loss
- 如果soft_loss出现NaN，降低温度到1.5
- 训练步数预估：9463/128≈74步/epoch × 3 epochs = 222步总计

### 4.2 结果验证

| 对比项 | 判断标准 |
|--------|---------|
| KD vs 基线 | Overall Acc > 25% = 蒸馏有效 |
| KD vs SFT | Overall Acc > 23.16% = KD优于SFT |
| 按类型分析 | Topological类型提升最大（教师领先31.66pp） |

### 4.3 评测指标（与exp0一致）

- Overall Accuracy（按spatial_type分层的准确率）
- Format Valid Rate
- BLEU-4
- ROUGE-L
- Spatial F1
- 按空间类型分层分析
- 按难度分层分析

## 5. 风险与应对

| 风险 | 概率 | 应对策略 |
|------|------|---------|
| A10显存不足 | 中 | batch_size降到1, gradient_accumulation升到128 |
| 教师推理太慢 | 中 | 减少eval频率，eval_strategy改为epoch |
| KD效果不明显 | 低 | 检查教师和学生logits分布差异，调高α或T |
| 评测格式不兼容 | 低 | 严格复用exp0的generate和evaluate模块 |
| lr=1e-4训练不稳定 | 低 | 降为5e-5，与SFT一致 |

## 6. 预期结果

| 指标 | 基线 | SFT | KD预期 |
|------|------|-----|--------|
| Overall Acc | 23.16% | 22.06% | 25-29% |
| Topological | 24.85% | 21.01% | 30-38% |
| Directional | 43.49% | 41.44% | 45-50% |
| Metric | 17.59% | 15.64% | 18-22% |
| Composite | 3.66% | 8.54% | 5-10% |

关键假设：KD在topological类型上提升最大，因为教师-学生差距最大(31.66pp)。

## 7. 参数审查变更日志

| 日期 | 审查内容 | 发现问题 | 处理 |
|------|---------|---------|------|
| 2026-03-29 | 三方参数对比(V5.2方案/SFT实际/exp02代码) | 7处参数不一致 | 全部修正并记录于§2.3 |
| - | data路径 | 指向geosr_chain/final/(不存在) | 改为data/splits/ |
| - | system_prompt | 有长prompt，SFT用空 | 改为空 |
| - | LoRA r/alpha | r=8/alpha=16，SFT用r=16/alpha=32 | 改为r=16/alpha=32 |
| - | effective_batch | 32，V5.2和SFT用128 | accum 16→64 |
| - | 混合精度 | fp16，SFT用bf16 | fp16→bf16 |
| - | save/eval_steps | 500(>1 epoch) | 500→200 |
| - | learning_rate | 1e-4 vs SFT的5e-5 | 保持1e-4(KD标准+大batch补偿) |

## 8. 参考文件路径

| 文件 | 路径 |
|------|------|
| 当前exp02代码 | `GeoKD-SR/exp/exp02_standard_kd/` |
| SFT训练配置 | `GeoKD-SR/exp/exp0/qwen-1.5B-sft/outputs/splits/seed_42/training_config.json` |
| SFT数据处理 | `GeoKD-SR/exp/exp0/qwen-1.5B-sft/src/data_processor.py` |
| V5.2实验方案 | `docs/1.4-GeoKD-SR-实验设计方案-V5.2.md` |
| 统一训练口径 | `docs/claudegen/00-统一前言与训练环境.md` |
| exp0 Stage1生成 | `GeoKD-SR/exp/exp0/exp0/stage1_generation/generate_answers.py` |
| exp0 Stage2评测 | `GeoKD-SR/exp/exp0/exp0/stage2_evaluation/evaluate.py` |
| exp0确定性指标 | `GeoKD-SR/exp/exp0/exp0/stage2_evaluation/metrics/deterministic.py` |
| exp0生成配置 | `GeoKD-SR/exp/exp0/exp0/stage1_generation/config/generation_config.yaml` |
| exp0评测配置 | `GeoKD-SR/exp/exp0/exp0/stage2_evaluation/config/eval_config.yaml` |
| 训练数据 | `GeoKD-SR/data/splits/{train,dev,test}.jsonl` |
| 本地模型 | `GeoKD-SR/models/{Qwen2.5-1.5B-Instruct,Qwen2.5-7B-Instruct}` |
