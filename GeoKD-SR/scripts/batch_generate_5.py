#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量生成拓扑数据 - 每次处理5条
"""
import json
import re
import os
import sys
from datetime import datetime
from zhipuai import ZhipuAI

# 配置
API_KEY = "809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW"
OUTPUT_DIR = "D:/30_keyan/GeoKD-SR/data/final"

# Contains提示词模板
CONTAINS_PROMPT = '''【任务】生成一个中国地理拓扑包含关系推理问题

【输入】
- 容器实体：{container_name}（类型：{container_type}）
- 被包含实体：{contained_name}（类型：{contained_type}）
- 难度：{difficulty}

【输出格式】严格输出以下JSON，不要有其他内容：
{{
  "id": "geosr_topological_{seq:05d}",
  "spatial_relation_type": "topological",
  "topology_subtype": "contains",
  "question": "{container_name}是否包含{contained_name}？",
  "answer": "是的，包含。",
  "reasoning_chain": [
    {{"step": 1, "name": "entity_identification", "action": "extract_entities", "content": "识别实体：{container_name}是{container_type}，{contained_name}是{contained_type}。", "entities_involved": ["{container_name}", "{contained_name}"]}},
    {{"step": 2, "name": "spatial_relation_extraction", "action": "classify_relation", "content": "判断包含关系。", "relation_type": "topological"}},
    {{"step": 3, "name": "coordinate_retrieval", "action": "infer_entity_to_token", "content": "获取坐标信息。", "coordinates": {{"{container_name}": {container_coords}, "{contained_name}": {contained_coords}}}},
    {{"step": 4, "name": "spatial_calculation", "action": "determine_topology", "content": "分析空间包含关系。", "calculation_result": "contains"}},
    {{"step": 5, "name": "answer_generation", "action": "generate_answer", "content": "生成答案。", "final_answer": "是的，包含。"}}
  ],
  "entities": [
    {{"name": "{container_name}", "type": "{container_type}", "coords": {container_coords}}},
    {{"name": "{contained_name}", "type": "{contained_type}", "coords": {contained_coords}}}
  ],
  "spatial_tokens": ["{container_name}", "{contained_name}", "包含", "位于"],
  "entity_to_token": {{"{container_name}": {{"char_start": 0, "char_end": 3, "token_indices": [0,1,2]}}, "{contained_name}": {{"char_start": 6, "char_end": 9, "token_indices": [6,7,8]}}},
  "difficulty": "{difficulty}",
  "difficulty_score": {score}
}}'''

# Overlap提示词模板
OVERLAP_PROMPT = '''【任务】生成一个中国地理拓扑交叉关系推理问题

【输入】
- 实体1：{entity1_name}（类型：{entity1_type}）
- 实体2：{entity2_name}（类型：{entity2_type}）
- 交叉信息：{overlap_info}
- 难度：{difficulty}

【输出格式】严格输出以下JSON，不要有其他内容：
{{
  "id": "geosr_topological_{seq:05d}",
  "spatial_relation_type": "topological",
  "topology_subtype": "overlap",
  "question": "{entity1_name}是否与{entity2_name}存在交叉？",
  "answer": "是的，存在交叉。",
  "reasoning_chain": [
    {{"step": 1, "name": "entity_identification", "action": "extract_entities", "content": "识别实体：{entity1_name}是{entity1_type}，{entity2_name}是{entity2_type}。", "entities_involved": ["{entity1_name}", "{entity2_name}"]}},
    {{"step": 2, "name": "spatial_relation_extraction", "action": "classify_relation", "content": "判断交叉关系。", "relation_type": "topological"}},
    {{"step": 3, "name": "coordinate_retrieval", "action": "infer_entity_to_token", "content": "获取空间信息。", "coordinates": {{"{entity1_name}": {entity1_coords}, "{entity2_name}": {entity2_coords}}}},
    {{"step": 4, "name": "spatial_calculation", "action": "determine_topology", "content": "分析空间交叉关系。", "calculation_result": "overlap"}},
    {{"step": 5, "name": "answer_generation", "action": "generate_answer", "content": "生成答案。", "final_answer": "是的，存在交叉。"}}
  ],
  "entities": [
    {{"name": "{entity1_name}", "type": "{entity1_type}", "coords": {entity1_coords}}},
    {{"name": "{entity2_name}", "type": "{entity2_type}", "coords": {entity2_coords}}}
  ],
  "spatial_tokens": ["{entity1_name}", "{entity2_name}", "交叉", "流经"],
  "entity_to_token": {{"{entity1_name}": {{"char_start": 0, "char_end": 2, "token_indices": [0,1]}}, "{entity2_name}": {{"char_start": 5, "char_end": 8, "token_indices": [5,6,7]}}},
  "difficulty": "{difficulty}",
  "difficulty_score": {score}
}}'''


def load_entity_db():
    """加载实体数据库"""
    db_path = os.path.join(OUTPUT_DIR, "entity_database_expanded_v3_fixed.json")
    with open(db_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_entity_pairs(entity_db, subtype):
    """构建实体对列表"""
    pairs = []

    if subtype == 'contains':
        # 省份-城市对
        for p in entity_db['entities']['provinces']:
            for city_name in p.get('cities', [])[:3]:  # 每省最多3个城市
                city = find_city(city_name, entity_db)
                if city:
                    pairs.append({
                        'container': p,
                        'contained': city,
                        'difficulty': 'easy' if len(pairs) % 3 == 0 else 'medium'
                    })

    elif subtype == 'overlap':
        # 河流-省份对
        for river in entity_db['entities']['rivers']:
            for prov_name in river.get('provinces', [])[:2]:  # 每河最多2个省份
                prov = find_province(prov_name, entity_db)
                if prov:
                    pairs.append({
                        'entity1': river,
                        'entity2': prov,
                        'overlap_info': f"{river['name']}流经{prov_name}",
                        'difficulty': 'easy' if len(pairs) % 3 == 0 else 'medium'
                    })

    return pairs


def find_city(name, entity_db):
    for c in entity_db['entities']['cities']:
        if c['name'] == name or c['name'] in name:
            return c
    return None


def find_province(name, entity_db):
    for p in entity_db['entities']['provinces']:
        if p['name'] == name or name in p['name']:
            return p
    return None


def parse_json_robust(response):
    """健壮的JSON解析"""
    if not response:
        return None

    # 提取JSON部分
    start = response.find('{')
    end = response.rfind('}')
    if start == -1 or end == -1:
        return None

    json_str = response[start:end+1]

    # 预处理：转义字符串内的换行符
    result = []
    in_string = False
    for i, char in enumerate(json_str):
        if char == '"' and (i == 0 or json_str[i-1] != '\\'):
            in_string = not in_string
            result.append(char)
        elif in_string:
            if char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            else:
                result.append(char)
        else:
            result.append(char)

    json_str = ''.join(result)

    # 修复常见问题
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # 尾部逗号

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  JSON解析失败: {e}")
        return None


def generate_batch(client, pairs, subtype, start_seq, output_file):
    """生成一批数据（5条）"""
    results = []
    seq = start_seq

    for i, pair in enumerate(pairs[:5]):  # 只处理前5条
        try:
            # 构建提示词
            if subtype == 'contains':
                container = pair['container']
                contained = pair['contained']
                difficulty = pair.get('difficulty', 'medium')
                score = 2.3 if difficulty == 'easy' else (3.0 if difficulty == 'medium' else 3.8)

                prompt = CONTAINS_PROMPT.replace('{container_name}', str(container['name']))
                prompt = prompt.replace('{container_type}', str(container['type']))
                prompt = prompt.replace('{contained_name}', str(contained['name']))
                prompt = prompt.replace('{contained_type}', str(contained['type']))
                prompt = prompt.replace('{container_coords}', json.dumps(container['coords']))
                prompt = prompt.replace('{contained_coords}', json.dumps(contained['coords']))
                prompt = prompt.replace('{difficulty}', difficulty)
                prompt = prompt.replace('{score}', str(score))
                prompt = prompt.replace('{seq:05d}', f'{seq:05d}')
                prompt = prompt.replace('{seq}', str(seq))

            else:  # overlap
                entity1 = pair['entity1']
                entity2 = pair['entity2']
                difficulty = pair.get('difficulty', 'medium')
                score = 2.3 if difficulty == 'easy' else (3.0 if difficulty == 'medium' else 3.8)

                prompt = OVERLAP_PROMPT.replace('{entity1_name}', str(entity1['name']))
                prompt = prompt.replace('{entity1_type}', str(entity1['type']))
                prompt = prompt.replace('{entity2_name}', str(entity2['name']))
                prompt = prompt.replace('{entity2_type}', str(entity2['type']))
                prompt = prompt.replace('{entity1_coords}', json.dumps(entity1['coords']))
                prompt = prompt.replace('{entity2_coords}', json.dumps(entity2['coords']))
                prompt = prompt.replace('{overlap_info}', str(pair.get('overlap_info', '')))
                prompt = prompt.replace('{difficulty}', difficulty)
                prompt = prompt.replace('{score}', str(score))
                prompt = prompt.replace('{seq:05d}', f'{seq:05d}')
                prompt = prompt.replace('{seq}', str(seq))

            # 调用API
            print(f"[{i+1}/5] 生成: {subtype}_{seq:05d}")
            response = client.chat.completions.create(
                model="glm-4-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )

            content = response.choices[0].message.content
            data = parse_json_robust(content)

            if data:
                # 保存结果
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(data, ensure_ascii=False) + '\n')
                results.append(data)
                print(f"  成功: {data.get('id', 'unknown')}")
            else:
                print(f"  失败: JSON解析错误")

            seq += 1

        except Exception as e:
            print(f"  错误: {e}")

    return results, seq


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--subtype', choices=['contains', 'overlap'], required=True)
    parser.add_argument('--batch', type=int, default=0, help='批次号（从0开始）')
    args = parser.parse_args()

    print(f"=" * 60)
    print(f"批量生成拓扑数据 - 每批5条")
    print(f"类型: {args.subtype}, 批次: {args.batch}")
    print(f"=" * 60)

    # 初始化客户端
    client = ZhipuAI(api_key=API_KEY)
    print("GLM客户端初始化成功")

    # 加载实体库
    entity_db = load_entity_db()
    print(f"实体库加载成功: {sum(len(v) for v in entity_db['entities'].values())} 个实体")

    # 构建实体对
    pairs = build_entity_pairs(entity_db, args.subtype)
    print(f"可用实体对: {len(pairs)} 对")

    # 跳过已处理的批次
    start_idx = args.batch * 5
    batch_pairs = pairs[start_idx:start_idx + 5]

    if not batch_pairs:
        print("没有更多数据可处理")
        return

    # 输出文件
    output_file = os.path.join(OUTPUT_DIR, f"topology_{args.subtype}_batch.jsonl")
    print(f"输出文件: {output_file}")

    # 生成
    start_seq = args.batch * 5 + 1
    results, _ = generate_batch(client, batch_pairs, args.subtype, start_seq, output_file)

    print(f"\n本批次完成: 成功 {len(results)}/5")


if __name__ == "__main__":
    main()
