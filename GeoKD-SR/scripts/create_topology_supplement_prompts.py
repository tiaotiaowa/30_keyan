"""
拓扑补充Prompts生成脚本

从entity_database_expanded.json选取实体对，生成符合prompts_config_full.json格式的prompts配置文件。

任务目标：
- within: 368条（城市-省份包含关系，当前232条，目标600条）
- contains: 374条（省份-城市被包含关系，当前226条，目标600条）
- adjacent: 440条（省份邻接关系，当前160条，目标600条）
- overlap: 512条（当前88条，目标600条）
"""

import json
import random
import math
from collections import defaultdict
from pathlib import Path

# 设置随机种子
random.seed(42)

# 文件路径
BASE_DIR = Path('D:/30_keyan/GeoKD-SR')
ENTITY_DB_FILE = BASE_DIR / 'data' / 'entity_database_expanded.json'
OUTPUT_FILE = BASE_DIR / 'data' / 'prompts' / 'topology_supplement_prompts.json'

# 省份邻接关系（基于中国地理）
# 参考数据：内蒙古自治区、陕西省各有8个邻省，河北省、四川省各有7个邻省
PROVINCE_ADJACENCY = {
    "北京市": ["河北省", "天津市"],
    "天津市": ["河北省", "北京市", "渤海"],
    "河北省": ["北京市", "天津市", "山西省", "内蒙古自治区", "辽宁省", "山东省", "河南省"],
    "山西省": ["内蒙古自治区", "河北省", "河南省", "陕西省"],
    "内蒙古自治区": ["黑龙江省", "吉林省", "辽宁省", "河北省", "山西省", "陕西省", "宁夏回族自治区", "甘肃省"],
    "辽宁省": ["内蒙古自治区", "吉林省", "河北省", "山东省", "渤海"],
    "吉林省": ["内蒙古自治区", "黑龙江省", "辽宁省"],
    "黑龙江省": ["吉林省", "内蒙古自治区"],
    "上海市": ["江苏省", "浙江省", "东海"],
    "江苏省": ["山东省", "安徽省", "浙江省", "上海市", "黄海"],
    "浙江省": ["江苏省", "安徽省", "江西省", "福建省", "上海市", "东海"],
    "安徽省": ["江苏省", "浙江省", "江西省", "湖北省", "河南省", "山东省"],
    "福建省": ["浙江省", "江西省", "广东省", "台湾省", "东海"],
    "江西省": ["安徽省", "浙江省", "福建省", "广东省", "湖南省", "湖北省"],
    "山东省": ["河北省", "河南省", "安徽省", "江苏省", "渤海"],
    "河南省": ["河北省", "山西省", "陕西省", "湖北省", "安徽省", "山东省"],
    "湖北省": ["河南省", "安徽省", "江西省", "湖南省", "重庆市", "陕西省"],
    "湖南省": ["湖北省", "江西省", "广东省", "广西壮族自治区", "贵州省", "重庆市"],
    "广东省": ["福建省", "江西省", "湖南省", "广西壮族自治区", "南海"],
    "广西壮族自治区": ["广东省", "湖南省", "贵州省", "云南省", "南海"],
    "海南省": ["南海"],
    "重庆市": ["陕西省", "湖北省", "湖南省", "贵州省", "四川省", "甘肃省"],
    "四川省": ["甘肃省", "陕西省", "重庆市", "贵州省", "云南省", "西藏自治区", "青海省"],
    "贵州省": ["重庆市", "四川省", "云南省", "广西壮族自治区", "湖南省"],
    "云南省": ["四川省", "贵州省", "广西壮族自治区", "西藏自治区"],
    "西藏自治区": ["新疆维吾尔自治区", "青海省", "四川省", "云南省"],
    "陕西省": ["内蒙古自治区", "山西省", "河南省", "湖北省", "重庆市", "四川省", "甘肃省", "宁夏回族自治区"],
    "甘肃省": ["宁夏回族自治区", "内蒙古自治区", "陕西省", "四川省", "青海省", "新疆维吾尔自治区"],
    "青海省": ["甘肃省", "新疆维吾尔自治区", "西藏自治区", "四川省"],
    "宁夏回族自治区": ["内蒙古自治区", "甘肃省", "陕西省"],
    "新疆维吾尔自治区": ["甘肃省", "青海省", "西藏自治区"],
    "台湾省": ["福建省", "东海"],
    "香港特别行政区": ["广东省", "南海"],
    "澳门特别行政区": ["广东省", "南海"],
}

# 省份重叠关系（用于overlap类型）
# 主要基于区域特点：沿海省份、沿江省份、山区省份等可能有重叠区域
PROVINCE_OVERLAP = [
    ("北京市", "河北省"),  # 北京被河北包围
    ("天津市", "河北省"),  # 天津被河北包围
    ("上海市", "江苏省"),  # 上海与江苏接壤
    ("上海市", "浙江省"),  # 上海与浙江隔海相望
    ("江苏省", "浙江省"),  # 两省接壤且有重叠区域
    ("江苏省", "安徽省"),  # 两省接壤
    ("浙江省", "安徽省"),  # 两省接壤
    ("浙江省", "江西省"),  # 两省接壤
    ("福建省", "浙江省"),  # 两省接壤
    ("安徽省", "湖北省"),  # 两省接壤
    ("湖北省", "河南省"),  # 两省接壤
    ("湖南省", "湖北省"),  # 两省接壤
    ("广东省", "湖南省"),  # 两省接壤
    ("广东省", "广西壮族自治区"),  # 两省接壤
    ("四川省", "重庆市"),  # 重庆原属四川
    ("四川省", "陕西省"),  # 两省接壤
    ("陕西省", "甘肃省"),  # 两省接壤
    ("河北省", "山西省"),  # 两省接壤
    ("河南省", "山东省"),  # 两省接壤
    ("辽宁省", "河北省"),  # 两省接壤
    ("内蒙古自治区", "甘肃省"),  # 两省接壤
    ("青海省", "甘肃省"),  # 两省接壤
    ("云南省", "贵州省"),  # 两省接壤
    ("云南省", "四川省"),  # 两省接壤
    ("西藏自治区", "四川省"),  # 两省接壤
    ("新疆维吾尔自治区", "甘肃省"),  # 两省接壤
    ("新疆维吾尔自治区", "青海省"),  # 两省接壤
]

def calculate_distance(coords1, coords2):
    """计算两点之间的近似直线距离（公里）"""
    lat1, lon1 = coords1[1], coords1[0]
    lat2, lon2 = coords2[1], coords2[0]

    # 使用Haversine公式
    R = 6371  # 地球半径（公里）
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_direction(coords1, coords2):
    """计算从点1到点2的方向"""
    lat1, lon1 = coords1[1], coords1[0]
    lat2, lon2 = coords2[1], coords2[0]

    dlon = math.radians(lon2 - lon1)
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    x = math.sin(dlon) * math.cos(lat2_rad)
    y = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))

    bearing = math.atan2(x, y)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360

    # 转换为中文方向
    if 337.5 <= bearing < 22.5:
        return "北方向"
    elif 22.5 <= bearing < 67.5:
        return "东北方向"
    elif 67.5 <= bearing < 112.5:
        return "东方向"
    elif 112.5 <= bearing < 157.5:
        return "东南方向"
    elif 157.5 <= bearing < 202.5:
        return "南方向"
    elif 202.5 <= bearing < 247.5:
        return "西南方向"
    elif 247.5 <= bearing < 292.5:
        return "西方向"
    else:
        return "西北方向"

def get_difficulty():
    """根据分布返回难度级别：easy 30%, medium 50%, hard 20%"""
    rand = random.random()
    if rand < 0.3:
        return "easy"
    elif rand < 0.8:
        return "medium"
    else:
        return "hard"

def get_split():
    """根据分布返回split类型：train 80%, dev 10%, test 10%"""
    rand = random.random()
    if rand < 0.8:
        return "train"
    elif rand < 0.9:
        return "dev"
    else:
        return "test"

def create_prompt_text(entity1, entity2, topology_subtype, difficulty):
    """创建prompt_text模板"""

    # 拓扑关系描述
    topology_descriptions = {
        "within": f"{entity2['name']}位于{entity1['name']}内",
        "contains": f"{entity1['name']}包含{entity2['name']}",
        "adjacent": f"{entity1['name']}与{entity2['name']}相邻",
        "overlap": f"{entity1['name']}与{entity2['name']}区域重叠"
    }

    topology_desc = topology_descriptions.get(topology_subtype, "")

    # 难度提示
    difficulty_prompts = {
        "easy": "简单直观",
        "medium": "中等难度，需要一定的空间推理",
        "hard": "较难，需要深入的空间分析"
    }

    difficulty_prompt = difficulty_prompts.get(difficulty, "中等难度")

    # 预处理坐标
    e1_coords_str = json.dumps(entity1['coords'], ensure_ascii=False)
    e2_coords_str = json.dumps(entity2['coords'], ensure_ascii=False)

    # 预构建坐标字典字符串
    coords_dict_str = json.dumps({
        entity1['name']: entity1['coords'],
        entity2['name']: entity2['coords']
    }, ensure_ascii=False)

    # 使用字符串替换方式构建JSON示例
    # 先定义模板，然后替换占位符
    json_template = '''{
  "id": "geosr_topological_prompt_XXXX_YYYY",
  "spatial_relation_type": "topological",
  "question": "问题文本（关于包含、相邻等拓扑关系）",
  "answer": "答案文本",
  "reasoning_chain": [
    STEP1,
    STEP2,
    STEP3,
    STEP4,
    STEP5
  ],
  "entities": [
    ENTITY1,
    ENTITY2
  ],
  "spatial_tokens": SPATIAL_TOKENS,
  "difficulty": "DIFFICULTY",
  "topology_subtype": "TOPOLOGY_SUBTYPE"
}'''

    # 构建各部分
    step1 = f'{{"step": 1, "name": "entity_identification", "action": "extract_entities", "content": "识别问题中的地理实体...", "entities_involved": ["{entity1['name']}", "{entity2['name']}"]}}'
    step2 = '{"step": 2, "name": "spatial_relation_extraction", "action": "classify_relation", "content": "识别空间关系类型...", "relation_type": "topological"}'
    step3 = f'{{"step": 3, "name": "coordinate_retrieval", "action": "infer_entity_to_token", "content": "获取实体坐标信息...", "coordinates": {coords_dict_str}}}'
    step4 = f'{{"step": 4, "name": "spatial_calculation", "action": "determine_topology", "content": "判断拓扑关系...", "calculation_result": "{topology_desc}"}}'
    step5 = f'{{"step": 5, "name": "answer_generation", "action": "generate_answer", "content": "生成最终答案...", "final_answer": "{topology_desc}"}}'

    entity1_str = f'{{"name": "{entity1['name']}", "type": "{entity1['type']}", "coords": {e1_coords_str}}}'
    entity2_str = f'{{"name": "{entity2['name']}", "type": "{entity2['type']}", "coords": {e2_coords_str}}}'

    spatial_tokens = json.dumps([entity1['name'], entity2['name'], "包含", "相邻", "位于", "边界"], ensure_ascii=False)

    # 替换占位符
    json_example = json_template.replace('STEP1', step1) \
                                 .replace('STEP2', step2) \
                                 .replace('STEP3', step3) \
                                 .replace('STEP4', step4) \
                                 .replace('STEP5', step5) \
                                 .replace('ENTITY1', entity1_str) \
                                 .replace('ENTITY2', entity2_str) \
                                 .replace('SPATIAL_TOKENS', spatial_tokens) \
                                 .replace('DIFFICULTY', difficulty) \
                                 .replace('TOPOLOGY_SUBTYPE', topology_subtype)

    # 构建完整的prompt_text
    prompt_text = f"""请生成一个关于"{entity1['name']}"和"{entity2['name']}"之间拓扑关系的地理问题。

已知信息：
- {entity1['name']}：{entity1['type']}类型
- {entity2['name']}：{entity2['type']}类型
- 拓扑关系：{topology_desc}

请按照以下JSON格式返回，**reasoning_chain必须包含严格的5步推理**：
{json_example}

注意：
1. question应该关于包含、相邻、重叠等拓扑关系
2. answer应该准确描述拓扑关系
3. **reasoning_chain必须严格包含5步推理**，每步必须包含step, name, action, content字段
4. entities中每个实体必须包含coords字段（[经度, 纬度]格式）
5. spatial_tokens应包含4-8个与空间关系相关的关键词
请生成{difficulty_prompt}的问题。"""

    return prompt_text

def generate_within_prompts(cities, provinces, count):
    """生成within类型prompts（城市位于省份内）"""
    prompts = []
    prompt_id = 1

    # 建立省份->城市映射
    province_cities = defaultdict(list)
    for city in cities:
        province_name = city.get('province', '')
        if province_name:
            province_cities[province_name].append(city)

    # 生成prompts
    for _ in range(count):
        # 随机选择一个有城市的省份
        valid_provinces = [p for p in provinces if p['name'] in province_cities and province_cities[p['name']]]
        if not valid_provinces:
            continue

        province = random.choice(valid_provinces)
        cities_in_province = province_cities[province['name']]
        city = random.choice(cities_in_province)

        # 计算距离和方向
        distance = calculate_distance(province['coords'], city['coords'])
        direction = calculate_direction(province['coords'], city['coords'])
        difficulty = get_difficulty()
        split = get_split()

        prompt = {
            "id": f"prompt_{prompt_id:04d}",
            "split": split,
            "relation_type": "topological",
            "difficulty": difficulty,
            "topology_subtype": "within",
            "entity1": {
                "name": province['name'],
                "type": "province",
                "coords": province['coords']
            },
            "entity2": {
                "name": city['name'],
                "type": "city",
                "coords": city['coords']
            },
            "prompt_text": create_prompt_text(
                {"name": province['name'], "type": "province", "coords": province['coords']},
                {"name": city['name'], "type": "city", "coords": city['coords']},
                "within",
                difficulty
            ),
            "expected_direction": direction,
            "expected_distance": round(distance, 1)
        }

        prompts.append(prompt)
        prompt_id += 1

    return prompts

def generate_contains_prompts(cities, provinces, count):
    """生成contains类型prompts（省份包含城市）"""
    prompts = []
    prompt_id = 1

    # 建立省份->城市映射
    province_cities = defaultdict(list)
    for city in cities:
        province_name = city.get('province', '')
        if province_name:
            province_cities[province_name].append(city)

    # 生成prompts
    for _ in range(count):
        # 随机选择一个有城市的省份
        valid_provinces = [p for p in provinces if p['name'] in province_cities and province_cities[p['name']]]
        if not valid_provinces:
            continue

        province = random.choice(valid_provinces)
        cities_in_province = province_cities[province['name']]
        city = random.choice(cities_in_province)

        # 计算距离和方向
        distance = calculate_distance(province['coords'], city['coords'])
        direction = calculate_direction(province['coords'], city['coords'])
        difficulty = get_difficulty()
        split = get_split()

        prompt = {
            "id": f"prompt_{prompt_id:04d}",
            "split": split,
            "relation_type": "topological",
            "difficulty": difficulty,
            "topology_subtype": "contains",
            "entity1": {
                "name": province['name'],
                "type": "province",
                "coords": province['coords']
            },
            "entity2": {
                "name": city['name'],
                "type": "city",
                "coords": city['coords']
            },
            "prompt_text": create_prompt_text(
                {"name": province['name'], "type": "province", "coords": province['coords']},
                {"name": city['name'], "type": "city", "coords": city['coords']},
                "contains",
                difficulty
            ),
            "expected_direction": direction,
            "expected_distance": round(distance, 1)
        }

        prompts.append(prompt)
        prompt_id += 1

    return prompts

def generate_adjacent_prompts(provinces, count):
    """生成adjacent类型prompts（省份邻接）"""
    prompts = []
    prompt_id = 1

    # 获取所有邻接对
    adjacent_pairs = []
    for province1_name, neighbors in PROVINCE_ADJACENCY.items():
        province1 = next((p for p in provinces if p['name'] == province1_name), None)
        if not province1:
            continue

        for neighbor_name in neighbors:
            # 跳过非省份实体（如"渤海"、"东海"）
            if neighbor_name in ["渤海", "东海", "南海", "黄海"]:
                continue

            province2 = next((p for p in provinces if p['name'] == neighbor_name), None)
            if not province2:
                continue

            # 避免重复对
            pair = tuple(sorted([province1['name'], province2['name']]))
            if pair not in adjacent_pairs:
                adjacent_pairs.append(pair)

    # 生成prompts
    for _ in range(count):
        if not adjacent_pairs:
            break

        pair = random.choice(adjacent_pairs)
        province1 = next((p for p in provinces if p['name'] == pair[0]), None)
        province2 = next((p for p in provinces if p['name'] == pair[1]), None)

        if not province1 or not province2:
            continue

        # 计算距离和方向
        distance = calculate_distance(province1['coords'], province2['coords'])
        direction = calculate_direction(province1['coords'], province2['coords'])
        difficulty = get_difficulty()
        split = get_split()

        prompt = {
            "id": f"prompt_{prompt_id:04d}",
            "split": split,
            "relation_type": "topological",
            "difficulty": difficulty,
            "topology_subtype": "adjacent",
            "entity1": {
                "name": province1['name'],
                "type": "province",
                "coords": province1['coords']
            },
            "entity2": {
                "name": province2['name'],
                "type": "province",
                "coords": province2['coords']
            },
            "prompt_text": create_prompt_text(
                {"name": province1['name'], "type": "province", "coords": province1['coords']},
                {"name": province2['name'], "type": "province", "coords": province2['coords']},
                "adjacent",
                difficulty
            ),
            "expected_direction": direction,
            "expected_distance": round(distance, 1)
        }

        prompts.append(prompt)
        prompt_id += 1

    return prompts

def generate_overlap_prompts(entities, count):
    """生成overlap类型prompts（区域重叠）"""
    prompts = []
    prompt_id = 1

    provinces = [e for e in entities if e['type'] == 'province']
    cities = [e for e in entities if e['type'] == 'city']

    # 使用预定义的省份重叠对
    overlap_pairs = PROVINCE_OVERLAP.copy()

    # 生成prompts
    for _ in range(count):
        if len(overlap_pairs) > 0:
            # 使用预定义的省份对
            pair = random.choice(overlap_pairs)
            entity1 = next((e for e in provinces if e['name'] == pair[0]), None)
            entity2 = next((e for e in provinces if e['name'] == pair[1]), None)

            if not entity1 or not entity2:
                continue
        else:
            # 随机选择两个省份（省份间可能有边界重叠）
            entity1 = random.choice(provinces)
            entity2 = random.choice(provinces)

            if entity1['name'] == entity2['name']:
                continue

        # 计算距离和方向
        distance = calculate_distance(entity1['coords'], entity2['coords'])
        direction = calculate_direction(entity1['coords'], entity2['coords'])
        difficulty = get_difficulty()
        split = get_split()

        prompt = {
            "id": f"prompt_{prompt_id:04d}",
            "split": split,
            "relation_type": "topological",
            "difficulty": difficulty,
            "topology_subtype": "overlap",
            "entity1": {
                "name": entity1['name'],
                "type": entity1['type'],
                "coords": entity1['coords']
            },
            "entity2": {
                "name": entity2['name'],
                "type": entity2['type'],
                "coords": entity2['coords']
            },
            "prompt_text": create_prompt_text(
                {"name": entity1['name'], "type": entity1['type'], "coords": entity1['coords']},
                {"name": entity2['name'], "type": entity2['type'], "coords": entity2['coords']},
                "overlap",
                difficulty
            ),
            "expected_direction": direction,
            "expected_distance": round(distance, 1)
        }

        prompts.append(prompt)
        prompt_id += 1

    return prompts

def main():
    print("=" * 60)
    print("拓扑补充Prompts生成脚本")
    print("=" * 60)

    # 读取实体数据库
    print(f"\n正在读取实体数据库: {ENTITY_DB_FILE}")
    with open(ENTITY_DB_FILE, 'r', encoding='utf-8') as f:
        entity_db = json.load(f)

    entities = entity_db.get('entities', {})
    provinces = entities.get('provinces', [])
    cities = entities.get('cities', [])
    rivers = entities.get('rivers', [])

    print(f"  - 省份: {len(provinces)} 个")
    print(f"  - 城市: {len(cities)} 个")
    print(f"  - 河流: {len(rivers)} 个")

    # 统计城市所属省份
    province_city_count = defaultdict(int)
    for city in cities:
        province_name = city.get('province', '')
        if province_name:
            province_city_count[province_name] += 1

    print(f"\n有城市的省份: {len(province_city_count)} 个")
    for province, count in sorted(province_city_count.items(), key=lambda x: -x[1])[:10]:
        print(f"  - {province}: {count} 个城市")

    # 目标数量（根据2026-03-09需求更新）
    target_counts = {
        "within": 512,    # 城市-省份包含关系
        "contains": 374,  # 省份-城市被包含关系（补齐到600）
        "adjacent": 440,  # 省份邻接关系
        "overlap": 512    # 区域重叠关系（保持）
    }

    print(f"\n目标生成数量:")
    for subtype, count in target_counts.items():
        print(f"  - {subtype}: {count} 条")

    # 生成各类prompts
    all_prompts = []

    print(f"\n正在生成 within 类型prompts...")
    within_prompts = generate_within_prompts(cities, provinces, target_counts["within"])
    print(f"  生成 {len(within_prompts)} 条")
    all_prompts.extend(within_prompts)

    print(f"\n正在生成 contains 类型prompts...")
    contains_prompts = generate_contains_prompts(cities, provinces, target_counts["contains"])
    print(f"  生成 {len(contains_prompts)} 条")
    all_prompts.extend(contains_prompts)

    print(f"\n正在生成 adjacent 类型prompts...")
    adjacent_prompts = generate_adjacent_prompts(provinces, target_counts["adjacent"])
    print(f"  生成 {len(adjacent_prompts)} 条")
    all_prompts.extend(adjacent_prompts)

    print(f"\n正在生成 overlap 类型prompts...")
    # 合并所有实体用于overlap类型
    all_entities = provinces + cities
    overlap_prompts = generate_overlap_prompts(all_entities, target_counts["overlap"])
    print(f"  生成 {len(overlap_prompts)} 条")
    all_prompts.extend(overlap_prompts)

    # 统计信息
    print(f"\n{'=' * 60}")
    print("生成统计:")
    print(f"  总计: {len(all_prompts)} 条")

    # 按拓扑子类型统计
    subtype_counter = defaultdict(int)
    for prompt in all_prompts:
        subtype = prompt.get('topology_subtype', 'unknown')
        subtype_counter[subtype] += 1

    print(f"\n拓扑子类型分布:")
    for subtype in ['within', 'contains', 'adjacent', 'overlap']:
        count = subtype_counter.get(subtype, 0)
        pct = count / len(all_prompts) * 100 if all_prompts else 0
        print(f"  - {subtype}: {count} ({pct:.1f}%)")

    # 按难度统计
    difficulty_counter = defaultdict(int)
    for prompt in all_prompts:
        difficulty = prompt.get('difficulty', 'unknown')
        difficulty_counter[difficulty] += 1

    print(f"\n难度分布:")
    for difficulty in ['easy', 'medium', 'hard']:
        count = difficulty_counter.get(difficulty, 0)
        pct = count / len(all_prompts) * 100 if all_prompts else 0
        print(f"  - {difficulty}: {count} ({pct:.1f}%)")

    # 按split统计
    split_counter = defaultdict(int)
    for prompt in all_prompts:
        split = prompt.get('split', 'unknown')
        split_counter[split] += 1

    print(f"\nSplit分布:")
    for split in ['train', 'dev', 'test']:
        count = split_counter.get(split, 0)
        pct = count / len(all_prompts) * 100 if all_prompts else 0
        print(f"  - {split}: {count} ({pct:.1f}%)")

    # 创建输出结构
    output_data = {
        "metadata": {
            "version": "1.0",
            "description": "拓扑补充Prompts配置",
            "created_at": "2026-03-09",
            "total_count": len(all_prompts),
            "target_distribution": target_counts,
            "random_seed": 42
        },
        "prompts": all_prompts
    }

    # 保存输出
    print(f"\n正在保存到: {OUTPUT_FILE}")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print("生成完成！")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
