#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GeoKD-SR 地理知识专家校验脚本 V7 (修复版)
"""

import json
import re
import math
import os
import sys
import argparse
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

# ==================== 常量定义 ====================
# 中国边界范围
CHINA_BOUNDS = {"min_lon": 73.0, "max_lon": 135.0, "min_lat": 18.0, "max_lat": 53.0}
DISTANCE_ERROR_THRESHOLD = 0.05  # 5%
DIRECTION_ANGLE_THRESHOLD = 45  # 方向角度误差阈值(度)
PROVINCE_DEVIATION_THRESHOLD = 200  # 省级坐标偏离阈值(公里)

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

DIRECTION_NAMES = {
    "北": 0, "东北": 45, "东": 90, "东南": 135,
    "南": 180, "西南": 225, "西": 270, "西北": 315
}


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
        r'(\d+\.?\d*)\s*公里',
        r'约(\d+\.?\d*)\s*km',
        r'距离为(\d+\.?\d*)\s*千米',
        r'约(\d+\.?\d*)km',
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


def validate_coordinates(record: Dict[str, Any]) -> Dict[str, Any]:
    """验证坐标范围"""
    issues = []
    entities = record.get("entities", [])
    if not entities:
        return {"valid": True, "issues": [], "reason": "无实体数据"}

    for entity in entities:
        coords = entity.get("coords", [])
        entity_name = entity.get("name", "")
        entity_type = entity.get("type", "")

        if not coords or len(coords) < 2:
            issues.append({
                "type": "missing_coordinates",
                "entity": entity_name,
                "entity_type": entity_type,
                "message": f"实体 {entity_name} ({entity_type}) 缺少坐标数据"
            })
            continue

        lon, lat = coords[0], coords[1]
        # 检查是否超出中国范围
        if not (CHINA_BOUNDS["min_lon"] <= lon <= CHINA_BOUNDS["max_lon"] and
                CHINA_BOUNDS["min_lat"] <= lat <= CHINA_BOUNDS["max_lat"]):
            issues.append({
                "type": "coordinate_out_of_range",
                "entity": entity_name,
                "coords": coords,
                "message": f"实体 {entity_name} 坐标{coords} 超出中国范围"
            })

    return {"valid": len(issues) == 0, "issues": issues}


def validate_distance(record: Dict[str, Any]) -> Dict[str, Any]:
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

    # 获取前两个实体的坐标
    coords_list = []
    names = []
    for entity in entities:
        coords = entity.get("coords", [])
        name = entity.get("name", "")
        if coords and len(coords) >= 2:
            coords_list.append(coords)
            names.append(name)

    if len(coords_list) < 2:
        return {"valid": True, "issues": [], "reason": "实体缺少坐标数据"}

    lon1, lat1 = coords_list[0][0], coords_list[0][1]
    lon2, lat2 = coords_list[1][0], coords_list[1][1]
    name1, name2 = names[0], names[1]

    # 计算距离
    calculated_distance = haversine_distance(lon1, lat1, lon2, lat2)

    if calculated_distance <= 0:
        return {"valid": True, "issues": [], "reason": "距离计算结果异常"}

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

    return {"valid": len(issues) == 0, "issues": issues,
            "answer_distance": answer_distance, "calculated_distance": calculated_distance}


def validate_direction(record: Dict[str, Any]) -> Dict[str, Any]:
    """验证方向判断准确性"""
    issues = []
    spatial_type = record.get("spatial_relation_type", "")
    answer = record.get("answer", "")
    entities = record.get("entities", [])

    if spatial_type != "directional":
        return {"valid": True, "issues": [], "reason": "非directional类型"}

    answer_direction = extract_direction_from_text(answer)
    if answer_direction is None:
        return {"valid": True, "issues": [], "reason": "无法从答案提取方向"}

    if len(entities) < 2:
        return {"valid": True, "issues": [], "reason": "实体数量不足"}

    # 获取前两个实体的坐标
    coords_list = []
    names = []
    for entity in entities:
        coords = entity.get("coords", [])
        name = entity.get("name", "")
        if coords and len(coords) >= 2:
            coords_list.append(coords)
            names.append(name)

    if len(coords_list) < 2:
        return {"valid": True, "issues": [], "reason": "实体缺少坐标数据"}

    lon1, lat1 = coords_list[0][0], coords_list[0][1]
    lon2, lat2 = coords_list[1][0], coords_list[1][1]
    name1, name2 = names[0], names[1]

    # 计算方向
    calculated_direction = calculate_direction(lon1, lat1, lon2, lat2)

    # 比较方向
    if answer_direction != calculated_direction:
        issues.append({
            "type": "direction_judgment_error",
            "entity1": name1,
            "entity2": name2,
            "answer_direction": answer_direction,
            "calculated_direction": calculated_direction,
            "coords1": [lon1, lat1],
            "coords2": [lon2, lat2],
            "message": f"方向判断不一致:答案:{answer_direction}, 计算值:{calculated_direction}"
        })

    return {"valid": len(issues) == 0, "issues": issues,
            "answer_direction": answer_direction, "calculated_direction": calculated_direction}


def validate_province_coordinate(record: Dict[str, Any]) -> Dict[str, Any]:
    """验证省级坐标偏离"""
    issues = []
    entities = record.get("entities", [])

    if not entities:
        return {"valid": True, "issues": [], "reason": "无实体数据"}

    for entity in entities:
        coords = entity.get("coords", [])
        entity_name = entity.get("name", "")
        entity_type = entity.get("type", "")

        if not coords or len(coords) < 2:
            continue

        # 检查是否是省级实体
        if entity_type != "province":
            continue

        lon, lat = coords[0], coords[1]

        # 尝试匹配省份名称
        matched_province = None
        for province_name in PROVINCE_CENTERS:
            if province_name in entity_name:
                matched_province = province_name
                break

        # 也检查简称
        if not matched_province:
            for short_name, full_name in PROVINCE_SHORT_NAMES.items():
                if short_name in entity_name:
                    matched_province = full_name
                    break

        if matched_province:
            standard_lon, standard_lat = PROVINCE_CENTERS[matched_province]
            dist = haversine_distance(lon, lat, standard_lon, standard_lat)
            if dist > PROVINCE_DEVIATION_THRESHOLD:
                issues.append({
                    "type": "province_coordinate_deviation",
                    "entity": entity_name,
                    "current_coords": coords,
                    "standard_coords": [standard_lon, standard_lat],
                    "deviation_km": round(dist, 1),
                    "message": f"省级坐标偏离标准中心{dist:.1f}公里"
                })

    return {"valid": len(issues) == 0, "issues": issues}


def validate_record(record: Dict[str, Any]) -> Dict[str, Any]:
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


def generate_report(stats: Dict, issues_by_type: Dict, output_path: str):
    """生成校验报告"""
    report_lines = []
    report_lines.append("# GeoKD-SR 地理知识专家校验报告")
    report_lines.append("")
    report_lines.append(f"> 校验时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"> 数据文件: final_1_v5.jsonl")
    report_lines.append("")

    # 1. 校验概览
    report_lines.append("## 1. 校验概览")
    report_lines.append("")
    report_lines.append(f"| 指标 | 数值 |")
    report_lines.append(f"|------|------|")
    report_lines.append(f"| 总记录数 | {stats['total']} |")
    report_lines.append(f"| 校验通过 | {stats['valid']} |")
    report_lines.append(f"| 校验失败 | {stats['invalid']} |")
    report_lines.append(f"| 通过率 | {stats['valid']/max(stats['total'],1)*100:.2f}% |")
    report_lines.append(f"| 问题总数 | {stats['total_issues']} |")
    report_lines.append("")

    # 2. 问题分类统计
    report_lines.append("## 2. 问题分类统计")
    report_lines.append("")
    report_lines.append("| 问题类型 | 数量 |")
    report_lines.append("|----------|------|")
    for issue_type, issue_list in sorted(issues_by_type.items(), key=lambda x: -len(x[1])):
        report_lines.append(f"| {issue_type} | {len(issue_list)} |")
    report_lines.append("")

    # 3. 按空间关系类型统计
    report_lines.append("## 3. 按空间关系类型统计")
    report_lines.append("")
    report_lines.append("| 空间关系类型 | 有效 | 无效 |")
    report_lines.append("|--------------|------|------|")
    for rel_type, counts in stats.get('by_relation', {}).items():
        report_lines.append(f"| {rel_type} | {counts.get('valid', 0)} | {counts.get('invalid', 0)} |")
    report_lines.append("")

    # 4. 问题详情
    report_lines.append("## 4. 问题详情 (前100条)")
    report_lines.append("")

    all_issues = []
    for issue_type, issue_list in issues_by_type.items():
        for issue in issue_list:
            issue['_type'] = issue_type
            all_issues.append(issue)

    # 按类型排序
    all_issues = sorted(all_issues, key=lambda x: x.get('_type', ''))

    for i, issue in enumerate(all_issues[:100]):
        report_lines.append(f"### {i+1}. {issue.get('_type', 'unknown')}")
        report_lines.append(f"- **记录ID**: {issue.get('id', 'N/A')}")
        report_lines.append(f"- **实体**: {issue.get('entity', issue.get('entity1', 'N/A'))}")
        if 'entity2' in issue:
            report_lines.append(f"- **相关实体**: {issue.get('entity2', 'N/A')}")
        report_lines.append(f"- **问题描述**: {issue.get('message', 'N/A')}")
        if 'error_percent' in issue:
            report_lines.append(f"- **误差百分比**: {issue.get('error_percent')}%")
        if 'answer_distance' in issue:
            report_lines.append(f"- **答案距离**: {issue.get('answer_distance')} km")
        if 'calculated_distance' in issue:
            report_lines.append(f"- **计算距离**: {issue.get('calculated_distance')} km")
        if 'answer_direction' in issue:
            report_lines.append(f"- **答案方向**: {issue.get('answer_direction')}")
        if 'calculated_direction' in issue:
            report_lines.append(f"- **计算方向**: {issue.get('calculated_direction')}")
        report_lines.append("")

    if len(all_issues) > 100:
        report_lines.append(f"> 注: 共 {len(all_issues)} 条问题，仅显示前100条")

    # 5. 修复建议
    report_lines.append("## 5. 修复建议")
    report_lines.append("")

    if issues_by_type.get('distance_calculation_error'):
        report_lines.append("### 距离计算问题修复")
        report_lines.append("- 使用Haversine公式重新计算距离")
        report_lines.append("- 检查坐标数据来源的准确性")
        report_lines.append("")

    if issues_by_type.get('direction_judgment_error'):
        report_lines.append("### 方向判断问题修复")
        report_lines.append("- 使用8方位计算公式重新计算方向")
        report_lines.append("- 检查方向描述是否与计算结果一致")
        report_lines.append("")

    if issues_by_type.get('province_coordinate_deviation'):
        report_lines.append("### 省级坐标偏离修复")
        report_lines.append("- 使用标准省级中心坐标")
        report_lines.append("- 检查坐标数据是否正确")
        report_lines.append("")

    if issues_by_type.get('missing_coordinates'):
        report_lines.append("### 缺少坐标修复")
        report_lines.append("- 补充实体的经纬度坐标")
        report_lines.append("")

    if issues_by_type.get('coordinate_out_of_range'):
        report_lines.append("### 坐标超出范围修复")
        report_lines.append("- 检查坐标是否在中国境内")
        report_lines.append("- 修正错误的坐标数据")
        report_lines.append("")

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    return '\n'.join(report_lines)


def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 地理知识专家校验')
    parser.add_argument('--input', type=str, required=True, help='输入JSONL文件路径')
    parser.add_argument('--output', type=str, required=True, help='输出Markdown报告路径')
    parser.add_argument('--issues', type=str, default='data/validation_issues.jsonl',
                        help='问题记录输出路径')
    parser.add_argument('--type', type=str, default='all',
                        choices=['all', 'metric', 'directional', 'topological'],
                        help='校验类型')
    parser.add_argument('--distance-threshold', type=float, default=0.05,
                        help='距离误差阈值')
    parser.add_argument('--direction-threshold', type=int, default=45,
                        help='方向角度误差阈值(度)')
    parser.add_argument('--province-threshold', type=float, default=200,
                        help='省级坐标偏离阈值(公里)')

    args = parser.parse_args()

    global DISTANCE_ERROR_THRESHOLD, DIRECTION_ANGLE_THRESHOLD, PROVINCE_DEVIATION_THRESHOLD
    DISTANCE_ERROR_THRESHOLD = args.distance_threshold
    DIRECTION_ANGLE_THRESHOLD = args.direction_threshold
    PROVINCE_DEVIATION_THRESHOLD = args.province_threshold

    print("=" * 60)
    print("GeoKD-SR 地理知识专家校验")
    print("=" * 60)
    print(f"输入文件: {args.input}")
    print(f"输出报告: {args.output}")
    print(f"问题记录: {args.issues}")
    print(f"校验类型: {args.type}")
    print(f"距离误差阈值: {args.distance_threshold*100}%")
    print(f"方向角度阈值: {args.direction_threshold}度")
    print(f"省级偏离阈值: {args.province_threshold}公里")
    print("=" * 60)

    # 检查输入文件
    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        sys.exit(1)

    # 读取数据
    print("正在读取数据...")
    records = []
    with open(args.input, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError as e:
                    print(f"警告: 跳过无效JSON行: {e}")

    total_records = len(records)
    print(f"共读取 {total_records} 条记录")

    # 统计
    stats = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "total_issues": 0,
        "by_relation": defaultdict(lambda: {"valid": 0, "invalid": 0}),
        "by_subtype": defaultdict(lambda: {"valid": 0, "invalid": 0})
    }
    issues_by_type = defaultdict(list)
    all_issues = []

    print("正在执行校验...")
    for i, record in enumerate(records):
        if (i + 1) % 1000 == 0:
            print(f"进度: {i+1}/{total_records} ({(i+1)/total_records*100:.1f}%)")

        result = validate_record(record)

        # 更新统计
        stats["total"] += 1
        rel_type = record.get("spatial_relation_type", "unknown")
        sub_type = record.get("topology_subtype", "unknown")

        if result["valid"]:
            stats["valid"] += 1
            stats["by_relation"][rel_type]["valid"] += 1
            stats["by_subtype"][sub_type]["valid"] += 1
        else:
            stats["invalid"] += 1
            stats["by_relation"][rel_type]["invalid"] += 1
            stats["by_subtype"][sub_type]["invalid"] += 1
            stats["total_issues"] += len(result["issues"])

            # 收集问题
            for issue in result["issues"]:
                issue["id"] = record.get("id", "")
                issue["spatial_relation_type"] = rel_type
                issue["topology_subtype"] = sub_type
                issues_by_type[issue["type"]].append(issue)
                all_issues.append(issue)

    print(f"校验完成: {stats['valid']}/{stats['total']} 通过")

    # 保存问题记录
    if all_issues:
        issues_dir = os.path.dirname(args.issues)
        if issues_dir:
            os.makedirs(issues_dir, exist_ok=True)
        with open(args.issues, 'w', encoding='utf-8') as f:
            for issue in all_issues:
                f.write(json.dumps(issue, ensure_ascii=False) + '\n')
        print(f"已保存 {len(all_issues)} 条问题记录到 {args.issues}")
    else:
        print("没有发现问题记录")

    # 生成报告
    print("正在生成校验报告...")
    generate_report(stats, issues_by_type, args.output)
    print(f"报告已保存到 {args.output}")

    # 打印摘要
    print("=" * 60)
    print("校验摘要:")
    print(f"  - 总记录数: {stats['total']}")
    print(f"  - 通过: {stats['valid']}")
    print(f"  - 失败: {stats['invalid']}")
    print(f"  - 通过率: {stats['valid']/max(stats['total'],1)*100:.2f}%")
    print(f"  - 问题总数: {stats['total_issues']}")
    print("=" * 60)


if __name__ == '__main__':
    main()
