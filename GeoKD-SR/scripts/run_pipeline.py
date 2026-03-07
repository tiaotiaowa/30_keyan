#!/usr/bin/env python3
"""
GeoKD-SR 数据生成Pipeline统一入口

整合所有数据生成模块，提供一键生成完整数据集的功能。

功能:
1. 统一Pipeline入口，支持测试模式和完整生成模式
2. 集成 GLM5Client 数据生成
3. 集成 EntityTokenMapper 生成 entity_to_token 映射
4. 集成 DataQualityController 6层验证
5. 自动调用 split_dataset.py 划分数据集
6. 生成详细的执行日志和报告

使用方法:
    # 测试模式：生成100条数据验证流程
    python scripts/run_pipeline.py --test_run

    # 完整生成：生成11,800条数据
    python scripts/run_pipeline.py --full_generation

    # 自定义配置
    python scripts/run_pipeline.py --train_count 8000 --dev_count 800 --test_count 3000

作者: GeoKD-SR Team
日期: 2026-03-04
版本: V1.0
"""

import os
import sys
import io
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import Counter

# 设置标准输出为UTF-8编码（修复Windows控制台编码问题）
# 注意：仅在需要时设置，避免重复包装
if sys.platform == 'win32':
    try:
        if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        if not isinstance(sys.stderr, io.TextIOWrapper) or sys.stderr.encoding != 'utf-8':
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass  # 如果已经包装或缓冲区不可用，跳过

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入各模块
from data.entity_database import EntityDatabase


# ================================
# Pipeline配置
# ================================

class PipelineConfig:
    """Pipeline配置"""

    # 默认数据量
    DEFAULT_TRAIN_COUNT = 8000
    DEFAULT_DEV_COUNT = 800
    DEFAULT_TEST_COUNT = 3000
    TEST_RUN_COUNT = 100

    # 输出目录
    DEFAULT_OUTPUT_DIR = "data/geosr_chain"

    # 空间关系分布
    RELATION_DISTRIBUTION = {
        "directional": 0.30,   # 30%
        "topological": 0.225,  # 22.5%
        "metric": 0.225,       # 22.5%
        "composite": 0.25      # 25%
    }

    # 难度分布
    DIFFICULTY_DISTRIBUTION = {
        "easy": 0.30,
        "medium": 0.50,
        "hard": 0.20
    }


# ================================
# Pipeline执行器
# ================================

class DataPipeline:
    """
    数据生成Pipeline

    整合所有模块，提供完整的数据生成流程。
    """

    def __init__(self, config: Optional[PipelineConfig] = None, verbose: bool = True):
        """
        初始化Pipeline

        Args:
            config: Pipeline配置
            verbose: 是否输出详细日志
        """
        self.config = config or PipelineConfig()
        self.verbose = verbose
        self.start_time = None
        self.stats = {}

        # 模块实例（延迟加载）
        self._glm5_client = None
        self._entity_db = None
        self._generator = None
        self._validator = None

    @property
    def glm5_client(self):
        """延迟加载GLM5客户端"""
        if self._glm5_client is None:
            from scripts.generate_data_glm5 import GLM5Client
            self._glm5_client = GLM5Client()
        return self._glm5_client

    @property
    def entity_db(self):
        """延迟加载实体数据库"""
        if self._entity_db is None:
            self._entity_db = EntityDatabase()
        return self._entity_db

    @property
    def generator(self):
        """延迟加载数据生成器"""
        if self._generator is None:
            from scripts.generate_data_glm5 import GeoSRDataGenerator
            self._generator = GeoSRDataGenerator(
                self.glm5_client,
                self.entity_db,
                tokenizer=None  # 可选：加载tokenizer
            )
        return self._generator

    @property
    def validator(self):
        """延迟加载验证器"""
        if self._validator is None:
            from scripts.validate_data import DataValidator
            self._validator = DataValidator(strict_mode=False)
        return self._validator

    def log(self, message: str, level: str = "INFO"):
        """输出日志"""
        if self.verbose:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] [{level}] {message}")

    def check_prerequisites(self) -> bool:
        """
        检查执行前提条件

        Returns:
            是否满足所有前提条件
        """
        self.log("检查执行前提条件...")

        # 检查API密钥
        api_key = os.getenv("ZHIPUAI_API_KEY", "")
        if not api_key:
            self.log("警告: 未设置ZHIPUAI_API_KEY环境变量", "WARNING")
            self.log("请先设置: export ZHIPUAI_API_KEY=your_api_key", "WARNING")
            return False

        # 检查实体数据库
        try:
            db = self.entity_db
            entities = db.get_entities_with_coords()
            if len(entities) < 50:
                self.log(f"警告: 实体数据库只有{len(entities)}个实体，建议至少50个", "WARNING")
            else:
                self.log(f"实体数据库: {len(entities)}个实体")
        except Exception as e:
            self.log(f"错误: 无法加载实体数据库 - {e}", "ERROR")
            return False

        # 检查输出目录
        output_dir = Path(self.config.DEFAULT_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        self.log(f"输出目录: {output_dir.absolute()}")

        return True

    def run_test_mode(self) -> bool:
        """
        运行测试模式

        生成100条数据验证整个流程。

        Returns:
            是否成功
        """
        self.log("=" * 60)
        self.log("GeoKD-SR 数据生成Pipeline - 测试模式")
        self.log("=" * 60)

        self.start_time = time.time()

        # 1. 检查前提条件
        if not self.check_prerequisites():
            return False

        # 2. 生成测试数据
        self.log(f"\n[阶段1] 生成{self.config.TEST_RUN_COUNT}条测试数据...")
        try:
            records = self.generator.generate_batch(
                self.config.TEST_RUN_COUNT,
                relation_distribution=self.config.RELATION_DISTRIBUTION
            )
        except Exception as e:
            self.log(f"数据生成失败: {e}", "ERROR")
            return False

        if len(records) < 50:  # 至少成功生成50条
            self.log(f"生成数据不足: 只有{len(records)}条", "ERROR")
            return False

        self.stats['generated'] = len(records)
        self.log(f"成功生成{len(records)}条数据")

        # 3. 后处理增强
        self.log("\n[阶段2] 后处理增强...")
        records = self._post_process(records)
        self.log(f"后处理完成: {len(records)}条")

        # 4. 数据验证
        self.log("\n[阶段3] 6层数据验证...")
        validation_result = self._validate_records(records)

        if validation_result['overall_pass_rate'] < 0.8:
            self.log(f"验证通过率过低: {validation_result['overall_pass_rate']:.1%}", "WARNING")

        self.stats['validation'] = validation_result

        # 5. 保存测试数据
        self.log("\n[阶段4] 保存测试数据...")
        output_path = Path(self.config.DEFAULT_OUTPUT_DIR) / "test_run.jsonl"
        self._save_records(records, str(output_path))

        # 6. 生成报告
        self._generate_report("test")

        duration = time.time() - self.start_time
        self.log(f"\n测试模式完成！耗时: {duration:.1f}秒")
        self.log(f"生成数据: {len(records)}条")
        self.log(f"验证通过率: {validation_result['overall_pass_rate']:.1%}")

        return True

    def run_full_generation(self, train_count: int = None, dev_count: int = None,
                           test_count: int = None) -> bool:
        """
        运行完整生成模式

        Args:
            train_count: 训练集数量
            dev_count: 验证集数量
            test_count: 测试集数量

        Returns:
            是否成功
        """
        train_count = train_count or self.config.DEFAULT_TRAIN_COUNT
        dev_count = dev_count or self.config.DEFAULT_DEV_COUNT
        test_count = test_count or self.config.DEFAULT_TEST_COUNT
        total_count = train_count + dev_count + test_count

        self.log("=" * 60)
        self.log("GeoKD-SR 数据生成Pipeline - 完整生成模式")
        self.log("=" * 60)
        self.log(f"目标: 训练集{train_count} + 验证集{dev_count} + 测试集{test_count} = {total_count}条")

        self.start_time = time.time()

        # 1. 检查前提条件
        if not self.check_prerequisites():
            return False

        # 2. 生成全部数据
        self.log(f"\n[阶段1] 生成{total_count}条原始数据...")
        try:
            all_records = self.generator.generate_batch(
                total_count,
                relation_distribution=self.config.RELATION_DISTRIBUTION
            )
        except Exception as e:
            self.log(f"数据生成失败: {e}", "ERROR")
            return False

        if len(all_records) < total_count * 0.8:  # 至少80%成功率
            self.log(f"警告: 只生成了{len(all_records)}条数据（目标{total_count}）", "WARNING")

        self.stats['generated'] = len(all_records)

        # 3. 后处理增强
        self.log("\n[阶段2] 后处理增强...")
        all_records = self._post_process(all_records)

        # 4. 数据验证
        self.log("\n[阶段3] 6层数据验证...")
        validation_result = self._validate_records(all_records)
        self.stats['validation'] = validation_result

        # 过滤无效数据
        valid_records = [r for r in all_records if self._is_record_valid(r)]
        self.log(f"有效数据: {len(valid_records)}条")

        # 5. 数据划分
        self.log("\n[阶段4] 数据集划分...")
        train_records, dev_records, test_records = self._split_dataset(
            valid_records, train_count, dev_count, test_count
        )

        # 6. 保存数据集
        self.log("\n[阶段5] 保存数据集...")
        output_dir = Path(self.config.DEFAULT_OUTPUT_DIR)

        self._save_records(train_records, str(output_dir / "train.jsonl"))
        self._save_records(dev_records, str(output_dir / "dev.jsonl"))
        self._save_records(test_records, str(output_dir / "test.jsonl"))

        # 7. 生成报告
        self._generate_report("full", {
            'train': len(train_records),
            'dev': len(dev_records),
            'test': len(test_records)
        })

        duration = time.time() - self.start_time
        self.log(f"\n完整生成完成！总耗时: {duration:.1f}秒")
        self.log(f"训练集: {len(train_records)}条")
        self.log(f"验证集: {len(dev_records)}条")
        self.log(f"测试集: {len(test_records)}条")

        return True

    def _post_process(self, records: List[Dict]) -> List[Dict]:
        """
        后处理增强数据

        Args:
            records: 原始数据列表

        Returns:
            增强后的数据列表
        """
        from scripts.generate_data_glm5 import (
            calculate_difficulty_score,
            add_entity_to_token_mapping
        )

        enhanced = []
        for idx, record in enumerate(records):
            try:
                # 确保spatial_relation_type字段
                if 'spatial_relation_type' not in record:
                    record['spatial_relation_type'] = self._infer_relation_type(record)

                # 确保difficulty字段
                if 'difficulty' not in record:
                    record['difficulty'] = self._infer_difficulty(record)

                # 添加difficulty_score
                if 'difficulty_score' not in record:
                    record['difficulty_score'] = calculate_difficulty_score(record)

                # 确保spatial_tokens
                if 'spatial_tokens' not in record or not record['spatial_tokens']:
                    record['spatial_tokens'] = self._extract_spatial_tokens(record)

                # 添加entity_to_token映射
                if 'entity_to_token' not in record:
                    record = add_entity_to_token_mapping(record, None)

                # 确保reasoning_chain是5步结构
                if 'reasoning_chain' in record:
                    record['reasoning_chain'] = self._normalize_reasoning_chain(
                        record['reasoning_chain']
                    )

                # 确保entities包含coords而非geometry
                if 'entities' in record:
                    record['entities'] = self._normalize_entities(record['entities'])

                enhanced.append(record)

                if (idx + 1) % 100 == 0:
                    self.log(f"  后处理进度: {idx + 1}/{len(records)}")

            except Exception as e:
                self.log(f"  跳过记录{idx}: {e}", "WARNING")
                continue

        return enhanced

    def _validate_records(self, records: List[Dict]) -> Dict:
        """
        验证数据记录

        Args:
            records: 数据列表

        Returns:
            验证结果
        """
        # 临时保存以使用验证器
        temp_path = Path(self.config.DEFAULT_OUTPUT_DIR) / "_temp_validation.jsonl"
        self._save_records(records, str(temp_path))

        try:
            result = self.validator.validate_file(
                str(temp_path),
                check_duplicates=True,
                similarity_threshold=0.9
            )

            # 打印各层验证结果
            for level_name, level_result in result.levels.items():
                self.log(f"  {level_name} {level_result.name}: "
                        f"{level_result.pass_rate:.1%} 通过")

            return result.to_dict()

        finally:
            # 清理临时文件
            if temp_path.exists():
                temp_path.unlink()

    def _split_dataset(self, records: List[Dict], train_count: int,
                       dev_count: int, test_count: int) -> tuple:
        """
        划分数据集

        Args:
            records: 数据列表
            train_count: 训练集目标数量
            dev_count: 验证集目标数量
            test_count: 测试集目标数量

        Returns:
            (train_records, dev_records, test_records)
        """
        from scripts.split_dataset import DatasetSplitter

        splitter = DatasetSplitter(seed=42)
        train_records, dev_records, test_records = splitter.stratified_split(
            records,
            train_size=train_count,
            dev_size=dev_count,
            test_size=test_count
        )

        return train_records, dev_records, test_records

    def _save_records(self, records: List[Dict], output_path: str):
        """
        保存数据记录

        Args:
            records: 数据列表
            output_path: 输出路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        self.log(f"已保存: {output_path} ({len(records)}条)")

    def _generate_report(self, mode: str, extra_stats: Dict = None):
        """生成执行报告"""
        output_dir = Path(self.config.DEFAULT_OUTPUT_DIR)
        report_path = output_dir / f"pipeline_report_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report = {
            'mode': mode,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'duration_seconds': time.time() - self.start_time if self.start_time else 0,
            'stats': self.stats,
            'config': {
                'relation_distribution': self.config.RELATION_DISTRIBUTION,
                'difficulty_distribution': self.config.DIFFICULTY_DISTRIBUTION
            }
        }

        if extra_stats:
            report['extra_stats'] = extra_stats

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.log(f"报告已保存: {report_path}")

    def _infer_relation_type(self, record: Dict) -> str:
        """推断空间关系类型"""
        question = record.get('question', '').lower()
        answer = record.get('answer', '').lower()
        text = f"{question} {answer}"

        # 度量关键词（优先级最高，避免与方向词冲突）
        metric_keywords = ['距离', '公里', '千米', '米', '远', '近', '多远', '相距']
        if any(kw in text for kw in metric_keywords):
            return 'metric'

        # 拓扑关键词
        topo_keywords = ['包含', '位于', '在内', '之中', '相交', '相邻', '交界', '接壤', '之内']
        if any(kw in text for kw in topo_keywords):
            return 'topological'

        # 方向关键词（需要完整词匹配，避免部分匹配）
        direction_keywords = ['方向', '方位', '哪个方向', '什么方向', '朝向', '指向']
        direction_words = ['东北', '西北', '东南', '西南', '东面', '西面', '南面', '北面']
        if any(kw in text for kw in direction_keywords) or any(kw in text for kw in direction_words):
            return 'directional'

        # 默认复合
        return 'composite'

    def _infer_difficulty(self, record: Dict) -> str:
        """推断难度级别"""
        entities = record.get('entities', [])
        entity_count = len(entities) if isinstance(entities, list) else 0

        question = record.get('question', '')
        answer = record.get('answer', '')
        total_length = len(question) + len(answer)

        if entity_count >= 3 or total_length > 300:
            return 'hard'
        elif entity_count == 2 and total_length > 150:
            return 'medium'
        return 'easy'

    def _extract_spatial_tokens(self, record: Dict) -> List[str]:
        """提取空间关键词"""
        tokens = set()

        # 从实体名称提取
        entities = record.get('entities', [])
        for entity in entities:
            if isinstance(entity, dict) and 'name' in entity:
                tokens.add(entity['name'])

        # 从问题和答案提取关键词
        text = record.get('question', '') + ' ' + record.get('answer', '')
        spatial_keywords = [
            '方向', '东', '西', '南', '北', '东北', '西北', '东南', '西南',
            '距离', '公里', '千米', '米', '远', '近',
            '包含', '位于', '内', '相交', '相邻'
        ]

        for kw in spatial_keywords:
            if kw in text:
                tokens.add(kw)

        return list(tokens)[:8]  # 最多8个关键词

    def _normalize_reasoning_chain(self, chain: List) -> List[Dict]:
        """标准化推理链为5步结构"""
        if not chain:
            return []

        # 如果已经是5步字典结构
        if len(chain) == 5 and all(isinstance(s, dict) for s in chain):
            return chain

        # 如果是字符串列表，转换为5步结构
        step_names = [
            ("entity_identification", "extract_entities"),
            ("spatial_relation_extraction", "classify_relation"),
            ("coordinate_retrieval", "infer_entity_to_token"),
            ("spatial_calculation", "calculate"),
            ("answer_generation", "generate_answer")
        ]

        normalized = []
        for idx, content in enumerate(chain[:5]):
            if isinstance(content, str):
                step = {
                    "step": idx + 1,
                    "name": step_names[idx][0] if idx < len(step_names) else f"step_{idx+1}",
                    "action": step_names[idx][1] if idx < len(step_names) else "unknown",
                    "content": content
                }
            else:
                step = content
            normalized.append(step)

        # 如果不足5步，补充
        while len(normalized) < 5:
            idx = len(normalized)
            normalized.append({
                "step": idx + 1,
                "name": step_names[idx][0] if idx < len(step_names) else f"step_{idx+1}",
                "action": step_names[idx][1] if idx < len(step_names) else "unknown",
                "content": "待补充"
            })

        return normalized

    def _normalize_entities(self, entities: List) -> List[Dict]:
        """标准化实体格式，确保包含coords"""
        normalized = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue

            norm_entity = {
                "name": entity.get("name", ""),
                "type": entity.get("type", "unknown")
            }

            # 提取坐标
            if "coords" in entity:
                norm_entity["coords"] = entity["coords"]
            elif "coordinates" in entity:
                coords = entity["coordinates"]
                if isinstance(coords, list) and len(coords) >= 2:
                    norm_entity["coords"] = [coords[0], coords[1]]
            elif "geometry" in entity:
                geom = entity["geometry"]
                if isinstance(geom, dict) and "coordinates" in geom:
                    coords = geom["coordinates"]
                    if isinstance(coords, list):
                        if isinstance(coords[0], list):  # Point or LineString
                            norm_entity["coords"] = coords[0] if coords else [0, 0]
                        else:
                            norm_entity["coords"] = coords
            else:
                norm_entity["coords"] = [0, 0]  # 默认坐标

            normalized.append(norm_entity)

        return normalized

    def _is_record_valid(self, record: Dict) -> bool:
        """检查记录是否有效"""
        required = ['id', 'question', 'answer', 'spatial_relation_type']
        return all(k in record for k in required)


# ================================
# 命令行接口
# ================================

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='GeoKD-SR 数据生成Pipeline统一入口',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试模式：生成100条数据验证流程
  python scripts/run_pipeline.py --test_run

  # 完整生成：生成11,800条数据
  python scripts/run_pipeline.py --full_generation

  # 自定义数量
  python scripts/run_pipeline.py --full_generation --train_count 1000 --dev_count 100 --test_count 300

  # 静默模式
  python scripts/run_pipeline.py --test_run --quiet
        """
    )

    # 模式选择
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--test_run',
        action='store_true',
        help='测试模式：生成100条数据验证流程'
    )
    mode_group.add_argument(
        '--full_generation',
        action='store_true',
        help='完整生成模式：生成完整数据集'
    )

    # 数量配置
    parser.add_argument(
        '--train_count',
        type=int,
        default=PipelineConfig.DEFAULT_TRAIN_COUNT,
        help=f'训练集数量（默认{PipelineConfig.DEFAULT_TRAIN_COUNT}）'
    )
    parser.add_argument(
        '--dev_count',
        type=int,
        default=PipelineConfig.DEFAULT_DEV_COUNT,
        help=f'验证集数量（默认{PipelineConfig.DEFAULT_DEV_COUNT}）'
    )
    parser.add_argument(
        '--test_count',
        type=int,
        default=PipelineConfig.DEFAULT_TEST_COUNT,
        help=f'测试集数量（默认{PipelineConfig.DEFAULT_TEST_COUNT}）'
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        default=PipelineConfig.DEFAULT_OUTPUT_DIR,
        help=f'输出目录（默认{PipelineConfig.DEFAULT_OUTPUT_DIR}）'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='静默模式，减少输出'
    )

    args = parser.parse_args()

    # 创建配置
    config = PipelineConfig()
    config.DEFAULT_OUTPUT_DIR = args.output_dir

    # 创建Pipeline
    pipeline = DataPipeline(config=config, verbose=not args.quiet)

    # 执行
    if args.test_run:
        success = pipeline.run_test_mode()
    else:
        success = pipeline.run_full_generation(
            train_count=args.train_count,
            dev_count=args.dev_count,
            test_count=args.test_count
        )

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
