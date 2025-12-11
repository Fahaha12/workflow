"""
配置管理模块
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


class Config:
    """配置管理类"""
    
    def __init__(self, env_file: str = None):
        """
        初始化配置
        
        Args:
            env_file: .env文件路径
        """
        # 加载环境变量
        if env_file and Path(env_file).exists():
            load_dotenv(env_file)
        else:
            load_dotenv()  # 加载默认的.env文件
        
        # AI配置
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-4-turbo-preview')
        
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.anthropic_model = os.getenv('ANTHROPIC_MODEL', 'claude-3-opus-20240229')
        
        self.dashscope_api_key = os.getenv('DASHSCOPE_API_KEY')
        self.qwen_model = os.getenv('QWEN_MODEL', 'qwen-max')
        self.qwen_vl_model = os.getenv('QWEN_VL_MODEL', 'qwen3-vl-plus')  # 视觉模型
        
        self.use_local_api = os.getenv('USE_LOCAL_API', 'false').lower() == 'true'
        self.local_api_url = os.getenv('LOCAL_API_URL', 'http://localhost:11434/v1')
        self.local_model = os.getenv('LOCAL_MODEL', 'llama3')
        
        # OCR配置
        self.tesseract_path = os.getenv('TESSERACT_PATH')
        
        # 输出配置
        self.output_dir = os.getenv('OUTPUT_DIR', 'output')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # 创建输出目录
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def get_ai_config(self) -> dict:
        """获取AI配置"""
        if self.use_local_api:
            return {
                'api_type': 'local',
                'api_key': None,
                'model': self.local_model,
                'base_url': self.local_api_url
            }
        elif self.dashscope_api_key:
            return {
                'api_type': 'qwen',
                'api_key': self.dashscope_api_key,
                'model': self.qwen_model,
                'vl_model': self.qwen_vl_model,
                'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
            }
        elif self.anthropic_api_key:
            return {
                'api_type': 'anthropic',
                'api_key': self.anthropic_api_key,
                'model': self.anthropic_model,
                'base_url': None
            }
        elif self.openai_api_key:
            return {
                'api_type': 'openai',
                'api_key': self.openai_api_key,
                'model': self.openai_model,
                'base_url': None
            }
        else:
            raise ValueError(
                "未配置AI API密钥。请在.env文件中设置 OPENAI_API_KEY、ANTHROPIC_API_KEY 或 DASHSCOPE_API_KEY，"
                "或设置 USE_LOCAL_API=true 使用本地API"
            )
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        try:
            self.get_ai_config()
            return True
        except ValueError as e:
            logger.error(f"配置验证失败: {str(e)}")
            return False
    
    def __repr__(self):
        """配置信息字符串表示"""
        ai_config = self.get_ai_config()
        vl_model = ai_config.get('vl_model', 'N/A')
        return (
            f"Config(\n"
            f"  AI文本模型: {ai_config['api_type']} - {ai_config['model']}\n"
            f"  AI视觉模型: {vl_model}\n"
            f"  Output: {self.output_dir}\n"
            f"  Log Level: {self.log_level}\n"
            f")"
        )
