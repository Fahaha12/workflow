"""
PDF文本提取器
直接提取PDF中的文字内容，过滤协议模板，只保留关键信息
"""
try:
    import fitz  # PyMuPDF
except ImportError:
    import PyMuPDF as fitz

from pathlib import Path
from typing import Dict, Any, List
import re
import logging

logger = logging.getLogger(__name__)


class PDFTextExtractor:
    """PDF文本提取器 - 直接提取文字，不使用视觉识别"""
    
    def __init__(self):
        """初始化提取器"""
        # 协议模板关键词（这些内容会被过滤）
        self.template_keywords = [
            '甲方', '乙方', '协议条款', '特别约定',
            '本协议', '双方约定', '违约责任', '争议解决',
            '法律适用', '协议生效', '协议终止', '附则',
            '声明与保证', '保密条款', '知识产权', '不可抗力',
            '通知与送达', '协议变更', '协议解除', '其他事项',
            '签字盖章', '签订日期', '合同编号', '合同期限',
        ]
        
        # 重要信息关键词（这些内容会被保留）
        self.important_keywords = [
            '号码', '手机', '电话', '联系方式', '身份证',
            '金额', '费用', '价格', '套餐', '资费',
            '日期', '时间', '年', '月', '日',
            '姓名', '用户', '客户', '申请人',
            '业务', '服务', '产品', '订单',
            '账号', '账户', '卡号', '流水号',
            '地址', '省', '市', '区', '县',
            '投诉', '申诉', '问题', '原因',
        ]
    
    def extract_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        从PDF提取文本内容
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            提取结果
        """
        logger.info(f"开始提取PDF文本: {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
            
            # 提取所有页面文本
            full_text = ""
            page_texts = []
            
            # 保存页数
            total_pages = len(doc)
            
            for page_num in range(total_pages):
                page = doc[page_num]
                page_text = page.get_text()
                page_texts.append({
                    'page': page_num + 1,
                    'text': page_text
                })
                full_text += page_text + "\n"
            
            # 关闭文档
            doc.close()
            
            # 过滤协议模板内容
            filtered_text = self._filter_template_content(full_text)
            
            # 提取关键信息
            key_info = self._extract_key_information(filtered_text)
            
            logger.info(f"PDF提取完成，共{total_pages}页，提取{len(filtered_text)}字符")
            
            return {
                'file_name': Path(pdf_path).name,
                'file_type': 'pdf',
                'total_pages': total_pages,
                'full_text': full_text,
                'filtered_text': filtered_text,
                'key_info': key_info,
                'page_texts': page_texts,
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"PDF提取失败: {e}")
            return {
                'file_name': Path(pdf_path).name,
                'file_type': 'pdf',
                'error': str(e),
                'status': 'failed'
            }
    
    def _filter_template_content(self, text: str) -> str:
        """过滤协议模板内容，保留关键信息"""
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否包含重要关键词
            has_important = any(kw in line for kw in self.important_keywords)
            
            # 检查是否是协议模板内容
            is_template = any(kw in line for kw in self.template_keywords)
            
            # 过滤规则：
            # 1. 包含重要关键词的保留
            # 2. 不包含模板关键词的保留
            # 3. 太短的行（<5字符）跳过
            if len(line) < 5:
                continue
            
            if has_important:
                filtered_lines.append(line)
            elif not is_template:
                # 进一步检查：是否是有意义的内容
                if self._is_meaningful_content(line):
                    filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def _is_meaningful_content(self, line: str) -> bool:
        """判断是否是有意义的内容"""
        # 过滤纯数字、纯符号
        if re.match(r'^[\d\s\-_\.]+$', line):
            return False
        
        # 过滤页码、页眉页脚
        if re.match(r'^第\s*\d+\s*页', line):
            return False
        if re.match(r'^\d+\s*/\s*\d+$', line):
            return False
        
        # 过滤常见的无意义内容
        meaningless_patterns = [
            r'^[\*\-=]{3,}$',  # 分隔线
            r'^第[一二三四五六七八九十]+[条章节]',  # 条款编号
            r'^\d+[\.\)]\s*$',  # 纯编号
        ]
        
        for pattern in meaningless_patterns:
            if re.match(pattern, line):
                return False
        
        return True
    
    def _extract_key_information(self, text: str) -> Dict[str, List[str]]:
        """提取关键信息"""
        key_info = {
            'phone_numbers': [],
            'amounts': [],
            'dates': [],
            'names': [],
            'addresses': [],
            'business_info': [],
        }
        
        # 提取手机号
        phone_pattern = r'1[3-9]\d{9}'
        key_info['phone_numbers'] = list(set(re.findall(phone_pattern, text)))
        
        # 提取金额
        amount_patterns = [
            r'¥\s*[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*元',
            r'人民币\s*[\d,]+\.?\d*',
        ]
        for pattern in amount_patterns:
            amounts = re.findall(pattern, text)
            key_info['amounts'].extend(amounts)
        key_info['amounts'] = list(set(key_info['amounts']))
        
        # 提取日期
        date_patterns = [
            r'\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?',
            r'\d{4}\.\d{1,2}\.\d{1,2}',
            r'\d{4}/\d{1,2}/\d{1,2}',
        ]
        for pattern in date_patterns:
            dates = re.findall(pattern, text)
            key_info['dates'].extend(dates)
        key_info['dates'] = list(set(key_info['dates']))
        
        # 提取业务信息（套餐、资费等）
        business_patterns = [
            r'[\u4e00-\u9fa5]*套餐[\u4e00-\u9fa5]*',
            r'[\u4e00-\u9fa5]*资费[\u4e00-\u9fa5]*',
            r'[\u4e00-\u9fa5]*业务[\u4e00-\u9fa5]*',
        ]
        for pattern in business_patterns:
            matches = re.findall(pattern, text)
            key_info['business_info'].extend([m for m in matches if len(m) > 2])
        key_info['business_info'] = list(set(key_info['business_info']))[:10]  # 限制数量
        
        # 提取地址信息
        address_pattern = r'[\u4e00-\u9fa5]{2,}省[\u4e00-\u9fa5]{2,}市[\u4e00-\u9fa5]{2,}[区县]?[\u4e00-\u9fa5]*'
        key_info['addresses'] = list(set(re.findall(address_pattern, text)))
        
        return key_info
    
    def extract_batch(self, pdf_files: List[str]) -> List[Dict[str, Any]]:
        """批量提取PDF文本"""
        results = []
        
        for pdf_file in pdf_files:
            logger.info(f"处理PDF: {pdf_file}")
            result = self.extract_from_pdf(pdf_file)
            results.append(result)
        
        return results
    
    def get_summary(self, extract_result: Dict[str, Any]) -> str:
        """生成提取结果摘要"""
        if extract_result['status'] != 'success':
            return f"提取失败: {extract_result.get('error', '未知错误')}"
        
        key_info = extract_result['key_info']
        
        summary_parts = [
            f"文件: {extract_result['file_name']}",
            f"页数: {extract_result['total_pages']}",
            f"提取文本: {len(extract_result['filtered_text'])}字符",
        ]
        
        if key_info['phone_numbers']:
            summary_parts.append(f"手机号: {', '.join(key_info['phone_numbers'][:3])}")
        
        if key_info['amounts']:
            summary_parts.append(f"金额: {', '.join(key_info['amounts'][:3])}")
        
        if key_info['dates']:
            summary_parts.append(f"日期: {', '.join(key_info['dates'][:3])}")
        
        if key_info['business_info']:
            summary_parts.append(f"业务: {', '.join(key_info['business_info'][:3])}")
        
        return ' | '.join(summary_parts)
