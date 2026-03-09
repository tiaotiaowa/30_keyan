# GeoKD-SR 数据审查流程说明

> **版本**: V2.2
> **更新时间**: 2026-03-08
> **适用数据集**: balanced_topology.jsonl (6,522条)

---

## 一、五级审查体系概述

GeoKD-SR 数据集采用五级审查体系，从基础格式到提示词偏差进行全面质量把控：

| 级别 | 名称 | 审查重点 | 检查项数量 |
|------|------|----------|------------|
| **L1** | 格式审查 | JSON格式有效性、必需字段完整性 | 4项 |
| **L2** | 逻辑审查 | 字段类型、取值范围、推理链结构 | 8项 |
| **L3** | 分布审查 | 空间关系、难度、拓扑子类型分布 | 8项 |
| **L4** | 语义审查 | 答案一致性、关键词覆盖、实体分布 | 10项 |
| **L5** | 提示词偏差审查 | 推理链泄露、术语泄露、引导词分布 | 5项 ⭐新增 |

### 审查优先级

| 优先级 | 标记 | 说明 | 处理要求 |
|--------|------|------|----------|
| **高** | 🔴 Critical | 阻塞性问题，必须修复 | 修复后才能使用 |
| **中** | 🟡 Important | 重要质量问题，建议修复 | 影响实验效果 |
| **低** | 🟢 Info | 参考信息，可选修复 | 不影响基本使用 |

---

## 二、审查流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                      数据审查流程                                │
└─────────────────────────────────────────────────────────────────┘

  输入: balanced_topology.jsonl (6,522条)
           │
           ▼
    ┌──────────────┐
    │   L1 格式审查  │  ←── 4项检查
    │  JSON+字段   │
    └──────┬───────┘
           │ 通过
           ▼
    ┌──────────────┐
    │   L2 逻辑审查  │  ←── 8项检查
    │  类型+推理链  │
    └──────┬───────┘
           │ 通过
           ▼
    ┌──────────────┐
    │   L3 分布审查  │  ←── 8项检查
    │  关系+难度   │
    └──────┬───────┘
           │ 通过
           ▼
    ┌──────────────┐
    │   L4 语义审查  │  ←── 10项检查
    │ 答案+关键词  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  生成审查报告  │
    │  问题清单+修复  │
    └──────────────┘
```

---

## 三、使用方法

### 3.1 快速验证

```bash
# 使用验证脚本进行完整审查
cd D:\30_keyan\GeoKD-SR\scripts
python validate_dataset_v2.py \
    --input ../data/geosr_chain/balanced_topology.jsonl \
    --output ../outputs/review_$(date +%Y%m%d)
```

### 3.2 自定义配置

```bash
# 使用自定义配置文件
python validate_dataset_v2.py \
    --input ../data/geosr_chain/balanced_topology.jsonl \
    --config ../docs/data_review/validation_config.yaml \
    --output ../outputs/review_custom
```

### 3.3 提示词偏差检查 ⭐新增

```bash
# 专门检查提示词偏差
python validate_dataset_v2.py \
    --input ../data/geosr_chain/balanced_topology.jsonl \
    --output ../outputs/prompt_bias \
    --levels 5

# 仅检查推理链泄露
python validate_dataset_v2.py \
    --input ../data/geosr_chain/balanced_topology.jsonl \
    --check-reasoning-chain-leakage
```

### 3.4 专项检查

```bash
# 仅执行L1+L2快速检查
python validate_dataset_v2.py \
    --input ../data/geosr_chain/balanced_topology.jsonl \
    --level L2 \
    --output ../outputs/quick_check
```

---

## 四、快速开始指南

### 第一次使用

1. **准备环境**
   ```bash
   cd D:\30_keyan\GeoKD-SR
   pip install -r requirements.txt
   ```

2. **运行完整验证**
   ```bash
   python scripts/validate_dataset_v2.py \
       --input data/geosr_chain/balanced_topology.jsonl \
       --output outputs/review_latest
   ```

3. **查看报告**
   - 打开 `outputs/review_latest/report.md`
   - 检查问题清单和通过率

4. **修复问题**
   - 参考报告中的修复建议
   - 使用提供的修复脚本

### 常用命令

| 任务 | 命令 |
|------|------|
| 完整验证 | `python scripts/validate_dataset_v2.py -i data.jsonl -o outputs/` |
| 生成分布图表 | `python scripts/validate_dataset_v2.py -i data.jsonl --plot` |
| 导出问题CSV | `python scripts/validate_dataset_v2.py -i data.jsonl --export-csv` |
| 仅L1检查 | `python scripts/validate_dataset_v2.py -i data.jsonl --level L1` |
| 提示词偏差检查 | `python scripts/validate_dataset_v2.py -i data.jsonl --levels 5` ⭐ |
| 推理链泄露检查 | `python scripts/validate_dataset_v2.py -i data.jsonl --check-leakage` ⭐ |

---

## 五、审查报告说明

### 报告结构

```
outputs/review_YYYYMMDD/
├── report.md              # Markdown格式主报告
├── issues.json            # 问题详情JSON
├── stats.csv              # 统计数据CSV
├── distribution_charts/   # 分布图表
├── fix_suggestions.py     # 修复建议脚本
└── prompt_bias_report.md  # 提示词偏差专项报告 ⭐新增
```

### 报告阅读指南

1. **执行摘要** - 快速了解整体质量
2. **分层验证** - 各级别详细问题
3. **分布统计** - 数据分布可视化
4. **问题清单** - 按优先级排序的问题列表
5. **修复建议** - 具体修复方案
6. **提示词偏差** - L5专项检查结果 ⭐新增

---

## 六、常见问题

### Q1: 验证失败怎么办？

**A**: 按优先级处理：
1. 先修复所有 Critical 问题
2. 再处理 Important 问题
3. Info 问题可选择性处理

### Q2: 如何解读分布偏差？

**A**:
- 偏差 < 2%: 正常范围
- 偏差 2-5%: 轻微偏差，可接受
- 偏差 > 5%: 需要调整数据

### Q3: 实验兼容性说明

| 实验组 | 需要字段 | 当前兼容性 |
|--------|----------|------------|
| Exp1-6 | 基础字段 | ✅ 100% |
| Exp7 | + entity_to_token | ❌ 需补充 |
| Exp8 | + difficulty_score | ❌ 需补充 |
| Exp9 | 完整字段 | ❌ 需补充 |

### Q4: 如何补充缺失字段？

使用项目提供的修复脚本：
```bash
python scripts/fix_dataset_fields.py \
    --input data/geosr_chain/balanced_topology.jsonl \
    --fix entity_to_token,difficulty_score
```

### Q5: 什么是提示词偏差？⭐新增

**A**: 提示词偏差是指数据集中的问题表述方式可能：
1. **泄露任务类型** - 如"拓扑关系"术语直接暴露问题类型
2. **暗示答案格式** - "是否"暗示是/否答案
3. **导致捷径学习** - 模型学习提示词模式而非真正推理

详细检查项请参考 `prompt_bias_checklist.md`。

### Q6: 如何处理提示词偏差？⭐新增

**A**: 使用以下脚本：
```bash
# 清洗推理链泄露
python scripts/sanitize_reasoning_chain.py \
    --input data/geosr_chain/balanced_topology.jsonl \
    --output data/geosr_chain/sanitized.jsonl

# 重写topological提示词
python scripts/rewrite_topological_prompts.py \
    --input data/geosr_chain/sanitized.jsonl \
    --output data/geosr_chain/final.jsonl
```

---

## 七、文档索引

| 文档 | 说明 |
|------|------|
| `validation_checklist.md` | 35项审查维度详细说明 (含L5) |
| `current_findings.md` | 当前数据集审查发现 |
| `validation_config_template.yaml` | 配置文件模板 |
| `prompt_bias_checklist.md` | 提示词偏差检查清单 ⭐新增 |

---

## 八、联系方式

如有问题或建议，请提交 Issue 或联系项目维护者。

---

*最后更新: 2026-03-08*
