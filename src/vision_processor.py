"""
视觉大模型处理器
直接使用千问视觉模型（qwen-vl）识别图片内容，跳过OCR
"""
import os
import base64
import json
from pathlib import Path
from typing import Dict, List, Any
import fitz  # PyMuPDF
from PIL import Image
import io
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class VisionProcessor:
    """视觉大模型处理器，直接调用千问VL模型识别图片"""
    
    def __init__(self, api_key: str, model: str = "qwen3-vl-plus"):
        """
        初始化视觉处理器
        
        Args:
            api_key: 千问API密钥
            model: 视觉模型名称，默认qwen3-vl-plus
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = model
        self.supported_image_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif', '.webp'}
        self.supported_pdf_format = '.pdf'
        
        logger.info(f"视觉处理器初始化完成，使用模型: {model}")
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        处理单个文件（PDF或图片）
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含文件信息和提取内容的字典
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        file_ext = file_path.suffix.lower()
        
        result = {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "file_type": file_ext,
            "content": "",
            "extracted_info": {},
            "metadata": {
                "extraction_method": "vision_model"
            }
        }
        
        try:
            if file_ext == self.supported_pdf_format:
                result = self._process_pdf(file_path, result)
            elif file_ext in self.supported_image_formats:
                result = self._process_image(file_path, result)
            else:
                logger.warning(f"不支持的文件格式: {file_ext}")
                result["error"] = f"不支持的文件格式: {file_ext}"
        
        except Exception as e:
            logger.error(f"处理文件失败 {file_path}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            result["error"] = str(e)
        
        return result
    
    def _process_pdf(self, file_path: Path, result: Dict) -> Dict:
        """处理PDF文件 - 转换为图片后用视觉模型识别"""
        logger.info(f"处理PDF文件: {file_path.name}")
        
        try:
            doc = fitz.open(str(file_path))
            all_content = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # 将PDF页面转换为图片
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x放大提高清晰度
                img_data = pix.tobytes("png")
                
                # 使用视觉模型识别
                content = self._call_vision_model(img_data, f"PDF第{page_num+1}页")
                all_content.append(content)
                
                logger.info(f"PDF第{page_num+1}页识别完成")
            
            doc.close()
            
            result["content"] = "\n\n".join(all_content)
            result["metadata"]["pages"] = len(doc)
            
        except Exception as e:
            logger.error(f"处理PDF失败: {e}")
            result["error"] = str(e)
        
        return result
    
    def _process_image(self, file_path: Path, result: Dict) -> Dict:
        """处理图片文件 - 直接用视觉模型识别"""
        logger.info(f"处理图片文件: {file_path.name}")
        
        try:
            # 读取图片
            with open(file_path, "rb") as f:
                img_data = f.read()
            
            # 使用视觉模型识别
            content = self._call_vision_model(img_data, file_path.name)
            result["content"] = content
            
            # 获取图片信息
            img = Image.open(file_path)
            result["metadata"]["width"] = img.width
            result["metadata"]["height"] = img.height
            result["metadata"]["format"] = img.format
            
        except Exception as e:
            logger.error(f"处理图片失败: {e}")
            result["error"] = str(e)
        
        return result
    
    def _call_vision_model(self, image_data: bytes, image_name: str) -> str:
        """
        调用视觉大模型识别图片
        
        Args:
            image_data: 图片二进制数据
            image_name: 图片名称（用于日志）
            
        Returns:
            识别的文本内容
        """
        logger.info(f"调用视觉模型识别: {image_name}")
        
        # 将图片转换为base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # 判断图片格式
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            media_type = "image/png"
        elif image_data[:2] == b'\xff\xd8':
            media_type = "image/jpeg"
        else:
            media_type = "image/png"  # 默认
        
        # 构建提示词
        prompt = """你是图片关键信息提取专家。请仔细识别这张图片中的所有文字和关键信息。

请提取以下内容（如果存在）：
1. 号码类：手机号码、业务号码、联系号码（11位数字）
2. 业务类：套餐名称、业务类型、协议编号
3. 数字类：金额（XX元）、日期（XXXX年XX月XX日）、时间
4. 其他关键文字内容

请直接输出识别到的文字内容，保持原有格式。如果是表格，请用文字描述表格内容。
如果图片模糊或无法识别，请说明。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{base64_image}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                timeout=60
            )
            
            content = response.choices[0].message.content.strip()
            
            # 调试输出
            logger.info(f"【调试】视觉模型识别结果 ({image_name}):")
            logger.info("-" * 40)
            logger.info(content[:500] if len(content) > 500 else content)
            logger.info("-" * 40)
            
            return content
            
        except Exception as e:
            logger.error(f"视觉模型调用失败: {e}")
            return f"[识别失败: {str(e)}]"
    
    def process_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        批量处理文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            处理结果列表
        """
        results = []
        
        for file_path in file_paths:
            logger.info(f"处理文件: {file_path}")
            result = self.process_file(file_path)
            results.append(result)
        
        return results
