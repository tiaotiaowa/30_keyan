"""
渐进式数据调度器使用示例

演示如何使用ProgressiveDataScheduler进行训练。
"""

import json
from pathlib import Path

from models.data import (
    ProgressiveDataScheduler,
    AdaptiveProgressiveScheduler,
    create_scheduler_from_json,
)


def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("示例1: 基本使用")
    print("=" * 60)

    # 假设有一个数据文件
    data_path = "data/train.json"

    # 创建调度器
    scheduler = ProgressiveDataScheduler(
        data_path=data_path,
        total_epochs=3,
        seed=42
    )

    # 获取每个epoch的数据
    for epoch in range(3):
        print(f"\n--- Epoch {epoch} ---")
        print(f"阶段: {scheduler.get_phase_name(epoch)}")

        # 获取关系掩码
        mask = scheduler.get_relation_mask(epoch)
        print(f"激活的关系: {[k for k, v in mask.items() if v]}")

        # 获取采样权重
        weights = scheduler.get_sampling_weights(epoch)
        print(f"采样权重: {weights}")

        # 获取训练数据
        epoch_data = scheduler.get_epoch_data(epoch, num_samples=100)
        print(f"采样数据量: {len(epoch_data)}")


def example_custom_phases():
    """自定义阶段配置示例"""
    print("\n" + "=" * 60)
    print("示例2: 自定义阶段配置")
    print("=" * 60)

    # 定义5个阶段的配置
    custom_phases = {
        0: {
            'relations': ['directional'],
            'weights': [1.0],
            'description': '阶段1: 仅方向关系'
        },
        1: {
            'relations': ['directional', 'topological'],
            'weights': [0.4, 1.0],
            'description': '阶段2: 方向 + 拓扑'
        },
        2: {
            'relations': ['directional', 'topological', 'metric'],
            'weights': [0.2, 0.4, 1.0],
            'description': '阶段3: 加入度量关系'
        },
        3: {
            'relations': ['directional', 'topological', 'metric', 'composite'],
            'weights': [0.1, 0.2, 0.4, 1.0],
            'description': '阶段4: 全部关系，组合关系权重最高'
        },
        4: {
            'relations': ['directional', 'topological', 'metric', 'composite'],
            'weights': [0.15, 0.25, 0.3, 0.3],
            'description': '阶段5: 均衡分布'
        }
    }

    scheduler = ProgressiveDataScheduler(
        data_path="data/train.json",
        phases=custom_phases,
        total_epochs=5
    )

    # 打印调度表
    schedule = scheduler.get_curriculum_schedule()
    for item in schedule:
        print(f"\nEpoch {item['epoch']}: {item['phase_name']}")
        print(f"  激活关系: {item['active_relations']}")
        print(f"  采样权重: {item['sampling_weights']}")


def example_adaptive_scheduler():
    """自适应调度器示例"""
    print("\n" + "=" * 60)
    print("示例3: 自适应调度器")
    print("=" * 60)

    scheduler = AdaptiveProgressiveScheduler(
        data_path="data/train.json",
        performance_threshold=0.85,  # 准确率达到85%才进入下一阶段
        min_samples_per_relation=100
    )

    # 模拟训练过程
    print(f"初始阶段: {scheduler.current_phase}")

    # 更新性能
    scheduler.update_performance('directional', 0.90, 150)
    scheduler.update_performance('directional', 0.92, 150)

    # 检查是否可以进入下一阶段
    if scheduler.should_advance_phase():
        print("满足条件，可以进入下一阶段")
        scheduler.advance_phase()
        print(f"当前阶段: {scheduler.current_phase}")
    else:
        print("尚未满足条件，继续当前阶段")


def example_training_loop():
    """训练循环示例"""
    print("\n" + "=" * 60)
    print("示例4: 训练循环")
    print("=" * 60)

    scheduler = ProgressiveDataScheduler(
        data_path="data/train.json",
        total_epochs=3
    )

    # 模拟训练循环
    for epoch in range(3):
        print(f"\n=== 训练 Epoch {epoch} ===")

        # 获取当前epoch的数据
        train_data = scheduler.get_epoch_data(
            current_epoch=epoch,
            num_samples=500,
            replace=True  # 允许重复采样以获取足够数据
        )

        print(f"训练数据量: {len(train_data)}")

        # 获取数据加载器
        dataloader = scheduler.get_data_loader(
            current_epoch=epoch,
            batch_size=8
        )

        print(f"批次数: {len(dataloader)}")

        # 模拟训练
        # for batch_idx, batch in enumerate(dataloader):
        #     # 训练逻辑
        #     pass


def example_config_file():
    """从配置文件创建示例"""
    print("\n" + "=" * 60)
    print("示例5: 从配置文件创建")
    print("=" * 60)

    # 创建示例配置
    config = {
        "data_path": "data/train.json",
        "total_epochs": 3,
        "seed": 42,
        "shuffle": True,
        "cache_data": True,
        "phases": {
            "0": {
                "relations": ["directional"],
                "weights": [1.0],
                "description": "Phase 1: 方向关系"
            },
            "1": {
                "relations": ["directional", "topological"],
                "weights": [0.3, 1.0],
                "description": "Phase 2: 方向 + 拓扑"
            },
            "2": {
                "relations": ["directional", "topological", "metric", "composite"],
                "weights": [0.2, 0.3, 0.5, 1.0],
                "description": "Phase 3: 全部关系"
            }
        }
    }

    # 保存配置
    config_path = "configs/scheduler_config.json"
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"配置已保存到: {config_path}")

    # 从配置创建调度器
    # scheduler = create_scheduler_from_json(config_path)


def example_statistics():
    """统计信息示例"""
    print("\n" + "=" * 60)
    print("示例6: 统计信息")
    print("=" * 60)

    scheduler = ProgressiveDataScheduler(
        data_path="data/train.json",
        total_epochs=3
    )

    # 获取统计信息
    stats = scheduler.get_stats()

    print("数据统计:")
    print(f"  总样本数: {stats['total_samples']}")
    print(f"  关系分布: {stats['relation_distribution']}")

    # 保存统计信息
    # scheduler.save_stats("outputs/scheduler_stats.json")


def example_visualization():
    """可视化示例"""
    print("\n" + "=" * 60)
    print("示例7: 可视化调度表")
    print("=" * 60)

    scheduler = ProgressiveDataScheduler(
        data_path="data/train.json",
        total_epochs=3
    )

    # 可视化（需要matplotlib）
    try:
        scheduler.visualize_schedule(save_path="outputs/schedule_plot.png")
        print("调度表已保存到: outputs/schedule_plot.png")
    except Exception as e:
        print(f"可视化失败: {e}")


if __name__ == "__main__":
    # 运行示例
    example_basic_usage()
    example_custom_phases()
    example_adaptive_scheduler()
    example_training_loop()
    example_config_file()
    example_statistics()
    example_visualization()

    print("\n" + "=" * 60)
    print("所有示例运行完成")
    print("=" * 60)
