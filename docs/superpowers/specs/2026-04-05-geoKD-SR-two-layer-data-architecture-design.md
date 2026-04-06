# GeoKD-SR 双层数据架构设计规范

> 设计日期: 2026-04-05
> 红束投目标: ISPRS IJGI Special Issue "LLM4GIS"

## 1. 核心定位

验证小模型(Qwen2.5-1.5B)能否从大模型(Qwen2.5-7B)通过知识蒸馏学习空间推理能力：
- **推理能力**：根据已知信息推导空间关系结论
- **自然语言理解**：理解不同表述方式的空间问题并准确回答

## 2. 双层数据架构

### Layer 1: 实体对事实层
- PostGIS精确计算空间事实，每对仅包含target_relation相关字段
- **两阶段生成**: Phase 1 = 10,000正例, Phase 2 = 1,237负例, 总计11,237条
- 用户按需选择负例策略进行对比实验

### Layer 2: 题目实例层
- GLM-4.7 API根据事实生成4种题型(判断/选择/填空/问答)
- 每对生成4题 × 11,237对 = 44,948条实例

## 3. 11种空间关系类型

| 关系类型 | 数量(正例) | 数量(负例) | spatial_facts字段 | 备注 |
|---------|-----------|-----------|------------------|------|
| directional | 2,500 | 0 | {direction_8, azimuth_deg} | |
| metric | 2,500 | 0 | {distance_km} | |
| topological.contains | 500 | 150 | {contains: bool} | |
| topological.within | 500 | 150 | {within: bool} | |
| topological.touches | 500 | 150 | {touches: bool} | PostGIS直接计算 |
| topological.crosses | 500 | 150 | {crosses: bool} | |
| topological.disjoint | 500 | 150 | {disjoint: bool} | |
| composite.direction_distance | 875 | 0 | {direction_8, azimuth_deg, distance_km} | |
| composite.direction_topology | 500 | 150 | {direction_8, azimuth_deg, within/contains/touches/crosses/disjoint} | |
| composite.distance_topology | 500 | 150 | {distance_km, within/contains/touches/crosses/disjoint} | |
| composite.direction_distance_topology | 625 | 187 | {direction_8, azimuth_deg, distance_km, within/contains/...} | |

## 4. 负例使用策略

| 方案 | 训练数据 | 说明 |
|------|---------|------|
| A | 10,000正例 | Baseline |
| B | 8,763正 + 1,237负 | 替换同量负例 |
| C | 10,000正 + 1,237负 | 全部混合 |

## 4.5 实体数据约束

- **实体来源**: entity_database_v3.json (1,360有效实体) + PostGIS geoatlas表(完整空间计算)
- **无park/small_lake/forest数据**: 原始设计中的city→park、city→small_lake组合已重新分配
- **Touches**: 500对正例，使用PostGIS从geoatlas表直接计算（省-省~70对 + 市-市~941对，数据充足）
- **过采样策略**: 1.5倍过采样(~15,000) → 多样性筛选 → 10,000正例
- **详细采样策略**: 见计划文件 Section 1B

## 5. 实现Pipeline

```
Step 1a: Phase 1 - 正例实体对生成 (PostGIS)
Step 1b: Phase 2 - 负例实体对生成 (PostGIS)
Step 2: 题目实例层生成 (GLM-4.7 API)
Step 3: 数据划分与组合 (8:1:1 based on Phase 1)
Step 4: 训练与评测 (Exp01-Exp09)
```

## 6. 评测场景

- **有坐标模式**: 测试空间推理能力(给定坐标推导关系)
- **无坐标模式**: 测试内部空间知识(不给坐标直接问关系)
- 两种模式独立评测，分开报告

## 7. 评测指标

| 题型 | 指标 |
|------|------|
| 判断题 | Accuracy (精确匹配) |
| 选择题 | Accuracy (精确匹配) |
| 填空题 | Keyword F1 |
| 问答题 | BLEU-4 + ROUGE-L + BERTScore + Spatial F1 |

## 8. 关键设计约束

1. answer_structured必须从spatial_facts直接派生
2. 方向推理不包含距离信息(纯方向)
3. 4种题型风格各异，保证多样性
4. 负例独立存储，用户按需选择
5. 实体对按pair_id分层8:1:1划分
