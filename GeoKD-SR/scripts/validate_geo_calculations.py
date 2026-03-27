"""
地理位置计算验证脚本
验证 split_coords 目录中数据的距离和方向计算是否正确
允许50公里偏差
"""

import json
import math
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# 地球半径（公里）
EARTH_RADIUS = 6371

# 允许的距离偏差（公里）
DISTANCE_TOLERANCE = 50


def haversine_distance(coord1, coord2):
    """
    计算两点间的球面距离（Haversine公式）
    coord: [经度, 纬度]
    返回：距离（公里）
    """
    lon1, lat1 = coord1
    lon2, lat2 = coord2

    # 转换为弧度
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Haversine公式
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return EARTH_RADIUS * c


def calculate_bearing(coord1, coord2):
    """
    计算从coord1到coord2的方位角
    coord: [经度, 纬度]
    返回：方位角（度，0-360）
    """
    lon1, lat1 = math.radians(coord1[0]), math.radians(coord1[1])
    lon2, lat2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    bearing = math.atan2(x, y)
    bearing = math.degrees(bearing)
    return (bearing + 360) % 360


def bearing_to_direction(bearing):
    """
    将方位角转换为8方向描述
    """
    directions = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
    # 每个方向占45度，从北开始
    index = round(bearing / 45) % 8
    return directions[index]


def bearing_to_detailed_direction(bearing):
    """
    将方位角转换为更详细的方向描述（包括偏方向）
    """
    # 16方向系统
    if 0 <= bearing < 11.25 or 348.75 <= bearing <= 360:
        return '北'
    elif 11.25 <= bearing < 33.75:
        return '北偏东'
    elif 33.75 <= bearing < 56.25:
        return '东北'
    elif 56.25 <= bearing < 78.75:
        return '东偏北'
    elif 78.75 <= bearing < 101.25:
        return '东'
    elif 101.25 <= bearing < 123.75:
        return '东偏南'
    elif 123.75 <= bearing < 146.25:
        return '东南'
    elif 146.25 <= bearing < 168.75:
        return '南偏东'
    elif 168.75 <= bearing < 191.25:
        return '南'
    elif 191.25 <= bearing < 213.75:
        return '南偏西'
    elif 213.75 <= bearing < 236.25:
        return '西南'
    elif 236.25 <= bearing < 258.75:
        return '西偏南'
    elif 258.75 <= bearing < 281.25:
        return '西'
    elif 281.25 <= bearing < 303.75:
        return '西偏北'
    elif 303.75 <= bearing < 326.25:
        return '西北'
    elif 326.25 <= bearing < 348.75:
        return '北偏西'
    return '未知'


def extract_distance_from_answer(answer):
    """
    从答案中提取距离数值
    支持格式：
    - 约XXX公里
    - XXX公里
    - 距离约XXX公里
    - 直线距离约XXX公里
    """
    # 匹配各种距离格式
    patterns = [
        r'约(\d+\.?\d*)\s*公里',
        r'(\d+\.?\d*)\s*公里',
        r'距离[约为]*(\d+\.?\d*)\s*公里',
        r'直线距离[约为]*(\d+\.?\d*)\s*公里',
    ]

    for pattern in patterns:
        match = re.search(pattern, answer)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def extract_direction_from_answer(answer):
    """
    从答案中提取方向描述
    """
    # 8方向关键词
    directions_8 = ['东北', '东南', '西北', '西南', '北', '东', '南', '西']

    # 偏方向关键词
    partial_directions = ['北偏东', '北偏西', '南偏东', '南偏西',
                          '东偏北', '东偏南', '西偏北', '西偏南',
                          '正北', '正南', '正东', '正西']

    # 先尝试匹配偏方向
    for d in partial_directions:
        if d in answer:
            return d

    # 再匹配8方向
    for d in directions_8:
        if d in answer:
            return d

    return None


def direction_match(calculated_dir, answer_dir):
    """
    检查计算方向和答案方向是否匹配
    使用更宽松的匹配规则
    """
    if not calculated_dir or not answer_dir:
        return False, "方向为空"

    # 标准化方向
    dir_mapping = {
        '北': ['北', '正北', '北方'],
        '南': ['南', '正南', '南方'],
        '东': ['东', '正东', '东方'],
        '西': ['西', '正西', '西方'],
        '东北': ['东北', '东北方'],
        '东南': ['东南', '东南方'],
        '西北': ['西北', '西北方'],
        '西南': ['西南', '西南方'],
    }

    # 宽松的偏方向兼容性（相邻方向可接受）
    # 例如：东和东偏北可以匹配，东北和东偏北可以匹配
    partial_compat = {
        '北偏东': ['北偏东', '东北', '北', '东'],
        '北偏西': ['北偏西', '西北', '北', '西'],
        '南偏东': ['南偏东', '东南', '南', '东'],
        '南偏西': ['南偏西', '西南', '南', '西'],
        '东偏北': ['东偏北', '东北', '东', '北'],
        '东偏南': ['东偏南', '东南', '东', '南'],
        '西偏北': ['西偏北', '西北', '西', '北'],
        '西偏南': ['西偏南', '西南', '西', '南'],
        '正北': ['正北', '北', '北偏东', '北偏西'],
        '正南': ['正南', '南', '南偏东', '南偏西'],
        '正东': ['正东', '东', '东偏北', '东偏南'],
        '正西': ['正西', '西', '西偏北', '西偏南'],
    }

    # 8方向到偏方向的映射
    main_to_partial = {
        '北': ['北', '北偏东', '北偏西', '正北'],
        '南': ['南', '南偏东', '南偏西', '正南'],
        '东': ['东', '东偏北', '东偏南', '正东'],
        '西': ['西', '西偏北', '西偏南', '正西'],
        '东北': ['东北', '东偏北', '北偏东'],
        '东南': ['东南', '东偏南', '南偏东'],
        '西北': ['西北', '西偏北', '北偏西'],
        '西南': ['西南', '西偏南', '南偏西'],
    }

    # 检查是否兼容
    for main_dir, aliases in dir_mapping.items():
        if calculated_dir in aliases and answer_dir in aliases:
            return True, None

    # 检查8方向到偏方向的兼容性
    for main_dir, partials in main_to_partial.items():
        if calculated_dir == main_dir and answer_dir in partials:
            return True, None
        if answer_dir == main_dir and calculated_dir in partials:
            return True, None

    # 检查偏方向兼容性
    for partial, compat_list in partial_compat.items():
        if calculated_dir in compat_list and answer_dir in compat_list:
            return True, None
        if calculated_dir == partial and answer_dir in compat_list:
            return True, None
        if answer_dir == partial and calculated_dir in compat_list:
            return True, None

    # 检查8方向
    if calculated_dir == answer_dir:
        return True, None

    # 检查是否是相近方向（如东北和东偏北）
    similar_pairs = [
        ('东北', '东偏北'), ('东北', '北偏东'),
        ('东南', '东偏南'), ('东南', '南偏东'),
        ('西北', '西偏北'), ('西北', '北偏西'),
        ('西南', '西偏南'), ('西南', '南偏西'),
        # 主方向和偏方向的兼容
        ('北', '北偏东'), ('北', '北偏西'),
        ('南', '南偏东'), ('南', '南偏西'),
        ('东', '东偏北'), ('东', '东偏南'),
        ('西', '西偏北'), ('西', '西偏南'),
    ]
    for d1, d2 in similar_pairs:
        if (calculated_dir == d1 and answer_dir == d2) or (calculated_dir == d2 and answer_dir == d1):
            return True, None

    return False, f"方向不匹配: 计算={calculated_dir}, 答案={answer_dir}"


def validate_metric_record(record):
    """
    验证度量关系（距离）记录
    """
    errors = []

    entities = record.get('entities', [])
    if len(entities) < 2:
        return [{"error": "实体数量不足"}]

    coord1 = entities[0].get('coords')
    coord2 = entities[1].get('coords')

    if not coord1 or not coord2:
        return [{"error": "坐标缺失"}]

    # 计算实际距离
    calculated_distance = haversine_distance(coord1, coord2)

    # 从答案提取距离
    answer = record.get('answer', '')
    answer_distance = extract_distance_from_answer(answer)

    if answer_distance is None:
        return [{"error": "无法从答案中提取距离", "answer": answer}]

    # 比较距离
    diff = abs(calculated_distance - answer_distance)

    if diff > DISTANCE_TOLERANCE:
        errors.append({
            "error": "距离偏差过大",
            "entity1": entities[0].get('name'),
            "entity2": entities[1].get('name'),
            "calculated_distance": round(calculated_distance, 2),
            "answer_distance": answer_distance,
            "diff_km": round(diff, 2),
            "coord1": coord1,
            "coord2": coord2
        })

    return errors


def validate_directional_record(record):
    """
    验证方向关系记录
    """
    errors = []

    entities = record.get('entities', [])
    if len(entities) < 2:
        return [{"error": "实体数量不足"}]

    coord1 = entities[0].get('coords')
    coord2 = entities[1].get('coords')

    if not coord1 or not coord2:
        return [{"error": "坐标缺失"}]

    # 计算方位角和方向
    bearing = calculate_bearing(coord1, coord2)
    calculated_direction = bearing_to_direction(bearing)
    detailed_direction = bearing_to_detailed_direction(bearing)

    # 从答案提取方向
    answer = record.get('answer', '')
    answer_direction = extract_direction_from_answer(answer)

    if answer_direction is None:
        return [{"error": "无法从答案中提取方向", "answer": answer}]

    # 检查方向匹配
    is_match, match_error = direction_match(calculated_direction, answer_direction)

    if not is_match:
        errors.append({
            "error": match_error or "方向不匹配",
            "entity1": entities[0].get('name'),
            "entity2": entities[1].get('name'),
            "calculated_direction": calculated_direction,
            "detailed_direction": detailed_direction,
            "bearing": round(bearing, 2),
            "answer_direction": answer_direction,
            "coord1": coord1,
            "coord2": coord2
        })

    return errors


def validate_composite_record(record):
    """
    验证复合关系（距离+方向）记录
    """
    errors = []

    entities = record.get('entities', [])
    if len(entities) < 2:
        return [{"error": "实体数量不足"}]

    coord1 = entities[0].get('coords')
    coord2 = entities[1].get('coords')

    if not coord1 or not coord2:
        return [{"error": "坐标缺失"}]

    answer = record.get('answer', '')

    # 验证距离
    calculated_distance = haversine_distance(coord1, coord2)
    answer_distance = extract_distance_from_answer(answer)

    if answer_distance is not None:
        diff = abs(calculated_distance - answer_distance)
        if diff > DISTANCE_TOLERANCE:
            errors.append({
                "error": "距离偏差过大",
                "entity1": entities[0].get('name'),
                "entity2": entities[1].get('name'),
                "calculated_distance": round(calculated_distance, 2),
                "answer_distance": answer_distance,
                "diff_km": round(diff, 2)
            })

    # 验证方向
    bearing = calculate_bearing(coord1, coord2)
    calculated_direction = bearing_to_direction(bearing)
    answer_direction = extract_direction_from_answer(answer)

    if answer_direction is not None:
        is_match, match_error = direction_match(calculated_direction, answer_direction)
        if not is_match:
            errors.append({
                "error": match_error or "方向不匹配",
                "entity1": entities[0].get('name'),
                "entity2": entities[1].get('name'),
                "calculated_direction": calculated_direction,
                "answer_direction": answer_direction,
                "bearing": round(bearing, 2)
            })

    return errors


def load_jsonl(file_path):
    """加载JSONL文件"""
    records = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {file_path}, 行: {line[:50]}...")
    return records


def main():
    """主函数"""
    data_dir = Path("D:/30_keyan/GeoKD-SR/data/split_coords")
    output_dir = Path("D:/30_keyan/GeoKD-SR/reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 统计信息
    stats = {
        'total': 0,
        'by_type': defaultdict(lambda: {'total': 0, 'errors': 0}),
        'errors_by_type': defaultdict(list)
    }

    # 处理每个文件
    files = ['train.jsonl', 'dev.jsonl', 'test.jsonl']

    for file_name in files:
        file_path = data_dir / file_name
        if not file_path.exists():
            print(f"文件不存在: {file_path}")
            continue

        print(f"处理文件: {file_name}")
        records = load_jsonl(file_path)

        for record in records:
            stats['total'] += 1
            record_type = record.get('spatial_relation_type', 'unknown')
            stats['by_type'][record_type]['total'] += 1

            # 根据类型验证
            if record_type == 'metric':
                errors = validate_metric_record(record)
            elif record_type == 'directional':
                errors = validate_directional_record(record)
            elif record_type == 'composite':
                errors = validate_composite_record(record)
            else:
                # topological 类型跳过验证
                continue

            if errors:
                stats['by_type'][record_type]['errors'] += len(errors)
                for error in errors:
                    error['id'] = record.get('id')
                    error['type'] = record_type
                    error['file'] = file_name
                    stats['errors_by_type'][record_type].append(error)

    # 生成报告
    generate_report(stats, output_dir)
    print(f"\n验证完成！报告已保存到: {output_dir}")


def generate_report(stats, output_dir):
    """生成验证报告"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"geo_validation_report_{timestamp}.md"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 地理位置计算验证报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 摘要
        f.write("## 验证摘要\n\n")
        f.write(f"- **总样本数**: {stats['total']}\n")

        # 各类型统计
        f.write("\n### 各类型验证结果\n\n")
        f.write("| 类型 | 总数 | 验证数 | 错误数 | 错误率 |\n")
        f.write("|------|------|--------|--------|--------|\n")

        validation_types = ['metric', 'directional', 'composite']
        for type_name in validation_types:
            type_stats = stats['by_type'].get(type_name, {'total': 0, 'errors': 0})
            total = type_stats['total']
            errors = type_stats['errors']
            error_rate = f"{errors/total*100:.2f}%" if total > 0 else "N/A"
            f.write(f"| {type_name} | {total} | {total} | {errors} | {error_rate} |\n")

        # 跳过的类型
        topo_total = stats['by_type'].get('topological', {'total': 0})['total']
        f.write(f"| topological | {topo_total} | - | - | 跳过（定性关系） |\n")

        # 错误详情
        f.write("\n## 错误详情\n\n")

        for type_name in validation_types:
            errors = stats['errors_by_type'].get(type_name, [])
            if not errors:
                f.write(f"### {type_name} 类型\n无错误\n\n")
                continue

            f.write(f"### {type_name} 类型 ({len(errors)} 个错误)\n\n")

            if type_name == 'metric':
                f.write("| ID | 实体1 | 实体2 | 计算距离(km) | 答案距离(km) | 偏差(km) |\n")
                f.write("|----|-------|-------|-------------|-------------|----------|\n")
                for e in errors[:100]:  # 限制显示前100个
                    f.write(f"| {e.get('id', 'N/A')} | {e.get('entity1', 'N/A')} | {e.get('entity2', 'N/A')} | "
                           f"{e.get('calculated_distance', 'N/A')} | {e.get('answer_distance', 'N/A')} | "
                           f"{e.get('diff_km', 'N/A')} |\n")

            elif type_name == 'directional':
                f.write("| ID | 实体1 | 实体2 | 计算方向 | 答案方向 | 方位角 |\n")
                f.write("|----|-------|-------|---------|---------|--------|\n")
                for e in errors[:100]:
                    f.write(f"| {e.get('id', 'N/A')} | {e.get('entity1', 'N/A')} | {e.get('entity2', 'N/A')} | "
                           f"{e.get('calculated_direction', 'N/A')} | {e.get('answer_direction', 'N/A')} | "
                           f"{e.get('bearing', 'N/A')}° |\n")

            elif type_name == 'composite':
                f.write("| ID | 实体1 | 实体2 | 错误类型 | 详情 |\n")
                f.write("|----|-------|-------|---------|------|\n")
                for e in errors[:100]:
                    f.write(f"| {e.get('id', 'N/A')} | {e.get('entity1', 'N/A')} | {e.get('entity2', 'N/A')} | "
                           f"{e.get('error', 'N/A')} | - |\n")

            if len(errors) > 100:
                f.write(f"\n*注：仅显示前100条错误，共{len(errors)}条*\n")

            f.write("\n")

        # 错误分析
        f.write("## 错误分析\n\n")

        # 距离错误分析
        metric_errors = stats['errors_by_type'].get('metric', [])
        if metric_errors:
            distances = [e.get('diff_km', 0) for e in metric_errors if e.get('diff_km')]
            if distances:
                f.write("### 距离错误分布\n\n")
                f.write(f"- 平均偏差: {sum(distances)/len(distances):.2f} km\n")
                f.write(f"- 最大偏差: {max(distances):.2f} km\n")
                f.write(f"- 最小偏差: {min(distances):.2f} km\n\n")

        # 方向错误分析
        directional_errors = stats['errors_by_type'].get('directional', [])
        if directional_errors:
            f.write("### 方向错误分析\n\n")
            direction_counts = defaultdict(int)
            for e in directional_errors:
                direction_counts[e.get('calculated_direction', '未知')] += 1
            f.write("计算方向分布:\n")
            for d, count in sorted(direction_counts.items()):
                f.write(f"- {d}: {count}\n")
            f.write("\n")

        # 建议
        f.write("## 建议\n\n")
        total_errors = sum(len(e) for e in stats['errors_by_type'].values())
        if total_errors > 0:
            f.write("1. 检查距离计算错误的样本，确认坐标是否正确\n")
            f.write("2. 对于方向不匹配的样本，考虑方向描述的模糊性\n")
            f.write("3. 复合关系错误需要分别检查距离和方向\n")
        else:
            f.write("所有验证样本均通过验证，数据质量良好。\n")

    print(f"报告已生成: {report_path}")

    # 同时输出简短摘要
    print(f"\n===== 验证摘要 =====")
    print(f"总样本数: {stats['total']}")
    for type_name in ['metric', 'directional', 'composite']:
        type_stats = stats['by_type'].get(type_name, {'total': 0, 'errors': 0})
        print(f"{type_name}: {type_stats['total']}条, 错误{type_stats['errors']}条")
    print(f"总错误数: {total_errors}")


if __name__ == "__main__":
    main()
