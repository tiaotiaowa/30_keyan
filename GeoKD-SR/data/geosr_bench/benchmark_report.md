# GeoSR-Bench 评测基准生成报告

## 基本信息

- **评测基准名称**: GeoSR-Bench
- **版本**: v1.0
- **生成时间**: 2026-03-01
- **总题目数**: 1000题
- **文件大小**: 约500KB

## 题目分布

### 按维度分布

| 维度 | 题目数量 | 占比 |
|------|---------|------|
| D1 - 空间关系理解 | 400 | 40% |
| D2 - 空间推理能力 | 400 | 40% |
| D3 - 地理知识融合 | 200 | 20% |

### D1 - 空间关系理解 (400题)

| 题型 | 数量 | 描述 |
|------|------|------|
| 方向关系 | 150 | 选择题，4选1，测试8方向判断能力 |
| 拓扑关系 | 150 | 判断题，真/假，测试包含和流经关系 |
| 度量关系 | 100 | 填空题，距离计算，容差±50公里 |

### D2 - 空间推理能力 (400题)

| 题型 | 数量 | 描述 |
|------|------|------|
| 单步推理 | 100 | 选择题，比较距离关系 |
| 多跳推理 | 200 | 推理题，需展示推理步骤 |
| 约束求解 | 100 | 选择题，根据多个约束条件确定城市 |

### D3 - 地理知识融合 (200题)

| 题型 | 数量 | 描述 |
|------|------|------|
| 实体识别 | 50 | 选择题，城市类型、地理实体类型、位置识别 |
| 常识应用 | 100 | 选择题/判断题，基于纬度和人口的常识推理 |
| 情境理解 | 50 | 推理题，结合实际旅行情境 |

## 题型统计

| 题型 | 数量 | 占比 |
|------|------|------|
| multiple_choice (选择题) | 500 | 50% |
| true_false (判断题) | 200 | 20% |
| reasoning (推理题) | 200 | 20% |
| fill_blank (填空题) | 100 | 10% |

## 数据来源

评测基准基于以下地理实体数据库生成：

- **城市**: 35个（包括直辖市、省会、主要地级市）
- **省份**: 32个（包括省、自治区、直辖市）
- **河流**: 8条（长江、黄河、珠江、淮河、海河、辽河、松花江、雅鲁藏布江）
- **山脉**: 10座（喜马拉雅山脉、昆仑山脉、天山山脉、秦岭等）
- **地标**: 20个（故宫、长城、西湖、黄山等著名景点）

## 质量保证

### ID唯一性
✓ 所有1000个题目ID均唯一，无重复

### 答案正确性
- 方向计算：使用精确的方位角公式
- 距离计算：使用Haversine球面距离公式
- 拓扑关系：基于权威地理数据

### 题目多样性
- 随机选择实体对，确保覆盖不同地区
- 干扰项合理且具有迷惑性
- 题目类型和难度分布均衡

## 文件结构

```
data/geosr_bench/
├── geosr_bench_v1.json       # 主评测基准文件
└── benchmark_report.md       # 本报告文件
```

## 题目示例

### 选择题示例
```json
{
  "id": "D1_DIR_001",
  "dimension": "D1_空间关系理解",
  "task_type": "multiple_choice",
  "question": "武汉在深圳的什么方向？",
  "options": ["A. 西南", "B. 东北", "C. 南", "D. 东"],
  "answer": "D",
  "reasoning": "武汉位于深圳的东方向。"
}
```

### 判断题示例
```json
{
  "id": "D1_TOP_001",
  "dimension": "D1_空间关系理解",
  "task_type": "true_false",
  "question": "长江流经湖北省。",
  "answer": true,
  "reasoning": "长江流经的省份包括：青海、西藏、四川、云南、重庆、湖北、湖南、江西、安徽、江苏和上海。"
}
```

### 填空题示例
```json
{
  "id": "D1_MET_001",
  "dimension": "D1_空间关系理解",
  "task_type": "fill_blank",
  "question": "从郑州到济南的直线距离大约是多少公里？（请填写整数）",
  "answer": 380,
  "tolerance": 50,
  "reasoning": "使用球面距离公式计算，郑州到济南的直线距离约为378.4公里。"
}
```

### 推理题示例
```json
{
  "id": "D2_MULTI_001",
  "dimension": "D2_空间推理能力",
  "task_type": "reasoning",
  "question": "说明为什么长沙与长江有关联？",
  "answer": "长沙是湖南省的省会，而长江流经湖南省。",
  "reasoning_steps": [
    "1. 长江流经湖南省",
    "2. 湖南省的省会是长沙",
    "3. 因此长沙位于长江流经的区域"
  ]
}
```

## 使用方法

### 加载评测基准
```python
import json

with open('data/geosr_bench/geosr_bench_v1.json', 'r', encoding='utf-8') as f:
    benchmark = json.load(f)

questions = benchmark['questions']
```

### 按维度筛选
```python
d1_questions = [q for q in questions if q['dimension'] == 'D1_空间关系理解']
d2_questions = [q for q in questions if q['dimension'] == 'D2_空间推理能力']
d3_questions = [q for q in questions if q['dimension'] == 'D3_地理知识融合']
```

### 按题型筛选
```python
multiple_choice = [q for q in questions if q['task_type'] == 'multiple_choice']
true_false = [q for q in questions if q['task_type'] == 'true_false']
reasoning = [q for q in questions if q['task_type'] == 'reasoning']
fill_blank = [q for q in questions if q['task_type'] == 'fill_blank']
```

## 评测指标建议

### 准确率计算
- 选择题：完全匹配
- 判断题：布尔值匹配
- 填空题：在容差范围内
- 推理题：可分步骤评分或整体评分

### 分维度评分
计算每个维度的准确率：
- D1准确率 = D1正确题数 / D1总题数
- D2准确率 = D2正确题数 / D2总题数
- D3准确率 = D3正确题数 / D3总题数

### 综合评分
综合得分 = (D1准确率 + D2准确率 + D3准确率) / 3

## 更新日志

### v1.0 (2026-03-01)
- 初始版本发布
- 包含1000道评测题目
- 覆盖三个维度、四种题型

## 贡献者

- GeoSR-Bench生成器: experiments/generate_benchmark.py
- 地理实体数据库: data/entity_database.json

---

*本报告由GeoSR-Bench生成器自动生成*
