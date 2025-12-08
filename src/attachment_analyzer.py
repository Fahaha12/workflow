"""
附件内容分析器
为每个附件生成详细的关键内容核查表
"""
import re
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class AttachmentAnalyzer:
    """附件内容分析器"""
    
    def __init__(self):
        """初始化分析器"""
        pass
    
    def generate_attachment_checklist(self,
                                     ocr_results: List[Dict[str, Any]],
                                     section2: Dict[str, Any],
                                     section3: Dict[str, Any]) -> Dict[str, Any]:
        """
        为每个附件生成关键内容核查表
        
        Args:
            ocr_results: OCR识别结果列表
            section2: 第二部分（申诉核查情况）
            section3: 第三部分（申诉后处理情况）
            
        Returns:
            附件核查表
        """
        logger.info("生成附件关键内容核查表...")
        
        checklist = {
            'total_attachments': len(ocr_results),
            'attachments': []
        }
        
        # 提取文档中的关键数据作为参照
        doc_reference = self._extract_document_reference(section2, section3)
        
        # 为每个附件生成核查表
        for idx, ocr_result in enumerate(ocr_results, 1):
            attachment_check = self._analyze_single_attachment(
                idx, ocr_result, doc_reference, section2, section3
            )
            checklist['attachments'].append(attachment_check)
        
        logger.info(f"已生成 {len(ocr_results)} 个附件的核查表")
        
        return checklist
    
    def _extract_document_reference(self, 
                                   section2: Dict[str, Any],
                                   section3: Dict[str, Any]) -> Dict[str, Any]:
        """提取文档中的参照数据"""
        
        # 合并第二、三部分的关键数据
        section2_data = section2.get('key_data', {})
        section3_data = section3.get('key_data', {})
        
        return {
            'phone_numbers': list(set(
                section2_data.get('phone_numbers', []) + 
                section3_data.get('phone_numbers', [])
            )),
            'business_numbers': list(set(
                section2_data.get('business_numbers', []) + 
                section3_data.get('business_numbers', [])
            )),
            'amounts': list(set(
                section2_data.get('amounts', []) + 
                section3_data.get('amounts', [])
            )),
            'dates': list(set(
                section2_data.get('dates', []) + 
                section3_data.get('dates', [])
            )),
            'times': list(set(
                section2_data.get('times', []) + 
                section3_data.get('times', [])
            ))
        }
    
    def _analyze_single_attachment(self,
                                   index: int,
                                   ocr_result: Dict[str, Any],
                                   doc_reference: Dict[str, Any],
                                   section2: Dict[str, Any],
                                   section3: Dict[str, Any]) -> Dict[str, Any]:
        """分析单个附件"""
        
        filename = ocr_result.get('file_name', f'附件{index}')
        content = ocr_result.get('content', '')
        file_type = ocr_result.get('file_type', '')
        
        logger.info(f"分析附件 {index}: {filename}")
        
        # 提取附件中的关键信息
        att_info = self._extract_attachment_info(content)
        
        # 查找文档中对该附件的引用
        references = self._find_attachment_references(index, filename, section2, section3)
        
        # 核对关键数据
        data_check = self._check_data_consistency(att_info, doc_reference)
        
        # 生成核查表
        checklist = {
            'index': index,
            'filename': filename,
            'file_type': file_type,
            'file_size': ocr_result.get('metadata', {}).get('file_size', 'Unknown'),
            'ocr_method': ocr_result.get('metadata', {}).get('extraction_method', 'Unknown'),
            
            # 文档引用情况
            'document_references': {
                'section2_refs': references['section2'],
                'section3_refs': references['section3'],
                'total_refs': len(references['section2']) + len(references['section3']),
                'is_referenced': len(references['section2']) + len(references['section3']) > 0
            },
            
            # 附件关键内容
            'key_content': {
                'phone_numbers': {
                    'found': att_info['phone_numbers'],
                    'count': len(att_info['phone_numbers']),
                    'match_status': self._match_status(att_info['phone_numbers'], doc_reference['phone_numbers'])
                },
                'business_numbers': {
                    'found': att_info['business_numbers'],
                    'count': len(att_info['business_numbers']),
                    'match_status': self._match_status(att_info['business_numbers'], doc_reference['business_numbers'])
                },
                'amounts': {
                    'found': att_info['amounts'],
                    'count': len(att_info['amounts']),
                    'match_status': self._match_status(att_info['amounts'], doc_reference['amounts'])
                },
                'dates': {
                    'found': att_info['dates'],
                    'count': len(att_info['dates']),
                    'match_status': self._match_status(att_info['dates'], doc_reference['dates'])
                },
                'times': {
                    'found': att_info['times'],
                    'count': len(att_info['times']),
                    'match_status': self._match_status(att_info['times'], doc_reference['times'])
                }
            },
            
            # 数据一致性核查
            'consistency_check': data_check,
            
            # 内容摘要
            'content_summary': {
                'total_length': len(content),
                'word_count': len(content.split()),
                'has_content': len(content.strip()) > 0,
                'quality': self._assess_quality(content, ocr_result)
            },
            
            # 核查结论
            'conclusion': self._generate_conclusion(att_info, doc_reference, references, data_check)
        }
        
        return checklist
    
    def _extract_attachment_info(self, content: str) -> Dict[str, List[str]]:
        """从附件内容中提取关键信息"""
        return {
            'phone_numbers': list(set(re.findall(r'1[3-9]\d{9}', content))),
            'business_numbers': list(set(re.findall(r'\b\d{10,15}\b', content))),
            'amounts': list(set(re.findall(r'¥?\s*\d+\.?\d*\s*元', content))),
            'dates': list(set(re.findall(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?', content))),
            'times': list(set(re.findall(r'\d{1,2}:\d{2}(?::\d{2})?', content))),
        }
    
    def _find_attachment_references(self,
                                   index: int,
                                   filename: str,
                                   section2: Dict[str, Any],
                                   section3: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """查找文档中对该附件的引用"""
        
        refs = {
            'section2': [],
            'section3': []
        }
        
        # 精确匹配附件编号的模式
        # 匹配 "附件1" 但不匹配 "附件10"、"附件11" 等
        index_str = str(index)
        
        def is_exact_match(ref_number: str, ref_text: str) -> bool:
            """精确匹配附件编号"""
            # 方法1：直接比较编号
            if ref_number == index_str:
                return True
            
            # 方法2：使用正则精确匹配 "附件X" 格式
            # 确保X后面不是数字（避免附件1匹配到附件10）
            pattern = rf'附件{index_str}(?!\d)'
            if re.search(pattern, ref_text):
                return True
            
            return False
        
        # 在第二部分查找引用
        for ref in section2.get('attachment_refs', []):
            ref_number = ref.get('number', '')
            ref_text = ref.get('reference', '')
            if is_exact_match(ref_number, ref_text):
                refs['section2'].append({
                    'reference': ref_text,
                    'context': ref.get('context', '')[:100]  # 限制长度
                })
        
        # 在第三部分查找引用
        for ref in section3.get('attachment_refs', []):
            ref_number = ref.get('number', '')
            ref_text = ref.get('reference', '')
            if is_exact_match(ref_number, ref_text):
                refs['section3'].append({
                    'reference': ref_text,
                    'context': ref.get('context', '')[:100]
                })
        
        return refs
    
    def _match_status(self, att_data: List[str], doc_data: List[str]) -> Dict[str, Any]:
        """检查数据匹配状态"""
        if not att_data:
            return {
                'status': 'empty',
                'message': '附件中未找到此类数据'
            }
        
        matched = [item for item in att_data if item in doc_data]
        unmatched = [item for item in att_data if item not in doc_data]
        
        if len(matched) == len(att_data):
            return {
                'status': 'full_match',
                'message': '完全匹配',
                'matched': matched
            }
        elif len(matched) > 0:
            return {
                'status': 'partial_match',
                'message': '部分匹配',
                'matched': matched,
                'unmatched': unmatched
            }
        else:
            return {
                'status': 'no_match',
                'message': '不匹配',
                'unmatched': unmatched
            }
    
    def _check_data_consistency(self,
                                att_info: Dict[str, List[str]],
                                doc_reference: Dict[str, Any]) -> Dict[str, Any]:
        """核查数据一致性"""
        
        issues = []
        
        # 检查手机号码
        for phone in att_info['phone_numbers']:
            if phone not in doc_reference['phone_numbers']:
                issues.append({
                    'type': 'phone_not_in_doc',
                    'severity': 'warning',
                    'data': phone,
                    'message': f'附件中的号码 {phone} 在文档中未提及'
                })
        
        # 检查金额
        for amount in att_info['amounts']:
            if amount not in doc_reference['amounts']:
                issues.append({
                    'type': 'amount_not_in_doc',
                    'severity': 'critical',
                    'data': amount,
                    'message': f'附件中的金额 {amount} 与文档中的金额不一致'
                })
        
        # 检查日期
        for date in att_info['dates']:
            if date not in doc_reference['dates']:
                issues.append({
                    'type': 'date_not_in_doc',
                    'severity': 'warning',
                    'data': date,
                    'message': f'附件中的日期 {date} 在文档中未提及'
                })
        
        return {
            'total_issues': len(issues),
            'critical_issues': len([i for i in issues if i['severity'] == 'critical']),
            'warnings': len([i for i in issues if i['severity'] == 'warning']),
            'issues': issues,
            'is_consistent': len([i for i in issues if i['severity'] == 'critical']) == 0
        }
    
    def _assess_quality(self, content: str, ocr_result: Dict) -> str:
        """评估附件质量"""
        if len(content.strip()) == 0:
            return '无内容'
        
        # 检查OCR质量
        if ocr_result.get('metadata', {}).get('extraction_method') == 'ocr':
            special_char_ratio = len(re.findall(r'[^\w\s\u4e00-\u9fff]', content)) / max(len(content), 1)
            if special_char_ratio > 0.3:
                return 'OCR质量较差'
            elif special_char_ratio > 0.15:
                return 'OCR质量一般'
            else:
                return 'OCR质量良好'
        
        return '质量良好'
    
    def _generate_conclusion(self,
                           att_info: Dict[str, List[str]],
                           doc_reference: Dict[str, Any],
                           references: Dict[str, List],
                           data_check: Dict[str, Any]) -> Dict[str, Any]:
        """生成核查结论"""
        
        # 判断附件是否被引用
        is_referenced = len(references['section2']) + len(references['section3']) > 0
        
        # 判断数据是否一致
        is_consistent = data_check['is_consistent']
        
        # 判断是否有内容
        has_key_content = any([
            att_info['phone_numbers'],
            att_info['business_numbers'],
            att_info['amounts'],
            att_info['dates']
        ])
        
        # 生成结论
        if is_referenced and is_consistent and has_key_content:
            status = 'pass'
            message = '✅ 附件内容完整，数据一致，引用正确'
        elif not is_referenced:
            status = 'warning'
            message = '⚠️ 附件未在文档中被引用'
        elif not is_consistent:
            status = 'fail'
            message = f'❌ 发现 {data_check["critical_issues"]} 个严重数据不一致问题'
        elif not has_key_content:
            status = 'warning'
            message = '⚠️ 附件中未提取到关键数据'
        else:
            status = 'warning'
            message = f'⚠️ 存在 {data_check["warnings"]} 个警告'
        
        return {
            'status': status,
            'message': message,
            'is_referenced': is_referenced,
            'is_consistent': is_consistent,
            'has_key_content': has_key_content
        }
    
    def format_checklist_as_table(self, checklist: Dict[str, Any]) -> str:
        """将核查表格式化为Markdown表格"""
        
        lines = []
        lines.append("# 附件关键内容核查表\n")
        lines.append(f"**总附件数**: {checklist['total_attachments']}\n")
        lines.append("---\n")
        
        for att in checklist['attachments']:
            lines.append(f"\n## 附件 {att['index']}: {att['filename']}\n")
            
            # 基本信息表
            lines.append("### 基本信息\n")
            lines.append("| 项目 | 内容 |")
            lines.append("|------|------|")
            lines.append(f"| 文件名 | {att['filename']} |")
            lines.append(f"| 文件类型 | {att['file_type']} |")
            lines.append(f"| 文件大小 | {att['file_size']} |")
            lines.append(f"| 识别方式 | {att['ocr_method']} |")
            lines.append(f"| 内容质量 | {att['content_summary']['quality']} |")
            lines.append("")
            
            # 文档引用情况
            lines.append("### 文档引用情况\n")
            lines.append("| 项目 | 内容 |")
            lines.append("|------|------|")
            lines.append(f"| 是否被引用 | {'✅ 是' if att['document_references']['is_referenced'] else '❌ 否'} |")
            lines.append(f"| 引用次数 | {att['document_references']['total_refs']} |")
            
            # 去重后显示引用
            if att['document_references']['section2_refs']:
                unique_refs = list(set([r['reference'] for r in att['document_references']['section2_refs']]))
                lines.append(f"| 第二部分引用 | {', '.join(unique_refs)} |")
            
            if att['document_references']['section3_refs']:
                unique_refs = list(set([r['reference'] for r in att['document_references']['section3_refs']]))
                lines.append(f"| 第三部分引用 | {', '.join(unique_refs)} |")
            
            lines.append("")
            
            # 关键内容核查表
            lines.append("### 关键内容核查\n")
            lines.append("| 数据类型 | 提取数量 | 匹配状态 | 具体内容 |")
            lines.append("|---------|---------|---------|---------|")
            
            # 手机号码
            phone_data = att['key_content']['phone_numbers']
            phone_status = phone_data['match_status']['status']
            phone_icon = self._get_status_icon(phone_status)
            phone_content = ', '.join(phone_data['found'][:3]) if phone_data['found'] else '-'
            lines.append(f"| 手机号码 | {phone_data['count']} | {phone_icon} {phone_data['match_status']['message']} | {phone_content} |")
            
            # 业务号码
            business_data = att['key_content']['business_numbers']
            business_status = business_data['match_status']['status']
            business_icon = self._get_status_icon(business_status)
            business_content = ', '.join(business_data['found'][:3]) if business_data['found'] else '-'
            lines.append(f"| 业务号码 | {business_data['count']} | {business_icon} {business_data['match_status']['message']} | {business_content} |")
            
            # 金额
            amount_data = att['key_content']['amounts']
            amount_status = amount_data['match_status']['status']
            amount_icon = self._get_status_icon(amount_status)
            amount_content = ', '.join(amount_data['found'][:3]) if amount_data['found'] else '-'
            lines.append(f"| 金额 | {amount_data['count']} | {amount_icon} {amount_data['match_status']['message']} | {amount_content} |")
            
            # 日期
            date_data = att['key_content']['dates']
            date_status = date_data['match_status']['status']
            date_icon = self._get_status_icon(date_status)
            date_content = ', '.join(date_data['found'][:3]) if date_data['found'] else '-'
            lines.append(f"| 日期 | {date_data['count']} | {date_icon} {date_data['match_status']['message']} | {date_content} |")
            
            # 时间
            time_data = att['key_content']['times']
            time_status = time_data['match_status']['status']
            time_icon = self._get_status_icon(time_status)
            time_content = ', '.join(time_data['found'][:3]) if time_data['found'] else '-'
            lines.append(f"| 时间 | {time_data['count']} | {time_icon} {time_data['match_status']['message']} | {time_content} |")
            
            lines.append("")
            
            # 数据一致性问题
            if att['consistency_check']['issues']:
                lines.append("### ⚠️ 数据一致性问题\n")
                lines.append("| 严重程度 | 类型 | 数据 | 说明 |")
                lines.append("|---------|------|------|------|")
                
                for issue in att['consistency_check']['issues']:
                    severity_icon = '🔴' if issue['severity'] == 'critical' else '🟡'
                    lines.append(f"| {severity_icon} {issue['severity']} | {issue['type']} | {issue['data']} | {issue['message']} |")
                
                lines.append("")
            
            # 核查结论
            lines.append("### 核查结论\n")
            conclusion = att['conclusion']
            lines.append(f"**{conclusion['message']}**\n")
            lines.append("| 检查项 | 结果 |")
            lines.append("|--------|------|")
            lines.append(f"| 文档引用 | {'✅ 已引用' if conclusion['is_referenced'] else '❌ 未引用'} |")
            lines.append(f"| 数据一致性 | {'✅ 一致' if conclusion['is_consistent'] else '❌ 不一致'} |")
            lines.append(f"| 关键内容 | {'✅ 有' if conclusion['has_key_content'] else '❌ 无'} |")
            
            lines.append("\n---\n")
        
        return '\n'.join(lines)
    
    def _get_status_icon(self, status: str) -> str:
        """获取状态图标"""
        icons = {
            'full_match': '✅',
            'partial_match': '⚠️',
            'no_match': '❌',
            'empty': '➖'
        }
        return icons.get(status, '❓')
