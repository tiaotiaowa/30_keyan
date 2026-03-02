"""
GeoSR-Bench评测基准生成器

生成1000道地理空间推理评测题目，涵盖三个维度：
- D1: 空间关系理解 (400题)
- D2: 空间推理能力 (400题)
- D3: 地理知识融合 (200题)
"""

import json
import random
import math
import sys
from typing import Dict, List, Tuple, Any
from pathlib import Path

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# ==================== 辅助函数 ====================

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """
    计算从点1到点2的8方向方位角

    Args:
        lat1, lon1: 起点的纬度和经度
        lat2, lon2: 终点的纬度和经度

    Returns:
        方向字符串（东、南、西、北、东北、东南、西北、西南）
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))

    bearing = math.atan2(x, y)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360

    # 转换为8方向
    directions = ["东", "东南", "南", "西南", "西", "西北", "北", "东北"]
    index = round(bearing / 45) % 8
    return directions[index]


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    使用Haversine公式计算两点间的球面距离（公里）

    Args:
        lat1, lon1: 点1的纬度和经度
        lat2, lon2: 点2的纬度和经度

    Returns:
        距离（公里）
    """
    R = 6371  # 地球半径（公里）

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def generate_distractors(correct_answer: str, answer_type: str,
                         all_answers: List[str] = None, count: int = 3) -> List[str]:
    """
    为选择题生成干扰项

    Args:
        correct_answer: 正确答案
        answer_type: 答案类型（direction, province, city等）
        all_answers: 所有可能的答案列表
        count: 干扰项数量

    Returns:
        干扰项列表
    """
    if answer_type == "direction":
        directions = ["东", "南", "西", "北", "东北", "东南", "西北", "西南"]
        distractors = [d for d in directions if d != correct_answer]
    elif answer_type == "province":
        distractors = [p for p in all_answers if p != correct_answer]
    elif answer_type == "city":
        distractors = [c for c in all_answers if c != correct_answer]
    elif answer_type == "river":
        distractors = [r for r in all_answers if r != correct_answer]
    elif answer_type == "mountain":
        distractors = [m for m in all_answers if m != correct_answer]
    else:
        distractors = []

    return random.sample(distractors, min(count, len(distractors)))


# ==================== D1: 空间关系理解 ====================

def generate_direction_questions(entities: Dict, count: int = 150) -> List[Dict]:
    """
    生成方向关系题目

    Args:
        entities: 实体数据库
        count: 题目数量

    Returns:
        题目列表
    """
    questions = []
    cities = entities["cities"]

    for i in range(count):
        # 随机选择两个不同的城市
        city1, city2 = random.sample(cities, 2)

        # 计算方向
        direction = calculate_bearing(city1["lat"], city1["lon"],
                                     city2["lat"], city2["lon"])

        # 生成干扰项
        directions = ["东", "南", "西", "北", "东北", "东南", "西北", "西南"]
        distractors = generate_distractors(direction, "direction")

        # 随机排列选项
        options = distractors + [direction]
        random.shuffle(options)

        # 确定正确答案的字母
        answer_letter = chr(65 + options.index(direction))

        question = {
            "id": f"D1_DIR_{i+1:03d}",
            "dimension": "D1_空间关系理解",
            "task_type": "multiple_choice",
            "question": f"{city2['name']}在{city1['name']}的什么方向？",
            "options": [f"{chr(65+j)}. {options[j]}" for j in range(4)],
            "answer": answer_letter,
            "reasoning": f"{city2['name']}位于{city1['name']}的{direction}方向。"
        }

        questions.append(question)

    return questions


def generate_topology_questions(entities: Dict, count: int = 150) -> List[Dict]:
    """
    生成拓扑关系题目

    Args:
        entities: 实体数据库
        count: 题目数量

    Returns:
        题目列表
    """
    questions = []
    cities = entities["cities"]
    rivers = entities["rivers"]
    provinces = entities["provinces"]

    # 河流流经省份的题目
    for i in range(count // 2):
        river = random.choice(rivers)
        province = random.choice(provinces)

        # 确定答案
        answer = province["name"] in river["provinces"]

        # 随机决定是真命题还是假命题
        if not answer and random.random() < 0.5:
            # 如果是假命题，选择一个确实流经的省份
            valid_province = random.choice(river["provinces"])
            province = next(p for p in provinces if p["name"] == valid_province)
            answer = True

        question = {
            "id": f"D1_TOP_{i+1:03d}",
            "dimension": "D1_空间关系理解",
            "task_type": "true_false",
            "question": f"{river['name']}流经{province['name']}。",
            "answer": answer,
            "reasoning": f"{river['name']}流经的省份包括：{', '.join(river['provinces'][:-1])}和{river['provinces'][-1]}。"
        }

        questions.append(question)

    # 城市位于省份的题目
    for i in range(count // 2, count):
        city = random.choice(cities)
        province_name = city["province"]

        # 有时使用省份名，有时使用城市所在的省份
        if random.random() < 0.3:
            # 生成假命题
            other_provinces = [p["name"] for p in provinces if p["name"] != province_name]
            fake_province = random.choice(other_provinces)
            answer = False
            question_text = f"{city['name']}位于{fake_province}。"
            reasoning = f"{city['name']}位于{province_name}，不位于{fake_province}。"
        else:
            answer = True
            question_text = f"{city['name']}位于{province_name}。"
            reasoning = f"{city['name']}确实位于{province_name}。"

        question = {
            "id": f"D1_TOP_{i+1:03d}",
            "dimension": "D1_空间关系理解",
            "task_type": "true_false",
            "question": question_text,
            "answer": answer,
            "reasoning": reasoning
        }

        questions.append(question)

    return questions


def generate_metric_questions(entities: Dict, count: int = 100) -> List[Dict]:
    """
    生成度量关系题目（距离计算）

    Args:
        entities: 实体数据库
        count: 题目数量

    Returns:
        题目列表
    """
    questions = []
    cities = entities["cities"]

    for i in range(count):
        # 随机选择两个不同的城市
        city1, city2 = random.sample(cities, 2)

        # 计算距离
        distance = calculate_distance(city1["lat"], city1["lon"],
                                     city2["lat"], city2["lon"])

        # 四舍五入到十位
        rounded_distance = round(distance / 10) * 10

        question = {
            "id": f"D1_MET_{i+1:03d}",
            "dimension": "D1_空间关系理解",
            "task_type": "fill_blank",
            "question": f"从{city1['name']}到{city2['name']}的直线距离大约是多少公里？（请填写整数）",
            "answer": int(rounded_distance),
            "tolerance": 50,
            "reasoning": f"使用球面距离公式计算，{city1['name']}到{city2['name']}的直线距离约为{distance:.1f}公里。"
        }

        questions.append(question)

    return questions


# ==================== D2: 空间推理能力 ====================

def generate_single_step_reasoning(entities: Dict, count: int = 100) -> List[Dict]:
    """
    生成单步推理题目

    Args:
        entities: 实体数据库
        count: 题目数量

    Returns:
        题目列表
    """
    questions = []
    cities = entities["cities"]

    for i in range(count):
        # 随机选择三个城市
        city1, city2, city3 = random.sample(cities, 3)

        # 计算距离
        dist12 = calculate_distance(city1["lat"], city1["lon"],
                                    city2["lat"], city2["lon"])
        dist13 = calculate_distance(city1["lat"], city1["lon"],
                                    city3["lat"], city3["lon"])

        # 比较
        if dist12 < dist13:
            closer_city = city2["name"]
            farther_city = city3["name"]
        else:
            closer_city = city3["name"]
            farther_city = city2["name"]

        # 生成选项
        options_text = [closer_city, farther_city, city1["name"],
                       random.choice([c["name"] for c in cities if c["name"] not in
                                    [closer_city, farther_city, city1["name"]]])]
        random.shuffle(options_text)

        answer_letter = chr(65 + options_text.index(closer_city))

        question = {
            "id": f"D2_SINGLE_{i+1:03d}",
            "dimension": "D2_空间推理能力",
            "task_type": "multiple_choice",
            "question": f"{city1['name']}离{city2['name']}和{city3['name']}哪个更近？",
            "options": [f"{chr(65+j)}. {options_text[j]}" for j in range(4)],
            "answer": answer_letter,
            "reasoning": f"{city1['name']}到{city2['name']}的距离约{dist12:.0f}公里，到{city3['name']}的距离约{dist13:.0f}公里，因此离{closer_city}更近。"
        }

        questions.append(question)

    return questions


def generate_multi_hop_reasoning(entities: Dict, count: int = 200) -> List[Dict]:
    """
    生成多跳推理题目

    Args:
        entities: 实体数据库
        count: 题目数量

    Returns:
        题目列表
    """
    questions = []
    cities = entities["cities"]
    provinces = entities["provinces"]
    rivers = entities["rivers"]

    # 类型1: 中转城市推理
    generated_count = 0
    attempts = 0
    max_attempts = count // 2 * 3  # 允许更多尝试

    while generated_count < count // 2 and attempts < max_attempts:
        attempts += 1

        # 选择一个有河流经过的省份
        river = random.choice(rivers)
        province_name = random.choice(river["provinces"])

        # 找到该省份的省会
        try:
            province = next(p for p in provinces if p["name"] == province_name)
            capital = province["capital"]
            capital_city = next((c for c in cities if c["name"] == capital), None)

            if not capital_city:
                continue

            # 找到河流流经的另一个省份
            other_provinces = [p for p in river["provinces"] if p != province_name]
            if not other_provinces:
                continue
            other_province_name = random.choice(other_provinces)
            other_province = next(p for p in provinces if p["name"] == other_province_name)

            # 生成问题
            steps = [
                f"1. {river['name']}流经{province_name}",
                f"2. {province_name}的省会是{capital}",
                f"3. 因此{capital}位于{river['name']}流经的区域"
            ]

            answer = f"{capital}是{province_name}的省会，而{river['name']}流经{province_name}。"

            question = {
                "id": f"D2_MULTI_{generated_count+1:03d}",
                "dimension": "D2_空间推理能力",
                "task_type": "reasoning",
                "question": f"说明为什么{capital}与{river['name']}有关联？",
                "answer": answer,
                "reasoning_steps": steps
            }

            questions.append(question)
            generated_count += 1
        except StopIteration:
            continue

    # 类型2: 路径规划推理
    for i in range(count // 2, count):
        # 选择三个城市
        city1, city2, city3 = random.sample(cities, 3)

        # 计算直接距离和经停距离
        direct_dist = calculate_distance(city1["lat"], city1["lon"],
                                        city3["lat"], city3["lon"])
        detour_dist = (calculate_distance(city1["lat"], city1["lon"],
                                         city2["lat"], city2["lon"]) +
                      calculate_distance(city2["lat"], city2["lon"],
                                        city3["lat"], city3["lon"]))

        # 判断哪种路线更短
        if direct_dist < detour_dist:
            conclusion = f"从{city1['name']}直接到{city3['name']}更近"
            shorter = "direct"
        else:
            conclusion = f"从{city1['name']}经{city2['name']}到{city3['name']}更近"
            shorter = "detour"

        steps = [
            f"1. {city1['name']}直接到{city3['name']}的距离约{direct_dist:.0f}公里",
            f"2. {city1['name']}到{city2['name']}约{calculate_distance(city1['lat'], city1['lon'], city2['lat'], city2['lon']):.0f}公里",
            f"3. {city2['name']}到{city3['name']}约{calculate_distance(city2['lat'], city2['lon'], city3['lat'], city3['lon']):.0f}公里",
            f"4. 经{city2['name']}的总距离约{detour_dist:.0f}公里",
            f"5. 比较可知：{conclusion}"
        ]

        question = {
            "id": f"D2_MULTI_{i+1:03d}",
            "dimension": "D2_空间推理能力",
            "task_type": "reasoning",
            "question": f"分析从{city1['name']}到{city3['name']}的路线，直接走和经{city2['name']}中转，哪个更近？",
            "answer": conclusion,
            "reasoning_steps": steps
        }

        questions.append(question)

    return questions


def generate_constraint_solving(entities: Dict, count: int = 100) -> List[Dict]:
    """
    生成约束求解题目

    Args:
        entities: 实体数据库
        count: 题目数量

    Returns:
        题目列表
    """
    questions = []
    cities = entities["cities"]

    for i in range(count):
        # 选择一个目标城市
        target_city = random.choice(cities)

        # 约束条件1: 方向
        other_cities = [c for c in cities if c["name"] != target_city["name"]]
        ref_city1 = random.choice(other_cities)
        direction = calculate_bearing(ref_city1["lat"], ref_city1["lon"],
                                     target_city["lat"], target_city["lon"])

        # 约束条件2: 距离范围
        ref_city2 = random.choice([c for c in other_cities if c["name"] != ref_city1["name"]])
        distance = calculate_distance(ref_city2["lat"], ref_city2["lon"],
                                     target_city["lat"], target_city["lon"])

        # 约束条件3: 省份
        province = target_city["province"]

        # 生成选项
        options_cities = [target_city["name"]] + [c["name"] for c in random.sample(other_cities, 3)]
        random.shuffle(options_cities)

        answer_letter = chr(65 + options_cities.index(target_city["name"]))

        question = {
            "id": f"D2_CONST_{i+1:03d}",
            "dimension": "D2_空间推理能力",
            "task_type": "multiple_choice",
            "question": f"哪个城市满足以下条件：\n1. 在{ref_city1['name']}的{direction}方向\n2. 距离{ref_city2['name']}约{distance:.0f}公里\n3. 位于{province}",
            "options": [f"{chr(65+j)}. {options_cities[j]}" for j in range(4)],
            "answer": answer_letter,
            "reasoning": f"{target_city['name']}满足所有条件：位于{ref_city1['name']}的{direction}方向，距离{ref_city2['name']}约{distance:.0f}公里，位于{province}。"
        }

        questions.append(question)

    return questions


# ==================== D3: 地理知识融合 ====================

def generate_entity_recognition(entities: Dict, count: int = 50) -> List[Dict]:
    """
    生成实体识别题目

    Args:
        entities: 实体数据库
        count: 题目数量

    Returns:
        题目列表
    """
    questions = []
    cities = entities["cities"]
    rivers = entities["rivers"]
    mountains = entities["mountains"]
    landmarks = entities["landmarks"]

    # 城市类型识别
    for i in range(count // 4):
        city = random.choice(cities)

        type_desc = {
            "capital": "首都",
            "municipality": "直辖市",
            "city": "普通城市"
        }

        question = {
            "id": f"D3_ENT_{i+1:03d}",
            "dimension": "D3_地理知识融合",
            "task_type": "multiple_choice",
            "question": f"{city['name']}属于什么类型的城市？",
            "options": [
                "A. 直辖市",
                "B. 省会城市",
                "C. 普通地级市",
                "D. 特别行政区"
            ],
            "answer": "A" if city["type"] == "municipality" else ("B" if city["name"] == city["province"] else "C"),
            "reasoning": f"{city['name']}位于{city['province']}，属于{type_desc[city['type']]}。"
        }

        questions.append(question)

    # 地理实体类型
    for i in range(count // 4, count // 2):
        entity_type = random.choice(["河流", "山脉", "地标"])

        if entity_type == "河流":
            entity = random.choice(rivers)
            options = ["A. 河流", "B. 山脉", "C. 城市", "D. 湖泊"]
            answer = "A"
        elif entity_type == "山脉":
            entity = random.choice(mountains)
            options = ["A. 河流", "B. 山脉", "C. 平原", "D. 高原"]
            answer = "B"
        else:
            entity = random.choice(landmarks)
            options = ["A. 河流", "B. 山脉", "C. 地标/景点", "D. 城市"]
            answer = "C"

        question = {
            "id": f"D3_ENT_{i+1:03d}",
            "dimension": "D3_地理知识融合",
            "task_type": "multiple_choice",
            "question": f"{entity['name']}属于什么类型的地理实体？",
            "options": options,
            "answer": answer,
            "reasoning": f"{entity['name']}是一个{entity_type}。"
        }

        questions.append(question)

    # 位置识别
    for i in range(count // 2, count):
        landmark = random.choice(landmarks)

        # 生成干扰项
        other_cities = [l["city"] for l in landmarks if l["city"] != landmark["city"]]
        distractors = random.sample(other_cities, min(3, len(other_cities)))

        options_cities = distractors + [landmark["city"]]
        random.shuffle(options_cities)

        answer_letter = chr(65 + options_cities.index(landmark["city"]))

        question = {
            "id": f"D3_ENT_{i+1:03d}",
            "dimension": "D3_地理知识融合",
            "task_type": "multiple_choice",
            "question": f"{landmark['name']}位于哪个城市？",
            "options": [f"{chr(65+j)}. {options_cities[j]}" for j in range(len(options_cities))],
            "answer": answer_letter,
            "reasoning": f"{landmark['name']}位于{landmark['city']}。"
        }

        questions.append(question)

    return questions


def generate_commonsense_questions(entities: Dict, count: int = 100) -> List[Dict]:
    """
    生成常识应用题目

    Args:
        entities: 实体数据库
        count: 题目数量

    Returns:
        题目列表
    """
    questions = []
    cities = entities["cities"]

    # 气候常识（基于纬度）
    for i in range(count // 2):
        # 选择一个南方城市和一个北方城市
        southern_cities = [c for c in cities if c["lat"] > 25]
        northern_cities = [c for c in cities if c["lat"] < 35]

        if not southern_cities or not northern_cities:
            continue

        city1 = random.choice(southern_cities)
        city2 = random.choice(northern_cities)

        # 判断谁更北
        if city1["lat"] > city2["lat"]:
            northern_city, southern_city = city1, city2
        else:
            northern_city, southern_city = city2, city1

        question = {
            "id": f"D3_COMM_{i+1:03d}",
            "dimension": "D3_地理知识融合",
            "task_type": "multiple_choice",
            "question": f"下列哪个城市纬度更高，位于更北的位置？",
            "options": [
                f"A. {northern_city['name']}",
                f"B. {southern_city['name']}",
                f"C. 两者纬度相同",
                f"D. 无法判断"
            ],
            "answer": "A",
            "reasoning": f"{northern_city['name']}的纬度为{northern_city['lat']}°N，{southern_city['name']}的纬度为{southern_city['lat']}°N，因此{northern_city['name']}纬度更高，位于更北的位置。"
        }

        questions.append(question)

    # 经济常识（基于人口）
    for i in range(count // 2, count):
        city1, city2 = random.sample(cities, 2)

        if city1["population"] > city2["population"]:
            larger_city, smaller_city = city1, city2
        else:
            larger_city, smaller_city = city2, city1

        question = {
            "id": f"D3_COMM_{i+1:03d}",
            "dimension": "D3_地理知识融合",
            "task_type": "true_false",
            "question": f"{larger_city['name']}的人口比{smaller_city['name']}多。",
            "answer": True,
            "reasoning": f"{larger_city['name']}人口约{larger_city['population']:,}万，{smaller_city['name']}人口约{smaller_city['population']:,}万。"
        }

        questions.append(question)

    return questions


def generate_context_understanding(entities: Dict, count: int = 50) -> List[Dict]:
    """
    生成情境理解题目

    Args:
        entities: 实体数据库
        count: 题目数量

    Returns:
        题目列表
    """
    questions = []
    cities = entities["cities"]
    landmarks = entities["landmarks"]

    for i in range(count):
        # 创建一个旅行情境
        start_city = random.choice(cities)

        # 找到该城市附近的另一个城市
        distances = []
        for city in cities:
            if city["name"] != start_city["name"]:
                dist = calculate_distance(start_city["lat"], start_city["lon"],
                                         city["lat"], city["lon"])
                distances.append((city, dist))

        # 按距离排序，选择最近的几个
        distances.sort(key=lambda x: x[1])
        nearest_city = distances[0][0]

        # 找到目的地城市的地标
        dest_landmarks = [l for l in landmarks if l["city"] == nearest_city["name"]]
        if not dest_landmarks:
            dest_landmarks = [l for l in landmarks if l["city"] in
                             [c["name"] for c in cities]]

        if dest_landmarks:
            landmark = random.choice(dest_landmarks)
            context = f"小王从{start_city['name']}出发，想要去{nearest_city['name']}参观{landmark['name']}"
            question_text = f"{context}，请问{nearest_city['name']}在{start_city['name']}的什么方向？"

            direction = calculate_bearing(start_city["lat"], start_city["lon"],
                                         nearest_city["lat"], nearest_city["lon"])

            options_list = ["东", "南", "西", "北", "东北", "东南", "西北", "西南"]
            distractors = generate_distractors(direction, "direction")
            options = distractors + [direction]
            random.shuffle(options)

            answer_letter = chr(65 + options.index(direction))

            question = {
                "id": f"D3_CTX_{i+1:03d}",
                "dimension": "D3_地理知识融合",
                "task_type": "multiple_choice",
                "question": question_text,
                "options": [f"{chr(65+j)}. {options[j]}" for j in range(4)],
                "answer": answer_letter,
                "reasoning": f"{nearest_city['name']}位于{start_city['name']}的{direction}方向，两地相距约{distances[0][1]:.0f}公里。"
            }
        else:
            context = f"小李计划从{start_city['name']}出发旅行"
            question_text = f"{context}，他想去最近的大城市，从{start_city['name']}到{nearest_city['name']}是什么方向？"

            direction = calculate_bearing(start_city["lat"], start_city["lon"],
                                         nearest_city["lat"], nearest_city["lon"])

            options_list = ["东", "南", "西", "北", "东北", "东南", "西北", "西南"]
            distractors = generate_distractors(direction, "direction")
            options = distractors + [direction]
            random.shuffle(options)

            answer_letter = chr(65 + options.index(direction))

            question = {
                "id": f"D3_CTX_{i+1:03d}",
                "dimension": "D3_地理知识融合",
                "task_type": "multiple_choice",
                "question": question_text,
                "options": [f"{chr(65+j)}. {options[j]}" for j in range(4)],
                "answer": answer_letter,
                "reasoning": f"{nearest_city['name']}是距离{start_city['name']}最近的大城市之一，位于{start_city['name']}的{direction}方向。"
            }

        questions.append(question)

    return questions


# ==================== 主函数 ====================

def generate_benchmark(entity_db_path: str, output_path: str, total_questions: int = 1000):
    """
    生成完整的GeoSR-Bench评测基准

    Args:
        entity_db_path: 实体数据库路径
        output_path: 输出文件路径
        total_questions: 总题目数量
    """
    print(f"正在加载实体数据库: {entity_db_path}")
    with open(entity_db_path, 'r', encoding='utf-8') as f:
        entities = json.load(f)

    print(f"实体数据库加载完成:")
    print(f"  - 城市: {len(entities['cities'])}个")
    print(f"  - 省份: {len(entities['provinces'])}个")
    print(f"  - 河流: {len(entities['rivers'])}条")
    print(f"  - 山脉: {len(entities['mountains'])}座")
    print(f"  - 地标: {len(entities['landmarks'])}个")

    print("\n开始生成评测题目...")
    all_questions = []

    # D1: 空间关系理解 (400题)
    print("\n生成D1 - 空间关系理解 (400题)...")
    all_questions.extend(generate_direction_questions(entities, 150))
    print(f"  [OK] 方向关系: 150题")

    all_questions.extend(generate_topology_questions(entities, 150))
    print(f"  [OK] 拓扑关系: 150题")

    all_questions.extend(generate_metric_questions(entities, 100))
    print(f"  [OK] 度量关系: 100题")

    # D2: 空间推理能力 (400题)
    print("\n生成D2 - 空间推理能力 (400题)...")
    all_questions.extend(generate_single_step_reasoning(entities, 100))
    print(f"  [OK] 单步推理: 100题")

    all_questions.extend(generate_multi_hop_reasoning(entities, 200))
    print(f"  [OK] 多跳推理: 200题")

    all_questions.extend(generate_constraint_solving(entities, 100))
    print(f"  [OK] 约束求解: 100题")

    # D3: 地理知识融合 (200题)
    print("\n生成D3 - 地理知识融合 (200题)...")
    all_questions.extend(generate_entity_recognition(entities, 50))
    print(f"  [OK] 实体识别: 50题")

    all_questions.extend(generate_commonsense_questions(entities, 100))
    print(f"  [OK] 常识应用: 100题")

    all_questions.extend(generate_context_understanding(entities, 50))
    print(f"  [OK] 情境理解: 50题")

    # 创建输出目录
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 保存评测基准
    benchmark_data = {
        "benchmark_name": "GeoSR-Bench",
        "version": "v1.0",
        "description": "地理空间推理评测基准",
        "total_questions": len(all_questions),
        "dimensions": {
            "D1_空间关系理解": 400,
            "D2_空间推理能力": 400,
            "D3_地理知识融合": 200
        },
        "questions": all_questions
    }

    print(f"\n保存评测基准到: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, ensure_ascii=False, indent=2)

    # 验证和统计
    print("\n" + "="*50)
    print("评测基准生成完成！")
    print("="*50)

    # 验证题目数量
    print(f"\n【验证】题目数量统计:")
    print(f"  总题目数: {len(all_questions)}")

    # 按维度统计
    dim_count = {}
    type_count = {}
    for q in all_questions:
        dim = q["dimension"]
        task_type = q["task_type"]
        dim_count[dim] = dim_count.get(dim, 0) + 1
        type_count[task_type] = type_count.get(task_type, 0) + 1

    print(f"\n【统计】按维度分布:")
    for dim, count in sorted(dim_count.items()):
        print(f"  {dim}: {count}题")

    print(f"\n【统计】按题型分布:")
    for task_type, count in sorted(type_count.items()):
        print(f"  {task_type}: {count}题")

    # 验证ID唯一性
    print(f"\n【验证】ID唯一性检查:")
    ids = [q["id"] for q in all_questions]
    unique_ids = set(ids)
    if len(ids) == len(unique_ids):
        print(f"  [OK] 所有{len(ids)}个题目ID均唯一")
    else:
        print(f"  [X] 发现{len(ids) - len(unique_ids)}个重复ID")

    # 随机抽样检查
    print(f"\n【质量检查】随机抽样5题:")
    sample_questions = random.sample(all_questions, min(5, len(all_questions)))
    for i, q in enumerate(sample_questions, 1):
        print(f"\n  {i}. [{q['id']}] {q['task_type']}")
        print(f"     问题: {q['question'][:80]}...")
        if q['task_type'] == 'multiple_choice':
            print(f"     答案: {q['answer']}")
        elif q['task_type'] == 'true_false':
            print(f"     答案: {q['answer']}")
        elif q['task_type'] == 'fill_blank':
            print(f"     答案: {q['answer']} (±{q.get('tolerance', 0)})")

    print("\n" + "="*50)
    print(f"评测基准已保存至: {output_path}")
    print("="*50)


if __name__ == "__main__":
    # 设置路径
    base_dir = Path(__file__).parent.parent
    entity_db_path = base_dir / "data" / "entity_database.json"
    output_path = base_dir / "data" / "geosr_bench" / "geosr_bench_v1.json"

    # 生成评测基准
    generate_benchmark(str(entity_db_path), str(output_path), total_questions=1000)
