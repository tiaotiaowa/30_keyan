# -*- coding: utf-8 -*-
"""
GLM-4.7 完整测试集回答生成脚本

功能:
- 批量调用 GLM-4.7 API 生成所有测试样本的预测
- 支持断点续传（checkpoint）
- 支持两种数据集: split_coords (含坐标) 和 splits (不含坐标)
- 进度显示和错误重试

用法:
    # 生成 splits 数据集
    python generate_all_predictions.py --dataset splits

    # 生成 split_coords 数据集
    python generate_all_predictions.py --dataset split_coords

    # 生成两个数据集
    python generate_all_predictions.py --dataset both

    # 从断点恢复
    python generate_all_predictions.py --dataset splits --resume

创建时间: 2026-03-17
"""

import os
import sys
import io
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 修复控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 设置 API Key
API_KEY = "809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW"
os.environ['ZHIPUAI_API_KEY'] = API_KEY

# 添加项目路径
SCRIPT_DIR = Path(__file__).parent  # exp/exp0/glm/scripts
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent  # GeoKD-SR 根目录
sys.path.insert(0, str(PROJECT_ROOT))

print(f"[DEBUG] 脚本目录: {SCRIPT_DIR}")
print(f"[DEBUG] 项目根目录: {PROJECT_ROOT}")

from zai import ZhipuAiClient

# 尝试导入错误类型（不同版本可能有差异）
try:
    from zai.errors import APIError, APIConnectionError, RateLimitError
except ImportError:
    # 如果无法导入特定错误类型，使用通用异常
    APIError = Exception
    APIConnectionError = Exception
    RateLimitError = Exception

# 尝试导入 tqdm
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("提示: 安装 tqdm 可获得更好的进度显示: pip install tqdm")


# ========================================
# 配置
# ========================================
CONFIG = {
    # API 配置
    "model": "glm-4.7",
    "max_tokens": 2048,
    "temperature": 0.1,
    "top_p": 0.9,

    # 批处理配置
    "delay_between_requests": 0.5,  # 请求间隔(秒)
    "checkpoint_interval": 50,      # 每50条保存checkpoint
    "max_retries": 3,               # 最大重试次数
    "retry_delay": 5,               # 重试延迟(秒)

    # 数据路径
    "data_dir": PROJECT_ROOT / "data",
    "output_dir": PROJECT_ROOT / "exp" / "exp0" / "glm" / "predictions",
}


# ========================================
# Prompt 模板
# ========================================
def format_inference_prompt(question: str) -> List[Dict]:
    """格式化推理 Prompt"""
    return [
        {
            "role": "user",
            "content": f"""你是一个地理空间推理专家。请根据问题给出准确、简洁的答案。

问题: {question}

请直接给出答案，不需要解释过程。答案格式要求：
- 方向问题：直接说明方向，如"东南方向"
- 距离问题：给出具体数值，如"约1200公里"
- 拓扑问题：明确说明关系，如"是的，XX位于YY内部"
- 复合问题：同时给出方向和距离

答案:"""
        }
    ]


# ========================================
# API 客户端
# ========================================
class GLM47Generator:
    """GLM-4.7 批量生成器"""

    def __init__(self, config: dict):
        self.config = config
        self.client = ZhipuAiClient(api_key=API_KEY)
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens': 0,
            'start_time': None,
            'end_time': None
        }

    def generate_single(self, messages: List[Dict]) -> str:
        """生成单条回复"""
        for attempt in range(self.config['max_retries']):
            try:
                self.stats['total_requests'] += 1

                response = self.client.chat.completions.create(
                    model=self.config['model'],
                    messages=messages,
                    max_tokens=self.config['max_tokens'],
                    temperature=self.config['temperature'],
                    top_p=self.config['top_p'],
                )

                self.stats['successful_requests'] += 1

                # 记录 token 使用
                if hasattr(response, 'usage'):
                    self.stats['total_tokens'] += response.usage.total_tokens

                return  response.choices[0].message.content 

            except RateLimitError as e:
                self.stats['failed_requests'] += 1
                wait_time = self.config['retry_delay'] * (2 ** attempt) * 2
                print(f"\n[限流] 等待 {wait_time}秒后重试 ({attempt + 1}/{self.config['max_retries']})")

                if attempt < self.config['max_retries'] - 1:
                    time.sleep(wait_time)
                else:
                    return f"[API_ERROR] RateLimitError: {e}"

            except APIConnectionError as e:
                self.stats['failed_requests'] += 1
                print(f"\n[连接错误] {self.config['retry_delay']}秒后重试 ({attempt + 1}/{self.config['max_retries']})")

                if attempt < self.config['max_retries'] - 1:
                    time.sleep(self.config['retry_delay'])
                else:
                    return f"[API_ERROR] APIConnectionError: {e}"

            except APIError as e:
                self.stats['failed_requests'] += 1
                return f"[API_ERROR] APIError: {e}"

            except Exception as e:
                self.stats['failed_requests'] += 1
                if attempt < self.config['max_retries'] - 1:
                    wait_time = self.config['retry_delay'] * (2 ** attempt)
                    print(f"\n[未知错误] {wait_time}秒后重试: {e}")
                    time.sleep(wait_time)
                else:
                    return f"[API_ERROR] {e}"

        return "[API_ERROR] Max retries exceeded"

    def generate_batch(
        self,
        data: List[Dict],
        output_path: Path,
        checkpoint_path: Optional[Path] = None,
        resume: bool = True
    ) -> List[Dict]:
        """批量生成"""
        results = []
        start_idx = 0

        # 检查是否需要从 checkpoint 恢复
        if resume and checkpoint_path and checkpoint_path.exists():
            print(f"\n从 checkpoint 恢复: {checkpoint_path}")
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))
            start_idx = len(results)
            print(f"已恢复 {start_idx} 条结果")

        total = len(data)
        print(f"\n开始处理: 共 {total} 条，从第 {start_idx + 1} 条开始")
        print(f"模型: {self.config['model']}")
        print(f"输出文件: {output_path}")

        self.stats['start_time'] = datetime.now()

        # 使用 tqdm 进度条
        iterator = range(start_idx, total)
        if HAS_TQDM:
            iterator = tqdm(iterator, desc="生成进度", unit="条", ncols=100)

        # 处理每条数据
        for i in iterator:
            item = data[i]

            # 格式化 Prompt
            messages = format_inference_prompt(item['question'])

            # 调用 API
            prediction = self.generate_single(messages)

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
            time.sleep(self.config['delay_between_requests'])

            # 进度显示 (非 tqdm 模式)
            if not HAS_TQDM and (i + 1) % 10 == 0:
                elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
                rate = (i + 1 - start_idx) / elapsed if elapsed > 0 else 0
                eta = (total - i - 1) / rate / 60 if rate > 0 else 0
                print(f"进度: {i + 1}/{total} ({(i+1)/total*100:.1f}%) | 速度: {rate:.2f}条/秒 | 预计剩余: {eta:.1f}分钟")

            # 保存 checkpoint
            if checkpoint_path and (i + 1) % self.config['checkpoint_interval'] == 0:
                self._save_checkpoint(results, checkpoint_path)
                if not HAS_TQDM:
                    print(f"Checkpoint 已保存: {i + 1} 条")

        # 最终保存
        self._save_results(results, output_path)
        self.stats['end_time'] = datetime.now()

        # 删除 checkpoint
        if checkpoint_path and checkpoint_path.exists():
            checkpoint_path.unlink()
            print(f"\nCheckpoint 已清理")

        print(f"\n生成完成: {len(results)} 条")
        return results

    def _save_checkpoint(self, results: List[Dict], path: Path):
        """保存 checkpoint"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

    def _save_results(self, results: List[Dict], path: Path):
        """保存最终结果"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        print(f"\n结果已保存: {path}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = self.stats.copy()
        if stats['start_time'] and stats['end_time']:
            stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()
        return stats


# ========================================
# 数据加载
# ========================================
def load_test_data(file_path: Path) -> List[Dict]:
    """加载测试数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


# ========================================
# 主函数
# ========================================
def main():
    parser = argparse.ArgumentParser(description="GLM-4.7 测试集回答生成")
    parser.add_argument(
        "--dataset",
        choices=["split_coords", "splits", "both"],
        default="splits",
        help="要处理的数据集"
    )
    parser.add_argument("--resume", action="store_true", help="从 checkpoint 恢复")
    parser.add_argument("--sample_size", type=int, default=None, help="采样数量(测试用)")
    args = parser.parse_args()

    print("=" * 70)
    print("GLM-4.7 测试集回答生成")
    print("=" * 70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据集: {args.dataset}")
    print(f"恢复模式: {args.resume}")
    print(f"采样数量: {args.sample_size or '全量'}")

    # 初始化生成器
    generator = GLM47Generator(CONFIG)

    # 创建输出目录
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = CONFIG['output_dir'] / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    # 确定要处理的数据集
    datasets = []
    data_dir = CONFIG['data_dir']

    if args.dataset in ["split_coords", "both"]:
        datasets.append(("split_coords", data_dir / "split_coords" / "test.jsonl"))
    if args.dataset in ["splits", "both"]:
        datasets.append(("splits", data_dir / "splits" / "test.jsonl"))

    # 处理每个数据集
    for name, path in datasets:
        print(f"\n{'#'*70}")
        print(f"# 数据集: {name}")
        print(f"{'#'*70}")

        if not path.exists():
            print(f"错误: 数据文件不存在 - {path}")
            continue

        # 加载数据
        data = load_test_data(path)
        print(f"加载样本数: {len(data)}")

        if args.sample_size:
            data = data[:args.sample_size]
            print(f"采样后样本数: {len(data)}")

        # 设置输出路径
        output_path = output_dir / f"predictions_{name}.jsonl"
        checkpoint_path = output_dir / f"checkpoint_{name}.jsonl"

        # 生成
        results = generator.generate_batch(
            data,
            output_path,
            checkpoint_path,
            resume=args.resume
        )

    # 打印统计
    stats = generator.get_stats()
    print("\n" + "=" * 70)
    print("生成统计")
    print("=" * 70)
    print(f"总请求数: {stats['total_requests']}")
    print(f"成功请求: {stats['successful_requests']}")
    print(f"失败请求: {stats['failed_requests']}")
    print(f"总 Token 数: {stats['total_tokens']}")

    if 'duration' in stats:
        print(f"总耗时: {stats['duration']:.1f} 秒 ({stats['duration']/60:.1f} 分钟)")
        print(f"平均速度: {stats['successful_requests']/stats['duration']:.2f} 条/秒")

    print(f"\n输出目录: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
