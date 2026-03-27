# GeoKD-SR Qwen2.5-1.5B 两阶段评测方案

本目录包含 GeoKD-SR 项目的两阶段评测系统，用于评估 Qwen2.5-1.5B-Instruct 模型在地理空间推理任务上的表现。

## 环境要求

- Python 3.8+
- PyTorch 2.0+
- CUDA 11.x（GPU推理）
- 6GB+ 显存

## 目录结构

```
exp0/
├── stage1_generation/          # 第一阶段：答案生成
│   ├── config/
│   │   └── generation_config.yaml
│   ├── generate_answers.py     # 主生成脚本
│   ├── model_loader.py         # 模型加载工具
│   └── outputs/                # 生成的答案
│       └── predictions.jsonl
│
├── stage2_evaluation/          # 第二阶段：评测计算
│   ├── config/
│   │   └── eval_config.yaml
│   ├── evaluate.py             # 主评测脚本
│   ├── metrics/                # 指标模块
│   │   ├── __init__.py
│   │   ├── deterministic.py    # 6个确定性指标
│   │   └── semantic.py         # BERTScore语义指标
│   └── results/                # 评测结果
│       ├── metrics.json
│       └── report.md
│
└── README.md                   # 本文件
```

## 安装依赖

```bash
# 核心依赖
pip install torch transformers accelerate

# 评测依赖
pip install bert-score pyyaml tqdm

# 可选：使用国内镜像加速
pip install torch transformers accelerate -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 使用方法

### Stage 1: 答案生成

```bash
cd stage1_generation

# 使用默认配置
python generate_answers.py --config config/generation_config.yaml

# 或自定义输入输出
python generate_answers.py --config config/generation_config.yaml
```

**配置说明** (`config/generation_config.yaml`):

| 参数 | 说明 | 默认值 |
|------|------|--------|
| model.name | 模型名称 | Qwen/Qwen2.5-1.5B-Instruct |
| model.path | 本地模型路径 | ./models/Qwen2.5-1.5B-Instruct |
| model.use_local | 是否使用本地模型 | true |
| generation.max_new_tokens | 最大生成token数 | 256 |
| generation.temperature | 温度参数 | 0.1 |
| data.input_file | 测试数据路径 | ../../data/splits/test.jsonl |
| data.output_file | 输出文件路径 | ./outputs/predictions.jsonl |

### Stage 2: 评测计算

```bash
cd stage2_evaluation

# 使用默认配置
python evaluate.py --predictions ../stage1_generation/outputs/predictions.jsonl

# 自定义输出目录
python evaluate.py \
    --predictions ../stage1_generation/outputs/predictions.jsonl \
    --output ./results
```

## 评测指标

### 确定性指标（6个）

| 指标 | 说明 |
|------|------|
| Overall Accuracy | 整体准确率（支持方向/拓扑/距离/组合匹配） |
| Format Valid Rate | 格式有效率 |
| BLEU-4 | 文本相似度 |
| ROUGE-L | 最长公共子序列 |
| Spatial Precision | 空间关键词精确率 |
| Spatial F1 | 空间关键词F1分数 |

### 语义指标

| 指标 | 说明 |
|------|------|
| BERTScore Precision | 语义精确率 |
| BERTScore Recall | 语义召回率 |
| BERTScore F1 | 语义F1分数 |

### 分层分析

- **按空间类型**: directional, topological, metric, composite
- **按难度**: easy, medium, hard

## 输入输出格式

### 输入格式（test.jsonl）

```json
{
  "id": "geosr_directional_00513",
  "spatial_relation_type": "directional",
  "question": "鼓浪屿郑成功纪念馆位于福建省的什么方位？",
  "answer": "东南方向",
  "difficulty": "medium"
}
```

### Stage 1 输出（predictions.jsonl）

```json
{
  "id": "geosr_directional_00513",
  "question": "鼓浪屿郑成功纪念馆位于福建省的什么方位？",
  "reference": "东南方向",
  "prediction": "东南",
  "spatial_type": "directional",
  "difficulty": "medium"
}
```

### Stage 2 输出（metrics.json）

```json
{
  "metadata": {
    "timestamp": "2026-03-14T10:30:00",
    "total_samples": 1000
  },
  "deterministic": {
    "total": 1000,
    "accuracy": {"overall": 0.75},
    "format_valid_rate": 0.95,
    "bleu4": 0.65,
    "rouge_l": 0.70,
    "spatial_f1": {"precision": 0.80, "recall": 0.75, "f1": 0.77}
  },
  "semantic": {
    "bertscore_precision": 0.85,
    "bertscore_recall": 0.82,
    "bertscore_f1": 0.83
  }
}
```

## 常见问题

### 1. 显存不足

- 确保使用 `float16` 而非 `float32`
- 设置 `max_memory` 参数限制显存使用
- 如果仍然不足，考虑使用 `device_map="auto"` 的量化模式

### 2. 模型加载失败

- 检查模型路径是否正确
- 确保网络连接正常（首次下载需要）
- 尝试设置 `use_local: false` 使用在线模型

### 3. BERTScore 计算失败

- 安装 bert-score: `pip install bert-score`
- 确保有网络连接（首次下载 bert-base-chinese）
- 在配置中设置 `semantic.enabled: false` 禁用

## 扩展开发

### 添加新的评测指标

1. 在 `stage2_evaluation/metrics/` 下创建新文件
2. 继承基础指标类
3. 在 `evaluate.py` 中导入并调用

### 修改答案生成逻辑

1. 编辑 `stage1_generation/generate_answers.py`
2. 修改 `format_prompt` 方法调整prompt格式
3. 修改 `generate_answer` 方法调整生成逻辑

## 版本历史

- v1.0 (2026-03-14): 初始版本，支持两阶段评测
