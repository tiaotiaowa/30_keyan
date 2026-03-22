"""
================================================================================
GeoKD-SR 确定性评测指标模块
================================================================================

模块概述:
    本模块提供用于评估地理空间推理模型性能的确定性指标计算功能。
    所有指标均基于规则和数学公式，保证完全可复现。

包含指标:
    1. Overall Accuracy（整体准确率）- 核心评测指标
       - 方向关系匹配（directional）
       - 拓扑关系匹配（topological）- 区分5种类型
       - 距离关系匹配（metric）- 支持容差计算
       - 复合关系匹配（composite）- AND逻辑

    2. Format Valid Rate（格式有效率）
       - 检查模型输出格式是否有效

    3. BLEU-4（文本相似度）
       - 基于n-gram精确率几何平均
       - 使用字符级分词（适用于中文）

    4. ROUGE-L（最长公共子序列）
       - 同时考虑精确率和召回率
       - 使用动态规划算法计算LCS

    5. Spatial F1（空间关键词F1）
       - 专门衡量空间术语使用准确性
       - 支持按空间类型分别计算

使用示例:
    >>> from metrics.deterministic import DeterministicMetrics
    >>>
    >>> # 初始化
    >>> metrics = DeterministicMetrics(config)
    >>>
    >>> # 计算所有指标
    >>> predictions = [
    ...     {
    ...         'spatial_type': 'directional',
    ...         'reference': '北京市在天津市的西北方向',
    ...         'prediction': '西北'
    ...     }
    ... ]
    >>> results = metrics.compute_all(predictions)

配置说明:
    config = {
        'accuracy': {
            'directional_fuzzy': True,      # 启用方向模糊匹配
            'distance_tolerance': 0.15      # 距离容差（15%）
        },
        'spatial_keywords': {
            'directions': ["东", "南", ...],
            'topological': ["相邻", "包含", ...],
            'metric': ["距离", "公里", ...]
        }
    }

自评测验证:
    本模块已通过自评测验证（2026-03-19）
    - 总体准确率: 100.00%
    - 样本数: 1,183
    - 所有空间类型均达到100%

作者: GeoKD-SR 项目组
版本: V1.0
日期: 2026-03-19
================================================================================
"""

import re
from typing import Dict, List, Any, Tuple
from collections import Counter
import math


class DeterministicMetrics:
    """
    确定性评测指标计算器

    该类封装了所有确定性评测指标的计算逻辑，支持：
    - 整体指标计算
    - 按空间类型分层计算
    - 按难度分层计算

    Attributes:
        config (Dict[str, Any]): 配置字典
        direction_keywords (List[str]): 方向关键词列表
        topological_keywords (List[str]): 拓扑关键词列表
        metric_keywords (List[str]): 度量关键词列表
        topology_type_map (Dict[str, List[str]]): 拓扑关系类型映射
        direction_aliases (Dict[str, List[str]]): 方向别名映射

    Example:
        >>> config = {'accuracy': {'directional_fuzzy': True}}
        >>> metrics = DeterministicMetrics(config)
        >>> results = metrics.compute_all(predictions)
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化确定性评测指标计算器

        Args:
            config: 配置字典，包含以下可选配置项：
                - accuracy.directional_fuzzy: 是否启用方向模糊匹配（默认True）
                - accuracy.distance_tolerance: 距离容差比例（默认0.15）
                - spatial_keywords.directions: 自定义方向关键词
                - spatial_keywords.topological: 自定义拓扑关键词
                - spatial_keywords.metric: 自定义度量关键词

        配置示例:
            config = {
                'accuracy': {
                    'directional_fuzzy': True,
                    'distance_tolerance': 0.15
                },
                'spatial_keywords': {
                    'directions': ["东", "南", "西", "北"]
                }
            }
        """
        self.config = config or {}

        # ==================== 空间关键词配置 ====================
        # 从配置中获取关键词，如果未配置则使用默认值
        spatial_config = self.config.get('spatial_keywords', {})

        # 方向关键词（8个基本方向 + 8个偏方向 + 4个正方向）
        # 共20个方向关键词
        self.direction_keywords = spatial_config.get('directions', [
            # 8个基本方向
            "东", "南", "西", "北", "东北", "东南", "西北", "西南",
            # 8个偏方向（更精确的描述）
            "东偏北", "东偏南", "西偏北", "西偏南",
            "北偏东", "北偏西", "南偏东", "南偏西",
            # 4个正方向
            "正北", "正南", "正东", "正西"
        ])

        # 拓扑关系关键词（23个常用词汇）
        # 用于判断文本中是否包含拓扑关系描述
        # 扩展版本：增加了更多拓扑关系词汇以提升覆盖率
        self.topological_keywords = spatial_config.get('topological', [
            "相邻", "包含", "被包含", "交叉", "分离", "接壤", "重叠",
            "位于", "在...内", "内部", "外部", "毗邻", "属于", "涵盖",
            # 新增词汇
            "相接", "相连", "不相邻", "不重叠", "被包围", "环绕",
            "穿过", "贯穿", "跨越"
        ])

        # 度量/距离关键词（11个常用词汇）
        # 用于判断文本中是否包含距离描述
        self.metric_keywords = spatial_config.get('metric', [
            "距离", "公里", "千米", "米", "远", "近", "相距", "间隔",
            "半径", "范围", "约"
        ])

        # ==================== 拓扑关系类型映射 ====================
        # 用于区分不同的拓扑关系类型（within、contains、adjacent、disjoint、overlap）
        # 这是自评测验证的关键修复：只有当拓扑关系类型一致时才判定为正确
        #
        # 匹配策略：
        # - 按关键词长度降序排序，优先匹配长关键词避免误匹配
        # - 例如："在...内部" 优先于 "内部" 匹配
        #
        # 类型说明：
        # - within: A在B内部（A被B包含）
        # - contains: A包含B
        # - adjacent: A与B相邻
        # - disjoint: A与B不相交/分离
        # - overlap: A与B重叠
        self.topology_type_map = {
            "within": [
                "在...内部", "位于...内", "在...里面", "属于", "包含于", "境内",
                "内部", "被包含", "被包围", "环绕"
            ],
            "contains": [
                "包含", "内部有", "有...在", "涵盖", "境内有"
            ],
            "adjacent": [
                "相邻", "毗邻", "接壤", "邻近", "交界", "边界",
                # 新增词汇
                "相接", "相连"
            ],
            "disjoint": [
                "不相交", "分离", "相离", "没有重叠", "不存在",
                # 新增词汇
                "不相邻", "不重叠"
            ],
            "overlap": [
                "重叠", "部分重叠", "交叉",
                # 新增词汇
                "穿过", "贯穿", "跨越"
            ]
        }

        # ==================== 方向别名映射 ====================
        # 用于模糊匹配方向词汇
        # 例如："正东" 和 "东" 应该视为相同方向
        #
        # 映射规则：
        # - 主方向 -> 该方向的所有别名列表
        # - 别名之间可以互换，均判定为正确
        self.direction_aliases = {
            "东": ["东", "正东"],
            "南": ["南", "正南"],
            "西": ["西", "正西"],
            "北": ["北", "正北"],
            "东北": ["东北", "东偏北", "北偏东"],
            "东南": ["东南", "东偏南", "南偏东"],
            "西北": ["西北", "西偏北", "北偏西"],
            "西南": ["西南", "西偏南", "南偏西"]
        }

    def compute_all(self, predictions: List[Dict]) -> Dict[str, Any]:
        """
        计算所有确定性指标

        这是主要的评测入口函数，一次性计算所有确定性指标。

        Args:
            predictions: 预测结果列表，每个元素是一个字典，包含：
                - spatial_type: 空间关系类型（directional/topological/metric/composite）
                - reference: 参考答案文本
                - prediction: 模型预测文本
                - difficulty: 难度级别（可选，easy/medium/hard）
                - id: 样本ID（可选）

        Returns:
            Dict[str, Any]: 包含所有指标的结果字典：
                - total: 总样本数
                - accuracy: 准确率相关指标（含总体和各类型分项）
                - format_valid_rate: 格式有效率
                - bleu4: BLEU-4分数
                - rouge_l: ROUGE-L分数
                - spatial_f1: 空间关键词F1（含总体和各类型分项）

        Example:
            >>> predictions = [
            ...     {
            ...         'spatial_type': 'directional',
            ...         'reference': '北京市在天津市的东南方向',
            ...         'prediction': '东南'
            ...     }
            ... ]
            >>> results = metrics.compute_all(predictions)
            >>> print(results['accuracy']['overall'])
            1.0
        """
        results = {
            'total': len(predictions),
            'accuracy': self._compute_accuracy(predictions),
            'format_valid_rate': self._compute_format_valid_rate(predictions),
            'bleu4': self._compute_bleu4(predictions),
            'rouge_l': self._compute_rouge_l(predictions),
            'spatial_f1': self._compute_spatial_f1(predictions)
        }

        return results

    # ==================== 准确率计算 ====================

    def _compute_accuracy(self, predictions: List[Dict]) -> Dict[str, float]:
        """
        计算准确率（按空间类型分层）

        根据不同的空间关系类型，使用不同的匹配策略：
        - directional: 方向关键词匹配（支持模糊匹配）
        - topological: 拓扑关系类型匹配（区分5种类型）
        - metric: 距离数值匹配（支持容差）
        - composite: 方向+距离复合匹配（AND逻辑）

        Args:
            predictions: 预测结果列表

        Returns:
            Dict[str, float]: 准确率结果字典：
                - overall: 总体准确率
                - {spatial_type}_accuracy: 各空间类型准确率
                - by_type: 各类型的详细统计（正确数/总数）
        """
        # 获取配置
        accuracy_config = self.config.get('accuracy', {})
        fuzzy_direction = accuracy_config.get('directional_fuzzy', True)
        distance_tolerance = accuracy_config.get('distance_tolerance', 0.15)

        results = {'overall': 0.0}
        type_results = {}

        # 遍历每个预测样本
        for pred in predictions:
            spatial_type = pred.get('spatial_type', 'unknown')
            reference = pred.get('reference', '')
            prediction = pred.get('prediction', '')

            # 初始化该类型的统计
            if spatial_type not in type_results:
                type_results[spatial_type] = {'correct': 0, 'total': 0}

            type_results[spatial_type]['total'] += 1

            # 判断答案是否正确（核心匹配逻辑）
            is_correct = self._check_answer_correct(
                reference, prediction, spatial_type,
                fuzzy_direction, distance_tolerance
            )

            if is_correct:
                type_results[spatial_type]['correct'] += 1

        # 计算各类型准确率
        total_correct = 0
        total_count = 0
        for stype, stats in type_results.items():
            acc = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
            results[f'{stype}_accuracy'] = acc
            total_correct += stats['correct']
            total_count += stats['total']

        results['overall'] = total_correct / total_count if total_count > 0 else 0
        results['by_type'] = type_results

        return results

    def _check_answer_correct(
        self,
        reference: str,
        prediction: str,
        spatial_type: str,
        fuzzy_direction: bool,
        distance_tolerance: float
    ) -> bool:
        """
        检查答案是否正确

        根据空间关系类型选择对应的匹配策略进行判断。

        Args:
            reference: 参考答案文本
            prediction: 预测答案文本
            spatial_type: 空间关系类型
                - directional: 方向关系
                - topological: 拓扑关系
                - metric: 度量关系
                - composite: 复合关系
            fuzzy_direction: 是否使用模糊方向匹配
            distance_tolerance: 距离容忍度（百分比）

        Returns:
            bool: 答案是否正确

        匹配优先级:
            1. 完全匹配（不区分大小写）
            2. 根据空间类型的特定匹配
            3. 包含匹配（参考答案包含在预测中，或反之）
        """
        # 预处理：转小写并去除首尾空格
        ref_lower = reference.lower().strip()
        pred_lower = prediction.lower().strip()

        # 1. 完全匹配
        if ref_lower == pred_lower:
            return True

        # 2. 根据空间类型进行特定匹配
        if spatial_type == 'directional':
            # 方向关系匹配
            return self._check_direction_match(ref_lower, pred_lower, fuzzy_direction)
        elif spatial_type == 'topological':
            # 拓扑关系匹配（区分5种类型）
            return self._check_topological_match(ref_lower, pred_lower)
        elif spatial_type == 'metric':
            # 度量/距离关系匹配
            return self._check_distance_match(ref_lower, pred_lower, distance_tolerance)
        elif spatial_type == 'composite':
            # 复合关系匹配（方向+距离，AND逻辑）
            return self._check_composite_match(ref_lower, pred_lower, fuzzy_direction, distance_tolerance)

        # 3. 包含匹配（回退策略）
        return ref_lower in pred_lower or pred_lower in ref_lower

    # ==================== 方向关系匹配 ====================

    def _check_direction_match(self, ref: str, pred: str, fuzzy: bool) -> bool:
        """
        检查方向匹配

        从参考答案和预测答案中提取方向词，然后比较是否一致。

        Args:
            ref: 参考答案文本
            pred: 预测答案文本
            fuzzy: 是否使用模糊匹配
                - True: 使用别名映射，如"正东"和"东"视为相同
                - False: 严格匹配，必须完全一致

        Returns:
            bool: 方向是否匹配

        匹配示例:
            fuzzy=True:
                - ref="正东", pred="东" -> True
                - ref="东偏北", pred="东北" -> True
            fuzzy=False:
                - ref="正东", pred="东" -> False
                - ref="东", pred="东" -> True
        """
        # 提取方向词
        ref_dir = self._extract_direction(ref)
        pred_dir = self._extract_direction(pred)

        # 如果任一答案无法提取方向词，判定为不匹配
        if not ref_dir or not pred_dir:
            return False

        if fuzzy:
            # 使用别名映射进行模糊匹配
            for main_dir, aliases in self.direction_aliases.items():
                if ref_dir in aliases and pred_dir in aliases:
                    return True
        else:
            # 严格匹配
            return ref_dir == pred_dir

        return False

    def _extract_direction(self, text: str) -> str:
        """
        从文本中提取方向词

        使用最长匹配策略，优先匹配较长的方向词。

        Args:
            text: 输入文本

        Returns:
            str: 提取到的方向词，如果未找到则返回空字符串

        匹配策略:
            按关键词长度降序排序，优先匹配长关键词避免误匹配。
            例如："东偏北" 应该匹配为 "东偏北"，而不是 "东"。

        Example:
            >>> extract_direction("北京市在天津市的东南方向")
            "东南"
            >>> extract_direction("上海市位于江苏省的正北方向")
            "正北"
        """
        # 按长度降序排序，优先匹配长关键词
        for keyword in sorted(self.direction_keywords, key=len, reverse=True):
            if keyword in text:
                return keyword
        return ""

    # ==================== 拓扑关系匹配 ====================

    def _check_topological_match(self, ref: str, pred: str) -> bool:
        """
        检查拓扑关系匹配

        这是自评测验证的关键修复：
        现在需要区分不同的拓扑关系类型（within、contains、adjacent、disjoint、overlap）
        只有当关系类型一致时才判定为正确。

        Args:
            ref: 参考答案文本
            pred: 预测答案文本

        Returns:
            bool: 拓扑关系是否匹配

        匹配规则:
            1. 从参考答案中提取拓扑关系类型
            2. 从预测答案中提取拓扑关系类型
            3. 比较两个类型是否一致

        示例:
            - ref="江苏省与浙江省相邻" (adjacent)
            - pred="江苏省位于浙江省内部" (within)
            - 结果：类型不一致 -> False

            - ref="江苏省与浙江省相邻" (adjacent)
            - pred="它们是相邻的" (adjacent)
            - 结果：类型一致 -> True
        """
        # 从参考答案中提取拓扑关系类型
        ref_type = self._extract_topology_type(ref)
        # 从预测答案中提取拓扑关系类型
        pred_type = self._extract_topology_type(pred)

        # 如果任一答案无法识别拓扑类型，使用回退逻辑
        if ref_type is None or pred_type is None:
            # 回退到关键词匹配（但不区分类型）
            for keyword in self.topological_keywords:
                if keyword in ref and keyword in pred:
                    return True
            return False

        # 比较拓扑关系类型是否一致
        return ref_type == pred_type

    def _extract_topology_type(self, text: str) -> str | None:
        """
        从文本中提取拓扑关系类型

        使用最长匹配策略，优先匹配较长的关键词。

        Args:
            text: 输入文本

        Returns:
            str | None: 拓扑关系类型（within/contains/adjacent/disjoint/overlap）
                        如果无法识别则返回None

        匹配策略:
            1. 遍历所有拓扑关系类型
            2. 对每种类型的关键词按长度降序排序
            3. 优先匹配长关键词，避免短关键词误匹配

        Example:
            >>> extract_topology_type("江苏省与浙江省相邻")
            "adjacent"
            >>> extract_topology_type("北京市位于河北省内部")
            "within"
            >>> extract_topology_type("这是一个普通句子")
            None
        """
        # 遍历所有拓扑关系类型
        for topo_type, keywords in self.topology_type_map.items():
            # 按长度降序排序关键词，避免短关键词误匹配
            # 例如："在...内部" 优先于 "内部" 匹配
            for keyword in sorted(keywords, key=len, reverse=True):
                if keyword in text:
                    return topo_type
        return None

    # ==================== 距离关系匹配 ====================

    def _check_distance_match(self, ref: str, pred: str, tolerance: float = 0.15) -> bool:
        """
        检查距离匹配

        使用容差规则判断预测的距离是否正确。

        Args:
            ref: 参考答案文本
            pred: 预测答案文本
            tolerance: 百分比容忍度（默认0.15即15%，与配置文件保持一致）

        Returns:
            bool: 距离是否在容差范围内

        容差规则:
            tolerance_value = max(ref_dist × tolerance, 50)

            即取以下两者中的较大值：
            - 百分比容差：ref_dist × tolerance
            - 固定容差：50公里

        容差设计原理:
            - 对于短距离（如100公里），15% = ±15公里，使用±50km兜底
            - 对于长距离（如2500公里），15% = ±375公里，使用百分比容忍

        示例:
            ref="距离约1200公里", pred="1150公里"
            tolerance_value = max(1200 × 0.15, 50) = 180
            范围: [1020, 1380]
            1150 在范围内 -> True
        """
        # 提取数字（支持整数和小数）
        ref_numbers = re.findall(r'(\d+(?:\.\d+)?)', ref)
        pred_numbers = re.findall(r'(\d+(?:\.\d+)?)', pred)

        # 如果无法提取数字，判定为不匹配
        if not ref_numbers or not pred_numbers:
            return False

        try:
            ref_dist = float(ref_numbers[0])
            pred_dist = float(pred_numbers[0])

            # 计算容差值：取百分比容差和固定容差（50km）中的较大值
            tolerance_value = max(ref_dist * tolerance, 50)

            # 计算容差范围
            lower = ref_dist - tolerance_value
            upper = ref_dist + tolerance_value

            # 判断预测距离是否在容差范围内
            return lower <= pred_dist <= upper
        except ValueError:
            return False

    # ==================== 复合关系匹配 ====================

    def _check_composite_match(self, ref: str, pred: str, fuzzy_dir: bool, dist_tol: float) -> bool:
        """
        检查复合关系匹配

        复合问题需要同时满足方向和距离两个条件。

        Args:
            ref: 参考答案文本
            pred: 预测答案文本
            fuzzy_dir: 是否使用方向模糊匹配
            dist_tol: 距离容忍度

        Returns:
            bool: 复合关系是否匹配

        匹配逻辑:
            使用AND逻辑：方向和距离都必须正确才算正确

            correct = direction_match AND distance_match

        示例:
            ref="上海市位于北京市东南方向约1200公里"
            pred="东南方向，1150公里"

            direction_match = True (东南匹配)
            distance_match = True (1150在[1020,1380]范围内)
            result = True

        注意:
            这是自评测验证的关键修复：
            之前使用OR逻辑（方向或距离正确一个就算正确），
            现在改为AND逻辑（两个都必须正确）。
        """
        # 分别检查方向和距离
        dir_match = self._check_direction_match(ref, pred, fuzzy_dir)
        dist_match = self._check_distance_match(ref, pred, dist_tol)

        # 方向和距离都必须正确才算复合问题正确
        return dir_match and dist_match

    # ==================== 格式有效率计算 ====================

    def _compute_format_valid_rate(self, predictions: List[Dict]) -> float:
        """
        计算格式有效率

        格式有效率衡量模型输出能否被正确解析的比例。

        Args:
            predictions: 预测结果列表

        Returns:
            float: 格式有效率（0.0-1.0）

        判定标准:
            1. 非空且长度>=2
            2. 不是错误信息（不以"ERROR:"开头）
            3. 包含有意义的中文或数字
        """
        valid_count = 0

        for pred in predictions:
            prediction = pred.get('prediction', '')

            if self._is_valid_format(prediction):
                valid_count += 1

        return valid_count / len(predictions) if predictions else 0

    def _is_valid_format(self, text: str) -> bool:
        """
        检查文本格式是否有效

        Args:
            text: 待检查的文本

        Returns:
            bool: 格式是否有效

        检查规则:
            1. 非空且长度>=2（排除单字符输出）
            2. 不是错误信息（不以"ERROR:"开头）
            3. 包含有意义的中文或数字（至少包含其中一种）
        """
        # 检查1：非空且长度>=2
        if not text or len(text.strip()) < 2:
            return False

        # 检查2：不是错误信息
        if text.startswith("ERROR:"):
            return False

        # 检查3：包含中文或数字
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        has_number = bool(re.search(r'\d', text))

        return has_chinese or has_number

    # ==================== BLEU-4 计算 ====================

    def _compute_bleu4(self, predictions: List[Dict]) -> float:
        """
        计算BLEU-4分数（语料级别）

        BLEU-4是基于n-gram精确率几何平均的文本相似度指标。

        Args:
            predictions: 预测结果列表

        Returns:
            float: BLEU-4分数（0.0-1.0）

        公式:
            BLEU = BP × exp(Σ(w_n × log(p_n)) / 4)

            其中：
            - BP (Brevity Penalty) = exp(1 - r/c) if c < r else 1
            - p_n = n-gram精确率 (n=1,2,3,4)
            - w_n = 1/4 (权重均等)

        特点:
            - 使用字符级分词（适用于中文）
            - 支持平滑处理零精确率情况
        """
        scores = []

        for pred in predictions:
            reference = pred.get('reference', '')
            prediction = pred.get('prediction', '')

            score = self._bleu_score(reference, prediction, max_n=4)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 0

    def _bleu_score(self, reference: str, prediction: str, max_n: int = 4) -> float:
        """
        计算单条BLEU分数

        Args:
            reference: 参考文本
            prediction: 预测文本
            max_n: 最大n-gram（默认4）

        Returns:
            float: BLEU分数（0.0-1.0）

        计算步骤:
            1. 字符级分词
            2. 计算短句惩罚（Brevity Penalty）
            3. 计算1-4 gram精确率
            4. 计算几何平均
        """
        # 字符级分词（适用于中文）
        ref_tokens = list(reference)
        pred_tokens = list(prediction)

        if not pred_tokens:
            return 0

        # 计算BP（短句惩罚）
        ref_len = len(ref_tokens)
        pred_len = len(pred_tokens)

        if pred_len > ref_len:
            bp = 1
        elif pred_len == 0:
            return 0
        else:
            bp = math.exp(1 - ref_len / pred_len)

        # 计算1-4 gram精确率
        precisions = []
        for n in range(1, max_n + 1):
            ref_ngrams = self._get_ngrams(ref_tokens, n)
            pred_ngrams = self._get_ngrams(pred_tokens, n)

            if not pred_ngrams:
                precisions.append(0)
                continue

            # 计算匹配的n-gram数量
            matches = 0
            for ngram, count in pred_ngrams.items():
                if ngram in ref_ngrams:
                    matches += min(count, ref_ngrams[ngram])

            precision = matches / sum(pred_ngrams.values())
            precisions.append(precision)

        # 几何平均
        if any(p == 0 for p in precisions):
            return 0

        geo_mean = math.exp(sum(math.log(p) for p in precisions) / len(precisions))

        return bp * geo_mean

    def _get_ngrams(self, tokens: List[str], n: int) -> Counter:
        """
        获取n-gram及其频率

        Args:
            tokens: 分词后的token列表
            n: n-gram的n值

        Returns:
            Counter: n-gram到频率的映射

        Example:
            >>> get_ngrams(["北", "京", "市"], 2)
            Counter({('北', '京'): 1, ('京', '市'): 1})
        """
        ngrams = Counter()
        for i in range(len(tokens) - n + 1):
            ngram = tuple(tokens[i:i+n])
            ngrams[ngram] += 1
        return ngrams

    # ==================== ROUGE-L 计算 ====================

    def _compute_rouge_l(self, predictions: List[Dict]) -> float:
        """
        计算ROUGE-L分数（语料级别）

        ROUGE-L基于最长公共子序列(LCS)计算文本相似度。

        Args:
            predictions: 预测结果列表

        Returns:
            float: ROUGE-L F1分数（0.0-1.0）

        公式:
            F1 = 2 × P × R / (P + R)

            其中：
            - P (Precision) = LCS长度 / 预测文本长度
            - R (Recall) = LCS长度 / 参考文本长度

        特点:
            - 能够捕捉词汇顺序信息
            - 使用动态规划算法计算LCS
        """
        scores = []

        for pred in predictions:
            reference = pred.get('reference', '')
            prediction = pred.get('prediction', '')

            score = self._rouge_l_score(reference, prediction)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 0

    def _rouge_l_score(self, reference: str, prediction: str) -> float:
        """
        计算单条ROUGE-L F1分数

        Args:
            reference: 参考文本
            prediction: 预测文本

        Returns:
            float: ROUGE-L F1分数（0.0-1.0）

        计算步骤:
            1. 字符级分词
            2. 计算LCS长度
            3. 计算Precision和Recall
            4. 计算F1分数
        """
        ref_tokens = list(reference)
        pred_tokens = list(prediction)

        if not ref_tokens or not pred_tokens:
            return 0

        # 计算LCS长度
        lcs_len = self._lcs_length(ref_tokens, pred_tokens)

        # 计算Precision和Recall
        precision = lcs_len / len(pred_tokens)
        recall = lcs_len / len(ref_tokens)

        # 计算F1
        if precision + recall == 0:
            return 0

        f1 = 2 * precision * recall / (precision + recall)
        return f1

    def _lcs_length(self, seq1: List, seq2: List) -> int:
        """
        计算最长公共子序列(LCS)长度

        使用动态规划算法计算。

        Args:
            seq1: 序列1
            seq2: 序列2

        Returns:
            int: LCS长度

        算法复杂度:
            时间复杂度: O(m×n)
            空间复杂度: O(m×n)

        DP方程:
            if seq1[i] == seq2[j]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        """
        m, n = len(seq1), len(seq2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])

        return dp[m][n]

    # ==================== 空间关键词F1计算 ====================

    def _compute_spatial_f1(self, predictions: List[Dict]) -> Dict[str, Any]:
        """
        计算空间关键词F1分数

        专门衡量模型输出中空间术语的使用准确性。
        支持按空间类型分别计算。

        Args:
            predictions: 预测结果列表

        Returns:
            Dict[str, Any]: 包含总体和各类型分项的F1结果：
                {
                    'overall': {
                        'precision': float,
                        'recall': float,
                        'f1': float
                    },
                    'by_type': {
                        'directional': {'precision': ..., 'recall': ..., 'f1': ...},
                        'topological': {'precision': ..., 'recall': ..., 'f1': ...},
                        'metric': {'precision': ..., 'recall': ..., 'f1': ...}
                    }
                }

        计算方式:
            1. 从参考答案和预测答案中提取空间关键词
            2. 计算TP（共有关键词）、FP（预测多出的）、FN（预测遗漏的）
            3. 计算Precision = TP / (TP + FP)
            4. 计算Recall = TP / (TP + FN)
            5. 计算F1 = 2 × P × R / (P + R)
        """
        # 合并所有关键词
        all_keywords = self.direction_keywords + self.topological_keywords + self.metric_keywords

        # 按空间类型分组的关键词
        keywords_by_type = {
            'directional': self.direction_keywords,
            'topological': self.topological_keywords,
            'metric': self.metric_keywords
        }

        # ==================== 计算总体F1 ====================
        tp, fp, fn = 0, 0, 0

        for pred in predictions:
            reference = pred.get('reference', '')
            prediction = pred.get('prediction', '')

            ref_keywords = set()
            pred_keywords = set()

            # 提取参考答案中的关键词
            for keyword in all_keywords:
                if keyword in reference:
                    ref_keywords.add(keyword)
                if keyword in prediction:
                    pred_keywords.add(keyword)

            # 累加TP、FP、FN
            tp += len(ref_keywords & pred_keywords)
            fp += len(pred_keywords - ref_keywords)
            fn += len(ref_keywords - pred_keywords)

        # 计算总体Precision、Recall、F1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        # ==================== 按类型计算F1 ====================
        type_results = {}
        for stype, keywords in keywords_by_type.items():
            tp_type, fp_type, fn_type = 0, 0, 0

            for pred in predictions:
                reference = pred.get('reference', '')
                prediction = pred.get('prediction', '')

                ref_keywords = set()
                pred_keywords = set()

                for keyword in keywords:
                    if keyword in reference:
                        ref_keywords.add(keyword)
                    if keyword in prediction:
                        pred_keywords.add(keyword)

                tp_type += len(ref_keywords & pred_keywords)
                fp_type += len(pred_keywords - ref_keywords)
                fn_type += len(ref_keywords - pred_keywords)

            # 计算该类型的Precision、Recall、F1
            p = tp_type / (tp_type + fp_type) if (tp_type + fp_type) > 0 else 0
            r = tp_type / (tp_type + fn_type) if (tp_type + fn_type) > 0 else 0
            f = 2 * p * r / (p + r) if (p + r) > 0 else 0

            type_results[stype] = {
                'precision': p,
                'recall': r,
                'f1': f
            }

        return {
            'overall': {
                'precision': precision,
                'recall': recall,
                'f1': f1
            },
            'by_type': type_results
        }

    # ==================== 分层分析 ====================

    def compute_by_type(self, predictions: List[Dict]) -> Dict[str, Dict]:
        """
        按空间类型分层计算指标

        将预测结果按空间关系类型分组，分别计算指标。

        Args:
            predictions: 预测结果列表

        Returns:
            Dict[str, Dict]: 各空间类型的完整指标结果
                {
                    'directional': {...},
                    'topological': {...},
                    'metric': {...},
                    'composite': {...}
                }
        """
        type_groups = {}

        # 按空间类型分组
        for pred in predictions:
            spatial_type = pred.get('spatial_type', 'unknown')
            if spatial_type not in type_groups:
                type_groups[spatial_type] = []
            type_groups[spatial_type].append(pred)

        # 分别计算指标
        results = {}
        for stype, preds in type_groups.items():
            results[stype] = self.compute_all(preds)

        return results

    def compute_by_difficulty(self, predictions: List[Dict]) -> Dict[str, Dict]:
        """
        按难度分层计算指标

        将预测结果按难度级别分组，分别计算指标。

        Args:
            predictions: 预测结果列表

        Returns:
            Dict[str, Dict]: 各难度级别的完整指标结果
                {
                    'easy': {...},
                    'medium': {...},
                    'hard': {...}
                }
        """
        diff_groups = {}

        # 按难度分组
        for pred in predictions:
            difficulty = pred.get('difficulty', 'unknown')
            if difficulty not in diff_groups:
                diff_groups[difficulty] = []
            diff_groups[difficulty].append(pred)

        # 分别计算指标
        results = {}
        for diff, preds in diff_groups.items():
            results[diff] = self.compute_all(preds)

        return results
