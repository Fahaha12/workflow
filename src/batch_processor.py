"""
批量案件审核处理器
读取Excel表格和案件文档，批量执行审核
"""
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class BatchCaseProcessor:
    """批量案件处理器"""
    
    def __init__(self, reviewer, doc_parser, vision_processor):
        """
        初始化批量处理器
        
        Args:
            reviewer: ComplaintReviewer实例
            doc_parser: 文档解析器
            vision_processor: 视觉处理器
        """
        self.reviewer = reviewer
        self.doc_parser = doc_parser
        self.vision_processor = vision_processor
    
    def process_batch(self, 
                     excel_path: str, 
                     docs_folder: str,
                     output_folder: str) -> Dict[str, Any]:
        """
        批量处理案件
        
        Args:
            excel_path: Excel表格路径
            docs_folder: 案件文档文件夹路径
            output_folder: 输出文件夹路径
            
        Returns:
            批量处理结果统计
        """
        logger.info("=" * 60)
        logger.info("开始批量案件审核")
        logger.info("=" * 60)
        
        # 读取Excel
        cases = self._load_cases_from_excel(excel_path)
        logger.info(f"共加载 {len(cases)} 个案件")
        
        # 创建输出目录
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        reports_path = output_path / 'reports'
        reports_path.mkdir(exist_ok=True)
        
        # 批量处理
        results = []
        stats = {
            'total': len(cases),
            'success': 0,
            'failed': 0,
            'matched': 0,  # AI判断与退回原因一致
            'mismatched': 0,  # AI判断与退回原因不一致
        }
        
        for idx, case in enumerate(cases, 1):
            logger.info(f"\n处理案件 {idx}/{len(cases)}: {case['流水号']}")
            
            try:
                # 查找对应文档和附件
                doc_files = self._find_case_files(case['流水号'], docs_folder)
                
                if not doc_files['main_doc']:
                    logger.warning(f"未找到案件文档: {case['流水号']}")
                    results.append({
                        **case,
                        'ai_result': '文档缺失',
                        'match_status': '无法审核'
                    })
                    stats['failed'] += 1
                    continue
                
                # 执行审核
                review_result = self._review_single_case(
                    case, 
                    doc_files,
                    reports_path
                )
                
                # 对比结果
                match_status = self._compare_results(
                    case['退回原因'],
                    review_result['issues']
                )
                
                results.append({
                    **case,
                    'ai_result': review_result['summary'],
                    'ai_issues': json.dumps(review_result['issues'], ensure_ascii=False),
                    'match_status': match_status,
                    'report_file': review_result['report_file']
                })
                
                stats['success'] += 1
                if match_status == '一致':
                    stats['matched'] += 1
                else:
                    stats['mismatched'] += 1
                    
            except Exception as e:
                logger.error(f"案件 {case['流水号']} 处理失败: {e}")
                results.append({
                    **case,
                    'ai_result': f'处理失败: {str(e)}',
                    'match_status': '错误'
                })
                stats['failed'] += 1
        
        # 保存结果
        self._save_results(results, stats, output_path)
        
        logger.info("=" * 60)
        logger.info("批量审核完成")
        logger.info(f"成功: {stats['success']}, 失败: {stats['failed']}")
        logger.info(f"匹配: {stats['matched']}, 不匹配: {stats['mismatched']}")
        logger.info("=" * 60)
        
        return stats
    
    def _load_cases_from_excel(self, excel_path: str) -> List[Dict[str, Any]]:
        """从Excel加载案件列表"""
        df = pd.read_excel(excel_path)
        
        # 标准化列名
        required_columns = ['申诉信息流水号', '申诉内容', '初判结果', '退回原因']
        
        cases = []
        for _, row in df.iterrows():
            case = {
                '流水号': row.get('申诉信息流水号', ''),
                '申诉日期': row.get('申诉日期', ''),
                '用户姓名': row.get('用户姓名', ''),
                '联系电话': row.get('联系电话', ''),
                '申诉涉及号码': row.get('申诉涉及号码', ''),
                '申诉内容': row.get('申诉内容', ''),
                '初判结果': row.get('初判结果', ''),
                '退回原因': row.get('退回原因', ''),
                '责任部门': row.get('责任部门', ''),
            }
            cases.append(case)
        
        return cases
    
    def _find_case_files(self, case_id: str, docs_folder: str) -> Dict[str, Any]:
        """查找案件对应的文档和附件"""
        docs_path = Path(docs_folder)
        
        # 查找主文档（包含流水号的Word文档）
        main_doc = None
        for doc_file in docs_path.glob('**/*.docx'):
            if case_id in doc_file.name:
                main_doc = doc_file
                break
        
        # 查找附件（同一文件夹下的图片和PDF）
        attachments = []
        if main_doc:
            doc_folder = main_doc.parent
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.pdf']:
                attachments.extend(doc_folder.glob(ext))
        
        return {
            'main_doc': main_doc,
            'attachments': attachments
        }
    
    def _review_single_case(self, 
                           case: Dict[str, Any],
                           doc_files: Dict[str, Any],
                           reports_path: Path) -> Dict[str, Any]:
        """审核单个案件"""
        # 解析文档
        from document_parser import DocumentParser
        parser = DocumentParser()
        parsed_doc = parser.parse_word_document(str(doc_files['main_doc']))
        
        # 处理附件
        ocr_results = []
        for attachment in doc_files['attachments']:
            result = self.vision_processor.process_file(str(attachment))
            ocr_results.append(result)
        
        # 执行审核
        review_result = self.reviewer.review_complaint_document(
            parsed_doc,
            ocr_results,
            [f.name for f in doc_files['attachments']]
        )
        
        # 保存报告
        report_file = reports_path / f"{case['流水号']}_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(review_result.get('three_dimension_report', ''))
        
        return {
            'summary': review_result.get('summary', {}),
            'issues': self._extract_issues(review_result),
            'report_file': str(report_file)
        }
    
    def _extract_issues(self, review_result: Dict[str, Any]) -> List[str]:
        """从审核结果中提取问题列表"""
        issues = []
        
        # 从三维度报告中提取问题
        report = review_result.get('three_dimension_report', '')
        
        # 简单提取：查找"错误"、"异常"、"不一致"等关键词的行
        for line in report.split('\n'):
            if any(kw in line for kw in ['错误', '异常', '不一致', '缺失', '问题']):
                issues.append(line.strip())
        
        return issues
    
    def _compare_results(self, 
                        expected_reason: str,
                        ai_issues: List[str]) -> str:
        """对比退回原因和AI发现的问题"""
        if not expected_reason or expected_reason.strip() == '':
            return '无参考标准'
        
        if not ai_issues:
            return '未发现问题'
        
        # 简单匹配：检查AI发现的问题是否包含退回原因中的关键词
        expected_keywords = self._extract_keywords(expected_reason)
        ai_text = ' '.join(ai_issues)
        
        matched_count = sum(1 for kw in expected_keywords if kw in ai_text)
        
        if matched_count >= len(expected_keywords) * 0.7:  # 70%匹配度
            return '一致'
        elif matched_count > 0:
            return '部分一致'
        else:
            return '不一致'
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单实现：分词并过滤
        keywords = []
        for word in text.split():
            if len(word) > 2 and word not in ['的', '了', '是', '在']:
                keywords.append(word)
        return keywords
    
    def _save_results(self, 
                     results: List[Dict[str, Any]],
                     stats: Dict[str, Any],
                     output_path: Path):
        """保存批量审核结果"""
        # 保存Excel
        df = pd.DataFrame(results)
        excel_file = output_path / f'batch_review_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        df.to_excel(excel_file, index=False)
        logger.info(f"结果已保存: {excel_file}")
        
        # 保存统计报告
        stats_file = output_path / 'statistics.json'
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # 生成汇总报告
        summary_file = output_path / 'summary_report.md'
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"# 批量审核汇总报告\n\n")
            f.write(f"## 统计信息\n\n")
            f.write(f"- 总案件数: {stats['total']}\n")
            f.write(f"- 成功审核: {stats['success']}\n")
            f.write(f"- 审核失败: {stats['failed']}\n")
            f.write(f"- 判断一致: {stats['matched']}\n")
            f.write(f"- 判断不一致: {stats['mismatched']}\n")
            f.write(f"- 准确率: {stats['matched']/stats['success']*100:.2f}%\n\n")
            
            f.write(f"## 不一致案件\n\n")
            for result in results:
                if result.get('match_status') == '不一致':
                    f.write(f"### {result['流水号']}\n")
                    f.write(f"- 退回原因: {result['退回原因']}\n")
                    f.write(f"- AI判断: {result['ai_result']}\n\n")
