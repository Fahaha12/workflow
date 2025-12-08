"""
申诉文档解析器
根据关键字将文档分成4部分
"""
import re
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ComplaintDocumentParser:
    """申诉文档解析器 - 仅分割文档，不解析内容"""
    
    def __init__(self):
        """初始化解析器"""
        # 四部分的关键字匹配模式
        self.section_patterns = {
            'section1': r'[一1][\s、.．]*用户申诉原文',
            'section2': r'[二2][\s、.．]*申诉核查情况',
            'section3': r'[三3][\s、.．]*申诉后处理情况',
            'section4': r'[四4][\s、.．]*附件(?:名称|列表)?',
        }
    
    def parse_document(self, doc_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析申诉文档，仅按关键字分割为4部分
        
        Args:
            doc_result: Word文档解析结果
            
        Returns:
            分割后的文档结构
        """
        logger.info("开始分割申诉文档...")
        
        content = doc_result.get('content', '')
        
        # 按关键字分割文档
        sections = self._split_sections(content)
        
        parsed = {
            'file_name': doc_result.get('file_name', ''),
            'sections': {
                'section1_original_complaint': {'content': sections.get('section1', '')},
                'section2_investigation': {'content': sections.get('section2', '')},
                'section3_handling': {'content': sections.get('section3', '')},
                'section4_attachments': {'content': sections.get('section4', '')},
            }
        }
        
        logger.info(f"文档分割完成，共{len(sections)}个部分")
        
        return parsed
    
    def _split_sections(self, content: str) -> Dict[str, str]:
        """按关键字分割文档为4部分"""
        sections = {}
        
        # 查找各部分的位置
        positions = {}
        for key, pattern in self.section_patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                positions[key] = match.start()
                logger.debug(f"找到 {key}，位置: {match.start()}")
        
        # 按位置排序
        sorted_positions = sorted(positions.items(), key=lambda x: x[1])
        
        # 提取各部分内容
        for i, (key, start_pos) in enumerate(sorted_positions):
            if i < len(sorted_positions) - 1:
                end_pos = sorted_positions[i + 1][1]
            else:
                end_pos = len(content)
            
            sections[key] = content[start_pos:end_pos].strip()
        
        return sections
