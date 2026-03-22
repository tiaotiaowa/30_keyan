"""
GLM-4.7 API 客户端

功能:
- API调用和认证 (使用zai-sdk)
- 批量处理
- 错误重试机制
- 断点续传

更新时间: 2026-03-16
修复: 升级到zai-sdk，增强错误处理
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Callable
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 配置日志
logger = logging.getLogger(__name__)

try:
    from zai import ZhipuAiClient
    from zai.errors import APIError, APIConnectionError, RateLimitError
except ImportError:
    print("错误: 请安装zai-sdk库: pip install zai-sdk")
    print("验证安装: python -c \"import zai; print(zai.__version__)\"")
    sys.exit(1)


class GLM47Client:
    """GLM-4.7 API客户端 (使用zai-sdk)"""

    def __init__(self, config: dict):
        """
        初始化客户端

        Args:
            config: 配置字典，包含api、generation、batch等配置
        """
        self.config = config

        # 初始化API客户端 (使用新版zai-sdk)
        api_key = os.getenv(config['api']['api_key_env'])
        if not api_key:
            raise ValueError(f"请设置环境变量 {config['api']['api_key_env']}")

        self.client = ZhipuAiClient(api_key=api_key)
        self.model = config['api']['model']
        logger.info(f"GLM客户端初始化成功，模型: {self.model}")

        # 批处理配置
        self.batch_size = config['batch']['batch_size']
        self.delay = config['batch']['delay_between_requests']
        self.checkpoint_interval = config['batch']['checkpoint_interval']

        # 重试配置
        self.max_retries = config['api']['max_retries']
        self.retry_delay = config['api']['retry_delay']

        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens': 0
        }

    def generate(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        生成回复

        Args:
            messages: 消息列表
            temperature: 温度参数（可选，覆盖配置）
            top_p: top_p参数（可选，覆盖配置）
            max_tokens: 最大token数（可选，覆盖配置）

        Returns:
            生成的文本
        """
        # 合并配置
        gen_config = self.config['generation'].copy()
        if temperature is not None:
            gen_config['temperature'] = temperature
        if top_p is not None:
            gen_config['top_p'] = top_p
        if max_tokens is not None:
            gen_config['max_tokens'] = max_tokens

        for attempt in range(self.max_retries):
            try:
                self.stats['total_requests'] += 1

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=gen_config['temperature'],
                    top_p=gen_config['top_p'],
                    max_tokens=gen_config['max_tokens']
                )

                self.stats['successful_requests'] += 1

                # 记录token使用
                if hasattr(response, 'usage'):
                    self.stats['total_tokens'] += response.usage.total_tokens

                return response.choices[0].message.content

            except RateLimitError as e:
                self.stats['failed_requests'] += 1
                wait_time = self.retry_delay * (2 ** attempt) * 2  # 限流时加倍等待
                logger.warning(f"请求限流，{wait_time}秒后重试 (尝试 {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    time.sleep(wait_time)
                else:
                    logger.error(f"请求限流，已达最大重试次数: {e}")
                    return f"[API_ERROR] RateLimitError: {e}"

            except APIConnectionError as e:
                self.stats['failed_requests'] += 1
                logger.warning(f"网络连接错误，{self.retry_delay}秒后重试 (尝试 {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"网络连接错误，已达最大重试次数: {e}")
                    return f"[API_ERROR] APIConnectionError: {e}"

            except APIError as e:
                self.stats['failed_requests'] += 1
                logger.error(f"API错误: {e}")
                return f"[API_ERROR] APIError: {e}"

            except Exception as e:
                self.stats['failed_requests'] += 1
                error_msg = str(e)
                logger.error(f"未知错误: {error_msg}")

                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"请求失败，{wait_time}秒后重试 (尝试 {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                else:
                    return f"[API_ERROR] {error_msg}"

        return "[API_ERROR] Max retries exceeded"

    def batch_generate(
        self,
        data_list: List[Dict],
        prompt_formatter: Callable,
        checkpoint_path: Optional[Path] = None,
        resume: bool = True
    ) -> List[Dict]:
        """
        批量生成

        Args:
            data_list: 数据列表，每项包含id, question等字段
            prompt_formatter: Prompt格式化函数
            checkpoint_path: checkpoint保存路径
            resume: 是否从checkpoint恢复

        Returns:
            结果列表，每项包含id, question, prediction, reference等
        """
        results = []
        start_idx = 0

        # 检查是否需要从checkpoint恢复
        if resume and checkpoint_path and checkpoint_path.exists():
            print(f"从checkpoint恢复: {checkpoint_path}")
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))
            start_idx = len(results)
            print(f"已恢复 {start_idx} 条结果")

        total = len(data_list)
        print(f"开始处理，共 {total} 条，从第 {start_idx + 1} 条开始")

        # 处理剩余数据
        for i in range(start_idx, total):
            item = data_list[i]

            # 格式化Prompt
            messages = prompt_formatter(item['question'])

            # 调用API
            prediction = self.generate(messages)

            # 保存结果
            result = {
                'id': item.get('id', f'item_{i}'),
                'question': item['question'],
                'reference': item.get('answer', ''),
                'prediction': prediction,
                'spatial_type': item.get('spatial_relation_type', 'unknown'),
                'difficulty': item.get('difficulty', 'unknown')
            }
            results.append(result)

            # 请求间隔
            time.sleep(self.delay)

            # 进度显示
            if (i + 1) % 10 == 0:
                print(f"进度: {i + 1}/{total} ({(i+1)/total*100:.1f}%)")

            # 保存checkpoint
            if checkpoint_path and (i + 1) % self.checkpoint_interval == 0:
                self._save_checkpoint(results, checkpoint_path)
                print(f"Checkpoint已保存: {i + 1} 条")

        # 最终保存
        if checkpoint_path:
            self._save_checkpoint(results, checkpoint_path)

        print(f"\n处理完成: {len(results)} 条")
        print(f"统计: 成功 {self.stats['successful_requests']}, 失败 {self.stats['failed_requests']}")

        return results

    def _save_checkpoint(self, results: List[Dict], path: Path):
        """保存checkpoint"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.stats.copy()


def test_api_connection():
    """测试API连接"""
    print("="*60)
    print("测试 GLM-4.7 API 连接 (zai-sdk)")
    print("="*60)

    # 检查API密钥
    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        print("错误: 请设置环境变量 ZHIPUAI_API_KEY")
        return False

    print(f"API密钥已设置: {api_key[:10]}...")

    # 初始化客户端
    config = {
        'api': {
            'model': 'glm-4.7',
            'api_key_env': 'ZHIPUAI_API_KEY',
            'timeout': 60,
            'max_retries': 3,
            'retry_delay': 5
        },
        'generation': {
            'temperature': 0.1,
            'top_p': 0.9,
            'max_tokens': 512
        },
        'batch': {
            'batch_size': 10,
            'delay_between_requests': 0.5,
            'checkpoint_interval': 50
        }
    }

    try:
        client = GLM47Client(config)
        print("客户端初始化成功 (zai-sdk)")
    except Exception as e:
        print(f"客户端初始化失败: {e}")
        return False

    # 测试简单请求
    test_messages = [
        {"role": "user", "content": "请用一句话回答：北京位于中国的哪个方向？"}
    ]

    print("\n发送测试请求...")
    response = client.generate(test_messages)

    print(f"\n响应: {response}")
    print(f"\n统计: {client.get_stats()}")

    return not response.startswith("[API_ERROR]")


if __name__ == "__main__":
    success = test_api_connection()
    sys.exit(0 if success else 1)
