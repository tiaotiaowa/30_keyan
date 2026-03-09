# GeoKD-SR 提示词偏差检查清单

> **版本**: V1.0
> **创建时间**: 2026-03-08
> **审查目标**: 检测数据集中可能导致模型偏差的提示词设计问题

---

## 一、提示词偏差概述

### 1.1 什么是提示词偏差？

提示词偏差是指数据集中的问题表述方式可能：
1. **泄露任务类型** - 直接告诉模型这是哪类空间关系问题
2. **暗示答案格式** - 通过问题措辞暗示答案的形式
3. **导致捷径学习** - 模型学习提示词模式而非真正的空间推理

### 1.2 偏差风险评估

| 偏差类型 | 风险等级 | 影响 |
|---------|---------|------|
| 推理链元数据泄露 | 🔴 高 | 直接暴露任务类型 |
| 专业术语泄露 | 🟠 中高 | 泄露问题分类 |
| 答案格式暗示 | 🟡 中 | 影响答案生成模式 |
| 提示词模式单一 | 🟡 中 | 模型过拟合特定表述 |

---

## 二、检查项清单

### 2.1 推理链元数据泄露检查 (高风险)

**检查项描述**: 推理链中不应包含直接泄露任务类型的字段

**禁止字段**:
| 字段名 | 风险 | 示例 |
|--------|------|------|
| `relation_type` | 🔴 高 | `"relation_type": "metric"` |
| `spatial_relation` | 🔴 高 | `"spatial_relation": "topological"` |
| 具体action名称 | 🔴 高 | `"action": "calculate_distance"` |

**检查方法**:
```python
def check_reasoning_chain_leakage(record):
    """检查推理链元数据泄露"""
    issues = []
    chain = record.get("reasoning_chain", [])

    for step in chain:
        # 检查 relation_type 字段
        if "relation_type" in step:
            issues.append({
                "type": "relation_type_leakage",
                "step": step.get("step"),
                "field": "relation_type",
                "value": step["relation_type"]
            })

        # 检查过于具体的 action
        specific_actions = ["calculate_distance", "determine_topology",
                          "calculate_direction", "classify_relation"]
        if step.get("action") in specific_actions:
            issues.append({
                "type": "action_leakage",
                "step": step.get("step"),
                "field": "action",
                "value": step["action"]
            })

    return issues
```

**修复建议**:
```python
# 改进前 (存在泄露)
{"step": 4, "action": "calculate_distance"}

# 改进后 (通用描述)
{"step": 4, "action": "process_spatial"}
```

---

### 2.2 专业术语泄露检查 (中高风险)

**检查项描述**: 问题中不应使用专业术语泄露任务类型

**高风险术语**:
| 术语 | 替代表述 | 风险 |
|------|---------|------|
| 拓扑关系 | 空间关系 | 🟠 |
| 从拓扑角度 | 从空间位置 | 🟠 |
| 拓扑学 | - | 🟠 |
| 拓扑结构 | 空间结构 | 🟠 |

**检查方法**:
```python
TECHNICAL_TERMS = {
    "topological": ["拓扑关系", "从拓扑角度", "拓扑学", "拓扑结构"]
}

def check_technical_terms(question, spatial_type):
    """检查专业术语泄露"""
    issues = []

    if spatial_type == "topological":
        for term in TECHNICAL_TERMS["topological"]:
            if term in question:
                issues.append({
                    "type": "technical_term_leakage",
                    "term": term,
                    "suggestion": "使用'空间关系'替代"
                })

    return issues
```

**修复建议**:
```
# 改进前
"从拓扑关系角度来看，北京与河北之间存在怎样的关系？"

# 改进后
"从空间位置来看，北京与河北之间有什么关系？"
```

---

### 2.3 引导词分布检查 (中风险)

**检查项描述**: 引导词不应过度集中在某一类型

**引导词类型**:
| 类型 | 示例 | 目标占比 |
|------|------|----------|
| 请问式 | "请问XX距离是多少？" | ≤30% |
| 判断式 | "请判断XX是否位于YY内" | ≤25% |
| 计算式 | "请计算两地距离" | ≤25% |
| 描述式 | "请描述空间关系" | ≤20% |

**检查方法**:
```python
INTRODUCTORY_PATTERNS = {
    "polite_inquiry": r"^请问",
    "judgment_request": r"^请判断|^判断",
    "calculation_request": r"^请计算|^计算|^请估算",
    "description_request": r"^请描述|^描述|^请说明"
}

def check_introductory_distribution(records):
    """检查引导词分布"""
    counts = defaultdict(int)

    for record in records:
        question = record.get("question", "")
        for pattern_type, pattern in INTRODUCTORY_PATTERNS.items():
            if re.match(pattern, question):
                counts[pattern_type] += 1
                break

    total = len(records)
    distribution = {k: v/total for k, v in counts.items()}

    # 检查单一类型是否超过阈值
    issues = []
    for pattern_type, ratio in distribution.items():
        if ratio > 0.30:
            issues.append({
                "type": "dominant_pattern",
                "pattern": pattern_type,
                "ratio": ratio,
                "threshold": 0.30
            })

    return issues, distribution
```

---

### 2.4 答案格式暗示检查 (中风险)

**检查项描述**: 问题措辞不应过度暗示答案格式

**暗示类型**:
| 暗示词 | 暗示的答案格式 | 示例 |
|--------|---------------|------|
| "是否" | 是/否 | "XX是否位于YY内？" |
| "多少公里" | 数值+单位 | "距离约多少公里？" |
| "什么方向" | 方向词 | "在什么方向？" |

**检查方法**:
```python
FORMAT_HINTS = {
    "binary_hint": ["是否", "有没有", "存不存在", "是否位于"],
    "numeric_hint": ["多少公里", "距离是", "约为多少", "多远"],
    "direction_hint": ["什么方向", "哪个方位", "位于什么方向"]
}

def check_format_hints(question, spatial_type):
    """检查答案格式暗示"""
    hints_found = []

    for hint_type, hints in FORMAT_HINTS.items():
        for hint in hints:
            if hint in question:
                hints_found.append({
                    "type": hint_type,
                    "hint": hint
                })

    return hints_found
```

---

### 2.5 信息给予模式检查 (低风险)

**检查项描述**: 检查问题中给予的信息模式是否合理

**信息模式**:
| 模式 | 示例 | 目标占比 |
|------|------|----------|
| 已知坐标 | "已知XX的坐标为..." | ≤40% |
| 背景描述 | "XX位于中国南部..." | ≤30% |
| 直接提问 | "XX和YY相距多远？" | ≥30% |

**检查方法**:
```python
INFO_PATTERNS = {
    "coordinate_given": r"已知.{0,10}坐标|位于北纬|经纬度是|地理位置为",
    "background_given": r"位于中国|位于.*省|地处",
    "direct_question": r"^[^，。]{0,20}(距离|方向|关系)"
}

def check_info_patterns(records):
    """检查信息给予模式"""
    counts = defaultdict(int)

    for record in records:
        question = record.get("question", "")
        for pattern_type, pattern in INFO_PATTERNS.items():
            if re.search(pattern, question):
                counts[pattern_type] += 1

    total = len(records)
    return {k: v/total for k, v in counts.items()}
```

---

## 三、按空间关系类型的特殊检查

### 3.1 Metric (度量关系)

**风险等级**: 🟢 低

**典型提示词**: "距离"、"公里"、"多远"

**检查要点**:
- ✅ "距离"是自然语言，无泄露风险
- ⚠️ 避免过度使用"请计算"引导

**合格示例**:
```
"桂林和益阳相距多远？"
"请问两地之间的直线距离是多少？"
```

### 3.2 Directional (方向关系)

**风险等级**: 🟢 低

**典型提示词**: "方向"、"方位"、"位于...的"

**检查要点**:
- ✅ "方向"是日常用语
- ⚠️ 避免过度使用"请判断方位"

**合格示例**:
```
"北京在上海的什么方向？"
"请问成都位于武汉的哪个方位？"
```

### 3.3 Composite (复合关系)

**风险等级**: 🟡 中

**典型提示词**: "方向和距离"、"综合判断"

**检查要点**:
- ⚠️ "方向和距离"组合较特殊，可能暗示类型
- ⚠️ "综合判断"暗示需要多步推理

**改进建议**:
```
# 改进前
"请综合判断XX相对于YY的空间位置关系（包括方向和大致距离）"

# 改进后
"XX相对于YY的位置如何？请描述方向和大概距离。"
```

### 3.4 Topological (拓扑关系)

**风险等级**: 🟠 中高

**典型提示词**: "是否位于"、"包含"、"相邻"

**检查要点**:
- 🔴 避免使用"拓扑关系"专业术语
- 🟠 "是否位于"暗示二元答案
- ⚠️ 保持术语的自然性

**改进建议**:
```
# 改进前
"从拓扑关系角度来看，北京与河北之间存在怎样的关系？"

# 改进后
"北京和河北在空间上有什么关系？北京是否在河北省内？"
```

---

## 四、审查报告模板

### 4.1 提示词偏差检查报告

```markdown
# 提示词偏差检查报告

## 检查摘要
- 数据集: {dataset_name}
- 记录数: {total_records}
- 检查时间: {timestamp}

## 偏差风险统计

| 风险等级 | 问题数 | 占比 |
|---------|--------|------|
| 🔴 高风险 | {high_count} | {high_ratio}% |
| 🟠 中高风险 | {medium_high_count} | {medium_high_ratio}% |
| 🟡 中风险 | {medium_count} | {medium_ratio}% |
| 🟢 低风险 | {low_count} | {low_ratio}% |

## 详细发现

### 1. 推理链元数据泄露
- 泄露记录数: {leakage_count}
- 主要泄露字段: {leakage_fields}

### 2. 专业术语泄露
- topological类型专业术语: {tech_term_count}

### 3. 引导词分布
| 引导词类型 | 占比 | 状态 |
|-----------|------|------|
| 请问式 | {polite_ratio}% | {polite_status} |
| 判断式 | {judgment_ratio}% | {judgment_status} |
| 计算式 | {calc_ratio}% | {calc_status} |
| 描述式 | {desc_ratio}% | {desc_status} |

## 改进建议
1. {suggestion_1}
2. {suggestion_2}
...
```

---

## 五、修复脚本使用

### 5.1 运行提示词偏差检查

```bash
# 完整检查
python scripts/validate_dataset_v2.py \
    --input data/geosr_chain/balanced_topology.jsonl \
    --output reports/prompt_bias \
    --levels 5 \
    --check-prompt-bias

# 仅检查推理链泄露
python scripts/validate_dataset_v2.py \
    --input data/geosr_chain/balanced_topology.jsonl \
    --check-reasoning-chain-leakage
```

### 5.2 清洗推理链

```bash
python scripts/sanitize_reasoning_chain.py \
    --input data/geosr_chain/balanced_topology.jsonl \
    --output data/geosr_chain/balanced_topology_sanitized.jsonl \
    --remove-relation-type \
    --generalize-actions
```

### 5.3 重写topological提示词

```bash
python scripts/rewrite_topological_prompts.py \
    --input data/geosr_chain/balanced_topology_sanitized.jsonl \
    --output data/geosr_chain/balanced_topology_v2.jsonl \
    --replace-technical-terms
```

---

## 六、参考资料

- [GeoKD-SR 数据生成规范](../GeoKD-SR-实验执行手册-V6.0/01-阶段1-数据准备/1.1-数据生成规范.md)
- [提示词偏差分析报告](../../GeoKD-SR/outputs/prompt_bias_report.md)

---

*最后更新: 2026-03-08*
