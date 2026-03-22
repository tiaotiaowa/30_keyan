# GLM-4.7 API 测试集评测实施计划

> **创建日期**: 2026-03-16
> **计划类型**: 评测验证
> **预估工时**: 8-10小时
> **工程师须知**: 本计划假设你对GeoKD-SR项目无先验知识，请严格按步骤执行

---

## 一、项目背景

### 1.1 为什么做这个评测？

**问题**: 我们设计了9个知识蒸馏实验，需要一套统一的评测指标。但这些指标是否合理？是否能有效区分不同质量的模型输出？

**解决方案**: 使用GLM-4.7（一个高性能大模型）对测试集进行评测，建立基线，验证指标有效性。

### 1.2 评测目标

| 目标 | 验证方法 | 成功标准 |
|------|----------|----------|
| 指标设计合理性 | 计算指标区分度、相关性 | 高低质量组差异>10%, r>0.6 |
| 坐标信息影响 | 对比split_coords vs splits | 差异显著性p<0.05 |
| 建立基线 | 记录GLM-4.7各项指标 | 作为后续实验参考 |

### 1.3 数据集说明

| 数据集 | 路径 | 样本数 | 特点 |
|--------|------|--------|------|
| split_coords | `data/split_coords/test.jsonl` | 1183条 | question包含坐标，如"北京(116.4,39.9)" |
| splits | `data/splits/test.jsonl` | 1183条 | question不含坐标，纯自然语言 |

**数据字段**:
```json
{
  "id": "geosr_directional_00513",
  "question": "鼓浪屿郑成功纪念馆位于福建省的什么方位？",
  "answer": "东南方向",
  "spatial_relation_type": "directional",
  "difficulty": "medium",
  "entities": [...],
  "reasoning_chain": [...]
}
```

---

## 二、文件结构

### 2.1 需要创建的文件

```
D:\30_keyan\GeoKD-SR\exp\exp0\glm\
├── PLAN.md                      # 本计划文档
├── README.md                    # 模块说明
├── config/
│   └── glm47_eval_config.yaml   # 评测配置
├── scripts/
│   ├── evaluate_glm47.py        # 主评测脚本
│   ├── glm47_client.py          # GLM-4.7 API客户端
│   ├── run_inference.py         # 推理脚本
│   ├── run_metrics.py           # 指标计算脚本
│   └── run_llm_eval.py          # LLM评估脚本
├── prompts/
│   ├── inference_prompt.py      # 推理Prompt模板
│   └── eval_prompt.py           # 评估Prompt模板
├── results/
│   └── .gitkeep                 # 结果输出目录
└── checkpoints/
    └── .gitkeep                 # 断点续传目录
```

### 2.2 需要复用的现有文件

| 文件 | 路径 | 用途 |
|------|------|------|
| deterministic.py | `exp/exp0/metrics/deterministic.py` | BLEU、ROUGE、Accuracy等指标 |
| semantic.py | `exp/exp0/metrics/semantic.py` | BERTScore计算 |
| evaluate_glm5.py | `experiments/evaluate_glm5.py` | GLM API调用参考 |

---

## 三、任务分解

### Task 1: 创建配置文件 (10分钟)

**文件**: `exp/exp0/glm/config/glm47_eval_config.yaml`

**说明**: 配置API密钥、模型参数、批处理参数等

```yaml
# API配置
api:
  model: "glm-4.7"              # 使用glm-4.7模型
  api_key_env: "ZHIPUAI_API_KEY"  # 从环境变量读取
  base_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions"
  timeout: 60                   # 请求超时(秒)
  max_retries: 3                # 最大重试次数
  retry_delay: 5                # 重试延迟(秒)

# 生成参数
generation:
  temperature: 0.1              # 低温度保证一致性
  top_p: 0.9
  max_tokens: 512               # 最大输出token数
  do_sample: true

# 批处理配置
batch:
  batch_size: 10                # 每批处理数量
  delay_between_requests: 0.5   # 请求间隔(秒)，避免限流
  checkpoint_interval: 50       # 每50条保存checkpoint

# 评测配置
eval:
  llm_eval_sample_size: 300     # LLM评估采样数(约25%)
  use_bertscore: true
  bert_model: "bert-base-chinese"
  bert_max_length: 512

# 路径配置
paths:
  split_coords_test: "data/split_coords/test.jsonl"
  splits_test: "data/splits/test.jsonl"
  output_dir: "exp/exp0/glm/results"
  checkpoint_dir: "exp/exp0/glm/checkpoints"
```

**验收标准**:
- [ ] YAML文件语法正确
- [ ] 所有必填字段已配置
- [ ] 路径相对于项目根目录正确

---

### Task 2: 创建Prompt模板 (15分钟)

**文件**: `exp/exp0/glm/prompts/inference_prompt.py`

**说明**: 定义让GLM-4.7回答问题的Prompt

```python
"""
GLM-4.7推理Prompt模板
"""

INFERENCE_PROMPT_TEMPLATE = """你是一个地理空间推理专家。请根据问题给出准确、简洁的答案。

问题: {question}

请直接给出答案，不需要解释过程。答案格式要求：
- 方向问题：直接说明方向，如"东南方向"
- 距离问题：给出具体数值，如"约1200公里"
- 拓扑问题：明确说明关系，如"是的，XX位于YY内部"
- 复合问题：同时给出方向和距离，如"东北方向，距离约2000公里"

答案:"""


SYSTEM_PROMPT = "你是一个专业的地理空间推理专家，擅长回答方向、距离、拓扑等空间关系问题。"


def format_inference_prompt(question: str) -> list:
    """
    格式化推理Prompt

    Args:
        question: 问题文本

    Returns:
        messages: 格式化后的消息列表
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": INFERENCE_PROMPT_TEMPLATE.format(question=question)}
    ]
```

**文件**: `exp/exp0/glm/prompts/eval_prompt.py`

```python
"""
LLM-as-Judge评估Prompt模板
"""

EVAL_PROMPT_TEMPLATE = """你是一个地理空间推理专家。请从以下维度评估模型输出的质量。

## 问题
{question}

## 标准答案
{reference_answer}

## 模型输出
{prediction}

## 评估维度

### 1. 推理质量 (1-5分)
- 5分: 推理链完整、逻辑清晰，步骤之间有明确的因果关系
- 4分: 推理基本正确，有小瑕疵但不影响结论
- 3分: 推理方向正确，但关键步骤缺失或跳跃
- 2分: 推理有明显错误，但有一定逻辑
- 1分: 推理完全错误或无推理过程

### 2. 答案完整性 (1-5分)
- 5分: 完整回答问题，包含所有必要信息，表述清晰
- 4分: 基本完整，有轻微遗漏但不影响理解
- 3分: 部分回答，关键信息缺失，需要补充
- 2分: 回答不完整，缺少重要内容
- 1分: 未给出有效答案或答非所问

### 3. 空间一致性 (1-5分)
- 5分: 空间描述完全正确，方向/位置/距离准确
- 4分: 基本正确，有小偏差但不影响主要结论
- 3分: 部分正确，存在空间概念混淆
- 2分: 空间描述有明显错误
- 1分: 空间描述完全错误

### 4. 综合评分 (1-5分)
综合考虑以上三个维度给出整体评分。

请严格按JSON格式输出评估结果（不要包含其他内容）：
{{
  "reasoning_quality": <1-5的整数>,
  "answer_completeness": <1-5的整数>,
  "spatial_consistency": <1-5的整数>,
  "overall_score": <1-5的整数>,
  "brief_comment": "<一句话评价，不超过50字>"
}}"""


def format_eval_prompt(question: str, reference: str, prediction: str) -> str:
    """
    格式化评估Prompt

    Args:
        question: 原始问题
        reference: 标准答案
        prediction: 模型预测

    Returns:
        格式化后的Prompt
    """
    return EVAL_PROMPT_TEMPLATE.format(
        question=question,
        reference_answer=reference,
        prediction=prediction
    )
```

**验收标准**:
- [ ] Prompt模板清晰，无歧义
- [ ] 支持所有4种空间类型问题
- [ ] 评估维度定义明确，有具体评分标准

---

### Task 3: 创建GLM-4.7客户端 (30分钟)

**文件**: `exp/exp0/glm/scripts/glm47_client.py`

**说明**: 封装GLM-4.7 API调用，支持批量处理和断点续传

```python
"""
GLM-4.7 API客户端

功能:
- API调用和认证
- 批量处理
- 错误重试
- 断点续传
"""

import os
import time
import json
from typing import List, Dict, Optional
from pathlib import Path

try:
    from zhipuai import ZhipuAI
except ImportError:
    raise ImportError("请安装zhipuai: pip install zhipuai")


class GLM47Client:
    """GLM-4.7 API客户端"""

    def __init__(self, config: dict):
        """
        初始化客户端

        Args:
            config: 配置字典，包含api、generation、batch等配置
        """
        self.config = config

        # 初始化API客户端
        api_key = os.getenv(config['api']['api_key_env'])
        if not api_key:
            raise ValueError(f"请设置环境变量 {config['api']['api_key_env']}")

        self.client = ZhipuAI(api_key=api_key)
        self.model = config['api']['model']

        # 批处理配置
        self.batch_size = config['batch']['batch_size']
        self.delay = config['batch']['delay_between_requests']
        self.checkpoint_interval = config['batch']['checkpoint_interval']

    def generate(self, messages: List[Dict], **kwargs) -> str:
        """
        生成回复

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            生成的文本
        """
        # 合并配置
        gen_config = {**self.config['generation'], **kwargs}

        max_retries = self.config['api']['max_retries']
        retry_delay = self.config['api']['retry_delay']

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=gen_config.get('temperature', 0.1),
                    top_p=gen_config.get('top_p', 0.9),
                    max_tokens=gen_config.get('max_tokens', 512)
                )
                return response.choices[0].message.content

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    print(f"请求失败，{wait_time}秒后重试: {e}")
                    time.sleep(wait_time)
                else:
                    return f"[API_ERROR] {str(e)}"

    def batch_generate(
        self,
        data_list: List[Dict],
        prompt_formatter,
        checkpoint_path: Optional[Path] = None
    ) -> List[Dict]:
        """
        批量生成

        Args:
            data_list: 数据列表，每项包含id, question等字段
            prompt_formatter: Prompt格式化函数
            checkpoint_path: checkpoint保存路径

        Returns:
            结果列表，每项包含id, question, prediction等
        """
        results = []

        # 检查是否有已完成的checkpoint
        start_idx = 0
        if checkpoint_path and checkpoint_path.exists():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                for line in f:
                    results.append(json.loads(line))
            start_idx = len(results)
            print(f"从checkpoint恢复，已完成 {start_idx} 条")

        total = len(data_list)
        print(f"开始处理，总计 {total} 条，从第 {start_idx + 1} 条开始")

        for i in range(start_idx, total):
            item = data_list[i]

            # 生成回复
            messages = prompt_formatter(item['question'])
            prediction = self.generate(messages)

            results.append({
                'id': item['id'],
                'question': item['question'],
                'reference': item['answer'],
                'prediction': prediction,
                'spatial_type': item.get('spatial_relation_type', 'unknown'),
                'difficulty': item.get('difficulty', 'unknown')
            })

            # 进度显示
            if (i + 1) % 10 == 0:
                print(f"进度: {i + 1}/{total} ({(i+1)/total*100:.1f}%)")

            # 保存checkpoint
            if checkpoint_path and (i + 1) % self.checkpoint_interval == 0:
                self._save_checkpoint(results, checkpoint_path)

            # 请求间隔
            time.sleep(self.delay)

        # 最终保存
        if checkpoint_path:
            self._save_checkpoint(results, checkpoint_path)

        return results

    def _save_checkpoint(self, results: List[Dict], path: Path):
        """保存checkpoint"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        print(f"Checkpoint已保存: {path}")


# 使用示例
if __name__ == "__main__":
    import yaml

    # 加载配置
    with open("config/glm47_eval_config.yaml") as f:
        config = yaml.safe_load(f)

    # 初始化客户端
    client = GLM47Client(config)

    # 测试单次调用
    messages = [{"role": "user", "content": "北京位于上海的什么方向？"}]
    result = client.generate(messages)
    print(f"测试结果: {result}")
```

**验收标准**:
- [ ] API调用成功
- [ ] 重试机制正常工作
- [ ] checkpoint保存和恢复正常
- [ ] 进度显示正确

**测试命令**:
```bash
cd D:\30_keyan\GeoKD-SR\exp\exp0\glm
python scripts/glm47_client.py
```

---

### Task 4: 创建主评测脚本 (45分钟)

**文件**: `exp/exp0/glm/scripts/evaluate_glm47.py`

**说明**: 主评测脚本，整合所有功能

```python
"""
GLM-4.7评测主脚本

用法:
    # 测试5条样本
    python evaluate_glm47.py --config config/glm47_eval_config.yaml --sample_size 5

    # 评测split_coords版本
    python evaluate_glm47.py --config config/glm47_eval_config.yaml --dataset split_coords

    # 评测splits版本
    python evaluate_glm47.py --config config/glm47_eval_config.yaml --dataset splits

    # 评测两个版本
    python evaluate_glm47.py --config config/glm47_eval_config.yaml --dataset both
"""

import argparse
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# 添加项目路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from exp.exp0.glm.scripts.glm47_client import GLM47Client
from exp.exp0.glm.prompts.inference_prompt import format_inference_prompt


def load_test_data(file_path: str, sample_size: int = None) -> List[Dict]:
    """加载测试数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))

    if sample_size:
        data = data[:sample_size]

    return data


def run_inference(
    client: GLM47Client,
    data: List[Dict],
    output_path: Path,
    checkpoint_path: Path = None
) -> List[Dict]:
    """运行推理"""
    print(f"\n{'='*60}")
    print("Phase 2: GLM-4.7 推理")
    print(f"{'='*60}")

    results = client.batch_generate(
        data_list=data,
        prompt_formatter=format_inference_prompt,
        checkpoint_path=checkpoint_path
    )

    # 保存结果
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"推理结果已保存: {output_path}")
    return results


def calculate_deterministic_metrics(predictions_path: Path) -> Dict:
    """计算确定性指标"""
    print(f"\n{'='*60}")
    print("Phase 3a: 计算确定性指标")
    print(f"{'='*60}")

    # 加载预测结果
    predictions = []
    references = []
    spatial_types = []

    with open(predictions_path, 'r', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line)
            predictions.append(item['prediction'])
            references.append(item['reference'])
            spatial_types.append(item['spatial_type'])

    # 导入指标计算模块
    try:
        from exp.exp0.metrics.deterministic import (
            calculate_overall_accuracy,
            calculate_format_valid_rate,
            calculate_corpus_bleu_4,
            calculate_corpus_rouge_l,
            calculate_corpus_spatial_f1
        )

        metrics = {
            "overall_accuracy": calculate_overall_accuracy(predictions, references, spatial_types),
            "format_valid_rate": calculate_format_valid_rate(predictions),
            "bleu_4": calculate_corpus_bleu_4(predictions, references),
            "rouge_l": calculate_corpus_rouge_l(predictions, references),
            "spatial_f1": calculate_corpus_spatial_f1(predictions, references, spatial_types)
        }

    except ImportError as e:
        print(f"警告: 无法导入指标模块: {e}")
        print("使用简化版指标计算...")
        metrics = calculate_simple_metrics(predictions, references, spatial_types)

    return metrics


def calculate_simple_metrics(predictions, references, spatial_types):
    """简化版指标计算（备用）"""
    import re
    from collections import Counter

    # Format Valid Rate
    valid_count = 0
    for pred in predictions:
        if pred and not pred.startswith("[API_ERROR]"):
            valid_count += 1
    format_valid_rate = valid_count / len(predictions) if predictions else 0

    # 简单Accuracy (关键词匹配)
    correct = 0
    for pred, ref in zip(predictions, references):
        pred_lower = pred.lower()
        ref_lower = ref.lower()
        # 检查关键词重叠
        pred_words = set(re.findall(r'[\u4e00-\u9fff]+', pred_lower))
        ref_words = set(re.findall(r'[\u4e00-\u9fff]+', ref_lower))
        if pred_words & ref_words:
            correct += 1
    accuracy = correct / len(predictions) if predictions else 0

    return {
        "overall_accuracy": accuracy,
        "format_valid_rate": format_valid_rate,
        "bleu_4": 0.0,  # 需要完整实现
        "rouge_l": 0.0,
        "spatial_f1": 0.0,
        "note": "简化版指标，部分指标为0"
    }


def generate_report(metrics: Dict, dataset_name: str, output_path: Path):
    """生成评测报告"""
    report = f"""# GLM-4.7 评测报告

## 评测信息
- 数据集: {dataset_name}
- 评测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 模型: GLM-4.7

## 确定性指标

| 指标 | 分数 |
|------|------|
| Overall Accuracy | {metrics.get('overall_accuracy', 0):.4f} |
| Format Valid Rate | {metrics.get('format_valid_rate', 0):.4f} |
| BLEU-4 | {metrics.get('bleu_4', 0):.4f} |
| ROUGE-L | {metrics.get('rouge_l', 0):.4f} |
| Spatial F1 | {metrics.get('spatial_f1', 0):.4f} |

## 备注
{metrics.get('note', '无')}
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"报告已生成: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="GLM-4.7评测脚本")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument(
        "--dataset",
        choices=["split_coords", "splits", "both"],
        default="both",
        help="要评测的数据集"
    )
    parser.add_argument("--sample_size", type=int, default=None, help="采样数量(测试用)")
    parser.add_argument("--skip_inference", action="store_true", help="跳过推理，直接计算指标")
    args = parser.parse_args()

    # 加载配置
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 初始化客户端
    client = GLM47Client(config)

    # 创建输出目录
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(config['paths']['output_dir']) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存配置
    with open(output_dir / 'config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)

    # 确定要评测的数据集
    datasets = []
    if args.dataset in ["split_coords", "both"]:
        datasets.append(("split_coords", config['paths']['split_coords_test']))
    if args.dataset in ["splits", "both"]:
        datasets.append(("splits", config['paths']['splits_test']))

    # 对每个数据集执行评测
    for name, path in datasets:
        print(f"\n{'#'*60}")
        print(f"# 评测数据集: {name}")
        print(f"{'#'*60}")

        # Phase 1: 加载数据
        data = load_test_data(path, args.sample_size)
        print(f"加载数据: {len(data)} 条")

        # Phase 2: 推理
        if not args.skip_inference:
            checkpoint_path = Path(config['paths']['checkpoint_dir']) / f"{name}_checkpoint.jsonl"
            predictions_path = output_dir / f"predictions_{name}.jsonl"
            predictions = run_inference(client, data, predictions_path, checkpoint_path)
        else:
            predictions_path = output_dir / f"predictions_{name}.jsonl"
            print(f"跳过推理，使用已有结果: {predictions_path}")

        # Phase 3: 计算指标
        metrics = calculate_deterministic_metrics(predictions_path)

        # 保存指标
        metrics_path = output_dir / f"metrics_{name}.json"
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(f"指标已保存: {metrics_path}")

        # Phase 4: 生成报告
        report_path = output_dir / f"report_{name}.md"
        generate_report(metrics, name, report_path)

    print(f"\n{'='*60}")
    print("评测完成!")
    print(f"结果目录: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
```

**验收标准**:
- [ ] 脚本可以正常运行
- [ ] 支持--sample_size参数测试
- [ ] 生成正确的输出文件

---

### Task 5: 创建README文档 (15分钟)

**文件**: `exp/exp0/glm/README.md`

```markdown
# GLM-4.7 测试集评测模块

> 用于验证GeoKD-SR项目评测指标设计的有效性

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install zhipuai pyyaml

# 设置API密钥
export ZHIPUAI_API_KEY="your_api_key_here"
```

### 2. 运行测试

```bash
cd D:\30_keyan\GeoKD-SR\exp\exp0\glm

# 测试5条样本
python scripts/evaluate_glm47.py --config config/glm47_eval_config.yaml --sample_size 5

# 完整评测
python scripts/evaluate_glm47.py --config config/glm47_eval_config.yaml --dataset both
```

## 目录结构

```
glm/
├── PLAN.md              # 实施计划
├── README.md            # 本文件
├── config/              # 配置文件
├── scripts/             # 脚本
├── prompts/             # Prompt模板
├── results/             # 输出结果
└── checkpoints/         # 断点续传
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

- `predictions_*.jsonl` - 模型预测结果
- `metrics_*.json` - 评测指标
- `report_*.md` - 评测报告

## 注意事项

1. **API限流**: 请求间隔设为0.5秒，避免触发限流
2. **断点续传**: 每50条自动保存checkpoint
3. **费用估算**: 2366条请求约需2-3元

## 联系方式

如有问题，请查阅 PLAN.md 或联系项目负责人。
```

---

### Task 6: 创建目录结构和.gitkeep (5分钟)

```bash
cd D:\30_keyan\GeoKD-SR\exp\exp0\glm

# 创建子目录
mkdir config
mkdir scripts
mkdir prompts
mkdir results
mkdir checkpoints

# 创建.gitkeep
echo. > results\.gitkeep
echo. > checkpoints\.gitkeep
```

---

### Task 7: 运行测试验证 (30分钟)

**测试步骤**:

1. **API连通性测试**:
```bash
python scripts/glm47_client.py
```
期望输出: 测试结果: [GLM-4.7的回答]

2. **5条样本测试**:
```bash
python scripts/evaluate_glm47.py --config config/glm47_eval_config.yaml --sample_size 5 --dataset splits
```
期望输出:
- predictions_splits.jsonl (5条)
- metrics_splits.json
- report_splits.md

3. **检查输出**:
```bash
# 查看预测结果
head results/*/predictions_splits.jsonl

# 查看指标
cat results/*/metrics_splits.json

# 查看报告
cat results/*/report_splits.md
```

**验收标准**:
- [ ] API调用成功率 > 95%
- [ ] 指标计算无报错
- [ ] 报告格式正确

---

## 四、执行顺序

```
Task 1 (配置) ──────► Task 2 (Prompt) ──────► Task 3 (客户端)
                                                     │
                                                     ▼
Task 5 (README) ◄──── Task 4 (主脚本) ◄──────────────┘
         │
         ▼
    Task 6 (目录)
         │
         ▼
    Task 7 (测试)
```

---

## 五、风险评估

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| API密钥无效 | 无法调用API | 检查环境变量设置 |
| API限流 | 评测中断 | 已实现断点续传 |
| 依赖模块缺失 | 脚本报错 | 提前安装zhipuai |
| 指标计算错误 | 结果不准确 | 使用简化版备用 |

---

## 六、验收清单

- [ ] Task 1: 配置文件创建完成
- [ ] Task 2: Prompt模板创建完成
- [ ] Task 3: GLM-4.7客户端创建完成
- [ ] Task 4: 主评测脚本创建完成
- [ ] Task 5: README文档创建完成
- [ ] Task 6: 目录结构创建完成
- [ ] Task 7: 测试验证通过

---

**创建日期**: 2026-03-16
**最后更新**: 2026-03-16
