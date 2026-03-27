# 工具模块

## data_loader.py

### `load_test_data(file_path, max_samples=None)`
加载测试数据集

**参数：**
- `file_path`: 数据文件路径（.jsonl格式）
- `max_samples`: 最大加载样本数，None表示全部

**返回：**
- List[Dict] 包含question和answer的数据列表

**示例：**
```python
from utils.data_loader import load_test_data

data = load_test_data("data/test.jsonl", max_samples=100)
```

---

## model_loader.py

### `load_model(config)`
加载模型（支持量化）

**参数：**
- `config`: 配置字典，包含model.name、model.path、model.quantization等

**返回：**
- (model, tokenizer) 模型和分词器元组

**支持的量化：**
- `None`: 全精度
- `"4bit"`: 4bit量化（bitsandbytes）
- `"8bit"`: 8bit量化（bitsandbytes）

**示例：**
```python
from utils.model_loader import load_model

config = {
    "name": "Qwen2.5-1.5B-Instruct",
    "path": "models/Qwen2.5-1.5B-Instruct",
    "quantization": None,
    "device": "cuda"
}
model, tokenizer = load_model(config)
```

---

## parser.py

### `extract_direction(text)`
从文本中提取方向关键词

**支持的方向：**
- 基本方向：东、南、西、北
- 组合方向：东北、东南、西北、西南

### `extract_topology(text)`
从文本中提取拓扑关键词

**支持的拓扑关系：**
- 邻接、包含、相交、相离

### `extract_distance(text)`
从文本中提取距离数值

**返回：**
- float或None：提取的距离值（公里）

### `match_answer(predicted, reference)`
答案匹配判断

**参数：**
- `predicted`: 模型预测答案
- `reference`: 标准答案

**返回：**
- bool: 是否匹配

**示例：**
```python
from utils.parser import extract_direction, extract_topology, extract_distance, match_answer

direction = extract_direction("答案在东北方向")
topology = extract_topology("两个区域相邻")
distance = extract_distance("距离约3.5公里")
is_match = match_answer(pred, ref)
```

---

## report.py

### `generate_report(results, output_path)`
生成评估报告

**参数：**
- `results`: 评测结果字典
- `output_path`: 报告输出路径

**报告格式：**
- Markdown格式，包含：
  - 实验配置
  - 指标汇总
  - 详细分析
  - 错误样例

**示例：**
```python
from utils.report import generate_report

results = {
    "accuracy": 0.75,
    "bertscore_f1": 0.80,
    ...
}
generate_report(results, "results/report.md")
```
