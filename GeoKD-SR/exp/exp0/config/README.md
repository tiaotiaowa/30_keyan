# 配置文件说明

## 配置文件列表
| 文件 | 模型 | 说明 |
|------|------|------|
| config_1.5b.yaml | Qwen2.5-1.5B | 学生模型配置 |
| config_7b.yaml | Qwen2.5-7B | 教师模型配置（全精度） |
| config_7b_4bit.yaml | Qwen2.5-7B | 教师模型配置（4bit量化） |

## 配置参数说明

### experiment
- `name`: 实验名称
- `description`: 实验描述
- `type`: 实验类型（baseline、finetuned等）

### model
- `name`: 模型名称
- `path`: 模型文件路径
- `quantization`: 量化配置（null、4bit、8bit）
- `device`: 运行设备（cuda、cpu）

### data
- `test_file`: 测试数据文件路径
- `max_samples`: 最大样本数（null表示全部）

### generation
- `temperature`: 生成温度
- `top_p`: 核采样参数
- `do_sample`: 是否采样
- `max_new_tokens`: 最大生成token数

### evaluation
- `metrics.deterministic`: 是否计算确定性指标
- `metrics.semantic`: 是否计算语义指标
- `metrics.llm_eval`: 是否使用LLM评测
- `llm_eval_config.model`: LLM评测模型
- `llm_eval_config.sample_size`: LLM评测样本数

### seeds
随机种子列表，用于多次运行取平均

### output
- `results_dir`: 结果保存目录
- `save_predictions`: 是否保存预测结果
- `save_metrics`: 是否保存评测指标
