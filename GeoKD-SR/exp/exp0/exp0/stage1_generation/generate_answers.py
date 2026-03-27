"""
Stage 1: 答案生成脚本
使用 Qwen2.5-1.5B-Instruct 模型生成测试集的预测答案
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import torch
from tqdm import tqdm
import yaml

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from model_loader import ModelLoader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AnswerGenerator:
    """答案生成器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化答案生成器

        Args:
            config: 配置字典
        """
        self.config = config
        self.model = None
        self.tokenizer = None
        self.prompt_template = config.get('prompt_template', '问题：{question}\n答案：')

    def load_model(self):
        """加载模型"""
        loader = ModelLoader(self.config['model'])
        self.model, self.tokenizer = loader.load()
        logger.info("模型加载完成")

    def format_prompt(self, question: str) -> str:
        """
        格式化prompt

        Args:
            question: 问题文本

        Returns:
            格式化后的prompt
        """
        return self.prompt_template.format(question=question)

    def generate_answer(self, question: str) -> str:
        """
        生成单个问题的答案

        Args:
            question: 问题文本

        Returns:
            生成的答案
        """
        prompt = self.format_prompt(question)

        # 使用chat模板
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # Tokenize
        inputs = self.tokenizer(text, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        # 生成参数
        gen_config = self.config.get('generation', {})

        # 生成
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=gen_config.get('max_new_tokens', 256),
                temperature=gen_config.get('temperature', 0.1),
                top_p=gen_config.get('top_p', 0.9),
                top_k=gen_config.get('top_k', 50),
                do_sample=gen_config.get('do_sample', True),
                repetition_penalty=gen_config.get('repetition_penalty', 1.1),
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )

        # 解码
        generated_text = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:],
            skip_special_tokens=True
        )

        return generated_text.strip()

    def load_test_data(self, input_file: str) -> List[Dict[str, Any]]:
        """
        加载测试数据

        Args:
            input_file: 输入文件路径

        Returns:
            测试数据列表
        """
        data = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
        logger.info(f"加载了 {len(data)} 条测试数据")
        return data

    def run(self):
        """运行答案生成"""
        # 加载模型
        self.load_model()

        # 加载测试数据
        data_config = self.config.get('data', {})
        input_file = data_config.get('input_file', '../../data/splits/test.jsonl')
        output_file = data_config.get('output_file', './outputs/predictions.jsonl')

        test_data = self.load_test_data(input_file)

        # 生成答案
        predictions = []
        save_interval = self.config.get('logging', {}).get('save_interval', 50)

        logger.info("开始生成答案...")

        for i, item in enumerate(tqdm(test_data, desc="生成中")):
            try:
                prediction = self.generate_answer(item['question'])

                result = {
                    "id": item.get('id', f'item_{i}'),
                    "question": item['question'],
                    "reference": item.get('answer', ''),
                    "prediction": prediction,
                    "spatial_type": item.get('spatial_relation_type', 'unknown'),
                    "difficulty": item.get('difficulty', 'unknown')
                }
                predictions.append(result)

                # 定期保存
                if (i + 1) % save_interval == 0:
                    self._save_predictions(predictions, output_file)
                    logger.info(f"已处理 {i + 1}/{len(test_data)} 条，已保存")

            except Exception as e:
                logger.error(f"处理第 {i} 条数据时出错: {e}")
                predictions.append({
                    "id": item.get('id', f'item_{i}'),
                    "question": item['question'],
                    "reference": item.get('answer', ''),
                    "prediction": f"ERROR: {str(e)}",
                    "spatial_type": item.get('spatial_relation_type', 'unknown'),
                    "difficulty": item.get('difficulty', 'unknown')
                })

        # 最终保存
        self._save_predictions(predictions, output_file)
        logger.info(f"答案生成完成！共 {len(predictions)} 条，保存至: {output_file}")

        return predictions

    def _save_predictions(self, predictions: List[Dict], output_file: str):
        """保存预测结果"""
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            for item in predictions:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description='Stage 1: 答案生成')
    parser.add_argument(
        '--config',
        type=str,
        default='config/generation_config.yaml',
        help='配置文件路径'
    )
    args = parser.parse_args()

    # 加载配置
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 创建生成器并运行
    generator = AnswerGenerator(config)
    generator.run()


if __name__ == "__main__":
    main()
