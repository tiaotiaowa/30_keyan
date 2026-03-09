#!/usr/bin/env python3
"""
拓扑子类型数据补充生成脚本
使用GLM-5 API (zhipuai SDK + thinking模式)
支持并行执行、断点续传、实体隔离验证
"""

import os
import json
import time
import random
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from zhipuai import ZhipuAI

# 配置API
ANTHROPIC_AUTH_TOKEN = "90fec3d49a8c40babbacecc617b34cf3.i4lMb9sTCUQlHKMw"

# 基础路径
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


class TopologyDataGenerator:
    def __init__(self, output_file: str, checkpoint_file: str):
        self.client = ZhipuAI(api_key=ANTHROPIC_AUTH_TOKEN)
        self.output_file = Path(output_file)
        self.checkpoint_file = Path(checkpoint_file)
        self.output_dir = self.output_file.parent
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 加载已有实体对（用于隔离验证）
        self.existing_pairs = self._load_existing_entity_pairs()

        # 加载进度
        self.generated_data = []
        self.progress = self._load_progress()

    def _load_existing_entity_pairs(self) -> set:
        """加载已有实体对，用于实体隔离验证"""
        pairs = set()

        # 从balanced_topology_downsampled.jsonl加载
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

        print(f"加载已有实体对: {len(pairs) // 2}对")
        return pairs

    def _load_progress(self) -> dict:
        """加载断点续传进度"""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                self.generated_data = progress.get("generated_data", [])
                print(f"恢复进度: 已生成 {len(self.generated_data)} 条数据")
                return progress

        return {
            "start_time": datetime.now().isoformat(),
            "generated_data": [],
            "completed_subtypes": {}
        }

    def _save_progress(self):
        """保存进度"""
        self.progress["generated_data"] = self.generated_data
        self.progress["last_update"] = datetime.now().isoformat()

        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)

    def _load_prompts(self) -> List[dict]:
        """加载提示词"""
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("prompts", [])

    def _select_prompts_by_subtype(
        self, prompts: List[dict], subtype: str, count: int
    ) -> List[dict]:
        """按子类型和难度分布选择提示词"""
        # 筛选指定子类型
        subtype_prompts = [p for p in prompts if p.get("topology_subtype") == subtype]

        # 排除已有实体对
        available = []
        for p in subtype_prompts:
            e1 = p.get("entity1", {}).get("name", "")
            e2 = p.get("entity2", {}).get("name", "")
            if (e1, e2) not in self.existing_pairs:
                available.append(p)

        # 按难度分组
        by_difficulty = {"easy": [], "medium": [], "hard": []}
        for p in available:
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
                # 如果不够，从其他难度补充
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
        """构建批量生成提示词"""
        prompt_text = f"""请按照以下格式生成{len(prompts)}条地理空间推理数据。

要求：
1. 每条数据必须包含完整的5步推理链(reasoning_chain)
2. 实体坐标必须使用[经度, 纬度]格式
3. topology_subtype必须正确填写
4. 每条数据之间用"---DATA---"分隔
5. 每条数据必须是有效的JSON格式

---
"""
        for i, p in enumerate(prompts, 1):
            prompt_text += f"""[数据{i}]
{p.get('prompt_text', '')}

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

            # 尝试提取JSON块 - 使用更宽松的正则
            # 查找所有可能的JSON对象
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
        """验证生成的数据是否有效"""
        required_fields = ["id", "question", "answer", "reasoning_chain", "entities", "topology_subtype"]

        for field in required_fields:
            if field not in data:
                return False

        # 验证reasoning_chain是否有5步
        chain = data.get("reasoning_chain", [])
        if len(chain) < 5:
            return False

        # 验证entities
        entities = data.get("entities", [])
        if len(entities) < 2:
            return False

        # 验证每个实体有coords
        for e in entities:
            if "coords" not in e:
                return False

        return True

    def generate_batch(self, prompts: List[dict], batch_size: int = 5) -> List[dict]:
        """批量生成数据"""
        batch_prompts = prompts[:batch_size]
        combined_prompt = self._build_batch_prompt(batch_prompts)

        try:
            # 使用zhipuai SDK的非流式模式
            response = self.client.chat.completions.create(
                model="glm-5",
                messages=[{"role": "user", "content": combined_prompt}],
                thinking={"type": "enabled"},
                stream=False,
                max_tokens=65536,
                temperature=1.0
            )

            # 从响应中提取内容
            full_content = ""
            if response.choices and len(response.choices) > 0:
                message = response.choices[0].message
                # GLM-5的thinking模式内容在reasoning_content中
                if hasattr(message, 'reasoning_content') and message.reasoning_content:
                    full_content = message.reasoning_content
                elif hasattr(message, 'content') and message.content:
                    full_content = message.content

            # 解析响应
            results = self._extract_json_from_response(full_content)

            # 为结果分配ID和补充字段
            final_results = []
            for i, (prompt, result) in enumerate(zip(batch_prompts, results)):
                # 生成新ID
                new_id = f"geosr_topological_{random.randint(10000, 99999)}_{random.randint(1000, 9999)}"
                result["id"] = new_id
                result["topology_subtype"] = prompt.get("topology_subtype")
                result["difficulty"] = prompt.get("difficulty", "medium")
                result["spatial_relation_type"] = "topological"
                result["prompt_id"] = prompt.get("id")
                result["split"] = "train"
                final_results.append(result)

            return final_results

        except Exception as e:
            print(f"API调用错误: {e}")
            import traceback
            traceback.print_exc()
            return []

    def generate_for_subtypes(
        self, subtype_counts: Dict[str, int], batch_size: int = 5
    ):
        """为多个子类型生成数据"""
        all_prompts = self._load_prompts()

        total_needed = sum(subtype_counts.values())
        print(f"\n开始生成数据，共需 {total_needed} 条")
        print(f"子类型分布: {subtype_counts}")
        print(f"批次大小: {batch_size}")
        print(f"预计批次数: {(total_needed + batch_size - 1) // batch_size}")

        for subtype, count in subtype_counts.items():
            print(f"\n{'='*60}")
            print(f"处理子类型: {subtype}, 需要生成: {count} 条")
            print(f"{'='*60}")

            # 选择提示词
            selected_prompts = self._select_prompts_by_subtype(all_prompts, subtype, count)

            if len(selected_prompts) < count:
                print(f"警告: 可用提示词不足，只有 {len(selected_prompts)} 条")

            # 分批生成
            generated_for_subtype = 0
            batch_num = 0

            while generated_for_subtype < count and selected_prompts:
                batch_num += 1
                batch_prompts = selected_prompts[:batch_size]
                selected_prompts = selected_prompts[batch_size:]

                print(f"\n批次 {batch_num}: 生成 {len(batch_prompts)} 条...")

                results = self.generate_batch(batch_prompts, batch_size)

                if results:
                    self.generated_data.extend(results)
                    generated_for_subtype += len(results)
                    print(f"  成功生成 {len(results)} 条，累计: {generated_for_subtype}/{count}")

                    # 保存进度
                    self._save_progress()

                    # 保存到输出文件
                    self._append_to_output(results)
                else:
                    print(f"  批次生成失败，跳过")

                # 避免API限流
                time.sleep(1)

            print(f"\n{subtype} 生成完成: {generated_for_subtype} 条")

        # 最终统计
        print(f"\n{'='*60}")
        print(f"生成完成!")
        print(f"总生成数据: {len(self.generated_data)} 条")
        print(f"{'='*60}")

    def _append_to_output(self, results: List[dict]):
        """追加数据到输出文件"""
        with open(self.output_file, 'a', encoding='utf-8') as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')


def parse_subtypes(subtypes_str: str) -> Dict[str, int]:
    """解析子类型参数，格式: subtype1:count1,subtype2:count2"""
    result = {}
    for item in subtypes_str.split(','):
        if ':' in item:
            subtype, count = item.split(':')
            result[subtype.strip()] = int(count.strip())
    return result


def main():
    parser = argparse.ArgumentParser(description='拓扑子类型数据补充生成')
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
