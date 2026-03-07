# GeoKD-SR 数据集优化方案 V2.0 实施报告

> **日期**: 2026-03-06
> **版本**: V2.0
> **状态**: 已完成

---

## 一、修改概述

按照V2.0设计方案，对GeoKD-SR数据生成脚本进行了全面优化，主要改进包括：
1. 稡型分布参数调整为GIS平衡型分布
2. 难度评分算法升级到V2.0版本
3. 拓扑关系Prompt支持子类型
4. 验证脚本支持新字段
5. 采样器支持拓扑子类型分布

---

## 二、详细修改内容
### 2.1 分布参数更新 (GIS平衡型)
**修改位置**: `scripts/generate_data_glm5.py` - `BalancedSampler.DEFAULT_RELATION_DISTRIBUTION`

| 稡块 | 旧版本 | 新版本 | 变更 |
|------|--------|--------|------|
| **directional** | 0.30 | 0.25 | ↓5% |
| **topological** | 0.225 | 0.275 | ↑5% |
| **metric** | 0.225 | 0.275 | ↑5% |
| **composite** | 0.25 | 0.20 | ↓5% |
| **总计** | 1.00 | 1.00 | ✓ |

**调整依据**:
- topological和metric在GIS中更为常见
- 娡型训练更均衡的空间推理能力

---

### 2.2 拓扑子类型分布 (均匀分布型)
**修改位置**: `scripts/generate_data_glm5.py` - `BalancedSampler.DEFAULT_TOPOLOGY_SUBTYPE_DISTRIBUTION`

| 子类型 | 占比 | 描述 |
|---------|------|---------|
| **within** | 20% | A在B内部 |
| **contains** | 20% | B包含A |
| **adjacent** | 20% | A与B相邻 |
| **disjoint** | 20% | A与B分离 |
| **overlap** | 20% | A与B交叉 |
| **总计** | 100% | ✓ |

**示例**:
- within: 故宫在北京市内
- contains: 北京市包含故宫
- adjacent: 河北省与山东省相邻
- disjoint: 海南省与黑龙江省不接壤
- overlap: 长江流经多个省份

---

### 2.3 难度评分算法 V2.0
**修改位置**: `scripts/generate_data_glm5.py` - `calculate_difficulty_score_v2()` 函数

#### 基础分微调
| 空间关系类型 | 旧版本 | 新版本 | 变更 |
|-------------|--------|--------|------|
| **directional** | 1.5 | 1.2 | ↓0.3 |
| **topological** | 2.0 | 2.2 | ↑0.2 |
| **metric** | 1.0 | 1.3 | ↑0.3 |
| **composite** | 3.0 | 3.2 | ↑0.2 |
#### 新增维度
**1. 拓扑子类型加成**
| 子类型 | 加成值 | 复杂度 |
|---------|--------|--------|
| **within** | 0.0 | 简单 |
| **contains** | 0.1 | 简单 |
| **adjacent** | 0.3 | 中等 |
| **disjoint** | 0.4 | 中等 |
| **overlap** | 0.6 | 复杂 |
**2. 实体数量加成**
```python
entity_count_bonus = max(0, (entity_count - 2) * 0.3)
```
**3. 实体类型对加成 (更精细)**
| 类型对 | 加成值 |
|---------|--------|
| ("city", "city") | 0.0 |
| ("city", "landmark") | 0.2 |
| ("province", "city") | 0.4 |
| ("river", "city") | 0.7 |
| ("mountain", "city") | 0.7 |
| ("region", "city") | 0.9 |
#### 难度映射函数
```python
def score_to_difficulty(score: float) -> str:
    if score <= 2.0:
        return "easy"
    elif score <= 3.5:
        return "medium"
    else:
        return "hard"
```
#### 难度等级划分
| 稡式 | 分数范围 | 占比 |
|------|---------|------|
| **Easy** | 1.0-2.0 | 30% |
| **Medium** | 2.1-3.5 | 50% |
| **Hard** | 3.6-5.0 | 20% |

---

### 2.4 拓扑关系Prompt V2.0
**修改位置**: `scripts/generate_data_glm5.py` - `_generate_topological_prompt()` 方法
#### 新增参数
- `topology_subtype`: 拓扑子类型 (within/contains/adjacent/disjoint/overlap)
#### 新增内容
1. 子类型关系描述
2. 子类型问题示例
3. 子类型说明表格
4. 输出中包含topology_subtype字段
#### Prompt模板结构
```
请生成一个关于"{entity1}"和"{entity2}"之间拓扑关系的地理问题。

已知信息：
- {entity1_name}: {entity1_type}类型
- {entity2_name}: {entity2_type}类型
- 拓扑关系子类型: {topology_subtype}
- 关系描述: {relation}

拓扑子类型说明：
- within: A在B内部 (如: 故宫在北京市内)
- contains: B包含A (如: 北京市包含故宫)
- adjacent: A与B相邻 (如: 河北省与山东省相邻)
- disjoint: A与B分离 (如: 海南省与黑龙江省不接壤)
- overlap: A与B交叉 (如: 长江流经多个省份)
```
---
### 2.5 騡型数据生成器分布更新
**修改位置**: `scripts/generate_data_glm5.py` - `GeoSRDataGenerator.DEFAULT_RELATION_DISTRIBUTION`
| 模块 | 旧版本 | 新版本 | 变更 |
|------|--------|--------|------|
| **directional** | 0.30 | 0.25 | ↓5% |
| **topological** | 0.225 | 0.275 | ↑5% |
| **metric** | 0.225 | 0.275 | ↑5% |
| **composite** | 0.25 | 0.20 | ↓5% |
#### 新增常量
```python
DEFAULT_TOPOLOGY_SUBTYPE_DISTRIBUTION = {
    "within": 0.20,     # A在B内部
    "contains": 0.20,   # B包含A
    "adjacent": 0.20,   # A与B相邻
    "disjoint": 0.20,   # A与B分离
    "overlap": 0.20      # A与B交叉
}
```
---
### 2.6 騡型数据生成器分布更新
**修改位置**: `scripts/generate_data_glm5.py` - `BalancedSampler.__init__()`
#### 新增参数
- `topology_subtype_distribution`: 拓扑子类型分布 (可选)
#### 初始化逻辑
```python
self.topology_subtype_distribution = (
    topology_subtype_distribution or
    self.DEFAULT_TOPOLOGY_SUBTYPE_DISTRIBUTION
)
self._validate_distribution(self.topology_subtype_distribution, "拓扑子类型")
```
---
### 2.7 騡型数据验证器更新
**修改位置**: `scripts/validate_data.py`
#### 新增常量
```python
TOPOLOGY_SUBTYPES = ["within", "contains", "adjacent", "disjoint", "overlap"]

# V2.0 目标分布
TARGET_RELATION_DISTRIBUTION = {
    "directional": 0.25,     # 25%
    "topological": 0.275,    # 27.5%
    "metric": 0.275,         # 27.5%
    "composite": 0.20          # 20%
}
```
#### 新增验证逻辑
**1. topology_subtype验证**
- 检查值是否为有效子类型 (within/contains/adjacent/disjoint/overlap)
- topological类型但没有topology_subtype时发出警告
**2. difficulty_score范围验证**
- 检查是否为数值类型
- 检查是否在1.0-5.0范围内
---

## 三、 测试验证结果
### 3.1 分布参数验证
```
空间关系分布总和: 1.000 ✅
难度分布总和: 1.000 ✅
拓扑子类型分布总和: 1.000 ✅
```
### 3.2 难度评分函数验证
```
Case 1: directional -> Score: 1.7, Level: easy ✅
Case 2: topological -> Score: 2.4, Level: medium ✅
Case 3: topological -> Score: 2.8, Level: medium ✅
Case 4: metric -> Score: 1.8, Level: easy ✅
Case 5: composite -> Score: 3.2, Level: medium ✅
```
---
## 四、 修改的文件列表
| 文件 | 修改类型 | 主要修改内容 |
|------|---------|---------|
| `scripts/generate_data_glm5.py` | **主要修改** | 分布参数、 难度算法、 拓扑Prompt, 采样器 |
| `scripts/validate_data.py` | **验证更新** | 勤量定义, 验证逻辑 |
| `memory.md` | **记录更新** | 添加V2.0实施记录 |
| `docs/GeoKD-SR-数据集优化方案V2.0-实施报告.md` | **新建** | 本文档 |
---
## 五、 阶段/阶段对照表
| 騡块 | 修改前行 | 修改后 | 说明 |
|------|---------|---------|------|
| **BalancedSampler** | | 4个属性 | 5个属性 | +topology_subtype_distribution |
| **GeoSRDataGenerator** | 1个常量 | 2个常量 | +DEFAULT_TOPOLOGY_SUBTYPE_DISTRIBUTION |
| **DataValidator** | 5个常量 | 7个常量 | +TOPOLOGY_SUBTYPES, +TARGET_RELATION_DISTRIBUTION |
| **calculate_difficulty_score** | 1个函数 | 2个函数 | +calculate_difficulty_score_v2, +score_to_difficulty |
| **_generate_topological_prompt** | 2个参数 | 3个参数 | +topology_subtype |

---

## 六、 兼容性验证
### 6.1 数据格式兼容性
| 检查项 | 要求 | 状态 |
|---------|------|------|
| JSON格式 | 有效的JSON | ✅ |
| 必需字段 | 9个字段全部存在 | ✅ |
| reasoning_chain | 5步结构完整 | ✅ |
| entities | 包含coords字段 | ✅ |
| spatial_tokens | 4-8个关键词 | ✅ |
| entity_to_token | 完整映射 | ✅ |
| difficulty | 有效枚举值 | ✅ |
| difficulty_score | 1.0-5.0范围 | ✅ |
| topology_subtype | 有效子类型 | ✅ (topological类型) |
### 6.2 模型兼容性
| 模型 | 输入兼容 | 输出兼容 |
|---------|---------|---------|
| **Exp1-3** | ✅ | ✅ |
| **Exp4-9** | ✅ | ✅ |
| **GLM-5 API** | ✅ | ✅ |
| **Qwen2.5** | ✅ | ✅ |
---
## 七、 数据集预期目标
### 7.1 数据规模
| 数据集 | 目标数量 | 分布 |
|---------|---------|------|
| **train.jsonl** | 8,000条 | 按V2.0分布 |
| **dev.jsonl** | 800条 | 按V2.0分布 |
| **test.jsonl** | 3,000条 | 按V2.0分布 |
| **总计** | 11,800条 | - |
### 7.2 分布目标
| 类型 | 占比 | 数量 (训练集) |
|------|------|--------------|
| **directional** | 25% | 2,000 |
| **topological** | 27.5% | 2,200 |
| **metric** | 27.5% | 2,200 |
| **composite** | 20% | 1,600 |
### 7.3 拓扑子类型目标
| 子类型 | 占比 | 数量 (训练集) |
|---------|------|--------------|
| **within** | 20% | 440 |
| **contains** | 20% | 440 |
| **adjacent** | 20% | 440 |
| **disjoint** | 20% | 440 |
| **overlap** | 20% | 440 |
### 7.4 难度目标
| 难度 | 占比 | 数量 (训练集) |
|------|------|--------------|
| **easy** | 30% | 2,400 |
| **medium** | 50% | 4,000 |
| **hard** | 20% | 1,600 |
---
## 八、 使用说明
### 8.1 生成测试数据
```bash
# 设置API密钥
export ZHIPUAI_API_KEY="your_api_key_here"

# 测试模式生成少量数据
python scripts/generate_data_glm5.py --test_mode --train_count 100 --dev_count 10 --test_count 30 --output data/geosr_chain/
```
### 8.2 生成完整数据集
```bash
# 生成完整数据集
python scripts/generate_data_glm5.py \
    --train_count 8000 \
    --dev_count 800 \
    --test_count 3000 \
    --output data/geosr_chain/ \
    --post_process
```
### 8.3 騡型数据验证
```bash
# 验证生成的数据
python scripts/validate_data.py \
    --input data/geosr_chain/train.jsonl \
    --verbose \
    --check_distribution
```
---
## 九、 注意事项
1. **API密钥**: 騡型需要设置 `ZHIPUAI_API_KEY` 环境变量
2. **模型下载**: 騡型需要先下载Qwen2.5模型
3. **内存要求**: 建议32GB+内存用于完整数据生成
4. **生成时间**: 完整数据集约需要12-24小时
5. **数据验证**: 生成后务必运行验证脚本检查数据质量
---

## 十、 版本历史
| 版本 | 日期 | 主要变更 |
|------|------|---------|
| **V1.0** | 2026-03-01 | 初始版本 |
| **V2.0** | 2026-03-06 | GIS平衡型分布、 拓扑子类型、 难度算法V2.0 |

---

*报告生成时间: 2026-03-06*
*作者: Claude Code Assistant*
