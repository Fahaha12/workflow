"""
申诉文档专用审核器
文本+图片+PDF
"""
import re
import json
from typing import Dict, List, Any
import logging
from attachment_analyzer import AttachmentAnalyzer
from three_dimension_validator import ThreeDimensionValidator, ImageInfoExtractor, PDFInfoExtractor

logger = logging.getLogger(__name__)


class ComplaintReviewer:
    """申诉文档审核器"""
    
    def __init__(self, ai_client=None, model=None):
        """
        初始化审核器
        
        Args:
            ai_client: AI客户端
            model: AI模型名称
        """
        self.ai_client = ai_client
        self.model = model
        self.attachment_analyzer = AttachmentAnalyzer()
        
        # 初始化三维度核验器
        if ai_client:
            self.validator = ThreeDimensionValidator(ai_client, model)
            self.image_extractor = ImageInfoExtractor(ai_client)
            self.pdf_extractor = PDFInfoExtractor()
        else:
            self.validator = None
            self.image_extractor = None
            self.pdf_extractor = None
    
    def review_complaint_document(self, 
                                  parsed_doc: Dict[str, Any],
                                  ocr_results: List[Dict[str, Any]],
                                  uploaded_files: List[str]) -> Dict[str, Any]:
        """
        审核申诉文档（三维度全核验流程）
        
        流程：
        1. 构建三个输入变量：input（报告文本）、picinput（图片信息）、pdfinput（PDF信息）
        2. 调用三维度核验器执行9项校验
        3. 生成Markdown格式核验报告
        
        Args:
            parsed_doc: 解析后的文档结构
            ocr_results: 视觉模型识别结果列表
            uploaded_files: 上传的附件文件名列表
            
        Returns:
            审核结果
        """
        logger.info("=" * 60)
        logger.info("开始三维度全核验（文本+图片+PDF）")
        logger.info("=" * 60)
        
        sections = parsed_doc['sections']
        
        results = {
            'document': parsed_doc.get('file_name', '未知文档'),
            'three_dimension_report': '',
            'extracted_info': {},
            'summary': {
                'total_issues': 0,
                'critical_issues': 0,
                'warnings': 0
            }
        }
        
        # ========== 第一步：构建三个输入变量 ==========
        logger.info("第一步：构建三个输入变量...")
        
        # 1.1 构建 {{input}} - 报告文本
        input_text = self._build_input_text(parsed_doc, sections)
        results['extracted_info']['input_text'] = input_text[:500] + "..."  # 保存预览
        logger.info(f"✓ input变量构建完成，长度: {len(input_text)} 字符")
        
        # 1.2 构建 {{picinput}} - 图片信息JSON
        if self.image_extractor:
            pic_input = self.image_extractor.extract_from_vision_results(ocr_results)
        else:
            pic_input = self._build_pic_input_basic(ocr_results)
        results['extracted_info']['pic_input'] = pic_input
        logger.info(f"✓ picinput变量构建完成，包含 {len(pic_input.get('图片信息提取结果', []))} 个附件")
        
        # 1.3 构建 {{pdfinput}} - PDF信息JSON
        if self.pdf_extractor:
            pdf_input = self.pdf_extractor.extract_from_vision_results(ocr_results)
        else:
            pdf_input = self._build_pdf_input_basic(ocr_results)
        results['extracted_info']['pdf_input'] = pdf_input
        logger.info(f"✓ pdfinput变量构建完成，包含 {pdf_input.get('整体状态', {}).get('总数', 0)} 个PDF")
        
        # ========== 第二步：执行三维度核验 ==========
        logger.info("第二步：执行三维度交叉核验...")
        
        if self.validator:
            validation_result = self.validator.validate(input_text, pic_input, pdf_input)
            
            if validation_result.get('success'):
                results['three_dimension_report'] = validation_result['markdown_report']
                logger.info("✓ 三维度核验完成")
            else:
                results['three_dimension_report'] = validation_result.get('markdown_report', '')
                results['error'] = validation_result.get('error', '核验失败')
                logger.error(f"三维度核验失败: {validation_result.get('error')}")
        else:
            # 降级到基础检测
            logger.warning("AI客户端不可用，使用基础检测")
            results['three_dimension_report'] = self._generate_basic_report(
                input_text, pic_input, pdf_input, sections, ocr_results
            )
        
        # ========== 第三步：生成附件核查表 ==========
        logger.info("第三步：生成附件核查表...")
        
        # 3.1 格式化附件列表
        results['attachment_list'] = self._format_attachment_list(
            sections['section4_attachments'],
            ocr_results,
            uploaded_files
        )
        
        # 3.2 生成附件关键内容核查表
        results['attachment_checklist'] = self.attachment_analyzer.generate_attachment_checklist(
            ocr_results,
            sections['section2_investigation'],
            sections['section3_handling']
        )
        
        # 3.3 生成Markdown格式核查表
        results['attachment_checklist_markdown'] = self.attachment_analyzer.format_checklist_as_table(
            results['attachment_checklist']
        )
        
        logger.info(f"✓ 已生成 {len(ocr_results)} 个附件的核查表")
        
        # ========== 统计问题数量 ==========
        # 从三维度报告中提取问题统计（简单解析）
        report = results['three_dimension_report']
        results['summary']['total_issues'] = report.count('❌') + report.count('冲突')
        results['summary']['critical_issues'] = report.count('❌')
        results['summary']['warnings'] = report.count('⚠️')
        
        logger.info("=" * 60)
        logger.info(f"三维度全核验完成！发现 {results['summary']['total_issues']} 个问题")
        logger.info("=" * 60)
        
        return results
    
    def _build_input_text(self, parsed_doc: Dict[str, Any], sections: Dict[str, Any]) -> str:
        """构建 {{input}} 报告文本变量"""
        
        parts = []
        
        # 标题
        title = parsed_doc.get('title', sections.get('title', {}).get('content', ''))
        if title:
            parts.append(f"### 标题\n{title}")
        
        # 编号
        doc_number = parsed_doc.get('document_number', sections.get('document_number', {}).get('content', ''))
        if doc_number:
            parts.append(f"### 编号\n{doc_number}")
        
        # 第一段：用户申诉原文
        section1 = sections.get('section1_original_complaint', {})
        section1_content = section1.get('content', '')
        if section1_content:
            parts.append(f"### 第一段（用户申诉原文）\n{section1_content}")
        
        # 第二段：申诉核查情况
        section2 = sections.get('section2_investigation', {})
        section2_content = section2.get('content', '')
        if section2_content:
            parts.append(f"### 第二段（申诉核查情况）\n{section2_content}")
        
        # 第三段：申诉后处理情况
        section3 = sections.get('section3_handling', {})
        section3_content = section3.get('content', '')
        if section3_content:
            parts.append(f"### 第三段（申诉后处理情况）\n{section3_content}")
        
        # 第四段：涉及的证明材料
        section4 = sections.get('section4_attachments', {})
        section4_content = section4.get('content', '')
        if section4_content:
            parts.append(f"### 第四段（涉及的证明材料）\n{section4_content}")
        
        return "\n\n".join(parts)
    
    def _build_pic_input_basic(self, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """基础方法：构建picinput（当AI不可用时）"""
        
        pic_input = {
            "图片信息提取结果": [],
            "整体状态": {
                "可识别图片": 0,
                "模糊图片": 0,
                "无核心信息图片": 0,
                "总数": len(ocr_results)
            }
        }
        
        for idx, result in enumerate(ocr_results, 1):
            filename = result.get('file_name', f'附件{idx}')
            content = result.get('content', '')
            file_type = result.get('file_type', '')
            
            # 跳过PDF
            if file_type.lower() == '.pdf':
                continue
            
            # 提取关键信息
            phone_numbers = list(set(re.findall(r'1[3-9]\d{9}', content)))
            amounts = list(set(re.findall(r'\d+\.?\d*元', content)))
            dates = list(set(re.findall(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}[日号]?', content)))
            
            # 判断状态
            if result.get('error') or len(content.strip()) < 10:
                status = "模糊/无法识别"
                pic_input["整体状态"]["模糊图片"] += 1
            elif not phone_numbers and not amounts:
                status = "无核心业务信息"
                pic_input["整体状态"]["无核心信息图片"] += 1
            else:
                status = "可识别"
                pic_input["整体状态"]["可识别图片"] += 1
            
            pic_input["图片信息提取结果"].append({
                "图片变量名": f"file{idx}",
                "对应附件": f"附件{idx}",
                "文件名": filename,
                "图片状态": status,
                "提取的关键信息": {
                    "号码类": {"所有号码": phone_numbers},
                    "数字类": {"金额": amounts, "日期": dates}
                }
            })
        
        return pic_input
    
    def _build_pdf_input_basic(self, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """基础方法：构建pdfinput（当AI不可用时）"""
        
        pdf_input = {
            "PDF信息提取结果": [],
            "整体状态": {
                "可识别PDF": 0,
                "部分模糊PDF": 0,
                "无核心信息PDF": 0,
                "总数": 0
            }
        }
        
        for idx, result in enumerate(ocr_results, 1):
            file_type = result.get('file_type', '')
            
            # 只处理PDF
            if file_type.lower() != '.pdf':
                continue
            
            pdf_input["整体状态"]["总数"] += 1
            
            filename = result.get('file_name', f'PDF附件')
            content = result.get('content', '')
            
            # 提取关键信息
            phone_numbers = list(set(re.findall(r'1[3-9]\d{9}', content)))
            amounts = list(set(re.findall(r'\d+\.?\d*元', content)))
            
            # 判断状态
            if result.get('error') or len(content.strip()) < 10:
                status = "部分模糊/无法识别"
                pdf_input["整体状态"]["部分模糊PDF"] += 1
            elif not phone_numbers and not amounts:
                status = "无核心业务信息"
                pdf_input["整体状态"]["无核心信息PDF"] += 1
            else:
                status = "可识别"
                pdf_input["整体状态"]["可识别PDF"] += 1
            
            pdf_input["PDF信息提取结果"].append({
                "PDF变量名": f"pdf{pdf_input['整体状态']['总数']}",
                "文件名": filename,
                "PDF状态": status,
                "提取的关键信息": {
                    "号码类": {"所有号码": phone_numbers},
                    "数字类": {"金额": amounts}
                }
            })
        
        return pdf_input
    
    def _generate_basic_report(self, 
                               input_text: str,
                               pic_input: Dict,
                               pdf_input: Dict,
                               sections: Dict,
                               ocr_results: List) -> str:
        """生成基础报告（当AI不可用时）"""
        
        report_lines = [
            "# 定则报告核验结果（文本+图片+PDF三维度）",
            "",
            "## ⚠️ 注意：AI核验不可用，使用基础检测",
            "",
            "## 一、三变量基础信息",
            "",
            "### 图片+PDF整体状态",
            f"- 可识别图片：{pic_input['整体状态']['可识别图片']}张",
            f"- 模糊图片：{pic_input['整体状态']['模糊图片']}张",
            f"- 无核心信息图片：{pic_input['整体状态']['无核心信息图片']}张",
            f"- PDF总数：{pdf_input['整体状态']['总数']}个",
            "",
            "## 二、附件列表",
            "",
            "| 附件 | 文件名 | 状态 | 提取的号码 |",
            "|------|--------|------|-----------|",
        ]
        
        for pic in pic_input.get("图片信息提取结果", []):
            numbers = pic.get("提取的关键信息", {}).get("号码类", {}).get("所有号码", [])
            numbers_str = ", ".join(numbers) if numbers else "无"
            report_lines.append(
                f"| {pic['对应附件']} | {pic['文件名']} | {pic['图片状态']} | {numbers_str} |"
            )
        
        report_lines.extend([
            "",
            "## 三、核验结论",
            "",
            "请使用AI核验获取完整的三维度交叉核验结果。",
            ""
        ])
        
        return "\n".join(report_lines)
    
    def _extract_section1_basic(self, section1: Dict[str, Any]) -> Dict[str, Any]:
        """基础方法：提取第一部分信息"""
        return {
            'core_business_number': '',
            'contact_numbers': [],
            'complaint_content': section1.get('content', '')[:200],
            'user_demands': section1.get('demands', []),
            'key_amounts': [],
            'key_dates': [],
            'special_terms': []
        }
    
    def _extract_attachments_basic(self, ocr_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基础方法：提取附件信息"""
        attachments = []
        for idx, ocr in enumerate(ocr_results, 1):
            content = ocr.get('content', '')
            attachments.append({
                'attachment_index': idx,
                'filename': ocr.get('file_name', f'附件{idx}'),
                'file_type': ocr.get('file_type', ''),
                'status': '已提取' if content else '无内容',
                'extracted_info': {
                    'business_numbers': list(set(re.findall(r'\b\d{10,15}\b', content))),
                    'contact_numbers': list(set(re.findall(r'1[3-9]\d{9}', content))),
                    'amounts': list(set(re.findall(r'¥?\s*\d+\.?\d*\s*元', content))),
                    'dates': list(set(re.findall(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?', content))),
                    'times': list(set(re.findall(r'\d{1,2}:\d{2}(?::\d{2})?', content))),
                    'special_terms': [],
                    'content_type': '未知',
                    'clarity': '可识别' if content else '无内容'
                }
            })
        return attachments
    
    def _basic_validation(self, sections: Dict, ocr_results: List, uploaded_files: List) -> Dict[str, Any]:
        """基础验证方法（当AI不可用时）"""
        issues = []
        
        # 简单的附件对应检查
        section4_attachments = sections['section4_attachments'].get('attachments', [])
        
        for att in section4_attachments:
            att_num = att.get('number', '')
            found = any(att_num in f for f in uploaded_files)
            
            if not found:
                issues.append({
                    'severity': 'critical',
                    'type': 'attachment_not_uploaded',
                    'description': f'附件{att_num}未上传',
                    'suggestion': '请上传对应附件'
                })
        
        return {
            'validation_results': issues,
            'summary': {
                'total_issues': len(issues),
                'critical_issues': len([i for i in issues if i['severity'] == 'critical']),
                'warnings': len([i for i in issues if i['severity'] == 'warning'])
            }
        }
    
    def _format_attachment_list(self, 
                                section4: Dict[str, Any],
                                ocr_results: List[Dict[str, Any]],
                                uploaded_files: List[str]) -> List[Dict[str, Any]]:
        """
        格式化附件列表，修复附件名称显示问题
        
        Returns:
            格式化后的附件列表
        """
        logger.info("格式化附件列表...")
        
        formatted_list = []
        
        # 从第四部分获取附件列表
        listed_attachments = section4.get('attachments', [])
        
        for att in listed_attachments:
            att_num = att.get('number', '')
            att_name = att.get('name', '')
            att_full_text = att.get('full_text', '')
            
            # 查找对应的上传文件
            matched_file = None
            for uploaded in uploaded_files:
                if att_num in uploaded or att_name in uploaded:
                    matched_file = uploaded
                    break
            
            # 查找对应的OCR结果
            matched_ocr = None
            for ocr in ocr_results:
                ocr_filename = ocr.get('file_name', '')
                if att_num in ocr_filename or att_name in ocr_filename:
                    matched_ocr = ocr
                    break
            
            formatted_list.append({
                'number': att_num,
                'name': att_name,
                'full_text': att_full_text,
                'uploaded_file': matched_file,
                'has_ocr': matched_ocr is not None,
                'file_type': matched_ocr.get('file_type', '') if matched_ocr else '',
                'status': '✅ 已上传' if matched_file else '❌ 未上传'
            })
        
        # 检查是否有上传但未列出的文件
        for uploaded in uploaded_files:
            found = any(att['uploaded_file'] == uploaded for att in formatted_list)
            if not found:
                formatted_list.append({
                    'number': '未知',
                    'name': uploaded,
                    'full_text': f'未列出的附件: {uploaded}',
                    'uploaded_file': uploaded,
                    'has_ocr': True,
                    'file_type': uploaded.split('.')[-1] if '.' in uploaded else '',
                    'status': '⚠️ 已上传但未在列表中'
                })
        
        logger.info(f"附件列表格式化完成，共 {len(formatted_list)} 项")
        
        return formatted_list
