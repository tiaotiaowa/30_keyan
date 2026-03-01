#!/usr/bin/env python3
"""
数据管理工具测试脚本
"""

import sys
import os
from pathlib import Path

# 设置UTF-8编码（仅对输出）
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.data_manager import DataManager


def test_list_data():
    """测试列出数据文件"""
    print("\n" + "="*60)
    print("测试 1: 列出数据文件")
    print("="*60)

    manager = DataManager()
    result = manager.list_data()

    if result:
        print(f"[OK] 找到 {len(result)} 个数据集")
        for dataset_name, files in result.items():
            print(f"  {dataset_name}: {len(files)} 个文件")
        return True
    else:
        print("[FAIL] 未找到数据文件")
        return False


def test_verify_jsonl():
    """测试验证JSONL文件"""
    print("\n" + "="*60)
    print("测试 2: 验证JSONL文件")
    print("="*60)

    manager = DataManager()
    result = manager.verify_data("data/geosr_chain/train.jsonl", verbose=False)

    if result['valid']:
        print(f"[OK] 验证通过")
        print(f"  总记录数: {result['total']}")
        print(f"  有效记录: {result['valid_count']}")
        print(f"  无效记录: {result['invalid_count']}")
        return True
    else:
        print(f"[FAIL] 验证失败")
        print(f"  错误: {result['errors']}")
        return False


def test_verify_json():
    """测试验证JSON文件"""
    print("\n" + "="*60)
    print("测试 3: 验证JSON文件")
    print("="*60)

    manager = DataManager()
    result = manager.verify_data("data/geosr_bench/benchmark.json", verbose=False)

    print(f"[OK] 文件已读取")
    print(f"  总记录数: {result['total']}")
    print(f"  文件格式: {result['file_type']}")
    return True


def test_statistics():
    """测试数据统计"""
    print("\n" + "="*60)
    print("测试 4: 数据统计")
    print("="*60)

    manager = DataManager()
    stats = manager.show_statistics(
        "data/geosr_chain/train.jsonl",
        output_file=None,  # 不保存文件
        visualize=False  # 不生成可视化
    )

    if stats:
        print(f"[OK] 统计完成")
        print(f"  总记录数: {stats['total_records']}")
        print(f"  空间关系类型数: {len(stats['spatial_relations'])}")
        print(f"  实体类型数: {len(stats['entity_types'])}")
        return True
    else:
        print("[FAIL] 统计失败")
        return False


def test_convert():
    """测试格式转换"""
    print("\n" + "="*60)
    print("测试 5: 格式转换")
    print("="*60)

    manager = DataManager()

    # JSONL 转 JSON
    success = manager.convert_format(
        input_path="data/geosr_chain/train.jsonl",
        output_path="data/geosr_chain/train_converted.json"
    )

    if success:
        print("[OK] JSONL -> JSON 转换成功")

        # 验证转换后的文件
        result = manager.verify_data("data/geosr_chain/train_converted.json", verbose=False)
        if result['total'] > 0:
            print(f"  转换后记录数: {result['total']}")

        # 清理测试文件
        Path("data/geosr_chain/train_converted.json").unlink(missing_ok=True)
        print("  测试文件已清理")

        return True
    else:
        print("[FAIL] 格式转换失败")
        return False


def test_config():
    """测试配置文件"""
    print("\n" + "="*60)
    print("测试 6: 配置文件")
    print("="*60)

    manager = DataManager()

    print(f"[OK] 配置文件已加载")
    print(f"  配置路径: {manager.config_path}")
    print(f"  数据目录: {manager.data_dir}")
    print(f"  缓存目录: {manager.cache_dir}")
    print(f"  统计目录: {manager.stats_dir}")

    # 检查配置内容
    if 'data' in manager.config:
        print(f"  数据集配置: {len(manager.config.get('datasets', {}))} 个")

    return True


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("GeoKD-SR 数据管理工具测试")
    print("="*60)

    tests = [
        ("列出数据文件", test_list_data),
        ("验证JSONL文件", test_verify_jsonl),
        ("验证JSON文件", test_verify_json),
        ("数据统计", test_statistics),
        ("格式转换", test_convert),
        ("配置文件", test_config),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"[ERROR] {test_name} 测试时出错: {e}")
            results.append((test_name, False))

    # 输出测试总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")

    print("\n" + "="*60)
    print(f"测试结果: {passed}/{total} 通过")
    print("="*60 + "\n")

    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
