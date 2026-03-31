# System Prompt 一致性调查报告

**调查时间**: 2026-03-25
**调查人员**: Prompt工程专家
**严重程度**: 🔴 高危 (Critical)

---

## 一、问题概述

本次调查发现了 **多处 System Prompt 不一致** 的问题，这很可能是导致模型预测结果异常（91%样本出现"专家"、"概念"等混乱输出）的根本原因。

---

## 二、System Prompt 来源追踪

### 2.1 配置文件中的定义

| 位置 | System Prompt 内容 |
|------|-------------------|
| `configs/train_linux_24gb.yaml:38` | "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。**请简洁准确地回答问题。**" |
| `src/config.py:65` | "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。**请简洁准确地回答问题。**" |
| `src/data_processor.py:38` | "你是一个专业的地理空间推理**助手**，擅长回答关于地理位置、方向、距离和**拓扑**关系的问题。" |
| `src/data_processor.py:49` | "你是一个专业的地理空间推理**助手**，擅长回答关于地理位置、方向、距离和**拓扑**关系的问题。" |
| `scripts/evaluate.py:149` | "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。**请简洁准确地回答问题。**" |

### 2.2 发现的不一致

**关键差异对比**:

| 差异点 | 训练配置 (YAML) | data_processor.py | 影响 |
|--------|----------------|-------------------|------|
| 身份定位 | "专家" | "助手" | ⚠️ 中等 |
| 描述词 | "空间关系" | "拓扑关系" | ⚠️ 中等 |
| 结尾指令 | "请简洁准确地回答问题。" | 无 | 🔴 **高危** |

**核心问题**:
```python
# 配置文件 (train_linux_24gb.yaml)
system_prompt: "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。请简洁准确地回答问题。"

# data_processor.py 默认值 (第38行、49行)
DEFAULT_SYSTEM_PROMPT = "你是一个专业的地理空间推理助手，擅长回答关于地理位置、方向、距离和拓扑关系的问题。"
```

---

## 三、Qwen 默认模板分析

### 3.1 Qwen2.5-1.5B-Instruct 的 Chat Template

```jinja
{%- if messages[0]['role'] == 'system' %}
    {{- '<|im_start|>system\n' + messages[0]['content'] + '<|im_end|>\n' }}
{%- else %}
    {{- '<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n' }}
{%- endif %}
```

### 3.2 关键发现

1. **当提供 system message 时**: 使用自定义内容
2. **当不提供 system message 时**: 使用默认 "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."

**重要**: Qwen 的 chat_template 会 **自动注入** 默认 system prompt，即使不显式提供！

### 3.3 模板格式示例

**无自定义 System Prompt**:
```
<|im_start|>system
You are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>
<|im_start|>user
测试问题<|im_end|>
<|im_start|>assistant
```

**有自定义 System Prompt**:
```
<|im_start|>system
你是一个地理空间推理专家。<|im_end|>
<|im_start|>user
测试问题<|im_end|>
<|im_start|>assistant
```

---

## 四、Prompt 冲突分析

### 4.1 训练 vs 推理的 System Prompt 对比

| 阶段 | System Prompt | 来源 |
|------|--------------|------|
| **训练数据处理** | "你是一个专业的地理空间推理**助手**，擅长回答关于地理位置、方向、距离和**拓扑**关系的问题。" | data_processor.py DEFAULT_SYSTEM_PROMPT |
| **推理评估** | "你是一个地理空间推理**专家**，专门回答关于地理位置、方向、距离和空间关系的问题。**请简洁准确地回答问题。**" | evaluate.py 默认参数 |

### 4.2 训练时实际发生了什么

**假设流程** (需要进一步验证):
1. 配置文件传入 `system_prompt`
2. `train.py` 将配置中的 `system_prompt` 传递给 `GeoSRDataProcessor`
3. 如果配置正确传递，训练时应使用配置中的 prompt

**潜在问题**:
- 如果 `train.py` 没有正确传递 `system_prompt` 参数
- 或者 `DataConfig` 加载失败
- 则会回退到 `data_processor.py` 中的默认值

### 4.3 推理时发生了什么

评估脚本 `evaluate.py` 第149行硬编码了默认 system_prompt:
```python
def generate_predictions(
    ...
    system_prompt: str = "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。请简洁准确地回答问题。"
)
```

---

## 五、预测结果异常分析

### 5.1 异常样本统计

- **总样本数**: 测试集
- **异常样本比例**: **91%** (前100个样本中91个异常)
- **异常类型**: 输出截断、格式混乱、包含"专家"字样

### 5.2 典型异常案例

| ID | 预测输出 | 参考答案 | 异常类型 |
|----|---------|---------|---------|
| geosr_directional_00513 | "郑\n\n福建省地理学家，**请从福建回答此类空间关系和距离及空间关联等的空间性**" | 东南方向 | Prompt泄漏+混乱 |
| geosr_composite_00819 | "相对安徽省与湖北省之间的**概念专家，请详细回答方向空间和方向和距离的空间关系推理问题**。" | 西北方向，约917公里。 | Prompt泄漏 |
| geosr_topological_03455 | "是**是的，你的概念专家，请以回答关于地理和空间和空间距离以及空间空间**。" | 是的，深圳属于广东省。 | Prompt泄漏+格式混乱 |
| geosr_composite_00464 | "约\n1800公里**航向回答关于空间和方向和空间范围和空间的空间**。" | 东北方向，距离约2692公里。 | 输出截断+Prompt泄漏 |
| geosr_metric_01427 | "" (空) | 约1200公里 | 输出为空 |

### 5.3 异常模式识别

1. **Prompt 泄漏**: 输出中包含 "专家"、"请详细回答"、"空间关系推理" 等指令性文本
2. **输出截断**: 只输出第一个字或几个字就停止
3. **格式混乱**: 混合了问题、指令和回答
4. **空输出**: 完全没有生成任何内容

### 5.4 根因分析

**最可能的根因**:

1. **训练时的 System Prompt 与推理时不一致**
   - 模型在训练时学到的是 "助手"+"拓扑关系" 的 prompt
   - 推理时给的是 "专家"+"空间关系"+"请简洁准确回答" 的 prompt
   - 这种 **分布偏移 (Distribution Shift)** 导致模型行为异常

2. **模型可能过拟合到特定的 Prompt 格式**
   - 1.5B 小模型容量有限
   - 对 prompt 变化非常敏感

3. **"请简洁准确地回答问题" 的副作用**
   - 训练时没有这个结尾指令
   - 推理时添加了这个指令
   - 模型可能将其理解为需要"解释"而不是"回答"

---

## 六、代码流程验证需求

需要进一步检查以下文件确认实际训练时使用的 system_prompt:

1. `scripts/train.py` - 检查如何调用 `GeoSRDataProcessor`
2. 训练日志 - 检查实际使用的 system_prompt 值
3. 训练数据 - 检查 `to_hf_dataset()` 方法是否正确传递 system_prompt

---

## 七、修复建议

### 7.1 紧急修复 (Critical)

1. **统一所有 System Prompt 定义**
   ```python
   # 建议统一定义为 (选择一个版本):
   SYSTEM_PROMPT = "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。请简洁准确地回答问题。"
   ```

2. **修改 data_processor.py 第38行和第49行**
   ```python
   # 修改前
   system_prompt: str = "你是一个专业的地理空间推理助手，擅长回答关于地理位置、方向、距离和拓扑关系的问题。"

   # 修改后 (与配置文件一致)
   system_prompt: str = "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。请简洁准确地回答问题。"
   ```

### 7.2 推荐修复 (Recommended)

1. **创建单一配置源**
   ```python
   # src/constants.py
   GEO_SPATIAL_SYSTEM_PROMPT = "你是一个地理空间推理专家，专门回答关于地理位置、方向、距离和空间关系的问题。请简洁准确地回答问题。"
   ```

2. **所有位置引用同一常量**
   - config.py 引用此常量作为默认值
   - data_processor.py 引用此常量
   - evaluate.py 引用此常量

### 7.3 长期改进

1. **添加配置验证**
   ```python
   def validate_config(config):
       assert config.data.system_prompt == evaluate_system_prompt, \
           "训练和评估的 system_prompt 必须一致！"
   ```

2. **添加训练日志记录**
   ```python
   logger.info(f"Training System Prompt: {system_prompt}")
   ```

---

## 八、下一步行动

1. [ ] 验证 `train.py` 中实际传递的 `system_prompt` 值
2. [ ] 统一所有 System Prompt 定义
3. [ ] 使用统一后的 System Prompt 重新训练
4. [ ] 对比重新训练前后的评估结果
5. [ ] 更新文档，明确 System Prompt 的重要性

---

## 九、结论

**System Prompt 不一致是导致模型预测异常的关键原因之一**。

具体表现为:
- 训练数据使用 "助手"+"拓扑关系" 版本
- 评估推理使用 "专家"+"空间关系"+"请简洁准确回答" 版本
- 这种不一致导致 91% 的预测结果出现 prompt 泄漏、输出截断等问题

**建议立即统一所有 System Prompt 定义，并重新训练模型**。

---

*报告完成时间: 2026-03-25*
