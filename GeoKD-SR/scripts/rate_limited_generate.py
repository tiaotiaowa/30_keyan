#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""带速率限制的并行生成脚本"""
import json
import os
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from zhipuai import ZhipuAI

API_KEY = "809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW"
OUTPUT_DIR = "D:/30_keyan/GeoKD-SR/data/final"

CONTAINS_PROMPT = '''生成中国地理包含关系JSON：
容器={container_name}({container_type}), 被包含={contained_name}({contained_type})
输出JSON:{{"id":"geosr_topological_{seq}","spatial_relation_type":"topological","topology_subtype":"contains","question":"{container_name}是否包含{contained_name}？","answer":"是的，包含。","reasoning_chain":[{{"step":1,"name":"entity_identification","action":"extract_entities","content":"识别{container_name}和{contained_name}","entities_involved":["{container_name}","{contained_name}"]}},{{"step":2,"name":"spatial_relation_extraction","action":"classify_relation","content":"判断包含关系","relation_type":"topological"}},{{"step":3,"name":"coordinate_retrieval","action":"infer_entity_to_token","content":"获取坐标","coordinates":{{"{container_name}":{c_coords},"{contained_name}":{cd_coords}}}},{{"step":4,"name":"spatial_calculation","action":"determine_topology","content":"分析空间关系","calculation_result":"contains"}},{{"step":5,"name":"answer_generation","action":"generate_answer","content":"生成答案","final_answer":"是的，包含。"}}],"entities":[{{"name":"{container_name}","type":"{container_type}","coords":{c_coords}}},{{"name":"{contained_name}","type":"{contained_type}","coords":{cd_coords}}}],"spatial_tokens":["{container_name}","{contained_name}","包含"],"entity_to_token":{{"{container_name}":{{"char_start":0,"char_end":3,"token_indices":[0,1,2]}},"{contained_name}":{{"char_start":6,"char_end":9,"token_indices":[6,7,8]}}}},"difficulty":"{difficulty}","difficulty_score":{score}}}'''

OVERLAP_PROMPT = '''生成中国地理交叉关系JSON：
实体1={entity1_name}({entity1_type}), 实体2={entity2_name}({entity2_type}), 关系={overlap_info}
输出JSON:{{"id":"geosr_topological_{seq}","spatial_relation_type":"topological","topology_subtype":"overlap","question":"{entity1_name}是否与{entity2_name}存在交叉？","answer":"是的，存在交叉。","reasoning_chain":[{{"step":1,"name":"entity_identification","action":"extract_entities","content":"识别{entity1_name}和{entity2_name}","entities_involved":["{entity1_name}","{entity2_name}"]}},{{"step":2,"name":"spatial_relation_extraction","action":"classify_relation","content":"判断交叉关系","relation_type":"topological"}},{{"step":3,"name":"coordinate_retrieval","action":"infer_entity_to_token","content":"获取空间信息","coordinates":{{"{entity1_name}":{e1_coords},"{entity2_name}":{e2_coords}}}},{{"step":4,"name":"spatial_calculation","action":"determine_topology","content":"分析空间交叉","calculation_result":"overlap"}},{{"step":5,"name":"answer_generation","action":"generate_answer","content":"生成答案","final_answer":"是的，存在交叉。"}}],"entities":[{{"name":"{entity1_name}","type":"{entity1_type}","coords":{e1_coords}}},{{"name":"{entity2_name}","type":"{entity2_type}","coords":{e2_coords}}}],"spatial_tokens":["{entity1_name}","{entity2_name}","交叉"],"entity_to_token":{{"{entity1_name}":{{"char_start":0,"char_end":2,"token_indices":[0,1]}},"{entity2_name}":{{"char_start":5,"char_end":8,"token_indices":[5,6,7]}}}},"difficulty":"{difficulty}","difficulty_score":{score}}}'''


def load_db():
    with open(os.path.join(OUTPUT_DIR, "entity_database_expanded_v3_fixed.json"), 'r', encoding='utf-8') as f:
        return json.load(f)


def find_city(name, db):
    for c in db['entities']['cities']:
        if c['name'] == name or name in c['name']:
            return c
    return None


def find_province(name, db):
    for p in db['entities']['provinces']:
        if p['name'] == name or name in p['name']:
            return p
    return None


def build_pairs(db, subtype, count):
    pairs = []
    if subtype == 'contains':
        for p in db['entities']['provinces']:
            for city_name in p.get('cities', []):
                if len(pairs) >= count: break
                city = find_city(city_name, db)
                if city:
                    pairs.append({'container': p, 'contained': city,
                                 'difficulty': ['easy','medium','hard'][len(pairs)%3]})
    else:
        for river in db['entities']['rivers']:
            for prov_name in river.get('provinces', []):
                if len(pairs) >= count: break
                prov = find_province(prov_name, db)
                if prov:
                    pairs.append({'entity1': river, 'entity2': prov,
                                 'overlap_info': f"{river['name']}流经{prov_name}",
                                 'difficulty': ['easy','medium','hard'][len(pairs)%3]})
    return pairs[:count]


def parse_json(response):
    if not response: return None
    start, end = response.find('{'), response.rfind('}')
    if start == -1 or end == -1: return None
    s = response[start:end+1]
    # 转义换行
    result, in_str = [], False
    for i, c in enumerate(s):
        if c == '"' and (i == 0 or s[i-1] != '\\'):
            in_str = not in_str
            result.append(c)
        elif in_str and c in '\n\r\t':
            result.append('\\n' if c == '\n' else ('\\r' if c == '\r' else '\\t'))
        else:
            result.append(c)
    try:
        return json.loads(''.join(result))
    except:
        return None


def generate_with_retry(client, pair, subtype, seq, max_retries=3):
    for attempt in range(max_retries):
        try:
            if subtype == 'contains':
                c, cd = pair['container'], pair['contained']
                score = {'easy':2.3,'medium':3.0,'hard':3.8}[pair['difficulty']]
                prompt = CONTAINS_PROMPT.replace('{container_name}',str(c['name'])).replace('{container_type}',str(c['type']))
                prompt = prompt.replace('{contained_name}',str(cd['name'])).replace('{contained_type}',str(cd['type']))
                prompt = prompt.replace('{c_coords}',json.dumps(c['coords'])).replace('{cd_coords}',json.dumps(cd['coords']))
            else:
                e1, e2 = pair['entity1'], pair['entity2']
                score = {'easy':2.3,'medium':3.0,'hard':3.8}[pair['difficulty']]
                prompt = OVERLAP_PROMPT.replace('{entity1_name}',str(e1['name'])).replace('{entity1_type}',str(e1['type']))
                prompt = prompt.replace('{entity2_name}',str(e2['name'])).replace('{entity2_type}',str(e2['type']))
                prompt = prompt.replace('{e1_coords}',json.dumps(e1['coords'])).replace('{e2_coords}',json.dumps(e2['coords']))
                prompt = prompt.replace('{overlap_info}',str(pair.get('overlap_info','')))

            prompt = prompt.replace('{seq}', str(seq)).replace('{difficulty}', pair['difficulty']).replace('{score}', str(score))

            # 添加随机延迟避免速率限制
            time.sleep(random.uniform(0.5, 1.5))

            resp = client.chat.completions.create(
                model="glm-4-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            data = parse_json(resp.choices[0].message.content)
            if data:
                return data
        except Exception as e:
            if '429' in str(e) or '1302' in str(e):
                wait = 60 + random.uniform(0, 30)
                print(f"  速率限制，等待{wait:.0f}秒...")
                time.sleep(wait)
            else:
                print(f"  尝试{attempt+1}/{max_retries}失败: {e}")
                time.sleep(5)
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--subtype', required=True, choices=['contains','overlap'])
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()

    print(f"="*60)
    print(f"带速率限制的并行生成 - {args.subtype} 目标{args.count}")
    print(f"="*60)

    client = ZhipuAI(api_key=API_KEY)
    db = load_db()
    pairs = build_pairs(db, args.subtype, args.count)
    print(f"实体对: {len(pairs)}")

    output = os.path.join(OUTPUT_DIR, f"topology_{args.subtype}_rate_limited.jsonl")
    success, fail = 0, 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(generate_with_retry, client, p, args.subtype, i+1): i for i, p in enumerate(pairs)}
        for future in as_completed(futures):
            data = future.result()
            if data:
                with open(output, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(data, ensure_ascii=False) + '\n')
                success += 1
                print(f"[{success}/{len(pairs)}] 成功")
            else:
                fail += 1

    print(f"\n完成! 成功:{success}, 失败:{fail}")


if __name__ == "__main__":
    main()
