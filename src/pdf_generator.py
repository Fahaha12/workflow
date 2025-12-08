"""
PDF报告生成器 - 使用reportlab直接生成PDF，完美支持中文
"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)


class MarkdownPDFGenerator:
    """Markdown转PDF生成器"""
    
    def __init__(self):
        """初始化生成器"""
        self.register_fonts()
        self.styles = self.create_styles()
    
    def register_fonts(self):
        """注册中文字体"""
        try:
            # Windows系统字体路径
            font_paths = [
                r'C:\Windows\Fonts\msyh.ttc',  # 微软雅黑
                r'C:\Windows\Fonts\simhei.ttf',  # 黑体
                r'C:\Windows\Fonts\simsun.ttc',  # 宋体
            ]
            
            for font_path in font_paths:
                if Path(font_path).exists():
                    try:
                        pdfmetrics.registerFont(TTFont('Chinese', font_path))
                        logger.info(f"已注册中文字体: {font_path}")
                        return
                    except:
                        continue
            
            logger.warning("未找到中文字体，使用默认字体")
            
        except Exception as e:
            logger.error(f"字体注册失败: {e}")
    
    def create_styles(self):
        """创建样式"""
        styles = getSampleStyleSheet()
        
        # 标题1
        styles.add(ParagraphStyle(
            name='CustomHeading1',
            parent=styles['Heading1'],
            fontName='Chinese',
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            spaceBefore=12,
        ))
        
        # 标题2
        styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=styles['Heading2'],
            fontName='Chinese',
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            spaceAfter=10,
            spaceBefore=10,
        ))
        
        # 标题3
        styles.add(ParagraphStyle(
            name='CustomHeading3',
            parent=styles['Heading3'],
            fontName='Chinese',
            fontSize=12,
            textColor=colors.HexColor('#555555'),
            spaceAfter=8,
            spaceBefore=8,
        ))
        
        # 正文
        styles.add(ParagraphStyle(
            name='CustomBody',
            parent=styles['BodyText'],
            fontName='Chinese',
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            spaceAfter=6,
            leading=14,
        ))
        
        # 列表项
        styles.add(ParagraphStyle(
            name='CustomBullet',
            parent=styles['BodyText'],
            fontName='Chinese',
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            leftIndent=20,
            spaceAfter=4,
        ))
        
        return styles
    
    def markdown_to_pdf(self, markdown_text: str, output_path: str):
        """
        将Markdown文本转换为PDF
        
        Args:
            markdown_text: Markdown格式文本
            output_path: 输出PDF路径
        """
        try:
            # 创建PDF文档（横向A4）
            doc = SimpleDocTemplate(
                output_path,
                pagesize=landscape(A4),
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm,
            )
            
            # 解析Markdown并生成内容
            story = []
            lines = markdown_text.split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                if not line:
                    i += 1
                    continue
                
                # 标题1
                if line.startswith('# '):
                    text = line[2:].strip()
                    story.append(Paragraph(text, self.styles['CustomHeading1']))
                    story.append(Spacer(1, 0.3*cm))
                
                # 标题2
                elif line.startswith('## '):
                    text = line[3:].strip()
                    story.append(Paragraph(text, self.styles['CustomHeading2']))
                    story.append(Spacer(1, 0.2*cm))
                
                # 标题3
                elif line.startswith('### '):
                    text = line[4:].strip()
                    story.append(Paragraph(text, self.styles['CustomHeading3']))
                    story.append(Spacer(1, 0.2*cm))
                
                # 分隔线
                elif line.startswith('---') or line.startswith('***'):
                    story.append(Spacer(1, 0.3*cm))
                
                # 表格
                elif line.startswith('|'):
                    table_lines = [line]
                    i += 1
                    while i < len(lines) and lines[i].strip().startswith('|'):
                        table_lines.append(lines[i].strip())
                        i += 1
                    i -= 1
                    
                    table = self.parse_table(table_lines)
                    if table:
                        story.append(table)
                        story.append(Spacer(1, 0.3*cm))
                
                # 列表项
                elif line.startswith('- ') or line.startswith('* '):
                    text = line[2:].strip()
                    # 处理加粗
                    text = self.process_inline_formatting(text)
                    story.append(Paragraph(f'• {text}', self.styles['CustomBullet']))
                
                # 普通段落
                else:
                    text = self.process_inline_formatting(line)
                    story.append(Paragraph(text, self.styles['CustomBody']))
                    story.append(Spacer(1, 0.1*cm))
                
                i += 1
            
            # 生成PDF
            doc.build(story)
            logger.info(f"PDF生成成功: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"PDF生成失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def process_inline_formatting(self, text: str) -> str:
        """处理行内格式（加粗、斜体等）"""
        # 加粗 **text** 或 __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
        
        # 斜体 *text* 或 _text_
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
        
        # 代码 `code`
        text = re.sub(r'`(.+?)`', r'<font name="Courier">\1</font>', text)
        
        # 转义特殊字符
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        # 恢复已处理的标签
        text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
        text = text.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
        text = text.replace('&lt;font', '<font').replace('&lt;/font&gt;', '</font>')
        
        return text
    
    def parse_table(self, table_lines: list) -> Table:
        """解析Markdown表格"""
        try:
            # 解析表格数据
            data = []
            for line in table_lines:
                # 跳过分隔线
                if re.match(r'\|[\s\-:]+\|', line):
                    continue
                
                # 提取单元格
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                data.append(cells)
            
            if not data:
                return None
            
            # 创建表格
            table = Table(data)
            
            # 设置样式
            style = TableStyle([
                # 表头样式
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a90e2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Chinese'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # 表格内容样式
                ('FONTNAME', (0, 1), (-1, -1), 'Chinese'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                
                # 边框
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                
                # 内边距
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ])
            
            table.setStyle(style)
            return table
            
        except Exception as e:
            logger.error(f"表格解析失败: {e}")
            return None
