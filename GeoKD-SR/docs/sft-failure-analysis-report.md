# SFT训练失败原因深度分析报告

**报告日期**: 2026-03-25
**分析团队**: SFT-Failure-Investigation Agent Team
**实验**: exp0/qwen-1.5B-sft

---

## 执行摘要

Qwen2.5-1.5B-Instruct 在 GeoKD-SR 数据集上的 SFT 微调出现**严重的性能下降**：
- **微调前准确率**: 23.16%
- **微调后准确率**: 5.16%
- **下降幅度**: **77.7%**

经过多维度深度调查，确定**根本原因是训练与推理阶段的System Prompt不一致**，导致模型无法正确响应。

---

## 1. 核心发现：System Prompt不一致

### 1.1 三个不同的System Prompt

| 阶段 | 文件位置 | System Prompt内容 |
|------|---------|------------------|
| **训练** | `data_processor.py:49` | "你是一个专业的地理空间推理助手，擅长回答关于地理位置、方向、距离和**拓扑关系**的问题。" |
| **推理** | `evaluate.py:149` | "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和**空间关系**的问题。请**简洁准确地回答问题**。" |
| **配置** | `train_linux_24gb.yaml:38` | 与推理时相同 |

### 1.2 关键差异

1. **关键词不同**: "拓扑关系" vs "空间关系"
2. **指令不同**: 训练时无指令，推理时有"请简洁准确地回答问题"
3. **角色定位**: "助手" vs "专家"

### 1.3 影响分析

```
训练时格式 (58 tokens):
<|im_start|>system
你是一个专业的地理空间推理助手，擅长回答关于地理位置、方向、距离和拓扑关系的问题。<|im_end|>
<|im_start|>user
渭南市属于陕西省的行政管辖范围之内吗？<|im_end|>
<|im_start|>assistant
是的，渭南市属于陕西省。<|im_end|>

推理时格式 (不同内容):
<|im_start|>system
你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。请简洁准确地回答问题。<|im_end|>
```

**后果**: 模型在训练时学习了特定的system prompt模式，但推理时看到的是不同的prompt，导致模型困惑和输出异常。

---

## 2. 预测结果异常分析

### 2.1 异常类型统计

| 异常类型 | 示例 | 出现频率 | 根因 |
|---------|------|---------|------|
| **空输出** | `""` | ~15% | 模型生成提前终止 |
| **截断输出** | "郑", "舟山", "迁" | ~10% | 只输出1-2个字符 |
| **System泄漏** | "福建省地理学家，请从福建回答..." | ~30% | 模型学习了prompt模式 |
| **格式混乱** | "约\n1800公里航向回答..." | ~25% | 格式学习失败 |
| **正常输出** | "东南方向" | ~20% | 正确回答 |

### 2.2 典型失败案例

```json
// 案例1: System Prompt泄漏
{"question": "鼓浪屿郑成功纪念馆位于福建省的什么方位？",
 "prediction": "郑\n\n福建省地理学家，请从福建回答此类空间关系和距离及空间关联等的空间性",
 "reference": "东南方向"}

// 案例2: 空输出
{"question": "昆明和海口分别是云南省和海南省的省会城市...",
 "prediction": "",
 "reference": "约1200公里"}

// 案例3: 格式混乱
{"question": "从宜宾到哈尔滨的直线距离大约是多少？...",
 "prediction": "约\n1800公里航向回答关于空间和方向和空间范围和空间的空间。",
 "reference": "东北方向，距离约2692公里。"}
```

---

## 3. 训练过程分析

### 3.1 训练曲线解读

| Epoch | Train Loss | Eval Loss | Token Accuracy | 说明 |
|-------|-----------|-----------|----------------|------|
| 0.13 | 3.22 | - | 43.6% | 训练开始 |
| 1.0 | - | 0.938 | 78.9% | 第一轮结束 |
| 2.0 | - | 0.839 | 80.4% | 第二轮结束 |
| 3.0 | 0.80 | 0.825 | 81.3% | 最终 |

### 3.2 关键发现

1. **训练Loss正常下降**: 3.22 → 0.80 (下降75%)
2. **Eval Loss也下降**: 0.938 → 0.825
3. **Token Accuracy上升**: 43.6% → 81.3%

**结论**: 从训练指标看，模型**成功学习了训练数据的模式**，但由于训练-推理格式不一致，导致学习的内容无法在实际推理中正确应用。

### 3.3 过拟合分析

- 训练数据量: 592条 (train.jsonl)
- 模型参数量: 1.5B
- LoRA可训练参数: ~1.6M (0.1%)
- **过拟合风险**: 中等

---

## 4. 超参数评估

### 4.1 当前配置

| 参数 | 当前值 | 推荐值 | 评估 |
|------|-------|-------|------|
| learning_rate | 5e-5 | 1e-5 ~ 2e-5 | ⚠️ 偏高 |
| num_epochs | 3 | 1~2 | ⚠️ 可能过多 |
| batch_size | 8 | 8~16 | ✅ 合理 |
| gradient_accumulation | 16 | 8~16 | ✅ 合理 |
| LoRA r | 16 | 16~32 | ✅ 合理 |
| LoRA alpha | 32 | 32~64 | ✅ 合理 |
| warmup_ratio | 0.1 | 0.05~0.1 | ✅ 合理 |

### 4.2 问题评估

- **学习率5e-5偏高**: 对于1.5B模型的SFT，通常使用1e-5到2e-5
- **3个epochs可能过多**: 小数据集上容易过拟合

---

## 5. 数据处理流程分析

### 5.1 Labels构造逻辑

```python
# data_processor.py:164-220
def _construct_labels(self, input_ids, messages):
    # 初始化全部为-100
    labels = [-100] * len(input_ids)

    # 定位 assistant 段
    assistant_starts = self._find_pattern_positions(
        input_ids_list,
        im_start + assistant_token  # <|im_start|>assistant
    )

    # 只将 assistant 段的 labels 设为对应的 token id
    for i in range(content_start, actual_end):
        labels[i] = input_ids[i]
```

### 5.2 潜在问题

1. **手动labels构造**: 可能与TRL SFTTrainer的自动处理冲突
2. **模式匹配可靠性**: 依赖特殊token定位，可能失败
3. **备选方案**: `_construct_labels_fallback` 使用末尾匹配，可能不准确

### 5.3 TRL期望的数据格式

```python
# TRL SFTTrainer 期望的格式
{"messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "问题"},
    {"role": "assistant", "content": "答案"}
]}
```

当前实现是正确的，但关键问题是**system content不一致**。

---

## 6. 根因总结

### 6.1 主要原因 (Critical)

| 问题 | 严重程度 | 影响范围 | 优先级 |
|------|---------|---------|-------|
| **System Prompt不一致** | 🔴 Critical | 所有推理 | P0 |
| 训练-推理格式差异 | 🔴 Critical | 所有推理 | P0 |

### 6.2 次要原因 (Important)

| 问题 | 严重程度 | 影响范围 | 优先级 |
|------|---------|---------|-------|
| 学习率偏高 | 🟡 Medium | 训练稳定性 | P1 |
| Epochs可能过多 | 🟡 Medium | 过拟合风险 | P1 |
| 模型输出截断 | 🟡 Medium | 生成质量 | P1 |

### 6.3 根因链

```
System Prompt不一致
    ↓
模型学习了特定prompt模式
    ↓
推理时看到不同prompt
    ↓
模型困惑，生成异常
    ↓
准确率从23%下降到5%
```

---

## 7. 修复方案

### 方案A: 统一移除System Prompt (推荐)

**原理**: 训练和推理都不使用自定义system prompt，让Qwen使用默认模板

**修改**:

1. `data_processor.py`:
```python
# 修改第49行
DEFAULT_SYSTEM_PROMPT = None  # 或 ""

# 修改第91行
messages = [
    # {"role": "system", "content": self.system_prompt},  # 移除
    {"role": "user", "content": question},
    {"role": "assistant", "content": answer}
]
```

2. `evaluate.py`:
```python
# 修改第175-178行
messages = [
    # {"role": "system", "content": system_prompt},  # 移除
    {"role": "user", "content": question}
]
```

3. `train_linux_24gb.yaml`:
```yaml
data:
  system_prompt: ""  # 空字符串
```

**优点**:
- 彻底解决不一致问题
- 利用Qwen的预训练知识
- 简单可靠

### 方案B: 统一使用相同System Prompt

**原理**: 确保训练和推理使用完全相同的system prompt

**修改**:

1. 创建统一的prompt常量文件 `src/prompts.py`:
```python
GEO_SYSTEM_PROMPT = "你是一个地理空间推理助手，请简洁准确地回答问题。"
```

2. 在所有地方引用这个常量

**优点**:
- 保持自定义prompt的控制
- 一致性有保证

**缺点**:
- 需要确保所有引用都正确
- 如果忘记某处仍会出问题

### 方案C: 调整超参数重新训练

**原理**: 降低学习率和epochs，减少过拟合

**修改**:

```yaml
training:
  learning_rate: 1.0e-5  # 降低5倍
  num_epochs: 1          # 减少到1个epoch
  warmup_ratio: 0.05

model:
  lora:
    r: 32  # 增大rank
    target_modules: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
```

**注意**: 此方案应与方案A或B配合使用

---

## 8. 验证计划

### Phase 1: 格式一致性验证

```python
# test_format_consistency.py
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(model_path)

# 训练格式 (无system)
train_msg = [{"role": "user", "content": "问题"}, {"role": "assistant", "content": "答案"}]
train_text = tokenizer.apply_chat_template(train_msg, tokenize=False)

# 推理格式 (无system)
infer_msg = [{"role": "user", "content": "问题"}]
infer_text = tokenizer.apply_chat_template(infer_msg, tokenize=False, add_generation_prompt=True)

# 验证：推理格式的prompt部分应该与训练格式完全一致
assert infer_text.startswith(train_text.split("<|im_start|>assistant")[0])
print("格式一致性验证通过!")
```

### Phase 2: 小规模训练验证

1. 使用100条样本
2. 训练1个epoch
3. 检查预测输出是否正常

### Phase 3: 完整评测

验证指标:
- 准确率应该 >= 23%（不低于原始模型）
- 无空输出或截断输出
- 格式正常

---

## 9. 关键文件清单

| 文件 | 路径 | 需要修改 |
|------|------|---------|
| 数据处理 | `exp/exp0/qwen-1.5B-sft/src/data_processor.py` | ✅ System Prompt |
| 评估脚本 | `exp/exp0/qwen-1.5B-sft/scripts/evaluate.py` | ✅ System Prompt |
| 训练配置 | `exp/exp0/qwen-1.5B-sft/configs/train_linux_24gb.yaml` | ✅ 超参数 |
| 训练器 | `exp/exp0/qwen-1.5B-sft/src/trainer.py` | ⚠️ 检查 |

---

## 10. 预期修复效果

修复后预期:
- ✅ 准确率恢复到基线水平 (23%+)
- ✅ 预测输出完整、格式正确
- ✅ 无system prompt泄漏
- ✅ 训练和推理格式完全一致

---

## 附录: 调查团队分工

| Agent | 负责领域 | 状态 |
|-------|---------|------|
| data-quality-analyst | 数据内容和质量分析 | ✅ 完成 |
| format-consistency-analyst | 输入输出格式一致性 | ✅ 完成 |
| prompt-template-analyst | System Prompt和模板分析 | ✅ 完成 |
| hyperparameter-analyst | 训练算法和超参数分析 | ✅ 完成 |
| e2e-flow-analyst | 端到端流程追踪 | ✅ 完成 |

---

*报告生成时间: 2026-03-25*
*分析工具: Agent Team Investigation*
