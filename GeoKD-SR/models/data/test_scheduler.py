"""
渐进式数据调度器测试

测试ProgressiveDataScheduler的各项功能。
"""

import json
import tempfile
from pathlib import Path

import pytest

from models.data import (
    ProgressiveDataScheduler,
    AdaptiveProgressiveScheduler,
    RelationSampler,
    DEFAULT_PHASES,
    RELATION_TYPES,
)


# 创建测试数据
def create_test_data(num_samples=100):
    """创建测试数据集"""
    data = []

    # 方向关系数据
    for i in range(25):
        data.append({
            "id": f"d_{i}",
            "question": f"北京在上海的什么方向？",
            "answer": "北方",
            "relation_type": "directional"
        })

    # 拓扑关系数据
    for i in range(25):
        data.append({
            "id": f"t_{i}",
            "question": f"河北与北京相邻吗？",
            "answer": "是的",
            "relation_type": "topological"
        })

    # 度量关系数据
    for i in range(25):
        data.append({
            "id": f"m_{i}",
            "question": f"北京到上海的距离大约是多少？",
            "answer": "约1200公里",
            "relation_type": "metric"
        })

    # 组合关系数据
    for i in range(25):
        data.append({
            "id": f"c_{i}",
            "question": f"从北京到上海经过哪些省份？",
            "answer": "河北、山东、江苏等",
            "relation_type": "composite"
        })

    return data


class TestProgressiveDataScheduler:
    """测试渐进式数据调度器"""

    def setup_method(self):
        """设置测试环境"""
        # 创建临时测试数据文件
        self.test_data = create_test_data()
        self.temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            encoding='utf-8'
        )
        json.dump(self.test_data, self.temp_file, ensure_ascii=False)
        self.temp_file.close()

        self.data_path = self.temp_file.name

    def teardown_method(self):
        """清理测试环境"""
        Path(self.data_path).unlink(missing_ok=True)

    def test_init(self):
        """测试初始化"""
        scheduler = ProgressiveDataScheduler(
            data_path=self.data_path,
            total_epochs=3,
            seed=42
        )

        assert scheduler.total_epochs == 3
        assert scheduler.seed == 42
        assert len(scheduler.phases) == 3

    def test_load_data(self):
        """测试数据加载"""
        scheduler = ProgressiveDataScheduler(data_path=self.data_path)

        data = scheduler.load_data()

        assert len(data) == 100
        assert data[0]['id'] == 'd_0'

    def test_group_by_relation(self):
        """测试按关系分组"""
        scheduler = ProgressiveDataScheduler(data_path=self.data_path)

        grouped = scheduler.group_by_relation()

        assert len(grouped['directional']) == 25
        assert len(grouped['topological']) == 25
        assert len(grouped['metric']) == 25
        assert len(grouped['composite']) == 25

    def test_get_phase_config(self):
        """测试获取阶段配置"""
        scheduler = ProgressiveDataScheduler(data_path=self.data_path)

        # Epoch 0
        config_0 = scheduler.get_phase_config(0)
        assert config_0['relations'] == ['directional']
        assert config_0['weights'] == [1.0]

        # Epoch 1
        config_1 = scheduler.get_phase_config(1)
        assert 'directional' in config_1['relations']
        assert 'topological' in config_1['relations']

        # Epoch 2
        config_2 = scheduler.get_phase_config(2)
        assert len(config_2['relations']) == 4

    def test_get_relation_mask(self):
        """测试获取关系掩码"""
        scheduler = ProgressiveDataScheduler(data_path=self.data_path)

        # Epoch 0: 只有directional
        mask_0 = scheduler.get_relation_mask(0)
        assert mask_0['directional'] == True
        assert mask_0['topological'] == False
        assert mask_0['metric'] == False
        assert mask_0['composite'] == False

        # Epoch 2: 全部激活
        mask_2 = scheduler.get_relation_mask(2)
        assert mask_2['directional'] == True
        assert mask_2['topological'] == True
        assert mask_2['metric'] == True
        assert mask_2['composite'] == True

    def test_get_sampling_weights(self):
        """测试获取采样权重"""
        scheduler = ProgressiveDataScheduler(data_path=self.data_path)

        weights_0 = scheduler.get_sampling_weights(0)
        assert weights_0 == {'directional': 1.0}

        weights_1 = scheduler.get_sampling_weights(1)
        assert 'directional' in weights_1
        assert 'topological' in weights_1
        assert weights_1['directional'] == 0.3
        assert weights_1['topological'] == 1.0

    def test_get_epoch_data(self):
        """测试获取epoch数据"""
        scheduler = ProgressiveDataScheduler(data_path=self.data_path)

        # Epoch 0: 只有方向关系
        data_0 = scheduler.get_epoch_data(0, num_samples=50)
        assert len(data_0) == 50
        # 所有数据应该是directional类型
        for item in data_0:
            assert item['relation_type'] == 'directional'

        # Epoch 2: 全部关系类型
        data_2 = scheduler.get_epoch_data(2, num_samples=100)
        assert len(data_2) == 100
        # 应该包含所有关系类型
        relation_types = set(item['relation_type'] for item in data_2)
        assert 'directional' in relation_types
        assert 'topological' in relation_types
        assert 'metric' in relation_types
        assert 'composite' in relation_types

    def test_get_phase_name(self):
        """测试获取阶段名称"""
        scheduler = ProgressiveDataScheduler(data_path=self.data_path)

        name_0 = scheduler.get_phase_name(0)
        assert 'Phase 1' in name_0 or '方向' in name_0

    def test_get_curriculum_schedule(self):
        """测试获取课程调度表"""
        scheduler = ProgressiveDataScheduler(data_path=self.data_path)

        schedule = scheduler.get_curriculum_schedule()

        assert len(schedule) == 3
        assert schedule[0]['epoch'] == 0
        assert schedule[1]['epoch'] == 1
        assert schedule[2]['epoch'] == 2

    def test_custom_phases(self):
        """测试自定义阶段配置"""
        custom_phases = {
            0: {
                'relations': ['metric'],
                'weights': [1.0],
                'description': '从度量关系开始'
            },
            1: {
                'relations': ['metric', 'directional'],
                'weights': [0.5, 1.0],
                'description': '加入方向关系'
            }
        }

        scheduler = ProgressiveDataScheduler(
            data_path=self.data_path,
            phases=custom_phases,
            total_epochs=2
        )

        config = scheduler.get_phase_config(0)
        assert config['relations'] == ['metric']

    def test_stats(self):
        """测试统计信息"""
        scheduler = ProgressiveDataScheduler(data_path=self.data_path)

        # 执行一些操作
        scheduler.get_epoch_data(0, num_samples=30)
        scheduler.get_epoch_data(1, num_samples=50)

        stats = scheduler.get_stats()

        assert stats['total_samples'] == 100
        assert stats['relation_distribution']['directional'] == 25
        assert 'phase_stats' in stats


class TestRelationSampler:
    """测试关系采样器"""

    def test_init(self):
        """测试初始化"""
        sampler = RelationSampler(
            relation_weights={'directional': 1.0, 'topological': 1.0},
            seed=42
        )

        assert len(sampler.relations) == 2

    def test_sample_relation(self):
        """测试采样关系类型"""
        sampler = RelationSampler(
            relation_weights={'directional': 0.7, 'topological': 0.3},
            seed=42
        )

        # 采样多次检查分布
        samples = [sampler.sample_relation() for _ in range(100)]
        directional_count = sum(1 for s in samples if s == 'directional')

        # directional应该占多数（约70%）
        assert directional_count > 50

    def test_get_distribution(self):
        """测试获取分布"""
        sampler = RelationSampler(
            relation_weights={'a': 0.5, 'b': 0.5}
        )

        dist = sampler.get_distribution()

        assert abs(dist['a'] - 0.5) < 0.01
        assert abs(dist['b'] - 0.5) < 0.01


class TestAdaptiveProgressiveScheduler:
    """测试自适应渐进式调度器"""

    def setup_method(self):
        """设置测试环境"""
        self.test_data = create_test_data()
        self.temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            encoding='utf-8'
        )
        json.dump(self.test_data, self.temp_file, ensure_ascii=False)
        self.temp_file.close()
        self.data_path = self.temp_file.name

    def teardown_method(self):
        """清理测试环境"""
        Path(self.data_path).unlink(missing_ok=True)

    def test_init(self):
        """测试初始化"""
        scheduler = AdaptiveProgressiveScheduler(
            data_path=self.data_path,
            performance_threshold=0.8,
            min_samples_per_relation=50
        )

        assert scheduler.performance_threshold == 0.8
        assert scheduler.min_samples_per_relation == 50

    def test_update_performance(self):
        """测试更新性能"""
        scheduler = AdaptiveProgressiveScheduler(data_path=self.data_path)

        scheduler.update_performance('directional', 0.9, 100)
        scheduler.update_performance('directional', 0.8, 100)

        perf = scheduler.relation_performance['directional']
        assert abs(perf['accuracy'] - 0.85) < 0.01  # 平均值
        assert perf['sample_count'] == 200

    def test_should_advance_phase(self):
        """测试判断是否应该进入下一阶段"""
        scheduler = AdaptiveProgressiveScheduler(
            data_path=self.data_path,
            performance_threshold=0.85,
            min_samples_per_relation=100
        )

        # 初始状态不应该进入下一阶段
        assert scheduler.should_advance_phase() == False

        # 更新性能达到阈值
        scheduler.update_performance('directional', 0.9, 150)

        # 现在应该可以进入下一阶段
        assert scheduler.should_advance_phase() == True

    def test_advance_phase(self):
        """测试进入下一阶段"""
        scheduler = AdaptiveProgressiveScheduler(
            data_path=self.data_path,
            performance_threshold=0.85,
            min_samples_per_relation=100
        )

        initial_phase = scheduler.current_phase

        # 更新性能
        scheduler.update_performance('directional', 0.9, 150)

        # 尝试进入下一阶段
        result = scheduler.advance_phase()

        assert result == True
        assert scheduler.current_phase == initial_phase + 1


if __name__ == "__main__":
    # 直接运行测试
    test = TestProgressiveDataScheduler()
    test.setup_method()

    print("运行ProgressiveDataScheduler测试...")

    try:
        test.test_init()
        print("  ✓ test_init 通过")

        test.test_load_data()
        print("  ✓ test_load_data 通过")

        test.test_group_by_relation()
        print("  ✓ test_group_by_relation 通过")

        test.test_get_phase_config()
        print("  ✓ test_get_phase_config 通过")

        test.test_get_relation_mask()
        print("  ✓ test_get_relation_mask 通过")

        test.test_get_sampling_weights()
        print("  ✓ test_get_sampling_weights 通过")

        test.test_get_epoch_data()
        print("  ✓ test_get_epoch_data 通过")

        test.test_get_phase_name()
        print("  ✓ test_get_phase_name 通过")

        test.test_get_curriculum_schedule()
        print("  ✓ test_get_curriculum_schedule 通过")

        test.test_custom_phases()
        print("  ✓ test_custom_phases 通过")

        test.test_stats()
        print("  ✓ test_stats 通过")

    finally:
        test.teardown_method()

    # 测试RelationSampler
    print("\n运行RelationSampler测试...")
    test_sampler = TestRelationSampler()

    test_sampler.test_init()
    print("  ✓ test_init 通过")

    test_sampler.test_sample_relation()
    print("  ✓ test_sample_relation 通过")

    test_sampler.test_get_distribution()
    print("  ✓ test_get_distribution 通过")

    # 测试AdaptiveProgressiveScheduler
    print("\n运行AdaptiveProgressiveScheduler测试...")
    test_adaptive = TestAdaptiveProgressiveScheduler()
    test_adaptive.setup_method()

    try:
        test_adaptive.test_init()
        print("  ✓ test_init 通过")

        test_adaptive.test_update_performance()
        print("  ✓ test_update_performance 通过")

        test_adaptive.test_should_advance_phase()
        print("  ✓ test_should_advance_phase 通过")

        test_adaptive.test_advance_phase()
        print("  ✓ test_advance_phase 通过")

    finally:
        test_adaptive.teardown_method()

    print("\n" + "=" * 50)
    print("所有测试通过!")
    print("=" * 50)
