# GLM-4.7 测试集评测模块

> 用于验证GeoKD-SR项目评测指标设计的有效性

## 快速开始

### 1. 环境准备

# 安装依赖
pip install zhipuai pyyaml

# 设置API密钥 (Windows)
set ZHIPUAI_API_KEY=your_api_key_here

# 或在PowerShell
$env:ZHIPUAI_API_KEY="your_api_key_here"
```

### 2. 运行测试
```bash
cd D:\30_keyan\GeoKD-SR\exp\exp0\glm

# 测试5条样本 (推荐先测试)
python scripts/evaluate_glm47.py --config config/glm47_eval_config.yaml --sample_size 5 --dataset splits

# 宣整评测 (两个数据集)
python scripts/evaluate_glm47.py --config config/glm47_eval_config.yaml --dataset both

# 仅评测含坐标版本
python scripts/evaluate_glm47.py --config config/glm47_eval_config.yaml --dataset split_coords
```

## 目录结构

```
glm/
├── PLAN.md              # 实施计划 (本文档)
├── README.md            # 模块说明
├── config/
│   └── glm47_eval_config.yaml   # 评测配置
├── scripts/
│   ├── glm47_client.py         # GLM-4.7 API客户端
│   └── evaluate_glm47.py       # 主评测脚本
├── prompts/
│   ├── inference_prompt.py    # 推理Prompt模板
│   └── eval_prompt.py          # 评估Prompt模板
├── results/                     # 输出结果目录
└── checkpoints/                # 断点续传目录
```

## 评测指标

| 类型 | 指标 | 说明 |
|------|------|------|
| 确定性 | Overall Accuracy | 整体准确率 |
| 确定性 | Format Valid Rate | 格式有效率 |
| 确定性 | BLEU-4 | 文本相似度 |
| 确定性 | ROUGE-L | 最长公共子序列 |
| 确定性 | Spatial F1 | 空间关键词F1 |

## 输出文件

评测完成后，结果保存在 `results/YYYYMMDD_HHMMSS/` 目录:

| 文件 | 说明 |
|------|------|
| `predictions_*.jsonl` | 模型预测结果 |
| `metrics_*.json` | 评测指标 |
| `report_*.md` | 评测报告 |
| `config.yaml` | 运行时配置 |

## 数据集说明

| 数据集 | 路径 | 样本数 | 特点 |
|--------|------|--------|------|
| split_coords | `data/split_coords/test.jsonl` | 1183 | question包含坐标信息 |
| splits | `data/splits/test.jsonl` | 1183 | question不含坐标，纯自然语言 |

## 注意事项

1. **API限流**: 请求间隔设为0.5秒，避免触发限流
2. **断点续传**: 每50条自动保存checkpoint，可中断后恢复
3. **费用估算**: 2366条请求约需2-3元 (按GLM-4.7定价计算)
4. **时间估算**: 完整评测约4-6小时

## 评测目的
1. 验证评测指标设计的有效性
2. 对比坐标信息对模型表现的影响
3. 为后续蒸馏实验建立基线

## 联系方式
如有问题，请查阅 PLAN.md 或联系项目负责人。
