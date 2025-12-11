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
        
        # 核对关键数据（操作指引类附件跳过一致性检查）
        if att_info.get('is_operation_guide', False):
            data_check = {
                'is_consistent': True,
                'issues': [],
                'critical_issues': 0,
                'warnings': 0,
                'skipped': True,
                'skip_reason': '操作指引类附件，无需核验业务数据'
            }
        else:
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
                'content_type': att_info.get('content_type', '未分类'),
                'content_summary': att_info.get('content_summary', ''),
                'is_operation_guide': att_info.get('is_operation_guide', False),
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
    
    def _extract_attachment_info(self, content: str) -> Dict[str, Any]:
        """从附件内容中提取关键信息"""
        # 判断是否为操作指引类（与业务数据无关）
        is_guide = self._is_operation_guide(content)
        
        # 提取视觉模型识别的内容类型
        content_type = self._extract_content_type(content)
        if content_type == '未分类':
            content_type = '操作指引' if is_guide else '业务数据'
        
        # 提取内容摘要
        content_summary = self._extract_content_summary(content)
        
        return {
            'phone_numbers': list(set(re.findall(r'(?<!\d)1[3-9]\d{9}(?!\d)', content))),
            'business_numbers': list(set(re.findall(r'\b\d{10,15}\b', content))),
            'amounts': list(set(re.findall(r'¥?\s*\d+\.?\d*\s*元', content))),
            'dates': list(set(re.findall(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?', content))),
            'times': list(set(re.findall(r'\d{1,2}:\d{2}(?::\d{2})?', content))),
            'is_operation_guide': is_guide or content_type == '操作指引',
            'content_type': content_type,
            'content_summary': content_summary
        }
    
    def _is_operation_guide(self, content: str) -> bool:
        """判断附件是否为操作指引类（与具体业务数据无关）"""
        # 检查视觉模型是否已标注
        if '【操作指引类' in content or '操作指引类-与具体业务数据无关' in content:
            return True
        if '【操作指引】' in content:
            return True
        
        # 根据文件名和内容关键词判断
        guide_keywords = [
            '销户入口', '操作入口', '知识库', '操作指引', '操作说明',
            '如何办理', '办理流程', '办理方式', '办理入口',
            '手厅', 'APP截图', '界面截图'
        ]
        
        content_lower = content.lower()
        for keyword in guide_keywords:
            if keyword in content_lower:
                return True
        
        return False
    
    def _extract_content_type(self, content: str) -> str:
        """从视觉模型输出中提取内容类型"""
        type_mapping = {
            '【业务凭证】': '业务凭证',
            '【账单明细】': '账单明细',
            '【记录查询】': '记录查询',
            '【沟通记录】': '沟通记录',
            '【操作指引】': '操作指引',
            '【操作指引类': '操作指引',
            '【其他】': '其他'
        }
        
        for marker, type_name in type_mapping.items():
            if marker in content:
                return type_name
        
        return '未分类'
    
    def _extract_content_summary(self, content: str) -> str:
        """从视觉模型输出中提取内容摘要"""
        # 查找 **内容摘要**：后面的内容
        import re
        match = re.search(r'\*\*内容摘要\*\*[：:]\s*(.+?)(?:\n|$)', content)
        if match:
            return match.group(1).strip()
        
        # 备用：取前100个字符
        clean_content = content.replace('【', '').replace('】', '')
        return clean_content[:100] + '...' if len(clean_content) > 100 else clean_content
    
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
        
        index_str = str(index)
        
        def is_exact_match(ref_number: str) -> bool:
            """精确匹配附件编号"""
            return ref_number == index_str
        
        # 在第二部分查找引用
        for ref in section2.get('attachment_refs', []):
            ref_number = ref.get('number', '')
            if is_exact_match(ref_number):
                refs['section2'].append({
                    'reference': ref.get('reference', ''),
                    'description': ref.get('description', ''),
                    'context': ref.get('context', '')[:100]
                })
        
        # 在第三部分查找引用
        for ref in section3.get('attachment_refs', []):
            ref_number = ref.get('number', '')
            if is_exact_match(ref_number):
                refs['section3'].append({
                    'reference': ref.get('reference', ''),
                    'description': ref.get('description', ''),
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
                                att_info: Dict[str, Any],
                                doc_reference: Dict[str, Any]) -> Dict[str, Any]:
        """核查数据一致性 - 简化版，与三维度核验报告保持一致"""
        
        # 简化的一致性检查：只检查是否有明显冲突
        # 不再对每个数据项进行严格匹配，因为三维度核验报告会由AI智能判断
        
        issues = []
        
        # 只检查关键的业务号码是否一致（如果文档和附件都有号码）
        doc_phones = doc_reference.get('phone_numbers', [])
        att_phones = att_info.get('phone_numbers', [])
        
        # 如果文档中有明确的业务号码，检查附件中是否包含
        if doc_phones and att_phones:
            # 检查是否有任何匹配
            has_match = any(p in doc_phones for p in att_phones)
            if not has_match and len(att_phones) == 1 and len(doc_phones) == 1:
                # 只有在双方都只有一个号码且不匹配时才报告问题
                issues.append({
                    'type': 'phone_mismatch',
                    'severity': 'warning',
                    'data': att_phones[0],
                    'message': f'附件号码 {att_phones[0]} 与文档号码 {doc_phones[0]} 不一致'
                })
        
        # 金额检查也简化：只有明显冲突才报告
        # 不再逐个检查，因为附件中可能有很多金额信息
        
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
                           att_info: Dict[str, Any],
                           doc_reference: Dict[str, Any],
                           references: Dict[str, List],
                           data_check: Dict[str, Any]) -> Dict[str, Any]:
        """生成核查结论"""
        
        # 判断附件是否被引用
        is_referenced = len(references['section2']) + len(references['section3']) > 0
        
        # 判断数据是否一致
        is_consistent = data_check['is_consistent']
        
        # 判断是否为操作指引类
        is_operation_guide = att_info.get('is_operation_guide', False)
        
        # 判断是否有内容
        has_key_content = any([
            att_info.get('phone_numbers', []),
            att_info.get('business_numbers', []),
            att_info.get('amounts', []),
            att_info.get('dates', [])
        ])
        
        # 生成结论 - 与三维度核验报告保持一致
        # 主要关注数据一致性，引用情况仅作为参考信息
        if is_operation_guide:
            status = 'pass'
            message = '✅ 操作指引，无需核验'
        elif not is_consistent:
            status = 'fail'
            message = f'❌ 发现 {data_check["critical_issues"]} 个数据不一致'
        elif data_check.get('warnings', 0) > 0:
            status = 'warning'
            message = f'⚠️ 存在 {data_check["warnings"]} 个警告'
        elif has_key_content:
            status = 'pass'
            message = '✅ 数据一致'
        else:
            # 无关键数据的附件也标记为通过
            status = 'pass'
            message = '✅ 通过'
        
        return {
            'status': status,
            'message': message,
            'is_referenced': is_referenced,
            'is_consistent': is_consistent,
            'has_key_content': has_key_content,
            'is_operation_guide': is_operation_guide
        }
    
    def format_checklist_as_table(self, checklist: Dict[str, Any]) -> str:
        """将核查表格式化为Markdown表格（与三维度报告附件部分格式一致）"""
        
        lines = []
        lines.append("# 📎 附件核查表（详细版）\n")
        lines.append("> 本表是三维度核验报告中「附件逐项核验」的详细补充\n")
        
        # 统计信息
        total = checklist['total_attachments']
        pass_count = sum(1 for att in checklist['attachments'] if att['conclusion']['status'] == 'pass')
        warn_count = sum(1 for att in checklist['attachments'] if att['conclusion']['status'] == 'warning')
        fail_count = sum(1 for att in checklist['attachments'] if att['conclusion']['status'] == 'fail')
        
        lines.append(f"**附件总数**: {total} | ✅ 通过: {pass_count} | ⚠️ 警告: {warn_count} | ❌ 问题: {fail_count}\n")
        lines.append("---\n")
        
        # 附件逐项核验表（与三维度报告格式一致）
        lines.append("## 📊 附件逐项核验\n")
        lines.append("| 附件 | 文件名 | 类型 | 关键信息 | 核验说明 |")
        lines.append("|:----:|--------|:----:|---------|---------|")
        
        for att in checklist['attachments']:
            idx = att['index']
            filename = att['filename'][:30] + '...' if len(att['filename']) > 30 else att['filename']
            
            # 内容类型
            key_content = att.get('key_content', {})
            is_guide = key_content.get('is_operation_guide', False)
            content_type = key_content.get('content_type', '未分类')
            
            # 关键信息摘要 - 不截断，完整显示
            content_summary = key_content.get('content_summary', '')
            if not content_summary:
                # 从提取的数据生成摘要
                info_parts = []
                if key_content.get('phone_numbers', {}).get('found'):
                    phones = key_content['phone_numbers']['found']
                    info_parts.append(f"号码: {', '.join(phones[:2])}")
                if key_content.get('amounts', {}).get('found'):
                    amounts = key_content['amounts']['found']
                    info_parts.append(f"金额: {', '.join(amounts[:3])}")
                if key_content.get('dates', {}).get('found'):
                    dates = key_content['dates']['found']
                    info_parts.append(f"日期: {', '.join(dates[:2])}")
                content_summary = '; '.join(info_parts) if info_parts else '-'
            
            # 核验说明 - 不截断
            conclusion = att['conclusion']
            if is_guide:
                result = '✅ 操作指引，无需核验'
            elif conclusion['status'] == 'pass':
                result = '✅ 数据一致'
            elif conclusion['status'] == 'fail':
                result = '❌ ' + conclusion['message'].split('❌')[-1].strip()
            else:
                result = '⚠️ ' + conclusion['message'].split('⚠️')[-1].strip()
            
            lines.append(f"| 附件{idx} | {filename} | {content_type} | {content_summary} | {result} |")
        
        lines.append("")
        
        # 附件类型说明（与三维度报告一致）
        lines.append("**附件类型处理规则**：")
        lines.append("- **业务凭证**：需核验金额、日期、号码等与文本一致性")
        lines.append("- **记录查询**：需核验查询结果与文本描述一致性")
        lines.append("- **操作指引**：直接标记为 ✅ 通过，其中的金额等信息与本次申诉无关")
        lines.append("- **沟通记录**：需核验沟通内容与文本描述一致性\n")
        
        # 只显示有问题的附件详情（排除操作指引类附件）
        problem_attachments = [att for att in checklist['attachments'] 
                              if (att['conclusion']['status'] != 'pass' or att['consistency_check'].get('issues', []))
                              and not att.get('key_content', {}).get('is_operation_guide', False)]
        
        if problem_attachments:
            lines.append("---\n")
            lines.append("## ⚠️ 需关注的附件详情\n")
            
            for att in problem_attachments:
                lines.append(f"### 附件{att['index']}: {att['filename']}\n")
                
                # 内容类型和摘要
                key_content = att.get('key_content', {})
                content_type = key_content.get('content_type', '未分类')
                content_summary = key_content.get('content_summary', '')
                if content_summary:
                    lines.append(f"**类型**: {content_type} | **内容**: {content_summary[:50]}\n")
                
                # 提取的关键数据表
                lines.append("| 数据类型 | 附件中的数据 | 与文档对比 |")
                lines.append("|:--------:|-------------|:----------:|")
                
                # 手机号码
                phone = key_content.get('phone_numbers', {})
                if phone.get('found'):
                    phone_icon = self._get_status_icon(phone['match_status']['status'])
                    lines.append(f"| 手机号 | {', '.join(phone['found'][:3])} | {phone_icon} |")
                
                # 金额
                amount = key_content.get('amounts', {})
                if amount.get('found'):
                    amount_icon = self._get_status_icon(amount['match_status']['status'])
                    lines.append(f"| 金额 | {', '.join(amount['found'][:3])} | {amount_icon} |")
                
                # 日期
                date = key_content.get('dates', {})
                if date.get('found'):
                    date_icon = self._get_status_icon(date['match_status']['status'])
                    lines.append(f"| 日期 | {', '.join(date['found'][:3])} | {date_icon} |")
                
                lines.append("")
                
                # 问题列表
                if att['consistency_check'].get('issues'):
                    lines.append("**发现的问题**：")
                    for issue in att['consistency_check']['issues'][:3]:
                        severity_icon = '❌' if issue['severity'] == 'critical' else '⚠️'
                        lines.append(f"- {severity_icon} {issue['message']}")
                    lines.append("")
                
                # 结论
                lines.append(f"**核验结论**: {att['conclusion']['message']}\n")
        else:
            lines.append("---\n")
            lines.append("## ✅ 所有附件核验通过\n")
            lines.append("> 未发现数据不一致或其他问题\n")
        
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
