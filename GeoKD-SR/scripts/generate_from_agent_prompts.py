#!/usr/bin/env python3
"""
从划分后的提示词文件生成数据
用于并行Agent执行

用法:
python scripts/generate_from_agent_prompts.py \
    --prompts-file data/prompts/agent_splits/agent1_prompts.json \
    --output data/geosr_chain/supplement/agent1_output_v2.jsonl \
    --checkpoint data/geosr_chain/supplement/agent1_progress_v2.json
"""

import os
import sys
import io
import json
import time
import random
import argparse
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
import traceback

# Setup UTF-8 encoding for Windows console
if sys.platform == 'win32':
    try:
        if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        if not isinstance(sys.stderr, io.TextIOWrapper) or sys.stderr.encoding != 'utf-8':
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================================
# Constants
# ================================

MODEL_NAME = "glm-4.7"
API_KEY = "90fec3d49a8c40babbacecc617b34cf3.i4lMb9sTCUQlHKMw"
BASE_URL = "https://open.bigmodel.cn/api/anthropic"

# 超时和重试配置
REQUEST_TIMEOUT = 180
MAX_RETRIES = 5
BASE_RETRY_DELAY = 30
RATE_LIMIT_DELAY = 300
BATCH_DELAY = 3
CHECKPOINT_INTERVAL = 5

# 专家系统提示词
SYSTEM_PROMPT = """你是一位资深的地理空间数据集设计专家，拥有以下专业能力：
1. 精通中国地理知识，包括省市区划、山川河流、地标建筑等
2. 擅长设计多层次、多维度的地理空间推理问题
3. 能够根据不同难度级别设计相应复杂度的地理问题
4. 熟悉拓扑关系（包含、相邻、重叠、相离等）的空间推理

你的任务是设计高质量的地理空间推理数据集，确保：
- 问题表述多样化和自然化
- 不同难度的问题具有明显的复杂度差异
- 推理过程清晰、逻辑严密
- 地理信息准确、坐标数据合理
"""

DIVERSITY_REQUIREMENTS = """
【问题多样性要求】

1. **问句结构多样性**（至少使用以下5种模式）：
   - 是否型
   - 判断型
   - 推理型
   - 描述型
   - 应用型

2. **背景信息多样性**（根据难度调整）：
   - Easy: 简短上下文
   - Medium: 包含实体类型、地理特征
   - Hard: 丰富背景描述、多实体关联

3. **语言表达多样性**：
   - 避免重复使用相同的句式
   - 使用同义词变换
   - 结合具体地理特征描述
"""


# ================================
# ProgressManager Class
# ================================

@dataclass
class ProgressState:
    """进度状态"""
    start_time: str = None
    last_update: str = None
    total_target: int = 0
    total_generated: int = 0
    total_failed: int = 0
    agent_name: str = ""
    completed_prompt_ids: List[str] = field(default_factory=list)
    failed_prompt_ids: List[str] = field(default_factory=list)
    errors: List[Dict] = field(default_factory=list)


class ProgressManager:
    """进度管理器 - 断点续传"""

    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = Path(checkpoint_file)
        self.state = self._load_progress()

    def _load_progress(self) -> ProgressState:
        """加载进度"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                state = ProgressState(
                    start_time=data.get('start_time'),
                    last_update=data.get('last_update'),
                    total_target=data.get('total_target', 0),
                    total_generated=data.get('total_generated', 0),
                    total_failed=data.get('total_failed', 0),
                    agent_name=data.get('agent_name', ''),
                    completed_prompt_ids=data.get('completed_prompt_ids', []),
                    failed_prompt_ids=data.get('failed_prompt_ids', []),
                    errors=data.get('errors', [])
                )
                logger.info(f"加载进度: 已生成 {state.total_generated} 条, 失败 {state.total_failed} 条")
                return state
            except Exception as e:
                logger.warning(f"加载进度失败: {e}")

        return ProgressState(start_time=datetime.now().isoformat())

    def save_progress(self):
        """保存进度"""
        self.state.last_update = datetime.now().isoformat()
        try:
            self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.state), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存进度失败: {e}")

    def is_completed(self, prompt_id: str) -> bool:
        """检查提示词是否已完成"""
        return prompt_id in self.state.completed_prompt_ids

    def mark_completed(self, prompt_id: str):
        """标记完成"""
        self.state.completed_prompt_ids.append(prompt_id)
        self.state.total_generated += 1

    def mark_failed(self, prompt_id: str, error: str):
        """标记失败"""
        self.state.failed_prompt_ids.append(prompt_id)
        self.state.total_failed += 1
        self.state.errors.append({
            "prompt_id": prompt_id,
            "error": error,
            "time": datetime.now().isoformat()
        })


# ================================
# GLMClient Class
# ================================

class GLMClient:
    """GLM API客户端 - 使用ANTHROPIC兼容接口"""

    def __init__(self, api_key: str = API_KEY, model: str = MODEL_NAME, base_url: str = BASE_URL):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0

        logger.info(f"GLM客户端初始化: model={model}, base_url={base_url}")

    def generate(self, prompt: str, max_tokens: int = 8192, temperature: float = 0.95) -> Optional[str]:
        """生成响应 - 带超时和重试机制"""
        if not prompt:
            return None

        self._request_count += 1

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"API调用 (attempt {attempt + 1}/{MAX_RETRIES})")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False
                )

                if response.choices and len(response.choices) > 0:
                    message = response.choices[0].message

                    content = None
                    if hasattr(message, 'content') and message.content:
                        content = message.content

                    if content:
                        self._success_count += 1
                        return content

                logger.warning("API返回空响应")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BASE_RETRY_DELAY)
                    continue

            except Exception as e:
                self._error_count += 1
                error_msg = str(e)

                if "429" in error_msg or "APIReachLimitError" in error_msg or "rate limit" in error_msg.lower():
                    wait_time = RATE_LIMIT_DELAY * (attempt + 1)
                    logger.warning(f"API限流，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue

                logger.error(f"API调用失败 (attempt {attempt + 1}): {error_msg}")

                if attempt < MAX_RETRIES - 1:
                    sleep_time = BASE_RETRY_DELAY * (attempt + 1)
                    logger.info(f"等待 {sleep_time} 秒后重试...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"API调用失败，已达最大重试次数")
                    return None

        return None

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "requests": self._request_count,
            "success": self._success_count,
            "errors": self._error_count
        }


# ================================
# TopologyDataGenerator Class
# ================================

class TopologyDataGenerator:
    """拓扑数据生成器 - 支持从划分文件读取"""

    def __init__(self, prompts_file: str, output_file: str, checkpoint_file: str):
        self.prompts_file = Path(prompts_file)
        self.output_file = Path(output_file)
        self.checkpoint_file = Path(checkpoint_file)

        # 创建输出目录
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # 初始化客户端和进度管理器
        self.client = GLMClient()
        self.progress = ProgressManager(checkpoint_file)

        # 加载提示词
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> List[dict]:
        """加载提示词"""
        with open(self.prompts_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        metadata = data.get('metadata', {})
        self.progress.state.agent_name = metadata.get('agent', 'unknown')
        self.progress.state.total_target = metadata.get('total_count', 0)

        prompts = data.get('prompts', [])
        logger.info(f"加载提示词: {len(prompts)} 条 (Agent: {self.progress.state.agent_name})")
        return prompts

    def _build_batch_prompt(self, prompts: List[dict]) -> str:
        """构建批量生成提示词 - 增强版"""
        prompt_text = f"""{SYSTEM_PROMPT}

{DIVERSITY_REQUIREMENTS}

请按照以下要求生成{len(prompts)}条地理空间推理数据：

---

"""
        for i, p in enumerate(prompts, 1):
            e1 = p.get('entity1', {})
            e2 = p.get('entity2', {})
            diff = p.get('difficulty', 'medium')

            # 根据难度设置问题长度要求
            length_req = {
                'easy': '30-50字符',
                'medium': '50-100字符',
                'hard': '80-150字符'
            }.get(diff, '50-100字符')

            prompt_text += f"""【数据{i}】
- 实体1: {e1.get('name', '')} ({e1.get('type', '')})，坐标: {e1.get('coords', [])}
- 实体2: {e2.get('name', '')} ({e2.get('type', '')})，坐标: {e2.get('coords', [])}
- 拓扑子类型: {p.get('topology_subtype', '')}
- 难度: {diff}
- 要求Question长度: {length_req}

---

"""

        prompt_text += """
【输出格式要求】
每条数据使用以下JSON格式，数据之间用 "---DATA---" 分隔：

{
  "id": "geosr_topological_XXXXX_YYYY",
  "spatial_relation_type": "topological",
  "question": "根据难度生成相应复杂度的问题",
  "answer": "详细答案",
  "reasoning_chain": [
    {"step": 1, "name": "entity_identification", "action": "extract_entities", "content": "识别问题中的地理实体...", "entities_involved": ["实体1", "实体2"]},
    {"step": 2, "name": "spatial_relation_extraction", "action": "classify_relation", "content": "识别空间关系类型...", "relation_type": "topological"},
    {"step": 3, "name": "coordinate_retrieval", "action": "infer_entity_to_token", "content": "获取实体坐标信息...", "coordinates": {"实体1": [经度, 纬度], "实体2": [经度, 纬度]}},
    {"step": 4, "name": "spatial_calculation", "action": "determine_topology", "content": "判断拓扑关系...", "calculation_result": "具体结果"},
    {"step": 5, "name": "answer_generation", "action": "generate_answer", "content": "生成最终答案...", "final_answer": "最终答案"}
  ],
  "entities": [
    {"name": "实体1", "type": "类型", "coords": [经度, 纬度]},
    {"name": "实体2", "type": "类型", "coords": [经度, 纬度]}
  ],
  "spatial_tokens": ["空间关键词1", "空间关键词2", ...],
  "difficulty": "easy/medium/hard",
  "topology_subtype": "子类型",
  "difficulty_score": 1.0-5.0,
  "entity_to_token": {"实体1": {"char_start": X, "char_end": Y, "token_indices": [...]}, ...}
}

【关键约束】
1. 每条question必须使用不同的句式结构
2. reasoning_chain每步content至少20字符
3. 必须包含difficulty_score和entity_to_token字段
4. spatial_tokens包含4-8个空间关键词
"""

        return prompt_text

    def _extract_json_from_response(self, content: str) -> List[dict]:
        """从响应中提取JSON数据"""
        results = []

        # 尝试按分隔符分割
        parts = content.split("---DATA---")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 查找JSON对象
            brace_count = 0
            json_start = -1
            for i, char in enumerate(part):
                if char == '{':
                    if brace_count == 0:
                        json_start = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and json_start >= 0:
                        json_str = part[json_start:i+1]
                        try:
                            data = json.loads(json_str)
                            if self._validate_data(data):
                                results.append(data)
                        except json.JSONDecodeError:
                            pass
                        json_start = -1

        return results

    def _validate_data(self, data: dict) -> bool:
        """验证生成的数据"""
        required_fields = ["question", "answer", "reasoning_chain", "entities"]

        for field in required_fields:
            if field not in data:
                return False

        # 验证reasoning_chain
        chain = data.get("reasoning_chain", [])
        if len(chain) < 5:
            return False

        # 验证entities
        entities = data.get("entities", [])
        if len(entities) < 2:
            return False

        # 验证坐标
        for e in entities:
            if "coords" not in e:
                return False

        return True

    def generate_batch(self, prompts: List[dict], batch_size: int = 5) -> List[dict]:
        """批量生成数据"""
        batch_prompts = prompts[:batch_size]
        combined_prompt = self._build_batch_prompt(batch_prompts)

        # 调用API
        content = self.client.generate(combined_prompt)

        if not content:
            return []

        # 解析响应
        results = self._extract_json_from_response(content)

        # 为结果分配ID和补充字段
        final_results = []
        for i, result in enumerate(results):
            if i >= len(batch_prompts):
                break

            prompt = batch_prompts[i]

            # 生成新ID
            new_id = f"geosr_topological_{random.randint(10000, 99999)}_{random.randint(1000, 9999)}"
            result["id"] = new_id
            result["topology_subtype"] = prompt.get("topology_subtype")
            result["difficulty"] = prompt.get("difficulty", "medium")
            result["spatial_relation_type"] = "topological"
            result["prompt_id"] = prompt.get("id")
            result["split"] = "train"

            # 补充difficulty_score
            result["difficulty_score"] = self._calculate_difficulty_score(result)

            # 补充spatial_tokens
            if "spatial_tokens" not in result or not result["spatial_tokens"]:
                result["spatial_tokens"] = self._extract_spatial_tokens(result)

            # 补充entity_to_token
            if "entity_to_token" not in result or not result["entity_to_token"]:
                result["entity_to_token"] = self._create_entity_to_token(result)

            final_results.append(result)

        return final_results

    def _calculate_difficulty_score(self, record: dict) -> float:
        """计算难度分数"""
        subtype = record.get("topology_subtype", "within")
        base_scores = {
            "within": 2.2, "contains": 2.3, "adjacent": 2.5,
            "disjoint": 2.6, "overlap": 2.8
        }
        score = base_scores.get(subtype, 2.2)
        return min(max(round(score, 2), 1.0), 5.0)

    def _extract_spatial_tokens(self, record: dict) -> List[str]:
        """提取空间tokens"""
        tokens = set()
        text = record.get("question", "") + " " + record.get("answer", "")

        spatial_keywords = [
            'contain', 'located', 'inside', 'intersect', 'adjacent',
            'boundary', 'within', 'between', 'around', 'overlap', 'disjoint',
            '包含', '位于', '内部', '相邻', '边界', '重叠', '相离'
        ]

        for kw in spatial_keywords:
            if kw.lower() in text.lower() or kw in text:
                tokens.add(kw)

        return list(tokens)[:8]

    def _create_entity_to_token(self, record: dict) -> dict:
        """创建entity_to_token映射"""
        entity_to_token = {}
        entities = record.get("entities", [])
        question = record.get("question", "")

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            name = entity.get("name", "")
            if not name:
                continue

            char_start = question.find(name)
            if char_start >= 0:
                char_end = char_start + len(name)
                entity_to_token[name] = {
                    "char_start": char_start,
                    "char_end": char_end,
                    "token_indices": list(range(char_start, char_end + 1))
                }

        return entity_to_token

    def _append_to_output(self, results: List[dict]):
        """追加数据到输出文件"""
        with open(self.output_file, 'a', encoding='utf-8') as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')

    def generate_all(self, batch_size: int = 5):
        """生成所有数据"""
        total = len(self.prompts)
        print(f"\n{'=' * 60}")
        print(f"开始生成数据 - {self.progress.state.agent_name}")
        print(f"{'=' * 60}")
        print(f"模型: {MODEL_NAME}")
        print(f"目标总数: {total}")
        print(f"批次大小: {batch_size}")
        print(f"预计批次数: {(total + batch_size - 1) // batch_size}")
        print(f"已生成: {self.progress.state.total_generated}")
        print(f"{'=' * 60}\n")

        # 过滤已完成的提示词
        pending_prompts = [p for p in self.prompts
                          if p.get('id') not in self.progress.state.completed_prompt_ids]

        print(f"待处理: {len(pending_prompts)} 条")

        batch_count = 0
        prompt_index = 0

        while prompt_index < len(pending_prompts):
            batch_count += 1
            batch_prompts = pending_prompts[prompt_index:prompt_index + batch_size]
            prompt_index += batch_size

            print(f"\n  批次 {batch_count}: 生成 {len(batch_prompts)} 条...")

            try:
                results = self.generate_batch(batch_prompts, batch_size)

                if results:
                    # 保存结果
                    self._append_to_output(results)

                    # 更新进度
                    for r in results:
                        self.progress.mark_completed(r.get("prompt_id", ""))

                    print(f"    成功: {len(results)} 条, 累计: {self.progress.state.total_generated}/{total}")
                else:
                    # 标记失败
                    for p in batch_prompts:
                        self.progress.mark_failed(p.get("id", ""), "生成失败")
                    print(f"    失败: {len(batch_prompts)} 条")

                # 定期保存进度
                if batch_count % CHECKPOINT_INTERVAL == 0:
                    self.progress.save_progress()
                    print(f"    [进度已保存]")

            except Exception as e:
                logger.error(f"批次生成错误: {e}")
                traceback.print_exc()

            # 批次间延迟
            time.sleep(BATCH_DELAY)

        # 最终保存
        self.progress.save_progress()

        print(f"\n{'=' * 60}")
        print(f"生成完成! - {self.progress.state.agent_name}")
        print(f"{'=' * 60}")
        print(f"总生成: {self.progress.state.total_generated} 条")
        print(f"总失败: {self.progress.state.total_failed} 条")
        print(f"API统计: {self.client.stats}")
        print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description='从划分提示词文件生成拓扑数据')
    parser.add_argument('--prompts-file', type=str, required=True,
                        help='提示词文件路径')
    parser.add_argument('--batch-size', type=int, default=5,
                        help='每批生成数量（默认5）')
    parser.add_argument('--output', type=str, required=True,
                        help='输出文件路径')
    parser.add_argument('--checkpoint', type=str, required=True,
                        help='进度文件路径')

    args = parser.parse_args()

    # 创建生成器
    generator = TopologyDataGenerator(
        prompts_file=args.prompts_file,
        output_file=args.output,
        checkpoint_file=args.checkpoint
    )

    # 开始生成
    generator.generate_all(args.batch_size)


if __name__ == "__main__":
    main()
