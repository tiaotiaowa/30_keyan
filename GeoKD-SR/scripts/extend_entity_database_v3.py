#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实体库扩展脚本 V3 - 全面扩展版本
扩展内容:
1. roads - 主要道路实体（高速公路、国道）
2. cities.neighbors - 城市相邻关系
3. mountains.cities - 山脉经过的城市
4. rivers.cities - 河河流经的城市
5. roads.provinces - 道路经过的省份
6. roads.cities - 道路经过的城市

作者: Claude
日期: 2026-03-11
"""

import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict


# ==================== 主要道路数据 ====================
# 包括高速公路和重要国道
ROADS_DATA = [
    # 南北向高速公路
    {"name": "京沪高速", "type": "highway", "code": "G2", "length": 1262,
     "provinces": ["北京市", "天津市", "河北省", "山东省", "江苏省", "上海市"],
     "cities": ["北京", "天津", "济南", "徐州", "南京", "上海"]},

    {"name": "京港澳高速", "type": "highway", "code": "G4", "length": 2285,
     "provinces": ["北京市", "河北省", "河南省", "湖北省", "湖南省", "广东省"],
     "cities": ["北京", "石家庄", "郑州", "武汉", "长沙", "广州"]},

    {"name": "京昆高速", "type": "highway", "code": "G5", "length": 2865,
     "provinces": ["北京市", "河北省", "山西省", "陕西省", "四川省", "云南省"],
     "cities": ["北京", "太原", "西安", "成都", "昆明"]},

    {"name": "京藏高速", "type": "highway", "code": "G6", "length": 3710,
     "provinces": ["北京市", "河北省", "内蒙古自治区", "宁夏回族自治区", "甘肃省", "青海省", "西藏自治区"],
     "cities": ["北京", "呼和浩特", "银川", "兰州", "西宁", "拉萨"]},

    {"name": "京新高速", "type": "highway", "code": "G7", "length": 2540,
     "provinces": ["北京市", "河北省", "内蒙古自治区", "甘肃省", "新疆维吾尔自治区"],
     "cities": ["北京", "呼和浩特", "乌鲁木齐"]},

    {"name": "沈海高速", "type": "highway", "code": "G15", "length": 3710,
     "provinces": ["辽宁省", "山东省", "江苏省", "上海市", "浙江省", "福建省", "广东省"],
     "cities": ["沈阳", "青岛", "上海", "杭州", "福州", "厦门", "深圳", "广州"]},

    {"name": "长深高速", "type": "highway", "code": "G25", "length": 3580,
     "provinces": ["吉林省", "辽宁省", "河北省", "天津市", "山东省", "江苏省", "浙江省", "福建省", "广东省"],
     "cities": ["长春", "沈阳", "天津", "济南", "南京", "杭州", "福州", "深圳"]},

    {"name": "大广高速", "type": "highway", "code": "G45", "length": 3550,
     "provinces": ["黑龙江省", "吉林省", "辽宁省", "河北省", "北京市", "河南省", "湖北省", "江西省", "广东省"],
     "cities": ["哈尔滨", "长春", "沈阳", "北京", "郑州", "武汉", "南昌", "广州"]},

    {"name": "二广高速", "type": "highway", "code": "G55", "length": 2685,
     "provinces": ["内蒙古自治区", "山西省", "河南省", "湖北省", "湖南省", "广东省"],
     "cities": ["呼和浩特", "太原", "洛阳", "襄阳", "长沙", "广州"]},

    {"name": "包茂高速", "type": "highway", "code": "G65", "length": 3130,
     "provinces": ["内蒙古自治区", "陕西省", "四川省", "重庆市", "湖南省", "广西壮族自治区", "广东省"],
     "cities": ["包头", "西安", "重庆", "桂林", "广州"]},

    {"name": "兰海高速", "type": "highway", "code": "G75", "length": 2570,
     "provinces": ["甘肃省", "四川省", "重庆市", "贵州省", "广西壮族自治区"],
     "cities": ["兰州", "成都", "重庆", "贵阳", "南宁"]},

    {"name": "渝昆高速", "type": "highway", "code": "G85", "length": 1238,
     "provinces": ["重庆市", "四川省", "云南省"],
     "cities": ["重庆", "成都", "昆明"]},

    # 东西向高速公路
    {"name": "青银高速", "type": "highway", "code": "G20", "length": 1520,
     "provinces": ["山东省", "河北省", "山西省", "陕西省", "宁夏回族自治区"],
     "cities": ["青岛", "济南", "石家庄", "太原", "银川"]},

    {"name": "青兰高速", "type": "highway", "code": "G22", "length": 1795,
     "provinces": ["山东省", "河北省", "山西省", "陕西省", "甘肃省", "宁夏回族自治区"],
     "cities": ["青岛", "济南", "太原", "兰州"]},

    {"name": "连霍高速", "type": "highway", "code": "G30", "length": 4395,
     "provinces": ["江苏省", "安徽省", "河南省", "陕西省", "甘肃省", "新疆维吾尔自治区"],
     "cities": ["连云港", "徐州", "郑州", "西安", "兰州", "乌鲁木齐"]},

    {"name": "宁洛高速", "type": "highway", "code": "G36", "length": 722,
     "provinces": ["江苏省", "安徽省", "河南省"],
     "cities": ["南京", "合肥", "洛阳"]},

    {"name": "沪陕高速", "type": "highway", "code": "G40", "length": 1490,
     "provinces": ["上海市", "江苏省", "安徽省", "河南省", "湖北省", "陕西省"],
     "cities": ["上海", "南京", "合肥", "武汉", "西安"]},

    {"name": "沪蓉高速", "type": "highway", "code": "G42", "length": 1960,
     "provinces": ["上海市", "江苏省", "安徽省", "湖北省", "重庆市", "四川省"],
     "cities": ["上海", "南京", "合肥", "武汉", "重庆", "成都"]},

    {"name": "沪渝高速", "type": "highway", "code": "G50", "length": 1768,
     "provinces": ["上海市", "浙江省", "安徽省", "江西省", "湖北省", "重庆市"],
     "cities": ["上海", "杭州", "合肥", "武汉", "重庆"]},

    {"name": "杭瑞高速", "type": "highway", "code": "G56", "length": 1905,
     "provinces": ["浙江省", "安徽省", "江西省", "湖北省", "湖南省", "贵州省", "云南省"],
     "cities": ["杭州", "黄山", "南昌", "长沙", "贵阳", "昆明"]},

    {"name": "福银高速", "type": "highway", "code": "G70", "length": 2485,
     "provinces": ["福建省", "江西省", "湖北省", "陕西省", "甘肃省", "宁夏回族自治区"],
     "cities": ["福州", "南昌", "武汉", "西安", "兰州", "银川"]},

    {"name": "泉南高速", "type": "highway", "code": "G72", "length": 1635,
     "provinces": ["福建省", "江西省", "湖南省", "广西壮族自治区"],
     "cities": ["泉州", "南昌", "长沙", "南宁"]},

    {"name": "厦蓉高速", "type": "highway", "code": "G76", "length": 2295,
     "provinces": ["福建省", "江西省", "湖南省", "贵州省", "四川省"],
     "cities": ["厦门", "赣州", "长沙", "贵阳", "成都"]},

    {"name": "沪昆高速", "type": "highway", "code": "G60", "length": 2370,
     "provinces": ["上海市", "浙江省", "江西省", "湖南省", "贵州省", "云南省"],
     "cities": ["上海", "杭州", "南昌", "长沙", "贵阳", "昆明"]},

    # 重要国道
    {"name": "京哈线", "type": "national_road", "code": "G102", "length": 1336,
     "provinces": ["北京市", "河北省", "辽宁省", "吉林省", "黑龙江省"],
     "cities": ["北京", "秦皇岛", "沈阳", "长春", "哈尔滨"]},

    {"name": "京广线", "type": "national_road", "code": "G107", "length": 2442,
     "provinces": ["北京市", "河北省", "河南省", "湖北省", "湖南省", "广东省"],
     "cities": ["北京", "石家庄", "郑州", "武汉", "长沙", "广州"]},

    {"name": "京昆线", "type": "national_road", "code": "G108", "length": 3356,
     "provinces": ["北京市", "河北省", "山西省", "陕西省", "四川省", "云南省"],
     "cities": ["北京", "太原", "西安", "成都", "昆明"]},

    {"name": "京拉线", "type": "national_road", "code": "G109", "length": 3850,
     "provinces": ["北京市", "河北省", "内蒙古自治区", "宁夏回族自治区", "甘肃省", "青海省", "西藏自治区"],
     "cities": ["北京", "呼和浩特", "银川", "兰州", "西宁", "拉萨"]},

    {"name": "京银线", "type": "national_road", "code": "G110", "length": 1357,
     "provinces": ["北京市", "河北省", "内蒙古自治区", "宁夏回族自治区"],
     "cities": ["北京", "呼和浩特", "银川"]},

    {"name": "连天线", "type": "national_road", "code": "G310", "length": 1613,
     "provinces": ["江苏省", "安徽省", "河南省", "陕西省", "甘肃省"],
     "cities": ["连云港", "徐州", "郑州", "西安", "兰州"]},

    {"name": "沪霍线", "type": "national_road", "code": "G312", "length": 4967,
     "provinces": ["上海市", "江苏省", "安徽省", "河南省", "陕西省", "甘肃省", "新疆维吾尔自治区"],
     "cities": ["上海", "南京", "合肥", "西安", "兰州", "乌鲁木齐"]},
]


# ==================== 省会城市相邻关系 ====================
# 主要省会城市和重要地级市的相邻关系
CITY_NEIGHBORS = {
    # 直辖市
    "北京": ["天津", "石家庄", "保定", "唐山", "张家口", "承德", "廊坊"],
    "天津": ["北京", "石家庄", "唐山", "廊坊", "沧州"],
    "上海": ["苏州", "杭州", "宁波", "嘉兴", "南通"],
    "重庆": ["成都", "贵阳", "武汉", "西安", "长沙", "昆明"],

    # 省会城市
    "石家庄": ["北京", "天津", "太原", "郑州", "济南", "保定", "邯郸", "邢台"],
    "太原": ["石家庄", "西安", "郑州", "呼和浩特", "大同", "临汾", "长治"],
    "呼和浩特": ["太原", "银川", "兰州", "大同", "包头", "鄂尔多斯"],
    "沈阳": ["长春", "大连", "北京", "鞍山", "抚顺", "锦州"],
    "长春": ["沈阳", "哈尔滨", "吉林", "四平", "通化"],
    "哈尔滨": ["长春", "齐齐哈尔", "牡丹江", "佳木斯", "大庆"],
    "南京": ["上海", "杭州", "合肥", "济南", "苏州", "无锡", "扬州"],
    "杭州": ["上海", "南京", "合肥", "南昌", "宁波", "温州", "绍兴"],
    "合肥": ["南京", "杭州", "武汉", "南昌", "郑州", "芜湖", "蚌埠"],
    "福州": ["杭州", "南昌", "厦门", "泉州", "宁德"],
    "南昌": ["杭州", "合肥", "福州", "武汉", "长沙", "九江", "赣州"],
    "济南": ["石家庄", "南京", "郑州", "合肥", "青岛", "烟台", "潍坊"],
    "郑州": ["石家庄", "太原", "济南", "合肥", "武汉", "西安", "洛阳", "开封"],
    "武汉": ["郑州", "合肥", "南昌", "长沙", "重庆", "西安", "宜昌", "襄阳"],
    "长沙": ["武汉", "南昌", "广州", "贵阳", "重庆", "株洲", "湘潭"],
    "广州": ["长沙", "南昌", "南宁", "深圳", "珠海", "东莞", "佛山"],
    "南宁": ["广州", "贵阳", "昆明", "柳州", "桂林"],
    "海口": ["三亚", "琼海", "儋州"],
    "成都": ["重庆", "贵阳", "昆明", "西安", "兰州", "绵阳", "宜宾"],
    "贵阳": ["重庆", "成都", "长沙", "昆明", "南宁", "遵义", "六盘水"],
    "昆明": ["成都", "贵阳", "南宁", "大理", "丽江", "曲靖"],
    "拉萨": ["西宁", "成都", "日喀则", "林芝"],
    "西安": ["太原", "郑州", "武汉", "重庆", "成都", "兰州", "银川", "咸阳"],
    "兰州": ["西安", "银川", "西宁", "成都", "乌鲁木齐", "天水"],
    "西宁": ["兰州", "拉萨", "乌鲁木齐", "格尔木"],
    "银川": ["太原", "西安", "兰州", "呼和浩特", "石嘴山"],
    "乌鲁木齐": ["兰州", "西宁", "克拉玛依", "吐鲁番"],

    # 重要地级市补充
    "苏州": ["上海", "南京", "杭州", "无锡", "嘉兴"],
    "无锡": ["苏州", "南京", "常州", "湖州"],
    "宁波": ["杭州", "上海", "温州", "绍兴", "舟山"],
    "厦门": ["福州", "泉州", "漳州", "龙岩"],
    "青岛": ["济南", "烟台", "潍坊", "日照"],
    "大连": ["沈阳", "丹东", "营口"],
    "深圳": ["广州", "香港", "东莞", "惠州"],
    "珠海": ["广州", "澳门", "中山", "江门"],
    "三亚": ["海口", "琼海", "万宁"],
    "大理": ["昆明", "丽江", "香格里拉"],
    "丽江": ["大理", "昆明", "香格里拉", "攀枝花"],
}


# ==================== 山脉经过城市 ====================
MOUNTAIN_CITIES = {
    "喜马拉雅山脉": ["拉萨", "日喀则", "林芝"],
    "昆仑山脉": ["格尔木", "喀什", "和田"],
    "天山山脉": ["乌鲁木齐", "伊宁", "喀什", "吐鲁番"],
    "秦岭": ["西安", "宝鸡", "汉中", "天水", "洛阳"],
    "大兴安岭": ["呼和浩特", "齐齐哈尔", "呼伦贝尔", "加格达奇"],
    "太行山脉": ["北京", "石家庄", "太原", "长治", "焦作", "安阳"],
    "武夷山脉": ["福州", "南平", "三明", "上饶", "鹰潭"],
    "南岭": ["桂林", "郴州", "韶关", "赣州", "永州"],
    "横断山脉": ["成都", "康定", "大理", "丽江", "香格里拉"],
    "长白山脉": ["长春", "延吉", "通化", "白山"],
    "祁连山脉": ["兰州", "西宁", "张掖", "酒泉", "武威"],
    "阿尔泰山脉": ["阿勒泰", "布尔津", "哈巴河"],
    "阴山山脉": ["呼和浩特", "包头", "乌兰察布", "巴彦淖尔"],
    "燕山山脉": ["北京", "承德", "张家口", "秦皇岛"],
    "大巴山脉": ["达州", "万州", "十堰", "安康", "汉中"],
    "武陵山脉": ["张家界", "湘西", "恩施", "铜仁", "怀化"],
    "雪峰山脉": ["怀化", "邵阳", "娄底", "益阳"],
    "罗霄山脉": ["井冈山", "萍乡", "宜春", "郴州"],
    "六盘山": ["固原", "平凉", "天水"],
    "贺兰山": ["银川", "石嘴山", "阿拉善盟"],
    "吕梁山脉": ["吕梁", "临汾", "忻州", "太原"],
    "大别山脉": ["信阳", "六安", "黄冈", "安庆", "麻城"],
    "井冈山": ["吉安", "赣州", "萍乡"],
    "雁荡山": ["温州", "台州", "丽水"],
    "峨眉山": ["乐山", "成都", "眉山"],
    "庐山": ["九江", "南昌", "景德镇"],
    "武当山": ["十堰", "襄阳", "安康"],
    "黄山": ["黄山市", "杭州", "景德镇", "衢州"],
    "泰山": ["泰安", "济南", "曲阜", "淄博"],
    "华山": ["渭南", "西安", "洛阳"],
    "衡山": ["衡阳", "长沙", "株洲"],
    "嵩山": ["郑州", "洛阳", "登封"],
    "恒山": ["大同", "朔州", "忻州"],
    "九华山": ["池州", "黄山", "铜陵"],
    "普陀山": ["舟山", "宁波", "杭州"],
    "五台山": ["忻州", "大同", "太原"],
    "青城山": ["成都", "都江堰", "雅安"],
    "三清山": ["上饶", "景德镇", "鹰潭"],
}


# ==================== 河河流经城市 ====================
RIVER_CITIES = {
    "长江": ["宜宾", "泸州", "重庆", "宜昌", "荆州", "岳阳", "武汉", "九江", "安庆", "芜湖", "南京", "镇江", "扬州", "上海"],
    "黄河": ["兰州", "银川", "包头", "呼和浩特", "榆林", "延安", "三门峡", "洛阳", "郑州", "开封", "济南", "东营"],
    "珠江": ["南宁", "柳州", "桂林", "梧州", "广州", "佛山", "中山", "珠海", "深圳"],
    "淮河": ["信阳", "阜阳", "淮南", "蚌埠", "淮安", "盐城"],
    "海河": ["大同", "张家口", "北京", "天津", "沧州"],
    "辽河": ["通辽", "沈阳", "盘锦", "营口"],
    "松花江": ["吉林", "长春", "哈尔滨", "佳木斯", "同江"],
    "雅鲁藏布江": ["拉萨", "日喀则", "林芝", "墨脱"],
    "澜沧江": ["西宁", "玉树", "昌都", "丽江", "大理", "西双版纳"],
    "怒江": ["昌都", "怒江", "保山", "临沧"],
    "闽江": ["三明", "南平", "福州"],
    "钱塘江": ["黄山", "杭州", "绍兴", "宁波"],
    "汉江": ["汉中", "安康", "十堰", "襄阳", "武汉"],
    "赣江": ["赣州", "吉安", "南昌", "九江"],
    "湘江": ["桂林", "永州", "衡阳", "株洲", "长沙", "岳阳"],
    "嘉陵江": ["宝鸡", "汉中", "广元", "南充", "重庆"],
    "岷江": ["松潘", "成都", "眉山", "乐山", "宜宾"],
    "大渡河": ["阿坝", "甘孜", "雅安", "乐山"],
    "塔里木河": ["阿克苏", "库车", "库尔勒", "若羌"],
    "黑龙江": ["漠河", "黑河", "哈尔滨", "佳木斯", "同江"],
}


def extend_entity_database_v3(input_path: str, output_path: str):
    """
    扩展实体数据库 V3 - 全面扩展版本
    """
    # 读取V2版本数据
    with open(input_path, 'r', encoding='utf-8') as f:
        db = json.load(f)

    entities = db['entities']

    # 获取城市和省份列表用于验证
    city_names = {c['name'] for c in entities['cities']}
    province_names = {p['name'] for p in entities['provinces']}

    # 1. 添加道路实体
    print("正在添加道路实体...")
    roads = []
    for road in ROADS_DATA:
        road_entity = {
            "name": road["name"],
            "type": road["type"],
            "code": road["code"],
            "length": road["length"],
            "provinces": [p for p in road["provinces"] if p in province_names],
            "cities": [c for c in road["cities"] if c in city_names],
            "coords": [0.0, 0.0]  # 道路没有单一坐标，设为默认值
        }
        roads.append(road_entity)

    entities["roads"] = roads
    print(f"  添加道路实体: {len(roads)}条")

    # 2. 扩展城市 - 添加neighbors
    print("正在扩展城市实体...")
    for city in entities['cities']:
        name = city['name']
        neighbors = CITY_NEIGHBORS.get(name, [])
        city['neighbors'] = [n for n in neighbors if n in city_names]

    cities_with_neighbors = sum(1 for c in entities['cities'] if c.get('neighbors'))
    print(f"  有相邻城市的城市: {cities_with_neighbors}/{len(entities['cities'])}")

    # 3. 扩展山脉 - 添加cities
    print("正在扩展山脉实体...")
    for mountain in entities['mountains']:
        name = mountain['name']
        cities = MOUNTAIN_CITIES.get(name, [])
        mountain['cities'] = [c for c in cities if c in city_names]

    mountains_with_cities = sum(1 for m in entities['mountains'] if m.get('cities'))
    total_mountain_cities = sum(len(m.get('cities', [])) for m in entities['mountains'])
    print(f"  有经过城市的山脉: {mountains_with_cities}/{len(entities['mountains'])}")
    print(f"  山脉-城市关系总数: {total_mountain_cities}")

    # 4. 扩展河流 - 添加cities
    print("正在扩展河流实体...")
    for river in entities['rivers']:
        name = river['name']
        cities = RIVER_CITIES.get(name, [])
        river['cities'] = [c for c in cities if c in city_names]

    rivers_with_cities = sum(1 for r in entities['rivers'] if r.get('cities'))
    total_river_cities = sum(len(r.get('cities', [])) for r in entities['rivers'])
    print(f"  有流经城市的河流: {rivers_with_cities}/{len(entities['rivers'])}")
    print(f"  河流-城市关系总数: {total_river_cities}")

    # 更新元数据
    db['metadata']['version'] = '3.0'
    db['metadata']['last_updated'] = '2026-03-11'
    db['metadata']['extensions'] = [
        'provinces.neighbors',
        'provinces.cities',
        'provinces.contains_landmarks',
        'rivers.provinces',
        'rivers.cities',
        'mountains.provinces',
        'mountains.cities',
        'lakes.provinces',
        'regions.provinces',
        'roads (new entity type)',
        'roads.provinces',
        'roads.cities',
        'cities.neighbors'
    ]

    # 保存扩展后的数据
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"\n扩展完成！输出文件: {output_path}")

    # 统计扩展结果
    print("\n" + "="*60)
    print("=== 扩展统计汇总 ===")
    print("="*60)

    print("\n【新增实体类型】")
    print(f"  道路实体: {len(entities['roads'])}条")

    print("\n【省份扩展】")
    provs_with_neighbors = sum(1 for p in entities['provinces'] if p.get('neighbors'))
    provs_with_cities = sum(1 for p in entities['provinces'] if p.get('cities'))
    provs_with_landmarks = sum(1 for p in entities['provinces'] if p.get('contains_landmarks'))
    print(f"  有相邻省份: {provs_with_neighbors}/34")
    print(f"  有城市列表: {provs_with_cities}/34")
    print(f"  有地标列表: {provs_with_landmarks}/34")

    print("\n【城市扩展】")
    print(f"  有相邻城市: {cities_with_neighbors}/{len(entities['cities'])}")

    print("\n【河流扩展】")
    rivers_with_provinces = sum(1 for r in entities['rivers'] if r.get('provinces'))
    total_river_provinces = sum(len(r.get('provinces', [])) for r in entities['rivers'])
    print(f"  有流经省份: {rivers_with_provinces}/30, 关系数: {total_river_provinces}")
    print(f"  有流经城市: {rivers_with_cities}/30, 关系数: {total_river_cities}")

    print("\n【山脉扩展】")
    mountains_with_provinces = sum(1 for m in entities['mountains'] if m.get('provinces'))
    total_mountain_provinces = sum(len(m.get('provinces', [])) for m in entities['mountains'])
    print(f"  有跨越省份: {mountains_with_provinces}/38, 关系数: {total_mountain_provinces}")
    print(f"  有经过城市: {mountains_with_cities}/38, 关系数: {total_mountain_cities}")

    print("\n【湖泊扩展】")
    lakes_multi_province = sum(1 for l in entities['lakes'] if len(l.get('provinces', [])) > 1)
    total_lake_provinces = sum(len(l.get('provinces', [])) for l in entities['lakes'])
    print(f"  跨省湖泊: {lakes_multi_province}/18, 关系数: {total_lake_provinces}")

    print("\n【区域扩展】")
    total_region_provinces = sum(len(r.get('provinces', [])) for r in entities['regions'])
    print(f"  区域-省份关系: {total_region_provinces}")

    print("\n【道路扩展】")
    total_road_provinces = sum(len(r.get('provinces', [])) for r in entities['roads'])
    total_road_cities = sum(len(r.get('cities', [])) for r in entities['roads'])
    print(f"  道路-省份关系: {total_road_provinces}")
    print(f"  道路-城市关系: {total_road_cities}")

    # 计算可生成的数据量
    print("\n" + "="*60)
    print("=== 可生成的overlap数据量估算 ===")
    print("="*60)

    # 河流-省份 overlap
    river_province = sum(len(r.get('provinces', [])) for r in entities['rivers'])
    print(f"\n1. 河流-省份 overlap: {river_province}条")

    # 河流-城市 overlap
    river_city = sum(len(r.get('cities', [])) for r in entities['rivers'])
    print(f"2. 河流-城市 overlap: {river_city}条")

    # 山脉-省份 overlap
    mountain_province = sum(len(m.get('provinces', [])) for m in entities['mountains'])
    print(f"3. 山脉-省份 overlap: {mountain_province}条")

    # 山脉-城市 overlap
    mountain_city = sum(len(m.get('cities', [])) for m in entities['mountains'])
    print(f"4. 山脉-城市 overlap: {mountain_city}条")

    # 湖泊-省份 overlap
    lake_province = sum(len(l.get('provinces', [])) for l in entities['lakes'])
    print(f"5. 湖泊-省份 overlap: {lake_province}条")

    # 区域-省份 overlap
    region_province = sum(len(r.get('provinces', [])) for r in entities['regions'])
    print(f"6. 区域-省份 overlap: {region_province}条")

    # 道路-省份 overlap
    road_province = sum(len(r.get('provinces', [])) for r in entities['roads'])
    print(f"7. 道路-省份 overlap: {road_province}条")

    # 道路-城市 overlap
    road_city = sum(len(r.get('cities', [])) for r in entities['roads'])
    print(f"8. 道路-城市 overlap: {road_city}条")

    total_overlap = (river_province + river_city + mountain_province + mountain_city +
                    lake_province + region_province + road_province + road_city)
    print(f"\n>>> overlap数据总量: {total_overlap}条")

    print("\n=== 可生成的contains数据量估算 ===")

    # 省份-城市 contains
    province_city = sum(len(p.get('cities', [])) for p in entities['provinces'])
    print(f"1. 省份-城市 contains: {province_city}条")

    # 省份-地标 contains
    province_landmark = sum(len(p.get('contains_landmarks', [])) for p in entities['provinces'])
    print(f"2. 省份-地标 contains: {province_landmark}条")

    total_contains = province_city + province_landmark
    print(f"\n>>> contains数据总量: {total_contains}条")

    print("\n" + "="*60)
    print(f">>> 总计可生成数据: {total_overlap + total_contains}条")
    print("="*60)

    return db


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="扩展实体数据库 V3")
    parser.add_argument("--input", "-i",
                       default="D:/30_keyan/GeoKD-SR/data/final/entity_database_expanded_v2.json",
                       help="输入文件路径(V2版本)")
    parser.add_argument("--output", "-o",
                       default="D:/30_keyan/GeoKD-SR/data/final/entity_database_expanded_v3.json",
                       help="输出文件路径(V3版本)")

    args = parser.parse_args()

    extend_entity_database_v3(args.input, args.output)
