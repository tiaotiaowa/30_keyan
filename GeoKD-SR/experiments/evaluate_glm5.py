"""
GLM-5评测脚本

使用GLM-5 API进行地理空间推理模型评测，避免使用GPT-4评测带来的数据泄露风险。

评测配置:
- 采样量：300题（30%）
- 评测维度：准确性、完整性、推理质量、语言流畅性
- 评分范围：1-5分
- 4-gram重叠检测

Author: GeoKD-SR Team
Date: 2026-03-03
"""

import json
import random
import os
import sys
import time
import requests
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
from pathlib import Path
from collections import defaultdict
import re

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# ==================== 配置 ====================

class EvalConfig:
    """评测配置"""

    # GLM-5 API配置
    GLM5_API_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    GLM5_MODEL = "glm-5"  # 可选: glm-5, glm-5-flash, glm-5-plus

    # 评测配置
    SAMPLE_SIZE = 300  # 采样量（30%）
    SAMPLE_RATIO = 0.3  # 采样比例

    # 评分配置
    MIN_SCORE = 1
    MAX_SCORE = 5

    # N-gram配置
    N_GRAM = 4  # 4-gram重叠检测

    # 输出配置
    OUTPUT_DIR = Path(__file__).parent.parent / "results" / "glm5_eval"

    # 评测维度
    EVAL_DIMENSIONS = [
        "accuracy",        # 准确性
        "completeness",    # 完整性
        "reasoning_quality",  # 推理质量
        "fluency"          # 语言流畅性
    ]


# ==================== GLM-5 API调用 ====================

class GLM5Client:
    """GLM-5 API客户端"""

    def __init__(self, api_key: str = None):
        """
        初始化GLM-5客户端

        Args:
            api_key: GLM-5 API密钥，如果为None则从环境变量读取
        """
        self.api_key = api_key or os.getenv("ZHIPUAI_API_KEY", "")
        self.api_base = EvalConfig.GLM5_API_BASE
        self.model = EvalConfig.GLM5_MODEL

        if not self.api_key:
            print("[警告] 未设置ZHIPUAI_API_KEY环境变量，将使用模拟模式")
            self.mock_mode = True
        else:
            self.mock_mode = False

    def _call_api(self, messages: List[Dict], temperature: float = 0.7,
                  max_tokens: int = 2000) -> Optional[str]:
        """
        调用GLM-5 API

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            响应文本，失败返回None
        """
        if self.mock_mode:
            return self._mock_response(messages)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(self.api_base, headers=headers,
                                    json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"[错误] GLM-5 API调用失败: {e}")
            return None

    def _mock_response(self, messages: List[Dict]) -> str:
        """
        模拟响应（用于测试）

        Args:
            messages: 消息列表

        Returns:
            模拟响应
        """
        # 返回模拟评分
        return json.dumps({
            "accuracy": 4,
            "completeness": 4,
            "reasoning_quality": 4,
            "fluency": 5,
            "overall": 4,
            "explanation": "模拟评分：答案基本正确，推理过程合理，表达清晰。"
        }, ensure_ascii=False)

    def evaluate_answer(self, question: str, reference: str,
                       prediction: str) -> Optional[Dict]:
        """
        使用GLM-5评估答案

        Args:
            question: 问题
            reference: 标准答案
            prediction: 模型预测答案

        Returns:
            评分结果字典
        """
        prompt = self._build_eval_prompt(question, reference, prediction)

        messages = [
            {"role": "system", "content": "你是一个地理空间推理专家。请评估以下答案的质量。"},
            {"role": "user", "content": prompt}
        ]

        response = self._call_api(messages, temperature=0.3)

        if response:
            try:
                # 尝试解析JSON响应
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                # 如果响应不是JSON，尝试提取JSON部分
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        return result
                    except json.JSONDecodeError:
                        pass

                # 如果无法解析，返回默认评分
                return {
                    "accuracy": 3,
                    "completeness": 3,
                    "reasoning_quality": 3,
                    "fluency": 3,
                    "overall": 3,
                    "explanation": "无法解析评分响应"
                }

        return None

    def _build_eval_prompt(self, question: str, reference: str,
                          prediction: str) -> str:
        """
        构建评测Prompt

        Args:
            question: 问题
            reference: 标准答案
            prediction: 模型预测答案

        Returns:
            评测Prompt
        """
        prompt = f"""你是一个地理空间推理专家。请评估以下答案的质量。

问题: {question}
标准答案: {reference}
模型答案: {prediction}

请从以下维度评分（1-5分）：
1. 准确性（accuracy）：答案是否正确
2. 完整性（completeness）：是否包含所有必要信息
3. 推理质量（reasoning_quality）：推理过程是否合理
4. 语言流畅性（fluency）：表达是否清晰

评分标准：
- 5分：优秀，完全符合要求
- 4分：良好，基本符合要求
- 3分：中等，部分符合要求
- 2分：较差，不太符合要求
- 1分：很差，完全不符合要求

输出JSON格式（不要包含其他内容）：
{{
  "accuracy": <1-5>,
  "completeness": <1-5>,
  "reasoning_quality": <1-5>,
  "fluency": <1-5>,
  "overall": <1-5>,
  "explanation": "<简要说明>"
}}"""
        return prompt


# ==================== N-gram重叠检测 ====================

class NGramOverlapDetector:
    """N-gram重叠检测器"""

    def __init__(self, n: int = 4):
        """
        初始化N-gram检测器

        Args:
            n: n-gram的n值
        """
        self.n = n

    def extract_ngrams(self, text: str) -> set:
        """
        提取n-gram

        Args:
            text: 输入文本

        Returns:
            n-gram集合
        """
        # 清理文本
        text = re.sub(r'\s+', ' ', text.strip())
        tokens = text.split()

        ngrams = set()
        for i in range(len(tokens) - self.n + 1):
            ngram = ' '.join(tokens[i:i + self.n])
            ngrams.add(ngram)

        return ngrams

    def calculate_overlap(self, text1: str, text2: str) -> Dict[str, Any]:
        """
        计算两个文本的n-gram重叠

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            重叠统计信息
        """
        ngrams1 = self.extract_ngrams(text1)
        ngrams2 = self.extract_ngrams(text2)

        if not ngrams1 or not ngrams2:
            return {
                "overlap_count": 0,
                "overlap_ratio": 0.0,
                "jaccard": 0.0
            }

        overlap = ngrams1 & ngrams2
        union = ngrams1 | ngrams2

        overlap_count = len(overlap)
        overlap_ratio = overlap_count / min(len(ngrams1), len(ngrams2))
        jaccard = overlap_count / len(union) if union else 0

        return {
            "overlap_count": overlap_count,
            "overlap_ratio": overlap_ratio,
            "jaccard": jaccard
        }

    def detect_data_leakage(self, train_data: List[str],
                           eval_data: List[str]) -> Dict[str, Any]:
        """
        检测训练数据和评测数据之间的重叠

        Args:
            train_data: 训练数据文本列表
            eval_data: 评测数据文本列表

        Returns:
            重叠报告
        """
        # 提取所有训练数据的n-gram
        train_ngrams = set()
        for text in train_data:
            train_ngrams.update(self.extract_ngrams(text))

        # 检查评测数据重叠
        eval_overlap_counts = []
        eval_overlap_ratios = []

        for text in eval_data:
            eval_ngrams = self.extract_ngrams(text)
            if eval_ngrams:
                overlap = train_ngrams & eval_ngrams
                overlap_ratio = len(overlap) / len(eval_ngrams)
                eval_overlap_counts.append(len(overlap))
                eval_overlap_ratios.append(overlap_ratio)

        # 统计
        avg_overlap_count = sum(eval_overlap_counts) / len(eval_overlap_counts) if eval_overlap_counts else 0
        avg_overlap_ratio = sum(eval_overlap_ratios) / len(eval_overlap_ratios) if eval_overlap_ratios else 0
        max_overlap_ratio = max(eval_overlap_ratios) if eval_overlap_ratios else 0

        # 计算有显著重叠的样本比例（重叠率>10%）
        significant_overlap = sum(1 for r in eval_overlap_ratios if r > 0.1)
        significant_ratio = significant_overlap / len(eval_overlap_ratios) if eval_overlap_ratios else 0

        return {
            "total_train_ngrams": len(train_ngrams),
            "total_eval_samples": len(eval_data),
            "avg_overlap_count": avg_overlap_count,
            "avg_overlap_ratio": avg_overlap_ratio,
            "max_overlap_ratio": max_overlap_ratio,
            "significant_overlap_samples": significant_overlap,
            "significant_overlap_ratio": significant_ratio
        }


# ==================== 评测器 ====================

class GLM5Evaluator:
    """GLM-5评测器"""

    def __init__(self, glm5_client: GLM5Client = None):
        """
        初始化评测器

        Args:
            glm5_client: GLM-5客户端
        """
        self.client = glm5_client or GLM5Client()
        self.ngram_detector = NGramOverlapDetector(n=EvalConfig.N_GRAM)
        self.results = []

    def sample_questions(self, benchmark: Dict, sample_size: int = None) -> List[Dict]:
        """
        从评测基准中采样问题

        Args:
            benchmark: 评测基准数据
            sample_size: 采样数量

        Returns:
            采样的问题列表
        """
        sample_size = sample_size or EvalConfig.SAMPLE_SIZE
        questions = benchmark.get("questions", [])

        if len(questions) <= sample_size:
            return questions

        # 按维度分层采样
        dimension_questions = defaultdict(list)
        for q in questions:
            dimension = q.get("dimension", "unknown")
            dimension_questions[dimension].append(q)

        sampled = []
        samples_per_dimension = sample_size // len(dimension_questions)

        for dimension, dim_questions in dimension_questions.items():
            if len(dim_questions) <= samples_per_dimension:
                sampled.extend(dim_questions)
            else:
                sampled.extend(random.sample(dim_questions, samples_per_dimension))

        # 如果样本不足，随机补充
        while len(sampled) < sample_size and len(sampled) < len(questions):
            remaining = [q for q in questions if q not in sampled]
            sampled.append(random.choice(remaining))

        return sampled[:sample_size]

    def evaluate_prediction(self, question: Dict, prediction: str) -> Dict:
        """
        评估单个预测

        Args:
            question: 问题数据
            prediction: 模型预测

        Returns:
            评测结果
        """
        # 提取问题和标准答案
        question_text = question.get("question", "")
        reference = self._extract_reference_answer(question)

        # 使用GLM-5评估
        eval_result = self.client.evaluate_answer(
            question_text, reference, prediction
        )

        if eval_result is None:
            eval_result = {
                "accuracy": 0,
                "completeness": 0,
                "reasoning_quality": 0,
                "fluency": 0,
                "overall": 0,
                "explanation": "评测失败"
            }

        # 添加问题信息
        result = {
            "question_id": question.get("id", ""),
            "dimension": question.get("dimension", ""),
            "question": question_text,
            "reference": reference,
            "prediction": prediction,
            "scores": eval_result
        }

        return result

    def _extract_reference_answer(self, question: Dict) -> str:
        """
        提取标准答案

        Args:
            question: 问题数据

        Returns:
            标准答案文本
        """
        # 尝试获取answer字段
        answer = question.get("answer", "")

        if isinstance(answer, bool):
            return "是" if answer else "否"
        elif isinstance(answer, (int, float)):
            return str(answer)
        else:
            return str(answer)

    def evaluate_benchmark(self, benchmark: Dict, predictions: Dict = None,
                          sample_size: int = None) -> Dict:
        """
        评测整个基准

        Args:
            benchmark: 评测基准数据
            predictions: 预测结果字典 {question_id: prediction}
            sample_size: 采样数量

        Returns:
            评测报告
        """
        print("=" * 60)
        print("GLM-5评测开始")
        print("=" * 60)

        # 采样问题
        questions = self.sample_questions(benchmark, sample_size)
        print(f"\n[采样] 从{len(benchmark.get('questions', []))}题中采样{len(questions)}题")

        # 如果没有提供预测，使用模拟预测
        if predictions is None:
            predictions = self._generate_mock_predictions(questions)
            print("[警告] 未提供预测结果，使用模拟预测")

        # 逐题评测
        results = []
        for i, question in enumerate(questions, 1):
            question_id = question.get("id", "")
            prediction = predictions.get(question_id, "")

            print(f"\r[评测] 进度: {i}/{len(questions)}", end="")

            result = self.evaluate_prediction(question, prediction)
            results.append(result)

            # 避免API限流
            time.sleep(0.5)

        print(f"\n[完成] 评测完成，共{len(results)}题")

        # 生成统计报告
        report = self._generate_report(results, benchmark)

        # 保存结果
        self._save_results(results, report, benchmark)

        return report

    def _generate_mock_predictions(self, questions: List[Dict]) -> Dict:
        """
        生成模拟预测

        Args:
            questions: 问题列表

        Returns:
            模拟预测字典
        """
        predictions = {}
        for q in questions:
            # 模拟预测：70%正确，30%错误
            if random.random() < 0.7:
                predictions[q["id"]] = self._extract_reference_answer(q)
            else:
                predictions[q["id"]] = "不知道答案"
        return predictions

    def _generate_report(self, results: List[Dict], benchmark: Dict) -> Dict:
        """
        生成评测报告

        Args:
            results: 评测结果列表
            benchmark: 评测基准数据

        Returns:
            评测报告
        """
        # 统计各维度分数
        dimension_scores = defaultdict(list)
        overall_scores = []

        for result in results:
            dimension = result["dimension"]
            scores = result["scores"]

            dimension_scores[dimension].append(scores)
            overall_scores.append(scores.get("overall", 0))

        # 计算平均分
        def avg_score(score_list, key):
            values = [s.get(key, 0) for s in score_list if s]
            return sum(values) / len(values) if values else 0

        # 总体统计
        overall_avg = sum(overall_scores) / len(overall_scores) if overall_scores else 0

        # 按维度统计
        dimension_stats = {}
        for dimension, scores in dimension_scores.items():
            dimension_stats[dimension] = {
                "count": len(scores),
                "accuracy": avg_score(scores, "accuracy"),
                "completeness": avg_score(scores, "completeness"),
                "reasoning_quality": avg_score(scores, "reasoning_quality"),
                "fluency": avg_score(scores, "fluency"),
                "overall": avg_score(scores, "overall")
            }

        # 分数分布
        score_distribution = defaultdict(int)
        for score in overall_scores:
            score_distribution[score] += 1

        # 生成报告
        report = {
            "evaluation_info": {
                "evaluator": "GLM-5",
                "model": EvalConfig.GLM5_MODEL,
                "sample_size": len(results),
                "total_questions": len(benchmark.get("questions", [])),
                "sample_ratio": len(results) / len(benchmark.get("questions", [])) if benchmark.get("questions") else 0
            },
            "overall_statistics": {
                "average_score": round(overall_avg, 2),
                "min_score": min(overall_scores) if overall_scores else 0,
                "max_score": max(overall_scores) if overall_scores else 0
            },
            "dimension_statistics": dimension_stats,
            "score_distribution": dict(score_distribution),
            "detailed_results": results
        }

        return report

    def _save_results(self, results: List[Dict], report: Dict,
                     benchmark: Dict):
        """
        保存评测结果

        Args:
            results: 详细结果
            report: 评测报告
            benchmark: 原始基准
        """
        # 创建输出目录
        output_dir = EvalConfig.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名（包含时间戳）
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # 保存完整报告
        report_path = output_dir / f"glm5_eval_report_{timestamp}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n[保存] 报告已保存: {report_path}")

        # 保存简明摘要
        summary = {
            "evaluation_info": report["evaluation_info"],
            "overall_statistics": report["overall_statistics"],
            "dimension_statistics": report["dimension_statistics"]
        }
        summary_path = output_dir / f"glm5_eval_summary_{timestamp}.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"[保存] 摘要已保存: {summary_path}")

    def check_ngram_overlap(self, train_texts: List[str],
                           eval_texts: List[str]) -> Dict:
        """
        检查训练和评测数据的n-gram重叠

        Args:
            train_texts: 训练数据文本列表
            eval_texts: 评测数据文本列表

        Returns:
            重叠报告
        """
        print("\n" + "=" * 60)
        print("N-gram重叠检测")
        print("=" * 60)

        report = self.ngram_detector.detect_data_leakage(train_texts, eval_texts)

        print(f"\n训练数据n-gram总数: {report['total_train_ngrams']}")
        print(f"评测数据样本数: {report['total_eval_samples']}")
        print(f"平均重叠数: {report['avg_overlap_count']:.2f}")
        print(f"平均重叠率: {report['avg_overlap_ratio']:.2%}")
        print(f"最大重叠率: {report['max_overlap_ratio']:.2%}")
        print(f"显著重叠样本数(>10%): {report['significant_overlap_samples']}")
        print(f"显著重叠样本比例: {report['significant_overlap_ratio']:.2%}")

        # 保存重叠报告
        output_dir = EvalConfig.OUTPUT_DIR
        overlap_path = output_dir / "ngram_overlap_report.json"
        with open(overlap_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n[保存] 重叠报告已保存: {overlap_path}")

        return report


# ==================== 主函数 ====================

def main():
    """主函数"""
    # 设置路径
    base_dir = Path(__file__).parent.parent
    benchmark_path = base_dir / "data" / "geosr_bench" / "geosr_bench_v1.json"

    print("=" * 60)
    print("GLM-5评测系统")
    print("=" * 60)

    # 加载评测基准
    print(f"\n加载评测基准: {benchmark_path}")
    if not benchmark_path.exists():
        print(f"[错误] 评测基准文件不存在: {benchmark_path}")
        print("请先运行 generate_benchmark.py 生成评测基准")
        return

    with open(benchmark_path, 'r', encoding='utf-8') as f:
        benchmark = json.load(f)

    print(f"[OK] 评测基准加载完成")
    print(f"  - 名称: {benchmark.get('benchmark_name', 'N/A')}")
    print(f"  - 版本: {benchmark.get('version', 'N/A')}")
    print(f"  - 总题数: {benchmark.get('total_questions', 0)}")

    # 创建评测器
    evaluator = GLM5Evaluator()

    # 运行评测
    report = evaluator.evaluate_benchmark(
        benchmark,
        sample_size=EvalConfig.SAMPLE_SIZE
    )

    # 打印摘要
    print("\n" + "=" * 60)
    print("评测摘要")
    print("=" * 60)
    print(f"采样数量: {report['evaluation_info']['sample_size']}")
    print(f"平均得分: {report['overall_statistics']['average_score']:.2f}")
    print(f"得分范围: {report['overall_statistics']['min_score']:.1f} - {report['overall_statistics']['max_score']:.1f}")

    print("\n按维度统计:")
    for dimension, stats in report['dimension_statistics'].items():
        print(f"  {dimension}:")
        print(f"    样本数: {stats['count']}")
        print(f"    平均分: {stats['overall']:.2f}")
        print(f"    准确性: {stats['accuracy']:.2f}")
        print(f"    完整性: {stats['completeness']:.2f}")
        print(f"    推理质量: {stats['reasoning_quality']:.2f}")
        print(f"    流畅性: {stats['fluency']:.2f}")

    print("\n" + "=" * 60)
    print("评测完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
