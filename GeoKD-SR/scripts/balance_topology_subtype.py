#!/usr/bin/env python3
"""
拓扑子类型分布修复脚本
目标: 使主要拓扑子类型(within/contains/adjacent/overlap/disjoint)分布均匀(各约20%)

执行步骤:
1. 读取 generated_fixed.jsonl
2. 分离拓扑类型数据
3. 删除非标准子类型(touch/inside/crosses/separated/connected等)
4. 随机过滤disjoint至302条
5. 基于实体数据库生成补充数据
6. 合并所有数据
7. 输出到 balanced_topology.jsonl

作者: Claude
日期: 2026-03-08
"""
import json
import os
import random
import uuid
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple
import copy


# 省份邻接关系数据 (手动定义)
PROVINCE_ADJACENCY = {
    "河北省": ["北京市", "天津市", "辽宁省", "内蒙古自治区", "山西省", "河南省", "山东省"],
    "山西省": ["河北省", "内蒙古自治区", "陕西省", "河南省"],
    "内蒙古自治区": ["黑龙江省", "吉林省", "辽宁省", "河北省", "山西省", "陕西省", "宁夏回族自治区", "甘肃省"],
    "辽宁省": ["吉林省", "内蒙古自治区", "河北省"],
    "吉林省": ["黑龙江省", "内蒙古自治区", "辽宁省"],
    "黑龙江省": ["吉林省", "内蒙古自治区"],
    "江苏省": ["山东省", "安徽省", "浙江省", "上海市"],
    "浙江省": ["江苏省", "安徽省", "江西省", "福建省", "上海市"],
    "安徽省": ["江苏省", "山东省", "河南省", "湖北省", "江西省", "浙江省"],
    "福建省": ["浙江省", "江西省", "广东省"],
    "江西省": ["安徽省", "湖北省", "湖南省", "广东省", "福建省", "浙江省"],
    "山东省": ["河北省", "河南省", "安徽省", "江苏省"],
    "河南省": ["河北省", "山西省", "陕西省", "湖北省", "安徽省", "山东省"],
    "湖北省": ["河南省", "安徽省", "江西省", "湖南省", "重庆市", "陕西省"],
    "湖南省": ["湖北省", "江西省", "广东省", "广西壮族自治区", "贵州省", "重庆市"],
    "广东省": ["江西省", "湖南省", "广西壮族自治区", "福建省", "海南省"],
    "广西壮族自治区": ["湖南省", "广东省", "云南省", "贵州省"],
    "海南省": ["广东省"],
    "重庆市": ["四川省", "贵州省", "湖南省", "湖北省", "陕西省"],
    "四川省": ["青海省", "甘肃省", "陕西省", "重庆市", "贵州省", "云南省", "西藏自治区"],
    "贵州省": ["四川省", "云南省", "广西壮族自治区", "湖南省", "重庆市"],
    "云南省": ["西藏自治区", "四川省", "贵州省", "广西壮族自治区"],
    "西藏自治区": ["新疆维吾尔自治区", "青海省", "四川省", "云南省"],
    "陕西省": ["山西省", "内蒙古自治区", "宁夏回族自治区", "甘肃省", "四川省", "重庆市", "湖北省", "河南省"],
    "甘肃省": ["内蒙古自治区", "宁夏回族自治区", "陕西省", "四川省", "青海省", "新疆维吾尔自治区"],
    "青海省": ["甘肃省", "新疆维吾尔自治区", "西藏自治区", "四川省"],
    "宁夏回族自治区": ["内蒙古自治区", "甘肃省", "陕西省"],
    "新疆维吾尔自治区": ["西藏自治区", "青海省", "甘肃省"],
    "北京市": ["河北省", "天津市"],
    "天津市": ["河北省", "北京市"],
    "上海市": ["江苏省", "浙江省"],
}

# 河流流经省份关系
RIVER_FLOW_PROVINCES = {
    "长江": ["青海省", "西藏自治区", "四川省", "云南省", "重庆市", "湖北省", "湖南省", "江西省", "安徽省", "江苏省", "上海市"],
    "黄河": ["青海省", "四川省", "甘肃省", "宁夏回族自治区", "内蒙古自治区", "山西省", "陕西省", "河南省", "山东省"],
    "珠江": ["云南省", "贵州省", "广西壮族自治区", "广东省"],
    "淮河": ["河南省", "安徽省", "江苏省"],
    "海河": ["河北省", "北京市", "天津市"],
    "辽河": ["河北省", "内蒙古自治区", "辽宁省"],
    "松花江": ["吉林省", "黑龙江省"],
    "汉江": ["陕西省", "湖北省"],
    "湘江": ["广西壮族自治区", "湖南省"],
    "赣江": ["江西省"],
    "嘉陵江": ["陕西省", "甘肃省", "四川省", "重庆市"],
    "闽江": ["福建省"],
}

# 河流流经城市
RIVER_FLOW_CITIES = {
    "长江": ["宜昌", "荆州", "岳阳", "武汉", "九江", "安庆", "芜湖", "南京", "镇江", "南通", "上海"],
    "黄河": ["兰州", "银川", "包头", "延安", "郑州", "开封", "济南", "东营"],
    "珠江": ["南宁", "广州", "佛山", "东莞", "深圳"],
    "淮河": ["信阳", "阜阳", "蚌埠", "淮安"],
    "松花江": ["吉林", "哈尔滨", "佳木斯"],
    "汉江": ["汉中", "十堰", "襄阳", "荆门", "武汉"],
}


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """加载jsonl文件"""
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"警告: {file_path} 第{line_num}行JSON解析失败: {e}")
        return data
    except Exception as e:
        print(f"错误: 无法读取文件 {file_path}: {e}")
        return []


def save_jsonl(data: List[Dict[str, Any]], file_path: str) -> None:
    """保存为jsonl文件"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        for record in data:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    print(f"已保存 {len(data)} 条记录到 {file_path}")


def load_entity_database(file_path: str) -> Dict[str, Any]:
    """加载实体数据库"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"错误: 无法加载实体数据库 {file_path}: {e}")
        return {}


def count_topology_by_subtype(data: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计topological类型的子类型分布"""
    counter = Counter()
    for record in data:
        if record.get("spatial_relation_type") == "topological":
            subtype = record.get("topology_subtype", "unknown")
            counter[subtype] += 1
    return dict(counter)


def generate_record_id(subtype: str) -> str:
    """生成唯一记录ID"""
    return f"geosr_topological_{subtype}_{uuid.uuid4().hex[:8]}"


def get_region_name(coords: List[float]) -> str:
    """根据坐标判断所属地理区域（中文大区名称）"""
    lon, lat = coords[0], coords[1]

    # 中国地理分区
    if lon < 105:
        return "西南" if lat < 35 else "西北"
    elif lon < 110:
        if lat > 42:
            return "西北"
        elif lat > 35:
            return "华北"
        else:
            return "西南"
    elif lon < 115:
        if lat > 42:
            return "东北"
        elif lat > 35:
            return "华北"
        else:
            return "华中"
    elif lon < 122:
        if lat > 42:
            return "东北"
        elif lat > 35:
            return "华北"
        elif lat > 28:
            return "华东"
        else:
            return "东南"
    else:
        if lat > 42:
            return "东北"
        elif lat > 30:
            return "华东"
        else:
            return "东南"


def get_location_description(entity_name: str, entity_type: str, coords: List[float]) -> str:
    """生成实体的地理位置描述"""
    region = get_region_name(coords)

    type_descriptions = {
        "province": f"{entity_name}位于中国{region}地区",
        "city": f"{entity_name}是一座{region}地区的城市",
        "river": f"{entity_name}是中国{region}地区的重要河流",
        "mountain": f"{entity_name}位于中国{region}地区",
        "lake": f"{entity_name}是中国{region}地区的湖泊",
    }

    return type_descriptions.get(entity_type, f"{entity_name}位于{region}地区")


def create_within_record(entity1: Dict, entity2: Dict, entity_db: Dict) -> Dict[str, Any]:
    """
    创建within类型记录
    entity1: 城市/地标
    entity2: 省份 (包含entity1)
    """
    e1_name = entity1.get("name", "")
    e2_name = entity2.get("name", "")
    e1_coords = entity1.get("coords", [0, 0])
    e2_coords = entity2.get("coords", [0, 0])

    # 多种问题模板 - 增加背景信息和多样性
    question_templates = [
        # 带背景信息的模板
        (f"{e1_name}是{e2_name}下辖的一个城市，请问从行政区划的角度来看，{e1_name}是否位于{e2_name}的行政区域范围内？", "medium"),
        (f"已知{e1_name}位于中国{get_region_name(e2_coords)}地区，{e2_name}是省级行政区。请判断{e1_name}是否位于{e2_name}境内？", "medium"),
        (f"{e1_name}是一座城市，其地理位置约为东经{e1_coords[0]:.1f}度、北纬{e1_coords[1]:.1f}度。请问该城市是否位于{e2_name}的管辖范围内？", "hard"),
        (f"从空间拓扑关系角度分析，{e1_name}与{e2_name}之间是否存在包含关系？即{e1_name}是否位于{e2_name}内部？", "hard"),
        # 简洁模板
        (f"{e1_name}是否位于{e2_name}内？", "easy"),
        (f"请判断：{e1_name}在{e2_name}的行政区域内吗？", "easy"),
    ]

    question, difficulty = random.choice(question_templates)

    # 多种答案模板
    answer_templates = [
        f"是的，{e1_name}位于{e2_name}内。从行政区划来看，{e1_name}是{e2_name}下辖的城市，其行政管辖权归属于{e2_name}。",
        f"确认，{e1_name}确实位于{e2_name}境内。在空间拓扑关系中，这属于典型的'包含'关系，即点（城市）位于面（省份）内部。",
        f"是的，{e1_name}位于{e2_name}的行政区域范围内。{e1_name}作为{e2_name}的下级行政单位，其地理空间完全被{e2_name}的边界所包围。",
    ]
    answer = random.choice(answer_templates)

    reasoning_chain = [
        {
            "step": 1,
            "name": "entity_identification",
            "action": "extract_entities",
            "content": f"识别问题中的地理实体：'{e1_name}'（城市类型，点状要素）和'{e2_name}'（省份类型，面状要素）。需要判断两者之间的空间拓扑包含关系。",
            "entities_involved": [e2_name, e1_name]
        },
        {
            "step": 2,
            "name": "spatial_relation_extraction",
            "action": "classify_relation",
            "content": f"分析问题核心，关键词'位于...内'或'包含关系'表明需要判断拓扑空间关系。具体为判定实体'{e1_name}'是否在实体'{e2_name}'的空间边界内部，属于拓扑关系中的'within'（被包含）关系查询。",
            "relation_type": "topological"
        },
        {
            "step": 3,
            "name": "coordinate_retrieval",
            "action": "infer_entity_to_token",
            "content": f"检索并获取实体的地理坐标及行政区划信息：{e2_name}位于中国{get_region_name(e2_coords)}地区，中心坐标约为({e2_coords[0]:.4f}°E, {e2_coords[1]:.4f}°N)；{e1_name}坐标约为({e1_coords[0]:.4f}°E, {e1_coords[1]:.4f}°N)。",
            "coordinates": {e2_name: e2_coords, e1_name: e1_coords}
        },
        {
            "step": 4,
            "name": "spatial_calculation",
            "action": "determine_topology",
            "content": f"执行拓扑空间判断：根据行政区划层级数据，{e1_name}是{e2_name}下辖的行政单位。从空间位置分析，{e1_name}的坐标点完全落在{e2_name}的行政边界多边形内部，两者构成'点在面内'的拓扑关系。",
            "calculation_result": f"{e1_name}位于{e2_name}内部（Within关系成立）"
        },
        {
            "step": 5,
            "name": "answer_generation",
            "action": "generate_answer",
            "content": f"基于拓扑计算结果和行政区划归属关系，生成肯定性回答，明确指出{e1_name}位于{e2_name}的行政管辖范围内。",
            "final_answer": f"{e1_name}位于{e2_name}内"
        }
    ]

    return {
        "id": generate_record_id("within"),
        "spatial_relation_type": "topological",
        "question": question,
        "answer": answer,
        "reasoning_chain": reasoning_chain,
        "entities": [
            {"name": e2_name, "type": "province", "coords": e2_coords},
            {"name": e1_name, "type": "city", "coords": e1_coords}
        ],
        "spatial_tokens": [e1_name, e2_name, "位于", "内部", "包含", "边界", "行政区划", "拓扑关系", "管辖"],
        "difficulty": difficulty,
        "topology_subtype": "within",
        "split": "train"
    }


def create_contains_record(entity1: Dict, entity2: Dict) -> Dict[str, Any]:
    """
    创建contains类型记录
    entity1: 省份
    entity2: 城市 (被entity1包含)
    """
    e1_name = entity1.get("name", "")
    e2_name = entity2.get("name", "")
    e1_coords = entity1.get("coords", [0, 0])
    e2_coords = entity2.get("coords", [0, 0])

    # 多种问题模板
    question_templates = [
        (f"{e2_name}是{e1_name}下辖的一个城市。从行政区划的角度，{e1_name}的行政边界是否包含{e2_name}？", "medium"),
        (f"已知{e1_name}是中国的一个省级行政区，{e2_name}是一座城市。请问从空间拓扑关系来看，{e1_name}是否包含{e2_name}？", "hard"),
        (f"{e1_name}位于中国{get_region_name(e1_coords)}地区，{e2_name}的坐标约为({e2_coords[0]:.1f}°E, {e2_coords[1]:.1f}°N)。请判断{e1_name}是否包含{e2_name}？", "hard"),
        (f"从空间包含关系的角度分析，{e1_name}的行政区域范围是否覆盖{e2_name}？", "medium"),
        (f"{e1_name}是否包含{e2_name}？", "easy"),
        (f"请判断：{e2_name}是否在{e1_name}的管辖范围内？", "easy"),
    ]

    question, difficulty = random.choice(question_templates)

    # 多种答案模板
    answer_templates = [
        f"是的，{e1_name}包含{e2_name}。从行政区划来看，{e2_name}是{e1_name}下辖的城市，其行政区域完全在{e1_name}的边界范围内。",
        f"确认，{e1_name}的行政区域包含{e2_name}。在空间拓扑关系中，这体现了'面包含点'的包含关系，即省级行政区的边界多边形完全覆盖城市点的空间位置。",
        f"是的，{e1_name}确实包含{e2_name}。{e2_name}作为{e1_name}的下级行政单位，其地理空间被{e1_name}的行政边界所包围，形成典型的空间包含关系。",
    ]
    answer = random.choice(answer_templates)

    reasoning_chain = [
        {
            "step": 1,
            "name": "entity_identification",
            "action": "extract_entities",
            "content": f"识别问题中的地理实体：'{e1_name}'（省份类型，面状要素）和'{e2_name}'（城市类型，点状要素）。需要判断省份是否在空间上包含城市。",
            "entities_involved": [e1_name, e2_name]
        },
        {
            "step": 2,
            "name": "spatial_relation_extraction",
            "action": "classify_relation",
            "content": f"分析问题关键词'包含'或'覆盖'，确定需要判断的空间关系为拓扑关系中的'Contains'（包含）关系。具体判定面要素'{e1_name}'是否在空间上完全覆盖点要素'{e2_name}'。",
            "relation_type": "topological"
        },
        {
            "step": 3,
            "name": "coordinate_retrieval",
            "action": "infer_entity_to_token",
            "content": f"检索实体空间信息：{e1_name}位于{get_region_name(e1_coords)}地区，中心坐标({e1_coords[0]:.4f}°E, {e1_coords[1]:.4f}°N)；{e2_name}坐标({e2_coords[0]:.4f}°E, {e2_coords[1]:.4f}°N)。",
            "coordinates": {e1_name: e1_coords, e2_name: e2_coords}
        },
        {
            "step": 4,
            "name": "spatial_calculation",
            "action": "determine_topology",
            "content": f"执行拓扑判断：基于行政区划数据，{e2_name}是{e1_name}下辖的行政单位。从空间几何分析，{e2_name}的坐标点完全落在{e1_name}的行政边界多边形内部，满足'Contains'拓扑关系的定义。",
            "calculation_result": f"{e1_name}包含{e2_name}（Contains关系成立）"
        },
        {
            "step": 5,
            "name": "answer_generation",
            "action": "generate_answer",
            "content": f"基于拓扑计算结果和行政隶属关系，生成肯定性回答，明确指出{e1_name}的行政区域包含{e2_name}。",
            "final_answer": f"{e1_name}包含{e2_name}"
        }
    ]

    return {
        "id": generate_record_id("contains"),
        "spatial_relation_type": "topological",
        "question": question,
        "answer": answer,
        "reasoning_chain": reasoning_chain,
        "entities": [
            {"name": e1_name, "type": "province", "coords": e1_coords},
            {"name": e2_name, "type": "city", "coords": e2_coords}
        ],
        "spatial_tokens": [e1_name, e2_name, "包含", "覆盖", "边界", "行政区划", "拓扑关系", "管辖"],
        "difficulty": difficulty,
        "topology_subtype": "contains",
        "split": "train"
    }


def create_adjacent_record(entity1: Dict, entity2: Dict, is_adjacent: bool = True) -> Dict[str, Any]:
    """
    创建adjacent类型记录
    entity1, entity2: 两个相邻的省份或城市
    """
    e1_name = entity1.get("name", "")
    e2_name = entity2.get("name", "")
    e1_coords = entity1.get("coords", [0, 0])
    e2_coords = entity2.get("coords", [0, 0])
    e1_type = entity1.get("type", "province")
    e2_type = entity2.get("type", "province")

    if is_adjacent:
        # 多种问题模板
        question_templates = [
            (f"{e1_name}和{e2_name}都是中国的省级行政区。请从空间拓扑的角度判断，这两个省份是否相邻（即是否有共同的行政边界）？", "medium"),
            (f"已知{e1_name}位于中国{get_region_name(e1_coords)}地区，{e2_name}位于{get_region_name(e2_coords)}地区。请问在行政区划上，{e1_name}与{e2_name}是否接壤？", "medium"),
            (f"从地理空间邻接关系分析，{e1_name}和{e2_name}之间是否存在共同的边界线？", "hard"),
            (f"{e1_name}的地理坐标中心约为({e1_coords[0]:.1f}°E, {e1_coords[1]:.1f}°N)，{e2_name}的中心约为({e2_coords[0]:.1f}°E, {e2_coords[1]:.1f}°N)。请判断两省是否相邻？", "hard"),
            (f"{e1_name}和{e2_name}是否相邻？", "easy"),
            (f"请判断：{e1_name}与{e2_name}是否接壤？", "easy"),
        ]

        question, difficulty = random.choice(question_templates)

        # 多种答案模板
        answer_templates = [
            f"是的，{e1_name}和{e2_name}相邻。这两个省份在行政区划上存在共同的边界线，属于空间拓扑关系中的'邻接'（Adjacent）关系。",
            f"确认，{e1_name}与{e2_name}是相邻省份。从地理空间分布来看，两省的行政边界相接，形成直接的空间邻接关系。",
            f"是的，{e1_name}和{e2_name}相互接壤。在拓扑空间关系中，两省的边界多边形共享一条公共边，属于典型的空间邻接关系。",
        ]
        answer = random.choice(answer_templates)
        calc_result = f"{e1_name}与{e2_name}相邻"
    else:
        question = f"{e1_name}和{e2_name}是否相邻？"
        answer = f"不，{e1_name}和{e2_name}不相邻。"
        calc_result = f"{e1_name}与{e2_name}不相邻"
        difficulty = "medium"

    reasoning_chain = [
        {
            "step": 1,
            "name": "entity_identification",
            "action": "extract_entities",
            "content": f"识别问题中的地理实体：'{e1_name}'（{e1_type}类型）和'{e2_name}'（{e2_type}类型）。需要判断两者之间的空间邻接关系。",
            "entities_involved": [e1_name, e2_name]
        },
        {
            "step": 2,
            "name": "spatial_relation_extraction",
            "action": "classify_relation",
            "content": f"分析问题关键词'相邻'、'接壤'或'共同边界'，确定空间关系类型为拓扑关系中的'Adjacent'（邻接）关系。需要判断两个面要素的边界是否相交。",
            "relation_type": "topological"
        },
        {
            "step": 3,
            "name": "coordinate_retrieval",
            "action": "infer_entity_to_token",
            "content": f"获取实体的空间位置信息：{e1_name}位于{get_region_name(e1_coords)}地区，坐标({e1_coords[0]:.4f}°E, {e1_coords[1]:.4f}°N)；{e2_name}位于{get_region_name(e2_coords)}地区，坐标({e2_coords[0]:.4f}°E, {e2_coords[1]:.4f}°N)。",
            "coordinates": {e1_name: e1_coords, e2_name: e2_coords}
        },
        {
            "step": 4,
            "name": "spatial_calculation",
            "action": "determine_topology",
            "content": f"执行邻接关系判断：根据行政区划边界数据，分析{e1_name}和{e2_name}的行政边界多边形。判断两省边界是否存在公共边（即边界线相交但内部不相交）。",
            "calculation_result": calc_result
        },
        {
            "step": 5,
            "name": "answer_generation",
            "action": "generate_answer",
            "content": f"基于拓扑判断结果，生成{'肯定' if is_adjacent else '否定'}性回答，明确两省的空间邻接状态。",
            "final_answer": calc_result
        }
    ]

    return {
        "id": generate_record_id("adjacent"),
        "spatial_relation_type": "topological",
        "question": question,
        "answer": answer,
        "reasoning_chain": reasoning_chain,
        "entities": [
            {"name": e1_name, "type": e1_type, "coords": e1_coords},
            {"name": e2_name, "type": e2_type, "coords": e2_coords}
        ],
        "spatial_tokens": [e1_name, e2_name, "相邻", "接壤", "邻接", "边界", "共同边界", "拓扑关系"],
        "difficulty": difficulty,
        "topology_subtype": "adjacent",
        "split": "train"
    }


def create_overlap_record(river: Dict, location: Dict) -> Dict[str, Any]:
    """
    创建overlap类型记录
    river: 河流实体
    location: 省份或城市 (河流流经该地区)
    """
    river_name = river.get("name", "")
    loc_name = location.get("name", "")
    river_coords = river.get("coords", [0, 0])
    loc_coords = location.get("coords", [0, 0])
    loc_type = location.get("type", "province")
    river_length = river.get("length", 0)

    # 多种问题模板
    question_templates = [
        (f"{river_name}是中国重要的河流之一，全长约{river_length}公里。请判断{river_name}是否流经{loc_name}地区？", "medium"),
        (f"已知{river_name}发源于{river.get('origin', '高原')}，最终注入{river.get('mouth', '海洋')}。请问从空间拓扑关系来看，{river_name}的河道是否穿越{loc_name}？", "hard"),
        (f"{loc_name}位于中国{get_region_name(loc_coords)}地区。请分析该地区与{river_name}之间的空间重叠关系，判断{river_name}是否流经{loc_name}？", "hard"),
        (f"从河流水系的空间分布角度分析，{river_name}是否与{loc_name}存在空间交叉或穿越关系？", "hard"),
        (f"{river_name}是否流经{loc_name}？", "easy"),
        (f"请判断：{river_name}的河道是否经过{loc_name}？", "easy"),
    ]

    question, difficulty = random.choice(question_templates)

    # 多种答案模板
    answer_templates = [
        f"是的，{river_name}流经{loc_name}。从空间拓扑关系来看，河流（线状要素）与地区（面状要素）之间存在'Overlap'（重叠/交叉）关系，即河流的河道穿越了该地区的行政边界。",
        f"确认，{river_name}确实流经{loc_name}地区。在地理空间中，{river_name}作为线状水体，其河道轨迹与{loc_name}的空间范围存在交集，形成了典型的空间重叠关系。",
        f"是的，{river_name}穿越{loc_name}。从拓扑学角度分析，河流的线状几何体与地区的面状几何体相交，两者共享部分空间区域，构成空间重叠（Overlap）关系。",
    ]
    answer = random.choice(answer_templates)

    reasoning_chain = [
        {
            "step": 1,
            "name": "entity_identification",
            "action": "extract_entities",
            "content": f"识别问题中的地理实体：'{river_name}'（河流类型，线状要素）和'{loc_name}'（{loc_type}类型，面状要素）。需要判断河流是否流经该地区。",
            "entities_involved": [river_name, loc_name]
        },
        {
            "step": 2,
            "name": "spatial_relation_extraction",
            "action": "classify_relation",
            "content": f"分析问题关键词'流经'、'穿越'或'经过'，确定空间关系类型为拓扑关系中的'Overlap'（重叠/交叉）关系。需要判断线要素（河流）是否与面要素（地区）相交。",
            "relation_type": "topological"
        },
        {
            "step": 3,
            "name": "coordinate_retrieval",
            "action": "infer_entity_to_token",
            "content": f"检索实体空间信息：{river_name}全长约{river_length}公里，发源于{river.get('origin', '高原')}，代表性坐标({river_coords[0]:.1f}°E, {river_coords[1]:.1f}°N)；{loc_name}位于{get_region_name(loc_coords)}，坐标({loc_coords[0]:.4f}°E, {loc_coords[1]:.4f}°N)。",
            "coordinates": {river_name: river_coords, loc_name: loc_coords}
        },
        {
            "step": 4,
            "name": "spatial_calculation",
            "action": "determine_topology",
            "content": f"执行重叠关系判断：分析{river_name}的河道轨迹与{loc_name}的行政边界。根据河流水系数据和行政区划数据，判断河流线要素是否穿越地区面要素的边界，即两者是否存在空间交集。",
            "calculation_result": f"{river_name}流经{loc_name}（Overlap关系成立）"
        },
        {
            "step": 5,
            "name": "answer_generation",
            "action": "generate_answer",
            "content": f"基于拓扑计算结果，生成肯定性回答，明确指出{river_name}流经{loc_name}地区，两者存在空间重叠关系。",
            "final_answer": f"{river_name}流经{loc_name}"
        }
    ]

    return {
        "id": generate_record_id("overlap"),
        "spatial_relation_type": "topological",
        "question": question,
        "answer": answer,
        "reasoning_chain": reasoning_chain,
        "entities": [
            {"name": river_name, "type": "river", "coords": river_coords},
            {"name": loc_name, "type": loc_type, "coords": loc_coords}
        ],
        "spatial_tokens": [river_name, loc_name, "流经", "穿越", "经过", "重叠", "交叉", "河道", "水系"],
        "difficulty": difficulty,
        "topology_subtype": "overlap",
        "split": "train"
    }


def generate_supplementary_within(city_province_pairs: List[Tuple[Dict, Dict]], count: int) -> List[Dict]:
    """生成within类型的补充数据"""
    records = []
    random.shuffle(city_province_pairs)

    for i in range(count):
        city, province = city_province_pairs[i % len(city_province_pairs)]
        records.append(create_within_record(city, province, {}))

    return records


def generate_supplementary_contains(city_province_pairs: List[Tuple[Dict, Dict]], count: int) -> List[Dict]:
    """生成contains类型的补充数据"""
    records = []
    random.shuffle(city_province_pairs)

    for i in range(count):
        city, province = city_province_pairs[i % len(city_province_pairs)]
        records.append(create_contains_record(province, city))

    return records


def generate_supplementary_adjacent(provinces: List[Dict], count: int) -> List[Dict]:
    """生成adjacent类型的补充数据"""
    records = []
    province_dict = {p["name"]: p for p in provinces}

    # 收集所有相邻的省份对
    adjacent_pairs = []
    for p1_name, neighbors in PROVINCE_ADJACENCY.items():
        if p1_name in province_dict:
            for p2_name in neighbors:
                if p2_name in province_dict:
                    adjacent_pairs.append((province_dict[p1_name], province_dict[p2_name]))

    random.shuffle(adjacent_pairs)

    for i in range(count):
        p1, p2 = adjacent_pairs[i % len(adjacent_pairs)]
        records.append(create_adjacent_record(p1, p2, is_adjacent=True))

    return records


def generate_supplementary_overlap(rivers: List[Dict], provinces: List[Dict], cities: List[Dict], count: int) -> List[Dict]:
    """生成overlap类型的补充数据"""
    records = []
    province_dict = {p["name"]: p for p in provinces}
    city_dict = {c["name"]: c for c in cities}

    # 收集河流-省份对和河流-城市对
    river_location_pairs = []

    for river in rivers:
        river_name = river.get("name", "")
        if river_name in RIVER_FLOW_PROVINCES:
            for prov_name in RIVER_FLOW_PROVINCES[river_name]:
                if prov_name in province_dict:
                    river_location_pairs.append((river, province_dict[prov_name]))

        if river_name in RIVER_FLOW_CITIES:
            for city_name in RIVER_FLOW_CITIES[river_name]:
                if city_name in city_dict:
                    river_location_pairs.append((river, city_dict[city_name]))

    random.shuffle(river_location_pairs)

    for i in range(count):
        river, location = river_location_pairs[i % len(river_location_pairs)]
        records.append(create_overlap_record(river, location))

    return records


def main():
    """主函数"""
    random.seed(42)

    # 路径配置
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / "data" / "geosr_chain" / "generated_fixed.jsonl"
    entity_db_file = base_dir / "data" / "entity_database_expanded.json"
    output_file = base_dir / "data" / "geosr_chain" / "balanced_topology.jsonl"
    report_file = base_dir / "data" / "geosr_chain" / "topology_balance_report.md"

    print("=" * 60)
    print("拓扑子类型分布修复脚本")
    print("=" * 60)

    # 步骤1: 加载数据
    print("\n[步骤1] 加载数据...")
    all_data = load_jsonl(str(input_file))
    entity_db = load_entity_database(str(entity_db_file))

    if not all_data:
        print("错误: 无法加载数据文件")
        return

    print(f"  加载记录数: {len(all_data)}")
    print(f"  实体数据库版本: {entity_db.get('metadata', {}).get('version', 'unknown')}")

    # 统计原始分布
    original_counts = count_topology_by_subtype(all_data)
    print("\n[原始拓扑子类型分布]")
    for subtype, count in sorted(original_counts.items(), key=lambda x: -x[1]):
        print(f"  {subtype}: {count}")

    # 步骤2: 分离拓扑类型数据和非拓扑数据
    print("\n[步骤2] 分离拓扑类型数据...")
    topo_records = [r for r in all_data if r.get("spatial_relation_type") == "topological"]
    other_records = [r for r in all_data if r.get("spatial_relation_type") != "topological"]
    print(f"  拓扑类型记录: {len(topo_records)}")
    print(f"  非拓扑类型记录: {len(other_records)}")

    # 步骤3: 删除非标准子类型
    print("\n[步骤3] 删除非标准子类型...")
    standard_subtypes = {"within", "contains", "adjacent", "overlap", "disjoint"}
    non_standard_subtypes = {"touch", "inside", "crosses", "separated", "connected"}

    cleaned_topo = []
    removed_non_standard = Counter()

    for r in topo_records:
        subtype = r.get("topology_subtype", "unknown")
        if subtype in non_standard_subtypes:
            removed_non_standard[subtype] += 1
        else:
            cleaned_topo.append(r)

    print(f"  移除非标准子类型记录:")
    for subtype, count in removed_non_standard.items():
        print(f"    {subtype}: {count}")
    print(f"  清理后拓扑记录: {len(cleaned_topo)}")

    # 步骤4: 按子类型分组
    print("\n[步骤4] 按子类型分组...")
    by_subtype = defaultdict(list)
    for r in cleaned_topo:
        subtype = r.get("topology_subtype", "unknown")
        by_subtype[subtype].append(r)

    for subtype in standard_subtypes:
        print(f"  {subtype}: {len(by_subtype.get(subtype, []))}")

    # 步骤5: 过滤disjoint类型
    print("\n[步骤5] 过滤disjoint类型...")
    disjoint_records = by_subtype.get("disjoint", [])
    target_disjoint = 302

    random.shuffle(disjoint_records)
    disjoint_kept = disjoint_records[:target_disjoint]
    disjoint_removed = len(disjoint_records) - len(disjoint_kept)

    print(f"  原始disjoint记录: {len(disjoint_records)}")
    print(f"  保留: {len(disjoint_kept)}")
    print(f"  移除: {disjoint_removed}")

    # 步骤6: 准备实体数据库
    print("\n[步骤6] 准备实体数据库...")
    provinces = entity_db.get("entities", {}).get("provinces", [])
    cities = entity_db.get("entities", {}).get("cities", [])
    rivers = entity_db.get("entities", {}).get("rivers", [])

    print(f"  省份数: {len(provinces)}")
    print(f"  城市数: {len(cities)}")
    print(f"  河流数: {len(rivers)}")

    # 构建城市-省份对应关系
    province_dict = {p["name"]: p for p in provinces}
    city_province_pairs = []
    for city in cities:
        prov_name = city.get("province", "")
        if prov_name and prov_name in province_dict:
            city_province_pairs.append((city, province_dict[prov_name]))

    print(f"  城市-省份对: {len(city_province_pairs)}")

    # 步骤7: 计算需要补充的数量
    print("\n[步骤7] 计算需要补充的数量...")
    current_counts = {
        "disjoint": len(disjoint_kept),
        "contains": len(by_subtype.get("contains", [])),
        "within": len(by_subtype.get("within", [])),
        "adjacent": len(by_subtype.get("adjacent", [])),
        "overlap": len(by_subtype.get("overlap", []))
    }

    target_per_type = 302
    needed = {
        "disjoint": 0,
        "contains": max(0, target_per_type - current_counts["contains"]),
        "within": max(0, target_per_type - current_counts["within"]),
        "adjacent": max(0, target_per_type - current_counts["adjacent"]),
        "overlap": max(0, target_per_type - current_counts["overlap"])
    }

    print(f"  目标每类数量: {target_per_type}")
    print(f"  需要补充:")
    for subtype, count in needed.items():
        print(f"    {subtype}: {count} (当前: {current_counts[subtype]})")

    # 步骤8: 生成补充数据
    print("\n[步骤8] 生成补充数据...")
    supplementary_records = []

    # 生成within补充数据
    if needed["within"] > 0:
        print(f"  生成within: {needed['within']}条...")
        within_records = generate_supplementary_within(city_province_pairs, needed["within"])
        supplementary_records.extend(within_records)
        print(f"    完成: {len(within_records)}条")

    # 生成contains补充数据
    if needed["contains"] > 0:
        print(f"  生成contains: {needed['contains']}条...")
        contains_records = generate_supplementary_contains(city_province_pairs, needed["contains"])
        supplementary_records.extend(contains_records)
        print(f"    完成: {len(contains_records)}条")

    # 生成adjacent补充数据
    if needed["adjacent"] > 0:
        print(f"  生成adjacent: {needed['adjacent']}条...")
        adjacent_records = generate_supplementary_adjacent(provinces, needed["adjacent"])
        supplementary_records.extend(adjacent_records)
        print(f"    完成: {len(adjacent_records)}条")

    # 生成overlap补充数据
    if needed["overlap"] > 0:
        print(f"  生成overlap: {needed['overlap']}条...")
        overlap_records = generate_supplementary_overlap(rivers, provinces, cities, needed["overlap"])
        supplementary_records.extend(overlap_records)
        print(f"    完成: {len(overlap_records)}条")

    print(f"  总补充记录: {len(supplementary_records)}")

    # 步骤9: 合并所有数据
    print("\n[步骤9] 合并所有数据...")
    balanced_topo = (
        disjoint_kept +
        by_subtype.get("contains", []) +
        by_subtype.get("within", []) +
        by_subtype.get("adjacent", []) +
        by_subtype.get("overlap", []) +
        supplementary_records
    )

    final_data = other_records + balanced_topo

    print(f"  拓扑类型记录: {len(balanced_topo)}")
    print(f"  非拓扑类型记录: {len(other_records)}")
    print(f"  最终总记录: {len(final_data)}")

    # 步骤10: 统计最终分布
    print("\n[步骤10] 统计最终分布...")
    final_counts = count_topology_by_subtype(final_data)
    total_topo = sum(final_counts.get(s, 0) for s in standard_subtypes)

    print("\n=== 最终拓扑子类型分布 ===")
    for subtype in standard_subtypes:
        count = final_counts.get(subtype, 0)
        percentage = (count / total_topo * 100) if total_topo > 0 else 0
        status = "[OK]" if 18 <= percentage <= 22 else "[!!]"
        print(f"  {status} {subtype}: {count} ({percentage:.2f}%)")
    print(f"\n  主要类型总计: {total_topo}")

    # 步骤11: 保存结果
    print("\n[步骤11] 保存结果...")
    save_jsonl(final_data, str(output_file))

    # 生成报告
    print("\n[步骤12] 生成报告...")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# 拓扑子类型分布修复报告\n\n")
        f.write(f"**生成时间**: 2026-03-08\n\n")

        f.write("## 1. 原始分布\n\n")
        f.write("| 子类型 | 数量 | 占比 |\n")
        f.write("|--------|------|------|\n")
        original_total = sum(original_counts.values())
        for subtype in standard_subtypes:
            count = original_counts.get(subtype, 0)
            pct = (count / original_total * 100) if original_total > 0 else 0
            f.write(f"| {subtype} | {count} | {pct:.2f}% |\n")

        f.write("\n## 2. 处理操作\n\n")
        f.write("### 2.1 移除非标准子类型\n\n")
        for subtype, count in removed_non_standard.items():
            f.write(f"- {subtype}: {count}条\n")

        f.write("\n### 2.2 过滤disjoint类型\n\n")
        f.write(f"- 原始数量: {len(disjoint_records)}\n")
        f.write(f"- 保留数量: {len(disjoint_kept)}\n")
        f.write(f"- 移除数量: {disjoint_removed}\n")

        f.write("\n### 2.3 生成补充数据\n\n")
        f.write("| 子类型 | 需补充 | 已生成 |\n")
        f.write("|--------|--------|--------|\n")
        for subtype in ["within", "contains", "adjacent", "overlap"]:
            f.write(f"| {subtype} | {needed[subtype]} | {needed[subtype]} |\n")

        f.write("\n## 3. 最终分布\n\n")
        f.write("| 子类型 | 数量 | 占比 | 状态 |\n")
        f.write("|--------|------|------|------|\n")
        for subtype in standard_subtypes:
            count = final_counts.get(subtype, 0)
            pct = (count / total_topo * 100) if total_topo > 0 else 0
            status = "OK" if 18 <= pct <= 22 else "WARN"
            f.write(f"| {subtype} | {count} | {pct:.2f}% | {status} |\n")

        f.write(f"\n**主要类型总计**: {total_topo}\n")
        f.write(f"**非拓扑类型记录**: {len(other_records)}\n")
        f.write(f"**总记录数**: {len(final_data)}\n")

    print(f"  报告已保存: {report_file}")

    print("\n" + "=" * 60)
    print("修复完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
