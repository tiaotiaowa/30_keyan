"""
generate_entity_mapping.py - 实体Token映射生成模块

集成 EntityTokenMapper，提供批量生成实体到Token索引映射的功能。

功能:
1. EntityMappingGenerator 类: 高层封装，简化映射生成流程
2. 支持单条和批量处理
3. 自动处理映射失败的情况
4. 生成统一格式的映射结果
"""

from typing import Dict, List, Any, Optional
from transformers import AutoTokenizer
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.utils.entity_token_mapper import EntityTokenMapper, create_mapper_from_pretrained


class EntityMappingGenerator:
    """
    实体到Token索引映射生成器

    高层封装类，简化 EntityTokenMapper 的使用，提供统一的数据处理接口。

    Attributes:
        tokenizer: 分词器实例
        mapper: EntityTokenMapper 实例
    """

    def __init__(
        self,
        tokenizer_name: str = "Qwen/Qwen2.5-1.5B",
        tokenizer: Optional[Any] = None
    ):
        """
        初始化映射生成器

        Args:
            tokenizer_name: 预训练tokenizer名称或路径
            tokenizer: 可选的已有tokenizer实例，如果提供则不重新加载
        """
        if tokenizer is not None:
            self.tokenizer = tokenizer
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)

        self.mapper = EntityTokenMapper(self.tokenizer)

    def generate_mapping(
        self,
        question: str,
        entities: List[Dict[str, Any]],
        entity_key: str = 'entity'
    ) -> Dict[str, Dict]:
        """
        为单个问题生成实体到Token的映射

        Args:
            question: 问题文本
            entities: 实体列表，每个实体是一个字典
            entity_key: 实体字典中实体名称的键名，默认为'entity'

        Returns:
            Dict[str, Dict]: 实体名称到映射信息的字典
                {
                    "entity_name": {
                        "char_start": 0,
                        "char_end": 2,
                        "token_indices": [1, 2],
                        "tokens": ["tok1", "tok2"],
                        "match_type": "exact"
                    }
                }

        Examples:
            >>> generator = EntityMappingGenerator()
            >>> question = "北京和上海的距离是多少?"
            >>> entities = [{"entity": "北京"}, {"entity": "上海"}]
            >>> mapping = generator.generate_mapping(question, entities)
            >>> print(mapping)
            {
                "北京": {"char_start": 0, "char_end": 2, "token_indices": [1], ...},
                "上海": {"char_start": 3, "char_end": 5, "token_indices": [3], ...}
            }
        """
        if not question or not entities:
            return {}

        try:
            # 使用 mapper 的 map_all_entities 方法
            results = self.mapper.map_all_entities(question, entities, entity_key)

            # 转换为以实体名称为键的字典
            mapping_dict = {}
            for result in results:
                entity_name = result['entity']
                # 只保留核心映射信息
                mapping_dict[entity_name] = {
                    "char_start": result['char_start'],
                    "char_end": result['char_end'],
                    "token_indices": result['token_indices'],
                    "tokens": result['tokens'],
                    "match_type": result['match_type']
                }

            return mapping_dict

        except Exception as e:
            print(f"映射生成失败: {e}")
            return {}

    def batch_generate_mapping(
        self,
        records: List[Dict[str, Any]],
        question_key: str = 'question',
        entities_key: str = 'entities',
        entity_name_key: str = 'entity'
    ) -> List[Dict[str, Any]]:
        """
        批量生成实体到Token的映射

        Args:
            records: 数据记录列表，每条记录包含问题和实体
            question_key: 问题字段在记录中的键名
            entities_key: 实体列表字段在记录中的键名
            entity_name_key: 实体名称在实体字典中的键名

        Returns:
            List[Dict[str, Any]]: 包含映射结果的记录列表
                每条记录增加 'entity_mapping' 字段

        Examples:
            >>> generator = EntityMappingGenerator()
            >>> records = [
            ...     {
            ...         "question": "北京和上海的距离?",
            ...         "entities": [{"entity": "北京"}, {"entity": "上海"}]
            ...     },
            ...     {
            ...         "question": "长城有多长?",
            ...         "entities": [{"entity": "长城"}]
            ...     }
            ... ]
            >>> results = generator.batch_generate_mapping(records)
        """
        results = []
        total = len(records)

        for idx, record in enumerate(records):
            # 提取问题和实体
            question = record.get(question_key, '')
            entities = record.get(entities_key, [])

            # 生成映射
            mapping = self.generate_mapping(question, entities, entity_name_key)

            # 复制原始记录并添加映射
            result_record = record.copy()
            result_record['entity_mapping'] = mapping
            result_record['mapping_status'] = 'success' if mapping else 'failed'

            # 添加统计信息
            if mapping:
                result_record['mapping_stats'] = {
                    'total_entities': len(entities),
                    'mapped_entities': len(mapping),
                    'failed_entities': len(entities) - len(mapping),
                    'coverage': len(mapping) / len(entities) if entities else 0.0
                }

            results.append(result_record)

            # 进度提示
            if (idx + 1) % 100 == 0:
                print(f"处理进度: {idx + 1}/{total}")

        return results

    def generate_mapping_from_text(
        self,
        text: str,
        entity_names: List[str]
    ) -> Dict[str, Dict]:
        """
        直接从文本和实体名称列表生成映射

        Args:
            text: 原始文本
            entity_names: 实体名称列表

        Returns:
            Dict[str, Dict]: 实体名称到映射信息的字典
        """
        # 将实体名称列表转换为实体字典列表
        entities = [{"entity": name} for name in entity_names]
        return self.generate_mapping(text, entities)

    def verify_mapping(
        self,
        text: str,
        mapping: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """
        验证映射结果的正确性

        Args:
            text: 原始文本
            mapping: 映射结果字典

        Returns:
            Dict[str, Any]: 验证结果
        """
        verification = {
            'valid': True,
            'issues': [],
            'statistics': {
                'total_entities': len(mapping),
                'successful_mappings': 0,
                'failed_mappings': 0
            }
        }

        for entity_name, entity_mapping in mapping.items():
            # 检查映射是否失败
            if entity_mapping['char_start'] == -1:
                verification['failed_mappings'] += 1
                verification['issues'].append(
                    f"实体 '{entity_name}' 未在文本中找到"
                )
                verification['valid'] = False
            else:
                verification['successful_mappings'] += 1

                # 验证token索引有效性
                if not entity_mapping['token_indices']:
                    verification['issues'].append(
                        f"实体 '{entity_name}' 没有对应的token"
                    )
                    verification['valid'] = False

                # 验证字符位置范围
                if not (0 <= entity_mapping['char_start'] < len(text)):
                    verification['issues'].append(
                        f"实体 '{entity_name}' 的起始位置超出文本范围"
                    )
                    verification['valid'] = False

                if not (0 <= entity_mapping['char_end'] <= len(text)):
                    verification['issues'].append(
                        f"实体 '{entity_name}' 的结束位置超出文本范围"
                    )
                    verification['valid'] = False

        return verification


# 便捷函数
def create_mapping_generator(
    model_name: str = "Qwen/Qwen2.5-1.5B"
) -> EntityMappingGenerator:
    """
    创建映射生成器实例

    Args:
        model_name: 预训练模型名称

    Returns:
        EntityMappingGenerator: 实例化的映射生成器
    """
    return EntityMappingGenerator(tokenizer_name=model_name)


def quick_generate_mapping(
    text: str,
    entities: List[Dict[str, Any]],
    model_name: str = "Qwen/Qwen2.5-1.5B"
) -> Dict[str, Dict]:
    """
    快速生成映射的便捷函数

    Args:
        text: 问题文本
        entities: 实体列表
        model_name: 模型名称

    Returns:
        Dict[str, Dict]: 映射结果
    """
    generator = create_mapping_generator(model_name)
    return generator.generate_mapping(text, entities)


# 命令行接口
def main():
    """命令行入口"""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description='生成实体到Token的映射'
    )
    parser.add_argument(
        '--input',
        type=str,
        help='输入JSON文件路径'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='输出JSON文件路径'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='Qwen/Qwen2.5-1.5B',
        help='Tokenizer模型名称'
    )

    args = parser.parse_args()

    # 创建生成器
    generator = create_mapping_generator(args.model)

    # 读取输入文件
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 生成映射
    if isinstance(data, list):
        results = generator.batch_generate_mapping(data)
    elif isinstance(data, dict):
        question = data.get('question', '')
        entities = data.get('entities', [])
        results = generator.generate_mapping(question, entities)
    else:
        raise ValueError("输入数据格式不支持")

    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"映射结果已保存到: {args.output}")


if __name__ == '__main__':
    main()
