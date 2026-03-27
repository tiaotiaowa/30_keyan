#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
final_1_corrected.jsonl 数据修复脚本

修复任务:
1. 删除 prompt_id 和 split 字段
2. 按标准顺序统一字段排列
3. 修复 entity_to_token 不匹配问题
4. 修复 reasoning_chain[4].final_answer 与 answer 不一致问题

作者: Claude
日期: 2026-03-11
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
from difflib import SequenceMatcher
import argparse


# 实体名变体映射表
ENTITY_VARIANTS = {
    # 省份简称/变体
    "内蒙古自治区": ["内蒙", "内蒙古"],
    "广西壮族自治区": ["广西"],
    "西藏自治区": ["西藏"],
    "宁夏回族自治区": ["宁夏"],
    "新疆维吾尔自治区": ["新疆"],
    "香港特别行政区": ["香港"],
    "澳门特别行政区": ["澳门"],
    # 常见简称
    "黑龙江省": ["黑龙江"],
    "吉林省": ["吉林"],
    "辽宁省": ["辽宁"],
    "河北省": ["河北"],
    "山西省": ["山西"],
    "山东省": ["山东"],
    "江苏省": ["江苏"],
    "浙江省": ["浙江"],
    "安徽省": ["安徽"],
    "福建省": ["福建"],
    "江西省": ["江西"],
    "河南省": ["河南"],
    "湖北省": ["湖北"],
    "湖南省": ["湖南"],
    "广东省": ["广东"],
    "海南省": ["海南"],
    "四川省": ["四川"],
    "贵州省": ["贵州"],
    "云南省": ["云南"],
    "陕西省": ["陕西"],
    "甘肃省": ["甘肃"],
    "青海省": ["青海"],
    "台湾省": ["台湾"],
    # 城市变体
    "北京市": ["北京"],
    "天津市": ["天津"],
    "上海市": ["上海"],
    "重庆市": ["重庆"],
}

# 标准字段顺序
STANDARD_FIELD_ORDER = [
    "id",
    "spatial_relation_type",
    "topology_subtype",
    "question",
    "answer",
    "difficulty",
    "difficulty_score",
    "reasoning_chain",
    "entities",
    "spatial_tokens",
    "entity_to_token",
]


def get_entity_variants(entity_name: str) -> List[str]:
    """获取实体名的所有可能变体"""
    variants = [entity_name]

    # 从映射表查找
    if entity_name in ENTITY_VARIANTS:
        variants.extend(ENTITY_VARIANTS[entity_name])

    # 自动生成常见变体
    # 1. 去掉"省"、"市"、"县"、"区"后缀
    for suffix in ["省", "市", "县", "区", "自治区", "特别行政区"]:
        if entity_name.endswith(suffix) and len(entity_name) > len(suffix):
            variants.append(entity_name[:-len(suffix)])

    # 2. 去掉"自治区"相关后缀
    for suffix in ["壮族自治区", "回族自治区", "维吾尔自治区", "自治区"]:
        if entity_name.endswith(suffix) and len(entity_name) > len(suffix):
            variants.append(entity_name[:-len(suffix)])

    return list(set(variants))


def regenerate_entity_to_token(question: str, entities: List[Dict], verbose: bool = False) -> Dict:
    """
    重新生成 entity_to_token 映射

    Args:
        question: 问题文本
        entities: 实体列表
        verbose: 是否输出调试信息

    Returns:
        entity_to_token 映射
    """
    entity_to_token = {}

    # 清理问题文本（移除坐标干扰）
    clean_question = re.sub(r'[\d\.\-]+°[NS]?[\s,]*[\d\.\-]+°[EW]?', '', question)
    clean_question = re.sub(r'\(\d+\.?\d*,\s*\d+\.?\d*\)', '', clean_question)

    for entity in entities:
        name = entity.get("name", "")
        if not name:
            continue

        found = False

        # 1. 尝试所有变体的完全匹配
        variants = get_entity_variants(name)
        for variant in variants:
            if variant in question:
                char_start = question.find(variant)
                char_end = char_start + len(variant)
                entity_to_token[name] = {
                    "char_start": char_start,
                    "char_end": char_end,
                    "token_indices": list(range(char_start, char_end))
                }
                found = True
                if verbose:
                    print(f"  [完全匹配] {name} -> {variant} @ [{char_start}, {char_end})")
                break

        if found:
            continue

        # 2. 尝试在清理后的问题中匹配
        for variant in variants:
            if variant in clean_question:
                char_start = question.find(variant)
                if char_start != -1:
                    char_end = char_start + len(variant)
                    entity_to_token[name] = {
                        "char_start": char_start,
                        "char_end": char_end,
                        "token_indices": list(range(char_start, char_end))
                    }
                    found = True
                    if verbose:
                        print(f"  [清理匹配] {name} -> {variant} @ [{char_start}, {char_end})")
                    break

        if found:
            continue

        # 3. 模糊匹配（滑动窗口 + 相似度）
        best_match = None
        best_ratio = 0

        for variant in variants:
            variant_len = len(variant)
            for length in range(variant_len, max(2, variant_len - 2), -1):
                for i in range(len(question) - length + 1):
                    candidate = question[i:i + length]
                    # 跳过纯数字或坐标
                    if re.match(r'^[\d\.\-\s,°]+$', candidate):
                        continue

                    ratio = SequenceMatcher(None, variant, candidate).ratio()
                    if ratio > 0.85 and ratio > best_ratio:
                        best_match = (i, i + length)
                        best_ratio = ratio

        if best_match:
            entity_to_token[name] = {
                "char_start": best_match[0],
                "char_end": best_match[1],
                "token_indices": list(range(best_match[0], best_match[1]))
            }
            found = True
            if verbose:
                print(f"  [模糊匹配] {name} -> {question[best_match[0]:best_match[1]]} (相似度: {best_ratio:.3f})")

        if not found and verbose:
            print(f"  [未匹配] {name}")

    return entity_to_token


def fix_record(record: Dict, record_idx: int, verbose: bool = False) -> Tuple[Dict, Dict]:
    """
    修复单条记录

    Returns:
        (修复后的记录, 修复统计)
    """
    stats = {
        "removed_prompt_id": False,
        "removed_split": False,
        "ett_regenerated": False,
        "final_answer_fixed": False,
        "ett_missing_entities": 0,
        "ett_extra_keys": 0
    }

    fixed = {}

    # 1. 删除不需要的字段并收集统计
    if "prompt_id" in record:
        stats["removed_prompt_id"] = True
    if "split" in record:
        stats["removed_split"] = True

    # 2. 修复 reasoning_chain[4].final_answer
    reasoning_chain = record.get("reasoning_chain", [])
    answer = record.get("answer", "")

    if len(reasoning_chain) >= 5:
        original_final_answer = reasoning_chain[4].get("final_answer", "")
        if original_final_answer != answer:
            reasoning_chain[4]["final_answer"] = answer
            stats["final_answer_fixed"] = True

    # 3. 修复 entity_to_token
    question = record.get("question", "")
    entities = record.get("entities", [])

    old_ett = record.get("entity_to_token", {})

    # 检查是否需要重新生成
    need_regenerate = False

    # 检查实体缺失映射
    entity_names = {e.get("name") for e in entities if e.get("name")}
    ett_keys = set(old_ett.keys())

    missing_entities = entity_names - ett_keys
    extra_keys = ett_keys - entity_names

    if missing_entities or extra_keys or not old_ett:
        need_regenerate = True
        stats["ett_missing_entities"] = len(missing_entities)
        stats["ett_extra_keys"] = len(extra_keys)

    if need_regenerate:
        new_ett = regenerate_entity_to_token(question, entities, verbose and record_idx < 5)
        stats["ett_regenerated"] = True
    else:
        new_ett = old_ett

    # 4. 按标准顺序重建记录
    for field in STANDARD_FIELD_ORDER:
        if field == "entity_to_token":
            fixed[field] = new_ett
        elif field == "reasoning_chain":
            fixed[field] = reasoning_chain
        elif field in record:
            fixed[field] = record[field]

    # 如果 topology_subtype 不存在且类型是 topological，设为 None
    if fixed.get("spatial_relation_type") == "topological" and "topology_subtype" not in fixed:
        fixed["topology_subtype"] = record.get("topology_subtype")

    return fixed, stats


def main():
    parser = argparse.ArgumentParser(description="final_1_corrected.jsonl 数据修复脚本")
    parser.add_argument("--input", "-i", required=True, help="输入文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="输出详细信息")
    parser.add_argument("--validate", action="store_true", help="验证修复结果")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}")
        return

    # 读取数据
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = len(records)
    print(f"总记录数: {total}")

    # 统计
    total_stats = {
        "removed_prompt_id": 0,
        "removed_split": 0,
        "ett_regenerated": 0,
        "final_answer_fixed": 0,
        "ett_missing_entities": 0,
        "ett_extra_keys": 0
    }

    # 修复记录
    print(f"\n开始修复...")
    fixed_records = []

    for i, record in enumerate(records):
        if args.verbose and i < 5:
            print(f"\n处理记录 {i + 1}: {record.get('question', '')[:50]}...")

        fixed, stats = fix_record(record, i, args.verbose)
        fixed_records.append(fixed)

        # 累计统计
        for key in total_stats:
            if isinstance(total_stats[key], int):
                total_stats[key] += stats.get(key, 0)
            elif stats.get(key):
                total_stats[key] += 1

        # 进度显示
        if (i + 1) % 1000 == 0:
            print(f"  已处理: {i + 1}/{total} ({(i + 1) / total * 100:.1f}%)")

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入输出文件
    with open(output_path, "w", encoding="utf-8") as f:
        for record in fixed_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n修复完成!")
    print(f"输出文件: {output_path}")

    # 输出统计
    print(f"\n=== 修复统计 ===")
    print(f"删除 prompt_id: {total_stats['removed_prompt_id']} 条")
    print(f"删除 split: {total_stats['removed_split']} 条")
    print(f"重新生成 entity_to_token: {total_stats['ett_regenerated']} 条")
    print(f"修复 final_answer: {total_stats['final_answer_fixed']} 条")

    if args.validate:
        print(f"\n=== 验证修复结果 ===")

        # 验证字段顺序
        field_order_ok = 0
        for record in fixed_records:
            keys = list(record.keys())
            expected = [k for k in STANDARD_FIELD_ORDER if k in record or
                       (k == "topology_subtype" and record.get("spatial_relation_type") == "topological")]
            actual = [k for k in keys if k in STANDARD_FIELD_ORDER]
            if actual == expected[:len(actual)]:
                field_order_ok += 1

        print(f"字段顺序正确: {field_order_ok}/{total} ({field_order_ok / total * 100:.2f}%)")

        # 验证无 prompt_id 和 split
        has_prompt_id = sum(1 for r in fixed_records if "prompt_id" in r)
        has_split = sum(1 for r in fixed_records if "split" in r)
        print(f"仍含 prompt_id: {has_prompt_id}")
        print(f"仍含 split: {has_split}")

        # 验证 entity_to_token
        ett_complete = 0
        ett_partial = 0
        ett_empty = 0

        for record in fixed_records:
            ett = record.get("entity_to_token", {})
            entities = record.get("entities", [])
            entity_names = {e.get("name") for e in entities if e.get("name")}

            if not ett:
                ett_empty += 1
            elif entity_names.issubset(set(ett.keys())):
                ett_complete += 1
            else:
                ett_partial += 1

        print(f"\nentity_to_token 状态:")
        print(f"  完整映射: {ett_complete} ({ett_complete / total * 100:.2f}%)")
        print(f"  部分映射: {ett_partial} ({ett_partial / total * 100:.2f}%)")
        print(f"  空映射: {ett_empty} ({ett_empty / total * 100:.2f}%)")

        # 验证 final_answer
        final_answer_ok = 0
        final_answer_error = 0

        for record in fixed_records:
            reasoning_chain = record.get("reasoning_chain", [])
            answer = record.get("answer", "")

            if len(reasoning_chain) >= 5:
                final_answer = reasoning_chain[4].get("final_answer", "")
                if final_answer == answer:
                    final_answer_ok += 1
                else:
                    final_answer_error += 1

        print(f"\nfinal_answer 一致性:")
        print(f"  一致: {final_answer_ok}")
        print(f"  不一致: {final_answer_error}")


if __name__ == "__main__":
    main()
