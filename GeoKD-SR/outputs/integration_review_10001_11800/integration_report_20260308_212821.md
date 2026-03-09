# 数据整合审查报告

## 概述
- 整合时间: 2026-03-08 21:28:21
- 源数据文件:
  - generated_10001_to_10600.jsonl
  - generated_10601_to_11200.jsonl
  - generated_11201_to_11800.jsonl

## Step 1: 字段修复
- 总记录数: 1791
- 修复记录数: 3582
- 缺少difficulty_score: 1791
- 缺少entity_to_token: 1791

## Step 2: 数据合并
- 现有数据: 9512 条
- 新数据: 1791 条
- 重复ID: 0 个
- 去重后新数据: 1791 条
- 合并后总数: 11303 条

## Step 3: 数据修复
- 重计算difficulty_score: 0
- 清理spatial_tokens: 0
- 修复topology_subtype: 0

## Step 5: 最终数据分布

### 空间关系类型分布
| composite | 2362 | 20.9% |
| directional | 2910 | 25.75% |
| metric | 3159 | 27.95% |
| topological | 2872 | 25.41% |

### 难度分布
| easy | 3427 | 30.32% |
| hard | 2335 | 20.66% |
| medium | 5541 | 49.02% |

### 拓扑子类型分布
| adjacent | 374 | 13.02% |
| contains | 378 | 13.16% |
| disjoint | 1381 | 48.08% |
| inside | 3 | 0.1% |
| intersect | 1 | 0.03% |
| overlap | 335 | 11.66% |
| touch | 8 | 0.28% |
| within | 392 | 13.65% |

### 数据集划分
| dev | 800 | 7.08% |
| test | 2986 | 26.42% |
| train | 7517 | 66.5% |

### 难度分数分布
| 1.0-2.0 | 1834 | 16.23% |
| 2.0-3.0 | 4670 | 41.32% |
| 3.0-4.0 | 2464 | 21.8% |
| 4.0-5.0 | 2335 | 20.66% |

### 字段完整性检查
| id | 11303/11303 | 100.0% |
| question | 11303/11303 | 100.0% |
| answer | 11303/11303 | 100.0% |
| spatial_relation_type | 11303/11303 | 100.0% |
| difficulty | 11303/11303 | 100.0% |
| entities | 11303/11303 | 100.0% |
| spatial_tokens | 11303/11303 | 100.0% |
| reasoning_chain | 11303/11303 | 100.0% |
| difficulty_score | 11303/11303 | 100.0% |
| entity_to_token | 11303/11303 | 100.0% |

## 总结

整合任务已完成，所有步骤执行成功。

### 变更记录
1. 新增 10001-11800 范围的数据
2. 补充缺失字段 (difficulty_score, entity_to_token)
3. 清理 spatial_tokens 字段
4. 修复 topology_subtype 字段
5. 更新主文件 balanced_topology.jsonl
