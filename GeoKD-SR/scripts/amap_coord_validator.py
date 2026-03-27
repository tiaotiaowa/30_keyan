#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用高德地图API验证地理实体坐标
"""

import json
import requests
import time
import math
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 高德API配置
AMAP_KEY = "6ddefdcd0a3de659a61ac13665b1800a"
AMAP_GEO_URL = "https://restapi.amap.com/v3/geocode/geo"

# 请求锁和计数器
request_lock = threading.Lock()
request_count = 0

def calculate_distance(coord1: List[float], coord2: List[float]) -> float:
    """计算两个坐标之间的球面距离（公里）"""
    if not coord1 or not coord2 or len(coord1) != 2 or len(coord2) != 2:
        return float('inf')

    lat1, lon1 = math.radians(coord1[1]), math.radians(coord1[0])
    lat2, lon2 = math.radians(coord2[1]), math.radians(coord2[0])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    r = 6371  # 地球半径（公里）
    return c * r

def query_amap_geocode(entity_name: str, max_retries: int = 3) -> Optional[Dict]:
    """调用高德API获取地理编码"""
    global request_count

    for attempt in range(max_retries):
        try:
            with request_lock:
                request_count += 1
                if request_count % 50 == 0:
                    print(f"已发送 {request_count} 个请求...")
                    time.sleep(0.5)  # 每50个请求暂停一下

            params = {
                "address": entity_name,
                "key": AMAP_KEY,
                "output": "json"
            }

            response = requests.get(AMAP_GEO_URL, params=params, timeout=10)
            result = response.json()

            if result.get("status") == "1" and result.get("geocodes"):
                geocodes = result["geocodes"]
                if geocodes and len(geocodes) > 0:
                    geo = geocodes[0]
                    location = geo.get("location", "")
                    if location:
                        lon, lat = location.split(",")
                        return {
                            "name": entity_name,
                            "amap_coords": [float(lon), float(lat)],
                            "province": geo.get("province", ""),
                            "city": geo.get("city", ""),
                            "district": geo.get("district", ""),
                            "level": geo.get("level", ""),
                            "adcode": geo.get("adcode", "")
                        }

            # 如果没有结果，等待后重试
            if attempt < max_retries - 1:
                time.sleep(0.3)

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
            else:
                print(f"查询失败 [{entity_name}]: {str(e)}")

    return None

def validate_entity(entity_name: str, recorded_coords: List[float]) -> Dict:
    """验证单个实体的坐标"""
    result = {
        "name": entity_name,
        "recorded_coords": recorded_coords,
        "amap_coords": None,
        "distance_km": None,
        "status": "unknown",
        "amap_info": None
    }

    # 调用高德API
    amap_result = query_amap_geocode(entity_name)

    if amap_result:
        result["amap_coords"] = amap_result["amap_coords"]
        result["amap_info"] = {
            "province": amap_result["province"],
            "city": amap_result["city"],
            "level": amap_result["level"]
        }

        # 计算距离
        distance = calculate_distance(recorded_coords, amap_result["amap_coords"])
        result["distance_km"] = round(distance, 2)

        # 判断状态
        if distance <= 10:  # 10公里以内认为正确
            result["status"] = "correct"
        elif distance <= 50:  # 50公里以内认为轻微偏差
            result["status"] = "minor_deviation"
        else:  # 超过50公里认为错误
            result["status"] = "incorrect"
    else:
        result["status"] = "not_found"

    return result

def validate_all_entities(input_file: str, output_file: str, max_workers: int = 5):
    """验证所有实体"""
    # 读取数据
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entities = data.get("entities", {})
    total = len(entities)
    print(f"共需验证 {total} 个实体...")

    results = {
        "total": total,
        "validated": 0,
        "correct": 0,
        "minor_deviation": 0,
        "incorrect": 0,
        "not_found": 0,
        "entities": {}
    }

    # 使用线程池并行验证
    tasks = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for name, info in entities.items():
            coords = info.get("primary_coords", [])
            if coords and len(coords) == 2:
                tasks.append(executor.submit(validate_entity, name, coords))

        # 收集结果
        for i, future in enumerate(as_completed(tasks), 1):
            try:
                result = future.result()
                entity_name = result["name"]
                results["entities"][entity_name] = result
                results["validated"] += 1

                # 统计
                status = result["status"]
                if status == "correct":
                    results["correct"] += 1
                elif status == "minor_deviation":
                    results["minor_deviation"] += 1
                elif status == "incorrect":
                    results["incorrect"] += 1
                else:
                    results["not_found"] += 1

                # 打印进度
                if i % 20 == 0:
                    print(f"进度: {i}/{total} ({i*100//total}%) - 正确:{results['correct']} 轻微偏差:{results['minor_deviation']} 错误:{results['incorrect']} 未找到:{results['not_found']}")

            except Exception as e:
                print(f"处理异常: {str(e)}")

    # 保存结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print("\n" + "="*60)
    print("验证完成!")
    print("="*60)
    print(f"总实体数: {results['total']}")
    print(f"已验证: {results['validated']}")
    print(f"正确 (≤10km): {results['correct']} ({results['correct']*100//max(results['validated'],1)}%)")
    print(f"轻微偏差 (10-50km): {results['minor_deviation']} ({results['minor_deviation']*100//max(results['validated'],1)}%)")
    print(f"错误 (>50km): {results['incorrect']} ({results['incorrect']*100//max(results['validated'],1)}%)")
    print(f"未找到: {results['not_found']}")
    print(f"\n结果已保存到: {output_file}")

    # 列出错误实体
    if results['incorrect'] > 0:
        print("\n坐标错误实体列表:")
        print("-"*60)
        for name, info in results['entities'].items():
            if info['status'] == 'incorrect':
                print(f"  {name}: 记录{info['recorded_coords']} 高德{info['amap_coords']} 偏差{info['distance_km']}km")

    return results

if __name__ == "__main__":
    input_file = r"d:\30_keyan\GeoKD-SR\data\final\entity_coordinates.json"
    output_file = r"d:\30_keyan\GeoKD-SR\data\final\amap_validation_result.json"

    validate_all_entities(input_file, output_file, max_workers=5)
