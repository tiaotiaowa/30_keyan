# GeoKD-SR: 地理空间关系知识蒸馏框架

> **Geographic Spatial Relation Knowledge Distillation Framework**
>
> 基于知识蒸馏的地理空间关系推理能力迁移框架

---

## 目录

- [项目概述](#项目概述)
- [目录结构](#目录结构)
- [环境配置](#环境配置)
- [数据格式规范](#数据格式规范)
- [核心模块](#核心模块)
- [快速开始](#快速开始)
- [实验设计](#实验设计)
- [命令行工具](#命令行工具)
- [验证机制](#验证机制)
- [常见问题](#常见问题)

---

## 项目概述

GeoKD-SR是一个用于地理空间关系推理的知识蒸馏框架，旨在将大模型（教师模型）的地理空间推理能力迁移到小模型（学生模型）。

### 核心功能

1. **数据生成Pipeline**: 使用GLM-5 API生成高质量地理空间推理数据
2. **6层验证机制**: 确保数据质量符合实验需求
3. **6个知识蒸馏组件**: C1-C6分别针对不同蒸馏策略
4. **实验兼容性检查**: 自动验证数据适配Exp1-Exp9

### 支持的空间关系类型

| 类型 | 说明 | 示例问题 |
|------|------|---------|
| Directional | 方向关系 | "北京在上海的什么方向？" |
| Topological | 拓扑关系 | "上海包含哪些区？" |
| Metric | 度量关系 | "北京到上海有多远？" |
| Composite | 复合关系 | "北京在上海的西北方向，距离约1000公里" |

---

## 目录结构

```
GeoKD-SR/
├── data/                           # 数据目录
│   ├── entity_database.json        # 实体数据库 (243个实体)
│   ├── geosr_chain/                # 训练数据
│   │   ├── train.jsonl             # 训练集 (目标8,000条)
│   │   ├── dev.jsonl               # 验证集 (目标800条)
│   │   └── test.jsonl              # 测试集 (目标3,000条)
│   └── geosr_bench/                # 基准测试
│       └── benchmark.json          # 测试基准
│
├── scripts/                        # 脚本目录
│   ├── run_pipeline.py             # [主入口] 统一Pipeline
│   ├── generate_data_glm5.py       # GLM-5数据生成
│   ├── validate_data.py            # 6层数据验证
│   ├── split_dataset.py            # 数据集划分
│   ├── generate_entity_mapping.py  # 实体Token映射
│   ├── generate_reasoning_chain.py # 推理链生成
│   ├── check_experiment_compatibility.py  # 实验兼容性检查
│   └── test_pipeline_offline.py    # 离线测试脚本
│
├── models/                         # 模型模块
│   ├── losses/                     # 损失函数
│   │   ├── spatial_relation_loss.py    # C1: 空间关系蒸馏
│   │   ├── spatial_cot_loss.py         # C2: 思维链蒸馏
│   │   ├── spatial_reverse_kl.py       # C3: 逆向KL蒸馏
│   │   ├── self_distillation_loss.py   # C4: 自蒸馏
│   │   ├── spatial_attention_distill.py # C5: 注意力蒸馏
│   │   └── progressive_distill.py      # C6: 渐进式蒸馏
│   ├── data/                       # 数据处理
│   │   ├── progressive_scheduler.py    # 渐进式数据调度
│   │   └── data_loader.py              # 数据加载器
│   └── utils/                      # 工具类
│       └── entity_token_mapper.py      # 实体Token映射器
│
├── experiments/                    # 实验模块
│   ├── evaluate_glm5.py            # GLM-5评测脚本
│   ├── statistical_analysis.py     # 统计分析 (Holm-Bonferroni)
│   └── metrics/                    # 评测指标
│       └── geo_metrics.py          # 地理特异性指标
│
└── docs/                           # 文档目录
    └── GeoKD-SR-实验设计方案-V5.2.md  # 实验设计方案
```

---

## 环境配置

### 1. 基础环境

```bash
# Python版本
Python >= 3.10

# 核心依赖
pip install torch transformers datasets peft accelerate
pip install requests numpy pandas scipy
```

### 2. 设置API密钥

```bash
# Windows
set ZHIPUAI_API_KEY=your_api_key

# Linux/Mac
export ZHIPUAI_API_KEY=your_api_key
```

### 3. 验证环境

```bash
cd GeoKD-SR
python verify_env.py
```

---

## 数据格式规范

### 完整数据格式

```json
{
  "id": "geosr_001",
  "spatial_relation_type": "directional",
  "question": "北京在上海的什么方向？",
  "answer": "北京位于上海的西北方向。",
  "reasoning_chain": [
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "识别问题中的地理实体：北京、上海",
      "entities_involved": ["北京", "上海"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "判断空间关系类型：方向关系",
      "relation_type": "directional"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "获取实体坐标信息",
      "coordinates": {"北京": [116.4, 39.9], "上海": [121.5, 31.2]}
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "计算方向关系：西北",
      "calculation_result": "西北"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "生成最终答案",
      "final_answer": "西北方向"
    }
  ],
  "entities": [
    {"name": "北京", "type": "city", "coords": [116.4, 39.9]},
    {"name": "上海", "type": "city", "coords": [121.5, 31.2]}
  ],
  "spatial_tokens": ["北京", "上海", "西北", "方向"],
  "entity_to_token": {
    "北京": {"char_start": 0, "char_end": 2, "token_indices": [1, 2]},
    "上海": {"char_start": 3, "char_end": 5, "token_indices": [4, 5]}
  },
  "difficulty": "easy",
  "difficulty_score": 1.5
}
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 唯一标识符，格式: `geosr_{序号}` |
| `spatial_relation_type` | enum | 是 | directional/topological/metric/composite |
| `question` | string | 是 | 问题文本 (10-100字符) |
| `answer` | string | 是 | 答案文本 (2-50字符) |
| `reasoning_chain` | array | 是 | 5步结构化推理链 |
| `entities` | array | 是 | 实体列表，包含name/type/coords |
| `spatial_tokens` | array | 是 | 空间关键词 (4-8个) |
| `entity_to_token` | object | 是* | 实体到Token映射 (Exp7必需) |
| `difficulty` | enum | 是 | easy/medium/hard |
| `difficulty_score` | float | 是 | 难度评分 (1.0-5.0) |

### 难度评分系统

```
Difficulty_Score = 0.4 × 认知负荷 + 0.3 × 计算步骤 + 0.3 × 数据需求

等级划分:
- Easy: 1.0-2.0
- Medium: 2.1-3.5
- Hard: 3.6-5.0
```

---

## 核心模块

### 1. 数据生成Pipeline (`scripts/run_pipeline.py`)

统一入口，整合所有数据生成模块：

```bash
# 测试模式：生成100条数据验证流程
python scripts/run_pipeline.py --test_run

# 完整生成：生成11,800条数据
python scripts/run_pipeline.py --full_generation

# 自定义数量
python scripts/run_pipeline.py --full_generation \
    --train_count 1000 \
    --dev_count 100 \
    --test_count 300
```

### 2. 6层验证机制 (`scripts/validate_data.py`)

| Level | 名称 | 验证内容 | 通过标准 |
|-------|------|---------|---------|
| L1 | 格式验证 | 必需字段存在性、类型正确性 | 100% |
| L2 | 语义验证 | 枚举值有效性、列表非空 | 100% |
| L3 | 空间关系验证 | 关键词检测匹配relation_type | ≥95% |
| L4 | 坐标验证 | 中国境内坐标范围 | 100% |
| L5 | 推理链验证 | 5步结构完整性 | ≥90% |
| L6 | 去重验证 | 余弦相似度 < 0.9 | 100% |

```bash
# 验证数据
python scripts/validate_data.py --input data/geosr_chain/train.jsonl --verbose

# 保存验证报告
python scripts/validate_data.py --input data/geosr_chain/train.jsonl \
    --output validation_report.json \
    --text_report validation_report.txt
```

### 3. 实验兼容性检查 (`scripts/check_experiment_compatibility.py`)

验证数据是否适配所有实验(Exp1-Exp9)：

```bash
python scripts/check_experiment_compatibility.py --data data/geosr_chain/
```

### 4. 损失函数模块 (`models/losses/`)

| 组件 | 文件 | 功能 |
|------|------|------|
| C1 | `spatial_relation_loss.py` | 空间关系加权Forward KL蒸馏 |
| C2 | `spatial_cot_loss.py` | 1/n归一化思维链蒸馏 |
| C3 | `spatial_reverse_kl.py` | 逆向KL蒸馏 |
| C4 | `self_distillation_loss.py` | 自蒸馏(EMA历史) |
| C5 | `spatial_attention_distill.py` | 空间注意力蒸馏 |
| C6 | `progressive_distill.py` | 3-epoch渐进式蒸馏 |

---

## 快速开始

### Step 1: 环境检查

```bash
# 检查API密钥
python -c "import os; print('API Key:', 'SET' if os.getenv('ZHIPUAI_API_KEY') else 'NOT SET')"

# 检查实体数据库
python -c "
import sys
sys.path = [p for p in sys.path if 'gisai' not in p.lower()]
from data.entity_database import EntityDatabase
db = EntityDatabase()
print(f'实体数量: {len(db.get_entities_with_coords())}')
"
```

### Step 2: 运行离线测试

```bash
# 验证Pipeline逻辑（无需API）
python scripts/test_pipeline_offline.py
```

### Step 3: 生成测试数据

```bash
# 生成100条测试数据
python scripts/run_pipeline.py --test_run
```

### Step 4: 验证数据质量

```bash
# 验证生成的数据
python scripts/validate_data.py --input data/geosr_chain/test_run.jsonl --verbose

# 检查实验兼容性
python scripts/check_experiment_compatibility.py --data data/geosr_chain/
```

### Step 5: 完整数据生成

```bash
# 生成完整数据集（约3-4小时）
python scripts/run_pipeline.py --full_generation
```

---

## 实验设计

### 实验列表

| 实验 | 方法 | 必需字段 |
|------|------|---------|
| Exp1 | B1: Direct-SFT | question, answer |
| Exp2 | B2: Standard-KD | question, answer |
| Exp3a | B2 + C1 (Uniform) | + spatial_relation_type |
| Exp3 | B2 + C1 (Learnable) | + spatial_relation_type |
| Exp4 | B2 + C2 | + reasoning_chain |
| Exp5 | B2 + C3 | question, answer |
| Exp6 | B2 + C4 | question, answer |
| Exp7 | B2 + C5 | + entities, spatial_tokens, entity_to_token |
| Exp8 | B2 + C6 | + spatial_relation_type, difficulty |
| Exp9 | GeoKD-SR (完整) | 所有字段 |

### 数据分布

**训练集 (8,000条)**:
| 空间关系类型 | Easy (30%) | Medium (50%) | Hard (20%) | 小计 |
|-------------|-----------|-------------|-----------|------|
| Directional | 720 | 1,200 | 480 | **2,400** |
| Topological | 540 | 900 | 360 | **1,800** |
| Metric | 540 | 900 | 360 | **1,800** |
| Composite | 600 | 1,000 | 400 | **2,000** |

**测试集 (3,000条)**:
- D1方向关系: 1,000题
- D2拓扑关系: 1,000题
- D3度量关系: 1,000题

---

## 命令行工具

### run_pipeline.py

```bash
python scripts/run_pipeline.py [OPTIONS]

选项:
  --test_run              测试模式：生成100条数据
  --full_generation       完整生成模式
  --train_count INT       训练集数量 (默认8000)
  --dev_count INT         验证集数量 (默认800)
  --test_count INT        测试集数量 (默认3000)
  --output_dir PATH       输出目录 (默认data/geosr_chain/)
  --quiet                 静默模式
```

### validate_data.py

```bash
python scripts/validate_data.py [OPTIONS]

选项:
  --input PATH            输入文件路径 (必需)
  --output PATH           JSON报告输出路径
  --text_report PATH      文本报告输出路径
  --verbose, -v           详细输出
  --threshold FLOAT       去重相似度阈值 (默认0.9)
  --no-duplicates         跳过去重验证
  --strict                严格模式
```

### split_dataset.py

```bash
python scripts/split_dataset.py [OPTIONS]

选项:
  --input PATH            输入文件路径 (必需)
  --output PATH           输出目录 (必需)
  --train INT             训练集大小 (默认8000)
  --dev INT               验证集大小 (默认800)
  --test INT              测试集大小 (默认3000)
  --seed INT              随机种子 (默认42)
```

### check_experiment_compatibility.py

```bash
python scripts/check_experiment_compatibility.py --data data/geosr_chain/
```

---

## 验证机制

### 坐标范围验证（中国境内）

```python
CHINA_LON_RANGE = (73.66, 135.05)  # 经度范围
CHINA_LAT_RANGE = (3.86, 53.55)    # 纬度范围
```

### 验证通过标准

| 验证项 | 通过标准 |
|--------|---------|
| L1 格式验证 | 100% |
| L2 语义验证 | 100% |
| L3 空间关系验证 | ≥95% |
| L4 坐标验证 | 100% |
| L5 推理链验证 | ≥90% |
| L6 去重验证 | 100% |
| 实验兼容性 | Exp1-Exp9 ≥95% |

---

## 常见问题

### Q1: API密钥未设置

```
[错误] 未设置ZHIPUAI_API_KEY环境变量
```

**解决方案**:
```bash
export ZHIPUAI_API_KEY=your_api_key
```

### Q2: 实体数据库加载失败

```
[错误] 无法加载实体数据库
```

**解决方案**: 检查 `data/entity_database.json` 文件是否存在

### Q3: 导入路径冲突

```
SyntaxError: '(' was never closed
```

**解决方案**: 代码已自动排除gisai路径，如仍有问题：
```python
sys.path = [p for p in sys.path if 'gisai' not in p.lower()]
```

### Q4: 数据验证通过率低

**解决方案**:
1. 检查GLM-5返回的JSON格式
2. 运行 `--verbose` 查看详细错误
3. 使用 `--test_run` 先验证流程

---

## 当前状态

| 项目 | 状态 | 数量 |
|------|------|------|
| 实体数据库 | ✅ 完成 | 243个实体 |
| 训练数据 | ⚠️ 需重新生成 | 3条 (目标8,000) |
| 验证数据 | ❌ 缺失 | 0条 (目标800) |
| 测试数据 | ❌ 缺失 | 0条 (目标3,000) |
| Pipeline模块 | ✅ 完成 | 7个模块 |
| 损失函数 | ✅ 完成 | 6个组件 |
| 验证机制 | ✅ 完成 | 6层验证 |

---

## 更新日志

### 2026-03-04
- 创建统一Pipeline入口 `run_pipeline.py`
- 完成离线测试验证 (8/8通过)
- 增强数据后处理功能
- 更新项目文档

### 2026-03-03
- 实现6个损失函数模块
- 创建统计分析模块
- 完成地理评测指标

---

## 联系方式

- 项目路径: `D:\30_keyan\GeoKD-SR`
- 文档路径: `docs/GeoKD-SR-实验设计方案-V5.2.md`

---

*最后更新: 2026-03-04*
