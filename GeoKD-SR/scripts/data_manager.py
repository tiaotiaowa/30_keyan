#!/usr/bin/env python3
"""
GeoKD-SR 数据管理工具

提供数据验证、统计、格式转换等功能
"""

import os
import sys
import json
import argparse
import io
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter, defaultdict
from datetime import datetime
import yaml

# 设置标准输出为UTF-8编码（修复Windows控制台编码问题）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class DataManager:
    """数据管理器 - 提供完整的数据管理功能"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化数据管理器

        Args:
            config_path: 配置文件路径，默认为 configs/data.yaml
        """
        if config_path is None:
            config_path = project_root / "configs" / "data.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.data_dir = Path(self.config.get('data', {}).get('base_dir', 'data'))
        self.cache_dir = Path(self.config.get('cache', {}).get('cache_dir', '.cache/data_manager'))
        self.stats_dir = Path(self.config.get('statistics', {}).get('output_dir', 'outputs/statistics'))

        # 创建必要目录
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict:
        """加载配置文件"""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}

    def list_data(self) -> Dict[str, List[str]]:
        """
        列出所有数据文件

        Returns:
            数据文件字典，按目录分组
        """
        result = {}

        if not self.data_dir.exists():
            return result

        for dataset_dir in self.data_dir.iterdir():
            if dataset_dir.is_dir():
                files = []
                for data_file in dataset_dir.iterdir():
                    if data_file.is_file() and data_file.suffix in ['.json', '.jsonl']:
                        files.append(str(data_file))
                result[dataset_dir.name] = files

        return result

    def verify_data(self, data_path: str, verbose: bool = True) -> Dict[str, Any]:
        """
        验证数据文件

        Args:
            data_path: 数据文件路径
            verbose: 是否显示详细信息

        Returns:
            验证结果字典
        """
        data_path = Path(data_path)

        if not data_path.exists():
            return {
                'valid': False,
                'error': f'文件不存在: {data_path}',
                'total': 0,
                'valid_count': 0,
                'invalid_count': 0
            }

        result = {
            'valid': True,
            'file_path': str(data_path),
            'file_type': data_path.suffix,
            'total': 0,
            'valid_count': 0,
            'invalid_count': 0,
            'errors': [],
            'warnings': []
        }

        # 获取验证规则
        required_fields = self.config.get('validation', {}).get('required_fields', [])
        entity_required_fields = self.config.get('validation', {}).get('entity_required_fields', [])
        valid_relations = self.config.get('validation', {}).get('spatial_relations', [])

        # 根据文件类型验证
        if data_path.suffix == '.jsonl':
            result = self._verify_jsonl(data_path, required_fields, entity_required_fields, valid_relations, result)
        elif data_path.suffix == '.json':
            result = self._verify_json(data_path, required_fields, entity_required_fields, valid_relations, result)
        else:
            result['valid'] = False
            result['errors'].append(f'不支持的文件类型: {data_path.suffix}')

        # 输出结果
        if verbose:
            self._print_verification_result(result)

        return result

    def _verify_jsonl(self, data_path: Path, required_fields: List[str],
                      entity_required_fields: List[str], valid_relations: List[str],
                      result: Dict) -> Dict:
        """验证JSONL文件"""
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    result['total'] += 1

                    try:
                        data = json.loads(line)
                        if self._validate_record(data, required_fields, entity_required_fields, valid_relations):
                            result['valid_count'] += 1
                        else:
                            result['invalid_count'] += 1
                            result['errors'].append(f'行 {line_num}: 数据验证失败')
                    except json.JSONDecodeError as e:
                        result['invalid_count'] += 1
                        result['valid'] = False
                        result['errors'].append(f'行 {line_num}: JSON解析错误 - {str(e)}')

        except Exception as e:
            result['valid'] = False
            result['errors'].append(f'文件读取错误: {str(e)}')

        return result

    def _verify_json(self, data_path: Path, required_fields: List[str],
                     entity_required_fields: List[str], valid_relations: List[str],
                     result: Dict) -> Dict:
        """验证JSON文件"""
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 判断是数组还是对象
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict) and 'data' in data:
                records = data['data']
            else:
                records = [data]

            for idx, record in enumerate(records, 1):
                result['total'] += 1
                if self._validate_record(record, required_fields, entity_required_fields, valid_relations):
                    result['valid_count'] += 1
                else:
                    result['invalid_count'] += 1
                    result['errors'].append(f'记录 {idx}: 数据验证失败')

        except json.JSONDecodeError as e:
            result['valid'] = False
            result['errors'].append(f'JSON解析错误: {str(e)}')
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f'文件读取错误: {str(e)}')

        return result

    def _validate_record(self, record: Dict, required_fields: List[str],
                         entity_required_fields: List[str], valid_relations: List[str]) -> bool:
        """验证单条记录"""
        # 检查必填字段
        for field in required_fields:
            if field not in record:
                return False

        # 检查空间关系类型
        if 'spatial_relation' in record and valid_relations:
            if record['spatial_relation'] not in valid_relations:
                return False

        # 检查实体字段
        if 'entities' in record and isinstance(record['entities'], list):
            for entity in record['entities']:
                if not isinstance(entity, dict):
                    continue
                for field in entity_required_fields:
                    if field not in entity:
                        return False

        return True

    def _print_verification_result(self, result: Dict):
        """打印验证结果"""
        print("\n" + "="*60)
        print("数据验证结果")
        print("="*60)
        print(f"文件路径: {result.get('file_path', 'N/A')}")
        print(f"文件类型: {result.get('file_type', 'N/A')}")
        print(f"状态: {'[OK] 通过' if result['valid'] else '[FAIL] 失败'}")
        print(f"\n总计记录: {result['total']}")
        print(f"有效记录: {result['valid_count']}")
        print(f"无效记录: {result['invalid_count']}")

        if result['errors']:
            print(f"\n错误信息 ({len(result['errors'])}):")
            for error in result['errors'][:10]:  # 只显示前10个错误
                print(f"  - {error}")
            if len(result['errors']) > 10:
                print(f"  ... 还有 {len(result['errors']) - 10} 个错误")

        if result['warnings']:
            print(f"\n警告信息 ({len(result['warnings'])}):")
            for warning in result['warnings']:
                print(f"  - {warning}")

        print("="*60 + "\n")

    def show_statistics(self, data_path: str, output_file: Optional[str] = None,
                        visualize: bool = True) -> Dict[str, Any]:
        """
        显示数据统计信息

        Args:
            data_path: 数据文件路径
            output_file: 输出文件路径（可选）
            visualize: 是否生成可视化图表

        Returns:
            统计信息字典
        """
        data_path = Path(data_path)

        if not data_path.exists():
            print(f"错误: 文件不存在 - {data_path}")
            return {}

        # 加载数据
        records = self._load_data(data_path)
        if not records:
            print("错误: 无法加载数据或数据为空")
            return {}

        # 计算统计信息
        stats = {
            'file_path': str(data_path),
            'total_records': len(records),
            'spatial_relations': self._stat_spatial_relations(records),
            'entity_types': self._stat_entity_types(records),
            'entity_count_distribution': self._stat_entity_count(records),
            'data_quality': self._stat_data_quality(records),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # 打印统计信息
        self._print_statistics(stats)

        # 保存统计报告
        if output_file or self.config.get('statistics', {}).get('save_report', True):
            if output_file is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = self.stats_dir / f"statistics_{timestamp}.json"
            self._save_statistics(stats, output_file)

        # 生成可视化
        if visualize and self.config.get('statistics', {}).get('visualize', True):
            self._visualize_statistics(stats, data_path.stem)

        return stats

    def _load_data(self, data_path: Path) -> List[Dict]:
        """加载数据文件"""
        records = []

        try:
            if data_path.suffix == '.jsonl':
                with open(data_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                records.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            elif data_path.suffix == '.json':
                with open(data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict) and 'data' in data:
                        records = data['data']
                    else:
                        records = [data]
        except Exception as e:
            print(f"加载数据时出错: {e}")

        return records

    def _stat_spatial_relations(self, records: List[Dict]) -> Dict[str, int]:
        """统计空间关系类型分布"""
        counter = Counter()
        for record in records:
            relation = record.get('spatial_relation', 'unknown')
            counter[relation] += 1
        return dict(counter)

    def _stat_entity_types(self, records: List[Dict]) -> Dict[str, int]:
        """统计实体类型分布"""
        counter = Counter()
        for record in records:
            entities = record.get('entities', [])
            if isinstance(entities, list):
                for entity in entities:
                    if isinstance(entity, dict):
                        entity_type = entity.get('type', 'unknown')
                        counter[entity_type] += 1
        return dict(counter)

    def _stat_entity_count(self, records: List[Dict]) -> Dict[str, int]:
        """统计实体数量分布"""
        counter = Counter()
        for record in records:
            entities = record.get('entities', [])
            if isinstance(entities, list):
                count = len(entities)
                counter[count] += 1
        return dict(counter)

    def _stat_data_quality(self, records: List[Dict]) -> Dict[str, Any]:
        """统计数据质量"""
        stats = {
            'missing_id': 0,
            'missing_relation': 0,
            'missing_entities': 0,
            'empty_entities': 0
        }

        for record in records:
            if 'id' not in record:
                stats['missing_id'] += 1
            if 'spatial_relation' not in record:
                stats['missing_relation'] += 1
            if 'entities' not in record:
                stats['missing_entities'] += 1
            elif not record.get('entities'):
                stats['empty_entities'] += 1

        return stats

    def _print_statistics(self, stats: Dict):
        """打印统计信息"""
        print("\n" + "="*60)
        print("数据统计报告")
        print("="*60)
        print(f"文件: {stats['file_path']}")
        print(f"总记录数: {stats['total_records']}")

        print("\n空间关系分布:")
        for relation, count in sorted(stats['spatial_relations'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / stats['total_records']) * 100
            print(f"  {relation}: {count} ({percentage:.2f}%)")

        print("\n实体类型分布:")
        for entity_type, count in sorted(stats['entity_types'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {entity_type}: {count}")

        print("\n实体数量分布:")
        for count, num_records in sorted(stats['entity_count_distribution'].items()):
            print(f"  {count} 个实体: {num_records} 条记录")

        print("\n数据质量:")
        for key, value in stats['data_quality'].items():
            print(f"  {key}: {value}")

        print(f"\n生成时间: {stats['generated_at']}")
        print("="*60 + "\n")

    def _save_statistics(self, stats: Dict, output_file: Path):
        """保存统计报告"""
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print(f"统计报告已保存到: {output_file}")

    def _visualize_statistics(self, stats: Dict, title_prefix: str):
        """生成统计可视化图表"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')  # 使用非交互式后端

            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False

            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle(f'{title_prefix} 数据统计', fontsize=16, fontweight='bold')

            # 空间关系分布饼图
            if stats['spatial_relations']:
                ax1 = axes[0, 0]
                relations = list(stats['spatial_relations'].keys())
                counts = list(stats['spatial_relations'].values())
                ax1.pie(counts, labels=relations, autopct='%1.1f%%', startangle=90)
                ax1.set_title('空间关系类型分布')

            # 实体类型分布柱状图
            if stats['entity_types']:
                ax2 = axes[0, 1]
                entity_types = list(stats['entity_types'].keys())
                counts = list(stats['entity_types'].values())
                ax2.bar(entity_types, counts)
                ax2.set_title('实体类型分布')
                ax2.set_xlabel('实体类型')
                ax2.set_ylabel('数量')
                ax2.tick_params(axis='x', rotation=45)

            # 实体数量分布
            if stats['entity_count_distribution']:
                ax3 = axes[1, 0]
                entity_counts = list(stats['entity_count_distribution'].keys())
                record_counts = list(stats['entity_count_distribution'].values())
                ax3.plot(entity_counts, record_counts, marker='o')
                ax3.set_title('实体数量分布')
                ax3.set_xlabel('实体数量')
                ax3.set_ylabel('记录数')
                ax3.grid(True)

            # 数据质量
            if stats['data_quality']:
                ax4 = axes[1, 1]
                quality_keys = list(stats['data_quality'].keys())
                quality_values = list(stats['data_quality'].values())
                ax4.barh(quality_keys, quality_values)
                ax4.set_title('数据质量问题')
                ax4.set_xlabel('数量')

            plt.tight_layout()

            # 保存图表
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = self.stats_dir / f"visualization_{timestamp}.png"
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            plt.close()

            print(f"可视化图表已保存到: {output_file}")

        except ImportError:
            print("提示: 安装 matplotlib 可以生成可视化图表")
            print("  pip install matplotlib")
        except Exception as e:
            print(f"生成可视化图表时出错: {e}")

    def convert_format(self, input_path: str, output_path: str,
                      input_format: Optional[str] = None,
                      output_format: Optional[str] = None) -> bool:
        """
        转换数据格式

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            input_format: 输入格式（可选，自动从文件扩展名推断）
            output_format: 输出格式（可选，自动从文件扩展名推断）

        Returns:
            是否成功
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        # 推断格式
        if input_format is None:
            input_format = input_path.suffix.lstrip('.')
        if output_format is None:
            output_format = output_path.suffix.lstrip('.')

        # 加载数据
        records = self._load_data(input_path)
        if not records:
            print(f"错误: 无法加载输入文件 - {input_path}")
            return False

        # 创建输出目录
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 转换并保存
        try:
            if output_format == 'jsonl':
                with open(output_path, 'w', encoding='utf-8') as f:
                    for record in records:
                        f.write(json.dumps(record, ensure_ascii=False) + '\n')
            elif output_format == 'json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)
            else:
                print(f"错误: 不支持的输出格式 - {output_format}")
                return False

            print(f"[OK] 成功转换 {len(records)} 条记录")
            print(f"  输入: {input_path} ({input_format})")
            print(f"  输出: {output_path} ({output_format})")
            return True

        except Exception as e:
            print(f"转换时出错: {e}")
            return False

    def clean_cache(self) -> bool:
        """
        清理缓存目录

        Returns:
            是否成功
        """
        if not self.cache_dir.exists():
            print("缓存目录不存在，无需清理")
            return True

        try:
            # 删除缓存目录中的所有文件
            file_count = 0
            for item in self.cache_dir.iterdir():
                if item.is_file():
                    item.unlink()
                    file_count += 1
                elif item.is_dir():
                    # 递归删除子目录
                    for sub_item in item.rglob('*'):
                        if sub_item.is_file():
                            sub_item.unlink()
                            file_count += 1
                    item.rmdir()

            print(f"[OK] 已清理 {file_count} 个缓存文件")
            print(f"  缓存目录: {self.cache_dir}")
            return True

        except Exception as e:
            print(f"清理缓存时出错: {e}")
            return False

    def download_all(self) -> Dict[str, bool]:
        """
        下载所有数据集

        Returns:
            下载结果字典
        """
        print("提示: 请配置数据下载源")
        print("当前功能需要根据实际数据源进行定制")
        return {}


def main():
    """命令行接口"""
    parser = argparse.ArgumentParser(
        description='GeoKD-SR 数据管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有数据文件
  python scripts/data_manager.py list

  # 验证数据
  python scripts/data_manager.py verify --data_path data/geosr_chain/train.jsonl

  # 统计数据
  python scripts/data_manager.py stats --data_path data/geosr_chain/train.jsonl

  # 转换格式
  python scripts/data_manager.py convert --input data.json --output data.jsonl

  # 清理缓存
  python scripts/data_manager.py clean
        """
    )

    parser.add_argument(
        'command',
        choices=['list', 'verify', 'stats', 'convert', 'clean', 'download'],
        help='命令'
    )

    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='配置文件路径'
    )

    parser.add_argument(
        '--data_path',
        type=str,
        help='数据文件路径'
    )

    parser.add_argument(
        '--input',
        type=str,
        help='输入文件路径（转换命令使用）'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='输出文件路径（转换命令使用）'
    )

    parser.add_argument(
        '--output_file',
        type=str,
        help='统计报告输出文件'
    )

    parser.add_argument(
        '--no-visualize',
        action='store_true',
        help='不生成可视化图表'
    )

    parser.add_argument(
        '--quiet',
        '-q',
        action='store_true',
        help='静默模式，减少输出'
    )

    args = parser.parse_args()

    # 创建数据管理器
    manager = DataManager(config_path=args.config)

    # 执行命令
    if args.command == 'list':
        result = manager.list_data()
        if result:
            print("\n数据文件列表:")
            print("="*60)
            for dataset_name, files in result.items():
                print(f"\n{dataset_name}:")
                for file in files:
                    print(f"  - {file}")
            print("="*60 + "\n")
        else:
            print("未找到数据文件")

    elif args.command == 'verify':
        if not args.data_path:
            print("错误: 请使用 --data_path 指定数据文件")
            sys.exit(1)
        manager.verify_data(args.data_path, verbose=not args.quiet)

    elif args.command == 'stats':
        if not args.data_path:
            print("错误: 请使用 --data_path 指定数据文件")
            sys.exit(1)
        manager.show_statistics(
            args.data_path,
            output_file=args.output_file,
            visualize=not args.no_visualize
        )

    elif args.command == 'convert':
        if not args.input or not args.output:
            print("错误: 请使用 --input 和 --output 指定输入输出文件")
            sys.exit(1)
        success = manager.convert_format(args.input, args.output)
        sys.exit(0 if success else 1)

    elif args.command == 'clean':
        manager.clean_cache()

    elif args.command == 'download':
        manager.download_all()


if __name__ == '__main__':
    main()
