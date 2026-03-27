#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强版 entity_to_token 修复脚本 V2

解决问题：
1. 实体名在问题中被简化（"南京紫金山" → "南京"）
2. 实体名变体（"内蒙古自治区" → "内蒙"）
3. 坐标文本干扰

作者: Claude
日期: 2026-03-10
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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


def enhanced_entity_to_token(question: str, entities: List[Dict], verbose: bool = False) -> Dict:
    """
    增强版 entity_to_token 生成，支持模糊匹配

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
                    "token_indices": list(range(char_start, char_end)),
                    "match_type": "exact_variant",
                    "matched_text": variant
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
                        "token_indices": list(range(char_start, char_end)),
                        "match_type": "clean_match",
                        "matched_text": variant
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
        best_variant = None

        for variant in variants:
            # 滑动窗口搜索
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
                        best_variant = variant

        if best_match:
            entity_to_token[name] = {
                "char_start": best_match[0],
                "char_end": best_match[1],
                "token_indices": list(range(best_match[0], best_match[1])),
                "match_type": "fuzzy",
                "matched_text": question[best_match[0]:best_match[1]],
                "similarity": round(best_ratio, 3),
                "original_name": best_variant
            }
            found = True
            if verbose:
                print(f"  [模糊匹配] {name} -> {question[best_match[0]:best_match[1]]} (相似度: {best_ratio:.3f})")

        if not found and verbose:
            print(f"  [未匹配] {name}")

    return entity_to_token


def validate_entity_to_token(record: Dict) -> Tuple[bool, List[str]]:
    """
    验证 entity_to_token 的正确性

    Returns:
        (是否有效, 错误列表)
    """
    errors = []
    question = record.get("question", "")
    entities = record.get("entities", [])
    entity_to_token = record.get("entity_to_token", {})

    # 检查每个实体是否有映射
    for entity in entities:
        name = entity.get("name", "")
        if not name:
            continue

        if name not in entity_to_token:
            errors.append(f"缺失实体映射: {name}")
            continue

        mapping = entity_to_token[name]
        char_start = mapping.get("char_start", -1)
        char_end = mapping.get("char_end", -1)

        # 验证位置有效性
        if char_start < 0 or char_end > len(question):
            errors.append(f"位置越界: {name} [{char_start}, {char_end})")
            continue

        # 验证位置正确性
        extracted = question[char_start:char_end]
        if extracted != name:
            # 检查是否是变体匹配
            variants = get_entity_variants(name)
            if extracted not in variants:
                # 检查相似度
                ratio = SequenceMatcher(None, name, extracted).ratio()
                if ratio < 0.7:
                    errors.append(f"位置错误: {name} -> '{extracted}' (相似度: {ratio:.2f})")

    return len(errors) == 0, errors


def fix_record(record: Dict, verbose: bool = False) -> Dict:
    """修复单条记录"""
    fixed = record.copy()

    question = fixed.get("question", "")
    entities = fixed.get("entities", [])

    if question and entities:
        fixed["entity_to_token"] = enhanced_entity_to_token(question, entities, verbose)

    return fixed


def main():
    parser = argparse.ArgumentParser(description="增强版 entity_to_token 修复脚本")
    parser.add_argument("--input", "-i", required=True, help="输入文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不输出文件")
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

    # 统计原始状态
    missing_count = 0
    error_count = 0
    correct_count = 0

    for record in records:
        entity_to_token = record.get("entity_to_token", {})
        entities = record.get("entities", [])

        if not entity_to_token:
            missing_count += 1
            continue

        # 验证映射
        is_valid, errors = validate_entity_to_token(record)
        if is_valid:
            correct_count += 1
        else:
            error_count += 1

    print(f"\n修复前统计:")
    print(f"  缺失 entity_to_token: {missing_count} ({missing_count / total * 100:.2f}%)")
    print(f"  错误映射: {error_count} ({error_count / total * 100:.2f}%)")
    print(f"  正确映射: {correct_count} ({correct_count / total * 100:.2f}%)")

    if args.dry_run:
        print("\n[dry-run 模式] 不输出文件")
        return

    # 修复记录
    print(f"\n开始修复...")
    fixed_records = []
    match_types = {"exact_variant": 0, "clean_match": 0, "fuzzy": 0, "none": 0}

    for i, record in enumerate(records):
        if args.verbose and i < 10:
            print(f"\n记录 {i + 1}: {record.get('question', '')[:50]}...")

        fixed = fix_record(record, args.verbose and i < 10)
        fixed_records.append(fixed)

        # 统计匹配类型
        for mapping in fixed.get("entity_to_token", {}).values():
            match_type = mapping.get("match_type", "none")
            if match_type in match_types:
                match_types[match_type] += 1

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入输出文件
    with open(output_path, "w", encoding="utf-8") as f:
        for record in fixed_records:
            # 移除调试字段
            clean_record = {}
            for k, v in record.items():
                if k == "entity_to_token":
                    clean_record[k] = {}
                    for entity_name, mapping in v.items():
                        clean_mapping = {
                            "char_start": mapping["char_start"],
                            "char_end": mapping["char_end"],
                            "token_indices": mapping["token_indices"]
                        }
                        clean_record[k][entity_name] = clean_mapping
                else:
                    clean_record[k] = v
            f.write(json.dumps(clean_record, ensure_ascii=False) + "\n")

    print(f"\n修复完成，输出文件: {output_path}")

    print(f"\n匹配类型统计:")
    print(f"  完全匹配: {match_types['exact_variant']}")
    print(f"  清理匹配: {match_types['clean_match']}")
    print(f"  模糊匹配: {match_types['fuzzy']}")
    print(f"  未匹配: {match_types['none']}")

    if args.validate:
        # 验证修复结果
        print(f"\n验证修复结果...")
        fixed_missing = 0
        fixed_errors = 0
        fixed_correct = 0

        for record in fixed_records:
            entity_to_token = record.get("entity_to_token", {})
            entities = record.get("entities", [])

            if not entity_to_token:
                fixed_missing += 1
                continue

            is_valid, errors = validate_entity_to_token(record)
            if is_valid:
                fixed_correct += 1
            else:
                fixed_errors += 1

        print(f"\n修复后统计:")
        print(f"  缺失 entity_to_token: {fixed_missing} ({fixed_missing / total * 100:.2f}%)")
        print(f"  错误映射: {fixed_errors} ({fixed_errors / total * 100:.2f}%)")
        print(f"  正确映射: {fixed_correct} ({fixed_correct / total * 100:.2f}%)")

        # 计算改善率
        original_correct_rate = correct_count / total * 100
        new_correct_rate = fixed_correct / total * 100
        improvement = new_correct_rate - original_correct_rate
        print(f"\n改善: {improvement:+.2f}%")


if __name__ == "__main__":
    main()
