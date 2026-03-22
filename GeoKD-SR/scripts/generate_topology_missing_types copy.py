#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拓扑数据补充脚本 V2.0
生成 contains 和 overlap 类型的拓扑推理数据

作者: Claude
日期: 2026-03-12
"""

import json
import os
import sys
import time
import random
import argparse
import re
import getpass
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

# 尝试导入zhipuai
try:
    from zhipuai import ZhipuAI
except ImportError:
    print("警告: zhipuai未安装，请运行: pip install zhipuai")
    ZhipuAI = None

# ============================================================================
# 1. 配置区
# ============================================================================

# API配置
API_KEY = os.environ.get("ZHIPUAI_API_KEY", "")
MODEL_NAME = "glm-4-plus"  # 使用GLM-4-Plus模型

# 路径配置
BASE_DIR = Path(__file__).parent.parent
ENTITY_DB_PATH = BASE_DIR / "data" / "final" / "entity_database_expanded_v3_fixed.json"
OUTPUT_DIR = BASE_DIR / "data" / "final"
OUTPUT_FILE = OUTPUT_DIR / "topology_supplement_v3.jsonl"
PROGRESS_FILE = OUTPUT_DIR / "generation_progress_v3.json"
REPORT_FILE = OUTPUT_DIR / "generation_report_v3.json"

# 常量配置
MAX_RETRIES = 5
RETRY_DELAY = 60  # 429错误等待时间(秒)
TIMEOUT = 180  # API超时时间(秒)
CHECKPOINT_INTERVAL = 20  # 每20条保存一次进度

# 难度分布配置
DEFAULT_DIFFICULTY_DISTRIBUTION = {
    "easy": 0.3,
    "medium": 0.5,
    "hard": 0.2
}

# 难度分数范围
DIFFICULTY_SCORE_RANGES = {
    "easy": (2.0, 2.5),
    "medium": (2.6, 3.5),
    "hard": (3.6, 4.5)
}

# 推理链步骤名称
REQUIRED_STEPS = [
    "entity_identification",
    "spatial_relation_extraction",
    "coordinate_retrieval",
    "spatial_calculation",
    "answer_generation"
]

REQUIRED_ACTIONS = [
    "extract_entities",
    "classify_relation",
    "infer_entity_to_token",
    "determine_topology",
    "generate_answer"
]

# ============================================================================
# 2. 提示词模板
# ============================================================================

CONTAINS_PROMPT_TEMPLATE = """【任务】生成一个中国地理拓扑包含关系推理问题

【角色定位】
你是一位资深的地理空间数据集设计专家，拥有以下专业能力：
1. 精通中国地理知识，包括省市区划、山川河流、地标建筑等
2. 擅长设计多层次、多维度的地理空间推理问题
3. 能够根据不同难度级别设计相应复杂度的地理问题
4. 熟悉拓扑关系（contains、adjacent、overlap、disjoint等）的空间推理

你的任务是设计高质量的地理空间推理数据集，确保：
- 问题表述多样化和自然化
- 不同难度的问题具有明显的复杂度差异
- 推理过程清晰、逻辑严密
- 地理信息准确、坐标数据合理

【背景知识】
- contains关系定义：A包含B，表示B完全位于A的边界范围内
- Contains关系描述的是一個几何对象完全将另一个几何对象囊括在其内部（包括边界）的情形
- 典型场景：省份包含城市、省份包含地标、城市包含地标

【输入参数】
- 容器实体：{container_name}（类型：{container_type}，坐标：{container_coords}）
- 被包含实体：{contained_name}（类型：{contained_type}，坐标：{contained_coords}）
- 拓扑子类型：contains
- 难度级别：{difficulty}

【数据格式规范】严格按照以下JSON格式输出，不要添加任何额外内容：

{{
  "id": "geosr_topological_{{序号:05d}}",
  "spatial_relation_type": "topological",
  "topology_subtype": "contains",
  "question": "生成的问题文本（15-80字符）",
  "answer": "简短明确答案（5-30字符）",
  "reasoning_chain": [
    {{"step": 1, "name": "entity_identification", "action": "extract_entities", "content": "详细识别实体信息（50-100字符，包含地理位置、行政级别、地理特征等）", "entities_involved": ["{container_name}", "{contained_name}"]}},
    {{"step": 2, "name": "spatial_relation_extraction", "action": "classify_relation", "content": "分析空间关系类型（40-80字符，解释为什么是拓扑关系）", "relation_type": "topological"}},
    {{"step": 3, "name": "coordinate_retrieval", "action": "infer_entity_to_token", "content": "获取坐标并解释地理意义（60-100字符，包含经纬度、相对位置、地理分区等）", "coordinates": "根据实际坐标填写"}},
    {{"step": 4, "name": "spatial_calculation", "action": "determine_topology", "content": "详细分析包含关系（60-100字符，包含行政隶属、空间范围、边界关系等）", "calculation_result": "contains"}},
    {{"step": 5, "name": "answer_generation", "action": "generate_answer", "content": "生成简短答案（30-50字符）", "final_answer": "简短直接答案"}}
  ],
  "entities": [
    {{"name": "{container_name}", "type": "{container_type}", "coords": "[经度, 纬度]"}},
    {{"name": "{contained_name}", "type": "{contained_type}", "coords": "[经度, 纬度]"}}
  ],
  "spatial_tokens": ["实体1", "实体2", "包含", "位于", "其他关键词"],
  "entity_to_token": "根据question中实体位置填写char_start/char_end/token_indices",
}}

【字段约束】
1. id格式：必须是"geosr_topological_XXXXX"，XXXXX为5位数字
2. coords格式：[经度, 纬度]，经度范围73-135，纬度范围18-54
3. difficulty：easy/medium/hard
4. difficulty_score：easy=2.0-2.5, medium=2.6-3.5, hard=3.6-4.5
5. reasoning_chain必须严格5步，每步content应详细结构化、富含地理知识
6. answer必须简短明确（5-30字符），如"是的，包含。"或"不包含。"
7. spatial_tokens：4-8个关键词
8. entity_to_token：char_start/char_end/token_indices必须与question中的实际位置匹配

【参考示例 - 省份包含城市】
输入：容器=河北省，被包含=石家庄
输出：
{{
  "id": "geosr_topological_00001",
  "spatial_relation_type": "topological",
  "topology_subtype": "contains",
  "question": "石家庄是否位于河北省境内？",
  "answer": "是的，石家庄位于河北省境内。",
  "reasoning_chain": [
    {{"step": 1, "name": "entity_identification", "action": "extract_entities", "content": "识别问题中的地理实体：河北省，位于中国华北地区，省会石家庄，东临渤海，西接太行山，北依燕山，是中国唯一兼有高原、山地、丘陵、平原、湖泊和海滨的省份；石家庄市，河北省省会，位于河北省中南部，太行山东麓，是京津冀地区重要的中心城市之一。", "entities_involved": ["河北省", "石家庄"]}},
    {{"step": 2, "name": "spatial_relation_extraction", "action": "classify_relation", "content": "问题询问'位于...境内'，涉及行政区划的包含关系判断。'境内'一词表明需要判断城市是否在省份的行政边界范围内，这属于拓扑空间关系中的contains（包含）关系类型。", "relation_type": "topological"}},
    {{"step": 3, "name": "coordinate_retrieval", "action": "infer_entity_to_token", "content": "检索实体坐标信息：河北省地理中心坐标约为(114.51°E, 38.04°N)，位于华北平原北部；石家庄市中心坐标约为(114.51°E, 38.04°N)，位于北纬37°27'-38°47'，东经113°30'-115°20'之间。从经纬度看，石家庄完全落在河北省的地理范围内。", "coordinates": {{"河北省": [114.5149, 38.0428], "石家庄": [114.5149, 38.0428]}}}},
    {{"step": 4, "name": "spatial_calculation", "action": "determine_topology", "content": "分析空间包含关系：石家庄市是河北省的省会城市，行政区划上直接隶属于河北省。从空间拓扑角度分析，石家庄市的行政边界完全被河北省的行政边界所包围，不存在任何边界交叉或外溢的情况。根据中国行政区划体系，地级市必须完整包含在其所属省份范围内。因此，河北省与石家庄市之间存在明确的contains（包含）拓扑关系。", "calculation_result": "contains"}},
    {{"step": 5, "name": "answer_generation", "action": "generate_answer", "content": "基于行政区划和空间拓扑分析，石家庄市完全位于河北省境内，构成包含关系。", "final_answer": "是的，石家庄位于河北省境内。"}}
  ],
  "entities": [{{"name": "河北省", "type": "province", "coords": [114.5149, 38.0428]}}, {{"name": "石家庄", "type": "city", "coords": [114.5149, 38.0428]}}],
  "spatial_tokens": ["河北省", "石家庄", "位于", "境内", "包含", "行政"],
  "entity_to_token": {{"河北省": {{"char_start": 7, "char_end": 10, "token_indices": [7, 8, 9]}}, "石家庄": {{"char_start": 0, "char_end": 3, "token_indices": [0, 1, 2]}}}},
  "difficulty": "easy",
  "difficulty_score": 2.4
}}

【注意事项】
1. question具有多样性，满足【问题多样性要求】：**问句结构多样性**、 **背景信息多样性**、**语言表达多样性**，包含实体名称
2. answer必须简短明确（5-30字符），如"是的，位于XX境内。"
3. reasoning_chain每步content应详细结构化，包含地理知识（位置、面积、行政级别、地理特征等）
4. reasoning_chain第4步必须包含详细的拓扑关系分析
5. final_answer必须与answer字段一致
6. 确保所有坐标在中国境内（经度73-135，纬度18-54）
7. entity_to_token的位置必须与question中的实际位置匹配

现在请根据输入参数生成一条contains类型的数据："""


OVERLAP_PROMPT_TEMPLATE = """【任务】生成一个中国地理拓扑交叉关系推理问题

【角色定位】
你是一位资深的地理空间数据集设计专家，拥有以下专业能力：
1. 精通中国地理知识，包括省市区划、山川河流、地标建筑等
2. 擅长设计多层次、多维度的地理空间推理问题
3. 能够根据不同难度级别设计相应复杂度的地理问题
4. 熟悉拓扑关系（contains、adjacent、overlap、disjoint等）的空间推理

你的任务是设计高质量的地理空间推理数据集，确保：
- 问题表述多样化和自然化
- 不同难度的问题具有明显的复杂度差异
- 推理过程清晰、逻辑严密
- 地理信息准确、坐标数据合理

【背景知识】
- overlap关系定义：A与B交叉，表示两个地理实体的空间范围存在交集
- Overlap关系描述的是两个同维度的几何对象在内部共享一部分空间，但彼此又不相互包含的情形。

【输入参数】
- 实体1：{entity1_name}（类型：{entity1_type}，坐标：{entity1_coords}）
- 实体2：{entity2_name}（类型：{entity2_type}，坐标：{entity2_coords}）
- 交叉信息：{overlap_info}
- 拓扑子类型：overlap
- 难度级别：{difficulty}

【数据格式规范】严格按照以下JSON格式输出：

{{
  "id": "geosr_topological_{{序号:05d}}",
  "spatial_relation_type": "topological",
  "topology_subtype": "overlap",
  "question": "生成的问题文本（15-80字符）",
  "answer": "简短明确答案（5-30字符）",
  "reasoning_chain": [
    {{"step": 1, "name": "entity_identification", "action": "extract_entities", "content": "详细识别实体信息（50-100字符，包含地理位置、地理特征、空间范围等）", "entities_involved": ["{entity1_name}", "{entity2_name}"]}},
    {{"step": 2, "name": "spatial_relation_extraction", "action": "classify_relation", "content": "分析空间关系类型（40-80字符，解释为什么是overlap关系）", "relation_type": "topological"}},
    {{"step": 3, "name": "coordinate_retrieval", "action": "infer_entity_to_token", "content": "获取坐标并解释地理意义（60-100字符，包含流经范围、跨越区域等）", "coordinates": {{"{entity1_name}": "坐标1", "{entity2_name}": "坐标2"}}}},
    {{"step": 4, "name": "spatial_calculation", "action": "determine_topology", "content": "详细分析交叉关系（60-100字符，包含空间交集、边界关系等）", "calculation_result": "overlap"}},
    {{"step": 5, "name": "answer_generation", "action": "generate_answer", "content": "生成简短答案（30-50字符）", "final_answer": "简短直接答案"}}
  ],
  "entities": [
    {{"name": "{entity1_name}", "type": "{entity1_type}", "coords": "坐标1"}},
    {{"name": "{entity2_name}", "type": "{entity2_type}", "coords": "坐标2"}}
  ],
  "spatial_tokens": ["实体1", "实体2", "流经", "交叉", "其他关键词"],
  "entity_to_token": "根据question中实体位置填写char_start/char_end/token_indices",
  "difficulty": "{difficulty}",
  "difficulty_score": "根据难度填写2.0-4.5之间的数值"
}}

【字段约束】
1. id格式：必须是"geosr_topological_XXXXX"
2. coords格式：[经度, 纬度]，经度范围73-135，纬度范围18-54
3. difficulty：easy/medium/hard
4. difficulty_score：easy=2.0-2.5, medium=2.6-3.5, hard=3.6-4.5
5. reasoning_chain必须严格5步，每步content应详细结构化、富含地理知识
6. answer必须简短明确（5-30字符）
7. spatial_tokens：4-8个关键词
8. entity_to_token：char_start/char_end/token_indices必须与question中的实际位置匹配
9.question具有多样性，满足【问题多样性要求】：**问句结构多样性**、 **背景信息多样性**、**语言表达多样性**

【参考示例 - 河流流经省份】
输入：实体1=长江，实体2=湖北省，交叉信息=长江流经湖北省
输出：
{{
  "id": "geosr_topological_00004",
  "spatial_relation_type": "topological",
  "topology_subtype": "overlap",
  "question": "长江是否流经湖北省？",
  "answer": "是的，流经。",
  "reasoning_chain": [
    {{"step": 1, "name": "entity_identification", "action": "extract_entities", "content": "识别问题中的地理实体：长江，中国第一长河，世界第三长河，发源于青藏高原唐古拉山脉，流经青海、西藏、四川、云南、重庆、湖北、湖南、江西、安徽、江苏、上海11个省级行政区，全长约6300公里，最终注入东海；湖北省，位于中国中部，长江中游，省会武汉，因位于洞庭湖以北而得名，是长江流经的重要省份之一。", "entities_involved": ["长江", "湖北省"]}},
    {{"step": 2, "name": "spatial_relation_extraction", "action": "classify_relation", "content": "问题询问'是否流经'，涉及判断线状水系与面状行政区划的空间交集关系。'流经'意味着河流的河道与省域存在空间交叉，这属于拓扑空间关系中的overlap（交叉）关系类型。", "relation_type": "topological"}},
    {{"step": 3, "name": "coordinate_retrieval", "action": "infer_entity_to_token", "content": "检索实体空间信息：长江自西向东流，在湖北段的河道长度约1061公里，流经湖北的主要江段称为荆江，长江湖北段坐标范围约为东经108°-116°，北纬29°-33°；湖北省位于长江中游，地理中心坐标约为(112.31°E, 30.79°N)。从空间位置分析，长江河道明显穿过湖北省境内。", "coordinates": {{"长江": [121.5, 31.2], "湖北省": [114.3055, 30.5928]}}}},
    {{"step": 4, "name": "spatial_calculation", "action": "determine_topology", "content": "分析空间交叉关系：长江从重庆进入湖北省，流经宜昌、荆州、武汉、黄冈等地后进入江西省。在湖北省境内，长江形成了著名的荆江河段，是长江防洪的重点区域。从空间拓扑角度分析，长江河道作为线状地理实体，其湖北段与湖北省行政边界存在明显的空间交集，河道穿过省域腹地。因此，长江与湖北省之间存在明确的overlap（交叉）拓扑关系。", "calculation_result": "overlap"}},
    {{"step": 5, "name": "answer_generation", "action": "generate_answer", "content": "基于河流流经路线和空间位置分析，长江确实流经湖北省。", "final_answer": "是的，流经。"}}
  ],
  "entities": [{{"name": "长江", "type": "river", "coords": [121.5, 31.2]}}, {{"name": "湖北省", "type": "province", "coords": [114.3055, 30.5928]}}],
  "spatial_tokens": ["长江", "湖北省", "流经", "交叉", "荆江", "中游"],
  "entity_to_token": {{"长江": {{"char_start": 0, "char_end": 2, "token_indices": [0, 1]}}, "湖北省": {{"char_start": 5, "char_end": 8, "token_indices": [5, 6, 7]}}}},
  "difficulty": "easy",
  "difficulty_score": 2.8
}}

【注意事项】
1. questionquestion具有多样性，满足【问题多样性要求】：**问句结构多样性**、 **背景信息多样性**、**语言表达多样性**，包含两个实体名称
2. answer必须简短明确（5-30字符），如"是的，流经。"或"不流经。"
3. reasoning_chain每步content应详细结构化，包含地理知识（流经范围、跨越区域、地理特征等）
4. reasoning_chain第4步必须包含详细的拓扑关系分析
5. 确保所有坐标在中国境内
6. entity_to_token的位置必须与question中的实际位置匹配
7.必须注意overlap不是contains，如果两个实体间没有各自独立的区域则不属于overlap关系，需要重新为我提供符合关系的实体

现在请根据生成一条overlap类型的数据："""


# ============================================================================
# 3. 实体管理类
# ============================================================================

class EntityManager:
    """实体数据库管理类"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db = None
        self.lookup = {}

    def load_database(self) -> bool:
        """加载实体数据库"""
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                self.db = json.load(f)
            self._build_entity_lookup()
            return True
        except Exception as e:
            print(f"加载数据库失败: {e}")
            return False

    def _build_entity_lookup(self):
        """构建实体查找索引"""
        self.lookup = {}
        for entity_type in ['provinces', 'cities', 'landmarks', 'rivers', 'mountains', 'lakes', 'regions']:
            if entity_type in self.db['entities']:
                for entity in self.db['entities'][entity_type]:
                    key = (entity['name'], entity['type'])
                    self.lookup[key] = entity
        print(f"实体索引构建完成，共 {len(self.lookup)} 个实体")

    def find_entity(self, name: str, entity_type: str = None) -> Optional[Dict]:
        """根据名称和类型查找实体"""
        if entity_type:
            return self.lookup.get((name, entity_type))
        # 尝试所有类型
        for t in ['province', 'city', 'landmark', 'river', 'mountain', 'lake', 'region']:
            result = self.lookup.get((name, t))
            if result:
                return result
        return None

    def find_province(self, name: str) -> Optional[Dict]:
        """查找省份（处理名称变体）"""
        # 直接查找
        result = self.find_entity(name, 'province')
        if result:
            return result
        # 尝试去掉"省"字
        name_without_suffix = name.replace('省', '').replace('自治区', '').replace('特别行政区', '')
        for entity in self.db['entities'].get('provinces', []):
            entity_name_clean = entity['name'].replace('省', '').replace('自治区', '').replace('特别行政区', '')
            if entity_name_clean == name_without_suffix:
                return entity
        return None

    def find_city(self, name: str) -> Optional[Dict]:
        """查找城市"""
        return self.find_entity(name, 'city')

    def find_landmark(self, name: str) -> Optional[Dict]:
        """查找地标"""
        return self.find_entity(name, 'landmark')

    def get_entity_info(self, entity: Dict) -> Dict:
        """获取实体完整信息"""
        return {
            'name': entity.get('name', ''),
            'type': entity.get('type', ''),
            'coords': entity.get('coords', [0, 0])
        }


# ============================================================================
# 4. 实体对生成器类
# ============================================================================

class EntityPairGenerator:
    """实体对生成器"""

    def __init__(self, entity_manager: EntityManager):
        self.em = entity_manager

    def generate_contains_pairs(self) -> List[Dict]:
        """生成contains实体对"""
        pairs = []
        entities = self.em.db['entities']

        # 1. 省份包含城市
        for province in entities.get('provinces', []):
            province_info = self.em.get_entity_info(province)
            for city_name in province.get('cities', []):
                city = self.em.find_city(city_name)
                if city:
                    city_info = self.em.get_entity_info(city)
                    pairs.append({
                        'container': province_info,
                        'contained': city_info,
                        'pair_type': 'province-city'
                    })

        # 2. 省份包含地标
        for province in entities.get('provinces', []):
            province_info = self.em.get_entity_info(province)
            for landmark_name in province.get('contains_landmarks', []):
                landmark = self.em.find_landmark(landmark_name)
                if landmark:
                    landmark_info = self.em.get_entity_info(landmark)
                    pairs.append({
                        'container': province_info,
                        'contained': landmark_info,
                        'pair_type': 'province-landmark'
                    })

        # 3. 城市包含地标
        for landmark in entities.get('landmarks', []):
            city_name = landmark.get('city')
            if city_name:
                city = self.em.find_city(city_name)
                if city:
                    city_info = self.em.get_entity_info(city)
                    landmark_info = self.em.get_entity_info(landmark)
                    pairs.append({
                        'container': city_info,
                        'contained': landmark_info,
                        'pair_type': 'city-landmark'
                    })

        print(f"生成contains实体对: {len(pairs)} 对")
        return pairs

    def generate_overlap_pairs(self) -> List[Dict]:
        """生成overlap实体对"""
        pairs = []
        entities = self.em.db['entities']

        # 1. 河流流经省份
        for river in entities.get('rivers', []):
            river_info = self.em.get_entity_info(river)
            for province_name in river.get('provinces', []):
                province = self.em.find_province(province_name)
                if province:
                    province_info = self.em.get_entity_info(province)
                    pairs.append({
                        'entity1': river_info,
                        'entity2': province_info,
                        'overlap_info': f"{river['name']}流经{province_name}",
                        'pair_type': 'river-province'
                    })

        # 2. 山脉跨越省份
        for mountain in entities.get('mountains', []):
            mountain_info = self.em.get_entity_info(mountain)
            for province_name in mountain.get('provinces', []):
                province = self.em.find_province(province_name)
                if province:
                    province_info = self.em.get_entity_info(province)
                    pairs.append({
                        'entity1': mountain_info,
                        'entity2': province_info,
                        'overlap_info': f"{mountain['name']}跨越{province_name}",
                        'pair_type': 'mountain-province'
                    })

        # 3. 湖泊位于省份
        for lake in entities.get('lakes', []):
            lake_info = self.em.get_entity_info(lake)
            for province_name in lake.get('provinces', []):
                province = self.em.find_province(province_name)
                if province:
                    province_info = self.em.get_entity_info(province)
                    pairs.append({
                        'entity1': lake_info,
                        'entity2': province_info,
                        'overlap_info': f"{lake['name']}位于{province_name}",
                        'pair_type': 'lake-province'
                    })

        # 4. 区域包含省份
        for region in entities.get('regions', []):
            region_info = self.em.get_entity_info(region)
            for province_name in region.get('provinces', []):
                province = self.em.find_province(province_name)
                if province:
                    province_info = self.em.get_entity_info(province)
                    pairs.append({
                        'entity1': region_info,
                        'entity2': province_info,
                        'overlap_info': f"{region['name']}包含{province_name}",
                        'pair_type': 'region-province'
                    })

        print(f"生成overlap实体对: {len(pairs)} 对")
        return pairs


# ============================================================================
# 5. GLM客户端类
# ============================================================================

class GLMClient:
    """GLM API客户端"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or API_KEY or self._load_api_key()
        if not self.api_key:
            raise ValueError("未设置API密钥，请设置ZHIPUAI_API_KEY环境变量或使用--api-key参数")
        if ZhipuAI is None:
            raise ImportError("zhipuai未安装，请运行: pip install zhipuai")
        self.client = ZhipuAI(api_key=self.api_key)
        print(f"GLM客户端初始化成功，使用模型: {MODEL_NAME}")

    def _load_api_key(self) -> Optional[str]:
        """从多种来源加载API密钥"""
        # 1. 环境变量
        api_key = os.environ.get("ZHIPUAI_API_KEY")
        if api_key:
            return api_key

        # 2. .env文件
        for env_path in [Path(".env"), Path(__file__).parent.parent / ".env"]:
            if env_path.exists():
                try:
                    with open(env_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("ZHIPUAI_API_KEY="):
                                return line.split("=", 1)[1].strip().strip('"').strip("'")
                except Exception:
                    pass

        # 3. 交互式输入
        try:
            print("\n未找到API密钥配置")
            api_key = getpass.getpass("请输入智谱API密钥（输入后不会显示）: ").strip()
            if api_key:
                return api_key
        except Exception:
            pass

        return None

    def generate(self, prompt: str, max_retries: int = MAX_RETRIES) -> Optional[str]:
        """调用API生成内容"""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2000
                )
                return response.choices[0].message.content
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate" in error_str.lower():
                    wait_time = RETRY_DELAY * (attempt + 1)
                    print(f"触发限流，等待 {wait_time} 秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                elif attempt < max_retries - 1:
                    wait_time = 5 * (attempt + 1)
                    print(f"API调用失败: {e}，等待 {wait_time} 秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"API调用失败，已达到最大重试次数: {e}")
                    return None
        return None

    def parse_json_response(self, response: str) -> Optional[Dict]:
        """解析JSON响应 - 使用更健壮的方法"""
        if not response:
            return None

        # 方法1: 尝试提取```json...```代码块
        json_str = None
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1).strip()

        # 方法2: 如果没有代码块，找到{...}的范围
        if not json_str:
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx + 1]

        if not json_str:
            return None

        # 预处理JSON字符串 - 使用字符遍历方式更健壮地处理
        def preprocess_json(s: str) -> str:
            # 移除JavaScript注释
            s = re.sub(r'//.*?$', '', s, flags=re.MULTILINE)
            s = re.sub(r'/\*[\s\S]*?\*/', '', s)

            # 修复尾部逗号
            s = re.sub(r',(\s*[}\]])', r'\1', s)

            # 修复中文引号
            s = s.replace('"', '"').replace('"', '"')
            s = s.replace(''', "'").replace(''', "'")

            # 关键修复：遍历字符串，转义JSON字符串值中的特殊字符
            result = []
            i = 0
            in_string = False
            while i < len(s):
                char = s[i]
                if char == '"' and (i == 0 or s[i-1] != '\\'):
                    in_string = not in_string
                    result.append(char)
                elif in_string:
                    # 在字符串内部，转义特殊字符
                    if char == '\n':
                        result.append('\\n')
                    elif char == '\r':
                        result.append('\\r')
                    elif char == '\t':
                        result.append('\\t')
                    elif char == '"' and s[i-1] != '\\':
                        result.append('\\"')
                    else:
                        result.append(char)
                else:
                    result.append(char)
                i += 1

            s = ''.join(result)

            # 移除控制字符
            s = re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', s)

            return s.strip()

        json_str = preprocess_json(json_str)

        # 尝试解析
        try:
                return json.loads(json_str)
        except json.JSONDecodeError as e:
                print(f"JSON解析失败: {e}")
                # 尝试使用更激进的方法: 将响应转换为Python字典
                try:
                    return self._parse_json_with_regex(json_str)
                except Exception as e2:
                    print(f"正则解析也失败: {e2}")
                    return None

    def _parse_json_with_regex(self, json_str: str) -> Optional[Dict]:
        """使用正则表达式提取JSON字段"""
        result = {}

        try:
                # 提取基本字段
                id_match = re.search(r'"id":\s*"([^"]+)"', json_str)
                if id_match:
                    result['id'] = id_match.group(1)

                # 提取spatial_relation_type
                srt_match = re.search(r'"spatial_relation_type":\s*"([^"]+)"', json_str)
                if srt_match:
                    result['spatial_relation_type'] = srt_match.group(1)

                # 提取topology_subtype
                ts_match = re.search(r'"topology_subtype":\s*"([^"]+)"', json_str)
                if ts_match:
                    result['topology_subtype'] = ts_match.group(1)

                # 提取question
                q_match = re.search(r'"question":\s*"([^"]*(?:\\.[^"]*)*?"', json_str)
                if q_match:
                    result['question'] = q_match.group(1)

                # 提取answer
                a_match = re.search(r'"answer":\s*"([^"]*(?:\\.[^"]*)*?"', json_str)
                if a_match:
                    result['answer'] = a_match.group(1)

                # 提取difficulty
                d_match = re.search(r'"difficulty":\s*"([^"]+)"', json_str)
                if d_match:
                    result['difficulty'] = d_match.group(1)

                # 提取difficulty_score
                ds_match = re.search(r'"difficulty_score":\s*([\d.]+)', json_str)
                if ds_match:
                    result['difficulty_score'] = float(ds_match.group(1))

                # 如果成功提取了基本字段，返回结果
                if len(result) >= 6:
                    # 添加默认的reasoning_chain和其他字段
                    if 'reasoning_chain' not in result:
                        result['reasoning_chain'] = []
                    if 'entities' not in result:
                        result['entities'] = []
                    if 'spatial_tokens' not in result:
                        result['spatial_tokens'] = []
                    if 'entity_to_token' not in result:
                        result['entity_to_token'] = {}
                    return result

        except Exception:
            return None


# ============================================================================
# 6. 数据验证器类
# ============================================================================

class DataValidator:
    """数据验证器"""

    @staticmethod
    def validate_required_fields(data: Dict) -> Tuple[bool, List[str]]:
        """验证必需字段"""
        required = [
            "id", "spatial_relation_type", "topology_subtype",
            "question", "answer", "reasoning_chain",
            "entities", "spatial_tokens", "entity_to_token",
            "difficulty", "difficulty_score"
        ]
        missing = [f for f in required if f not in data]
        return len(missing) == 0, missing

    @staticmethod
    def validate_coords(coords: List) -> Tuple[bool, str]:
        """验证坐标范围"""
        if not isinstance(coords, list) or len(coords) != 2:
            return False, f"坐标格式错误: {coords}"
        lon, lat = coords
        if not (73.0 <= lon <= 135.0):
            return False, f"经度超出范围: {lon}"
        if not (18.0 <= lat <= 54.0):
            return False, f"纬度超出范围: {lat}"
        return True, ""

    @staticmethod
    def validate_reasoning_chain(chain: List) -> Tuple[bool, List[str]]:
        """验证推理链结构"""
        errors = []
        if not isinstance(chain, list):
            return False, ["reasoning_chain不是列表"]
        if len(chain) != 5:
            errors.append(f"推理链必须5步，实际{len(chain)}步")

        for i, step in enumerate(chain):
            if not isinstance(step, dict):
                errors.append(f"步骤{i+1}不是字典")
                continue
            if step.get('step') != i + 1:
                errors.append(f"步骤{i+1}序号错误: {step.get('step')}")
            if step.get('name') != REQUIRED_STEPS[i]:
                errors.append(f"步骤{i+1}名称错误: {step.get('name')}")
            if 'content' not in step:
                errors.append(f"步骤{i+1}缺少content字段")

        return len(errors) == 0, errors

    @staticmethod
    def validate_difficulty_score(data: Dict) -> Tuple[bool, str]:
        """验证难度与分数匹配"""
        difficulty = data.get('difficulty')
        score = data.get('difficulty_score')
        min_score, max_score = DIFFICULTY_SCORE_RANGES.get(difficulty, (0, 5))
        if not (min_score <= score <= max_score):
            return False, f"难度分数不匹配: {difficulty} -> {score}"
        return True, ""

    @staticmethod
    def validate_entity_to_token(data: Dict) -> Tuple[bool, List[str]]:
        """验证token位置与question匹配"""
        errors = []
        question = data.get('question', '')
        entity_to_token = data.get('entity_to_token', {})

        if not question or not entity_to_token:
            return True, []  # 空数据跳过验证

        for entity_name, token_info in entity_to_token.items():
            char_start = token_info.get('char_start', 0)
            char_end = token_info.get('char_end', 0)
            if char_start < 0 or char_end > len(question):
                errors.append(f"entity_to_token位置超出范围: {entity_name}")
                continue
            extracted = question[char_start:char_end]
            if extracted != entity_name:
                # 允许一些差异（如"石家庄市" vs "石家庄"）
                if entity_name not in extracted and extracted not in entity_name:
                    errors.append(f"entity_to_token位置不匹配: {entity_name} != {extracted}")

        return len(errors) == 0, errors

    def validate(self, data: Dict) -> Tuple[bool, List[str]]:
        """综合验证"""
        all_errors = []

        # 验证必需字段
        ok, missing = self.validate_required_fields(data)
        if not ok:
            all_errors.extend([f"缺少字段: {m}" for m in missing])
            return False, all_errors

        # 验证坐标
        for entity in data.get('entities', []):
            ok, msg = self.validate_coords(entity.get('coords', []))
            if not ok:
                all_errors.append(msg)

        # 验证推理链
        ok, errors = self.validate_reasoning_chain(data.get('reasoning_chain', []))
        all_errors.extend(errors)

        # 验证难度分数
        ok, msg = self.validate_difficulty_score(data)
        if not ok:
            all_errors.append(msg)

        # 验证entity_to_token
        ok, errors = self.validate_entity_to_token(data)
        all_errors.extend(errors)

        return len(all_errors) == 0, all_errors


# ============================================================================
# 7. 进度管理器类
# ============================================================================

class ProgressManager:
    """进度管理器"""

    def __init__(self, progress_file: Path):
        self.progress_file = progress_file
        self.completed = set()
        self.failed = []
        self.stats = {
            "total_attempted": 0,
            "total_success": 0,
            "total_failed": 0,
            "start_time": None,
            "last_update": None
        }
        self._load_progress()

    def _load_progress(self):
        """加载进度"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.completed = set(data.get('completed', []))
                    self.failed = data.get('failed', [])
                    self.stats = data.get('stats', self.stats)
                print(f"加载进度: 已完成 {len(self.completed)} 条")
            except Exception as e:
                print(f"加载进度失败: {e}")

    def _save_progress(self):
        """保存进度"""
        data = {
            'completed': list(self.completed),
            'failed': self.failed,
            'stats': self.stats
        }
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def is_completed(self, pair_key: str) -> bool:
        """检查实体对是否已处理"""
        return pair_key in self.completed

    def mark_completed(self, pair_key: str, record_id: str):
        """标记成功"""
        self.completed.add(pair_key)
        self.stats['total_success'] += 1
        self.stats['last_update'] = datetime.now().isoformat()

    def mark_failed(self, pair_key: str, error: str):
        """记录失败"""
        self.failed.append({
            'pair_key': pair_key,
            'error': error,
            'time': datetime.now().isoformat()
        })
        self.stats['total_failed'] += 1

    def save_checkpoint(self):
        """保存检查点"""
        self._save_progress()
        print(f"进度已保存: 成功 {self.stats['total_success']}, 失败 {self.stats['total_failed']}")


# ============================================================================
# 8. 主流程
# ============================================================================

def sample_by_difficulty(pairs: List[Dict], count: int, distribution: Dict[str, float]) -> List[Dict]:
    """按难度分布采样"""
    random.shuffle(pairs)

    # 计算各难度数量
    easy_count = int(count * distribution.get('easy', 0.3))
    medium_count = int(count * distribution.get('medium', 0.5))
    hard_count = count - easy_count - medium_count

    # 分配难度标签
    result = []
    for i, pair in enumerate(pairs[:count]):
        if i < easy_count:
            pair['difficulty'] = 'easy'
            pair['difficulty_score'] = round(random.uniform(*DIFFICULTY_SCORE_RANGES['easy']), 1)
        elif i < easy_count + medium_count:
            pair['difficulty'] = 'medium'
            pair['difficulty_score'] = round(random.uniform(*DIFFICULTY_SCORE_RANGES['medium']), 1)
        else:
            pair['difficulty'] = 'hard'
            pair['difficulty_score'] = round(random.uniform(*DIFFICULTY_SCORE_RANGES['hard']), 1)
        result.append(pair)

    random.shuffle(result)  # 打乱顺序
    return result


def generate_pair_key(pair: Dict, subtype: str) -> str:
    """生成实体对唯一标识"""
    if subtype == 'contains':
        return f"{subtype}_{pair['container']['name']}_{pair['contained']['name']}"
    else:
        return f"{subtype}_{pair['entity1']['name']}_{pair['entity2']['name']}"


def build_prompt(pair: Dict, subtype: str, seq_num: int) -> str:
    """构建提示词 - 使用字符串替换避免格式化冲突"""
    if subtype == 'contains':
        container = pair['container']
        contained = pair['contained']
        difficulty = pair.get('difficulty', 'medium')
        difficulty_score = pair.get('difficulty_score', 3.0)

        # 使用字符串替换而不是format()
        prompt = CONTAINS_PROMPT_TEMPLATE
        prompt = prompt.replace('{container_name}', str(container['name']))
        prompt = prompt.replace('{container_type}', str(container['type']))
        prompt = prompt.replace('{container_coords}', json.dumps(container['coords'], ensure_ascii=False))
        prompt = prompt.replace('{contained_name}', str(contained['name']))
        prompt = prompt.replace('{contained_type}', str(contained['type']))
        prompt = prompt.replace('{contained_coords}', json.dumps(contained['coords'], ensure_ascii=False))
        prompt = prompt.replace('{difficulty}', str(difficulty))
        prompt = prompt.replace('{difficulty_score}', str(difficulty_score))
        return prompt
    else:  # overlap
        entity1 = pair['entity1']
        entity2 = pair['entity2']
        overlap_info = pair.get('overlap_info', '')
        difficulty = pair.get('difficulty', 'medium')
        difficulty_score = pair.get('difficulty_score', 3.0)

        prompt = OVERLAP_PROMPT_TEMPLATE
        prompt = prompt.replace('{entity1_name}', str(entity1['name']))
        prompt = prompt.replace('{entity1_type}', str(entity1['type']))
        prompt = prompt.replace('{entity1_coords}', json.dumps(entity1['coords'], ensure_ascii=False))
        prompt = prompt.replace('{entity2_name}', str(entity2['name']))
        prompt = prompt.replace('{entity2_type}', str(entity2['type']))
        prompt = prompt.replace('{entity2_coords}', json.dumps(entity2['coords'], ensure_ascii=False))
        prompt = prompt.replace('{overlap_info}', str(overlap_info))
        prompt = prompt.replace('{difficulty}', str(difficulty))
        prompt = prompt.replace('{difficulty_score}', str(difficulty_score))
        return prompt


def fix_record(data: Dict, pair: Dict, subtype: str, seq_num: int) -> Dict:
    """修复和补全记录"""
    # 修复ID
    data['id'] = f"geosr_topological_{seq_num:05d}"

    # 确保topology_subtype正确
    data['topology_subtype'] = subtype
    data['spatial_relation_type'] = "topological"

    # 使用pair中的难度设置
    if 'difficulty' in pair:
        data['difficulty'] = pair['difficulty']
    if 'difficulty_score' in pair:
        data['difficulty_score'] = pair['difficulty_score']

    # 确保entities使用正确的坐标
    if subtype == 'contains':
        data['entities'] = [
            {"name": pair['container']['name'], "type": pair['container']['type'], "coords": pair['container']['coords']},
            {"name": pair['contained']['name'], "type": pair['contained']['type'], "coords": pair['contained']['coords']}
        ]
    else:
        data['entities'] = [
            {"name": pair['entity1']['name'], "type": pair['entity1']['type'], "coords": pair['entity1']['coords']},
            {"name": pair['entity2']['name'], "type": pair['entity2']['type'], "coords": pair['entity2']['coords']}
        ]

    return data


def main():
    parser = argparse.ArgumentParser(description='生成拓扑数据补充脚本')
    parser.add_argument('--subtype', type=str, required=True, choices=['contains', 'overlap'],
                        help='拓扑子类型')
    parser.add_argument('--batch', type=int, default=1, help='批次数（每批5条）')
    parser.add_argument('--difficulty-distribution', type=str, default='easy=0.3,medium=0.5,hard=0.2',
                        help='难度分布')
    parser.add_argument('--checkpoint-interval', type=int, default=CHECKPOINT_INTERVAL,
                        help='检查点保存间隔')
    parser.add_argument('--resume', action='store_true', help='从断点继续')
    parser.add_argument('--test', action='store_true', help='测试模式，只生成5条')
    parser.add_argument('--api-key', type=str, default=None, help='智谱API密钥（也可通过环境变量ZHIPUAI_API_KEY设置）')
    args = parser.parse_args()

    # 解析难度分布
    distribution = {}
    for item in args.difficulty_distribution.split(','):
        k, v = item.split('=')
        distribution[k.strip()] = float(v.strip())

    target_count = args.batch * 5  # 每批5条
    print(f"=" * 60)
    print(f"拓扑数据补充脚本 V2.0 (批量模式)")
    print(f"子类型: {args.subtype}")
    print(f"批次数: {args.batch}, 每批5条, 目标总数: {target_count}")
    print(f"难度分布: {distribution}")
    print(f"=" * 60)

    # 初始化组件
    entity_manager = EntityManager(ENTITY_DB_PATH)
    if not entity_manager.load_database():
        print("加载数据库失败，退出")
        return 1

    pair_generator = EntityPairGenerator(entity_manager)
    validator = DataValidator()
    progress_manager = ProgressManager(PROGRESS_FILE)

    try:
        glm_client = GLMClient(api_key=args.api_key)
    except Exception as e:
        print(f"初始化GLM客户端失败: {e}")
        return 1

    # 生成实体对
    if args.subtype == 'contains':
        pairs = pair_generator.generate_contains_pairs()
    else:
        pairs = pair_generator.generate_overlap_pairs()

    # 采样
    target_count = 5 if args.test else args.count
    sampled_pairs = sample_by_difficulty(pairs, min(target_count, len(pairs)), distribution)

    print(f"采样完成: {len(sampled_pairs)} 对")

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 开始生成
    progress_manager.stats['start_time'] = datetime.now().isoformat()
    success_count = 0
    generated_records = []

    with open(OUTPUT_FILE, 'a', encoding='utf-8') as out_f:
        for i, pair in enumerate(sampled_pairs):
            pair_key = generate_pair_key(pair, args.subtype)

            # 跳过已完成的
            if args.resume and progress_manager.is_completed(pair_key):
                print(f"[{i+1}/{len(sampled_pairs)}] 跳过已完成: {pair_key}")
                continue

            progress_manager.stats['total_attempted'] += 1
            print(f"\n[{i+1}/{len(sampled_pairs)}] 处理: {pair_key}")

            # 构建提示词
            prompt = build_prompt(pair, args.subtype, success_count + 1)

            # 调用API
            response = glm_client.generate(prompt)
            if not response:
                print(f"  API调用失败")
                progress_manager.mark_failed(pair_key, "API调用失败")
                continue

            # 解析响应
            data = glm_client.parse_json_response(response)
            if not data:
                print(f"  JSON解析失败")
                progress_manager.mark_failed(pair_key, "JSON解析失败")
                continue

            # 修复和验证
            data = fix_record(data, pair, args.subtype, success_count + 1)
            ok, errors = validator.validate(data)

            if not ok:
                print(f"  验证失败: {errors[:3]}")
                # 仍然保存，但标记问题
                data['_validation_errors'] = errors

            # 保存记录
            out_f.write(json.dumps(data, ensure_ascii=False) + '\n')
            out_f.flush()

            progress_manager.mark_completed(pair_key, data['id'])
            success_count += 1
            generated_records.append(data)

            print(f"  成功: {data['id']} - {data['question'][:30]}...")

            # 定期保存进度
            if (i + 1) % args.checkpoint_interval == 0:
                progress_manager.save_checkpoint()

    # 最终保存
    progress_manager.save_checkpoint()

    # 生成报告
    report = {
        "subtype": args.subtype,
        "target_count": target_count,
        "actual_count": success_count,
        "difficulty_distribution": distribution,
        "stats": progress_manager.stats,
        "failed_count": len(progress_manager.failed),
        "generation_time": datetime.now().isoformat()
    }

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n" + "=" * 60)
    print(f"生成完成!")
    print(f"成功: {success_count} 条")
    print(f"失败: {len(progress_manager.failed)} 条")
    print(f"输出文件: {OUTPUT_FILE}")
    print(f"进度文件: {PROGRESS_FILE}")
    print(f"报告文件: {REPORT_FILE}")
    print(f"=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
