"""
独立验证脚本 - 验证ProgressiveDataScheduler配置和功能
"""

import json
import sys
import tempfile
from pathlib import Path

# 直接导入模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.data.progressive_scheduler import (
    ProgressiveDataScheduler,
    DEFAULT_PHASES,
    PHASE_1_CONFIG,
    PHASE_2_CONFIG,
    PHASE_3_CONFIG,
)


def create_test_data(num_samples=100):
    """创建测试数据集"""
    data = []

    # 方向关系数据
    for i in range(25):
        data.append({
            "id": f"d_{i}",
            "question": f"Beijing is in which direction from Shanghai?",
            "answer": "North",
            "relation_type": "directional"
        })

    # 拓扑关系数据
    for i in range(25):
        data.append({
            "id": f"t_{i}",
            "question": f"Is Hebei adjacent to Beijing?",
            "answer": "Yes",
            "relation_type": "topological"
        })

    # 度量关系数据
    for i in range(25):
        data.append({
            "id": f"m_{i}",
            "question": f"What is the distance from Beijing to Shanghai?",
            "answer": "About 1200 km",
            "relation_type": "metric"
        })

    # 组合关系数据
    for i in range(25):
        data.append({
            "id": f"c_{i}",
            "question": f"Which provinces does the route from Beijing to Shanghai pass through?",
            "answer": "Hebei, Shandong, Jiangsu, etc.",
            "relation_type": "composite"
        })

    return data


def main():
    print("=" * 60)
    print("ProgressiveDataScheduler Configuration Verification")
    print("=" * 60)
    print()

    # 1. 验证阶段配置
    print("1. Phase Configuration Verification")
    print("-" * 60)

    print("\nEpoch 0 Config:")
    print(f"  Relations: {PHASE_1_CONFIG['relations']}")
    print(f"  Weights: {PHASE_1_CONFIG['weights']}")
    print(f"  Expected: ['directional'], [1.0]")
    assert PHASE_1_CONFIG['relations'] == ['directional']
    assert PHASE_1_CONFIG['weights'] == [1.0]
    print("  [PASS]")

    print("\nEpoch 1 Config:")
    print(f"  Relations: {PHASE_2_CONFIG['relations']}")
    print(f"  Weights: {PHASE_2_CONFIG['weights']}")
    print(f"  Expected: ['directional', 'topological'], [0.3, 1.0]")
    assert PHASE_2_CONFIG['relations'] == ['directional', 'topological']
    assert PHASE_2_CONFIG['weights'] == [0.3, 1.0]
    print("  [PASS]")

    print("\nEpoch 2 Config:")
    print(f"  Relations: {PHASE_3_CONFIG['relations']}")
    print(f"  Weights: {PHASE_3_CONFIG['weights']}")
    print(f"  Expected: ['directional', 'topological', 'metric', 'composite'], [0.2, 0.3, 0.5, 1.0]")
    assert PHASE_3_CONFIG['relations'] == ['directional', 'topological', 'metric', 'composite']
    assert PHASE_3_CONFIG['weights'] == [0.2, 0.3, 0.5, 1.0]
    print("  [PASS]")

    # 2. 创建测试数据
    print("\n2. Creating Test Data")
    print("-" * 60)
    test_data = create_test_data()
    print(f"Created {len(test_data)} test samples")

    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(test_data, temp_file, ensure_ascii=False)
    temp_file.close()

    # 3. 测试调度器
    print("\n3. Scheduler Functionality Test")
    print("-" * 60)

    scheduler = ProgressiveDataScheduler(
        data_path=temp_file.name,
        total_epochs=3,
        seed=42
    )

    # 测试Epoch 0
    print("\nEpoch 0: Should only have directional data")
    data_0 = scheduler.get_epoch_data(0, num_samples=50)
    relation_types_0 = set(item['relation_type'] for item in data_0)
    print(f"  Sampled: {len(data_0)} items")
    print(f"  Relation types: {relation_types_0}")
    assert relation_types_0 == {'directional'}
    print("  [PASS]")

    # 测试Epoch 1
    print("\nEpoch 1: Should have directional + topological data")
    data_1 = scheduler.get_epoch_data(1, num_samples=100)
    relation_types_1 = set(item['relation_type'] for item in data_1)
    print(f"  Sampled: {len(data_1)} items")
    print(f"  Relation types: {relation_types_1}")
    assert 'directional' in relation_types_1
    assert 'topological' in relation_types_1
    assert 'metric' not in relation_types_1
    assert 'composite' not in relation_types_1
    print("  [PASS]")

    # 测试Epoch 2
    print("\nEpoch 2: Should have all relation types")
    data_2 = scheduler.get_epoch_data(2, num_samples=200)
    relation_types_2 = set(item['relation_type'] for item in data_2)
    print(f"  Sampled: {len(data_2)} items")
    print(f"  Relation types: {relation_types_2}")
    assert 'directional' in relation_types_2
    assert 'topological' in relation_types_2
    assert 'metric' in relation_types_2
    assert 'composite' in relation_types_2
    print("  [PASS]")

    # 4. 测试权重分布
    print("\n4. Sampling Weight Distribution Test")
    print("-" * 60)

    weights_0 = scheduler.get_sampling_weights(0)
    print(f"Epoch 0 weights: {weights_0}")
    assert weights_0 == {'directional': 1.0}
    print("  [PASS]")

    weights_1 = scheduler.get_sampling_weights(1)
    print(f"Epoch 1 weights: {weights_1}")
    assert weights_1['directional'] == 0.3
    assert weights_1['topological'] == 1.0
    print("  [PASS]")

    weights_2 = scheduler.get_sampling_weights(2)
    print(f"Epoch 2 weights: {weights_2}")
    assert weights_2['directional'] == 0.2
    assert weights_2['topological'] == 0.3
    assert weights_2['metric'] == 0.5
    assert weights_2['composite'] == 1.0
    print("  [PASS]")

    # 5. 测试关系掩码
    print("\n5. Relation Mask Test")
    print("-" * 60)

    mask_0 = scheduler.get_relation_mask(0)
    print(f"Epoch 0 mask: {mask_0}")
    assert mask_0['directional'] == True
    assert mask_0['topological'] == False
    assert mask_0['metric'] == False
    assert mask_0['composite'] == False
    print("  [PASS]")

    mask_2 = scheduler.get_relation_mask(2)
    print(f"Epoch 2 mask: {mask_2}")
    assert mask_2['directional'] == True
    assert mask_2['topological'] == True
    assert mask_2['metric'] == True
    assert mask_2['composite'] == True
    print("  [PASS]")

    # 6. 课程调度表
    print("\n6. Curriculum Schedule Test")
    print("-" * 60)

    schedule = scheduler.get_curriculum_schedule()
    print(f"Schedule length: {len(schedule)} epochs")
    for item in schedule:
        print(f"  Epoch {item['epoch']}: {item['active_relations']}")
    assert len(schedule) == 3
    print("  [PASS]")

    # 清理
    Path(temp_file.name).unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print("All Tests Passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
