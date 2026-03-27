# GeoKD-SR 项目记忆文档

---

## 2026-03-21 Qwen2.5-1.5B SFT 训练数据格式修复

### 问题描述
SFT 训练代码报错：
```
AttributeError: 'GeoSRDataProcessor' object has no attribute 'column_names'
```

### 根本原因
`GeoSRDataProcessor` 继承自 `torch.utils.data.Dataset`，但 TRL 的 `SFTTrainer` 期望 Hugging Face `datasets.Dataset` 格式，后者具有 `column_names` 属性。

### 修复方案
在 `data_processor.py` 中添加 HF Dataset 转换方法。

### 修改内容

#### 1. `src/data_processor.py`
- 添加导入: `from datasets import Dataset as HFDataset`
- 新增 `to_hf_dataset()` 方法 - 将内部数据转换为 messages 格式的 HF Dataset
- 新增 `create_hf_dataset()` 静态方法 - 直接创建 HF Dataset（推荐方式）

#### 2. `scripts/train.py`
- 修改数据加载部分，使用 `GeoSRDataProcessor.create_hf_dataset()` 静态方法
- 添加数据集列名日志输出验证

### 验证结果
- ✅ Dry-run 模式通过
- ✅ HF Dataset 类型正确: `<class 'datasets.arrow_dataset.Dataset'>`
- ✅ 数据集列名: `['messages']`
- ✅ 训练样本数: 9463
- ✅ 验证样本数: 1124

### 代码示例
```python
# 使用新的静态方法创建 HF Dataset
train_dataset = GeoSRDataProcessor.create_hf_dataset(
    data_path=data_dir,
    tokenizer=trainer.tokenizer,
    max_length=config.optimization.max_length,
    system_prompt=config.data.system_prompt,
    data_version=data_version,
    split="train"
)
```

### 数据格式
转换后的 HF Dataset 包含 `messages` 列，格式如下：
```python
{
    'messages': [
        {'content': '系统提示词', 'role': 'system'},
        {'content': '用户问题', 'role': 'user'},
        {'content': '模型回答', 'role': 'assistant'}
    ]
}
```

---

## 2026-03-21 创建 GeoSRSFTTrainer 训练器模块

### 任务概述
在 `D:\30_keyan\GeoKD-SR\exp\exp0\qwen-1.5B-sft\src\trainer.py` 创建训练器模块，用于 Qwen2.5-1.5B 模型的监督微调。

### 实现功能

1. **GeoSRSFTTrainer 类** - 封装完整训练逻辑
   - `__init__(model_path, config)` - 初始化训练器
   - `setup_model_and_tokenizer()` - 加载模型和 tokenizer
   - `setup_lora()` - 配置 LoRA 参数高效微调
   - `train(train_dataset, eval_dataset)` - 执行训练
   - `save_model(output_path)` - 保存模型

2. **核心特性**
   - 使用 TRL 的 SFTTrainer 进行监督微调
   - 使用 PEFT 的 LoRA 进行参数高效微调
   - 支持配置化的训练参数（从 Config 对象读取）
   - 支持 gradient_checkpointing
   - 支持 fp16/bf16 混合精度训练（自动检测 GPU 支持）
   - 支持 Trackio 日志记录
   - 自动保存 checkpoints

3. **辅助函数**
   - `create_trainer()` - 便捷函数，创建并初始化训练器

### 技术细节

- **LoRA 配置**: 从 Config 对象读取 r, alpha, dropout, target_modules
- **混合精度**: 自动检测 BF16 支持，不支持时回退到 FP16
- **保存策略**: 支持按 epoch 或 steps 保存，可配置保存数量限制
- **日志**: 使用 logging 模块，详细记录训练过程
- **参数统计**: 自动计算并打印可训练参数占比

### 文件位置
- `GeoKD-SR/exp/exp0/qwen-1.5B-sft/src/trainer.py`

### 依赖库
- transformers
- peft
- trl
- torch
- datasets

---

## 2026-03-21 创建 Qwen2.5-1.5B SFT 评测脚本

### 任务概述
为 Qwen2.5-1.5B LoRA 微调实验创建评测脚本 `evaluate.py`。

### 执行内容

**创建文件**: `exp/exp0/qwen-1.5B-sft/scripts/evaluate.py`

**功能特性**:
1. **命令行参数支持**:
   - `--checkpoint`: 模型 checkpoint 路径
   - `--test-file`: 测试数据路径
   - `--output`: 输出目录
   - `--batch-size`: 批次大小（默认 8）
   - `--max-new-tokens`: 最大生成 token 数（默认 256）
   - `--base-model`: 基础模型路径
   - `--temperature`, `--top-p`, `--do-sample`: 生成参数
   - `--system-prompt`: 系统提示词

2. **LoRA 模型加载**:
   - 支持加载 PeftModel 微调后的模型
   - 支持自动合并 LoRA 权重到基础模型
   - 兼容 CPU/GPU 设备

3. **批量推理**:
   - 使用 Qwen2.5 的 chat template 格式
   - 支持批量生成提高效率

4. **评测指标**（复用 `exp/exp0/metrics/deterministic.py`）:
   - Overall Accuracy（整体准确率）
   - Format Valid Rate（格式有效率）
   - BLEU-4（文本相似度）
   - ROUGE-L（最长公共子序列）
   - Spatial F1（空间关键词 F1）

5. **分层统计**:
   - 按空间类型分层（directional, topological, metric, composite）
   - 按难度分层（easy, medium, hard）

6. **输出文件**:
   - `predictions.jsonl`: 预测结果
   - `metrics.json`: 指标结果

### 使用示例
```bash
python evaluate.py \
    --checkpoint ./checkpoints/checkpoint-500 \
    --test-file ../../data/splits/test.jsonl \
    --output ./results \
    --batch-size 8 \
    --max-new-tokens 256
```

### 输出示例
```
【整体指标】
  样本数量: 1183
  Overall Accuracy: 0.2316
  Format Valid Rate: 0.9234
  BLEU-4: 0.1823
  ROUGE-L: 0.3456
  Spatial F1: 0.4521

【按空间类型分层】
  类型           数量     准确率     BLEU-4    ROUGE-L   Spatial F1
  directional    457   0.4349    0.2345    0.4123      0.5123
  ...
```

---

## 2026-03-19 Qwen2.5-1.5B 坐标增强数据集答案生成完成

### 任务概述
使用 Qwen2.5-1.5B 本地模型对带坐标的测试数据进行答案生成。

### 执行内容
1. **创建配置文件**: `exp/exp0/exp0/stage1_generation/config/generation_config_coords.yaml`
   - 关键改动: Prompt 模板增加了坐标说明 "地理实体后的括号里附有相应坐标，格式为(经度,纬度)"

2. **运行环境**: conda llamafactory

3. **执行命令**:
   ```bash
   conda run -n llamafactory python generate_answers.py --config config/generation_config_coords.yaml
   ```

### 执行结果
- **输入数据**: `data/split_coords/test.jsonl` (1183条)
- **输出文件**: `exp/exp0/exp0/stage1_generation/outputs/predictions_qwen_coords.jsonl` (1183条)
- **执行时间**: 约16分钟32秒
- **模型**: Qwen2.5-1.5B-Instruct (本地路径)

### 输出格式示例
```json
{
  "id": "geosr_directional_00513",
  "question": "鼓浪屿郑成功纪念馆(118.0694,24.4511)位于福建省(117.5,26.5)的什么方位？",
  "reference": "东南方向",
  "prediction": "东南方向",
  "spatial_type": "directional",
  "difficulty": "medium"
}
```

### 观察
- 模型对坐标信息的利用程度有限
- 部分预测存在格式不规范问题（如包含列表格式）
- 方向问题准确率相对较高
- 距离问题数值偏差较大

### 后续任务
- ~~对预测结果进行评估~~ ✅ 已完成
- ~~分析模型对坐标信息的利用情况~~ ✅ 已完成
- ~~对比有无坐标提示的性能差异~~ ✅ 已完成

---

## 2026-03-21 Qwen2.5-1.5B SFT 训练系统实施完成

### 任务概述
实现 Qwen2.5-1.5B-Instruct 的 LoRA 微调训练系统，用于 GeoKD-SR Exp1 Direct-SFT 基线实验。

### 项目结构
```
d:\30_keyan\GeoKD-SR\exp\exp0\qwen-1.5B-sft\
├── configs/
│   ├── train_6gb.yaml           # Windows 6GB配置 (batch=1, grad_accum=128)
│   ├── train_24gb.yaml          # 阿里云 24GB配置 (batch=8, grad_accum=16)
│   └── eval.yaml                # 评测配置
├── scripts/
│   ├── train.py                 # 主训练脚本
│   ├── evaluate.py              # 评测脚本
│   ├── run_windows.bat          # Windows启动脚本
│   └── run_aliyun.sh            # 阿里云启动脚本
├── src/
│   ├── __init__.py
│   ├── config.py                # 配置加载模块
│   ├── data_processor.py        # 数据处理（ChatML格式）
│   ├── trainer.py               # 训练器封装
│   └── utils.py                 # 工具函数
├── outputs/                     # 训练输出
├── logs/                        # 训练日志
├── checkpoints/                 # 模型检查点
└── README.md                    # 使用说明
```

### 关键配置

#### 6GB 配置 (train_6gb.yaml)
- batch_size: 1
- gradient_accumulation_steps: 128
- effective_batch_size: 128
- learning_rate: 5e-5
- max_length: 1024
- mixed_precision: fp16
- LoRA: r=8, alpha=16

#### 24GB 配置 (train_24gb.yaml)
- batch_size: 8
- gradient_accumulation_steps: 16
- effective_batch_size: 128
- learning_rate: 5e-5
- max_length: 2048
- mixed_precision: bf16
- LoRA: r=16, alpha=32

### 核心模块

1. **config.py** - 配置加载
   - Config, LoRAConfig, ModelConfig, TrainingConfig 等数据类
   - from_yaml() 方法加载 YAML 配置
   - get_dataset_path() 获取数据路径

2. **data_processor.py** - 数据处理
   - ChatMLConverter: 将数据转换为 ChatML 格式
   - GeoSRDataProcessor: 加载和处理 GeoKD-SR 数据集
   - Label 构造: system/user 段 → -100, assistant 段 → token_ids

3. **trainer.py** - 训练器
   - GeoSRSFTTrainer 类封装 TRL SFTTrainer
   - 支持 LoRA 微调
   - 支持 Gradient Checkpointing
   - 支持 FP16/BF16 混合精度
   - 支持 Trackio 日志记录

4. **utils.py** - 工具函数
   - setup_seed(): 设置随机种子
   - setup_logging(): 配置日志
   - get_device_info(): 获取设备信息
   - format_time(): 时间格式化
   - AverageMeter, Timer 类

### 验证结果

Dry-run 测试通过:
- 配置文件加载正常
- 训练数据: 9463 样本
- 验证数据: 1124 样本
- 模型文件验证通过 (config.json, tokenizer.json, tokenizer_config.json)

### 使用方法

```bash
# Windows 6GB 环境训练
python scripts/train.py --config configs/train_6gb.yaml --dataset splits

# 阿里云 24GB 环境训练
python scripts/train.py --config configs/train_24gb.yaml --dataset split_coords

# Dry-run 验证
python scripts/train.py --config configs/train_6gb.yaml --dataset splits --dry-run

# 评测
python scripts/evaluate.py --checkpoint ./checkpoints/checkpoint-xxx --test-file ../../data/splits/test.jsonl --output ./results
```

### 设计文档
- `docs/superpowers/specs/2026-03-21-qwen-1.5b-sft-design.md`
- `docs/superpowers/plans/2026-03-21-qwen-1.5b-sft-implementation.md`

### 复用模块
- `exp/exp0/metrics/deterministic.py` - 评测指标
- `exp/exp0/utils/model_loader.py` - 模型加载参考

---

## 2026-03-19 predictions_qwen_coords.jsonl 评价完成

### 任务概述
对带坐标版本的预测结果（predictions_qwen_coords.jsonl）进行评价，并与不带坐标版本进行对比分析。

### 评价结果

#### 带坐标版本 (qwen_coords_eval)
- **总体准确率**: 19.53%
- **样本数**: 1183

#### 不带坐标版本 (qwen_eval)
- **总体准确率**: 23.16%
- **样本数**: 1183

### 关键发现

#### 准确率对比
| 类型 | 不带坐标 | 带坐标 | 变化 |
|------|---------|--------|------|
| **总体** | 23.16% | 19.53% | **-3.63%** ⬇️ |
| Directional | 43.49% | 33.22% | **-10.27%** ⬇️⬇️ |
| Topological | 24.85% | 23.37% | -1.48% |
| Metric | 17.59% | 13.36% | -4.23% |
| Composite | 3.66% | 5.69% | **+2.03%** ⬆️ |

#### 难度分层对比
| 难度 | 不带坐标 | 带坐标 | 变化 |
|------|---------|--------|------|
| Easy | 32.53% | 25.81% | -6.72% |
| Medium | 26.92% | 22.12% | -4.80% |
| Hard | 4.47% | 6.87% | +2.40% |

### 主要结论
1. **坐标信息总体产生负面影响**: 准确率下降3.63%
2. **方向关系受影响最大**: 准确率下降10.27%
3. **复合关系是唯一提升的类型**: 准确率提升2.03%
4. **Hard难度受益**: 复杂问题中坐标可能提供辅助信息

### 输出文件
- 评价结果: `stage2_evaluation/results/qwen_coords_eval/metrics.json`
- 评价报告: `stage2_evaluation/results/qwen_coords_eval/report.md`
- 对比分析: `stage2_evaluation/results/coords_comparison_report.md`

### 建议
1. 如使用带坐标输入，需针对性微调
2. 考虑仅在Hard难度的复合关系问题上使用坐标
3. 探索不同坐标表示方式的效果
