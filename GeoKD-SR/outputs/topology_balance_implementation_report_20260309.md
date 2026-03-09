# 拓扑子类型平衡修复方案实施报告

> **执行日期**: 2026-03-09
> **执行状态**: 进行中（后台API生成）

---

## 一、执行摘要

### 1.1 完成的工作

| 步骤 | 状态 | 结果 |
|------|------|------|
| Step 1: 创建补充prompts配置 | ✅ 完成 | 生成1838条prompts |
| Step 2: 下采样原始数据 | ✅ 完成 | disjoint从2531降到600 |
| Step 3: API生成补充数据 | 🔄 进行中 | 后台任务运行中 |
| Step 4: 合并数据 | ⏳ 待执行 | 等待API完成 |
| Step 5: 验证最终分布 | ⏳ 待执行 | 等待合并完成 |

### 1.2 后台任务信息
- **任务ID**: b9npdcy02
- **预计生成数量**: 1838条
- **API**: GLM-5 (zhipuai SDK)
- **预计时间**: 2-3小时

---

## 二、详细执行记录

### 2.1 创建的脚本

#### scripts/create_topology_supplement_prompts.py
- 从entity_database_expanded.json选取实体对
- 生成符合prompts_config_full.json格式的prompts
- 支持四种拓扑子类型: within, contains, adjacent, overlap

#### scripts/merge_balanced_topology.py
- 合并原始数据和补充数据
- 支持字段名兼容: `topology_subtype` 和 `relation_subtype`
- 非标准子类型映射:
  - touch → adjacent
  - inside → within
  - crosses → overlap

### 2.2 生成的文件

| 文件 | 路径 | 说明 |
|------|------|------|
| 补充prompts | data/prompts/topology_supplement_prompts.json | 1838条 |
| 下采样数据 | data/geosr_chain/balanced_topology_downsampled.jsonl | 9757条 |
| 补充数据 | data/geosr_chain/supplement_topology.jsonl | 生成中... |

### 2.3 下采样结果

**原始分布** (raw_merged.jsonl中的topological数据):
| 子类型 | 原始数量 | 下采样后 |
|--------|----------|----------|
| disjoint | 2531 | 600 |
| overlap | 89 | 89 |
| contains | 226 | 226 |
| adjacent | 172 | 172 |
| within | 239 | 239 |
| **总计** | 3257 | 1326 |

**需要补充的数量** (目标各600条):
| 子类型 | 当前 | 需要 |
|--------|------|------|
| disjoint | 600 | 0 ✅ |
| overlap | 89 | 511 |
| contains | 226 | 374 |
| adjacent | 172 | 428 |
| within | 239 | 361 |
| **补充总计** | - | **1674** |

### 2.4 Prompts生成分布

| 子类型 | 数量 | 占比 |
|--------|------|------|
| within | 512 | 27.9% |
| contains | 374 | 20.3% |
| adjacent | 440 | 23.9% |
| overlap | 512 | 27.9% |
| **总计** | 1838 | 100% |

**难度分布**:
- easy: 536 (29.2%)
- medium: 946 (51.5%)
- hard: 356 (19.4%)

**Split分布**:
- train: 1486 (80.8%)
- dev: 175 (9.5%)
- test: 177 (9.6%)

---

## 三、后续步骤

### 3.1 等待API生成完成

检查后台任务进度:
```bash
# 查看进度
cat D:/30_keyan/GeoKD-SR/data/geosr_chain/generation_progress.json

# 或检查输出文件
wc -l D:/30_keyan/GeoKD-SR/data/geosr_chain/supplement_topology.jsonl
```

### 3.2 合并数据

API生成完成后执行:
```bash
python scripts/merge_balanced_topology.py \
    --input data/geosr_chain/raw_merged.jsonl \
    --supplement data/geosr_chain/supplement_topology.jsonl \
    --output data/geosr_chain/balanced_topology_final_v2.jsonl \
    --target-per-type 600 \
    --report outputs/topology_balance_report_v2.md
```

### 3.3 验证最终数据

```bash
python scripts/validate_dataset_v2.py \
    --input data/geosr_chain/balanced_topology_final_v2.jsonl \
    --check topology_balance
```

---

## 四、技术要点

### 4.1 字段名兼容性处理
原始数据使用 `topology_subtype`，合并脚本需要兼容 `relation_subtype`。

### 4.2 非标准子类型映射
```
touch → adjacent
inside → within
crosses → overlap
covers → contains
coveredby → within
intersects → overlap
equals → overlap
```

### 4.3 随机种子
使用种子42确保下采样可复现。

---

## 五、注意事项

1. **API生成时间**: 1838条数据预计需要2-3小时
2. **推理链泄露问题**: 新生成的数据可能仍包含泄露，建议生成后统一修复
3. **数据验证**: 合并后需要验证每个子类型达到600条目标
4. **非拓扑数据**: 保持不变（约8431条）

---

*报告生成时间: 2026-03-09 12:26*
