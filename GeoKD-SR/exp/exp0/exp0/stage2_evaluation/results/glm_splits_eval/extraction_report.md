# GLM错误样本提取报告

## 2026-03-20 任务完成

### 任务概述
使用与evaluate.py完全相同的DeterministicMetrics判断逻辑，重新提取GLM预测的错误样本，确保结果与metrics.json一致。

### 关键发现

#### 配置差异问题
初始脚本使用默认配置，导致topological类型结果不一致：
- 默认配置：topological 221/338 = 65.38%（错误117例）
- 正确配置：topological 188/338 = 55.62%（错误150例）

#### 根本原因
配置文件 `eval_config.yaml` 使用了自定义的 `spatial_keywords`：
- 配置文件中的topological关键词：["相邻", "包含", "被包含", "交叉", "分离", "接壤", "重叠"]
- DeterministicMetrics默认包含更多关键词（23个）

### 创建的文件
- `stage2_evaluation/extract_glm_errors.py` - 错误样本提取脚本

### 输出文件
- `results/glm_splits_eval/error_samples.jsonl` - 321条错误样本（661KB）
- `results/glm_splits_eval/error_stats.json` - 统计信息

### 验证结果（与metrics.json完全一致）

| 空间类型 | 准确率 | 正确/总数 | 错误数 |
|---------|--------|----------|--------|
| directional | 85.62% | 250/292 | 42 |
| metric | 88.93% | 273/307 | 34 |
| composite | 61.38% | 151/246 | 95 |
| topological | 55.62% | 188/338 | 150 |
| **总计** | **72.87%** | **862/1183** | **321** |

### 错误类型分布（Top 5）
1. 拓扑关系未识别: 59例
2. 拓扑类型错误（None→包含于）: 38例
3. 拓扑类型错误（包含→包含于）: 17例
4. 距离错误: 17例
5. 方向错误（应为东南，预测为西南）: 10例

### Topological子类型转换分析

主要错误模式：
| 转换类型 | 数量 |
|---------|------|
| None→within | 38例 |
| None→None | 30例 |
| contains→within | 17例 |
| disjoint→None | 10例 |
| disjoint→contains | 6例 |
| disjoint→within | 6例 |

### 错误样本格式

```json
{
  "id": "geosr_xxx_xxxxx",
  "spatial_type": "directional/metric/topological/composite",
  "difficulty": "easy/medium/hard",
  "question": "原始问题",
  "reference": "标准答案",
  "prediction": "模型预测",
  "error_type": "错误类型描述",
  "entities": [...],
  "reasoning_chain": [...],
  "spatial_tokens": [...],
  "topology_subtype_ref": "参考拓扑类型（仅topological）",
  "topology_subtype_pred": "预测拓扑类型（仅topological）"
}
```

### 使用方法

```bash
cd D:/30_keyan/GeoKD-SR/exp/exp0/exp0/stage2_evaluation
python extract_glm_errors.py
```
