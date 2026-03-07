"""
EntityTokenMapper - 实体到Token索引映射器

解决D1-7问题: 将地理实体名称映射到tokenizer的token索引

功能:
1. 使用tokenizer的offset_mapping功能定位实体字符位置
2. 支持模糊匹配处理分词差异
3. 输出包含char_start, char_end, token_indices的映射结果
"""

from typing import Dict, List, Tuple, Optional, Any
import re
from transformers import PreTrainedTokenizer


class EntityTokenMapper:
    """
    实体到Token索引映射器

    用于将文本中的实体名称映射到分词后的token索引，
    解决实体级别特征对齐问题。

    Attributes:
        tokenizer: 分词器，用于生成offset_mapping
    """

    def __init__(self, tokenizer: PreTrainedTokenizer):
        """
        初始化映射器

        Args:
            tokenizer: 预训练的分词器，必须支持offset_mapping功能
        """
        self.tokenizer = tokenizer

        # 验证tokenizer是否支持offset_mapping
        # 现代tokenizer使用__call__方法
        if not (hasattr(tokenizer, '__call__') or hasattr(tokenizer, 'encode_plus')):
            raise ValueError("Tokenizer must be callable or support encode_plus method")

    def map_entity_to_tokens(
        self,
        text: str,
        entity_name: str,
        fuzzy_threshold: float = 0.8
    ) -> Dict[str, Any]:
        """
        将实体名映射到token索引

        Args:
            text: 原始文本
            entity_name: 实体名称
            fuzzy_threshold: 模糊匹配阈值（0-1之间）

        Returns:
            Dict: 包含以下键的字典:
                - entity: 实体名称
                - char_start: 实体在文本中的起始字符位置
                - char_end: 实体在文本中的结束字符位置
                - token_indices: 对应的token索引列表
                - tokens: 对应的token文本列表
                - match_type: 匹配类型 ('exact' 或 'fuzzy')
        """
        # 1. 首先尝试精确匹配
        char_start, char_end, match_type = self._find_entity_position(
            text, entity_name
        )

        # 2. 如果精确匹配失败，尝试模糊匹配
        if char_start == -1:
            char_start, char_end = self._fuzzy_match(text, entity_name, fuzzy_threshold)
            match_type = 'fuzzy'

        # 如果都失败，返回空结果
        if char_start == -1:
            return {
                'entity': entity_name,
                'char_start': -1,
                'char_end': -1,
                'token_indices': [],
                'tokens': [],
                'match_type': 'none'
            }

        # 3. 使用tokenizer获取offset_mapping
        encoding = self.tokenizer(
            text,
            return_offsets_mapping=True,
            add_special_tokens=True,
            truncation=True,
            max_length=self.tokenizer.model_max_length
        )

        # 4. 根据字符位置找到对应的token索引
        token_indices, tokens = self._map_char_range_to_tokens(
            encoding.offset_mapping,
            char_start,
            char_end,
            encoding.tokens()
        )

        return {
            'entity': entity_name,
            'char_start': char_start,
            'char_end': char_end,
            'token_indices': token_indices,
            'tokens': tokens,
            'match_type': match_type
        }

    def map_all_entities(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        entity_key: str = 'entity'
    ) -> List[Dict[str, Any]]:
        """
        映射所有实体

        Args:
            text: 原始文本
            entities: 实体列表，每个实体是一个字典
            entity_key: 实体字典中实体名称的键名

        Returns:
            List[Dict]: 包含所有实体映射结果的列表
        """
        results = []
        for entity in entities:
            entity_name = entity.get(entity_key, '')
            if not entity_name:
                continue

            mapping = self.map_entity_to_tokens(text, entity_name)
            # 合并原始实体信息
            mapping['original_entity'] = entity
            results.append(mapping)

        return results

    def _find_entity_position(
        self,
        text: str,
        entity_name: str
    ) -> Tuple[int, int, str]:
        """
        在文本中查找实体的精确位置

        Args:
            text: 原始文本
            entity_name: 实体名称

        Returns:
            Tuple[int, int, str]: (起始位置, 结束位置, 匹配类型)
        """
        # 去除前后空格
        entity_clean = entity_name.strip()

        # 尝试精确匹配
        pos = text.find(entity_clean)
        if pos != -1:
            return pos, pos + len(entity_clean), 'exact'

        # 尝试忽略大小写匹配
        text_lower = text.lower()
        entity_lower = entity_clean.lower()
        pos = text_lower.find(entity_lower)
        if pos != -1:
            return pos, pos + len(entity_clean), 'case_insensitive'

        return -1, -1, 'none'

    def _fuzzy_match(
        self,
        text: str,
        entity: str,
        threshold: float = 0.8
    ) -> Tuple[int, int]:
        """
        模糊匹配处理分词差异

        使用多种策略处理分词导致的匹配问题：
        1. 去除特殊字符和空格
        2. 基于编辑距离的相似度匹配
        3. 子串匹配

        Args:
            text: 原始文本
            entity: 实体名称
            threshold: 相似度阈值

        Returns:
            Tuple[int, int]: (起始位置, 结束位置)，未找到返回(-1, -1)
        """
        # 策略1: 去除空格和特殊字符后匹配
        text_normalized = re.sub(r'[^\w]', '', text)
        entity_normalized = re.sub(r'[^\w]', '', entity)

        if entity_normalized in text_normalized:
            # 找到在原始文本中的位置
            pos = self._find_normalized_position(text, entity_normalized)
            if pos != -1:
                return pos, pos + len(entity)

        # 策略2: 编辑距离相似度匹配
        best_match = self._find_best_similarity_match(text, entity, threshold)
        if best_match:
            return best_match

        # 策略3: 子串匹配（至少匹配50%的实体长度）
        min_match_len = max(len(entity) // 2, 2)
        for i in range(len(text) - min_match_len + 1):
            substring = text[i:i + len(entity)]
            similarity = self._calculate_similarity(entity, substring)
            if similarity >= threshold:
                return i, i + len(substring)

        return -1, -1

    def _find_normalized_position(
        self,
        text: str,
        normalized_entity: str
    ) -> int:
        """找到规范化实体在原始文本中的位置"""
        # 滑动窗口查找
        for i in range(len(text) - len(normalized_entity) + 1):
            window = text[i:i + len(normalized_entity)]
            if re.sub(r'[^\w]', '', window) == normalized_entity:
                return i
        return -1

    def _find_best_similarity_match(
        self,
        text: str,
        entity: str,
        threshold: float
    ) -> Optional[Tuple[int, int]]:
        """
        基于相似度查找最佳匹配

        使用滑动窗口在文本中查找与实体最相似的子串
        """
        best_similarity = 0
        best_match = None

        entity_len = len(entity)
        window_range = range(entity_len - 2, entity_len + 3)

        for window_len in window_range:
            if window_len <= 0 or window_len > len(text):
                continue

            for i in range(len(text) - window_len + 1):
                substring = text[i:i + window_len]
                similarity = self._calculate_similarity(entity, substring)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = (i, i + window_len)

        if best_similarity >= threshold and best_match:
            return best_match

        return None

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """
        计算两个字符串的相似度

        使用编辑距离（Levenshtein距离）
        """
        if len(s1) == 0 and len(s2) == 0:
            return 1.0

        # 动态规划计算编辑距离
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i - 1][j],      # 删除
                        dp[i][j - 1],      # 插入
                        dp[i - 1][j - 1]   # 替换
                    )

        max_len = max(m, n)
        return 1.0 - (dp[m][n] / max_len) if max_len > 0 else 0.0

    def _map_char_range_to_tokens(
        self,
        offset_mapping: List[Tuple[int, int]],
        char_start: int,
        char_end: int,
        tokens: List[str]
    ) -> Tuple[List[int], List[str]]:
        """
        将字符范围映射到token索引

        Args:
            offset_mapping: tokenizer输出的offset_mapping
            char_start: 实体起始字符位置
            char_end: 实体结束字符位置
            tokens: token列表

        Returns:
            Tuple[List[int], List[str]]: (token索引列表, token文本列表)
        """
        token_indices = []
        matched_tokens = []

        for token_idx, (start, end) in enumerate(offset_mapping):
            # 跳过特殊token（offset为(0,0)）
            if start == 0 and end == 0:
                continue

            # 检查token是否与实体范围重叠
            if end > char_start and start < char_end:
                token_indices.append(token_idx)
                if token_idx < len(tokens):
                    matched_tokens.append(tokens[token_idx])

        return token_indices, matched_tokens

    def batch_map_entities(
        self,
        texts: List[str],
        entities_list: List[List[Dict[str, Any]]],
        entity_key: str = 'entity'
    ) -> List[List[Dict[str, Any]]]:
        """
        批量映射多个文本的实体

        Args:
            texts: 文本列表
            entities_list: 每个文本对应的实体列表
            entity_key: 实体字典中实体名称的键名

        Returns:
            List[List[Dict]]: 每个文本的实体映射结果列表
        """
        results = []
        for text, entities in zip(texts, entities_list):
            results.append(self.map_all_entities(text, entities, entity_key))
        return results

    def get_entity_coverage(
        self,
        mapping_result: Dict[str, Any],
        text_length: int
    ) -> Dict[str, float]:
        """
        计算实体在文本中的覆盖率统计

        Args:
            mapping_result: map_entity_to_tokens的返回结果
            text_length: 原始文本长度

        Returns:
            Dict: 包含覆盖率统计的字典
        """
        if mapping_result['char_start'] == -1:
            return {
                'char_coverage': 0.0,
                'token_count': 0,
                'coverage_ratio': 0.0
            }

        char_span = mapping_result['char_end'] - mapping_result['char_start']
        token_count = len(mapping_result['token_indices'])

        return {
            'char_coverage': char_span / text_length if text_length > 0 else 0.0,
            'token_count': token_count,
            'coverage_ratio': char_span / token_count if token_count > 0 else 0.0
        }


# 便捷函数
def create_mapper_from_pretrained(model_name: str) -> EntityTokenMapper:
    """
    从预训练模型创建映射器

    Args:
        model_name: 预训练模型名称或路径

    Returns:
        EntityTokenMapper: 实例化的映射器
    """
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    return EntityTokenMapper(tokenizer)
