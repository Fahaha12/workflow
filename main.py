"""
AI文档审核系统 - 主程序
"""
import argparse
import sys
from pathlib import Path
import logging

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import Config
from logger import setup_logger
from ocr_processor import OCRProcessor
from docx_parser import DocxParser
from ai_reviewer import AIReviewer

logger = logging.getLogger(__name__)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='AI文档审核系统 - 比对Word文档和附件内容',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 审核单个文档和附件目录
  python main.py --docx report.docx --attachments ./attachments/
  
  # 指定审核类型
  python main.py --docx report.docx --attachments ./attachments/ --review-type typo
  
  # 使用自定义配置文件
  python main.py --docx report.docx --attachments ./attachments/ --env custom.env
  
  # 仅进行OCR处理
  python main.py --ocr-only --attachments ./attachments/ --output ./output/
        """
    )
    
    # 输入参数
    parser.add_argument('--docx', type=str, help='Word文档路径')
    parser.add_argument('--attachments', type=str, help='附件目录路径')
    parser.add_argument('--attachment-file', type=str, action='append', 
                       help='单个附件文件路径（可多次使用）')
    
    # 处理模式
    parser.add_argument('--ocr-only', action='store_true', 
                       help='仅进行OCR处理，不进行AI审核')
    parser.add_argument('--parse-only', action='store_true',
                       help='仅解析Word文档，不进行AI审核')
    
    # 审核配置
    parser.add_argument('--review-type', type=str, 
                       choices=['comprehensive', 'typo', 'consistency'],
                       default='comprehensive',
                       help='审核类型：comprehensive(全面), typo(笔误), consistency(一致性)')
    
    # 输出配置
    parser.add_argument('--output', type=str, help='输出目录路径')
    parser.add_argument('--env', type=str, help='.env配置文件路径')
    
    # 日志配置
    parser.add_argument('--log-level', type=str, 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='日志级别')
    
    args = parser.parse_args()
    
    # 加载配置
    try:
        config = Config(env_file=args.env)
        
        # 设置日志
        log_level = args.log_level or config.log_level
        output_dir = Path(args.output or config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = output_dir / 'review.log'
        setup_logger(log_level, str(log_file))
        
        logger.info("AI文档审核系统启动")
        logger.debug(f"配置: {config}")
        
        # 验证配置
        if not args.ocr_only and not args.parse_only:
            if not config.validate():
                logger.error("配置验证失败，请检查.env文件")
                return 1
        
    except Exception as e:
        print(f"配置加载失败: {str(e)}")
        return 1
    
    # 执行处理流程
    try:
        # 1. OCR处理附件
        ocr_results = []
        if args.attachments or args.attachment_file:
            logger.info("[1/3] OCR处理附件...")
            
            ocr_processor = OCRProcessor(tesseract_path=config.tesseract_path)
            
            # 处理附件目录
            if args.attachments:
                attachments_dir = Path(args.attachments)
                if not attachments_dir.exists():
                    logger.error(f"附件目录不存在: {attachments_dir}")
                    return 1
                
                ocr_results = ocr_processor.process_directory(
                    str(attachments_dir),
                    output_dir=str(output_dir)
                )
            
            # 处理单个附件文件
            if args.attachment_file:
                for file_path in args.attachment_file:
                    result = ocr_processor.process_file(file_path)
                    ocr_results.append(result)
            
            logger.info(f"OCR处理完成，共处理 {len(ocr_results)} 个文件")
            
            if args.ocr_only:
                logger.info(f"OCR结果已保存到: {output_dir}")
                return 0
        
        # 2. 解析Word文档
        doc_result = None
        if args.docx:
            logger.info("[2/3] 解析Word文档...")
            
            docx_path = Path(args.docx)
            if not docx_path.exists():
                logger.error(f"Word文档不存在: {docx_path}")
                return 1
            
            parser = DocxParser()
            doc_result = parser.parse_document(str(docx_path))
            
            # 保存解析结果
            parser.save_result(doc_result, str(output_dir / 'document_parsed.json'))
            
            logger.info(f"文档解析完成: {doc_result['file_name']}")
            
            if args.parse_only:
                logger.info(f"解析结果已保存到: {output_dir}")
                return 0
        
        # 3. AI审核
        if doc_result and ocr_results:
            logger.info("[3/3] AI审核比对...")
            
            ai_config = config.get_ai_config()
            reviewer = AIReviewer(**ai_config)
            
            # 执行审核
            review_result = reviewer.batch_review(
                doc_result,
                ocr_results,
                review_types=[args.review_type]
            )
            
            # 生成报告
            report_path = output_dir / 'review_report'
            reviewer.generate_report(review_result, str(report_path))
            
            summary = review_result['summary']
            logger.info(f"审核完成! 问题: {summary['total_issues']} (高:{summary['high_severity']} 中:{summary['medium_severity']} 低:{summary['low_severity']})")
            logger.info(f"报告: {report_path}.json / .md")
        
        elif not doc_result and not args.ocr_only:
            logger.error("未指定Word文档，请使用 --docx 参数")
            return 1
        
        elif not ocr_results and not args.parse_only:
            logger.error("未指定附件，请使用 --attachments 或 --attachment-file 参数")
            return 1
        
        return 0
    
    except Exception as e:
        logger.error(f"处理过程中出错: {str(e)}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
