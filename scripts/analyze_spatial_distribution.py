"""
空间分布分析脚本
分析实体对数据的空间分布特征
输出UTF-8编码的中文报告
"""

import json
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict
from scipy import stats
import sys
import io

# 设置标准输出为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 定义方向映射 - 使用中文方向名称
DIRECTION_8_MAP = {
    '北': 0, '东北': 1, '东': 2, '东南': 3,
    '南': 4, '西南': 5, '西': 6, '西北': 7
}

DIRECTION_NAMES = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']

def get_relation_category(target_relation):
    """将目标关系映射到类别"""
    if 'directional' in target_relation:
        return 'directional'
    elif target_relation in ['topological.contains', 'topological.within', 'topological.overlaps']:
        return 'C1'
    elif 'adjacent' in target_relation:
        return 'C2'
    elif 'metric' in target_relation:
        return 'metric'
    elif 'sameside' in target_relation:
        return 'C4'
    return 'unknown'

def load_jsonl(filepath):
    """加载JSONL文件"""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line.strip()))
    return data

def analyze_direction_distribution(data, data_name):
    """分析方向分布"""
    print(f"\n{'='*60}")
    print(f"1. 方向分布分析 - {data_name}")
    print(f"{'='*60}")

    # 筛选有direction_8的记录
    has_direction = []
    for d in data:
        if 'spatial_facts' in d and d['spatial_facts'].get('direction_8'):
            has_direction.append({
                'direction_8': d['spatial_facts']['direction_8'],
                'relation': get_relation_category(d.get('target_relation', 'unknown')),
                'target_relation': d.get('target_relation', 'unknown')
            })

    print(f"\n总记录数: {len(data)}")
    print(f"包含direction_8的记录数: {len(has_direction)} ({len(has_direction)/len(data)*100:.1f}%)")

    if len(has_direction) == 0:
        return has_direction

    # 1a. 总体8方位分布
    print(f"\n1a. 总体8方位分布:")
    print(f"{'方向':<6} {'数量':>8} {'百分比':>10}")
    print("-" * 26)

    direction_counts = Counter(d['direction_8'] for d in has_direction)
    total = len(has_direction)

    for dir_name in DIRECTION_NAMES:
        count = direction_counts.get(dir_name, 0)
        pct = count / total * 100 if total > 0 else 0
        print(f"{dir_name:<6} {count:>8} {pct:>9.2f}%")

    # 1b. 按关系类型统计
    print(f"\n1b. 按关系类型的8方位分布:")

    rel_types = {
        'directional': 'Directional关系',
        'C1': 'C1拓扑关系',
        'C2': 'C2方向关系',
        'C4': 'C4空间关系'
    }

    for rel_key, rel_name in rel_types.items():
        rel_list = [d for d in has_direction if d['relation'] == rel_key]
        if len(rel_list) == 0:
            continue

        print(f"\n{rel_name} (n={len(rel_list)}):")
        print(f"{'方向':<6} {'数量':>8} {'百分比':>10}")
        print("-" * 26)

        dir_counts = Counter(d['direction_8'] for d in rel_list)
        rel_total = len(rel_list)

        for dir_name in DIRECTION_NAMES:
            count = dir_counts.get(dir_name, 0)
            pct = count / rel_total * 100 if rel_total > 0 else 0
            print(f"{dir_name:<6} {count:>8} {pct:>9.2f}%")

    # 1c. 计算TVD
    print(f"\n1c. 各关系类型的TVD (相对于理想均匀分布12.5%):")
    print(f"{'关系类型':<20} {'TVD':>10} {'状态':>10}")
    print("-" * 42)

    uniform_pct = 0.125  # 12.5%

    for rel_key, rel_name in rel_types.items():
        rel_list = [d for d in has_direction if d['relation'] == rel_key]
        if len(rel_list) == 0:
            continue

        dir_counts = Counter(d['direction_8'] for d in rel_list)
        rel_total = len(rel_list)

        # 计算TVD
        tvd = sum(abs(dir_counts.get(d, 0) / rel_total - uniform_pct) for d in DIRECTION_NAMES) / 2

        status = "[合格]" if tvd < 0.05 else "[不合格]"
        print(f"{rel_name:<20} {tvd:>10.4f} {status:>10}")

    return has_direction

def analyze_azimuth_distribution(data, data_name):
    """分析方位角分布"""
    print(f"\n{'='*60}")
    print(f"2. 方位角分布分析 - {data_name}")
    print(f"{'='*60}")

    # 筛选有azimuth_deg的记录
    has_azimuth = []
    for d in data:
        if 'spatial_facts' in d and d['spatial_facts'].get('azimuth_deg') is not None:
            has_azimuth.append({
                'azimuth_deg': d['spatial_facts']['azimuth_deg'],
                'relation': get_relation_category(d.get('target_relation', 'unknown'))
            })

    print(f"\n包含azimuth_deg的记录数: {len(has_azimuth)}")

    if len(has_azimuth) == 0:
        return

    azimuths = [d['azimuth_deg'] for d in has_azimuth]

    # 2a. 基本统计量
    print(f"\n2a. 方位角基本统计量:")
    print(f"  最小值: {min(azimuths):.2f}°")
    print(f"  最大值: {max(azimuths):.2f}°")
    print(f"  平均值: {np.mean(azimuths):.2f}°")
    print(f"  中位数: {np.median(azimuths):.2f}°")
    print(f"  标准差: {np.std(azimuths):.2f}°")

    # 2b. 按45度区间统计
    print(f"\n2b. 按45度区间分布:")
    print(f"{'区间(度)':<15} {'数量':>8} {'百分比':>10}")
    print("-" * 35)

    bins = [0, 45, 90, 135, 180, 225, 270, 315, 360]
    bin_labels = ['[0-45)', '[45-90)', '[90-135)', '[135-180)',
                  '[180-225)', '[225-270)', '[270-315)', '[315-360)']

    hist, _ = np.histogram(azimuths, bins=bins)

    for i, (label, count) in enumerate(zip(bin_labels, hist)):
        pct = count / len(azimuths) * 100
        direction = DIRECTION_NAMES[i]
        print(f"{label:<15} {count:>8} {pct:>9.2f}% (对应{direction})")

    # 2c. 角度聚集分析
    print(f"\n2c. 角度聚集分析:")
    # 转换为弧度计算圆形统计量
    azimuths_rad = np.array([np.radians(a) for a in azimuths])

    # 计算平均向量
    mean_cos = np.mean(np.cos(azimuths_rad))
    mean_sin = np.mean(np.sin(azimuths_rad))

    # R值表示聚集程度 (0=均匀, 1=完全聚集)
    R = np.sqrt(mean_cos**2 + mean_sin**2)
    print(f"  聚集系数R: {R:.4f} (0=均匀分布, 1=完全聚集)")

    if R > 0.3:
        mean_angle = np.degrees(np.arctan2(mean_sin, mean_cos))
        if mean_angle < 0:
            mean_angle += 360
        print(f"  平均方向: {mean_angle:.2f}° (存在明显聚集)")
    else:
        print(f"  分布较为均匀")

def analyze_distance_distribution(data, data_name):
    """分析距离分布"""
    print(f"\n{'='*60}")
    print(f"3. 距离分布分析 - {data_name}")
    print(f"{'='*60}")

    # 筛选有distance_km的记录
    has_distance = []
    for d in data:
        if 'spatial_facts' in d and d['spatial_facts'].get('distance_km') is not None:
            has_distance.append({
                'distance_km': d['spatial_facts']['distance_km'],
                'relation': get_relation_category(d.get('target_relation', 'unknown')),
                'target_relation': d.get('target_relation', 'unknown'),
                'pair_id': d.get('pair_id', '')
            })

    print(f"\n包含distance_km的记录数: {len(has_distance)}")

    if len(has_distance) == 0:
        return has_distance

    distances = [d['distance_km'] for d in has_distance]

    # 3a. 按关系类型统计
    print(f"\n3a. 按关系类型的距离分布:")

    rel_groups = {
        'metric': ('Metric关系', [d for d in has_distance if d['relation'] == 'metric']),
        'C1': ('C1拓扑关系', [d for d in has_distance if d['relation'] == 'C1']),
        'C3': ('C3包含关系', [d for d in has_distance if d['relation'] == 'C3']),
        'C4': ('C4空间关系', [d for d in has_distance if d['relation'] == 'C4'])
    }

    for rel_key, (rel_name, rel_list) in rel_groups.items():
        if len(rel_list) == 0:
            continue

        rel_distances = [d['distance_km'] for d in rel_list]
        print(f"\n{rel_name} (n={len(rel_list)}):")
        print(f"  最小值: {min(rel_distances):.2f} km")
        print(f"  最大值: {max(rel_distances):.2f} km")
        print(f"  平均值: {np.mean(rel_distances):.2f} km")
        print(f"  中位数: {np.median(rel_distances):.2f} km")
        print(f"  标准差: {np.std(rel_distances):.2f} km")

        if len(rel_distances) > 2:
            skew = stats.skew(rel_distances)
            kurtosis = stats.kurtosis(rel_distances)
            print(f"  偏度: {skew:.4f}")
            print(f"  峰度: {kurtosis:.4f}")

    # 3b. metric类型距离区间分析
    metric_rels = rel_groups['metric'][1]
    if len(metric_rels) > 0:
        print(f"\n3b. Metric关系距离区间分布 (确认自然分布而非强制均匀):")
        print(f"{'区间(km)':<15} {'数量':>8} {'百分比':>10} {'理想均匀':>12}")
        print("-" * 47)

        metric_distances = [d['distance_km'] for d in metric_rels]

        bins = [0, 100, 500, 1000, 2000, float('inf')]
        bin_labels = ['[0-100)', '[100-500)', '[500-1000)', '[1000-2000)', '[2000+)']
        ideal_uniform = 100 / 5  # 20%

        hist, _ = np.histogram(metric_distances, bins=bins)

        for label, count in zip(bin_labels, hist):
            pct = count / len(metric_distances) * 100
            diff = pct - ideal_uniform
            print(f"{label:<15} {count:>8} {pct:>9.2f}% {ideal_uniform:>11.1f}% ({diff:+.1f}%)")

        # 检查是否接近均匀分布
        max_diff = max(abs(hist[i] / len(metric_distances) * 100 - ideal_uniform) for i in range(5))
        print(f"\n  最大偏差: {max_diff:.2f}%")
        if max_diff < 5:
            print(f"  结论: 接近均匀分布 (可能是强制采样)")
        else:
            print(f"  结论: 自然分布 (非强制均匀采样)")

    # 3c. C3/C4类型Point-in-Polygon约束分析
    c3_rels = rel_groups['C3'][1]
    c4_rels = rel_groups['C4'][1]

    if len(c3_rels) > 0 or len(c4_rels) > 0:
        print(f"\n3c. Point-in-Polygon约束下距离分布特征:")

        for rel_key, (rel_name, rel_list) in [('C3', ('C3包含关系', c3_rels)), ('C4', ('C4空间关系', c4_rels))]:
            if len(rel_list) == 0:
                continue

            rel_distances = [d['distance_km'] for d in rel_list]
            zero_distance = sum(1 for d in rel_distances if d < 0.01)  # <10m视为0

            print(f"\n{rel_name}:")
            print(f"  零距离(<10m): {zero_distance} ({zero_distance/len(rel_list)*100:.1f}%)")
            print(f"  平均距离: {np.mean(rel_distances):.2f} km")
            print(f"  距离中位数: {np.median(rel_distances):.2f} km")

            # 统计距离区间
            bins = [0, 0.01, 1, 10, 50, float('inf')]
            bin_labels = ['0km', '(0-1]km', '(1-10]km', '(10-50]km', '>50km']

            hist, _ = np.histogram(rel_distances, bins=bins)
            print(f"  距离分布:")
            for label, count in zip(bin_labels, hist):
                pct = count / len(rel_list) * 100
                print(f"    {label:<12} {count:>6} ({pct:>5.1f}%)")

    return has_distance

def analyze_direction_distance_correlation(data):
    """分析方向-距离联合分布"""
    print(f"\n{'='*60}")
    print(f"4. 方向-距离联合分析")
    print(f"{'='*60}")

    # 提取同时有方向和距离的数据
    has_both = []
    for d in data:
        spatial_facts = d.get('spatial_facts', {})
        if spatial_facts.get('direction_8') and spatial_facts.get('distance_km') is not None:
            has_both.append({
                'direction_8': spatial_facts['direction_8'],
                'distance_km': spatial_facts['distance_km'],
                'relation': get_relation_category(d.get('target_relation', 'unknown'))
            })

    if len(has_both) == 0:
        print(f"\n没有同时包含direction_8和distance_km的记录")
        return

    # 4a. 按8方位统计平均距离
    print(f"\n4a. 按8方位统计平均距离:")
    print(f"{'方向':<6} {'数量':>8} {'平均距离':>12} {'中位数':>12} {'标准差':>12}")
    print("-" * 52)

    dir_stats = defaultdict(list)

    for d in has_both:
        dir_stats[d['direction_8']].append(d['distance_km'])

    for dir_name in DIRECTION_NAMES:
        distances = dir_stats.get(dir_name, [])
        if len(distances) > 0:
            mean_dist = np.mean(distances)
            median_dist = np.median(distances)
            std_dist = np.std(distances)
            print(f"{dir_name:<6} {len(distances):>8} {mean_dist:>12.2f} {median_dist:>12.2f} {std_dist:>12.2f}")
        else:
            print(f"{dir_name:<6} {0:>8} {'N/A':>12} {'N/A':>12} {'N/A':>12}")

    # 4b. 方向-距离相关性分析
    print(f"\n4b. 方向-距离相关性分析:")

    # 将方向转换为数值 (0-7)
    direction_numeric = []
    distances = []

    for d in has_both:
        dir_code = DIRECTION_8_MAP.get(d['direction_8'])
        if dir_code is not None:
            direction_numeric.append(dir_code)
            distances.append(d['distance_km'])

    if len(direction_numeric) > 2:
        correlation, p_value = stats.pearsonr(direction_numeric, distances)
        print(f"  Pearson相关系数: {correlation:.4f}")
        print(f"  p值: {p_value:.4f}")

        if abs(correlation) < 0.1:
            print(f"  结论: 方向与距离无明显相关")
        elif p_value < 0.05:
            direction = "正相关" if correlation > 0 else "负相关"
            print(f"  结论: 存在{direction} (p<{p_value:.4f})")
        else:
            print(f"  结论: 相关性不显著")

def analyze_negative_examples(data):
    """分析负例的空间分布特征"""
    print(f"\n{'='*60}")
    print(f"5. 负例空间分布特征分析")
    print(f"{'='*60}")

    # 5a. 关系类型分布
    print(f"\n5a. 负例关系类型分布:")
    rel_counts = Counter(get_relation_category(d.get('target_relation', 'unknown')) for d in data)
    total = len(data)

    print(f"{'关系类型':<15} {'数量':>8} {'百分比':>10}")
    print("-" * 35)

    for rel_type, count in rel_counts.most_common():
        pct = count / total * 100
        print(f"{rel_type:<15} {count:>8} {pct:>9.2f}%")

    # 5b. C2/C3/C4负例的方向/距离分布
    for rel_type in ['C2', 'C3', 'C4']:
        rel_data = [d for d in data if get_relation_category(d.get('target_relation', 'unknown')) == rel_type]
        if len(rel_data) == 0:
            continue

        print(f"\n5b-{rel_type} {rel_type}关系负例分析:")

        # 方向分布
        if rel_type in ['C2', 'C4']:
            has_direction = []
            for d in rel_data:
                if 'spatial_facts' in d and d['spatial_facts'].get('direction_8'):
                    has_direction.append(d['spatial_facts']['direction_8'])

            if len(has_direction) > 0:
                print(f"  方向分布 (n={len(has_direction)}):")
                dir_counts = Counter(has_direction)
                for dir_name in DIRECTION_NAMES:
                    count = dir_counts.get(dir_name, 0)
                    pct = count / len(has_direction) * 100
                    print(f"    {dir_name}: {count} ({pct:.1f}%)")
            else:
                print(f"  无方向数据")

        # 距离分布
        if rel_type in ['C3', 'C4']:
            has_distance = []
            for d in rel_data:
                if 'spatial_facts' in d and d['spatial_facts'].get('distance_km') is not None:
                    has_distance.append(d['spatial_facts']['distance_km'])

            if len(has_distance) > 0:
                print(f"  距离统计 (n={len(has_distance)}):")
                print(f"    平均距离: {np.mean(has_distance):.2f} km")
                print(f"    中位数: {np.median(has_distance):.2f} km")
                print(f"    标准差: {np.std(has_distance):.2f} km")
            else:
                print(f"  无距离数据")

def generate_summary_report(positive_data, negative_data):
    """生成总结报告"""
    print(f"\n{'='*60}")
    print(f"总结报告")
    print(f"{'='*60}")

    # 数据覆盖统计
    pos_has_dir = sum(1 for d in positive_data if 'spatial_facts' in d and d['spatial_facts'].get('direction_8'))
    pos_has_azi = sum(1 for d in positive_data if 'spatial_facts' in d and d['spatial_facts'].get('azimuth_deg') is not None)
    pos_has_dist = sum(1 for d in positive_data if 'spatial_facts' in d and d['spatial_facts'].get('distance_km') is not None)

    print(f"\n正例数据覆盖情况:")
    print(f"  总记录数: {len(positive_data)}")
    print(f"  方向数据: {pos_has_dir} ({pos_has_dir/len(positive_data)*100:.1f}%)")
    print(f"  方位角数据: {pos_has_azi} ({pos_has_azi/len(positive_data)*100:.1f}%)")
    print(f"  距离数据: {pos_has_dist} ({pos_has_dist/len(positive_data)*100:.1f}%)")

    neg_has_dir = sum(1 for d in negative_data if 'spatial_facts' in d and d['spatial_facts'].get('direction_8'))
    neg_has_dist = sum(1 for d in negative_data if 'spatial_facts' in d and d['spatial_facts'].get('distance_km') is not None)

    print(f"\n负例数据覆盖情况:")
    print(f"  总记录数: {len(negative_data)}")
    print(f"  方向数据: {neg_has_dir} ({neg_has_dir/len(negative_data)*100:.1f}%)")
    print(f"  距离数据: {neg_has_dist} ({neg_has_dist/len(negative_data)*100:.1f}%)")

def main():
    """主函数"""
    print("="*60)
    print("实体对空间分布特征分析")
    print("="*60)

    # 数据路径
    positive_path = Path(r"D:\gis_data\output\pairs_positive.jsonl")
    negative_path = Path(r"D:\gis_data\output\pairs_negative.jsonl")

    # 加载数据
    print("\n加载数据...")
    positive_data = load_jsonl(positive_path)
    negative_data = load_jsonl(negative_path)

    print(f"正例数据: {len(positive_data)} 条")
    print(f"负例数据: {len(negative_data)} 条")

    # 分析正例
    analyze_direction_distribution(positive_data, "正例数据")
    analyze_azimuth_distribution(positive_data, "正例数据")
    analyze_distance_distribution(positive_data, "正例数据")
    analyze_direction_distance_correlation(positive_data)

    # 分析负例
    analyze_negative_examples(negative_data)

    # 生成总结报告
    generate_summary_report(positive_data, negative_data)

    print(f"\n{'='*60}")
    print("分析完成!")
    print(f"{'='*60}")

if __name__ == "__main__":
    # 同时输出到文件和终端
    output_file = Path(r"D:\30_keyan\scripts\spatial_distribution_analysis_report.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        # 保存原始stdout
        original_stdout = sys.stdout
        # 重定向到文件
        sys.stdout = f
        try:
            main()
        finally:
            # 恢复stdout
            sys.stdout = original_stdout

    print(f"报告已生成: {output_file}")
    print("\n报告内容:")
    print("-" * 60)

    # 读取并显示报告内容
    with open(output_file, 'r', encoding='utf-8') as f:
        print(f.read())
