# -*- coding: utf-8 -*-
"""
解析器模块
"""

import re
from typing import Tuple

DIRECTIONS_8 = ["东", "东南", "南", "西南", "西", "西北", "北", "东北"]

DIRECTION_KEYWORDS = {
    "东": ["东", "东方", "正东", "偏东", "东边", "向东", "往东", "E", "east"],
    "南": ["南", "南方", "正南", "偏南", "南边", "向南", "往南", "S", "south"],
    "西": ["西", "西方", "正西", "偏西", "西边", "向西", "往西", "W", "west"],
    "北": ["北", "北方", "正北", "偏北", "北边", "向北", "往北", "N", "north"],
    "东北": ["东北", "东北方", "东北边", "向东北", "往东北", "NE", "northeast"],
    "东南": ["东南", "东南方", "东南边", "向东南", "往东南", "SE", "southeast"],
    "西北": ["西北", "西北方", "西北边", "向西北", "往西北", "NW", "northwest"],
    "西南": ["西南", "西南方", "西南边", "向西南", "往西南", "SW", "southwest"],
}

TOPOLOGY_KEYWORDS = {
    "包含": ["包含", "在...内", "在...中", "位于...内", "内含", "属于"],
    "相邻": ["相邻", "接壤", "交界", "毗邻", "相连", "连接", "边界"],
    "相交": ["相交", "交叉", "穿过", "跨越", "横穿", "经过"],
    "相离": ["相离", "分离", "不相连", "远离", "隔开"],
}

DISTANCE_PATTERNS = [
    r'(\d+(?:\.\d+)?)\s*公里',
    r'(\d+(?:\.\d+)?)\s*千米',
    r'(\d+(?:\.\d+)?)\s*km',
    r'(\d+(?:\.\d+)?)\s*米',
    r'(\d+(?:\.\d+)?)\s*m',
]

def extract_direction(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    for direction, keywords in DIRECTION_KEYWORDS.items():
        if direction in ["东北", "东南", "西北", "西南"]:
            for kw in keywords:
                if kw.lower() in text:
                    return direction
    for direction, keywords in DIRECTION_KEYWORDS.items():
        if direction in ["东", "南", "西", "北"]:
            for kw in keywords:
                if kw.lower() in text:
                    return direction
    return ""

def extract_topology(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    for topology, keywords in TOPOLOGY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return topology
    return ""

def extract_distance(text: str) -> Tuple[float, str]:
    if not text:
        return 0.0, ""
    for pattern in DISTANCE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if "公里" in match.group(0) or "km" in match.group(0).lower():
                unit = "公里"
            elif "千米" in match.group(0):
                unit = "公里"
            elif "米" in match.group(0) and "千米" not in match.group(0):
                unit = "米"
            elif "m" in match.group(0).lower() and "km" not in match.group(0).lower():
                unit = "米"
            else:
                unit = "公里"
            return value, unit
    return 0.0, ""

def normalize_direction(direction: str) -> str:
    direction = direction.strip().replace("方向", "")
    aliases = {
        "正东": "东", "正南": "南", "正西": "西", "正北": "北",
        "偏东": "东", "偏南": "南", "偏西": "西", "偏北": "北",
        "东方": "东", "南方": "南", "西方": "西", "北方": "北",
        "E": "东", "S": "南", "W": "西", "N": "北",
        "NE": "东北", "SE": "东南", "NW": "西北", "SW": "西南"
    }
    return aliases.get(direction, direction)

def normalize_topology(topology: str) -> str:
    topology = topology.strip()
    aliases = {
        "内含": "包含", "在...内": "包含", "在...中": "包含",
        "接壤": "相邻", "交界": "相邻", "毗邻": "相邻",
        "交叉": "相交", "穿过": "相交",
        "分离": "相离", "不相连": "相离",
    }
    return aliases.get(topology, topology)

def normalize_distance(value: float, unit: str) -> float:
    unit_conversions = {
        "公里": 1.0, "千米": 1.0, "km": 1.0,
        "米": 0.001, "m": 0.001,
    }
    return value * unit_conversions.get(unit.lower(), 1.0)

def match_answer(prediction: str, reference: str, spatial_type: str = "auto") -> int:
    if not prediction or not reference:
        return 0
    
    prediction = prediction.strip()
    reference = reference.strip()
    
    if spatial_type == "direction" or (spatial_type == "auto" and extract_direction(reference)):
        pred_dir = normalize_direction(extract_direction(prediction))
        ref_dir = normalize_direction(extract_direction(reference))
        return int(pred_dir == ref_dir and bool(pred_dir))
    
    elif spatial_type == "topology" or (spatial_type == "auto" and extract_topology(reference)):
        pred_topo = normalize_topology(extract_topology(prediction))
        ref_topo = normalize_topology(extract_topology(reference))
        return int(pred_topo == ref_topo and bool(pred_topo))
    
    elif spatial_type == "distance" or (spatial_type == "auto" and extract_distance(reference)[0]):
        pred_val, pred_unit = extract_distance(prediction)
        ref_val, ref_unit = extract_distance(reference)
        if not pred_val or not ref_val:
            return 0
        pred_km = normalize_distance(pred_val, pred_unit)
        ref_km = normalize_distance(ref_val, ref_unit)
        tolerance = max(ref_km * 0.05, 1.0)
        return int(abs(pred_km - ref_km) <= tolerance)
    
    return int(prediction.lower() == reference.lower())
