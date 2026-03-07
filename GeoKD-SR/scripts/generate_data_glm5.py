#!/usr/bin/env python3
"""
GeoKD-SR GLM-5 Data Generation Script

Strictly following specifications:
- docs/GeoKD-SR-实验执行手册-V6.0/01-阶段1-数据准备/1.1-数据生成规范.md (V2.1)
- docs/GeoKD-SR-实验设计方案-V5.2.md (V5.3)

Features:
1. Load prompts from prompts_config_full.json
2. Call GLM-5 API using zhipuai SDK for batch data generation
3. Support checkpoint/resume mode
4. Progressive testing: 1 -> 10 -> 11800

Usage:
    python scripts/generate_data_glm5.py --test          # 1 sample
    python scripts/generate_data_glm5.py --small         # 10 samples
    python scripts/generate_data_glm5.py --medium        # 100 samples
    python scripts/generate_data_glm5.py --full          # all 11800 samples
    python scripts/generate_data_glm5.py --resume        # resume from last checkpoint

Author: GeoKD-SR Team
Date: 2026-03-07
Version: V3.0 (zhipuai SDK)
"""

import os
import sys
import io
import json
import time
import argparse
import re
import random
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
from collections import Counter
from dataclasses import dataclass, field, asdict
import traceback

# Setup UTF-8 encoding for Windows console
if sys.platform == 'win32':
    try:
        if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        if not isinstance(sys.stderr, io.TextIOWrapper) or sys.stderr.encoding != 'utf-8':
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================================
# Constants
# ================================

MODEL_NAME = "glm-5"
# Use absolute path based on script location
DEFAULT_PROMPTS_FILE = str(project_root / "data/prompts/prompts_config_full.json")
DEFAULT_OUTPUT_DIR = str(project_root / "data/geosr_chain")
PROGRESS_FILE = "generation_progress.json"
CHECKPOINT_INTERVAL = 50
MAX_RETRIES = 3
RETRY_DELAY = 2.0
REQUEST_TIMEOUT = 120

# 5-step reasoning chain definition
REASONING_STEPS = [
    'entity_identification',
    'spatial_relation_extraction',
    'coordinate_retrieval',
    'spatial_calculation',
    'answer_generation'
]

STEP_ACTIONS = {
    'entity_identification': 'extract_entities',
    'spatial_relation_extraction': 'classify_relation',
    'coordinate_retrieval': 'infer_entity_to_token',
    'spatial_calculation': 'calculate',
    'answer_generation': 'generate_answer'
}

# Difficulty score configuration (V2.0)
BASE_SCORES = {
    "directional": 1.2,
    "topological": 2.2,
    "metric": 1.3,
    "composite": 3.2
}

TOPOLOGY_BONUS = {
    "within": 0.0,
    "contains": 0.1,
    "adjacent": 0.3,
    "disjoint": 0.4,
    "overlap": 0.6
}

ENTITY_BONUS = {
    ("city", "city"): 0.0,
    ("city", "landmark"): 0.2,
    ("province", "city"): 0.4,
    ("river", "city"): 0.7,
    ("mountain", "city"): 0.7,
    ("region", "city"): 0.9
}


# ================================
# GLM5Client Class (zhipuai SDK)
# ================================

class GLM5Client:
    """GLM-5 API Client using zhipuai SDK"""

    MAX_RETRIES = MAX_RETRIES
    RETRY_DELAY = RETRY_DELAY

    def __init__(self, api_key: str = None):
        """Initialize GLM5 client with zhipuai SDK"""
        self.api_key = api_key or self._load_api_key()
        if not self.api_key:
            raise ValueError("API key not found. Please set ZHIPUAI_API_KEY environment variable or configure in .env file")

        # Initialize zhipuai client
        try:
            from zhipuai import ZhipuAI
            self.client = ZhipuAI(api_key=self.api_key)
            logger.info("zhipuai SDK initialized successfully")
        except ImportError:
            raise ImportError("zhipuai SDK not installed. Run: pip install zhipuai")

        self._request_count = 0
        self._success_count = 0
        self._error_count = 0

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment or .env file"""
        # First check environment variable
        api_key = os.getenv("ZHIPUAI_API_KEY")
        if api_key:
            return api_key

        # Try to load from .env file
        env_paths = [
            project_root / ".env",
            Path(".env"),
            Path(__file__).parent.parent / ".env"
        ]

        for env_path in env_paths:
            if env_path.exists():
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("ZHIPUAI_API_KEY="):
                            return line.split("=", 1)[1].strip()
        return None

    def generate(self, prompt: str, max_tokens: int = 4096, temperature: float = 0.7) -> Optional[str]:
        """Call API to generate response using zhipuai SDK"""
        if not prompt:
            return None

        self._request_count += 1

        for attempt in range(self.MAX_RETRIES):
            try:
                # Build request with specific parameters for JSON output
                response = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    # Disable thinking mode to get direct JSON output
                    extra_body={"thinking": {"type": "disabled"}}
                )

                # Get response content
                message = response.choices[0].message
                content = message.content

                # If content is empty but reasoning_content exists, use it as fallback
                if not content and hasattr(message, 'reasoning_content') and message.reasoning_content:
                    # Try to extract JSON from reasoning content
                    content = message.reasoning_content
                    logger.warning("Response in reasoning_content, attempting JSON extraction")

                if content:
                    self._success_count += 1
                    logger.debug(f"API call successful (attempt {attempt + 1})")
                    return content

            except Exception as e:
                self._error_count += 1
                error_msg = str(e)
                logger.error(f"API call failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {error_msg}")

                if attempt < self.MAX_RETRIES - 1:
                    sleep_time = self.RETRY_DELAY * (attempt + 1)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"API call failed after {self.MAX_RETRIES} attempts")
                    return None

        return None

    @property
    def stats(self) -> Dict[str, int]:
        """Get statistics"""
        return {
            "requests": self._request_count,
            "success": self._success_count,
            "errors": self._error_count
        }


# ================================
# JSONParser Class
# ================================

class JSONParser:
    """Robust JSON parser for API responses"""

    @staticmethod
    def extract_json(text: str) -> Optional[dict]:
        """Extract JSON from text with multiple strategies"""
        if not text:
            return None

        # Strategy 1: Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code blocks
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue

        # Strategy 3: Find JSON object in text
        json_pattern = r'\{[\s\S]*\}'
        matches = re.findall(json_pattern, text)
        for match in matches:
            try:
                # Try to fix common issues
                fixed = JSONParser._fix_common_issues(match)
                return json.loads(fixed)
            except json.JSONDecodeError:
                continue

        return None

    @staticmethod
    def _fix_common_issues(text: str) -> str:
        """Fix common JSON formatting issues"""
        # Remove trailing commas before } or ]
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        # Fix unescaped quotes in strings (basic attempt)
        # This is a simple heuristic and may not work for all cases

        return text.strip()


# ================================
# ProgressManager Class
# ================================

@dataclass
class ProgressState:
    """Progress state for checkpoint/resume"""
    total: int = 0
    completed: int = 0
    failed: int = 0
    completed_ids: List[str] = field(default_factory=list)
    failed_ids: List[str] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)
    start_time: str = None
    end_time: str = None
    last_index: int = 0


class ProgressManager:
    """Progress manager with checkpoint/resume support"""

    PROGRESS_FILE = PROGRESS_FILE
    CHECKPOINT_INTERVAL = CHECKPOINT_INTERVAL

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.progress_file = self.output_dir / self.PROGRESS_FILE
        self.state = self._load_progress()

    def _load_progress(self) -> ProgressState:
        """Load progress from file"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return ProgressState(
                        total=data.get('total', 0),
                        completed=data.get('completed', 0),
                        failed=data.get('failed', 0),
                        completed_ids=data.get('completed_ids', []),
                        failed_ids=data.get('failed_ids', []),
                        errors=data.get('errors', []),
                        start_time=data.get('start_time'),
                        end_time=data.get('end_time'),
                        last_index=data.get('last_index', 0)
                    )
            except Exception as e:
                logger.warning(f"Failed to load progress file: {e}")
        return ProgressState(start_time=datetime.now().isoformat())

    def reset(self):
        """Reset progress"""
        self.state = ProgressState(start_time=datetime.now().isoformat())
        self.save_progress()
        logger.info("Progress reset")

    def mark_completed(self, prompt_id: str, index: int):
        """Mark as completed"""
        self.state.completed += 1
        self.state.completed_ids.append(prompt_id)
        self.state.last_index = index
        self._auto_save()

    def mark_failed(self, prompt_id: str, index: int, error: str):
        """Mark as failed"""
        self.state.failed += 1
        self.state.failed_ids.append(prompt_id)
        self.state.errors.append({"id": prompt_id, "error": error})
        self.state.last_index = index
        self._auto_save()

    def is_completed(self, prompt_id: str) -> bool:
        """Check if completed"""
        return prompt_id in self.state.completed_ids

    def get_resume_index(self) -> int:
        """Get resume index"""
        return self.state.last_index + 1

    def _auto_save(self):
        """Auto save progress"""
        self.state.end_time = datetime.now().isoformat()
        self.save_progress()

    def save_progress(self):
        """Save progress to file"""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.state), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    @property
    def summary(self) -> Dict[str, Any]:
        """Get progress summary"""
        return {
            "total": self.state.total,
            "completed": self.state.completed,
            "failed": self.state.failed,
            "success_rate": self.state.completed / self.state.total if self.state.total > 0 else 0.0,
            "remaining": self.state.total - self.state.completed - self.state.failed
        }


# ================================
# DataValidator Class
# ================================

class DataValidator:
    """Data validator for generated records"""

    REQUIRED_FIELDS = ['id', 'question', 'answer', 'spatial_relation_type', 'reasoning_chain', 'entities', 'difficulty']

    @staticmethod
    def validate(record: Dict) -> Tuple[bool, List[str]]:
        """Validate a data record"""
        errors = []

        # Required field check
        for field in DataValidator.REQUIRED_FIELDS:
            if field not in record:
                errors.append(f"Missing required field: {field}")

        # Type check
        if not isinstance(record.get('question'), str):
            errors.append("question must be a string")
        if not isinstance(record.get('answer'), str):
            errors.append("answer must be a string")

        # Reasoning chain validation
        if not isinstance(record.get('reasoning_chain'), list):
            errors.append("reasoning_chain must be a list")
        elif len(record['reasoning_chain']) != 5:
            errors.append(f"reasoning_chain must contain 5 steps, got {len(record['reasoning_chain'])}")
        else:
            for i, step in enumerate(record['reasoning_chain']):
                if not isinstance(step, dict):
                    errors.append(f"reasoning_chain step {i + 1} must be a dict")
                else:
                    required_step_fields = ['step', 'name', 'action', 'content']
                    for field in required_step_fields:
                        if field not in step:
                            errors.append(f"reasoning_chain step {i + 1} missing field: {field}")

        # Entities validation
        if not isinstance(record.get('entities'), list):
            errors.append("entities must be a list")
        elif len(record['entities']) < 2:
            errors.append("entities must contain at least 2 entities")
        else:
            for i, entity in enumerate(record['entities']):
                if not isinstance(entity, dict):
                    errors.append(f"entities item {i + 1} must be a dict")
                else:
                    if 'name' not in entity:
                        errors.append(f"entities item {i + 1} missing name field")
                    if 'type' not in entity:
                        errors.append(f"entities item {i + 1} missing type field")
                    if 'coords' not in entity:
                        errors.append(f"entities item {i + 1} missing coords field")
                    elif not isinstance(entity['coords'], list) or len(entity['coords']) != 2:
                        errors.append(f"entities item {i + 1} coords format error")

        # Difficulty validation
        if 'difficulty' in record:
            if record['difficulty'] not in ['easy', 'medium', 'hard']:
                errors.append("difficulty must be easy/medium/hard")

        return len(errors) == 0, errors


# ================================
# GeoSRDataGenerator Class
# ================================

class GeoSRDataGenerator:
    """GeoSR Data Generator"""

    def __init__(self, client: GLM5Client = None,
                 prompts_file: str = DEFAULT_PROMPTS_FILE,
                 output_dir: str = DEFAULT_OUTPUT_DIR,
                 verbose: bool = True):
        """Initialize data generator"""
        self.client = client or GLM5Client()
        # Convert relative paths to absolute based on project root
        prompts_path = Path(prompts_file)
        if not prompts_path.is_absolute():
            prompts_path = project_root / prompts_path
        self.prompts_file = prompts_path

        output_path = Path(output_dir)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        self.output_dir = output_path

        self.verbose = verbose
        self.progress = ProgressManager(str(self.output_dir))
        self.parser = JSONParser()
        self.validator = DataValidator()
        self.prompts_data = self._load_prompts()
        self.prompts = self.prompts_data.get("prompts", [])
        self.stats = {
            "total": 0,
            "generated": 0,
            "failed": 0,
            "validation_errors": 0
        }

    def _load_prompts(self) -> Dict:
        """Load prompts configuration"""
        if not self.prompts_file.exists():
            raise FileNotFoundError(f"Prompts file not found: {self.prompts_file}")
        with open(self.prompts_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data.get('prompts', []))} prompts from {self.prompts_file}")
            return data

    def log(self, message: str, level: str = "INFO"):
        """Print log message"""
        if self.verbose:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] [{level}] {message}")

    def generate_single(self, prompt_data: dict, index: int = 0) -> Optional[dict]:
        """Generate single data record"""
        prompt_id = prompt_data.get("id", f"unknown_{index}")
        prompt_text = prompt_data.get("prompt_text", "")

        if not prompt_text:
            self.log(f"Prompt {prompt_id} has no prompt_text", "WARNING")
            return None

        # Check if already completed
        if self.progress.is_completed(prompt_id):
            self.log(f"Prompt {prompt_id} already completed, skipping", "INFO")
            return None

        # Call API
        self.log(f"Generating data for {prompt_id}...")
        response = self.client.generate(prompt_text)

        if not response:
            self.progress.mark_failed(prompt_id, index, "API call failed")
            self.stats["failed"] += 1
            return None

        # Parse JSON response
        record = self.parser.extract_json(response)
        if not record:
            self.log(f"Prompt {prompt_id} JSON parse failed", "WARNING")
            self.progress.mark_failed(prompt_id, index, "JSON parse failed")
            self.stats["failed"] += 1
            # Save raw response for debugging
            self._save_raw_response(prompt_id, response)
            return None

        # Enhance record with metadata from prompt_data
        record = self._enhance_record(record, prompt_data, index)

        # Validate record
        is_valid, errors = self.validator.validate(record)
        if not is_valid:
            self.log(f"Prompt {prompt_id} validation failed: {errors[:2]}", "WARNING")
            self.stats["validation_errors"] += 1
            # Still mark as completed but log the issues

        self.progress.mark_completed(prompt_id, index)
        self.stats["generated"] += 1
        return record

    def _save_raw_response(self, prompt_id: str, response: str):
        """Save raw API response for debugging"""
        try:
            debug_dir = self.output_dir / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"raw_response_{prompt_id}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response)
        except Exception as e:
            logger.error(f"Failed to save raw response: {e}")

    def _enhance_record(self, record: Dict, prompt_data: Dict, index: int) -> Dict:
        """Enhance data record with additional fields"""
        # Ensure id
        if 'id' not in record or not record['id']:
            record['id'] = f"geosr_{index + 1:05d}"

        # Add spatial_relation_type from prompt_data
        if 'spatial_relation_type' not in record:
            record['spatial_relation_type'] = prompt_data.get('relation_type', "composite")

        # Add difficulty from prompt_data
        if 'difficulty' not in record:
            record['difficulty'] = prompt_data.get('difficulty', "medium")

        # Add topology_subtype from prompt_data
        if 'topology_subtype' not in record and prompt_data.get('topology_subtype'):
            record['topology_subtype'] = prompt_data['topology_subtype']

        # Add split field
        if 'split' not in record:
            record['split'] = prompt_data.get('split', "train")

        # Ensure reasoning_chain is 5 steps
        if 'reasoning_chain' in record:
            record['reasoning_chain'] = self._normalize_reasoning_chain(
                record['reasoning_chain'], prompt_data
            )
        else:
            record['reasoning_chain'] = self._create_default_reasoning_chain(prompt_data)

        # Add difficulty_score
        if 'difficulty_score' not in record:
            record['difficulty_score'] = self._calculate_difficulty_score(record)

        # Add spatial_tokens
        if 'spatial_tokens' not in record or not record['spatial_tokens']:
            record['spatial_tokens'] = self._extract_spatial_tokens(record)

        # Add entity_to_token mapping
        if 'entity_to_token' not in record:
            record['entity_to_token'] = self._create_entity_to_token_mapping(record)

        return record

    def _normalize_reasoning_chain(self, chain: List, prompt_data: Dict) -> List[Dict]:
        """Normalize reasoning chain to 5 steps"""
        if not chain:
            return self._create_default_reasoning_chain(prompt_data)

        # If already 5-step dict structure
        if len(chain) == 5 and all(isinstance(s, dict) for s in chain):
            return chain

        # Convert string list to 5-step structure
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
                    "name": step_names[idx][0] if idx < len(step_names) else f"step_{idx + 1}",
                    "action": step_names[idx][1] if idx < len(step_names) else "unknown",
                    "content": content
                }
            else:
                step = content
            normalized.append(step)

        # Pad missing steps
        while len(normalized) < 5:
            idx = len(normalized)
            normalized.append({
                "step": idx + 1,
                "name": step_names[idx][0] if idx < len(step_names) else f"step_{idx + 1}",
                "action": step_names[idx][1] if idx < len(step_names) else "unknown",
                "content": " "
            })

        return normalized

    def _create_default_reasoning_chain(self, prompt_data: Dict) -> List[Dict]:
        """Create default reasoning chain from prompt_data"""
        entity1 = prompt_data.get('entity1', {})
        entity2 = prompt_data.get('entity2', {})
        relation_type = prompt_data.get('relation_type', "composite")

        chain = []
        for i in range(5):
            step = {
                "step": i + 1,
                "name": REASONING_STEPS[i],
                "action": STEP_ACTIONS[REASONING_STEPS[i]],
                "content": f"Step {i + 1} reasoning"
            }
            if i == 0:
                step["entities_involved"] = [entity1.get('name', ''), entity2.get('name', '')]
            elif i == 1:
                step["relation_type"] = relation_type
            elif i == 2:
                step["coordinates"] = {
                    entity1.get('name', ''): entity1.get('coords', []),
                    entity2.get('name', ''): entity2.get('coords', [])
                }
            elif i == 3:
                step["calculation_result"] = "Calculation result"
            elif i == 4:
                step["final_answer"] = "Final answer"
            chain.append(step)
        return chain

    def _calculate_difficulty_score(self, record: Dict) -> float:
        """Calculate difficulty score V2.0"""
        spatial_type = record.get('spatial_relation_type', 'composite')
        topology_subtype = record.get('topology_subtype')
        entities = record.get('entities', [])

        # Base score
        score = BASE_SCORES.get(spatial_type, 1.2)

        # Topology subtype bonus
        if topology_subtype and topology_subtype in TOPOLOGY_BONUS:
            score += TOPOLOGY_BONUS[topology_subtype]

        # Entity type pair bonus
        entity_types = []
        if entities:
            for entity in entities:
                if isinstance(entity, dict) and 'type' in entity:
                    entity_types.append(entity.get('type', 'unknown'))
        entity_types = sorted(entity_types)
        score += ENTITY_BONUS.get(tuple(entity_types), 0.5)

        # Entity count bonus
        entity_count = len(entities) if isinstance(entities, list) else 2
        score += max(0, (entity_count - 2) * 0.3)

        # Limit range
        score = min(max(score, 1.0), 5.0)
        return round(score, 2)

    def _extract_spatial_tokens(self, record: Dict) -> List[str]:
        """Extract spatial tokens from record"""
        tokens = set()
        question = record.get('question', '')
        answer = record.get('answer', '')
        text = question + ' ' + answer

        spatial_keywords = [
            'direction', 'east', 'west', 'south', 'north',
            'northeast', 'northwest', 'southeast', 'southwest',
            'distance', 'km', 'kilometer', 'meter', 'far', 'near',
            'contain', 'located', 'inside', 'intersect', 'adjacent',
            'boundary', 'within', 'between', 'around'
        ]

        for kw in spatial_keywords:
            if kw.lower() in text.lower():
                tokens.add(kw)

        return list(tokens)[:8]

    def _create_entity_to_token_mapping(self, record: Dict) -> Dict:
        """Create entity to token mapping"""
        entity_to_token = {}
        entities = record.get('entities', [])

        if not entities:
            return entity_to_token

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            name = entity.get('name', '')
            if not name:
                continue

            # Find entity position in question
            question = record.get('question', '')
            char_start = question.find(name)
            if char_start >= 0:
                char_end = char_start + len(name)
                entity_to_token[name] = {
                    "char_start": char_start,
                    "char_end": char_end,
                    "token_indices": list(range(char_start, char_end + 1))
                }

        return entity_to_token

    def generate_batch(self, count: int, start_index: int = 0, split: str = None) -> List[dict]:
        """Generate batch of data"""
        # Filter prompts by split
        if split:
            prompts_to_process = [p for p in self.prompts if p.get('split') == split]
        else:
            prompts_to_process = self.prompts

        # Limit count
        if count:
            prompts_to_process = prompts_to_process[start_index:start_index + count]
        else:
            prompts_to_process = prompts_to_process[start_index:]

        self.log(f"Starting generation of {len(prompts_to_process)} samples...")
        self.progress.state.total = len(prompts_to_process)

        records = []
        for idx, prompt_data in enumerate(prompts_to_process):
            actual_index = start_index + idx
            record = self.generate_single(prompt_data, actual_index)

            if record:
                records.append(record)

            # Progress report
            if (idx + 1) % 10 == 0:
                self.log(f"Progress: {idx + 1}/{len(prompts_to_process)} (success: {self.stats['generated']}, failed: {self.stats['failed']})")

        # Save final progress
        self.progress.save_progress()
        return records

    def generate_all(self, resume: bool = True) -> Dict[str, Any]:
        """Generate all data with resume support"""
        start_index = self.progress.get_resume_index() if resume else 0

        if resume and start_index > 0:
            self.log(f"Resuming from index {start_index}")

        # Get split counts from metadata
        metadata = self.prompts_data.get('metadata', {})
        train_count = metadata.get('train_count', 8000)
        dev_count = metadata.get('dev_count', 800)
        test_count = metadata.get('test_count', 3000)

        # Generate each split
        results = {}
        for split_name, target_count in [('train', train_count), ('dev', dev_count), ('test', test_count)]:
            self.log(f"\nGenerating {split_name} set ({target_count} samples)...")
            split_prompts = [p for p in self.prompts if p.get('split') == split_name]

            records = []
            for idx, prompt_data in enumerate(split_prompts):
                record = self.generate_single(prompt_data, idx)
                if record:
                    records.append(record)
                    self.stats["generated"] += 1

                if (idx + 1) % 50 == 0:
                    self.log(f"  {split_name}: {idx + 1}/{len(split_prompts)}")

                # Save progress periodically
                if (idx + 1) % CHECKPOINT_INTERVAL == 0:
                    self.progress.save_progress()

            # Save split data
            if records:
                output_path = self.output_dir / f"{split_name}.jsonl"
                self._save_records(records, str(output_path))
                results[split_name] = len(records)

        # Save final progress
        self.progress.save_progress()

        return {
            "stats": self.stats,
            "results": results,
            "progress": self.progress.summary
        }

    def _save_records(self, records: List[Dict], output_path: str):
        """Save records to JSONL file"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        self.log(f"Saved: {output_path} ({len(records)} records)")


# ================================
# Command-line Interface
# ================================

def main():
    """Command-line entry"""
    parser = argparse.ArgumentParser(
        description='GeoKD-SR GLM-5 data generation script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test mode: generate 1 sample
  python scripts/generate_data_glm5.py --test

  # Small batch test: generate 10 samples
  python scripts/generate_data_glm5.py --small

  # Medium batch test: generate 100 samples
  python scripts/generate_data_glm5.py --medium

  # Full generation: generate all 11800 samples
  python scripts/generate_data_glm5.py --full

  # Resume: resume from last checkpoint
  python scripts/generate_data_glm5.py --resume

  # Reset and start fresh
  python scripts/generate_data_glm5.py --full --reset

  # Generate only specific split
  python scripts/generate_data_glm5.py --medium --split train

  # Custom count
  python scripts/generate_data_glm5.py --medium --count 50 --output data/custom
        """
    )

    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--test', action='store_true',
                           help='Test mode: generate 1 sample')
    mode_group.add_argument('--small', action='store_true',
                           help='Small batch test: generate 10 samples')
    mode_group.add_argument('--medium', action='store_true',
                           help='Medium batch test: generate 100 samples')
    mode_group.add_argument('--full', action='store_true',
                           help='Full generation: generate all 11800 samples')
    mode_group.add_argument('--resume', action='store_true',
                           help='Resume from last checkpoint')
    mode_group.add_argument('--count', type=int,
                           help='Custom count mode: generate N samples')

    # Configuration options
    parser.add_argument('--prompts', type=str, default=DEFAULT_PROMPTS_FILE,
                       help=f'Prompts config file path (default: {DEFAULT_PROMPTS_FILE})')
    parser.add_argument('--output', type=str, default=DEFAULT_OUTPUT_DIR,
                       help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('--split', type=str, choices=['train', 'dev', 'test'],
                       default=None, help='Generate only specific split')
    parser.add_argument('--reset', action='store_true',
                       help='Reset progress and start fresh')
    parser.add_argument('--quiet', action='store_true',
                       help='Quiet mode with less output')

    args = parser.parse_args()

    # Determine count
    if args.test:
        count = 1
    elif args.small:
        count = 10
    elif args.medium:
        count = 100
    elif args.full or args.resume:
        count = None  # All
    elif args.count:
        count = args.count
    else:
        count = 10  # Default

    print("=" * 60)
    print("GeoKD-SR GLM-5 Data Generation (zhipuai SDK)")
    print("=" * 60)
    print(f"Prompts file: {args.prompts}")
    print(f"Output directory: {args.output}")
    if count:
        print(f"Count: {count}")
    else:
        print("Mode: Full")
    print("=" * 60)

    start_time = time.time()

    try:
        # Create client
        client = GLM5Client()

        # Create generator
        generator = GeoSRDataGenerator(
            client=client,
            prompts_file=args.prompts,
            output_dir=args.output,
            verbose=not args.quiet
        )

        # Reset progress if requested
        if args.reset:
            generator.progress.reset()
            print("Progress reset")

        # Generate data
        if args.full or args.resume:
            result = generator.generate_all(resume=args.resume)
            print(f"\nGeneration complete!")
            print(f"Results: {result['results']}")
            print(f"Stats: {result['stats']}")
        else:
            records = generator.generate_batch(count, split=args.split)

            # Save results
            if records:
                output_file = f"generated_{count}"
                if args.split:
                    output_file += f"_{args.split}"
                output_file += ".jsonl"
                output_path = Path(args.output) / output_file
                generator._save_records(records, str(output_path))
                print(f"\nGeneration complete: {len(records)} records")
            else:
                print("\nNo records generated")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please install required dependencies: pip install zhipuai")
        return 1
    except Exception as e:
        print(f"Runtime error: {e}")
        traceback.print_exc()
        return 1

    duration = time.time() - start_time
    print(f"\nDuration: {duration:.1f} seconds")
    return 0


if __name__ == '__main__':
    sys.exit(main())
