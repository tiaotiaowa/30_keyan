# 阶段1 - 数据准备 Pipeline

> **版本**: V7.0
> **最后更新**: 2026-03-06
> **状态**: ✅ 已实现

---

## 一、Pipeline 概述

### 1.1 目标

生成高质量地理空间推理数据集，满足GeoKD-SR 10个实验（Exp1-Exp9 + GeoKD-SR完整版）的数据需求。

### 1.2 数据规模

| 数据集 | 数量 | 用途 |
|--------|------|------|
| 训练集 (train.jsonl) | 8,000条 | 模型训练 |
| 验证集 (dev.jsonl) | 800条 | 超参调优 |
| 测试集 (test.jsonl) | 3,000条 | 最终评估 |

### 1.3 核心模块

```
GeoKD-SR/scripts/
├── generate_data_glm5.py          # 主生成脚本 (V7.0增强版)
├── generate_reasoning_chain.py    # 5步推理链生成模块
├── generate_entity_mapping.py     # 实体Token映射模块
├── sample_topology_subtype()      # 拓扑子类型采样方法 (V7.0新增)
├── validate_data.py               # 6层数据验证模块
├── split_dataset.py               # 数据集划分模块
└── check_experiment_compatibility.py  # 实验兼容性检查
```

---

## 二、快速开始

### 2.1 环境准备

```bash
# 1. 确保Python环境
python --version  # >= 3.8

# 2. 安装依赖
cd D:/30_keyan/GeoKD-SR
pip install -r requirements.txt

# 3. 配置GLM-5 API密钥
# Windows
set ZHIPUAI_API_KEY=your_api_key_here
# Linux/Mac
export ZHIPUAI_API_KEY=your_api_key_here
```

### 2.2 一键生成完整数据集

```bash
# 生成训练集(8000) + 验证集(800) + 测试集(3000)
python scripts/generate_data_glm5.py \
    --train_count 8000 \
    --dev_count 800 \
    --test_count 3000 \
    --output data/geosr_chain/
```

### 2.3 验证数据质量

```bash
# 验证训练集
python scripts/validate_data.py \
    --input data/geosr_chain/train.jsonl \
    --verbose

# 检查实验兼容性
python scripts/check_experiment_compatibility.py \
    --data data/geosr_chain/
```

---

## 三、Pipeline 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    GeoKD-SR 数据生成Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│  阶段1: 实体准备                                                  │
│  └── EntityDatabase → 34省级行政区 + 309城市 + 61地标 + 30河流 + 38山脉 + 18湖泊 + 20区域    │
│                          ↓                                       │
│  阶段2: GLM-5 API生成                                            │
│  └── 生成question/answer + reasoning_chain(5步) + entities       │
│                          ↓                                       │
│  阶段3: 后处理与增强                                              │
│  └── EntityTokenMapper → 计算entity_to_token映射                 │
│  └── DifficultyCalculator → 计算difficulty_score                │
│                          ↓                                       │
│  阶段4: 质量控制                                                  │
│  └── DataValidator → 6层验证 (L1-L6)                            │
│                          ↓                                       │
│  阶段5: 数据划分与输出                                            │
│  └── train.jsonl (8,000) + dev.jsonl (800) + test.jsonl (3,000) │
└─────────────────────────────────────────────────────────────────┘
```

---

## 四、核心功能详解

### 4.1 5步结构化推理链

与 `spatial_cot_loss.py` 中的 `REASONING_STEPS` 完全对齐：

| Step | name | action | 说明 |
|------|------|--------|------|
| 1 | entity_identification | extract_entities | 识别问题中的地理实体 |
| 2 | spatial_relation_extraction | classify_relation | 判断空间关系类型 |
| 3 | coordinate_retrieval | infer_entity_to_token | 获取实体坐标 |
| 4 | spatial_calculation | calculate | 执行空间计算 |
| 5 | answer_generation | generate_answer | 生成最终答案 |

### 4.2 6层数据验证

| Level | 验证内容 | 通过标准 | 说明 |
|-------|---------|---------|------|
| L1 | 格式验证 | 100% | 必需字段存在性、类型正确性 |
| L2 | 语义验证 | 100% | 枚举值有效性、列表非空 |
| L3 | 空间关系验证 | ≥95% | 关键词检测匹配relation_type |
| L4 | 坐标验证 | 100% | 经度73.66-135.05°E，纬度3.86-53.55°N |
| L5 | 推理链验证 | ≥90% | 5步结构完整性、逻辑一致性 |
| L6 | 去重验证 | 100% | 余弦相似度 < 0.9 |

### 4.3 difficulty_score 计算

```python
Difficulty_Score = 0.4 × 认知负荷 + 0.3 × 计算步骤 + 0.3 × 数据需求

难度等级映射:
- Easy: 1.0-2.0
- Medium: 2.1-3.5
- Hard: 3.6-5.0
```

---

## 五、数据分布规范

### 5.1 训练集分布 (8,000条) - GIS平衡型

| 空间关系类型 | 占比 | Easy (30%) | Medium (50%) | Hard (20%) | 小计 |
|-------------|------|-----------|-------------|-----------|------|
| Directional | 25% | 600 | 1,000 | 400 | **2,000** |
| Topological | 27.5% | 660 | 1,100 | 440 | **2,200** |
| Metric | 27.5% | 660 | 1,100 | 440 | **2,200** |
| Composite | 20% | 480 | 800 | 320 | **1,600** |

### 5.2 测试集分布 (3,000条)

- D1方向关系: 1,000题
- D2拓扑关系: 1,000题
- D3度量关系: 1,000题

### 5.3 拓扑子类型分布 (新增)

| 子类型 | 占比 | 描述 | 示例 |
|--------|------|------|------|
| within | 20% | A在B内部 | 故宫在北京市内 |
| contains | 20% | B包含A | 北京市包含故宫 |
| adjacent | 20% | A与B相邻 | 河北省与山东省相邻 |
| disjoint | 20% | A与B分离 | 海南省与黑龙江省不接壤 |
| overlap | 20% | A与B交叉 | 长江流经多个省份 |

---

## 六、命令行参数详解

### 6.1 主生成脚本 (generate_data_glm5.py)

```bash
python scripts/generate_data_glm5.py [OPTIONS]

必需参数:
  --train_count INT      训练集数量 (默认: 8000)
  --dev_count INT        验证集数量 (默认: 800)
  --test_count INT       测试集数量 (默认: 3000)

输出参数:
  --output DIR           输出目录 (默认: data/geosr_chain/)
  --train_output STR     训练集文件名 (默认: train.jsonl)
  --dev_output STR       验证集文件名 (默认: dev.jsonl)
  --test_output STR      测试集文件名 (默认: test.jsonl)

生成控制:
  --test_only            仅生成测试集
  --dev_only             仅生成验证集
  --post_process         启用后处理 (默认: 开启)
  --no_post_process      禁用后处理

API配置:
  --api_key STR          智谱API密钥 (默认: 环境变量ZHIPUAI_API_KEY)

数据分布:
  --relation_distribution STR  关系类型分布 (默认: directional:0.25,topological:0.275,metric:0.275,composite:0.20)

测试模式:
  --test_mode            测试模式，生成少量示例数据
```

### 6.2 数据验证脚本 (validate_data.py)

```bash
python scripts/validate_data.py [OPTIONS]

参数:
  --input PATH           输入文件路径 (必需)
  --output PATH          JSON报告输出路径
  --text_report PATH     文本报告输出路径
  --verbose              详细输出
  --threshold FLOAT      去重相似度阈值 (默认: 0.9)
  --no_duplicates        跳过去重验证
  --strict               严格模式
```

### 6.3 实验兼容性检查 (check_experiment_compatibility.py)

```bash
python scripts/check_experiment_compatibility.py [OPTIONS]

参数:
  --data DIR             数据目录路径 (必需)
  --verbose              详细输出
  --output PATH          报告输出路径
```

### 6.4 数据集划分 (split_dataset.py)

```bash
python scripts/split_dataset.py [OPTIONS]

必需参数:
  --input PATH           输入文件路径
  --output DIR           输出目录路径

划分参数:
  --train INT            训练集大小 (默认: 8000)
  --dev INT              验证集大小 (默认: 800)
  --test INT             测试集大小 (默认: 3000)

比例模式:
  --ratio                使用比例模式
  --train_ratio FLOAT    训练集比例 (默认: 0.667)
  --dev_ratio FLOAT      验证集比例 (默认: 0.067)
  --test_ratio FLOAT     测试集比例 (默认: 0.267)

其他:
  --seed INT             随机种子 (默认: 42)
  --no_report            不生成统计报告
```

---

## 七、数据格式规范

### 7.1 完整数据格式

```json
{
  "id": "geosr_001",
  "spatial_relation_type": "directional",
  "question": "北京在上海的什么方向？",
  "answer": "西北方向",
  "reasoning_chain": [
    // topological类型示例:
    // "spatial_relation_type": "topological",
    // "topology_subtype": "within",  // 新增字段 (topological类型专用)
    {
      "step": 1,
      "name": "entity_identification",
      "action": "extract_entities",
      "content": "从问题中识别实体：北京、上海",
      "entities_involved": ["北京", "上海"]
    },
    {
      "step": 2,
      "name": "spatial_relation_extraction",
      "action": "classify_relation",
      "content": "空间关系类型：方向判断",
      "relation_type": "directional"
    },
    {
      "step": 3,
      "name": "coordinate_retrieval",
      "action": "infer_entity_to_token",
      "content": "北京坐标：(39.9042, 116.4074)，上海坐标：(31.2304, 121.4737)",
      "coordinates": {
        "北京": [116.4074, 39.9042],
        "上海": [121.4737, 31.2304]
      }
    },
    {
      "step": 4,
      "name": "spatial_calculation",
      "action": "calculate",
      "content": "计算方位角：北京相对于上海位于西北方向",
      "calculation_result": "西北"
    },
    {
      "step": 5,
      "name": "answer_generation",
      "action": "generate_answer",
      "content": "基于计算结果，北京在上海的西北方向",
      "final_answer": "西北方向"
    }
  ],
  "entities": [
    {"name": "北京", "type": "city", "coords": [116.4074, 39.9042]},
    {"name": "上海", "type": "city", "coords": [121.4737, 31.2304]}
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

### 7.2 必需字段清单

| 字段名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| id | string | 是 | 格式: `geosr_{序号}`，全局唯一 |
| spatial_relation_type | enum | 是 | 取值: `directional`, `topological`, `metric`, `composite` |
| question | string | 是 | 长度: 10-100字符，自然语言问题 |
| answer | string | 是 | 长度: 2-50字符，简洁准确 |
| reasoning_chain | array | 是 | **5步结构化推理** |
| entities | array | 是 | 至少2个实体，每个包含name/type/coords |
| spatial_tokens | array | 是 | 空间相关关键词列表，4-8个 |
| entity_to_token | object | 是* | 实体到Token索引映射 (**Exp7必需**) |
| difficulty | enum | 是 | 取值: `easy`, `medium`, `hard` |
| difficulty_score | float | 是 | 难度评分，1.0-5.0 |

---

## 八、实验数据适配

### 8.1 实验字段依赖矩阵

| 实验 | 方法 | 必需字段 | 数据处理方式 |
|------|------|---------|-------------|
| Exp1 | B1: Direct-SFT | question, answer | 直接使用 |
| Exp2 | B2: Standard-KD | question, answer | 计算KL散度 |
| Exp3a | B2 + C1 (Uniform) | question, answer, spatial_relation_type | 等权重空间关系加权 |
| Exp3 | B2 + C1 (Learnable) | question, answer, spatial_relation_type | 可学习权重 |
| Exp4 | B2 + C2 | question, answer, reasoning_chain | 推理链蒸馏 |
| Exp5 | B2 + C3 | question, answer | 逆向KL |
| Exp6 | B2 + C4 | question, answer | 自蒸馏，使用EMA |
| Exp7 | B2 + C5 | question, answer, entities, spatial_tokens, entity_to_token | 注意力蒸馏 |
| Exp8 | B2 + C6 | question, answer, spatial_relation_type, difficulty | 渐进式调度 |
| Exp9 | GeoKD-SR (完整) | **所有字段** | 组合所有组件 |

### 8.2 数据公平性保障

**核心原则**：所有实验使用**同一个数据文件**，仅在训练时选择性使用不同字段。

```
数据文件: data/geosr_chain/train.jsonl (8,000条)
         data/geosr_chain/dev.jsonl (800条)
         data/geosr_chain/test.jsonl (3,000条)

字段全集: {id, question, answer, spatial_relation_type,
          reasoning_chain, entities, spatial_tokens,
          entity_to_token, difficulty, difficulty_score}
```

---

## 九、执行检查清单

### 9.1 阶段1: 环境准备

- [ ] Python 3.8+ 已安装
- [ ] requirements.txt 依赖已安装
- [ ] GLM-5 API密钥已配置 (`ZHIPUAI_API_KEY`)
- [ ] 实体数据库可用 (`data/entity_database.json`)
- [ ] 输出目录存在 (`data/geosr_chain/`)

### 9.2 阶段2: 数据生成

- [ ] 训练集8,000条按分布生成
- [ ] 验证集800条按比例生成
- [ ] 测试集3,000条按要求生成

### 9.3 阶段3: 数据验证

- [ ] 格式验证通过率 100%
- [ ] 空间关系验证通过率 ≥95%
- [ ] 坐标范围验证通过率 100%
- [ ] 推理链结构验证通过率 ≥90%
- [ ] 去重验证通过率 100%

### 9.4 阶段4: 实验适配验证

- [ ] Exp1-Exp2: question/answer字段可用
- [ ] Exp3a-Exp3: spatial_relation_type字段有效
- [ ] Exp4: reasoning_chain 5步结构完整
- [ ] Exp7: entity_to_token映射完整
- [ ] Exp8: difficulty字段有效
- [ ] Exp9: 所有字段完整

---

## 十、常见问题排查

### 问题1: API调用失败

**现象**: `[错误] API调用失败: 401 - Unauthorized`

**解决方案**:
1. 检查API密钥是否正确设置
2. 确认API密钥未过期
3. 检查网络连接

### 问题2: 数据格式验证失败

**现象**: `[警告] 数据格式验证失败: 缺少必填字段: entity_to_token`

**解决方案**:
1. 确保使用 `--post_process` 参数
2. 检查tokenizer是否正确加载
3. 使用 `--verbose` 查看详细错误

### 问题3: 推理链不完整

**现象**: `L5验证失败: 推理链步骤数量错误`

**解决方案**:
1. 检查GLM-5 API返回的JSON格式
2. 确认prompt模板包含5步要求
3. 使用测试模式验证: `--test_mode`

### 问题4: 坐标超出范围

**现象**: `L4验证失败: 经度超出中国范围`

**解决方案**:
1. 检查实体数据库中的坐标数据
2. 确认坐标格式为 [lon, lat]
3. 验证中国边界范围设置

---

## 十一、下一步

数据准备完成后，请进入：

**[阶段2 - 代码实现](../02-阶段2-代码实现/)**

---

## 相关文档

- [01-数据集获取](./01-数据集获取.md) - 数据获取方式
- [1.1-数据生成规范](./1.1-数据生成规范.md) - 推理链标准格式
- [1.2-数据验证清单](./1.2-数据验证清单.md) - 详细验证规则
- [1.3-输入输出规范](./1.3-输入输出规范.md) - 格式和字段定义

---

*版本: V7.0*
*最后更新: 2026-03-06*
