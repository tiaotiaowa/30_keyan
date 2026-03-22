#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
并行批量生成拓扑数据
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zhipuai import ZhipuAI

# 配置
API_KEY = "809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW"
OUTPUT_DIR = "D:/30_keyan/GeoKD-SR/data/final"

# 简化的提示词模板
CONTAINS_PROMPT = '''生成一个中国地理包含关系JSON数据：
输入：容器={container_name}({container_type})，被包含={contained_name}({contained_type})
输出严格JSON格式：
{{"id":"geosr_topological_{seq:05d}","spatial_relation_type":"topological","topology_subtype":"contains","question":"{container_name}是否包含{contained_name}？","answer":"是的，包含。","reasoning_chain":[{{"step":1,"name":"entity_identification","action":"extract_entities","content":"识别{container_name}({container_type})和{contained_name}({contained_type})","entities_involved":["{container_name}","{contained_name}"]}},{{"step":2,"name":"spatial_relation_extraction","action":"classify_relation","content":"判断拓扑包含关系","relation_type":"topological"}},{{"step":3,"name":"coordinate_retrieval","action":"infer_entity_to_token","content":"获取坐标","coordinates":{{"{container_name}":{container_coords},"{contained_name}":{contained_coords}}}}},{{"step":4,"name":"spatial_calculation","action":"determine_topology","content":"分析空间包含关系","calculation_result":"contains"}},{{"step":5,"name":"answer_generation","action":"generate_answer","content":"生成答案","final_answer":"是的，包含。"}}],"entities":[{{"name":"{container_name}","type":"{container_type}","coords":{container_coords}}},{{"name":"{contained_name}","type":"{contained_type}","coords":{contained_coords}}}],"spatial_tokens":["{container_name}","{contained_name}","包含","位于"],"entity_to_token":{{"{container_name}":{{"char_start":0,"char_end":3,"token_indices":[0,1,2]}},"{contained_name}":{{"char_start":6,"char_end":9,"token_indices":[6,7,8]}}}},"difficulty":"{difficulty}","difficulty_score":{score}}}'''

OVERLAP_PROMPT = '''生成一个中国地理交叉关系JSON数据：
输入：实体1={entity1_name}({entity1_type})，实体2={entity2_name}({entity2_type})，关系={overlap_info}
输出严格JSON格式：
{{"id":"geosr_topological_{seq:05d}","spatial_relation_type":"topological","topology_subtype":"overlap","question":"{entity1_name}是否与{entity2_name}存在交叉？","answer":"是的，存在交叉。","reasoning_chain":[{{"step":1,"name":"entity_identification","action":"extract_entities","content":"识别{entity1_name}({entity1_type})和{entity2_name}({entity2_type})","entities_involved":["{entity1_name}","{entity2_name}"]}},{{"step":2,"name":"spatial_relation_extraction","action":"classify_relation","content":"判断拓扑交叉关系","relation_type":"topological"}},{{"step":3,"name":"coordinate_retrieval","action":"infer_entity_to_token","content":"获取空间信息","coordinates":{{"{entity1_name}":{entity1_coords},"{entity2_name}":{entity2_coords}}}}},{{"step":4,"name":"spatial_calculation","action":"determine_topology","content":"分析空间交叉关系","calculation_result":"overlap"}},{{"step":5,"name":"answer_generation","action":"generate_answer","content":"生成答案","final_answer":"是的，存在交叉。"}}],"entities":[{{"name":"{entity1_name}","type":"{entity1_type}","coords":{entity1_coords}}},{{"name":"{entity2_name}","type":"{entity2_type}","coords":{entity2_coords}}}],"spatial_tokens":["{entity1_name}","{entity2_name}","交叉","流经"],"entity_to_token":{{"{entity1_name}":{{"char_start":0,"char_end":2,"token_indices":[0,1]}},"{entity2_name}":{{"char_start":5,"char_end":8,"token_indices":[5,6,7]}}}},"difficulty":"{difficulty}","difficulty_score":{score}}}'''


def load_entity_db():
    db_path = os.path.join(OUTPUT_DIR, "entity_database_expanded_v3_fixed.json")
    with open(db_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_city(name, entity_db):
    for c in entity_db['entities']['cities']:
        if c['name'] == name or c['name'] in name or name in c['name']:
            return c
    return None


def find_province(name, entity_db):
    for p in entity_db['entities']['provinces']:
        if p['name'] == name or name in p['name'] or p['name'] in name:
            return p
    return None


def build_pairs(entity_db, subtype, count):
    """构建指定数量的实体对"""
    pairs = []

    if subtype == 'contains':
        # 省份-城市对
        for p in entity_db['entities']['provinces']:
            for city_name in p.get('cities', []):
                if len(pairs) >= count:
                    break
                city = find_city(city_name, entity_db)
                if city:
                    pairs.append({
                        'container': p,
                        'contained': city,
                        'difficulty': 'easy' if len(pairs) % 3 == 0 else ('medium' if len(pairs) % 3 == 1 else 'hard')
                    })
            if len(pairs) >= count:
                break

    elif subtype == 'overlap':
        # 河流-省份对
        for river in entity_db['entities']['rivers']:
            for prov_name in river.get('provinces', []):
                if len(pairs) >= count:
                    break
                prov = find_province(prov_name, entity_db)
                if prov:
                    pairs.append({
                        'entity1': river,
                        'entity2': prov,
                        'overlap_info': f"{river['name']}流经{prov_name}",
                        'difficulty': 'easy' if len(pairs) % 3 == 0 else ('medium' if len(pairs) % 3 == 1 else 'hard')
                    })
            if len(pairs) >= count:
                break

    return pairs[:count]


def parse_json_robust(response):
    """健壮的JSON解析"""
    if not response:
        return None

    start = response.find('{')
    end = response.rfind('}')
    if start == -1 or end == -1:
        return None

    json_str = response[start:end+1]

    # 转义字符串内的换行符
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
    json_str = json_str.replace(',]', ']').replace(',}', '}')

    try:
        return json.loads(json_str)
    except:
        return None


def generate_single(client, pair, subtype, seq):
    """生成单条数据"""
    try:
        if subtype == 'contains':
            container = pair['container']
            contained = pair['contained']
            difficulty = pair.get('difficulty', 'medium')
            score = 2.3 if difficulty == 'easy' else (3.0 if difficulty == 'medium' else 3.8)

            prompt = CONTAINS_PROMPT
            prompt = prompt.replace('{container_name}', str(container['name']))
            prompt = prompt.replace('{container_type}', str(container['type']))
            prompt = prompt.replace('{contained_name}', str(contained['name']))
            prompt = prompt.replace('{contained_type}', str(contained['type']))
            prompt = prompt.replace('{container_coords}', json.dumps(container['coords']))
            prompt = prompt.replace('{contained_coords}', json.dumps(contained['coords']))
            prompt = prompt.replace('{difficulty}', difficulty)
            prompt = prompt.replace('{score}', str(score))
            prompt = prompt.replace('{seq:05d}', f'{seq:05d}')

        else:  # overlap
            entity1 = pair['entity1']
            entity2 = pair['entity2']
            difficulty = pair.get('difficulty', 'medium')
            score = 2.3 if difficulty == 'easy' else (3.0 if difficulty == 'medium' else 3.8)

            prompt = OVERLAP_PROMPT
            prompt = prompt.replace('{entity1_name}', str(entity1['name']))
            prompt = prompt.replace('{entity1_type}', str(entity1['type']))
            prompt = prompt.replace('{entity2_name}', str(entity2['name']))
            prompt = prompt.replace('{entity2_type}', str(entity2['type']))
            prompt = prompt.replace('{entity1_coords}', json.dumps(entity1['coords']))
            prompt = prompt.replace('{entity2_coords}', json.dumps(entity2['coords']))
            prompt = prompt.replace('{overlap_info}', str(pair.get('overlap_info', '')))
            prompt = prompt.replace('{difficulty}', difficulty)
            prompt = prompt.replace('{score}', str(score))
            prompt = prompt.replace('{seq:05d}', f'{seq:05d}')

        response = client.chat.completions.create(
            model="glm-4-plus",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        content = response.choices[0].message.content
        data = parse_json_robust(content)

        if data:
            return data
        return None

    except Exception as e:
        print(f"  错误(seq={seq}): {e}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--subtype', choices=['contains', 'overlap'], required=True)
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--workers', type=int, default=5)
    args = parser.parse_args()

    print(f"=" * 60)
    print(f"并行批量生成拓扑数据")
    print(f"类型: {args.subtype}, 目标: {args.count}, 并行数: {args.workers}")
    print(f"=" * 60)

    # 初始化
    client = ZhipuAI(api_key=API_KEY)
    entity_db = load_entity_db()
    pairs = build_pairs(entity_db, args.subtype, args.count)
    print(f"可用实体对: {len(pairs)} 对")

    # 输出文件
    output_file = os.path.join(OUTPUT_DIR, f"topology_{args.subtype}_parallel.jsonl")
    print(f"输出文件: {output_file}")

    # 并行生成
    results = []
    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for i, pair in enumerate(pairs):
            seq = i + 1
            future = executor.submit(generate_single, client, pair, args.subtype, seq)
            futures[future] = (i, seq)

        for future in as_completed(futures):
            i, seq = futures[future]
            data = future.result()
            if data:
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(data, ensure_ascii=False) + '\n')
                success_count += 1
                print(f"[{success_count}/{len(pairs)}] 成功: seq={seq}")
            else:
                fail_count += 1
                print(f"[{fail_count}] 失败: seq={seq}")

    print(f"\n完成! 成功: {success_count}, 失败: {fail_count}")


if __name__ == "__main__":
    main()
