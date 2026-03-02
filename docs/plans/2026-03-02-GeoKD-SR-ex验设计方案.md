# GeoKD-SR 实施计划

**创建时间**: 2026年3月2日
**目标**: 实现GeoKD-SR地理空间推理知识蒸馏框架

## 概述

本实施计划基于已完成的设计方案，分阶段实现以下内容：
1. 数据集生成（5,000条训练 + 500条验证 + 1,000条测试）
2. 4个基线方法实现
3. 6组件GeoKD-SR框架实现
4. 实验与消融

## 技术栈

- Python 3.12.12
- PyTorch 2.6.0+cu124
- Transformers 4.48.3
- PEFT 0.14.0
- Qwen2.5-7B-Instruct (教师)
- Qwen2.5-1.5B-Instruct (学生)

## 实施阶段

### 阶段1: 数据准备 (第1-2天)

#### 任务1.1: 声地理实体库

**文件**: `GeoKD-SR/data/entity_database.json`

**步骤**:
1. 收集中国主要城市数据（200+城市）
2. 添加省份信息（34个省级行政区)
3. 添加国家信息（50+)

**验证**:
```bash
python scripts/data_manager.py stats --file data/entity_database.json
```

#### 任务1.2: 实现数据生成脚本

**文件**: `GeoKD-SR/scripts/generate_data.py`

**步骤**:
1. 实现方向关系模板
2. 实现拓扑关系模板
3. 实现度量关系模板
4. 实现组合推理模板
5. 生成5,000条训练数据
6. 生成500条验证数据
7. 生成1,000条测试数据

**验证**:
```bash
python scripts/data_manager.py validate --file data/geosr_chain/train.jsonl
# 预期: 所有数据通过质量检查
```

### 阶段2: 基线实现 (第3-5天)

#### 任务2.1: B1-DirectSFT

**文件**: `GeoKD-SR/baselines/direct_sft.py`

**步骤**:
1. 创建DirectSFT类
2. 实现forward方法
3. 添加单元测试

#### 任务2.2: B2-StandardKD

**文件**: `GeoKD-SR/baselines/standard_kd.py`

**步骤**:
1. 创建StandardKD类
2. 实现Forward KL蒸馏
3. 添加单元测试

#### 任务2.3: B3-MiniLLM

**文件**: `GeoKD-SR/baselines/minillm.py`

**步骤**:
1. 创建MiniLLM类
2. 实现Reverse KL蒸馏
3. 添加单元测试

#### 任务2.4: B4-CoTDistill

**文件**: `GeoKD-SR/baselines/cot_distill.py`

**步骤**:
1. 创建CoTDistill类
2. 实现思维链蒸馏
3. 添加单元测试

### 阶段3: GeoKD-SR实现 (第6-10天)

#### 任务3.1: C1-空间关系蒸馏

**文件**: `GeoKD-SR/models/losses/spatial_relation_loss.py`

#### 任务3.2: C2-空间推理链蒸馏

**文件**: `GeoKD-SR/models/losses/spatial_cot_loss.py`

#### 任务3.3: C3-空间反向KL

**文件**: `GeoKD-SR/models/losses/spatial_reverse_kl.py`

#### 任务3.4: C4-空间Token加权

**文件**: `GeoKD-SR/models/losses/spatial_token_weighting.py`

#### 任务3.5: C5-空间对比蒸馏

**文件**: `GeoKD-SR/models/losses/spatial_contrastive.py`

#### 任务3.6: C6-空间注意力蒸馏

**文件**: `GeoKD-SR/models/losses/spatial_attention.py`

#### 任务3.7: 整合损失函数

**文件**: `GeoKD-SR/models/losses/geo_kd_sr_loss.py`

### 阶段4: 实验与消融 (第11-13天)

#### 任务4.1: 基线对比实验

**步骤**:
1. 训练4个基线模型
2. 训练GeoKD-SR模型
3. 在GeoSR-Bench上评测

#### 任务4.2: 消融实验

**步骤**:
1. 运行9种消融配置(A0-A8)
2. 记录各组件贡献
3. 分析结果

## 验证方法

### 数据质量验证

```bash
python scripts/data_manager.py stats --file data/geosr_chain/train.jsonl
python scripts/data_manager.py validate --file data/geosr_chain/train.jsonl
```

### 模型训练验证

```bash
python scripts/train.py --method direct_sft --epochs 1
python scripts/train.py --method standard_kd --epochs 1
python scripts/train.py --method geo_kd_sr --epochs 3
```

### 评测验证

```bash
python scripts/evaluate.py --model checkpoints/geo_kd_sr --benchmark data/geosr_bench/benchmark.json
```

## 执行选项

推荐使用 **Subagent-Driven** 模式，在当前会话中通过分派子任务执行各模块实现。

## 风险与应对

| 风险 | 应对 |
|------|------|
| 显存不足 | 使用4bit量化+LoRA |
| 训练时间过长 | 梯度累积+混合精度 |
| 数据质量不佳 | 增加验证规则 |

## 成功标准

- 所有基线评测完成
- GeoKD-SR优于所有基线
- 消融实验显示各组件贡献
- 训练损失收敛
- 评测指标达标
