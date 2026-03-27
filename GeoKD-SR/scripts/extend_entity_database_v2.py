#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实体库扩展脚本 V2
扩展内容:
1. provinces.neighbors - 省份相邻关系
2. provinces.cities - 省份包含的城市列表
3. provinces.contains_landmarks - 省份包含的地标列表
4. rivers.provinces - 河流流经省份
5. mountains.provinces - 山脉跨越省份
6. lakes.provinces - 湖泊所在省份(跨省湖泊)
7. regions.provinces - 区域包含省份

作者: Claude
日期: 2026-03-11
"""

import json
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict


# ==================== 省份相邻关系数据 ====================
# 基于中国行政区划地理邻接关系
PROVINCE_NEIGHBORS = {
    "北京市": ["天津市", "河北省"],
    "天津市": ["北京市", "河北省"],
    "河北省": ["北京市", "天津市", "辽宁省", "内蒙古自治区", "山西省", "河南省", "山东省"],
    "山西省": ["河北省", "内蒙古自治区", "陕西省", "河南省"],
    "内蒙古自治区": ["黑龙江省", "吉林省", "辽宁省", "河北省", "山西省", "陕西省", "宁夏回族自治区", "甘肃省"],
    "辽宁省": ["吉林省", "内蒙古自治区", "河北省"],
    "吉林省": ["黑龙江省", "内蒙古自治区", "辽宁省"],
    "黑龙江省": ["吉林省", "内蒙古自治区"],
    "上海市": ["江苏省", "浙江省"],
    "江苏省": ["上海市", "浙江省", "安徽省", "山东省", "河南省"],
    "浙江省": ["上海市", "江苏省", "安徽省", "江西省", "福建省"],
    "安徽省": ["江苏省", "浙江省", "江西省", "湖北省", "河南省", "山东省"],
    "福建省": ["浙江省", "江西省", "广东省"],
    "江西省": ["安徽省", "浙江省", "福建省", "广东省", "湖南省", "湖北省"],
    "山东省": ["河北省", "河南省", "安徽省", "江苏省"],
    "河南省": ["河北省", "山西省", "陕西省", "湖北省", "安徽省", "江苏省", "山东省"],
    "湖北省": ["河南省", "安徽省", "江西省", "湖南省", "重庆市", "陕西省"],
    "湖南省": ["湖北省", "江西省", "广东省", "广西壮族自治区", "贵州省", "重庆市"],
    "广东省": ["福建省", "江西省", "湖南省", "广西壮族自治区", "海南省"],
    "广西壮族自治区": ["湖南省", "广东省", "贵州省", "云南省"],
    "海南省": ["广东省"],
    "重庆市": ["四川省", "贵州省", "湖南省", "湖北省", "陕西省"],
    "四川省": ["青海省", "甘肃省", "陕西省", "重庆市", "贵州省", "云南省", "西藏自治区"],
    "贵州省": ["四川省", "云南省", "广西壮族自治区", "湖南省", "重庆市"],
    "云南省": ["四川省", "贵州省", "广西壮族自治区", "西藏自治区"],
    "西藏自治区": ["新疆维吾尔自治区", "青海省", "四川省", "云南省"],
    "陕西省": ["山西省", "内蒙古自治区", "宁夏回族自治区", "甘肃省", "四川省", "重庆市", "湖北省", "河南省"],
    "甘肃省": ["内蒙古自治区", "宁夏回族自治区", "陕西省", "四川省", "青海省", "新疆维吾尔自治区"],
    "青海省": ["甘肃省", "新疆维吾尔自治区", "西藏自治区", "四川省"],
    "宁夏回族自治区": ["内蒙古自治区", "陕西省", "甘肃省"],
    "新疆维吾尔自治区": ["甘肃省", "青海省", "西藏自治区"],
    "香港特别行政区": ["广东省"],
    "澳门特别行政区": ["广东省"],
    "台湾省": [],  # 海岛省份，无陆地相邻
}


# ==================== 河流流经省份数据 ====================
RIVER_PROVINCES = {
    "长江": ["青海省", "西藏自治区", "四川省", "云南省", "重庆市", "湖北省", "湖南省", "江西省", "安徽省", "江苏省", "上海市"],
    "黄河": ["青海省", "四川省", "甘肃省", "宁夏回族自治区", "内蒙古自治区", "陕西省", "山西省", "河南省", "山东省"],
    "珠江": ["云南省", "贵州省", "广西壮族自治区", "广东省"],
    "淮河": ["河南省", "安徽省", "江苏省"],
    "海河": ["山西省", "河北省", "北京市", "天津市"],
    "辽河": ["河北省", "内蒙古自治区", "吉林省", "辽宁省"],
    "松花江": ["吉林省", "黑龙江省"],
    "雅鲁藏布江": ["西藏自治区"],
    "澜沧江": ["青海省", "西藏自治区", "云南省"],
    "怒江": ["西藏自治区", "云南省"],
    "闽江": ["福建省"],
    "钱塘江": ["安徽省", "浙江省"],
    "汉江": ["陕西省", "湖北省"],
    "赣江": ["江西省"],
    "湘江": ["广西壮族自治区", "湖南省"],
    "嘉陵江": ["陕西省", "甘肃省", "四川省", "重庆市"],
    "岷江": ["四川省"],
    "大渡河": ["青海省", "四川省"],
    "塔里木河": ["新疆维吾尔自治区"],
    "黑龙江": ["黑龙江省"],
    "鸭绿江": ["吉林省"],
    "图们江": ["吉林省"],
    "乌苏里江": ["黑龙江省"],
    "红河": ["云南省"],
    "伊犁河": ["新疆维吾尔自治区"],
    "额尔齐斯河": ["新疆维吾尔自治区"],
    "湟水": ["青海省", "甘肃省"],
    "渭河": ["甘肃省", "陕西省"],
    "汾河": ["山西省"],
    "沅江": ["贵州省", "湖南省"],
}


# ==================== 山脉跨越省份数据 ====================
MOUNTAIN_PROVINCES = {
    "喜马拉雅山脉": ["西藏自治区"],
    "昆仑山脉": ["新疆维吾尔自治区", "西藏自治区", "青海省"],
    "天山山脉": ["新疆维吾尔自治区"],
    "秦岭": ["甘肃省", "陕西省", "河南省"],
    "大兴安岭": ["内蒙古自治区", "黑龙江省"],
    "太行山脉": ["北京市", "河北省", "山西省", "河南省"],
    "武夷山脉": ["江西省", "福建省"],
    "南岭": ["湖南省", "江西省", "广东省", "广西壮族自治区"],
    "横断山脉": ["四川省", "云南省", "西藏自治区"],
    "长白山脉": ["吉林省"],
    "祁连山脉": ["甘肃省", "青海省"],
    "阿尔泰山脉": ["新疆维吾尔自治区"],
    "阴山山脉": ["内蒙古自治区"],
    "燕山山脉": ["河北省", "北京市", "天津市"],
    "大巴山脉": ["四川省", "重庆市", "湖北省", "陕西省"],
    "武陵山脉": ["湖南省", "湖北省", "重庆市", "贵州省"],
    "雪峰山脉": ["湖南省"],
    "罗霄山脉": ["湖南省", "江西省"],
    "六盘山": ["宁夏回族自治区", "甘肃省", "陕西省"],
    "贺兰山": ["宁夏回族自治区", "内蒙古自治区"],
    "吕梁山脉": ["山西省"],
    "大别山脉": ["湖北省", "河南省", "安徽省"],
    "井冈山": ["江西省"],
    "雁荡山": ["浙江省"],
    "峨眉山": ["四川省"],
    "庐山": ["江西省"],
    "武当山": ["湖北省"],
    "黄山": ["安徽省"],
    "泰山": ["山东省"],
    "华山": ["陕西省"],
    "衡山": ["湖南省"],
    "嵩山": ["河南省"],
    "恒山": ["山西省"],
    "九华山": ["安徽省"],
    "普陀山": ["浙江省"],
    "五台山": ["山西省"],
    "青城山": ["四川省"],
    "三清山": ["江西省"],
}


# ==================== 湖泊所在省份数据 ====================
LAKE_PROVINCES = {
    "青海湖": ["青海省"],
    "鄱阳湖": ["江西省"],
    "洞庭湖": ["湖南省"],
    "太湖": ["江苏省", "浙江省"],  # 跨省湖泊
    "洪泽湖": ["江苏省"],
    "巢湖": ["安徽省"],
    "纳木错": ["西藏自治区"],
    "色林错": ["西藏自治区"],
    "滇池": ["云南省"],
    "洱海": ["云南省"],
    "西湖": ["浙江省"],
    "千岛湖": ["浙江省"],
    "呼伦湖": ["内蒙古自治区"],
    "博斯腾湖": ["新疆维吾尔自治区"],
    "南四湖": ["山东省"],
    "镜泊湖": ["黑龙江省"],
    "长白山天池": ["吉林省"],
    "泸沽湖": ["四川省", "云南省"],  # 跨省湖泊
}


# ==================== 区域包含省份数据 ====================
REGION_PROVINCES = {
    "长三角": ["上海市", "江苏省", "浙江省", "安徽省"],
    "珠三角": ["广东省"],
    "京津冀": ["北京市", "天津市", "河北省"],
    "环渤海": ["北京市", "天津市", "河北省", "辽宁省", "山东省"],
    "粤港澳大湾区": ["广东省", "香港特别行政区", "澳门特别行政区"],
    "长江中游城市群": ["湖北省", "湖南省", "江西省"],
    "成渝城市群": ["四川省", "重庆市"],
    "中原城市群": ["河南省"],
    "海峡西岸": ["福建省"],
    "北部湾": ["广西壮族自治区"],
    "关中平原": ["陕西省"],
    "哈长城市群": ["黑龙江省", "吉林省"],
    "辽中南": ["辽宁省"],
    "山东半岛": ["山东省"],
    "皖江城市带": ["安徽省"],
    "长株潭": ["湖南省"],
    "武汉城市圈": ["湖北省"],
    "鄱阳湖生态经济区": ["江西省"],
    "太原都市圈": ["山西省"],
    "乌鲁木齐都市圈": ["新疆维吾尔自治区"],
}


def extend_entity_database(input_path: str, output_path: str):
    """
    扩展实体数据库

    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
    """
    # 读取原始数据
    with open(input_path, 'r', encoding='utf-8') as f:
        db = json.load(f)

    entities = db['entities']

    # 1. 扩展省份 - 添加neighbors, cities, contains_landmarks
    print("正在扩展省份实体...")
    province_names = {p['name'] for p in entities['provinces']}

    # 构建省份-城市映射
    province_cities = defaultdict(list)
    for city in entities['cities']:
        prov = city.get('province', '')
        if prov:
            province_cities[prov].append(city['name'])

    # 构建省份-地标映射
    city_to_province = {c['name']: c['province'] for c in entities['cities']}
    province_landmarks = defaultdict(list)
    for lm in entities['landmarks']:
        city = lm.get('city', '')
        prov = city_to_province.get(city, '')
        if prov:
            province_landmarks[prov].append(lm['name'])

    # 扩展省份数据
    for prov in entities['provinces']:
        name = prov['name']
        prov['neighbors'] = [n for n in PROVINCE_NEIGHBORS.get(name, []) if n in province_names]
        prov['cities'] = province_cities.get(name, [])
        prov['contains_landmarks'] = province_landmarks.get(name, [])

    # 2. 扩展河流 - 添加provinces
    print("正在扩展河流实体...")
    river_names = {r['name'] for r in entities['rivers']}
    for river in entities['rivers']:
        name = river['name']
        if name in RIVER_PROVINCES:
            river['provinces'] = [p for p in RIVER_PROVINCES[name] if p in province_names]
        else:
            river['provinces'] = []

    # 3. 扩展山脉 - 添加provinces
    print("正在扩展山脉实体...")
    mountain_names = {m['name'] for m in entities['mountains']}
    for mountain in entities['mountains']:
        name = mountain['name']
        if name in MOUNTAIN_PROVINCES:
            mountain['provinces'] = [p for p in MOUNTAIN_PROVINCES[name] if p in province_names]
        else:
            mountain['provinces'] = []

    # 4. 扩展湖泊 - 添加provinces (支持跨省湖泊)
    print("正在扩展湖泊实体...")
    for lake in entities['lakes']:
        name = lake['name']
        if name in LAKE_PROVINCES:
            lake['provinces'] = [p for p in LAKE_PROVINCES[name] if p in province_names]
        else:
            # 如果没有跨省数据，使用原有province字段
            single_prov = lake.get('province', '')
            lake['provinces'] = [single_prov] if single_prov else []

    # 5. 扩展区域 - 添加provinces
    print("正在扩展区域实体...")
    for region in entities['regions']:
        name = region['name']
        if name in REGION_PROVINCES:
            region['provinces'] = [p for p in REGION_PROVINCES[name] if p in province_names]
        else:
            region['provinces'] = []

    # 更新元数据
    db['metadata']['version'] = '2.0'
    db['metadata']['last_updated'] = '2026-03-11'
    db['metadata']['extensions'] = [
        'provinces.neighbors',
        'provinces.cities',
        'provinces.contains_landmarks',
        'rivers.provinces',
        'mountains.provinces',
        'lakes.provinces',
        'regions.provinces'
    ]

    # 保存扩展后的数据
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"\n扩展完成！输出文件: {output_path}")

    # 统计扩展结果
    print("\n=== 扩展统计 ===")

    print("\n省份扩展:")
    provs_with_neighbors = sum(1 for p in entities['provinces'] if p.get('neighbors'))
    provs_with_cities = sum(1 for p in entities['provinces'] if p.get('cities'))
    provs_with_landmarks = sum(1 for p in entities['provinces'] if p.get('contains_landmarks'))
    print(f"  有相邻省份的省份: {provs_with_neighbors}/34")
    print(f"  有城市列表的省份: {provs_with_cities}/34")
    print(f"  有地标列表的省份: {provs_with_landmarks}/34")

    print("\n河流扩展:")
    rivers_with_provinces = sum(1 for r in entities['rivers'] if r.get('provinces'))
    total_river_provinces = sum(len(r.get('provinces', [])) for r in entities['rivers'])
    print(f"  有流经省份的河流: {rivers_with_provinces}/30")
    print(f"  河流-省份关系总数: {total_river_provinces}")

    print("\n山脉扩展:")
    mountains_with_provinces = sum(1 for m in entities['mountains'] if m.get('provinces'))
    total_mountain_provinces = sum(len(m.get('provinces', [])) for m in entities['mountains'])
    print(f"  有跨越省份的山脉: {mountains_with_provinces}/38")
    print(f"  山脉-省份关系总数: {total_mountain_provinces}")

    print("\n湖泊扩展:")
    lakes_multi_province = sum(1 for l in entities['lakes'] if len(l.get('provinces', [])) > 1)
    print(f"  跨省湖泊: {lakes_multi_province}/18")

    print("\n区域扩展:")
    regions_with_provinces = sum(1 for r in entities['regions'] if r.get('provinces'))
    total_region_provinces = sum(len(r.get('provinces', [])) for r in entities['regions'])
    print(f"  有包含省份的区域: {regions_with_provinces}/20")
    print(f"  区域-省份关系总数: {total_region_provinces}")

    # 计算可生成的overlap数据量
    print("\n=== 可生成的overlap数据量估算 ===")

    # 河流-省份overlap
    river_overlap = sum(len(r.get('provinces', [])) for r in entities['rivers'])
    print(f"河流流经省份: {river_overlap}条")

    # 山脉-省份overlap
    mountain_overlap = sum(len(m.get('provinces', [])) for m in entities['mountains'])
    print(f"山脉跨越省份: {mountain_overlap}条")

    # 湖泊-省份overlap
    lake_overlap = sum(len(l.get('provinces', [])) for l in entities['lakes'])
    print(f"湖泊所在省份: {lake_overlap}条")

    # 区域-省份overlap
    region_overlap = sum(len(r.get('provinces', [])) for r in entities['regions'])
    print(f"区域包含省份: {region_overlap}条")

    total_overlap = river_overlap + mountain_overlap + lake_overlap + region_overlap
    print(f"\noverlap数据总量估算: {total_overlap}条")

    return db


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="扩展实体数据库")
    parser.add_argument("--input", "-i", default="D:/30_keyan/GeoKD-SR/data/final/entity_database_expanded_fixed.json", help="输入文件路径")
    parser.add_argument("--output", "-o", default="D:/30_keyan/GeoKD-SR/data/final/entity_database_expanded_v2.json", help="输出文件路径")

    args = parser.parse_args()

    extend_entity_database(args.input, args.output)
