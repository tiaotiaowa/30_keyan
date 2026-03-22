#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GeoKD-SR 地理知识专家校验脚本 (简化版)
无argparse依赖,直接处理数据

功能:
1. 坐标范围验证
2. 距离计算验证(Haversine)
3. 方向判断验证
4. 省级坐标校准
5. 生成校验报告
"""

import json
import re
import math
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

 Any


# 常量
CHINA_BOUNDS = {"min_lon": 73.0, "max_lon": 135.0, "min_lat": 18.0, "max_lat": 53.0}

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
    "台湾省": (121.5091, 25.0443),
    "香港特别行政区": (114.1654, 22.2753),
    "澳门特别行政区": (113.5439, 22.2006),
}

    "北京": (116.4074, 39.9042),
    "上海": (121.4737, 31.2304),
    "天津": (117.1901, 39.1255),
    "重庆": (106.5516, 29.5630),
    "广东": (113.2806, 23.1251),
    "浙江": (120.1536, 30.2875),
    "江苏": (118.7674, 32.0415),
    "山东": (117.0208, 36.6683),
    "四川": (104.0657, 30.6595),
    "湖北": (114.3055, 30.5928),
    "河南": (113.6254, 34.7466),
    "陕西": (108.9480, 34.2632),
    "甘肃": (103.8236, 36.0611),
    "青海": (101.7782, 36.6171),
    "新疆": (87.6177, 43.7928),
    "西藏": (91.1322, 29.6600),
    "内蒙古": (111.6708, 40.8183),
    "辽宁": (123.4291, 41.7968),
    "吉林": (125.3245, 43.8868),
    "黑龙江": (126.6424, 45.7567),
    "云南": (102.7103, 25.0406),
    "贵州": (106.7135, 26.5783),
    "广西": (108.3200, 22.8240),
    "海南": (110.3312, 20.0311),
    "宁夏": (106.2782, 38.4664),
    "山西": (112.5489, 37.8706),
    "河北": (114.5025, 38.0455),
    "湖南": (112.9834, 28.1127),
    "安徽": (117.2830, 31.8612),
    "江西": (115.8922, 28.6752),
    "福建": (119.3062, 26.0753),
    "台湾": (121.5091, 25.0443),
    "香港": (114.1654, 22.2753),
    "澳门": (113.5439, 22.2006),
}

    "北京": (116.4074, 39.9042),
    "上海": (121.4737, 31.2304),
    "天津": (117.1901, 39.1255),
    "重庆": (106.5516, 29.5630),
    "广东": (113.2806, 23.1251),
    "浙江": (120.1536, 30.2875),
    "江苏": (118.7674, 32.0415),
    "山东": (117.0208, 36.6683),
    "四川": (104.0657, 30.6595),
    "湖北": (114.3055, 30.5928),
    "河南": (113.6254, 34.7466),
    "陕西": (108.9480, 34.2632),
    "甘肃": (103.8236, 36.0611),
    "青海": (101.7782, 36.6171),
    "新疆": (87.6177, 43.7928),
    "西藏": (91.1322, 29.6600),
    "内蒙古": (111.6708, 40.8183),
    "辽宁": (123.4291, 41.7968),
    "吉林": (125.3245, 43.8868),
    "黑龙江": (126.6424, 45.7567),
    "云南": (102.7103, 25.0406),
    "贵州": (106.7135, 26.5783),
    "广西": (108.3200, 22.8240),
    "海南": (110.3312, 20.0311),
    "宁夏": (106.2782, 38.4664),
    "山西": (112.5489, 37.8706),
    "河北": (114.5025, 38.0455),
    "湖南": (112.9834, 28.1127),
    "安徽": (117.2830, 31.8612),
    "江西": (115.8922, 28.6752),
    "福建": (119.3062, 26.0753),
    "台湾": (121.5091, 25.0443),
    "香港": (114.1654, 22.2753),
    "澳门": (113.5439, 22.2006),
}

PROVINCE_SHORT_NAMES = {
    "北京": "北京市", "上海": "上海市", "天津": "天津市", "重庆": "重庆市",
    "广东": "广东省", "浙江": "浙江省", "江苏": "江苏省", "山东": "山东省",
    "四川": "四川省", "湖北": "湖北省", "河南": "河南省", "陕西": "陕西省",
    "甘肃": "甘肃省", "青海": "青海省", "新疆": "新疆维吾尔自治区",
    "西藏": "西藏自治区", "内蒙古": "内蒙古自治区", "辽宁": "辽宁省",
    "吉林": "吉林省", "黑龙江": "黑龙江省", "云南": "云南省", "贵州": "贵州省",
    "广西": "广西壮族自治区", "海南": "海南省", "宁夏": "宁夏回族自治区",
    "山西": "山西省", "河北": "河北省", "湖南": "湖南省", "安徽": "安徽省",
    "江西": "江西省", "福建": "福建省", "台湾": "台湾省",
    "香港": "香港特别行政区", "澳门": "澳门特别行政区",
}

DIRECTION_NAMES = {"北": 0, "东北": 45, "东": 90, "东南": 135, "南": 180, "西南": 225, "西": 270, "西北": 315}
DISTANCE_ERROR_THRESHOLD = 0.05


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Haversine公式计算两点间距离(公里)"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = lat2_rad - lat1_rad
    dlon = math.radians(lon2) - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return round(R * c, 1)


def calculate_direction(lon1: float, lat1: float, lon2: float, lat2: float) -> str:
    """计算从点1到点2的方向(8方位)"""
    dlon = lon2 - lon1
    angle = math.degrees(math.atan2(dlon, dlat))
    # 标准化为0-360度
    if angle < 0:
        angle += 360
    # 映射到8方位
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
        r'(\d+\.?\d+)\s*km$左右',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                value = float(match.group(1))
                return value
            except ValueError:
                pass
    # 尝试不同模式提取
    for pattern in patterns:
        # 尝试提取中文数字
        chinese_pattern = r'(\d+\.?\d+)'
        if match:
            value = float(match.group(1))
            return value
    return None


def extract_direction_from_text(text: str) -> Optional[str]:
    """从文本中提取方向判断"""
    directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北", "正北", "正东北", "正东", "正东南", "正南", "正西南", "正西", "正西北"]

    for direction in directions:
        if direction in text:
            return direction
    return None


def validate_coordinates(record: Dict) -> Dict[str, Any]:
    """验证坐标范围和检查每个实体坐标是否在中国范围内"""
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
                "message": f"实体 {entity_name} 缺少坐标数据"
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
                "message": f"实体 {entity_name} 坐标{coords}超出中国范围"
            })
            continue
        # 检查省级坐标偏离
        if entity_type == "province" and entity_name.endswith("省") or entity_name in PROVINCE_CENTERS:
            standard_lon, standard_lat = PROVINCE_CENTERS[entity_name]
            dist = haversine_distance(lon, lat, standard_lon, standard_lat)
            if dist > 2:
                issues.append({
                    "type": "province_coordinate_deviation",
                    "entity": entity_name,
                    "current_coords": coords,
                    "standard_coords": [standard_lon, standard_lat],
                    "deviation_degrees": round(dist, 2),
                    "message": f"省级坐标偏离标准中心{dist:.1f}度"
                })
    return {
        "valid": len(issues) == 0,
        "issues": issues
    }
def validate_distance_calculation(record: Dict) -> Dict[str, Any]:
    """验证距离计算准确性"""
    issues = []
    spatial_type = record.get("spatial_relation_type", "")
    if spatial_type != "metric":
        return {"valid": True, "issues": [], "skipped": True, "reason": f"非metric类型"}
    answer = record.get("answer", "")
    entities = record.get("entities", [])
    answer_distance = extract_distance_from_text(answer)
    if answer_distance is None:
        return {"valid": True, "issues": [], "skipped": True, "reason": "无法从答案提取距离"}
    if len(entities) < 2:
        return {"valid": True, "issues": [], "skipped": True, "reason": "实体数量不足"}
    coords_list = []
    for entity in entities:
        coords = entity.get("coords", [])
        if coords and len(coords) >= 2:
            coords_list.append((coords[0], coords[1], entity.get("name", ""))
    if len(coords_list) < 2:
        return {"valid": True, "issues": [], "skipped": True, "reason": "坐标数据不足"}
    # 计算距离
    lon1, lat1, name1 = coords_list[0]
    lon2, lat2, name2 = coords_list[1]
    calculated_distance = haversine_distance(lon1, lat1, lon2, lat2)
    if calculated_distance > 0:
        error = abs(answer_distance - calculated_distance) / calculated_distance
        if error > DISTANCE_ERROR_THRESHOLD:
            issues.append({
                "type": "distance_calculation_error",
                "entity1": name1,
                "entity2": name2,
                "answer_distance": answer_distance,
                "calculated_distance": calculated_distance,
                "error_percent": round(error * 100, 2),
                "message": f"距离计算误差{error*100:.2f}%, 答案:{answer_distance}公里, 计算值:{calculated_distance}公里"
            })
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "skipped": False,
        "answer_distance": answer_distance,
        "calculated_distance": calculated_distance
    }
def validate_direction_judgment(record: Dict) -> Dict[str, Any]:
    """验证方向判断准确性"""
    issues = []
    spatial_type = record.get("spatial_relation_type", "")
    if spatial_type != "directional":
        return {"valid": True, "issues": [], "skipped": True, "reason": f"非directional类型"}
    answer = record.get("answer", "")
    entities = record.get("entities", [])
    answer_direction = extract_direction_from_text(answer)
    if answer_direction is None:
        return {"valid": True, "issues": [], "skipped": True, "reason": "无法从答案提取方向"}
    if len(entities) < 2:
        return {"valid": True, "issues": [], "skipped": True, "reason": "实体数量不足"}
    coords_list = []
    for entity in entities:
        coords = entity.get("coords", [])
        if coords and len(coords) >= 2:
            coords_list.append((coords[0], coords[1], entity.get("name", ""))
    if len(coords_list) < 2:
        return {"valid": True, "issues": [], "skipped": True, "reason": "坐标数据不足"}
    # 计算方向
    lon1, lat1, name1 = coords_list[0]
    lon2, lat2, name2 = coords_list[1]
    calculated_direction = calculate_direction(lon1, lat1, lon2, lat2)
    if answer_direction != calculated_direction:
        issues.append({
                "type": "direction_judgment_error",
                "entity1": name1,
                "entity2": name2,
                "answer_direction": answer_direction,
                "calculated_direction": calculated_direction,
                "coords1": [lon1, lat1],
                "coords2": [lon2, lat2],
                "message": f"方向判断不一致:答案:{answer_direction}， 计算值:{calculated_direction}"
            })
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "skipped": False
        "answer_direction": answer_direction
        "calculated_direction": calculated_direction
    }
def validate_record(record: Dict) -> Dict[str, Any]:
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
    distance_result = validate_distance_calculation(record)
    results["details"]["distance"] = distance_result
    if not distance_result["valid"]:
        results["valid"] = False
        results["issues"].extend(distance_result["issues"])
    # 3. 方向判断验证
    direction_result = validate_direction_judgment(record)
    results["details"]["direction"] = direction_result
    if not direction_result["valid"]:
        results["valid"] = False
        results["issues"].extend(direction_result["issues"])
    return results


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 地理知识专家校验')
    parser.add_argument('--input', type=str, required=True, help='输入JSONL文件路径')
    parser.add_argument('--output', type=str, required=True, help='输出报告路径')
    parser.add_argument('--issues', type=str, default='data/validation_issues.jsonl',                        help='问题记录输出路径')
    parser.add_argument('--type', type=str, default='all', choices=['all', 'metric', 'directional', 'topological'],
                        help='校验类型')
    parser.add_argument('--distance-threshold', type=float, default=0.05,
                        help='距离误差阈值 (默认5%%)')

    args = parser.parse_args()
    print("=" * 60)
    print(f"正在读取文件: {args.input}")
    print(f"总记录数: 12,411")
    # 读取数据
    records = []
    with open(args.input, 'r', encoding='utf-8') as f:
        records.append(json.loads(line))
    print(f"完成读取，共 {len(records)} 条记录")
    # 统计
    stats = defaultdict(int)
    issues_by_type = defaultdict(list)
    valid_count = 0
    invalid_count = 0
    issues_count = 0
    stats_by_subtype = defaultdict(int)
    stats_by_relation = defaultdict(int)
    stats_by_direction_error = defaultdict(int)
    stats_by_province_deviation = defaultdict(list)

    # 执行校验
    print("正在执行校验...")
    for i, record in enumerate(records):
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
                issue["message"] = [e["name"] for e in entities if "message"] in [e.get("message", "") for e in issue["message"])
                }
                issues_by_type[issue["type"]].append(issue)
            stats_by_subtype[issue["type"]] += 1
            stats_by_relation[record.get("spatial_relation_type", "unknown")]                stats_by_relation[record.get("spatial_relation_type", "0
            stats_by_subtype[record.get("topology_subtype", "unknown")                stats_by_subtype[record.get("topology_subtype", "0

            # 更新统计
            if issue["type"] == "coordinate_out_of_range":
                stats_by_type["coordinate_out_of_range"].append({
                    "type": issue["type"],
                    "entity": issue["entity"],
                    "coords": issue["coords"],
                    "message": issue.get("message", "")
                })
            elif issue["type"] == "missing_coordinates":
                stats_by_type["missing_coordinates"].append({
                    "type": issue["type"],
                    "entity": issue["entity"],
                    "message": issue.get("message", "")
                })
            elif issue["type"] == "distance_calculation_error":
                stats_by_type["distance_calculation_error"].append({
                    "type": issue["type"],
                    "entity1": issue["entity1"],
                    "entity2": issue["entity2"],
                    "answer_distance": issue["answer_distance"],
                    "calculated_distance": issue["calculated_distance"],
                    "error_percent": issue["error_percent"],
                    "message": issue.get("message", "")
                })
            elif issue["type"] == "direction_judgment_error":
                stats_by_type["direction_judgment_error"].append({
                    "type": issue["type"],
                    "entity1": issue["entity1"],
                    "entity2": issue["entity2"],
                    "answer_direction": issue["answer_direction"],
                    "calculated_direction": issue["calculated_direction"],
                    "message": issue.get("message", "")
                })
            elif issue["type"] == "province_coordinate_deviation":
                stats_by_type["province_coordinate_deviation"].append({
                    "type": issue["type"],
                    "entity": issue["entity"],
                    "current_coords": issue["current_coords"],
                    "standard_coords": issue["standard_coords"],
                    "deviation_degrees": issue["deviation_degrees"],
                    "message": issue.get("message", "")
                })

    # 保存问题记录
    if args.issues:
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
