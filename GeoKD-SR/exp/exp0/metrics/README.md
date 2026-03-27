# 评测指标模块

## 确定性指标 (deterministic.py)

| 函数 | 说明 |
|------|------|
| `calculate_overall_accuracy` | 整体准确率 - 预测答案与标准答案完全匹配的比例 |
| `calculate_format_valid_rate` | 格式有效率 - 输出符合JSON格式的比例 |
| `calculate_bleu_4` | BLEU-4 分数 - 4-gram精确度 |
| `calculate_rouge_l` | ROUGE-L 分数 - 最长公共子序列F1值 |
| `calculate_perplexity` | 困惑度 - 模型输出的不确定性度量 |
| `calculate_spatial_f1` | 空间关键词F1 - 方向/拓扑/距离关键词的F1分数 |

## 语义指标 (semantic.py)

| 函数 | 说明 |
|------|------|
| `calculate_bertscore` | BERTScore - 基于BERT的语义相似度（P/R/F1） |

## 指标计算示例

```python
from metrics.deterministic import calculate_overall_accuracy, calculate_spatial_f1
from metrics.semantic import calculate_bertscore

# 确定性指标
accuracy = calculate_overall_accuracy(predictions, references)
spatial_f1 = calculate_spatial_f1(predictions, references)

# 语义指标
bertscore = calculate_bertscore(predictions, references)
```

## 输出格式

指标结果将保存为JSON格式：
```json
{
  "overall_accuracy": 0.75,
  "format_valid_rate": 0.95,
  "bleu_4": 0.42,
  "rouge_l": 0.58,
  "perplexity": 1.23,
  "spatial_f1": 0.68,
  "bertscore_precision": 0.82,
  "bertscore_recall": 0.79,
  "bertscore_f1": 0.80
}
```
