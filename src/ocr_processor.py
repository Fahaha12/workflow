"""
OCR处理模块：处理PDF和图片文件，提取文本内容
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from tqdm import tqdm
import logging

logger = logging.getLogger(__name__)


class OCRProcessor:
    """OCR处理器，支持PDF和图片文件"""
    
    def __init__(self, tesseract_path: str = None):
        """
        初始化OCR处理器
        
        Args:
            tesseract_path: Tesseract可执行文件路径（Windows需要）
        """
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            logger.info(f"使用Tesseract路径: {tesseract_path}")
        
        self.supported_image_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}
        self.supported_pdf_format = '.pdf'
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        处理单个文件（PDF或图片）
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含文件信息和提取文本的字典
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
            "pages": [],
            "metadata": {}
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
            result["error"] = str(e)
        
        return result
    
    def _process_pdf(self, file_path: Path, result: Dict) -> Dict:
        """处理PDF文件"""
        logger.info(f"处理PDF文件: {file_path.name}")
        
        # 首先尝试直接提取文本（对于可搜索的PDF）
        doc = fitz.open(file_path)
        result["metadata"]["total_pages"] = len(doc)
        
        all_text = []
        has_text = False
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            page_data = {
                "page_number": page_num + 1,
                "text": text.strip(),
                "method": "direct_extraction"
            }
            
            if text.strip():
                has_text = True
                all_text.append(text)
                result["pages"].append(page_data)
            else:
                # 如果没有文本，标记需要OCR
                page_data["needs_ocr"] = True
                result["pages"].append(page_data)
        
        doc.close()
        
        # 如果PDF没有可提取的文本，使用OCR
        if not has_text:
            logger.info(f"PDF无可提取文本，使用OCR: {file_path.name}")
            result = self._ocr_pdf(file_path, result)
        else:
            result["content"] = "\n\n".join(all_text)
            result["metadata"]["extraction_method"] = "direct"
        
        return result
    
    def _ocr_pdf(self, file_path: Path, result: Dict) -> Dict:
        """对PDF进行OCR识别"""
        try:
            # 将PDF转换为图片
            images = convert_from_path(str(file_path), dpi=300)
            
            all_text = []
            for i, image in enumerate(tqdm(images, desc=f"OCR处理 {file_path.name}")):
                text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                all_text.append(text)
                
                # 更新页面数据
                if i < len(result["pages"]):
                    result["pages"][i]["text"] = text.strip()
                    result["pages"][i]["method"] = "ocr"
                else:
                    result["pages"].append({
                        "page_number": i + 1,
                        "text": text.strip(),
                        "method": "ocr"
                    })
            
            result["content"] = "\n\n".join(all_text)
            result["metadata"]["extraction_method"] = "ocr"
            
        except Exception as e:
            logger.error(f"OCR处理PDF失败: {str(e)}")
            result["error"] = f"OCR失败: {str(e)}"
        
        return result
    
    def _process_image(self, file_path: Path, result: Dict) -> Dict:
        """处理图片文件"""
        logger.info(f"处理图片文件: {file_path.name}")
        
        try:
            image = Image.open(file_path)
            
            # 获取图片信息
            result["metadata"]["image_size"] = image.size
            result["metadata"]["image_mode"] = image.mode
            
            # OCR识别
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            
            result["content"] = text.strip()
            result["pages"] = [{
                "page_number": 1,
                "text": text.strip(),
                "method": "ocr"
            }]
            result["metadata"]["extraction_method"] = "ocr"
            
        except Exception as e:
            logger.error(f"处理图片失败: {str(e)}")
            result["error"] = f"图片处理失败: {str(e)}"
        
        return result
    
    def process_directory(self, directory: str, output_dir: str = None) -> List[Dict]:
        """
        处理目录中的所有PDF和图片文件
        
        Args:
            directory: 输入目录路径
            output_dir: 输出JSON文件的目录（可选）
            
        Returns:
            所有文件的处理结果列表
        """
        directory = Path(directory)
        
        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")
        
        # 查找所有支持的文件
        files = []
        for ext in self.supported_image_formats | {self.supported_pdf_format}:
            files.extend(directory.glob(f"*{ext}"))
        
        logger.info(f"找到 {len(files)} 个文件待处理")
        
        results = []
        for file_path in tqdm(files, desc="处理文件"):
            result = self.process_file(str(file_path))
            results.append(result)
        
        # 保存结果到JSON
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = output_dir / "ocr_results.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"OCR结果已保存到: {output_file}")
        
        return results
    
    def save_result(self, result: Dict, output_path: str):
        """
        保存单个文件的处理结果
        
        Args:
            result: 处理结果字典
            output_path: 输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存到: {output_path}")
