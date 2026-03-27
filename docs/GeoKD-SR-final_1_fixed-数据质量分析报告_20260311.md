# GeoKD-SR final_1_fixed.jsonl 数据质量分析报告

> **分析日期**: 2026-03-11
> **数据版本**: final_1_fixed.jsonl
> **记录数**: 11,656条
> **分析工具**: Claude Code 自动化分析

---

## 一、执行摘要

本报告对 `GeoKD-SR/data/final/final_1_fixed.jsonl` 数据集进行了全面的质量审查，与 `docs/GeoKD-SR-实验执行手册-V6.0/01-阶段1-数据准备/1.1-数据生成规范.md` 和 `docs/GeoKD-SR-实验设计方案-V5.2.md` 进行对比分析。

### 关键发现

| 严重性 | 问题类型 | 影响范围 | 状态 |
|--------|---------|---------|------|
| 🔴 严重 | 重复ID | 449条记录 | 需修复 |
| 🔴 严重 | 拓扑子类型分布不均衡 | 3,225条 | 需补充数据 |
| 🟡 中等 | answer过短 | 1,814条 | 可选修复 |
| 🟢 轻微 | entity_to_token部分映射 | 14条 | 需修复 |

---

## 二、已完成的修复项（之前的工作）

| 修复项 | 状态 | 通过率 | 说明 |
|--------|------|--------|------|
| 删除 prompt_id/split | ✅ 完成 | 100% | 0条残留 |
| 统一字段顺序 | ✅ 完成 | 100% | 符合规范顺序 |
| final_answer 一致性 | ✅ 完成 | 100% | 与answer完全一致 |
| reasoning_chain 5步 | ✅ 完成 | 100% | 所有记录5步推理 |
| entities coords | ✅ 完成 | 100% | 所有实体有坐标 |
| 必需字段完整性 | ✅ 完成 | 100% | 无缺失字段 |
| entity_to_token 完整性 | ✅ 基本完成 | 99.88% | 14条有缺失 |

---

## 三、发现的问题详情

### 3.1 重复ID问题（严重）

**问题描述**: 449条记录存在重复ID，共涉及25个ID。

**重复ID完整清单**:

| ID | 重复次数 | 空间类型 |
|-----|---------|---------|
| geosr_metric_001 | 89 | metric |
| geosr_metric_002 | 50 | metric |
| geosr_metric_003 | 39 | metric |
| geosr_metric_004 | 30 | metric |
| geosr_directional_005 | 26 | directional |
| geosr_metric_005 | 24 | metric |
| geosr_directional_001 | 20 | directional |
| geosr_metric_006 | 18 | metric |
| geosr_directional_003 | 17 | directional |
| geosr_directional_002 | 15 | directional |
| geosr_composite_001 | 14 | composite |
| geosr_composite_002 | 13 | composite |
| geosr_composite_003 | 11 | composite |
| geosr_directional_004 | 10 | directional |
| geosr_topological_001 | 9 | topological |
| geosr_topological_002 | 8 | topological |
| geosr_topological_003 | 7 | topological |
| geosr_topological_004 | 6 | topological |
| geosr_topological_005 | 5 | topological |
| geosr_composite_004 | 4 | composite |
| geosr_composite_005 | 3 | composite |
| geosr_topological_006 | 3 | topological |
| geosr_topological_007 | 2 | topological |
| geosr_composite_006 | 2 | composite |
| geosr_topological_008 | 2 | topological |

**影响分析**:
- 训练集可能存在数据泄露风险（相同记录在训练/测试集出现）
- 模型可能过度拟合重复样本
- 统计分析结果可能不准确

**修复建议**:
```python
# 方案A: 重新生成唯一ID
def regenerate_unique_ids(records):
    seen_ids = set()
    for i, record in enumerate(records):
        original_id = record['id']
        if original_id in seen_ids:
            record['id'] = f"{original_id}_{i}"
        seen_ids.add(record['id'])
    return records

# 方案B: 基于内容去重
def deduplicate_by_content(records):
    seen = set()
    unique = []
    for r in records:
        key = (r['question'], r['answer'])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique
```

---

### 3.2 拓扑子类型分布不均衡（严重）

**问题描述**: topological类型的5种子类型分布严重偏离规范要求的均匀分布(各20%)。

**当前分布 vs 规范要求**:

| 子类型 | 实际数量 | 实际占比 | 目标占比 | 偏差 | 状态 |
|--------|---------|---------|---------|------|------|
| within | 818 | 25.4% | 20% | +5.4% | ⚠️ 可接受 |
| contains | 181 | **5.6%** | 20% | **-14.4%** | ❌ 严重不足 |
| adjacent | 966 | 30.0% | 20% | +10.0% | ⚠️ 偏高 |
| disjoint | 1,249 | **38.7%** | 20% | **+18.7%** | ❌ 过多 |
| overlap | 11 | **0.3%** | 20% | **-19.7%** | ❌ 几乎没有 |

**可视化对比**:
```
目标分布 (各20%):
within    ████████████████████ 20%
contains  ████████████████████ 20%
adjacent  ████████████████████ 20%
disjoint  ████████████████████ 20%
overlap   ████████████████████ 20%

实际分布:
within    █████████████████████████ 25.4%
contains  ██████ 5.6% ❌
adjacent  ██████████████████████████████ 30.0%
disjoint  ████████████████████████████████████████ 38.7% ❌
overlap   █ 0.3% ❌
```

**需要的数据补充**:
- contains: 需增加约 464条
- overlap: 需增加约 634条
- 可考虑减少: disjoint(约604条)、adjacent(约322条)

**根本原因**: 数据生成脚本中拓扑子类型采样策略存在问题

---

### 3.3 answer过短问题（中等）

**问题描述**: 1,814条记录(15.6%)的answer字段少于5个字符。

**过短答案类型分布**:

| 答案内容 | 预估出现次数 | 字符数 |
|---------|-------------|--------|
| 相离关系 | ~800 | 4 |
| 相离 | ~600 | 2 |
| 相邻 | ~200 | 2 |
| 包含 | ~150 | 2 |
| 其他短答案 | ~64 | 2-4 |

**示例记录**:
```
ID: geosr_topological_prompt_4929_4016
question: "..."
answer: "相离关系" (4字符)

ID: geosr_topological_prompt_4065_4778
question: "..."
answer: "相离" (2字符)
```

**规范要求**: 2-50字符（技术上符合，但可能影响模型学习）

**修复建议**:
```python
# 扩展过短答案
answer_expansion = {
    "相离": "两者在空间上相离，不存在包含关系",
    "相邻": "两者在空间上相邻，存在边界接触",
    "包含": "存在包含关系，一个实体位于另一个实体内部",
}
```

---

### 3.4 entity_to_token 部分映射（轻微）

**问题描述**: 14条记录的entity_to_token映射不完整，缺失部分实体的映射。

**缺失映射详情**:

| 记录ID | 缺失实体 | 现有映射 |
|--------|---------|---------|
| geosr_topological_prompt_1507_5582 | 内蒙古自治区 | 赤峰市 |
| geosr_topological_prompt_1539_4679 | 四川省 | 达州市 |
| geosr_topological_prompt_6211_6988 | 江苏省, 浙江省 | 杭州, 南京 |
| geosr_topological_prompt_1212_5995 | 江苏省 | 无锡 |
| geosr_topological_prompt_5686_7290 | 浙江省 | 宁波 |
| ... (共14条) | | |

**问题模式**: 省份全称（如"内蒙古自治区"、"四川省"）在问题中以简称出现（如"内蒙"、"四川"），导致映射失败。

**修复方案**: 运行增强版 `fix_entity_to_token_v2.py` 脚本，支持省份变体匹配。

---

### 3.5 难度分布偏差（轻微）

| 难度 | 实际数量 | 实际占比 | 目标占比 | 偏差 | 状态 |
|------|---------|---------|---------|------|------|
| easy | 3,094 | 26.5% | 30% | -3.5% | ✅ 可接受 |
| medium | 6,445 | 55.3% | 50% | +5.3% | ⚠️ 略高 |
| hard | 2,117 | 18.2% | 20% | -1.8% | ✅ 可接受 |

---

## 四、空间关系类型分布验证

| 类型 | 数量 | 占比 | 目标占比 | 状态 |
|------|------|------|---------|------|
| directional | 2,910 | 24.97% | 25% | ✅ |
| topological | 3,225 | 27.67% | 27.5% | ✅ |
| metric | 3,157 | 27.08% | 27.5% | ✅ |
| composite | 2,364 | 20.28% | 20% | ✅ |

**结论**: 空间关系类型分布符合规范要求。

---

## 五、数据质量汇总

### 5.1 通过的验证项

| 验证项 | 通过率 | 规范要求 | 状态 |
|--------|--------|---------|------|
| 必需字段完整性 | 100% | 100% | ✅ |
| reasoning_chain 5步结构 | 100% | 100% | ✅ |
| final_answer 与 answer 一致 | 100% | 100% | ✅ |
| entities ≥2个 | 100% | ≥2 | ✅ |
| entities 有 coords | 100% | 100% | ✅ |
| entity_to_token 完整性 | 99.88% | ≥95% | ✅ |
| 空间关系类型分布 | 合理 | 25/27.5/27.5/20 | ✅ |
| 字段顺序统一 | 100% | 100% | ✅ |
| 无 prompt_id/split | 100% | 0% | ✅ |

### 5.2 未通过的验证项

| 验证项 | 当前状态 | 规范要求 | 严重性 |
|--------|---------|---------|--------|
| 唯一ID | 449条重复 | 0重复 | 🔴 严重 |
| 拓扑子类型分布 | 严重不均衡 | 各20% | 🔴 严重 |
| answer长度 | 15.6%<5字符 | 2-50字符 | 🟡 中等 |

---

## 六、修复优先级与建议

### 优先级排序

| 优先级 | 问题 | 修复方案 | 预计工作量 | 影响 |
|--------|------|---------|-----------|------|
| **P0** | 重复ID | 重新生成ID或去重 | 1小时 | 阻断性问题 |
| **P1** | 拓扑子类型分布 | 补充生成数据 | 需调用API | 实验有效性 |
| **P2** | entity_to_token | 运行修复脚本 | 30分钟 | 数据完整性 |
| **P3** | answer过短 | 可选修复 | 2小时 | 模型学习 |

### 短期行动（立即执行）

1. **修复重复ID**
   ```bash
   python scripts/fix_duplicate_ids.py \
       --input GeoKD-SR/data/final/final_1_fixed.jsonl \
       --output GeoKD-SR/data/final/final_1_v2.jsonl
   ```

2. **修复entity_to_token缺失**
   ```bash
   python scripts/fix_entity_to_token_v2.py \
       --input GeoKD-SR/data/final/final_1_v2.jsonl \
       --output GeoKD-SR/data/final/final_1_v3.jsonl
   ```

### 中期行动（需要规划）

1. **补充拓扑子类型数据**
   - 需要调用GLM-5 API生成新数据
   - contains: +464条
   - overlap: +634条
   - 预计API调用成本: ~1100条 × 0.01元/条 ≈ 11元

### 长期行动（可选）

1. **扩展过短答案** - 提升模型学习效果
2. **建立自动化数据质量检查流程** - CI/CD集成

---

## 七、验证命令

修复后运行以下验证脚本：

```bash
python -c "
import json
from collections import Counter

with open('GeoKD-SR/data/final/final_1_v3.jsonl', 'r', encoding='utf-8') as f:
    records = [json.loads(l) for l in f if l.strip()]

print(f'总记录数: {len(records)}')

# 验证ID唯一性
ids = [r['id'] for r in records]
unique = len(set(ids))
print(f'唯一ID: {unique}/{len(ids)} ({unique/len(ids)*100:.1f}%)')

# 验证拓扑子类型分布
topo = [r for r in records if r.get('spatial_relation_type') == 'topological']
subtypes = Counter(r.get('topology_subtype') for r in topo)
print(f'\\n拓扑子类型分布:')
for s in ['within', 'contains', 'adjacent', 'disjoint', 'overlap']:
    c = subtypes.get(s, 0)
    print(f'  {s}: {c} ({c/len(topo)*100:.1f}%)')

# 验证entity_to_token
ett_complete = sum(1 for r in records
    if {e['name'] for e in r.get('entities', [])}
    .issubset(set(r.get('entity_to_token', {}).keys())))
print(f'\\nentity_to_token完整: {ett_complete}/{len(records)}')
"
```

---

## 八、附录

### A. 与 final_1_final.jsonl 对比

| 对比项 | final_1_final.jsonl | final_1_fixed.jsonl |
|--------|---------------------|---------------------|
| 记录数 | 11,656 | 11,656 |
| prompt_id字段 | 存在 | 已删除 ✅ |
| split字段 | 存在 | 已删除 ✅ |
| 字段顺序 | 不统一 | 已统一 ✅ |
| final_answer一致性 | 有不一致 | 100%一致 ✅ |

### B. 参考文档

1. `docs/GeoKD-SR-实验执行手册-V6.0/01-阶段1-数据准备/1.1-数据生成规范.md`
2. `docs/GeoKD-SR-实验设计方案-V5.2.md`
3. `GeoKD-SR/scripts/fix_entity_to_token_v2.py`
4. `GeoKD-SR/scripts/fix_final_1_data.py`

---

*报告生成: 2026-03-11*
*分析工具: Claude Code*
*报告版本: V1.0*
