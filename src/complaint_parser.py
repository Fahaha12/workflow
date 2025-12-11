"""
申诉文档解析器
根据关键字将文档分成4部分
"""
import re
from typing import Dict, Any, List
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
        
        # 标题匹配模式（关于...报告）
        self.title_pattern = r'关于[^\n]*(?:报告|情况)'
        # 编号匹配模式（部-数字编号）
        self.number_pattern = r'部-\d+'
    
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
        
        # 提取标题和编号
        title, doc_number = self._extract_title_and_number(content)
        logger.info(f"提取到标题: {title}")
        logger.info(f"提取到编号: {doc_number}")
        
        # 按关键字分割文档
        sections = self._split_sections(content)
        
        # 提取各部分的附件引用
        section2_refs = self._extract_attachment_refs(sections.get('section2', ''))
        section3_refs = self._extract_attachment_refs(sections.get('section3', ''))
        
        parsed = {
            'file_name': doc_result.get('file_name', ''),
            'title': title,
            'document_number': doc_number,
            'sections': {
                'section1_original_complaint': {'content': sections.get('section1', '')},
                'section2_investigation': {
                    'content': sections.get('section2', ''),
                    'attachment_refs': section2_refs
                },
                'section3_handling': {
                    'content': sections.get('section3', ''),
                    'attachment_refs': section3_refs
                },
                'section4_attachments': {'content': sections.get('section4', '')},
            }
        }
        
        logger.info(f"文档分割完成，共{len(sections)}个部分")
        logger.info(f"第二部分附件引用: {len(section2_refs)}个，第三部分附件引用: {len(section3_refs)}个")
        
        return parsed
    
    def _extract_title_and_number(self, content: str) -> tuple:
        """
        从文档开头提取标题和编号
        
        Args:
            content: 文档全文
            
        Returns:
            (标题, 编号) 元组
        """
        title = ''
        doc_number = ''
        
        # 获取文档前500个字符用于提取标题和编号
        header_text = content[:500] if len(content) > 500 else content
        
        # 提取标题（关于...报告/情况）
        title_match = re.search(self.title_pattern, header_text)
        if title_match:
            title = title_match.group(0).strip()
        else:
            # 备用方案：取第一行非空内容作为标题
            lines = header_text.split('\n')
            for line in lines:
                line = line.strip()
                if line and len(line) > 5:
                    title = line
                    break
        
        # 提取编号（部-数字）
        number_match = re.search(self.number_pattern, header_text)
        if number_match:
            doc_number = number_match.group(0).strip()
        else:
            # 备用方案：查找类似编号的模式
            alt_patterns = [
                r'[\u90e8\u5c40\u53f7][-—]\d{10,}',  # 部/局/号-数字
                r'\d{4}\d{6,}',  # 年份+序号
                r'[A-Z]*-?\d{10,}',  # 字母-数字
            ]
            for pattern in alt_patterns:
                match = re.search(pattern, header_text)
                if match:
                    doc_number = match.group(0).strip()
                    break
        
        return title, doc_number
    
    def _extract_attachment_refs(self, section_content: str) -> List[Dict[str, str]]:
        """
        从文档内容中提取附件引用
        
        匹配格式：
        - "见附件2"
        - "见附件2，见附件3"
        - "（附件2-用户手机号码...）"
        - "附件2-xxx"
        
        Args:
            section_content: 文档部分内容
            
        Returns:
            附件引用列表，每项包含 number, reference, context, description
        """
        refs = []
        
        if not section_content:
            return refs
        
        # 模式1: "见附件X" 格式
        pattern1 = r'见附件(\d+)'
        for match in re.finditer(pattern1, section_content):
            att_num = match.group(1)
            # 获取上下文（前后50个字符）
            start = max(0, match.start() - 50)
            end = min(len(section_content), match.end() + 50)
            context = section_content[start:end].replace('\n', ' ').strip()
            
            refs.append({
                'number': att_num,
                'reference': f'见附件{att_num}',
                'context': context,
                'description': ''
            })
        
        # 模式2: "（附件X-描述）" 格式
        pattern2 = r'[（(]附件(\d+)[-—]([^）)]+)[）)]'
        for match in re.finditer(pattern2, section_content):
            att_num = match.group(1)
            description = match.group(2).strip()
            
            # 获取上下文
            start = max(0, match.start() - 30)
            end = min(len(section_content), match.end() + 30)
            context = section_content[start:end].replace('\n', ' ').strip()
            
            # 检查是否已存在相同编号的引用，如果存在则更新描述
            existing = next((r for r in refs if r['number'] == att_num), None)
            if existing:
                if not existing['description']:
                    existing['description'] = description
            else:
                refs.append({
                    'number': att_num,
                    'reference': f'附件{att_num}',
                    'context': context,
                    'description': description
                })
        
        # 模式3: 独立的 "附件X-描述" 格式（不在括号内）
        pattern3 = r'(?<![（(])附件(\d+)[-—]([^\n,，。；;）)]{5,50})'
        for match in re.finditer(pattern3, section_content):
            att_num = match.group(1)
            description = match.group(2).strip()
            
            # 检查是否已存在
            existing = next((r for r in refs if r['number'] == att_num), None)
            if existing:
                if not existing['description']:
                    existing['description'] = description
            else:
                start = max(0, match.start() - 30)
                end = min(len(section_content), match.end() + 30)
                context = section_content[start:end].replace('\n', ' ').strip()
                
                refs.append({
                    'number': att_num,
                    'reference': f'附件{att_num}',
                    'context': context,
                    'description': description
                })
        
        # 按附件编号排序
        refs.sort(key=lambda x: int(x['number']))
        
        # 去重（保留描述最完整的）
        unique_refs = {}
        for ref in refs:
            num = ref['number']
            if num not in unique_refs:
                unique_refs[num] = ref
            elif len(ref.get('description', '')) > len(unique_refs[num].get('description', '')):
                unique_refs[num]['description'] = ref['description']
        
        return list(unique_refs.values())
    
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
