"""
模型加载工具
支持本地模型加载
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import logging

logger = logging.getLogger(__name__)


class ModelLoader:
    """模型加载器"""

    def __init__(self, config):
        """
        初始化模型加载器

        Args:
            config: 模型配置字典
        """
        self.config = config
        self.model = None
        self.tokenizer = None

    def load(self):
        """
        加载模型和分词器

        Returns:
            model, tokenizer
        """
        model_path = self.config.get('path', '')
        use_local = self.config.get('use_local', True)
        torch_dtype = self.config.get('torch_dtype', 'float16')

        # 转换 torch_dtype
        if isinstance(torch_dtype, str):
            dtype_map = {
                'float16': torch.float16,
                'bfloat16': torch.bfloat16,
                'float32': torch.float32
            }
            torch_dtype = dtype_map.get(torch_dtype, torch.float16)

        logger.info(f"加载模型: {model_path}")
        logger.info(f"数据类型: {torch_dtype}")

        # 加载分词器
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            use_fast=False
        )

        # 确保有 pad_token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # 加载模型 - 直接加载到GPU，避免offload
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch_dtype,
            device_map="cuda:0",
            trust_remote_code=True
        )

        self.model.eval()
        logger.info(f"模型加载完成，设备: {self.model.device}")

        return self.model, self.tokenizer
