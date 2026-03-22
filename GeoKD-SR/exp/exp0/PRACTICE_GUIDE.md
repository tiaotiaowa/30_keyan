# GeoKD-SR 模型评测流程实践指导文档

> 本文档记录了已验证的 Qwen2.5-1.5B 模型加载与评测流程，供复用参考。

---

## 目录

1. [环境配置](#1-环境配置)
2. [模型准备](#2-模型准备)
3. [数据准备](#3-数据准备)
4. [运行评测](#4-运行评测)
5. [结果解读](#5-结果解读)
6. [常见问题](#6-常见问题)

---

## 1. 环境配置

### 1.1 Conda 环境创建

```bash
# 创建并激活环境
conda create -n llamafactory python=3.10 -y
conda activate llamafactory
```

### 1.2 CUDA 检查

```bash
# 检查CUDA版本
nvidia-smi
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}')"
```

**已验证环境**: PyTorch 2.5.1 + CUDA 12.4

### 1.3 核心依赖安装

```bash
# 安装PyTorch（CUDA 12.4版本）
pip install torch==2.5.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 安装Transformers及相关库
pip install transformers>=4.40.0
pip install accelerate>=0.27.0
pip install bitsandbytes>=0.43.0  # 量化支持
pip install sentencepiece
pip install protobuf

# 安装评测依赖
pip install bert-score  # BERTScore计算
pip install nltk rouge-score  # 文本指标
pip install numpy pyyaml
```

### 1.4 验证安装

```bash
python -c "
import torch
import transformers
print(f'PyTorch: {torch.__version__}')
print(f'Transformers: {transformers.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')
"
```

---

## 2. 模型准备

### 2.1 模型路径配置

| 模型 | 路径 | 显存占用 |
|------|------|----------|
| Qwen2.5-1.5B-Instruct | `D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct` | ~2.88GB |
| Qwen2.5-7B-Instruct | `D:/30_keyan/GeoKD-SR/models/Qwen2.5-7B-Instruct` | ~14GB |
| Qwen2.5-7B-Instruct (4bit) | 同上（量化加载） | ~4GB |

### 2.2 显存要求

```python
# 快速检查显存
import torch
print(f"可用显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
```

**推荐配置**:
- 1.5B模型: 4GB+ 显存
- 7B模型（全精度）: 16GB+ 显存
- 7B模型（4bit量化）: 8GB+ 显存

### 2.3 配置文件说明

配置文件位于 `config/` 目录:

```yaml
# config/config_1.5b.yaml 示例
experiment:
  name: "exp0a_baseline_1.5b"
  description: "Qwen2.5-1.5B-Instruct 原始模型基线评估"
  type: "baseline"

model:
  name: "Qwen2.5-1.5B-Instruct"
  path: "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct"
  quantization: null  # 可选: "4bit", "8bit", null
  device: "cuda"

data:
  test_file: "D:/30_keyan/GeoKD-SR/data/final/final_1_v5.jsonl"
  max_samples: null  # null表示加载全部

generation:
  temperature: 0.1
  top_p: 0.9
  do_sample: true
  max_new_tokens: 512

evaluation:
  metrics:
    deterministic: true
    semantic: true
    llm_eval: false

output:
  results_dir: "results/baseline_1.5b"
  save_predictions: true
  save_metrics: true
```

---

## 3. 数据准备

### 3.1 数据格式要求

测试数据采用 JSONL 格式，每行一个 JSON 对象:

```json
{
  "id": "unique_id",
  "question": "地理空间推理问题文本",
  "answer": "标准答案文本",
  "spatial_relation_type": "方向|拓扑|距离|组合",
  "difficulty": "easy|medium|hard"
}
```

### 3.2 必需字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识符 |
| `question` | string | 输入问题 |
| `answer` | string | 标准答案 |
| `spatial_relation_type` | string | 空间关系类型（用于分层分析） |
| `difficulty` | string | 难度等级（用于分层分析） |

### 3.3 数据验证

```python
from utils.data_loader import load_test_data, validate_data_format

# 加载数据
data = load_test_data("D:/30_keyan/GeoKD-SR/data/final/final_1_v5.jsonl")

# 验证格式
if validate_data_format(data):
    print(f"数据格式正确，共 {len(data)} 条样本")
else:
    print("数据格式错误")
```

---

## 4. 运行评测

### 4.1 单次评测

```bash
# 进入exp0目录
cd D:/30_keyan/GeoKD-SR/exp/exp0

# 运行1.5B模型评测（seed=42）
python evaluate.py --config config/config_1.5b.yaml --seed 42
```

### 4.2 指定种子评测

```bash
# 使用不同随机种子
python evaluate.py --config config/config_1.5b.yaml --seed 123
python evaluate.py --config config/config_1.5b.yaml --seed 456
```

### 4.3 批量评测

```bash
# 评测全部模型（3模型 × 5种子 = 15次评测）
python batch_evaluate.py --all

# 评测指定模型
python batch_evaluate.py --model 1.5b

# 评测指定模型和种子
python batch_evaluate.py --model 7b --seed 42
```

### 4.4 评测参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config` | 配置文件路径 | 必需 |
| `--seed` | 随机种子 | 42 |
| `--all` | 运行全部评测 | - |
| `--model` | 指定模型 (1.5b/7b/7b_4bit) | - |

### 4.5 输出文件

评测完成后，结果保存在 `results/` 目录:

```
results/baseline_1.5b/
├── seed_42/
│   ├── metrics.json      # 指标结果
│   ├── predictions.jsonl # 预测详情
│   └── report.md         # Markdown报告
├── seed_123/
│   └── ...
└── ...
```

---

## 5. 结果解读

### 5.1 确定性指标

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| **Overall Accuracy** | 整体准确率 | 综合方向、拓扑、距离匹配准确率 |
| **Format Valid Rate** | 格式有效率 | 有效回答占比 |
| **BLEU-4** | 文本相似度 | 4-gram匹配度 |
| **ROUGE-L** | 最长公共子序列 | 基于LCS的F1分数 |
| **Perplexity** | 困惑度 | 语言模型困惑度（越低越好） |
| **Spatial F1** | 空间关键词F1 | 空间词汇的精确率和召回率 |

### 5.2 语义指标

| 指标 | 说明 | 基础模型 |
|------|------|----------|
| **BERTScore Precision** | 语义精确率 | bert-base-chinese |
| **BERTScore Recall** | 语义召回率 | bert-base-chinese |
| **BERTScore F1** | 语义F1分数 | bert-base-chinese |

### 5.3 分层分析

评测结果包含按空间类型和难度的分层分析:

```json
{
  "stratified": {
    "by_spatial_type": {
      "方向": {"accuracy": 0.85, "count": 100},
      "拓扑": {"accuracy": 0.78, "count": 100},
      "距离": {"accuracy": 0.65, "count": 80},
      "组合": {"accuracy": 0.55, "count": 50}
    },
    "by_difficulty": {
      "easy": {"accuracy": 0.90, "count": 100},
      "medium": {"accuracy": 0.75, "count": 150},
      "hard": {"accuracy": 0.55, "count": 80}
    }
  }
}
```

### 5.4 结果示例

```json
{
  "meta": {
    "experiment": "exp0a_baseline_1.5b",
    "model": "Qwen2.5-1.5B-Instruct",
    "seed": 42,
    "test_samples": 330
  },
  "deterministic": {
    "overall_accuracy": 0.72,
    "format_valid_rate": 0.95,
    "bleu_4": 0.35,
    "rouge_l": 0.48,
    "spatial_f1": 0.68
  },
  "semantic": {
    "bertscore_precision": 0.82,
    "bertscore_recall": 0.79,
    "bertscore_f1": 0.80
  }
}
```

---

## 6. 常见问题

### 6.1 CUDA 内存不足

**问题**: `CUDA out of memory`

**解决方案**:
1. 使用量化加载（4bit或8bit）
2. 减小 `max_samples` 限制
3. 减小 `max_new_tokens`

```yaml
# config_7b_4bit.yaml
model:
  quantization: "4bit"  # 启用4bit量化
```

### 6.2 模型加载失败

**问题**: `OSError: Can't load tokenizer`

**解决方案**:
1. 检查模型路径是否正确
2. 确保模型文件完整
3. 添加 `trust_remote_code=True`

```python
tokenizer = AutoTokenizer.from_pretrained(
    model_path,
    trust_remote_code=True
)
```

### 6.3 BERTScore 计算失败

**问题**: `ImportError: cannot import name 'bert_score'`

**解决方案**:
```bash
pip install bert-score
```

### 6.4 数据格式错误

**问题**: `KeyError: 'question'`

**解决方案**:
1. 检查数据文件是否为 JSONL 格式
2. 验证必需字段是否存在
3. 使用 `validate_data_format()` 函数检查

### 6.5 中文乱码

**问题**: 输出中文乱码

**解决方案**:
```python
# 确保文件编码为UTF-8
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
```

### 6.6 多GPU问题

**问题**: 模型未正确分配到多GPU

**解决方案**:
```yaml
# 配置文件中使用auto
model:
  device: "cuda"  # 自动使用device_map="auto"
```

---

## 附录

### A. 目录结构

```
exp0/
├── config/                    # 配置文件
│   ├── config_1.5b.yaml       # 1.5B模型配置
│   ├── config_7b.yaml         # 7B模型配置
│   └── config_7b_4bit.yaml    # 7B模型4bit量化配置
├── metrics/                   # 指标模块
│   ├── __init__.py
│   ├── deterministic.py       # 确定性指标
│   └── semantic.py            # 语义指标
├── utils/                     # 工具模块
│   ├── __init__.py
│   ├── data_loader.py         # 数据加载
│   ├── model_loader.py        # 模型加载
│   ├── parser.py              # 参数解析
│   └── report.py              # 报告生成
├── results/                   # 评测结果
├── evaluate.py                # 单次评测脚本
├── batch_evaluate.py          # 批量评测脚本
├── README.md                  # 实验说明
└── PRACTICE_GUIDE.md          # 本文档
```

### B. 相关文档

- [9实验统一评测指标设计方案](./GeoKD-SR-9实验统一评测指标设计方案_20260313.md)
- [指标模块说明](./metrics/README.md)
- [工具模块说明](./utils/README.md)

### C. 版本历史

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-03-14 | v1.0 | 初始版本 |

---

**文档维护者**: GeoKD-SR 项目组
**最后更新**: 2026-03-14
