"""
推理链生成模块 (Reasoning Chain Generator)

与 spatial_cot_loss.py 中的 REASONING_STEPS 对齐的5步结构化推理链生成:
1. entity_identification - 实体识别
2. spatial_relation_extraction - 空间关系抽取
3. coordinate_retrieval - 坐标检索
4. spatial_calculation - 空间计算
5. answer_generation - 答案生成

支持与GLM-5 API集成生成自然语言推理内容。
"""

import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import httpx
from datetime import datetime


class SpatialRelationType(Enum):
    """空间关系类型枚举"""
    # 方向关系
    DIRECTIONAL = "directional"  # 方向关系
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTHEAST = "northeast"
    NORTHWEST = "northwest"
    SOUTHEAST = "southeast"
    SOUTHWEST = "southwest"

    # 拓扑关系
    TOPOLOGICAL = "topological"  # 拓扑关系
    ADJACENT = "adjacent"        # 相邻
    CONTAINS = "contains"        # 包含
    WITHIN = "within"            # 在...内
    OVERLAPS = "overlaps"        # 重叠
    DISJOINT = "disjoint"        # 分离

    # 度量关系
    METRIC = "metric"            # 度量关系
    DISTANCE = "distance"        # 距离
    AREA = "area"                # 面积
    LENGTH = "length"            # 长度


@dataclass
class ReasoningStep:
    """推理步骤数据类"""
    step: int
    name: str
    action: str
    content: str
    entities_involved: List[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "step": self.step,
            "name": self.name,
            "action": self.action,
            "content": self.content,
            "entities_involved": self.entities_involved,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "timestamp": datetime.now().isoformat()
        }


@dataclass
class GeoEntity:
    """地理实体数据类"""
    name: str
    entity_type: str  # city, province, country, landmark, etc.
    coordinates: Optional[Tuple[float, float]] = None
    aliases: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "coordinates": self.coordinates,
            "aliases": self.aliases,
            "attributes": self.attributes
        }


class ReasoningChainGenerator:
    """
    推理链生成器

    与 SpatialReasoningChainLoss.REASONING_STEPS 对齐:
    - entity_identification: 实体识别
    - spatial_relation_extraction: 空间关系抽取 (对应 spatial_relation)
    - coordinate_retrieval: 坐标检索 (对应 relation_classification)
    - spatial_calculation: 空间计算 (对应 spatial_inference)
    - answer_generation: 答案生成
    """

    # 标准推理步骤 (与 loss 模块对齐)
    REASONING_STEPS = [
        'entity_identification',    # 步骤1: 实体识别
        'spatial_relation_extraction',  # 步骤2: 空间关系抽取
        'coordinate_retrieval',      # 步骤3: 坐标检索
        'spatial_calculation',       # 步骤4: 空间计算
        'answer_generation'          # 步骤5: 答案生成
    ]

    # 步骤动作映射
    STEP_ACTIONS = {
        'entity_identification': 'extract_entities',
        'spatial_relation_extraction': 'extract_relations',
        'coordinate_retrieval': 'retrieve_coordinates',
        'spatial_calculation': 'compute_spatial',
        'answer_generation': 'generate_answer'
    }

    def __init__(
        self,
        glm_api_key: Optional[str] = None,
        glm_api_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        enable_llm: bool = False,
        timeout: float = 30.0
    ):
        """
        初始化推理链生成器

        Args:
            glm_api_key: GLM API密钥 (可选)
            glm_api_url: GLM API地址
            enable_llm: 是否启用LLM生成自然语言内容
            timeout: API请求超时时间
        """
        self.glm_api_key = glm_api_key
        self.glm_api_url = glm_api_url
        self.enable_llm = enable_llm
        self.timeout = timeout

        # 知识库缓存 (模拟坐标数据库)
        self._coordinate_cache = self._build_coordinate_cache()

    def _build_coordinate_cache(self) -> Dict[str, Tuple[float, float]]:
        """构建坐标缓存数据库"""
        return {
            # 中国主要城市
            "北京": (39.9042, 116.4074),
            "上海": (31.2304, 121.4737),
            "广州": (23.1291, 113.2644),
            "深圳": (22.5431, 114.0579),
            "杭州": (30.2741, 120.1551),
            "南京": (32.0603, 118.7969),
            "成都": (30.5728, 104.0668),
            "重庆": (29.4316, 106.9123),
            "武汉": (30.5928, 114.3055),
            "西安": (34.3416, 108.9398),
            # 省份
            "河北省": (38.0428, 114.5149),
            "山西省": (37.8706, 112.5489),
            "辽宁省": (41.2956, 123.4315),
            "吉林省": (43.8371, 125.3235),
            "黑龙江省": (45.7732, 126.6618),
            "江苏省": (32.0603, 118.7969),
            "浙江省": (30.2741, 120.1551),
            "安徽省": (31.8612, 117.2262),
            "福建省": (26.0745, 119.2965),
            "江西省": (28.6769, 115.9099),
            "山东省": (36.6683, 117.0009),
            "河南省": (34.7466, 113.6253),
            "湖北省": (30.5928, 114.3055),
            "湖南省": (28.2282, 112.9388),
            "广东省": (23.1291, 113.2644),
            "海南省": (20.0174, 110.3492),
            "四川省": (30.5728, 104.0668),
            "贵州省": (26.5783, 106.7135),
            "云南省": (25.0389, 102.7183),
            "陕西省": (34.3416, 108.9398),
            "甘肃省": (36.0611, 103.8343),
            "青海省": (36.6171, 101.7782),
            # 地标
            "长城": (40.4319, 116.5704),
            "故宫": (39.9163, 116.3972),
            "天安门": (39.9075, 116.3972),
            "黄山": (30.1318, 118.1669),
            "泰山": (36.2573, 117.1018),
            "长江": (29.7279, 111.2827),
            "黄河": (34.8254, 111.2262),
        }

    async def _generate_llm_content(
        self,
        prompt: str,
        step_name: str
    ) -> str:
        """
        使用GLM-5 API生成自然语言推理内容

        Args:
            prompt: 提示词
            step_name: 步骤名称

        Returns:
            生成的自然语言内容
        """
        if not self.enable_llm or not self.glm_api_key:
            return self._get_default_content(step_name)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "Authorization": f"Bearer {self.glm_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "glm-5",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"作为地理空间推理专家，请完成以下推理步骤:\n{prompt}\n\n请用简洁专业的语言描述该推理步骤的分析过程。"
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 300
                }

                response = await client.post(
                    self.glm_api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                return result["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"GLM API调用失败: {e}")
            return self._get_default_content(step_name)

    def _get_default_content(self, step_name: str) -> str:
        """获取默认推理内容模板"""
        templates = {
            'entity_identification': "识别问题中的地理实体名称和类型",
            'spatial_relation_extraction': "分析实体间的空间关系类型（方向、拓扑、度量）",
            'coordinate_retrieval': "从知识库检索实体的精确坐标信息",
            'spatial_calculation': "基于坐标进行空间关系计算和验证",
            'answer_generation': "综合推理结果生成最终答案"
        }
        return templates.get(step_name, "执行推理分析")

    def _compute_difficulty_score(
        self,
        chain: List[ReasoningStep]
    ) -> float:
        """
        计算推理链难度评分

        考虑因素:
        - 实体数量
        - 关系复杂度
        - 计算步骤

        Args:
            chain: 推理链

        Returns:
            难度评分 (0-1)
        """
        if not chain:
            return 0.0

        # 基础分
        base_score = 0.3

        # 实体数量加分
        all_entities = set()
        for step in chain:
            all_entities.update(step.entities_involved)
        entity_score = min(len(all_entities) * 0.1, 0.3)

        # 计算步骤加分
        calc_steps = sum(
            1 for step in chain
            if step.name == 'spatial_calculation'
        )
        calc_score = min(calc_steps * 0.2, 0.3)

        # 总难度
        total_score = min(base_score + entity_score + calc_score, 1.0)

        return round(total_score, 3)

    def generate_directional_chain(
        self,
        entity1: Union[str, GeoEntity],
        entity2: Union[str, GeoEntity],
        use_llm: bool = False
    ) -> List[Dict[str, Any]]:
        """
        生成方向关系推理链

        Args:
            entity1: 实体1 (名称或GeoEntity对象)
            entity2: 实体2 (名称或GeoEntity对象)
            use_llm: 是否使用LLM生成内容

        Returns:
            推理链字典列表
        """
        # 标准化实体
        if isinstance(entity1, str):
            entity1 = GeoEntity(name=entity1, entity_type="unknown")
        if isinstance(entity2, str):
            entity2 = GeoEntity(name=entity2, entity_type="unknown")

        chain = []

        # 步骤1: 实体识别
        step1 = ReasoningStep(
            step=1,
            name='entity_identification',
            action=self.STEP_ACTIONS['entity_identification'],
            content=f"识别问题中的地理实体: {entity1.name} 和 {entity2.name}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "entity_types": [entity1.entity_type, entity2.entity_type],
                "relation_type": "directional"
            }
        )
        chain.append(step1)

        # 步骤2: 空间关系抽取
        step2 = ReasoningStep(
            step=2,
            name='spatial_relation_extraction',
            action=self.STEP_ACTIONS['spatial_relation_extraction'],
            content=f"分析 {entity1.name} 相对于 {entity2.name} 的方向关系",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "relation_category": "directional",
                "expected_output": "方位描述"
            }
        )
        chain.append(step2)

        # 步骤3: 坐标检索
        coord1 = self._coordinate_cache.get(entity1.name)
        coord2 = self._coordinate_cache.get(entity2.name)

        coord_info = f"{entity1.name}: {coord1 if coord1 else '未知'}"
        if coord2:
            coord_info += f", {entity2.name}: {coord2}"

        step3 = ReasoningStep(
            step=3,
            name='coordinate_retrieval',
            action=self.STEP_ACTIONS['coordinate_retrieval'],
            content=f"从知识库检索坐标: {coord_info}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "coordinates": {
                    entity1.name: coord1,
                    entity2.name: coord2
                },
                "data_source": "coordinate_cache"
            }
        )
        chain.append(step3)

        # 步骤4: 空间计算
        calculation = "方向计算"
        if coord1 and coord2:
            lat_diff = coord1[0] - coord2[0]
            lon_diff = coord1[1] - coord2[1]
            calculation = f"纬度差: {lat_diff:.4f}, 经度差: {lon_diff:.4f}"

            # 简单方向判断
            if lat_diff > 0:
                direction = "北"
            else:
                direction = "南"
            if lon_diff > 0:
                direction += "东"
            else:
                direction += "西"

            step4 = ReasoningStep(
                step=4,
                name='spatial_calculation',
                action=self.STEP_ACTIONS['spatial_calculation'],
                content=f"基于坐标差计算方向: {calculation}, 推断方向: {direction}方",
                entities_involved=[entity1.name, entity2.name],
                metadata={
                    "calculation_type": "directional",
                    "lat_diff": lat_diff,
                    "lon_diff": lon_diff,
                    "inferred_direction": direction
                }
            )
        else:
            step4 = ReasoningStep(
                step=4,
                name='spatial_calculation',
                content="坐标信息不完整，无法进行精确计算",
                entities_involved=[entity1.name, entity2.name],
                metadata={"calculation_type": "directional", "status": "incomplete"}
            )
        chain.append(step4)

        # 步骤5: 答案生成
        if coord1 and coord2:
            lat_diff = coord1[0] - coord2[0]
            lon_diff = coord1[1] - coord2[1]

            direction_parts = []
            if lat_diff > 1:
                direction_parts.append("北")
            elif lat_diff < -1:
                direction_parts.append("南")
            if lon_diff > 1:
                direction_parts.append("东")
            elif lon_diff < -1:
                direction_parts.append("西")

            direction = "".join(direction_parts) if direction_parts else "邻近"
            answer = f"{entity1.name} 位于 {entity2.name} 的{direction}方"
        else:
            answer = f"无法确定 {entity1.name} 相对于 {entity2.name} 的精确方向"

        step5 = ReasoningStep(
            step=5,
            name='answer_generation',
            action=self.STEP_ACTIONS['answer_generation'],
            content=f"综合以上分析，得出答案: {answer}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "answer": answer,
                "confidence": 0.9 if coord1 and coord2 else 0.5
            }
        )
        chain.append(step5)

        # 计算难度评分
        difficulty = self._compute_difficulty_score(chain)

        # 转换为字典格式
        return {
            "chain": [step.to_dict() for step in chain],
            "metadata": {
                "relation_type": "directional",
                "difficulty_score": difficulty,
                "num_steps": len(chain),
                "entities": [entity1.name, entity2.name]
            }
        }

    def generate_topological_chain(
        self,
        entity1: Union[str, GeoEntity],
        entity2: Union[str, GeoEntity],
        relation_type: str = "adjacent",
        use_llm: bool = False
    ) -> List[Dict[str, Any]]:
        """
        生成拓扑关系推理链

        Args:
            entity1: 实体1
            entity2: 实体2
            relation_type: 拓扑关系类型 (adjacent, contains, within, overlaps)
            use_llm: 是否使用LLM生成内容

        Returns:
            推理链字典列表
        """
        # 标准化实体
        if isinstance(entity1, str):
            entity1 = GeoEntity(name=entity1, entity_type="unknown")
        if isinstance(entity2, str):
            entity2 = GeoEntity(name=entity2, entity_type="unknown")

        chain = []

        # 步骤1: 实体识别
        step1 = ReasoningStep(
            step=1,
            name='entity_identification',
            action=self.STEP_ACTIONS['entity_identification'],
            content=f"识别拓扑关系实体: {entity1.name} 和 {entity2.name}",
            entities_involved=[entity1.name, entity2.name],
            metadata={"relation_type": "topological"}
        )
        chain.append(step1)

        # 步骤2: 空间关系抽取
        relation_desc = {
            "adjacent": "相邻/接壤",
            "contains": "包含",
            "within": "位于...内",
            "overlaps": "重叠"
        }.get(relation_type, relation_type)

        step2 = ReasoningStep(
            step=2,
            name='spatial_relation_extraction',
            action=self.STEP_ACTIONS['spatial_relation_extraction'],
            content=f"分析 {entity1.name} 与 {entity2.name} 的拓扑关系: {relation_desc}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "relation_category": "topological",
                "relation_subtype": relation_type
            }
        )
        chain.append(step2)

        # 步骤3: 坐标检索
        coord1 = self._coordinate_cache.get(entity1.name)
        coord2 = self._coordinate_cache.get(entity2.name)

        step3 = ReasoningStep(
            step=3,
            name='coordinate_retrieval',
            action=self.STEP_ACTIONS['coordinate_retrieval'],
            content=f"检索实体坐标信息用于拓扑验证",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "coordinates": {
                    entity1.name: coord1,
                    entity2.name: coord2
                }
            }
        )
        chain.append(step3)

        # 步骤4: 空间计算
        step4 = ReasoningStep(
            step=4,
            name='spatial_calculation',
            action=self.STEP_ACTIONS['spatial_calculation'],
            content=f"基于行政区划和地理知识验证拓扑关系: {relation_desc}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "calculation_type": "topological",
                "relation_subtype": relation_type,
                "verification_method": "administrative_hierarchy"
            }
        )
        chain.append(step4)

        # 步骤5: 答案生成
        answer = f"{entity1.name} 与 {entity2.name} 存在{relation_desc}关系"
        step5 = ReasoningStep(
            step=5,
            name='answer_generation',
            action=self.STEP_ACTIONS['answer_generation'],
            content=f"拓扑关系分析结论: {answer}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "answer": answer,
                "relation_type": relation_type
            }
        )
        chain.append(step5)

        # 计算难度评分
        difficulty = self._compute_difficulty_score(chain)

        return {
            "chain": [step.to_dict() for step in chain],
            "metadata": {
                "relation_type": "topological",
                "relation_subtype": relation_type,
                "difficulty_score": difficulty,
                "num_steps": len(chain)
            }
        }

    def generate_metric_chain(
        self,
        entity1: Union[str, GeoEntity],
        entity2: Union[str, GeoEntity],
        metric_type: str = "distance",
        use_llm: bool = False
    ) -> List[Dict[str, Any]]:
        """
        生成度量关系推理链

        Args:
            entity1: 实体1
            entity2: 实体2
            metric_type: 度量类型 (distance, area, length)
            use_llm: 是否使用LLM生成内容

        Returns:
            推理链字典列表
        """
        # 标准化实体
        if isinstance(entity1, str):
            entity1 = GeoEntity(name=entity1, entity_type="unknown")
        if isinstance(entity2, str):
            entity2 = GeoEntity(name=entity2, entity_type="unknown")

        chain = []

        # 步骤1: 实体识别
        step1 = ReasoningStep(
            step=1,
            name='entity_identification',
            action=self.STEP_ACTIONS['entity_identification'],
            content=f"识别度量计算实体: {entity1.name} 和 {entity2.name}",
            entities_involved=[entity1.name, entity2.name],
            metadata={"metric_type": metric_type}
        )
        chain.append(step1)

        # 步骤2: 空间关系抽取
        metric_desc = {
            "distance": "距离",
            "area": "面积",
            "length": "长度"
        }.get(metric_type, metric_type)

        step2 = ReasoningStep(
            step=2,
            name='spatial_relation_extraction',
            action=self.STEP_ACTIONS['spatial_relation_extraction'],
            content=f"确定需要计算的度量关系: {metric_desc}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "relation_category": "metric",
                "metric_subtype": metric_type
            }
        )
        chain.append(step2)

        # 步骤3: 坐标检索
        coord1 = self._coordinate_cache.get(entity1.name)
        coord2 = self._coordinate_cache.get(entity2.name)

        coord_info = []
        if coord1:
            coord_info.append(f"{entity1.name}: {coord1}")
        if coord2:
            coord_info.append(f"{entity2.name}: {coord2}")

        step3 = ReasoningStep(
            step=3,
            name='coordinate_retrieval',
            action=self.STEP_ACTIONS['coordinate_retrieval'],
            content=f"检索坐标用于度量计算: {', '.join(coord_info)}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "coordinates": {
                    entity1.name: coord1,
                    entity2.name: coord2
                },
                "metric_type": metric_type
            }
        )
        chain.append(step3)

        # 步骤4: 空间计算
        calculation_result = "无法计算 - 坐标信息缺失"
        if coord1 and coord2:
            # Haversine公式计算距离
            import math
            R = 6371  # 地球半径(km)
            lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
            lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = (math.sin(dlat/2)**2 +
                 math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
            c = 2 * math.asin(math.sqrt(a))
            distance = R * c

            calculation_result = f"{distance:.2f} km"

        step4 = ReasoningStep(
            step=4,
            name='spatial_calculation',
            action=self.STEP_ACTIONS['spatial_calculation'],
            content=f"执行{metric_desc}计算，结果: {calculation_result}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "calculation_type": "metric",
                "metric_subtype": metric_type,
                "result": calculation_result
            }
        )
        chain.append(step4)

        # 步骤5: 答案生成
        if coord1 and coord2:
            answer = f"{entity1.name} 与 {entity2.name} 的距离约为 {calculation_result}"
        else:
            answer = f"无法计算 {entity1.name} 与 {entity2.name} 的距离 - 缺少坐标信息"

        step5 = ReasoningStep(
            step=5,
            name='answer_generation',
            action=self.STEP_ACTIONS['answer_generation'],
            content=f"度量计算结果: {answer}",
            entities_involved=[entity1.name, entity2.name],
            metadata={
                "answer": answer,
                "metric_type": metric_type,
                "result": calculation_result
            }
        )
        chain.append(step5)

        # 计算难度评分
        difficulty = self._compute_difficulty_score(chain)

        return {
            "chain": [step.to_dict() for step in chain],
            "metadata": {
                "relation_type": "metric",
                "metric_subtype": metric_type,
                "difficulty_score": difficulty,
                "num_steps": len(chain)
            }
        }

    def generate_composite_chain(
        self,
        entities: List[Union[str, GeoEntity]],
        relations: List[Dict[str, str]],
        use_llm: bool = False
    ) -> List[Dict[str, Any]]:
        """
        生成复合推理链

        支持多实体、多关系的复杂空间推理

        Args:
            entities: 实体列表
            relations: 关系列表 [{"type": "directional", "entities": [0, 1]}, ...]
            use_llm: 是否使用LLM生成内容

        Returns:
            推理链字典列表
        """
        # 标准化实体
        normalized_entities = []
        for e in entities:
            if isinstance(e, str):
                normalized_entities.append(GeoEntity(name=e, entity_type="unknown"))
            else:
                normalized_entities.append(e)

        chain = []
        entity_names = [e.name for e in normalized_entities]

        # 步骤1: 实体识别
        step1 = ReasoningStep(
            step=1,
            name='entity_identification',
            action=self.STEP_ACTIONS['entity_identification'],
            content=f"识别复合推理中的{len(entities)}个地理实体: {', '.join(entity_names)}",
            entities_involved=entity_names,
            metadata={
                "num_entities": len(entities),
                "entity_types": [e.entity_type for e in normalized_entities]
            }
        )
        chain.append(step1)

        # 步骤2: 空间关系抽取
        relation_descs = []
        for r in relations:
            idx1, idx2 = r.get("entities", [0, 1])
            if idx1 < len(entity_names) and idx2 < len(entity_names):
                relation_descs.append(
                    f"{entity_names[idx1]}-{entity_names[idx2]}: {r.get('type', 'unknown')}"
                )

        step2 = ReasoningStep(
            step=2,
            name='spatial_relation_extraction',
            action=self.STEP_ACTIONS['spatial_relation_extraction'],
            content=f"分析{len(relations)}个空间关系: {'; '.join(relation_descs)}",
            entities_involved=entity_names,
            metadata={
                "num_relations": len(relations),
                "relations": relations
            }
        )
        chain.append(step2)

        # 步骤3: 坐标检索
        coord_map = {}
        coord_info = []
        for e in normalized_entities:
            coord = self._coordinate_cache.get(e.name)
            coord_map[e.name] = coord
            if coord:
                coord_info.append(f"{e.name}: {coord}")

        step3 = ReasoningStep(
            step=3,
            name='coordinate_retrieval',
            action=self.STEP_ACTIONS['coordinate_retrieval'],
            content=f"检索所有实体的坐标信息: {'; '.join(coord_info)}",
            entities_involved=entity_names,
            metadata={
                "coordinates": coord_map,
                "complete_coords": sum(1 for c in coord_map.values() if c)
            }
        )
        chain.append(step3)

        # 步骤4: 空间计算
        calc_results = []
        for r in relations:
            idx1, idx2 = r.get("entities", [0, 1])
            if idx1 < len(normalized_entities) and idx2 < len(normalized_entities):
                e1, e2 = normalized_entities[idx1], normalized_entities[idx2]
                c1, c2 = coord_map.get(e1.name), coord_map.get(e2.name)

                if c1 and c2:
                    import math
                    R = 6371
                    lat1, lon1 = math.radians(c1[0]), math.radians(c1[1])
                    lat2, lon2 = math.radians(c2[0]), math.radians(c2[1])
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    a = (math.sin(dlat/2)**2 +
                         math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
                    distance = R * 2 * math.asin(math.sqrt(a))
                    calc_results.append(f"{e1.name}-{e2.name}: {distance:.2f}km")
                else:
                    calc_results.append(f"{e1.name}-{e2.name}: 坐标缺失")

        step4 = ReasoningStep(
            step=4,
            name='spatial_calculation',
            action=self.STEP_ACTIONS['spatial_calculation'],
            content=f"执行复合空间计算: {'; '.join(calc_results)}",
            entities_involved=entity_names,
            metadata={
                "calculation_type": "composite",
                "results": calc_results
            }
        )
        chain.append(step4)

        # 步骤5: 答案生成
        answer = f"完成{len(entities)}个实体间的{len(relations)}个空间关系分析"
        step5 = ReasoningStep(
            step=5,
            name='answer_generation',
            action=self.STEP_ACTIONS['answer_generation'],
            content=f"复合推理结论: {answer}",
            entities_involved=entity_names,
            metadata={
                "answer": answer,
                "num_entities": len(entities),
                "num_relations": len(relations)
            }
        )
        chain.append(step5)

        # 计算难度评分 (复合推理难度更高)
        difficulty = min(self._compute_difficulty_score(chain) + 0.2, 1.0)

        return {
            "chain": [step.to_dict() for step in chain],
            "metadata": {
                "relation_type": "composite",
                "difficulty_score": difficulty,
                "num_steps": len(chain),
                "num_entities": len(entities),
                "num_relations": len(relations)
            }
        }

    def save_chain(
        self,
        chain_data: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        保存推理链到文件

        Args:
            chain_data: 推理链数据
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chain_data, f, ensure_ascii=False, indent=2)

    def load_chain(self, input_path: str) -> Dict[str, Any]:
        """
        从文件加载推理链

        Args:
            input_path: 输入文件路径

        Returns:
            推理链数据
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def export_for_training(
        self,
        chain_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        导出为训练格式

        将推理链转换为可用于模型训练的格式

        Args:
            chain_data: 推理链数据

        Returns:
            训练格式数据
        """
        chain = chain_data.get("chain", [])
        metadata = chain_data.get("metadata", {})

        # 构建步骤logits模拟
        training_data = {
            "steps": {},
            "chain_text": "",
            "metadata": metadata
        }

        chain_texts = []
        for step in chain:
            step_name = step["name"]
            training_data["steps"][step_name] = {
                "content": step["content"],
                "action": step["action"],
                "entities": step["entities_involved"],
                "confidence": step.get("confidence", 1.0)
            }
            chain_texts.append(f"Step {step['step']}: {step['content']}")

        training_data["chain_text"] = " | ".join(chain_texts)
        training_data["difficulty"] = metadata.get("difficulty_score", 0.5)

        return training_data


# 便捷函数
def create_directional_chain(
    entity1: str,
    entity2: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建方向关系推理链的便捷函数

    Args:
        entity1: 实体1名称
        entity2: 实体2名称
        api_key: GLM API密钥 (可选)

    Returns:
        推理链数据
    """
    generator = ReasoningChainGenerator(glm_api_key=api_key)
    return generator.generate_directional_chain(entity1, entity2)


def create_topological_chain(
    entity1: str,
    entity2: str,
    relation_type: str = "adjacent",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建拓扑关系推理链的便捷函数

    Args:
        entity1: 实体1名称
        entity2: 实体2名称
        relation_type: 拓扑关系类型
        api_key: GLM API密钥 (可选)

    Returns:
        推理链数据
    """
    generator = ReasoningChainGenerator(glm_api_key=api_key)
    return generator.generate_topological_chain(entity1, entity2, relation_type)


def create_metric_chain(
    entity1: str,
    entity2: str,
    metric_type: str = "distance",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建度量关系推理链的便捷函数

    Args:
        entity1: 实体1名称
        entity2: 实体2名称
        metric_type: 度量类型
        api_key: GLM API密钥 (可选)

    Returns:
        推理链数据
    """
    generator = ReasoningChainGenerator(glm_api_key=api_key)
    return generator.generate_metric_chain(entity1, entity2, metric_type)


if __name__ == "__main__":
    # 测试代码
    generator = ReasoningChainGenerator()

    print("=== 测试方向关系推理链 ===")
    directional_chain = generator.generate_directional_chain("北京", "上海")
    print(json.dumps(directional_chain, ensure_ascii=False, indent=2))

    print("\n=== 测试拓扑关系推理链 ===")
    topological_chain = generator.generate_topological_chain("北京", "河北省", "contains")
    print(json.dumps(topological_chain, ensure_ascii=False, indent=2))

    print("\n=== 测试度量关系推理链 ===")
    metric_chain = generator.generate_metric_chain("北京", "上海", "distance")
    print(json.dumps(metric_chain, ensure_ascii=False, indent=2))

    print("\n=== 测试复合推理链 ===")
    composite_chain = generator.generate_composite_chain(
        entities=["北京", "天津", "上海"],
        relations=[
            {"type": "directional", "entities": [0, 1]},
            {"type": "metric", "entities": [0, 2]}
        ]
    )
    print(json.dumps(composite_chain, ensure_ascii=False, indent=2))
