"""
附件名称检查器
从文件名中提取附件编号和名称，并与文档中的附件列表对比
"""
import re
from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class AttachmentNameChecker:
    """附件名称检查器"""
    
    def extract_attachment_info_from_filename(self, filename: str) -> Dict[str, Any]:
        """
        从文件名中提取附件信息
        
        文件名格式示例：
        - "1-392021-.pdf" -> 编号1, 名称"392021"
        - "6-18638511201.jpg" -> 编号6, 名称"18638511201"
        - "16-20251019-.jpg" -> 编号16, 名称"20251019"
        - "3--.jpg" -> 编号3, 名称""（空）
        
        Args:
            filename: 文件名
            
        Returns:
            附件信息字典
        """
        # 去掉扩展名
        if '.' in filename:
            name_without_ext = filename.rsplit('.', 1)[0]
            file_ext = filename.rsplit('.', 1)[1]
        else:
            name_without_ext = filename
            file_ext = ''
        
        # 匹配格式：数字-内容（内容可能为空或包含多个连字符）
        pattern = r'^(\d+)-(.*)$'
        match = re.match(pattern, name_without_ext)
        
        if match:
            number = match.group(1)
            name_part = match.group(2)
            
            # 清理名称：去掉首尾的连字符和空格
            name_part = name_part.strip('-').strip()
            
            # 如果名称为空，设置为空字符串
            display_name = name_part if name_part else ''
            
            logger.info(f"解析文件名: {filename} -> 编号:{number}, 名称:{display_name or '(空)'}")
            
            return {
                'number': number,
                'name': display_name,
                'filename': filename,
                'file_ext': file_ext,
                'parsed': True
            }
        else:
            # 无法解析，返回原文件名
            logger.warning(f"无法解析文件名: {filename}")
            return {
                'number': '',
                'name': filename,
                'filename': filename,
                'file_ext': file_ext,
                'parsed': False
            }
    
    def check_attachment_names(self, 
                               section4_attachments: List[Dict[str, Any]],
                               ocr_results: List[Dict[str, Any]],
                               uploaded_files: List[str]) -> Dict[str, Any]:
        """
        检查附件名称一致性
        
        Args:
            section4_attachments: 第四部分的附件列表
            ocr_results: OCR结果列表
            uploaded_files: 上传的文件名列表
            
        Returns:
            检查结果
        """
        logger.info("检查附件名称一致性...")
        
        issues = []
        matched_attachments = []
        unmatched_files = []
        
        # 1. 从上传文件中提取附件信息
        uploaded_att_info = []
        for uploaded_file in uploaded_files:
            info = self.extract_attachment_info_from_filename(uploaded_file)
            uploaded_att_info.append(info)
            logger.info(f"解析文件: {uploaded_file} -> 编号:{info['number']}, 名称:{info['name']}")
        
        # 2. 对比文档中的附件列表与上传文件
        for doc_att in section4_attachments:
            doc_num = doc_att.get('number', '')
            doc_name = doc_att.get('name', '')
            
            # 查找匹配的上传文件
            found = False
            matched_file = None
            
            for uploaded_info in uploaded_att_info:
                # 匹配条件：编号相同
                if uploaded_info['number'] == doc_num:
                    found = True
                    matched_file = uploaded_info['filename']
                    
                    # 检查名称是否一致
                    if doc_name and uploaded_info['name']:
                        # 名称应该包含在文件名中
                        if doc_name not in uploaded_info['name'] and uploaded_info['name'] not in doc_name:
                            issues.append({
                                'severity': 'warning',
                                'type': 'name_mismatch',
                                'attachment_number': doc_num,
                                'doc_name': doc_name,
                                'file_name': uploaded_info['name'],
                                'description': f'附件{doc_num}名称不一致：文档中为"{doc_name}"，文件名为"{uploaded_info["name"]}"',
                                'suggestion': '检查附件名称是否正确'
                            })
                    
                    matched_attachments.append({
                        'number': doc_num,
                        'doc_name': doc_name,
                        'file_name': uploaded_info['filename'],
                        'extracted_name': uploaded_info['name'],
                        'status': '✅ 已匹配'
                    })
                    break
            
            if not found:
                issues.append({
                    'severity': 'critical',
                    'type': 'attachment_not_found',
                    'attachment_number': doc_num,
                    'doc_name': doc_name,
                    'description': f'附件{doc_num}（{doc_name}）未找到对应的上传文件',
                    'suggestion': f'请上传编号为{doc_num}的附件'
                })
                
                matched_attachments.append({
                    'number': doc_num,
                    'doc_name': doc_name,
                    'file_name': None,
                    'extracted_name': None,
                    'status': '❌ 未找到'
                })
        
        # 3. 检查是否有多余的上传文件
        for uploaded_info in uploaded_att_info:
            if uploaded_info['parsed']:
                found = any(att['number'] == uploaded_info['number'] for att in section4_attachments)
                if not found:
                    unmatched_files.append(uploaded_info['filename'])
                    issues.append({
                        'severity': 'warning',
                        'type': 'unlisted_file',
                        'file_name': uploaded_info['filename'],
                        'description': f'文件"{uploaded_info["filename"]}"（编号{uploaded_info["number"]}）未在文档附件列表中',
                        'suggestion': '将该附件添加到文档的附件列表中'
                    })
        
        return {
            'matched_attachments': matched_attachments,
            'unmatched_files': unmatched_files,
            'issues': issues,
            'total_doc_attachments': len(section4_attachments),
            'total_uploaded_files': len(uploaded_files),
            'matched_count': len([a for a in matched_attachments if a['status'] == '✅ 已匹配'])
        }
    
    def format_attachment_comparison_table(self, check_result: Dict[str, Any]) -> str:
        """
        生成附件对比表格（Markdown格式）
        
        Args:
            check_result: 检查结果
            
        Returns:
            Markdown表格
        """
        lines = []
        lines.append("## 附件名称对比表\n")
        lines.append("| 编号 | 文档中的名称 | 上传文件名 | 提取的名称 | 状态 |")
        lines.append("|------|-------------|-----------|-----------|------|")
        
        for att in check_result['matched_attachments']:
            number = att['number']
            doc_name = att['doc_name'] or '-'
            file_name = att['file_name'] or '-'
            extracted_name = att['extracted_name'] or '-'
            status = att['status']
            
            lines.append(f"| {number} | {doc_name} | {file_name} | {extracted_name} | {status} |")
        
        lines.append("")
        lines.append(f"**统计**: 文档中{check_result['total_doc_attachments']}个附件，上传{check_result['total_uploaded_files']}个文件，匹配{check_result['matched_count']}个")
        
        if check_result['unmatched_files']:
            lines.append(f"\n**未列出的文件**: {', '.join(check_result['unmatched_files'])}")
        
        return '\n'.join(lines)
