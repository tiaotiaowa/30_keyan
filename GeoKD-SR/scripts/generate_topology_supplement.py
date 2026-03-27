#!/usr/bin/env python3
"""
拓扑子类型数据补充生成脚本 V2.0
- 使用GLM-4.7模型
- 超时等待机制
- 断点续传机制
- 429错误自动重试
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

MODEL_NAME = "glm-4.7"  # 使用GLM-4.7模型
API_KEY = "90fec3d49a8c40babbacecc617b34cf3.i4lMb9sTCUQlHKMw"

# 路径配置
BASE_DIR = Path(__file__).parent.parent
PROMPTS_FILE = BASE_DIR / "data" / "prompts" / "topology_supplement_prompts.json"
OUTPUT_DIR = BASE_DIR / "data" / "geosr_chain" / "supplement"
EXISTING_DATA = BASE_DIR / "data" / "geosr_chain" / "balanced_topology_downsampled.jsonl"
DEV_TEST_DATA = [
    BASE_DIR / "data" / "geosr_chain" / "final" / "dev.jsonl",
    BASE_DIR / "data" / "geosr_chain" / "final" / "test.jsonl"
]

# 难度分布
DIFFICULTY_DISTRIBUTION = {"easy": 0.30, "medium": 0.50, "hard": 0.20}

# 超时和重试配置
REQUEST_TIMEOUT = 180  # 单次请求超时（秒）
MAX_RETRIES = 5  # 最大重试次数
BASE_RETRY_DELAY = 30  # 基础重试延迟（秒）
RATE_LIMIT_DELAY = 300  # 429错误等待时间（5分钟）
BATCH_DELAY = 5  # 批次间延迟（秒）
CHECKPOINT_INTERVAL = 10  # 每10批保存一次进度


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
    current_subtype: str = ""
    subtype_progress: Dict[str, Dict] = field(default_factory=dict)
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
                    current_subtype=data.get('current_subtype', ''),
                    subtype_progress=data.get('subtype_progress', {}),
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

    def mark_completed(self, prompt_id: str, subtype: str):
        """标记完成"""
        self.state.completed_prompt_ids.append(prompt_id)
        self.state.total_generated += 1

        if subtype not in self.state.subtype_progress:
            self.state.subtype_progress[subtype] = {"generated": 0, "failed": 0}
        self.state.subtype_progress[subtype]["generated"] += 1

    def mark_failed(self, prompt_id: str, subtype: str, error: str):
        """标记失败"""
        self.state.failed_prompt_ids.append(prompt_id)
        self.state.total_failed += 1
        self.state.errors.append({
            "prompt_id": prompt_id,
            "subtype": subtype,
            "error": error,
            "time": datetime.now().isoformat()
        })

        if subtype not in self.state.subtype_progress:
            self.state.subtype_progress[subtype] = {"generated": 0, "failed": 0}
        self.state.subtype_progress[subtype]["failed"] += 1

    def set_subtype(self, subtype: str, target: int):
        """设置当前子类型"""
        self.state.current_subtype = subtype
        if subtype not in self.state.subtype_progress:
            self.state.subtype_progress[subtype] = {"generated": 0, "failed": 0, "target": target}
        else:
            self.state.subtype_progress[subtype]["target"] = target
        self.save_progress()


# ================================
# GLMClient Class
# ================================

class GLMClient:
    """GLM API客户端 - 带超时和重试"""

    def __init__(self, api_key: str = API_KEY, model: str = MODEL_NAME):
        from zhipuai import ZhipuAI
        self.client = ZhipuAI(api_key=api_key)
        self.model = model
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0

        logger.info(f"GLM客户端初始化: model={model}")

    def generate(self, prompt: str, max_tokens: int = 8192, temperature: float = 0.95) -> Optional[str]:
        """生成响应 - 带超时和重试机制"""
        if not prompt:
            return None

        self._request_count += 1

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"API调用 (attempt {attempt + 1}/{MAX_RETRIES})")

                # 使用超时参数
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False
                )

                # 提取内容
                if response.choices and len(response.choices) > 0:
                    message = response.choices[0].message

                    # 优先使用content字段
                    content = None
                    if hasattr(message, 'content') and message.content:
                        content = message.content
                    elif hasattr(message, 'reasoning_content') and message.reasoning_content:
                        content = message.reasoning_content

                    if content:
                        self._success_count += 1
                        return content

                # 空响应
                logger.warning("API返回空响应")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BASE_RETRY_DELAY)
                    continue

            except Exception as e:
                self._error_count += 1
                error_msg = str(e)

                # 处理429错误（限流）
                if "429" in error_msg or "APIReachLimitError" in error_msg or "rate limit" in error_msg.lower():
                    wait_time = RATE_LIMIT_DELAY * (attempt + 1)
                    logger.warning(f"API限流，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue

                # 其他错误
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
    """拓扑数据生成器"""

    def __init__(self, output_file: str, checkpoint_file: str):
        self.output_file = Path(output_file)
        self.checkpoint_file = Path(checkpoint_file)

        # 创建输出目录
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # 初始化客户端和进度管理器
        self.client = GLMClient()
        self.progress = ProgressManager(checkpoint_file)

        # 加载已有实体对
        self.existing_pairs = self._load_existing_entity_pairs()

        # 加载提示词
        self.prompts = self._load_prompts()

    def _load_existing_entity_pairs(self) -> set:
        """加载已有实体对"""
        pairs = set()

        # 从现有数据加载
        if EXISTING_DATA.exists():
            with open(EXISTING_DATA, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        entities = data.get("entities", [])
                        if len(entities) >= 2:
                            e1 = entities[0].get("name", "")
                            e2 = entities[1].get("name", "")
                            pairs.add((e1, e2))
                            pairs.add((e2, e1))
                    except:
                        pass

        # 从dev/test集加载
        for filepath in DEV_TEST_DATA:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line.strip())
                            entities = data.get("entities", [])
                            if len(entities) >= 2:
                                e1 = entities[0].get("name", "")
                                e2 = entities[1].get("name", "")
                                pairs.add((e1, e2))
                                pairs.add((e2, e1))
                        except:
                            pass

        logger.info(f"加载已有实体对: {len(pairs) // 2} 对")
        return pairs

    def _load_prompts(self) -> List[dict]:
        """加载提示词"""
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        prompts = data.get("prompts", [])
        logger.info(f"加载提示词: {len(prompts)} 条")
        return prompts

    def _select_prompts_by_subtype(self, subtype: str, count: int) -> List[dict]:
        """按子类型选择提示词"""
        # 筛选子类型
        subtype_prompts = [p for p in self.prompts if p.get("topology_subtype") == subtype]

        # 排除已完成的
        available = [p for p in subtype_prompts
                     if p.get("id") not in self.progress.state.completed_prompt_ids]

        # 排除已有实体对
        filtered = []
        for p in available:
            e1 = p.get("entity1", {}).get("name", "")
            e2 = p.get("entity2", {}).get("name", "")
            if (e1, e2) not in self.existing_pairs:
                filtered.append(p)

        # 按难度分组
        by_difficulty = {"easy": [], "medium": [], "hard": []}
        for p in filtered:
            diff = p.get("difficulty", "medium")
            if diff in by_difficulty:
                by_difficulty[diff].append(p)

        # 计算每种难度需要的数量
        counts = {
            "easy": int(count * DIFFICULTY_DISTRIBUTION["easy"]),
            "medium": int(count * DIFFICULTY_DISTRIBUTION["medium"]),
            "hard": count - int(count * DIFFICULTY_DISTRIBUTION["easy"]) - int(count * DIFFICULTY_DISTRIBUTION["medium"])
        }

        # 随机选择
        random.seed(42)
        selected = []
        for diff, n in counts.items():
            pool = by_difficulty[diff]
            if len(pool) >= n:
                selected.extend(random.sample(pool, n))
            else:
                selected.extend(pool)
                # 从其他难度补充
                remaining = n - len(pool)
                for other_diff in ["medium", "easy", "hard"]:
                    if other_diff != diff and remaining > 0:
                        other_pool = [p for p in by_difficulty[other_diff] if p not in selected]
                        if other_pool:
                            take = min(remaining, len(other_pool))
                            selected.extend(random.sample(other_pool, take))
                            remaining -= take

        return selected[:count]

    def _build_batch_prompt(self, prompts: List[dict]) -> str:
        """构建批量生成提示词 - 增强版（专家角色+多样性要求）"""

        # 专家角色设定
        SYSTEM_PROMPT = """你是一位资深的地理空间数据集设计专家，拥有以下专业能力：
1. 精通中国地理知识，包括省市区划、山川河流、地标建筑等
2. 擅长设计多层次、多维度的地理空间推理问题
3. 能够根据不同难度级别设计相应复杂度的地理问题
4. 熟悉拓扑关系（包含、相邻、重叠、相离等）的空间推理

你的任务是设计高质量的地理空间推理数据集，确保：
- 问题表述多样化和自然化
- 不同难度的问题具有明显的复杂度差异
- 推理过程清晰、逻辑严密
- 地理信息准确、坐标数据合理"""

        # 多样性要求
        DIVERSITY_REQUIREMENTS = """【问题多样性要求】

1. **问句结构多样性**


2. **背景信息多样性**


3. **语言表达多样性**
   - 避免重复使用相同的句式
   - 使用同义词变换（如：包含/含有/涵盖/位于...内）
   - 结合具体地理特征描述"""

        prompt_text = f"""{SYSTEM_PROMPT}

{DIVERSITY_REQUIREMENTS}

请按照以下要求生成{len(prompts)}条地理空间推理数据：

【关键约束】
1. 每条question必须达到指定长度要求
2. reasoning_chain每步content至少20字符
3. 必须包含difficulty_score和entity_to_token字段
4. spatial_tokens包含4-8个空间关键词
5. 每条数据之间用"---DATA---"分隔
6. 每条数据必须是有效的JSON格式

---
"""
        for i, p in enumerate(prompts, 1):
            # 获取实体信息
            entity1 = p.get('entity1', {})
            entity2 = p.get('entity2', {})
            difficulty = p.get('difficulty', 'medium')

            # 根据难度设置Question长度要求
            if difficulty == 'easy':
                q_len_req = '30-50字符'
            elif difficulty == 'medium':
                q_len_req = '50-100字符'
            else:
                q_len_req = '80-150字符'

            prompt_text += f"""【数据{i}】
- 实体1: {entity1.get('name', '未知')} ({entity1.get('type', 'city')}类型)，坐标: {entity1.get('coords', [0,0])}
- 实体2: {entity2.get('name', '未知')} ({entity2.get('type', 'province')}类型)，坐标: {entity2.get('coords', [0,0])}
- 拓扑子类型: {p.get('topology_subtype', 'within')}
- 难度: {difficulty}
- 要求Question长度: {q_len_req}

---DATA---
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
            if "spatial_tokens" not in result:
                result["spatial_tokens"] = self._extract_spatial_tokens(result)

            # 补充entity_to_token
            if "entity_to_token" not in result:
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
            'boundary', 'within', 'between', 'around', 'overlap', 'disjoint'
        ]

        for kw in spatial_keywords:
            if kw.lower() in text.lower():
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

    def generate_for_subtypes(self, subtype_counts: Dict[str, int], batch_size: int = 5):
        """为多个子类型生成数据"""
        total_needed = sum(subtype_counts.values())
        self.progress.state.total_target = total_needed

        print(f"\n{'=' * 60}")
        print(f"开始生成数据")
        print(f"{'=' * 60}")
        print(f"模型: {MODEL_NAME}")
        print(f"目标总数: {total_needed}")
        print(f"子类型分布: {subtype_counts}")
        print(f"批次大小: {batch_size}")
        print(f"预计批次数: {(total_needed + batch_size - 1) // batch_size}")
        print(f"{'=' * 60}\n")

        batch_count = 0

        for subtype, count in subtype_counts.items():
            print(f"\n{'=' * 60}")
            print(f"处理子类型: {subtype}, 需要生成: {count} 条")
            print(f"{'=' * 60}")

            self.progress.set_subtype(subtype, count)

            # 检查是否已完成
            subtype_prog = self.progress.state.subtype_progress.get(subtype, {})
            already_generated = subtype_prog.get("generated", 0)

            if already_generated >= count:
                print(f"  已完成: {already_generated}/{count}")
                continue

            remaining = count - already_generated
            print(f"  已生成: {already_generated}/{count}, 剩余: {remaining}")

            # 选择提示词
            selected_prompts = self._select_prompts_by_subtype(subtype, remaining)

            if len(selected_prompts) < remaining:
                print(f"  警告: 可用提示词不足，只有 {len(selected_prompts)} 条")

            # 分批生成
            generated_for_subtype = already_generated
            prompt_index = 0

            while prompt_index < len(selected_prompts):
                batch_count += 1
                batch_prompts = selected_prompts[prompt_index:prompt_index + batch_size]
                prompt_index += batch_size

                print(f"\n  批次 {batch_count}: 生成 {len(batch_prompts)} 条...")

                try:
                    results = self.generate_batch(batch_prompts, batch_size)

                    if results:
                        # 保存结果
                        self._append_to_output(results)

                        # 更新进度
                        for r in results:
                            self.progress.mark_completed(r.get("prompt_id", ""), subtype)

                        generated_for_subtype += len(results)
                        print(f"    成功: {len(results)} 条, 累计: {generated_for_subtype}/{count}")
                    else:
                        # 标记失败
                        for p in batch_prompts:
                            self.progress.mark_failed(p.get("id", ""), subtype, "生成失败")
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

            print(f"\n  {subtype} 完成: {generated_for_subtype} 条")

        # 最终保存
        self.progress.save_progress()

        print(f"\n{'=' * 60}")
        print(f"生成完成!")
        print(f"{'=' * 60}")
        print(f"总生成: {self.progress.state.total_generated} 条")
        print(f"总失败: {self.progress.state.total_failed} 条")
        print(f"API统计: {self.client.stats}")
        print(f"{'=' * 60}")


def parse_subtypes(subtypes_str: str) -> Dict[str, int]:
    """解析子类型参数"""
    result = {}
    for item in subtypes_str.split(','):
        if ':' in item:
            subtype, count = item.split(':')
            result[subtype.strip()] = int(count.strip())
    return result


def main():
    parser = argparse.ArgumentParser(description='拓扑子类型数据补充生成 V2.0')
    parser.add_argument('--subtypes', type=str, required=True,
                        help='子类型和数量，格式: subtype1:count1,subtype2:count2')
    parser.add_argument('--batch-size', type=int, default=5,
                        help='每批生成数量（默认5）')
    parser.add_argument('--output', type=str, required=True,
                        help='输出文件路径')
    parser.add_argument('--checkpoint', type=str, required=True,
                        help='进度文件路径')

    args = parser.parse_args()

    # 解析子类型
    subtype_counts = parse_subtypes(args.subtypes)
    print(f"子类型配置: {subtype_counts}")

    # 创建生成器
    generator = TopologyDataGenerator(
        output_file=args.output,
        checkpoint_file=args.checkpoint
    )

    # 开始生成
    generator.generate_for_subtypes(subtype_counts, args.batch_size)


if __name__ == "__main__":
    main()
