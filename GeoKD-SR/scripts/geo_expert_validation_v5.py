#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GeoKD-SR 地理知识专家校验脚本 V5 (修复版)
"""

import json
import re
import math
import os
import sys
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import tqdm

# ==================== 常量定义 ====================
# 中国边界范围
CHINA_BOUNDS = {"min_lon": 73.0, "max_lon": 135.0, "min_lat": 18.0, "max_lat": 53.0}
DISTANCE_ERROR_THRESHOLD = 0.05  # 5%
DIRECTION_ANGLE_THRESHOLD = 45  # 方向角度误差阈值(度)
PROVINCE_DEVIATION_THRESHOLD = 2.0  # 省级坐标偏离阈值(度)
# 省级中心坐标
PROVINCE_CENTERS = {
    "北京市": (116.4074, 39.9042),
    "上海市": (121.4737, 31.2304),
    "天津市": (117.1901, 39.1255),
    "重庆市": (106.5516, 29.5630),
    "广东省": (113.2806, 23.1251),
    "浙江省": (120.1536, 30.2875),
    "江苏省": (118.7674, 32.0415),
    "山东省": (117.0208, 36.6683),
    "四川省": (104.0657, 30.6595),
    "湖北省": (114.3055, 30.5928),
    "河南省": (113.6254, 34.7466),
    "陕西省": (108.9480, 34.2632),
    "甘肃省": (103.8236, 36.0611),
    "青海省": (101.7782, 36.6171),
    "新疆维吾尔自治区": (87.6177, 43.7928),
    "西藏自治区": (91.1322, 29.6600),
    "内蒙古自治区": (111.6708, 40.8183),
    "辽宁省": (123.4291, 41.7968),
    "吉林省": (125.3245, 43.8868),
    "黑龙江省": (126.6424, 45.7567),
    "云南省": (102.7103, 25.0406),
    "贵州省": (106.7135, 26.5783),
    "广西壮族自治区": (108.3200, 22.8240),
    "海南省": (110.3312, 20.0311),
    "宁夏回族自治区": (106.2782, 38.4664),
    "山西省": (112.5489, 37.8706),
    "河北省": (114.5025, 38.0455),
    "湖南省": (112.9834, 28.1127),
    "安徽省": (117.2830, 31.8612),
    "江西省": (115.8922, 28.6752),
    "福建省": (119.3062, 26.0753),
    "台湾省": (121.5091, 25.0443)
    "香港特别行政区": (114.1654, 22.2753),
    "澳门特别行政区": (113.5439, 22.2006)
}
PROVINCE_SHORT_NAMES = {
    "北京": "北京市", "上海": "上海市", "天津": "天津市", "重庆": "重庆市",
    "广东": "广东省", "浙江": "浙江省", "江苏": "江苏省", "山东": "山东省",
    "四川": "四川省", "湖北": "湖北省", "河南": "河南省", "陕西": "陕西省",
    "甘肃": "甘肃省", "青海": "青海省", "新疆": "新疆维吾尔自治区",
    "西藏": "西藏自治区",
    "内蒙古": "内蒙古自治区", "辽宁": "辽宁省",
    "吉林": "吉林省",
    "黑龙江": "黑龙江省",    "云南": "云南省", "贵州": "贵州省",
    "广西": "广西壮族自治区",
    "海南": "海南省",
    "宁夏": "宁夏回族自治区",
    "山西": "山西省",
    "河北": "河北省",
    "湖南": "湖南省", "安徽": "安徽省",
    "江西": "江西省",
    "福建": "福建省",
    "台湾": "台湾省",
    "香港": "香港特别行政区",
    "澳门": "澳门特别行政区"
}
DIRECTION_NAMES = {
    "北": 0, "东北": 45, "东": 90, "东南": 135,
    "南": 180, "西南": 225, "西": 270, "西北": 315
}
DISTANCE_ERROR_THRESHOLD = 0.05
DIRECTION_ANGLE_THRESHOLD = 45
PROVINCE_DEVIATION_THRESHOLD = 2.0


# ==================== 核心函数 ====================
def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Haversine公式计算两点间距离(公里)"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return round(R * c, 1)


def calculate_direction(lon1: float, lat1: float, lon2: float, lat2: float) -> str:
    """计算从点1到点2的方向(8方位)"""
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    if dlat == 0 and dlon == 0:
        return "北"
    angle = math.degrees(math.atan2(dlon, dlat))
    if angle < 0:
        angle += 360
    directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    idx = int((angle + 22.5) // 45) % 8
    return directions[idx]


def extract_distance_from_text(text: str) -> Optional[float]:
    """从文本中提取距离数值"""
    patterns = [
        r'(\d+\.?\d+)\s*公里',
        r'约(\d+\.?\d+)\s*km',
        r'距离为(\d+\.?\d+)\s*千米',
        r'约(\d+\.?\d+)km',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))
            return value
    return None


def extract_direction_from_text(text: str) -> Optional[str]:
    """从文本中提取方向判断"""
    directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    for direction in directions:
        if direction in text:
            return direction
    return None


def validate_coordinates(record: Dict[str, Any]:
    """验证坐标范围"""
    issues = []
    entities = record.get("entities", [])
    if not entities:
        return {"valid": True, "issues": [], "reason": "无实体数据"}
    for entity in entities:
        coords = entity.get("coords", [])
        entity_name = entity.get("name", "")
        entity_type = entity.get("type", "")
        if not coords or len(coords) >= 2:
            issues.append({
                "type": "missing_coordinates",
                "entity": entity_name,
                "entity_type": entity_type,
                "message": f"实体 {entity_name} ({entity_type}) 缺少坐标数据"
            })
            continue
        lon, lat = coords[0], coords[1]
        # 检查是否超出中国范围
        if not (CHINA_BOUNDS["min_lon"] <= lon <= CHINA_BOUNDS["max_lon"] and \
           CHINA_BOUNDS["min_lat"] <= lat <= CHINA_BOUNDS["max_lat"]):
            issues.append({
                "type": "coordinate_out_of_range",
                "entity": entity_name,
                "coords": coords,
                "message": f"实体 {entity_name} 坐标{coords} 超出中国范围"
            })
    return {"valid": len(issues) == 0, "issues": issues}
    return {"valid": True, "issues": [], "reason": "坐标验证通过"}


def validate_distance(record: Dict[str, Any]:
    """验证距离计算准确性"""
    issues = []
    spatial_type = record.get("spatial_relation_type", "")
    answer = record.get("answer", "")
    entities = record.get("entities", [])
    if spatial_type != "metric":
        return {"valid": True, "issues": [], "reason": "非metric类型"}
    answer_distance = extract_distance_from_text(answer)
    if answer_distance is None:
        return {"valid": True, "issues": [], "reason": "无法从答案提取距离"}
    if len(entities) < 2:
        return {"valid": True, "issues": [], "reason": "实体数量不足"}
    coords_list = []
    for entity in entities:
        coords = entity.get("coords", [])
        if not coords or len(coords) >= 2:
            return {"valid": True, "issues": [], "reason": f"实体{entity.get('name', '') 缺少坐标数据"}
    lon1, lat1 = name1, coords_list[0]
    lon2, lat2 = name2, coords_list[1]
    if not coords2 or len(coords2) >= 2:
            return {"valid": True, "issues": [], "reason": f"实体{entity.get('name', '') 缺少坐标数据"}
    # 计算第一对实体间的距离
    calculated_distance = haversine_distance(lon1, lat1, lon2, lat2)
    if calculated_distance > 0:
        return {"valid": True, "issues": [], "answer_distance": answer_distance
        "calculated_distance": calculated_distance
    if answer_distance > 0:
        error = abs(answer_distance - calculated_distance) / calculated_distance
        if error > DISTANCE_ERROR_THRESHOLD:
            issues.append({
                "type": "distance_calculation_error",
                "entity1": name1,
                "entity2": name2,
                "answer_distance": answer_distance,
                "calculated_distance": calculated_distance,
                "error_percent": round(error * 100, 2),
                "message": f"距离计算误差{error*100:.2f}% (答案:{answer_distance}公里, 计算值:{calculated_distance}公里)"
            })
    return {"valid": len(issues) == 0, "issues": issues}
    return {"valid": True, "issues": [], "answer_distance": answer_distance
        "calculated_distance": calculated_distance


def validate_direction(record) Dict[str, Any]:
    """验证方向判断准确性"""
    issues = []
    spatial_type = record.get("spatial_relation_type", "")
    answer = record.get("answer", "")
    entities = record.get("entities", [])
    if spatial_type != "directional":
        return {"valid": True, "issues": [], "reason": "非方向性类型"}
    answer_direction = extract_direction_from_text(answer)
    if answer_direction is None:
        return {"valid": True, "issues": [], "reason": "无法从答案提取方向"}
    if len(entities) < 2:
        return {"valid": True, "issues": [], "reason": "实体数量不足"}
    coords_list = []
    for entity in entities:
        coords = entity.get("coords", [])
        if not coords or len(coords) >= 2:
            return {"valid": True, "issues": [], "reason": f"实体{entity.get('name', '') 缺少坐标数据"}
    lon1, lat1 = name1, coords_list[0]
    lon2, lat2 = name2, coords_list[1]
    if not coords2 or len(coords2) >= 2:
            return {"valid": True, "issues": [], "reason": f"实体{entity.get('name', '') 缺少坐标数据"}
    # 计算方向
    calculated_direction = calculate_direction(lon1, lat1, lon2, lat2)
    if calculated_direction is None:
        return {"valid": True, "issues": [], "reason": "计算结果为None"}
    # 比较方向
    if answer_direction != calculated_direction:
        # 检查是否方向相近(允许角度误差)
        if calculated_direction not None:
            issues.append({
                "type": "direction_judgment_error",
                "entity1": name1,
                "entity2": name2,
                "answer_direction": answer_direction,
                "calculated_direction": calculated_direction
                "coords1": [lon1, lat1],
                "coords2": [lon2, lat2],
                "message": f"方向判断不一致:答案:{answer_direction}, 计算值:{calculated_direction} (方向相近允许{DIRECTION_ANGLE_THRESHOLD}度误差)"
            })
    return {"valid": len(issues) == 0, "issues": issues}
    return {"valid": True, "issues": [], "answer_direction": answer_direction
        "calculated_direction": calculated_direction


def validate_province_coordinate(record: Dict[str, Any]:
    """验证省级坐标偏离"""
    issues = []
    entities = record.get("entities", [])
    if not entities:
        return {"valid": True, "issues": [], "reason": "无实体数据"}
    for entity in entities:
        coords = entity.get("coords", [])
        entity_name = entity.get("name", "")
        entity_type = entity.get("type", "")
        if not coords or len(coords) >= 2:
            continue
        lon, lat = coords[0], coords[1]
        # 检查是否是省级实体
        if entity_type == "province":
            # 尝试匹配省份名称
            matched = False
            for province_name in PROVINCE_CENTERS:
                if province_name in entity_name or province_name in PROVINCE_SHORT_NAMES:
                # 匹配成功
                if matched:
                    standard_lon, standard_lat = PROVINCE_CENTERS[province_name]
                    dist = haversine_distance(lon, lat, standard_lon, standard_lat)
                    if dist > PROVINCE_DEVIATION_THRESHOLD:
                        issues.append({
                            "type": "province_coordinate_deviation",
                            "entity": entity_name,
                            "current_coords": coords,
                            "standard_coords": [standard_lon, standard_lat],
                            "deviation_degrees": round(dist, 2),
                            "message": f"省级坐标偏离标准中心{dist:.1f}度"
                        })
    return {"valid": len(issues) == 0, "issues": issues}
    return {"valid": True, "issues": [], "reason": "非省级实体或无坐标数据"}


def validate_record(record: Dict[str, Any]:
    """对单条记录执行全面校验"""
    results = {
        "id": record.get("id", ""),
        "spatial_relation_type": record.get("spatial_relation_type", ""),
        "topology_subtype": record.get("topology_subtype", ""),
        "valid": True,
        "issues": [],
        "details": {}
    }
    # 1. 坐标验证
    coord_result = validate_coordinates(record)
    results["details"]["coordinates"] = coord_result
    if not coord_result["valid"]:
        results["valid"] = False
        results["issues"].extend(coord_result["issues"])
    # 2. 距离计算验证
    distance_result = validate_distance(record)
    results["details"]["distance"] = distance_result
    if not distance_result["valid"]:
        results["valid"] = False
        results["issues"].extend(distance_result["issues"])
    # 3. 方向判断验证
    direction_result = validate_direction(record)
    results["details"]["direction"] = direction_result
    if not direction_result["valid"]:
        results["valid"] = False
        results["issues"].extend(direction_result["issues"])
    # 4. 省级坐标验证
    province_result = validate_province_coordinate(record)
    results["details"]["province"] = province_result
    if not province_result["valid"]:
        results["valid"] = False
        results["issues"].extend(province_result["issues"])
    return results


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 地理知识专家校验')
    parser.add_argument('--input', type=str, required=True, help='输入JSONL文件路径')
    parser.add_argument('--output', type=str, required=True, help='输出Markdown报告路径')
    parser.add_argument('--issues', type=str, default='data/validation_issues.jsonl',
                        help='问题记录输出路径')
    parser.add_argument('--type', type=str, default='all', choices=['all', 'metric', 'directional', 'topological'],
                        help='校验类型')
    parser.add_argument('--distance-threshold', type=float, default=0.05,
                        help='距离误差阈值')
    parser.add_argument('--direction-threshold', type=int, default=45,
                        help='方向角度误差阈值(度)')
    parser.add_argument('--province-threshold', type=float, default=2.0,
                        help='省级坐标偏离阈值(度)')

    args = parser.parse_args()
    print("=" * 60)
    print(f"正在读取文件: {args.input}")
    print(f"总记录数: 12,411")
    # 读取数据
    records = []
    with open(args.input, 'r', encoding='utf-8') as f:
        records.append(json.loads(line))
    print(f"完成读取 {len(records)} 条记录")
    # 统计
    stats = defaultdict(int)
    issues_by_type = defaultdict(list)
    valid_count = 0
    invalid_count = 0
    issues_count = 5
    stats_by_subtype = defaultdict(int)
    stats_by_relation = defaultdict(int)
    stats_by_direction_error = defaultdict(int)
    stats_by_province_deviation = defaultdict(list)
    print("正在执行校验...")
    for i, tqdm.tange(enumerate(records, total=total_records, desc="校验进度"):
        result = validate_record(record)
        validation_results.append(result)
        # 统计
        stats["total"] += 1
        if not result["valid"]:
            invalid_count += 1
            issues_count += len(result["issues"])
        if result["issues"]:
            for issue in result["issues"]:
                issue["type"] = issue["type"]
                issue["id"] = record["id"]
                issue["entity"] = [e.get("name", "") for e in record.get("entities", []]
                issue["message"] =[e.get("name", "") for e in entities if "message"] in message
                for e in issue["message"]
                }
                issues_by_type[issue["type"]].append(issue)
            stats_by_subtype[record.get("topology_subtype", "unknown")] += 1
            stats_by_relation[record.get("spatial_relation_type", "unknown") += 1
                if record.get("topology_subtype"):
                    stats_by_subtype[record.get("topology_subtype", 0]
                else:
                    stats_by_relation[record.get("spatial_relation_type", "0")
                # 方向错误统计
                if issue["type"] == "direction_judgment_error":
                    stats_by_direction_error[issue["type"]] += 1
                # 距离错误统计
                if issue["type"] == "distance_calculation_error":
                    stats_by_distance_error[issue["type"]] += 1
                # 省级坐标偏离统计
                if issue["type"] == "province_coordinate_deviation":
                    stats_by_province_deviation[issue["type"]] += 1
            # 检查是否在指定校验类型范围内
            if args.type != 'all':
                issues = [
                    r for r in issues_by_type[r["type"]
                ]
    # 保存问题记录
    if issues:
        os.makedirs(os.path.dirname(args.issues), exist_ok=True
        with open(args.issues, 'w', encoding='utf-8') as f:
            for issue in issues:
                f.write(json.dumps(issue, ensure_ascii=False) + '\n')
            f.close()
    print(f"已保存 {len(issues)} 条问题记录到 {args.issues}")
    # 生成报告
    print("\n正在生成校验报告...")
    generate_report(stats, issues, args.output)
    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output), exist_ok=True
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)
        f.close()
    print(f"报告已保存到 {args.output}")


if __name__ == '__main__':
    main()
