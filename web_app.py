"""
Web界面 - AI文档审核系统
"""
import os
import sys
import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename
import logging
from io import BytesIO

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import Config
from logger import setup_logger
from ocr_processor import OCRProcessor
from vision_processor import VisionProcessor
from pdf_text_extractor import PDFTextExtractor
from pdf_generator import MarkdownPDFGenerator
from docx_parser import DocxParser
from ai_reviewer import AIReviewer
from complaint_parser import ComplaintDocumentParser
from complaint_reviewer_new import ComplaintReviewer

# 获取当前目录
BASE_DIR = Path(__file__).parent

# 创建Flask应用，指定模板和静态文件目录
app = Flask(__name__, 
            template_folder=str(BASE_DIR / 'templates'),
            static_folder=str(BASE_DIR / 'static'))
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB限制
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

# 创建必要的目录
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
Path(app.config['OUTPUT_FOLDER']).mkdir(parents=True, exist_ok=True)

# 配置日志
setup_logger('INFO', 'output/web_app.log')
logger = logging.getLogger(__name__)

# 加载配置
config = Config()

# 允许的文件扩展名
ALLOWED_DOCX = {'docx', 'doc'}
ALLOWED_ATTACHMENTS = {'pdf', 'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'gif'}


def allowed_file(filename, allowed_extensions):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置信息"""
    try:
        ai_config = config.get_ai_config()
        return jsonify({
            'success': True,
            'config': {
                'ai_type': ai_config['api_type'],
                'ai_model': ai_config['model'],
                'has_api_key': bool(ai_config['api_key'])
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/upload', methods=['POST'])
def upload_files():
    """上传文件"""
    try:
        # 检查是否有文件
        if 'docx' not in request.files:
            return jsonify({'success': False, 'error': '未上传Word文档'})
        
        docx_file = request.files['docx']
        if docx_file.filename == '':
            return jsonify({'success': False, 'error': 'Word文档名称为空'})
        
        if not allowed_file(docx_file.filename, ALLOWED_DOCX):
            return jsonify({'success': False, 'error': 'Word文档格式不支持'})
        
        # 保存Word文档
        docx_filename = secure_filename(docx_file.filename)
        docx_path = Path(app.config['UPLOAD_FOLDER']) / docx_filename
        docx_file.save(str(docx_path))
        
        # 保存附件
        attachment_files = request.files.getlist('attachments')
        attachment_paths = []
        
        for file in attachment_files:
            if file and file.filename and allowed_file(file.filename, ALLOWED_ATTACHMENTS):
                filename = secure_filename(file.filename)
                filepath = Path(app.config['UPLOAD_FOLDER']) / filename
                file.save(str(filepath))
                attachment_paths.append(str(filepath))
        
        return jsonify({
            'success': True,
            'docx_path': str(docx_path),
            'attachment_paths': attachment_paths,
            'attachment_count': len(attachment_paths)
        })
    
    except Exception as e:
        logger.error(f"上传文件失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/review', methods=['POST'])
def review_document():
    """执行文档审核"""
    try:
        data = request.json
        docx_path = data.get('docx_path')
        attachment_paths = data.get('attachment_paths', [])
        review_type = data.get('review_type', 'comprehensive')
        
        if not docx_path or not Path(docx_path).exists():
            return jsonify({'success': False, 'error': 'Word文档不存在'})
        
        # 获取AI配置
        ai_config = config.get_ai_config()
        
        # 1. 使用视觉大模型处理附件（跳过OCR）
        logger.info(f"[1/3] 视觉识别 {len(attachment_paths)} 个附件...")
        vision_processor = VisionProcessor(
            api_key=ai_config.get('api_key'),
            model="qwen3-vl-plus"
        )
        ocr_results = []
        
        for i, att_path in enumerate(attachment_paths):
            if Path(att_path).exists():
                result = vision_processor.process_file(att_path)
                ocr_results.append(result)
                yield f"data: {json.dumps({'type': 'progress', 'step': 'vision', 'current': i+1, 'total': len(attachment_paths), 'message': f'视觉识别: {Path(att_path).name}'}, ensure_ascii=False)}\n\n"
        
        # 2. 解析Word文档
        logger.debug("解析Word文档...")
        yield f"data: {json.dumps({'type': 'progress', 'step': 'parse', 'message': '解析Word文档'}, ensure_ascii=False)}\n\n"
        
        parser = DocxParser()
        doc_result = parser.parse_document(docx_path)
        
        # 3. AI审核
        logger.debug("AI审核...")
        yield f"data: {json.dumps({'type': 'progress', 'step': 'review', 'message': 'AI审核中...'}, ensure_ascii=False)}\n\n"
        reviewer = AIReviewer(**ai_config)
        
        review_result = reviewer.batch_review(
            doc_result,
            ocr_results,
            review_types=[review_type]
        )
        
        # 4. 生成报告
        output_path = Path(app.config['OUTPUT_FOLDER']) / 'review_report'
        reviewer.generate_report(review_result, str(output_path))
        
        # 返回结果
        yield f"data: {json.dumps({'type': 'complete', 'result': review_result}, ensure_ascii=False)}\n\n"
    
    except Exception as e:
        logger.error(f"审核失败: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"


@app.route('/api/review-sync', methods=['POST'])
def review_document_sync():
    """执行文档审核（同步版本）"""
    try:
        data = request.json
        docx_path = data.get('docx_path')
        attachment_paths = data.get('attachment_paths', [])
        review_type = data.get('review_type', 'comprehensive')
        
        if not docx_path or not Path(docx_path).exists():
            return jsonify({'success': False, 'error': 'Word文档不存在'})
        
        # 获取AI配置
        ai_config = config.get_ai_config()
        
        # 1. 处理附件（PDF用文本提取，图片用视觉识别）
        logger.info(f"[1/3] 处理 {len(attachment_paths)} 个附件...")
        vision_processor = VisionProcessor(
            api_key=ai_config.get('api_key'),
            model="qwen3-vl-plus"
        )
        pdf_extractor = PDFTextExtractor()
        ocr_results = []
        
        for att_path in attachment_paths:
            if not Path(att_path).exists():
                continue
            
            file_ext = Path(att_path).suffix.lower()
            
            if file_ext == '.pdf':
                # PDF直接提取文本
                logger.debug(f"PDF提取: {Path(att_path).name}")
                result = pdf_extractor.extract_from_pdf(att_path)
                ocr_results.append(result)
            else:
                # 图片使用视觉识别
                logger.debug(f"视觉识别: {Path(att_path).name}")
                result = vision_processor.process_file(att_path)
                ocr_results.append(result)
        
        # 2. 解析Word文档
        logger.info("[2/3] 解析Word文档...")
        parser = DocxParser()
        doc_result = parser.parse_document(docx_path)
        
        # 3. AI审核
        logger.info("[3/3] AI审核...")
        
        # 判断审核类型
        if review_type == 'complaint':
            # 申诉文档专用审核
            logger.debug("使用申诉文档专用审核流程")
            complaint_parser = ComplaintDocumentParser()
            parsed_doc = complaint_parser.parse_document(doc_result)
            
            # 创建审核器（传入AI客户端）
            from openai import OpenAI
            ai_client = OpenAI(
                api_key=ai_config.get('api_key'),
                base_url=ai_config.get('base_url')
            )
            complaint_reviewer = ComplaintReviewer(
                ai_client=ai_client,
                model=ai_config.get('model')
            )
            
            # 获取上传的文件名列表
            uploaded_files = [Path(p).name for p in attachment_paths]
            
            # 执行审核
            review_result = complaint_reviewer.review_complaint_document(
                parsed_doc,
                ocr_results,
                uploaded_files
            )
        else:
            # 通用审核
            reviewer = AIReviewer(**ai_config)
            review_result = reviewer.batch_review(
                doc_result,
                ocr_results,
                review_types=[review_type]
            )
        
        # 4. 生成报告
        output_path = Path(app.config['OUTPUT_FOLDER']) / 'review_report'
        
        # 保存JSON报告
        json_path = str(output_path) + '.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(review_result, f, ensure_ascii=False, indent=2)
        
        # 保存Markdown报告
        md_path = str(output_path) + '.md'
        if review_type == 'complaint':
            # 申诉文档报告 - 三维度全核验
            with open(md_path, 'w', encoding='utf-8') as f:
                # 写入三维度核验报告（主报告）
                if 'three_dimension_report' in review_result and review_result['three_dimension_report']:
                    f.write(review_result['three_dimension_report'])
                    f.write("\n\n---\n\n")
                else:
                    # 兼容旧格式
                    f.write("# 申诉文档审核报告\n\n")
                    f.write(f"**文档**: {review_result.get('document', 'Unknown')}\n\n")
                    f.write(f"**总问题数**: {review_result['summary']['total_issues']}\n")
                    f.write(f"**严重问题**: {review_result['summary']['critical_issues']}\n")
                    f.write(f"**警告**: {review_result['summary']['warnings']}\n\n")
                    f.write("---\n\n")
                
                # 附件名称对比表
                if 'attachment_name_comparison' in review_result:
                    f.write(review_result['attachment_name_comparison'])
                    f.write("\n\n---\n\n")
                
                # 附件核查表
                if 'attachment_checklist_markdown' in review_result:
                    f.write(review_result['attachment_checklist_markdown'])
        else:
            # 通用报告
            if 'reviewer' in locals():
                reviewer.generate_report(review_result, str(output_path))
        
        return jsonify({
            'success': True,
            'result': review_result,
            'report_json': json_path,
            'report_md': md_path
        })
    
    except Exception as e:
        logger.error(f"审核失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/download/<filename>')
def download_file(filename):
    """下载报告文件"""
    try:
        file_path = Path(app.config['OUTPUT_FOLDER']) / filename
        if file_path.exists():
            return send_file(str(file_path), as_attachment=True)
        else:
            return jsonify({'success': False, 'error': '文件不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/download-pdf')
def download_pdf():
    """下载PDF报告 - 使用reportlab直接生成，完美支持中文"""
    try:
        # 读取Markdown文件
        md_path = Path(app.config['OUTPUT_FOLDER']) / 'review_report.md'
        if not md_path.exists():
            return jsonify({'success': False, 'error': 'Markdown报告不存在'})
        
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        pdf_path = Path(app.config['OUTPUT_FOLDER']) / 'review_report.pdf'
        
        # 使用reportlab直接生成PDF
        try:
            pdf_gen = MarkdownPDFGenerator()
            success = pdf_gen.markdown_to_pdf(md_content, str(pdf_path))
            
            if success and pdf_path.exists():
                logger.info(f"PDF报告已生成(reportlab): {pdf_path}")
                return send_file(str(pdf_path), as_attachment=True, download_name='review_report.pdf')
            else:
                logger.warning("PDF生成失败，返回Markdown文件")
                return send_file(str(md_path), as_attachment=True, download_name='review_report.md')
                
        except ImportError as e:
            logger.warning(f"reportlab不可用: {e}，返回Markdown文件")
            return send_file(str(md_path), as_attachment=True, download_name='review_report.md')
        except Exception as e:
            logger.error(f"PDF生成失败: {e}，返回Markdown文件")
            import traceback
            logger.error(traceback.format_exc())
            return send_file(str(md_path), as_attachment=True, download_name='review_report.md')
            
    except Exception as e:
        logger.error(f"PDF下载失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/clear', methods=['POST'])
def clear_files():
    """清理上传的文件"""
    try:
        # 清理上传目录
        upload_dir = Path(app.config['UPLOAD_FOLDER'])
        for file in upload_dir.glob('*'):
            if file.is_file():
                file.unlink()
        
        return jsonify({'success': True, 'message': '文件已清理'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    print("AI文档审核系统 - Web界面")
    print(f"访问地址: http://localhost:5002")
    app.run(host='0.0.0.0', port=5002, debug=True)
