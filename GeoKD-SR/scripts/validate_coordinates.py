#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
地理坐标验证脚本
验证final_1_v5.jsonl中实体坐标的正确性
"""

import json
import sys
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import math

@dataclass
class CoordinateIssue:
    """坐标问题记录"""
    record_id: str
    entity_name: str
    entity_type: str
    recorded_coords: List[float]
    issue_type: str
    severity: str  # "critical" 或 "minor"
    description: str

# 中国主要地理实体坐标参考数据库
COORDINATE_REFERENCE = {
    # 省级行政区（省会/中心坐标）
    "北京市": [116.4074, 39.9042],
    "上海市": [121.4737, 31.2304],
    "天津市": [117.2000, 39.1333],
    "重庆市": [106.5516, 29.5630],
    "河北省": [114.5025, 38.0455],
    "山西省": [112.5489, 37.8706],
    "辽宁省": [123.4315, 41.7969],
    "吉林省": [125.3245, 43.8868],
    "黑龙江省": [126.6424, 45.7569],
    "江苏省": [118.7969, 32.0603],
    "浙江省": [120.1551, 30.2741],
    "安徽省": [117.2830, 31.8612],
    "福建省": [119.2965, 26.1004],
    "江西省": [115.8581, 28.6832],
    "山东省": [117.0208, 36.6683],
    "河南省": [113.6254, 34.7466],
    "湖北省": [114.3055, 30.5931],
    "湖南省": [112.9388, 28.2282],
    "广东省": [113.2644, 23.1291],
    "广西壮族自治区": [108.3275, 22.8155],
    "海南省": [110.3492, 20.0174],
    "四川省": [104.0665, 30.5723],
    "贵州省": [106.6302, 26.6477],
    "云南省": [102.7046, 25.0443],
    "西藏自治区": [91.1322, 29.6600],
    "陕西省": [108.9540, 34.2656],
    "甘肃省": [103.8343, 36.0611],
    "青海省": [101.7782, 36.6171],
    "宁夏回族自治区": [106.2586, 38.4680],
    "新疆维吾尔自治区": [87.6278, 43.7928],
    "内蒙古自治区": [111.7513, 40.8424],
    "香港特别行政区": [114.1694, 22.3193],
    "澳门特别行政区": [113.5439, 22.2006],
    "台湾省": [121.5091, 25.0445],

    # 主要城市
    "南京": [118.7969, 32.0603],
    "武汉": [114.3055, 30.5931],
    "成都": [104.0665, 30.5723],
    "西安": [108.9540, 34.2656],
    "广州": [113.2644, 23.1291],
    "深圳": [114.0859, 22.5470],
    "杭州": [120.1551, 30.2741],
    "苏州": [120.5954, 31.2989],
    "郑州": [113.6254, 34.7466],
    "长沙": [112.9388, 28.2282],
    "济南": [117.0000, 36.6500],
    "青岛": [120.3826, 36.0671],
    "大连": [121.5680, 38.9140],
    "沈阳": [123.4315, 41.7969],
    "哈尔滨": [126.6424, 45.7569],
    "长春": [125.3245, 43.8868],
    "昆明": [102.7046, 25.0443],
    "贵阳": [106.6302, 26.6477],
    "南宁": [108.3275, 22.8155],
    "福州": [119.2965, 26.1004],
    "厦门": [118.0894, 24.4798],
    "合肥": [117.2830, 31.8612],
    "南昌": [115.8581, 28.6832],
    "太原": [112.5489, 37.8706],
    "石家庄": [114.5025, 38.0455],
    "呼和浩特": [111.7513, 40.8424],
    "银川": [106.2586, 38.4680],
    "西宁": [101.7782, 36.6171],
    "兰州": [103.8343, 36.0611],
    "乌鲁木齐": [87.6278, 43.7928],
    "拉萨": [91.1322, 29.6600],

    # 更多城市
    "集安": [126.1944, 41.1258],
    "同江": [132.5108, 47.6458],
    "长治": [113.1161, 36.1953],
    "阜新": [121.6709, 42.0215],
    "邵阳": [111.4672, 27.2368],
    "泊头": [116.5667, 38.0833],
    "满洲里": [117.4789, 49.5978],
    "烟台": [121.4479, 37.4637],
    "株洲": [113.1337, 27.8274],
    "沧州": [116.8388, 38.3037],
    "张家口": [114.8869, 40.7677],
    "商洛": [109.9402, 33.8680],
    "溧阳": [119.4836, 31.4314],
    "衡水": [115.6700, 37.7348],
    "邯郸": [114.5391, 36.6256],
    "任丘": [116.0933, 38.7111],
    "延安": [109.4898, 36.5853],
    "鸡西": [130.9697, 45.2956],
    "聊城": [115.9853, 36.4559],
    "佛山": [113.1219, 23.0218],
    "百色": [106.6182, 23.9025],
    "舟山": [122.2070, 29.9850],
    "普兰店": [121.9383, 39.3917],
    "漳州": [117.6471, 24.5130],
    "鞍山": [122.9956, 41.1087],
    "定西": [104.5861, 35.5806],

    # 著名地标
    "云冈石窟": [113.1206, 40.1106],
    "黄山风景区": [118.1692, 30.1314],
    "普陀山": [122.3833, 30.0000],
    "嵩山": [113.0500, 34.4500],

    # 山脉
    "大巴山脉": [108.5000, 32.5000],
    "泰山": [117.1000, 36.2500],
    "华山": [110.0500, 34.4800],
    "衡山": [112.7200, 27.2300],
    "恒山": [113.7000, 39.6700],
    "峨眉山": [103.4800, 29.5300],

    # 河流（中点或主要流经区域）
    "海河": [117.2000, 39.1333],
    "沅江": [111.4000, 28.4000],
    "珠江": [113.2644, 23.1291],
    "乌江": [106.9000, 28.5000],
    "长江": [116.3000, 30.7000],
    "黄河": [106.5000, 36.0000],
}

def calculate_distance(coord1: List[float], coord2: List[float]) -> float:
    """计算两个坐标之间的球面距离（公里）"""
    lat1, lon1 = math.radians(coord1[1]), math.radians(coord1[0])
    lat2, lon2 = math.radians(coord2[1]), math.radians(coord2[0])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    r = 6371  # 地球半径（公里）
    return c * r

def is_in_china(coords: List[float]) -> bool:
    """检查坐标是否在中国境内"""
    lon, lat = coords
    return 73.0 <= lon <= 135.0 and 18.0 <= lat <= 53.0

def validate_entity_coord(entity_name: str, coords: List[float], entity_type: str) -> List[CoordinateIssue]:
    """验证单个实体的坐标"""
    issues = []

    # 1. 检查坐标格式
    if not isinstance(coords, list) or len(coords) != 2:
        issues.append(CoordinateIssue(
            record_id="",
            entity_name=entity_name,
            entity_type=entity_type,
            recorded_coords=coords,
            issue_type="format_error",
            severity="critical",
            description=f"坐标格式错误：应为[经度, 纬度]格式"
        ))
        return issues

    lon, lat = coords

    # 2. 检查经纬度范围
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        issues.append(CoordinateIssue(
            record_id="",
            entity_name=entity_name,
            entity_type=entity_type,
            recorded_coords=coords,
            issue_type="invalid_range",
            severity="critical",
            description=f"坐标超出有效范围：经度应在[-180,180]，纬度应在[-90,90]"
        ))
        return issues

    # 3. 检查是否在中国境内（对于中国地理实体）
    if not is_in_china(coords):
        issues.append(CoordinateIssue(
            record_id="",
            entity_name=entity_name,
            entity_type=entity_type,
            recorded_coords=coords,
            issue_type="outside_china",
            severity="critical",
            description=f"坐标不在中国境内"
        ))

    # 4. 与参考坐标对比
    # 尝试匹配实体名称（支持部分匹配）
    ref_coords = None
    matched_name = None

    for ref_name, ref_c in COORDINATE_REFERENCE.items():
        if ref_name in entity_name or entity_name in ref_name:
            ref_coords = ref_c
            matched_name = ref_name
            break

    if ref_coords:
        distance = calculate_distance(coords, ref_coords)
        if distance > 100:  # 超过100公里认为是错误
            issues.append(CoordinateIssue(
                record_id="",
                entity_name=entity_name,
                entity_type=entity_type,
                recorded_coords=coords,
                issue_type="coordinate_mismatch",
                severity="critical" if distance > 200 else "minor",
                description=f"坐标偏差{distance:.1f}公里，参考坐标{matched_name}:{ref_coords}"
            ))

    return issues

def validate_record(record: Dict) -> List[CoordinateIssue]:
    """验证单条记录中的所有实体坐标"""
    all_issues = []
    record_id = record.get("id", "unknown")

    # 从entities字段提取坐标
    entities = record.get("entities", [])
    for entity in entities:
        entity_name = entity.get("name", "")
        entity_type = entity.get("type", "")
        coords = entity.get("coords", [])

        if coords:
            issues = validate_entity_coord(entity_name, coords, entity_type)
            for issue in issues:
                issue.record_id = record_id
            all_issues.extend(issues)

    # 从reasoning_chain中提取坐标进行交叉验证
    reasoning_chain = record.get("reasoning_chain", [])
    for step in reasoning_chain:
        coords_dict = step.get("coordinates", {})
        for entity_name, coords in coords_dict.items():
            if isinstance(coords, list) and len(coords) == 2:
                issues = validate_entity_coord(entity_name, coords, "from_reasoning")
                for issue in issues:
                    issue.record_id = record_id
                all_issues.extend(issues)

    return all_issues

def validate_batch(input_file: str, start_line: int, end_line: int, output_file: str):
    """验证指定范围的数据"""
    issues = []
    total_records = 0

    with open(input_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if i < start_line:
                continue
            if i > end_line:
                break

            try:
                record = json.loads(line.strip())
                total_records += 1
                record_issues = validate_record(record)
                issues.extend(record_issues)
            except json.JSONDecodeError as e:
                issues.append(CoordinateIssue(
                    record_id=f"line_{i}",
                    entity_name="",
                    entity_type="",
                    recorded_coords=[],
                    issue_type="json_error",
                    severity="critical",
                    description=f"JSON解析错误: {str(e)}"
                ))

    # 输出结果
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# 坐标验证报告 (第{start_line}-{end_line}条)\n\n")
        f.write(f"验证记录数: {total_records}\n")
        f.write(f"发现问题数: {len(issues)}\n\n")

        critical_issues = [i for i in issues if i.severity == "critical"]
        minor_issues = [i for i in issues if i.severity == "minor"]

        f.write(f"## 严重问题 ({len(critical_issues)}个)\n\n")
        for issue in critical_issues:
            f.write(f"- **记录ID**: {issue.record_id}\n")
            f.write(f"  - **实体**: {issue.entity_name} ({issue.entity_type})\n")
            f.write(f"  - **记录坐标**: {issue.recorded_coords}\n")
            f.write(f"  - **问题类型**: {issue.issue_type}\n")
            f.write(f"  - **描述**: {issue.description}\n\n")

        f.write(f"## 轻微问题 ({len(minor_issues)}个)\n\n")
        for issue in minor_issues[:50]:  # 只显示前50个轻微问题
            f.write(f"- **记录ID**: {issue.record_id}\n")
            f.write(f"  - **实体**: {issue.entity_name} ({issue.entity_type})\n")
            f.write(f"  - **记录坐标**: {issue.recorded_coords}\n")
            f.write(f"  - **问题类型**: {issue.issue_type}\n")
            f.write(f"  - **描述**: {issue.description}\n\n")

        if len(minor_issues) > 50:
            f.write(f"... 还有 {len(minor_issues) - 50} 个轻微问题未显示\n")

    return len(issues), len(critical_issues), len(minor_issues)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python validate_coordinates.py <input_file> <start_line> <end_line> [output_file]")
        sys.exit(1)

    input_file = sys.argv[1]
    start_line = int(sys.argv[2])
    end_line = int(sys.argv[3])
    output_file = sys.argv[4] if len(sys.argv) > 4 else f"validation_report_{start_line}_{end_line}.md"

    total, critical, minor = validate_batch(input_file, start_line, end_line, output_file)
    print(f"验证完成: 共{total}个问题, 严重{critical}个, 轻微{minor}个")
    print(f"报告已保存到: {output_file}")
