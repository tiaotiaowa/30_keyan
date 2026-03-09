# GeoKD-SR 30项审查维度详细说明

> **版本**: V2.1
> **适用数据集**: balanced_topology.jsonl (6,522条)
> **审查标准**: GeoKD-SR数据规范V2.1

---

## 目录

- [L1 格式审查 (4项)](#l1-格式审查-4项)
- [L2 逻辑审查 (8项)](#l2-逻辑审查-8项)
- [L3 分布审查 (8项)](#l3-分布审查-8项)
- [L4 语义审查 (10项)](#l4-语义审查-10项)
- [L5 提示词偏差审查 (5项)](#l5-提示词偏差审查-5项) ⭐新增

---

## L1 格式审查 (4项)

基础格式验证，确保数据可被正确解析。

### L1-1 JSON格式有效性

**检查项描述**: 验证每条记录是否为有效的JSON格式

**通过标准**:
- JSON解析成功，无语法错误
- 字符串编码正确（UTF-8）
- 无控制字符或非法字符

**检查方法**:
```python
import json
try:
    record = json.loads(line)
except json.JSONDecodeError as e:
    return False, str(e)
```

**失败处理建议**:
- 检查JSON语法（括号匹配、逗号位置）
- 确认字符串转义正确
- 验证UTF-8编码

---

### L1-2 必需字段完整性

**检查项描述**: 验证所有必需字段是否存在

**通过标准**:
| 字段名 | 类型 | 必需 |
|--------|------|------|
| id | str | ✅ |
| spatial_relation_type | str | ✅ |
| question | str | ✅ |
| answer | str | ✅ |
| reasoning_chain | list | ✅ |
| entities | list | ✅ |
| spatial_tokens | list | ✅ |
| difficulty | str | ✅ |
| entity_to_token | dict | ⚠️ |
| difficulty_score | float | ⚠️ |

**检查方法**:
```python
required_fields = ["id", "spatial_relation_type", "question",
                   "answer", "reasoning_chain", "entities",
                   "spatial_tokens", "difficulty"]
missing = [f for f in required_fields if f not in record]
```

**失败处理建议**:
- 缺失基础字段：从原始数据补充
- entity_to_token缺失：运行修复脚本
- difficulty_score缺失：根据difficulty映射

---

### L1-3 数据集划分标识

**检查项描述**: 验证split字段正确性（train/dev/test）

**通过标准**:
- split字段存在
- 取值为 train/dev/test 之一
- 数量比例约为 8:1:1

**检查方法**:
```python
assert record.get("split") in ["train", "dev", "test"]
```

**失败处理建议**:
- 根据ID范围分配split
- 确保分层采样一致

---

### L1-4 文件格式规范

**检查项描述**: 验证文件为JSONL格式（每行一个JSON）

**通过标准**:
- 文件扩展名为 .jsonl
- 每行一个完整的JSON对象
- 行尾无多余空白

**检查方法**:
```bash
wc -l data.jsonl
jq '.' data.jsonl | head -n 5
```

**失败处理建议**:
- 转换JSON为JSONL
- 删除空行
- 统一行结束符

---

## L2 逻辑审查 (8项)

验证字段类型、取值范围和结构逻辑。

### L2-1 spatial_relation_type枚举值

**检查项描述**: 验证空间关系类型是否为有效枚举值

**通过标准**:
- 取值必须为以下之一：
  - `directional` - 方向关系
  - `topological` - 拓扑关系
  - `metric` - 距离关系
  - `composite` - 复合关系

**检查方法**:
```python
VALID_TYPES = ["directional", "topological", "metric", "composite"]
assert record["spatial_relation_type"] in VALID_TYPES
```

**失败处理建议**:
- 检查拼写错误
- 根据问题内容重新分类
- 更新映射表

---

### L2-2 difficulty枚举值

**检查项描述**: 验证难度级别是否为有效枚举值

**通过标准**:
- 取值必须为以下之一：
  - `easy` - 简单
  - `medium` - 中等
  - `hard` - 困难

**检查方法**:
```python
assert record["difficulty"] in ["easy", "medium", "hard"]
```

**失败处理建议**:
- 根据实体数量和推理复杂度重新评估
- 参考difficulty_score映射

---

### L2-3 difficulty_score范围

**检查项描述**: 验证难度分数是否在有效范围

**通过标准**:
- 分数范围：1.0 ≤ score ≤ 5.0
- 与difficulty标签一致：
  - easy: 1.0-2.5
  - medium: 2.5-3.5
  - hard: 3.5-5.0

**检查方法**:
```python
score = record.get("difficulty_score")
assert 1.0 <= score <= 5.0
# 验证与difficulty一致性
difficulty = record["difficulty"]
if difficulty == "easy":
    assert 1.0 <= score <= 2.5
```

**失败处理建议**:
- 重新计算difficulty_score
- 使用默认映射规则：
  - easy → 1.5
  - medium → 2.75
  - hard → 4.0

---

### L2-4 reasoning_chain结构

**检查项描述**: 验证推理链是否为5步结构

**通过标准**:
- reasoning_chain长度为5
- 每步包含必需字段：
  - `step`: 步骤编号（1-5）
  - `name`: 步骤名称
  - `action`: 执行动作
  - `content`: 步骤内容

**检查方法**:
```python
chain = record["reasoning_chain"]
assert len(chain) == 5
for i, step in enumerate(chain, 1):
    assert step["step"] == i
    assert "name" in step
    assert "action" in step
    assert "content" in step
```

**失败处理建议**:
- 补全缺失步骤
- 修正步骤编号
- 标准化字段名

---

### L2-5 reasoning_chain步骤名称

**检查项描述**: 验证推理链步骤名称符合规范

**通过标准**:
| 步骤 | 期望名称 | 说明 |
|------|----------|------|
| 1 | entity_identification | 实体识别 |
| 2 | spatial_relation_extraction | 关系提取 |
| 3 | coordinate_retrieval | 坐标获取 |
| 4 | spatial_calculation | 空间计算 |
| 5 | answer_generation | 答案生成 |

**检查方法**:
```python
REASONING_STEPS = {
    1: "entity_identification",
    2: "spatial_relation_extraction",
    3: "coordinate_retrieval",
    4: "spatial_calculation",
    5: "answer_generation"
}
for step in chain:
    assert step["name"] == REASONING_STEPS[step["step"]]
```

**失败处理建议**:
- 更新为标准步骤名称
- 或更新配置允许自定义名称

---

### L2-6 entities字段结构

**检查项描述**: 验证实体列表结构完整性

**通过标准**:
- entities为列表，长度≥2
- 每个entity包含：
  - `name`: 实体名称（str）
  - `coords`: 坐标（list [lon, lat]）

**检查方法**:
```python
entities = record["entities"]
assert len(entities) >= 2
for entity in entities:
    assert "name" in entity
    assert "coords" in entity
    assert len(entity["coords"]) >= 2
```

**失败处理建议**:
- 补充缺失实体
- 添加coords字段
- 验证坐标格式

---

### L2-7 坐标范围有效性

**检查项描述**: 验证坐标是否在中国境内

**通过标准**:
- 经度范围：73.0° ≤ lon ≤ 135.0°
- 纬度范围：18.0° ≤ lat ≤ 54.0°

**检查方法**:
```python
COORD_RANGE = {"lon": (73.0, 135.0), "lat": (18.0, 54.0)}
lon, lat = entity["coords"][0], entity["coords"][1]
assert COORD_RANGE["lon"][0] <= lon <= COORD_RANGE["lon"][1]
assert COORD_RANGE["lat"][0] <= lat <= COORD_RANGE["lat"][1]
```

**失败处理建议**:
- 检查坐标顺序（lon, lat）
- 验证坐标系（WGS84）
- 修正明显错误的坐标

---

### L2-8 topology_subtype枚举值

**检查项描述**: 验证拓扑子类型（仅topological时检查）

**通过标准**:
- spatial_relation_type=topological时必须存在
- 取值为以下之一：
  - `within` - 在内部
  - `contains` - 包含
  - `adjacent` - 相邻
  - `disjoint` - 分离
  - `overlap` - 重叠

**检查方法**:
```python
if record["spatial_relation_type"] == "topological":
    assert "topology_subtype" in record
    assert record["topology_subtype"] in VALID_TOPOLOGY_SUBTYPES
```

**失败处理建议**:
- 补充topology_subtype字段
- 根据实体几何关系重新分类

---

## L3 分布审查 (8项)

验证数据分布是否符合设计目标。

### L3-1 空间关系类型分布

**检查项描述**: 验证四种空间关系类型的分布比例

**通过标准**:
| 类型 | 目标占比 | 允许偏差 |
|------|----------|----------|
| directional | 25.0% | ±2% |
| topological | 27.5% | ±2% |
| metric | 27.5% | ±2% |
| composite | 20.0% | ±2% |

**检查方法**:
```python
TARGETS = {
    "directional": 0.25,
    "topological": 0.275,
    "metric": 0.275,
    "composite": 0.20
}
for type_, target in TARGETS.items():
    actual = count[type_] / total
    assert abs(actual - target) <= 0.02
```

**失败处理建议**:
- 计算偏差量
- 过滤或补充数据
- 更新目标配置

---

### L3-2 难度分布

**检查项描述**: 验证三种难度级别的分布比例

**通过标准**:
| 难度 | 目标占比 | 允许偏差 |
|------|----------|----------|
| easy | 30.0% | ±2% |
| medium | 50.0% | ±2% |
| hard | 20.0% | ±2% |

**检查方法**:
```python
TARGETS = {"easy": 0.30, "medium": 0.50, "hard": 0.20}
```

**失败处理建议**:
- 重新分配难度标签
- 调整采样权重
- 验证打分标准

---

### L3-3 拓扑子类型平衡

**检查项描述**: 验证5种拓扑子类型的平衡性（仅topological数据）

**通过标准**:
- 5种子类型各占20%
- 允许偏差：±5%

**检查方法**:
```python
topo_data = [r for r in data if r["spatial_relation_type"] == "topological"]
for subtype in ["within", "contains", "adjacent", "disjoint", "overlap"]:
    count = sum(1 for r in topo_data if r["topology_subtype"] == subtype)
    ratio = count / len(topo_data)
    assert abs(ratio - 0.20) <= 0.05
```

**失败处理建议**:
- 使用balance_topology脚本
- 生成补充数据
- 过滤超额类型

---

### L3-4 数据集划分分布一致性

**检查项描述**: 验证train/dev/test中各类别分布一致

**通过标准**:
- 各划分中空间关系类型分布一致
- 各划分中难度分布一致
- 偏差 < 3%

**检查方法**:
```python
for split in ["train", "dev", "test"]:
    split_data = [r for r in data if r["split"] == split]
    # 计算各类型占比
    # 与整体分布比较
```

**失败处理建议**:
- 使用分层采样
- 重新分配split

---

### L3-5 实体数量分布

**检查项描述**: 验证每条数据的实体数量分布

**通过标准**:
- 实体数量范围：2-5个
- 平均值：约2.5个
- 2实体占比 > 60%

**检查方法**:
```python
entity_counts = [len(r["entities"]) for r in data]
assert min(entity_counts) >= 2
assert max(entity_counts) <= 5
assert sum(1 for c in entity_counts if c == 2) / len(data) > 0.6
```

**失败处理建议**:
- 过滤实体过多的记录
- 评估实体抽取准确性

---

### L3-6 question长度分布

**检查项描述**: 验证问题文本长度分布

**通过标准**:
- 长度范围：10-100字符
- 平均长度：约30字符
- 超长问题（>80字符）< 5%

**检查方法**:
```python
lengths = [len(r["question"]) for r in data]
assert all(10 <= l <= 100 for l in lengths)
```

**失败处理建议**:
- 截断过长问题
- 检查拼接错误

---

### L3-7 answer长度分布

**检查项描述**: 验证答案文本长度分布

**通过标准**:
- 长度范围：2-50字符
- 平均长度：约10字符
- 简短答案（2-10字符）> 80%

**检查方法**:
```python
lengths = [len(r["answer"]) for r in data]
assert all(2 <= l <= 50 for l in lengths)
```

**失败处理建议**:
- 简化冗长答案
- 提取关键信息

---

### L3-8 spatial_tokens数量分布

**检查项描述**: 验证空间token数量分布

**通过标准**:
- 数量范围：4-8个
- 平均值：约6个
- 5-7个占比 > 70%

**检查方法**:
```python
token_counts = [len(r["spatial_tokens"]) for r in data]
assert all(4 <= c <= 8 for c in token_counts)
```

**失败处理建议**:
- 补充缺失关键词
- 移除冗余token

---

## L4 语义审查 (10项)

验证答案逻辑、关键词和实体语义。

### L4-1 答案与问题一致性

**检查项描述**: 验证答案是否直接回答问题

**通过标准**:
- 答案类型匹配问题类型
- 是/否问题答案是 是/否
- 数值问题答案包含数字

**检查方法**:
```python
# 检查问题类型和答案匹配
if "是否" in question or "?" in question:
    assert answer in ["是", "否", "是的", "不是"]
```

**失败处理建议**:
- 人工审核答案相关性
- 修正不一致答案

---

### L4-2 答案与reasoning_chain一致性

**检查项描述**: 验证答案与推理链最终步骤一致

**通过标准**:
- reasoning_chain[4]["content"] 与 answer 语义一致
- 推导结果与答案匹配

**检查方法**:
```python
final_step = record["reasoning_chain"][-1]["content"]
assert final_step in record["answer"] or record["answer"] in final_step
```

**失败处理建议**:
- 更新answer与推理链一致
- 或修正推理链

---

### L4-3 spatial_tokens覆盖度

**检查项描述**: 验证空间关键词是否出现在question中

**通过标准**:
- 至少80%的spatial_tokens出现在question中
- 核心空间词（方向、拓扑、距离）100%覆盖

**检查方法**:
```python
tokens = record["spatial_tokens"]
question = record["question"]
covered = sum(1 for t in tokens if t in question)
coverage = covered / len(tokens)
assert coverage >= 0.8
```

**失败处理建议**:
- 更新spatial_tokens列表
- 移除question中不存在的token

---

### L4-4 空间关系关键词准确性

**检查项描述**: 验证空间关系类型对应的关键词准确

**通过标准**:
| 关系类型 | 核心关键词 | 准确率要求 |
|----------|------------|------------|
| directional | 东、西、南、北 | 95% |
| topological | 包含、相邻、分离 | 95% |
| metric | 公里、米、距离 | 95% |
| composite | 混合词 | 90% |

**检查方法**:
```python
RELATION_KEYWORDS = {
    "directional": ["东", "西", "南", "北", "方向"],
    "topological": ["包含", "相邻", "分离", "重叠"],
    "metric": ["公里", "米", "距离", "远"],
    "composite": []
}
```

**失败处理建议**:
- 检查spatial_relation_type分类
- 验证关键词抽取逻辑

---

### L4-5 拓扑子类型关键词准确性

**检查项描述**: 验证拓扑子类型对应关键词准确

**通过标准**:
| 子类型 | 核心关键词 | 当前准确率 |
|--------|------------|------------|
| Within | 在...内 | 100% |
| Adjacent | 相邻、接壤 | 97.7% |
| Overlap | 重叠、相交 | 需验证 |
| Disjoint | 不相邻、分离 | 需验证 |
| Contains | 包含 | 需验证 |

**检查方法**:
```python
SUBTYPE_KEYWORDS = {
    "within": ["在...内", "内部"],
    "adjacent": ["相邻", "接壤", "边界"],
    "overlap": ["重叠", "相交", "部分"],
    "disjoint": ["不相邻", "分离"],
    "contains": ["包含", "涵盖"]
}
```

**失败处理建议**:
- 更新关键词映射规则
- 修正错误分类

---

### L4-6 实体名称在问题中出现

**检查项描述**: 验证entities名称出现在question中

**通过标准**:
- 所有实体名称都在question中
- 或其别名/简称在question中

**检查方法**:
```python
entities = [e["name"] for e in record["entities"]]
question = record["question"]
for entity in entities:
    assert entity in question
```

**失败处理建议**:
- 更新实体名称匹配
- 添加别名映射

---

### L4-7 entity_to_token映射正确性

**检查项描述**: 验证实体到token的字符位置映射正确

**通过标准**:
- char_start和char_end在question长度内
- question[char_start:char_end] == entity.name
- 所有实体都有映射

**检查方法**:
```python
for entity, mapping in record["entity_to_token"].items():
    start, end = mapping["char_start"], mapping["char_end"]
    substring = record["question"][start:end]
    assert entity == substring
```

**失败处理建议**:
- 重新计算字符位置
- 修正索引偏移

---

### L4-8 距离计算准确性

**检查项描述**: 验证metric关系的距离计算正确

**通过标准**:
- 使用Haversine公式计算大圆距离
- 误差 < 10%（考虑单位换算）

**检查方法**:
```python
def haversine(lon1, lat1, lon2, lat2):
    # 计算两点间距离
    ...
# 与answer中的距离比较
```

**失败处理建议**:
- 重新计算距离
- 验证单位（km/m）

---

### L4-9 实体分布均衡性

**检查项描述**: 验证实体在数据中分布不过度集中

**通过标准**:
- 变异系数（CV）< 0.8
- 最频繁实体占比 < 5%
- 单一实体出现次数 < 总数据2%

**检查方法**:
```python
from collections import Counter
entity_counts = Counter()
for record in data:
    for entity in record["entities"]:
        entity_counts[entity["name"]] += 1
cv = stats.stdev(entity_counts.values()) / stats.mean(entity_counts.values())
assert cv < 0.8
```

**失败处理建议**:
- 过滤高频实体数据
- 生成新实体数据

---

### L4-10 推理链逻辑连贯性

**检查项描述**: 验证推理链步骤间逻辑连贯

**通过标准**:
- 每步输出作为下一步输入
- 步骤间因果关系明确
- 无逻辑跳跃

**检查方法**:
```python
# 检查步骤间的引用关系
for i in range(len(chain) - 1):
    # 验证chain[i]的输出在chain[i+1]中被引用
    ...
```

**失败处理建议**:
- 人工审核推理链
- 修正逻辑断点

---

## L5 提示词偏差审查 (5项)

验证提示词设计不会导致模型偏差或泄露任务类型。

### L5-1 推理链元数据泄露

**检查项描述**: 推理链中不应包含直接泄露任务类型的字段

**通过标准**:
- 无 `relation_type` 字段
- 无 `spatial_relation` 字段
- action 使用通用描述而非具体类型

**检查方法**:
```python
# 检查推理链泄露
forbidden_fields = ["relation_type", "spatial_relation"]
specific_actions = ["calculate_distance", "determine_topology",
                   "calculate_direction", "classify_relation"]

for step in reasoning_chain:
    assert not any(f in step for f in forbidden_fields)
    assert step.get("action") not in specific_actions
```

**失败处理建议**:
- 移除或重命名泄露字段
- 将具体action改为通用描述
- 使用 `scripts/sanitize_reasoning_chain.py` 自动处理

---

### L5-2 专业术语泄露

**检查项描述**: 问题中不应使用专业术语泄露任务类型

**通过标准**:
- topological类型不使用"拓扑关系"术语
- 避免专业领域特定词汇
- 使用日常语言表述

**检查方法**:
```python
TECHNICAL_TERMS = {
    "topological": ["拓扑关系", "从拓扑角度", "拓扑学", "拓扑结构"]
}

if spatial_relation_type == "topological":
    for term in TECHNICAL_TERMS["topological"]:
        assert term not in question
```

**失败处理建议**:
- 将"拓扑关系"替换为"空间关系"
- 使用 `scripts/rewrite_topological_prompts.py` 批量处理

---

### L5-3 引导词分布均衡

**检查项描述**: 引导词不应过度集中在某一类型

**通过标准**:
| 引导词类型 | 最大占比 |
|-----------|----------|
| 请问式 | ≤30% |
| 判断式 | ≤25% |
| 计算式 | ≤25% |
| 描述式 | ≤20% |

**检查方法**:
```python
patterns = {
    "polite_inquiry": r"^请问",
    "judgment_request": r"^请判断|^判断",
    "calculation_request": r"^请计算|^计算",
    "description_request": r"^请描述|^描述"
}
# 统计各类型占比
# 单一类型不应超过30%
```

**失败处理建议**:
- 增加多样化提示词模板
- 平衡引导词类型分布

---

### L5-4 答案格式暗示检查

**检查项描述**: 问题措辞不应过度暗示答案格式

**通过标准**:
- 是否类问题占比 ≤25%
- 数值暗示类占比 ≤25%
- 单一暗示模式 ≤30%

**检查方法**:
```python
FORMAT_HINTS = {
    "binary_hint": ["是否", "有没有", "存不存在"],
    "numeric_hint": ["多少公里", "距离是", "约为多少"],
    "direction_hint": ["什么方向", "哪个方位"]
}
# 统计各类暗示占比
```

**失败处理建议**:
- 减少是否类问题比例
- 增加开放式问题描述

---

### L5-5 信息给予模式检查

**检查项描述**: 检查问题中给予的信息模式是否合理

**通过标准**:
| 信息模式 | 目标占比 |
|---------|----------|
| 已知坐标 | ≤40% |
| 背景描述 | ≤30% |
| 直接提问 | ≥30% |

**检查方法**:
```python
INFO_PATTERNS = {
    "coordinate_given": r"已知.{0,10}坐标|位于北纬|经纬度是",
    "background_given": r"位于中国|位于.*省|地处",
    "direct_question": r"^[^，。]{0,20}(距离|方向|关系)"
}
# 统计各模式占比
```

**失败处理建议**:
- 增加直接提问式问题
- 减少已知坐标模式

---

## 附录

### A. 问题严重性定义

| 级别 | 标记 | 说明 | 处理要求 |
|------|------|------|----------|
| Critical | 🔴 | 阻塞性问题，数据不可用 | 必须修复 |
| Important | 🟡 | 重要质量问题，影响效果 | 建议修复 |
| Info | 🟢 | 参考信息，优化建议 | 可选处理 |

### B. 修复优先级

1. **P0**: L1 Critical问题（阻塞使用）
2. **P1**: L2 Critical + L2 Important问题
3. **P2**: L3 Important问题（影响分布）
4. **P3**: L4 Important问题（语义质量）
5. **P4**: Info级别问题（优化建议）

---

*最后更新: 2026-03-08*
