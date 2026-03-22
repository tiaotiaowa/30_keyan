"""
模型加载工具模块
支持 Qwen2.5-1.5B-Instruct 模型的加载，支持量化
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ModelLoader:
    """模型加载器，支持本地和远程模型"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化模型加载器

        Args:
            config: 模型配置字典
        """
        self.config = config
        self.model = None
        self.tokenizer = None
        self.device = config.get("device", "cuda")

    def load(self) -> tuple:
        """
        加载模型和tokenizer

        Returns:
            (model, tokenizer) 元组
        """
        model_name = self.config.get("name", "Qwen/Qwen2.5-1.5B-Instruct")
        local_path = self.config.get("path", "")
        use_local = self.config.get("use_local", False)

        # 确定实际使用的模型路径
        model_path = local_path if use_local and local_path else model_name

        logger.info(f"正在加载模型: {model_path}")

        # 加载tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            use_fast=False
        )

        # 确保pad_token存在
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # 设置模型加载参数
        dtype_str = self.config.get("dtype", "float16")
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32
        }
        torch_dtype = dtype_map.get(dtype_str, torch.float16)

        # 加载模型
        max_memory = self.config.get("max_memory", "5GB")

        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch_dtype,
            device_map="auto",
            max_memory={0: max_memory} if torch.cuda.is_available() else None,
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )

        self.model.eval()

        logger.info(f"模型加载完成，设备: {self.model.device}")
        logger.info(f"模型参数量: {sum(p.numel() for p in self.model.parameters()) / 1e9:.2f}B")

        return self.model, self.tokenizer

    def get_model(self):
        """获取已加载的模型"""
        if self.model is None:
            raise RuntimeError("模型尚未加载，请先调用 load()")
        return self.model

    def get_tokenizer(self):
        """获取已加载的tokenizer"""
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer尚未加载，请先调用 load()")
        return self.tokenizer

    def get_device(self):
        """获取模型所在设备"""
        return self.model.device if self.model else None


def load_model_from_config(config_path: str) -> tuple:
    """
    从配置文件加载模型

    Args:
        config_path: 配置文件路径

    Returns:
        (model, tokenizer) 元组
    """
    import yaml

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    loader = ModelLoader(config.get('model', {}))
    return loader.load()


if __name__ == "__main__":
    # 测试加载
    import yaml

    config_path = "config/generation_config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    loader = ModelLoader(config['model'])
    model, tokenizer = loader.load()

    # 简单测试
    test_text = "你好，请介绍一下自己。"
    inputs = tokenizer(test_text, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=50)

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"测试响应: {response}")
