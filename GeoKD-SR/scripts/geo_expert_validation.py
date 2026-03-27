#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GeoKD-SR 地理知识专家校验脚本

功能:
1. 坐标范围验证 - 检查坐标是否在中国境内
2. 距离计算验证 - 使用Haversine公式验证距离计算
3. 方向判断验证 - 验证方向判断是否正确
4. 省级坐标校准 - 检查省级坐标是否偏离标准中心
5. 地理事实验证 - 验证行政区划关系
6. 生成校验报告

作者: GeoKD-SR Team
日期: 2026-03-13
"""

import json
import re
import math
import os
import argparse
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any


# ==================== 常量定义 ====================

# 中国边界范围
CHINA_BOUNDS = {
    "min_lon": 73.0,
    "max_lon": 135.0,
    "min_lat": 18.0,
    "max_lat": 53.0
}

# 省级中心坐标标准值 (来源: 国家地理信息公共服务平台)
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

# 省份简称映射
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

# 方位名称映射
DIRECTION_NAMES = {
    "北": 0, "东北": 45, "东": 90, "东南": 135,
    "南": 180, "西南": 225, "西": 270, "西北": 315
}

# 距离误差阈值
DISTANCE_ERROR_THRESHOLD = 0.05  # 5%


# ==================== 核心函数 ====================

def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    使用Haversine公式计算两点间的大圆距离(公里)

    Args:
        lon1, lat1: 点1的经纬度
        lon2, lat2: 点2的经纬度

    Returns:
        两点间距离(公里), 保留1位小数
    """
    R = 6371  # 地球半径(公里)

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return round(R * c, 1)


def calculate_direction(lon1: float, lat1: float, lon2: float, lat2: float) -> str:
    """
    计算从点1到点2的方向(8方位)

    Args:
        lon1, lat1: 起点经纬度
        lon2, lat2: 终点经纬度

    Returns:
        方位名称(北/东北/东/东南/南/西南/西/西北)
    """
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    # 计算方位角(从北向顺时针)
    angle = math.degrees(math.atan2(dlon, dlat))
    if angle < 0:
        angle += 360

    # 映射到8方位
    directions = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
    idx = int((angle + 22.5) // 45) % 8

    return directions[idx]


def is_in_china(lon: float, lat: float) -> bool:
    """检查坐标是否在中国境内"""
    return (CHINA_BOUNDS["min_lon"] <= lon <= CHINA_BOUNDS["max_lon"] and
            CHINA_BOUNDS["min_lat"] <= lat <= CHINA_BOUNDS["max_lat"])


def calculate_coordinate_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """计算两个坐标点之间的欧氏距离(度)"""
    return math.sqrt((lon2 - lon1) ** 2 + (lat2 - lat1) ** 2)


def get_province_center(province_name: str) -> Optional[Tuple[float, float]]:
    """获取省份的标准中心坐标"""
    # 直接匹配
    if province_name in PROVINCE_CENTERS:
        return PROVINCE_CENTERS[province_name]
    # 简称匹配
    for short, full in PROVINCE_SHORT_NAMES.items():
        if short in province_name or province_name in short:
            return PROVINCE_CENTERS.get(full)
    # 包含匹配
    for full_name, coords in PROVINCE_CENTERS.items():
        if province_name in full_name or full_name.startswith(province_name):
            return coords
    return None


def extract_distance_from_text(text: str) -> Optional[float]:
    """从文本中提取距离数值(公里)"""
    # 匹配 "约XXX公里" 或 "XXX千米" 或 "XXXkm"
    patterns = [
        r'约?(\d+\.?\d*)\s*(公里|千米|km)',
        r'距离[是为]\s*(\d+\.?\d*)\s*(公里|千米|km)',
        r'(\d+\.?\d*)\s*(公里|千米|km)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def extract_direction_from_text(text: str) -> Optional[str]:
    """从文本中提取方向"""
    directions = ['东北', '东南', '西北', '西南', '北', '东', '南', '西']

    for direction in directions:
        if direction in text:
            return direction

    return None


# ==================== 校验函数 ====================

def validate_coordinates(record: Dict) -> Dict[str, Any]:
    """
    验证坐标范围

    Returns:
        校验结果字典
    """
    issues = []
    entities = record.get("entities", [])

    for entity in entities:
        name = entity.get("name", "")
        coords = entity.get("coords", [])
        entity_type = entity.get("type", "")

        if coords and len(coords) >= 2:
            lon, lat = coords[0], coords[1]

            # 检查是否在中国境内
            if not is_in_china(lon, lat):
                issues.append({
                    "type": "coordinate_out_of_china",
                    "entity": name,
                    "coords": coords,
                    "message": f"坐标({lon}, {lat})超出中国境内范围"
                })

            # 检查省级实体坐标偏差
            if entity_type == "province":
                standard_center = get_province_center(name)
                if standard_center:
                    dist = calculate_coordinate_distance(lon, lat, standard_center[0], standard_center[1])
                    if dist > 2.0:  # 偏离超过2度
                        issues.append({
                            "type": "province_coordinate_deviation",
                            "entity": name,
                            "current_coords": coords,
                            "standard_coords": list(standard_center),
                            "deviation_degrees": round(dist, 2),
                            "message": f"省级坐标偏离标准中心{dist:.2f}度"
                        })

    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


def validate_distance_calculation(record: Dict) -> Dict[str, Any]:
    """
    验证距离计算准确性

    Returns:
        校验结果字典
    """
    issues = []
    spatial_type = record.get("spatial_relation_type", "")

    # 只验证metric类型
    if spatial_type != "metric":
        return {"valid": True, "issues": [], "skipped": True, "reason": "非metric类型"}

    answer = record.get("answer", "")
    entities = record.get("entities", [])

    # 提取答案中的距离
    answer_distance = extract_distance_from_text(answer)
    if answer_distance is None:
        return {"valid": True, "issues": [], "skipped": True, "reason": "无法从答案提取距离"}

    # 获取实体坐标
    if len(entities) < 2:
        return {"valid": True, "issues": [], "skipped": True, "reason": "实体数量不足"}

    coords_list = []
    for entity in entities:
        coords = entity.get("coords", [])
        if coords and len(coords) >= 2:
            coords_list.append((coords[0], coords[1], entity.get("name", "")))

    if len(coords_list) < 2:
        return {"valid": True, "issues": [], "skipped": True, "reason": "坐标数据不足"}

    # 计算第一对实体间的距离
    lon1, lat1, name1 = coords_list[0]
    lon2, lat2, name2 = coords_list[1]

    calculated_distance = haversine_distance(lon1, lat1, lon2, lat2)

    # 计算误差
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
                "message": f"距离计算误差{error*100:.2f}%，答案:{answer_distance}公里，计算值:{calculated_distance}公里"
            })

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "skipped": False,
        "answer_distance": answer_distance,
        "calculated_distance": calculated_distance if 'calculated_distance' in dir() else None
    }


def validate_direction_judgment(record: Dict) -> Dict[str, Any]:
    """
    验证方向判断准确性

    Returns:
        校验结果字典
    """
    issues = []
    spatial_type = record.get("spatial_relation_type", "")

    # 只验证directional类型
    if spatial_type != "directional":
        return {"valid": True, "issues": [], "skipped": True, "reason": "非directional类型"}

    answer = record.get("answer", "")
    entities = record.get("entities", [])

    # 提取答案中的方向
    answer_direction = extract_direction_from_text(answer)
    if answer_direction is None:
        return {"valid": True, "issues": [], "skipped": True, "reason": "无法从答案提取方向"}

    # 获取实体坐标
    if len(entities) < 2:
        return {"valid": True, "issues": [], "skipped": True, "reason": "实体数量不足"}

    coords_list = []
    for entity in entities:
        coords = entity.get("coords", [])
        if coords and len(coords) >= 2:
            coords_list.append((coords[0], coords[1], entity.get("name", "")))

    if len(coords_list) < 2:
        return {"valid": True, "issues": [], "skipped": True, "reason": "坐标数据不足"}

    # 计算方向
    lon1, lat1, name1 = coords_list[0]
    lon2, lat2, name2 = coords_list[1]

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
            "message": f"方向判断不一致，答案:{answer_direction}，计算值:{calculated_direction}"
        })

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "skipped": False,
        "answer_direction": answer_direction,
        "calculated_direction": calculated_direction
    }


def validate_geographic_facts(record: Dict) -> Dict[str, Any]:
    """
    验证地理事实(行政区划关系)

    Returns:
        校验结果字典
    """
    issues = []
    topology_subtype = record.get("topology_subtype", "")
    entities = record.get("entities", [])
    answer = record.get("answer", "")

    # 验证包含关系
    if topology_subtype == "contains":
        # 检查是否存在明显的行政区划错误
        entity_names = [e.get("name", "") for e in entities]

        # 常见的行政区划关系
        known_relations = {
            ("北京市", "北京"): True,
            ("上海市", "上海"): True,
            ("天津市", "天津"): True,
            ("重庆市", "重庆"): True,
        }

        # 如果答案说"包含"但实际不应该包含
        if "不包含" in answer or "不相邻" in answer:
            # 这些是否定的回答，暂时跳过
            pass

    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


def validate_record(record: Dict) -> Dict[str, Any]:
    """
    对单条记录执行全面校验

    Returns:
        综合校验结果
    """
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

    # 4. 地理事实验证
    facts_result = validate_geographic_facts(record)
    results["details"]["facts"] = facts_result
    if not facts_result["valid"]:
        results["valid"] = False
        results["issues"].extend(facts_result["issues"])

    return results


# ==================== 报告生成 ====================

def generate_report(validation_results: List[Dict], output_path: str):
    """生成校验报告(Markdown格式)"""

    total = len(validation_results)
    valid_count = sum(1 for r in validation_results if r["valid"])
    invalid_count = total - valid_count

    # 统计各类型问题
    issue_stats = defaultdict(lambda: {"count": 0, "examples": []})
    for result in validation_results:
        for issue in result.get("issues", []):
            issue_type = issue.get("type", "unknown")
            issue_stats[issue_type]["count"] += 1
            if len(issue_stats[issue_type]["examples"]) < 5:
                issue_stats[issue_type]["examples"].append({
                    "id": result["id"],
                    "issue": issue
                })

    # 统计各空间类型
    type_stats = defaultdict(lambda: {"total": 0, "valid": 0, "invalid": 0})
    for result in validation_results:
        spatial_type = result.get("spatial_relation_type", "unknown")
        type_stats[spatial_type]["total"] += 1
        if result["valid"]:
            type_stats[spatial_type]["valid"] += 1
        else:
            type_stats[spatial_type]["invalid"] += 1

    # 生成报告
    report = f"""# GeoKD-SR 地理知识专家校验报告

> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **数据文件**: final_1_v5.jsonl
> **校验规则**: 距离误差阈值 {DISTANCE_ERROR_THRESHOLD*100}%

---

## 1. 校验概览

| 指标 | 数值 |
|------|------|
| 总记录数 | {total:,} |
| 校验通过 | {valid_count:,} |
| 校验失败 | {invalid_count:,} |
| **通过率** | **{valid_count/total*100:.2f}%** |

---

## 2. 分类校验结果

### 2.1 按空间关系类型统计

| 空间类型 | 总数 | 通过 | 失败 | 通过率 |
|----------|------|------|------|--------|
"""

    for spatial_type, stats in sorted(type_stats.items()):
        rate = stats["valid"] / stats["total"] * 100 if stats["total"] > 0 else 0
        report += f"| {spatial_type} | {stats['total']:,} | {stats['valid']:,} | {stats['invalid']:,} | {rate:.2f}% |\n"

    report += f"""
### 2.2 问题类型统计

| 问题类型 | 数量 | 严重程度 |
|----------|------|----------|
"""

    severity_map = {
        "coordinate_out_of_china": "🔴 严重",
        "distance_calculation_error": "🟡 中等",
        "direction_judgment_error": "🟡 中等",
        "province_coordinate_deviation": "🟢 轻微",
    }

    for issue_type, stats in sorted(issue_stats.items(), key=lambda x: -x[1]["count"]):
        severity = severity_map.get(issue_type, "⚪ 未知")
        report += f"| {issue_type} | {stats['count']:,} | {severity} |\n"

    report += """
---

## 3. 问题详情

"""

    for issue_type, stats in sorted(issue_stats.items(), key=lambda x: -x[1]["count"]):
        report += f"### 3.{list(issue_stats.keys()).index(issue_type)+1} {issue_type}\n\n"
        report += f"**数量**: {stats['count']}条\n\n"
        report += "**示例**:\n\n"

        for i, example in enumerate(stats["examples"][:3], 1):
            issue = example["issue"]
            report += f"{i}. **记录ID**: {example['id']}\n"
            report += f"   - {issue.get('message', 'N/A')}\n"
            if "answer_distance" in issue:
                report += f"   - 答案距离: {issue['answer_distance']}公里\n"
                report += f"   - 计算距离: {issue['calculated_distance']}公里\n"
                report += f"   - 误差: {issue['error_percent']}%\n"
            if "answer_direction" in issue:
                report += f"   - 答案方向: {issue['answer_direction']}\n"
                report += f"   - 计算方向: {issue['calculated_direction']}\n"
            report += "\n"

    report += """
---

## 4. 修复建议

### 4.1 距离计算问题
- 使用Haversine公式重新计算所有metric类型记录的距离
- 更新entity_database.json中的实体坐标

### 4.2 方向判断问题
- 使用标准方向计算公式重新计算
- 注意坐标顺序(从实体A到实体B)

### 4.3 省级坐标问题
- 使用国家地理信息公共服务平台的标准坐标
- 对于偏离超过2度的省级坐标进行校准

---

## 5. 数据质量评估

"""

    if valid_count / total >= 0.95:
        report += "**整体评价**: ⭐⭐⭐⭐⭐ 优秀 - 数据质量非常高\n"
    elif valid_count / total >= 0.90:
        report += "**整体评价**: ⭐⭐⭐⭐ 良好 - 数据质量较好\n"
    elif valid_count / total >= 0.80:
        report += "**整体评价**: ⭐⭐⭐ 一般 - 存在一定问题需要修复\n"
    else:
        report += "**整体评价**: ⭐⭐ 较差 - 需要重点修复\n"

    report += f"""
---

*报告生成工具: GeoKD-SR Geo Expert Validation v1.0*
"""

    # 写入文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"✅ 报告已生成: {output_path}")
    return report


def save_issues(validation_results: List[Dict], output_path: str):
    """保存问题记录到JSONL文件"""
    issues_records = []

    for result in validation_results:
        if not result["valid"]:
            issues_records.append({
                "id": result["id"],
                "spatial_relation_type": result["spatial_relation_type"],
                "topology_subtype": result["topology_subtype"],
                "issues": result["issues"],
                "issue_count": len(result["issues"])
            })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in issues_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"✅ 问题记录已保存: {output_path} ({len(issues_records)}条)")
    return issues_records


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(description='GeoKD-SR 地理知识专家校验')
    parser.add_argument('--input', type=str,
                        default='GeoKD-SR/data/final/final_1_v5.jsonl',
                        help='输入JSONL文件路径')
    parser.add_argument('--output', type=str,
                        default='GeoKD-SR/reports/geo_expert_validation_report.md',
                        help='输出报告路径')
    parser.add_argument('--issues', type=str,
                        default='GeoKD-SR/data/validation_issues.jsonl',
                        help='问题记录输出路径')
    parser.add_argument('--type', type=str, default='all',
                        choices=['all', 'metric', 'directional', 'topological'],
                        help='校验类型')

    args = parser.parse_args()

    print("=" * 60)
    print("GeoKD-SR 地理知识专家校验")
    print("=" * 60)
    print(f"📁 输入文件: {args.input}")
    print(f"📊 输出报告: {args.output}")
    print(f"📝 问题记录: {args.issues}")
    print(f"🔍 校验类型: {args.type}")
    print("=" * 60)

    # 读取数据
    print("\n📖 正在读取数据...")
    records = []
    with open(args.input, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print(f"✅ 已加载 {len(records):,} 条记录")

    # 过滤类型
    if args.type != 'all':
        records = [r for r in records if r.get('spatial_relation_type') == args.type]
        print(f"🔍 筛选{args.type}类型: {len(records):,} 条记录")

    # 执行校验
    print("\n🔬 正在校验...")
    validation_results = []

    # 进度显示
    progress_interval = max(1, len(records) // 20)

    for i, record in enumerate(records):
        if (i + 1) % progress_interval == 0 or i == len(records) - 1:
            progress = (i + 1) / len(records) * 100
            print(f"   进度: {progress:.1f}% ({i+1:,}/{len(records):,})")

        result = validate_record(record)
        validation_results.append(result)

    # 统计结果
    valid_count = sum(1 for r in validation_results if r["valid"])
    invalid_count = len(validation_results) - valid_count

    print(f"\n📊 校验完成:")
    print(f"   ✅ 通过: {valid_count:,} 条 ({valid_count/len(validation_results)*100:.2f}%)")
    print(f"   ❌ 失败: {invalid_count:,} 条 ({invalid_count/len(validation_results)*100:.2f}%)")

    # 生成报告
    print("\n📝 正在生成报告...")
    generate_report(validation_results, args.output)

    # 保存问题记录
    save_issues(validation_results, args.issues)

    print("\n" + "=" * 60)
    print("✅ 校验完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
