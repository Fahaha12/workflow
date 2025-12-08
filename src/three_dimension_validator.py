"""
三维度全核验专家
实现"文本+图片+PDF"三维度交叉核验
"""
import json
import re
from typing import Dict, List, Any, Optional
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class ThreeDimensionValidator:
    """三维度全核验专家"""
    
    def __init__(self, ai_client: OpenAI, model: str):
        """
        初始化核验器
        
        Args:
            ai_client: AI客户端
            model: 模型名称
        """
        self.client = ai_client
        self.model = model
        self.timeout = 180  # 三维度核验需要更长时间
    
    def validate(self, 
                 input_text: str,
                 pic_input: Dict[str, Any],
                 pdf_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行三维度全核验
        
        Args:
            input_text: 报告文本变量 {{input}}
            pic_input: 图片信息变量 {{picinput}}（JSON格式）
            pdf_input: PDF解析变量 {{pdfinput}}（JSON格式）
            
        Returns:
            核验结果（Markdown格式）
        """
        logger.info("=" * 60)
        logger.info("开始三维度全核验（文本+图片+PDF）")
        logger.info("=" * 60)
        
        # 第一步：解析三个变量
        logger.info("第一步：解析三个输入变量...")
        
        # 检查输入有效性
        validation_error = self._validate_inputs(input_text, pic_input, pdf_input)
        if validation_error:
            return validation_error
        
        # 第二步：构建核验提示词
        logger.info("第二步：构建三维度核验提示词...")
        prompt = self._build_validation_prompt(input_text, pic_input, pdf_input)
        
        # 第三步：调用AI执行核验
        logger.info("第三步：调用AI执行三维度交叉核验...")
        result = self._call_ai_validation(prompt)
        
        logger.info("=" * 60)
        logger.info("三维度全核验完成")
        logger.info("=" * 60)
        
        return result
    
    def _validate_inputs(self, 
                         input_text: str,
                         pic_input: Dict[str, Any],
                         pdf_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """验证输入有效性"""
        
        # 检查文本输入
        if not input_text or len(input_text.strip()) < 50:
            return {
                "error": "input变量文本异常，缺失核心段落标识、核心业务号码或内容为空，请检查变量",
                "error_type": "input_error"
            }
        
        # 检查图片输入
        if not pic_input:
            return {
                "error": "picinput变量异常，解析失败或缺失附件对应的图片信息，请检查变量",
                "error_type": "picinput_error"
            }
        
        # 检查PDF输入（PDF可以为空，但需要标注）
        # pdf_input 可以为空字典，表示没有PDF附件
        
        return None
    
    def _build_validation_prompt(self,
                                  input_text: str,
                                  pic_input: Dict[str, Any],
                                  pdf_input: Dict[str, Any]) -> str:
        """构建三维度核验提示词"""
        
        # 将字典转换为JSON字符串
        pic_json = json.dumps(pic_input, ensure_ascii=False, indent=2)
        pdf_json = json.dumps(pdf_input, ensure_ascii=False, indent=2) if pdf_input else "{}"
        
        prompt = f'''你是定则报告"文本+图片+PDF"三维度全核验专家，请执行以下核验任务：

## 输入变量

### 变量 {{{{input}}}}（报告文本）：
{input_text[:8000]}

### 变量 {{{{picinput}}}}（图片信息JSON）：
{pic_json}

### 变量 {{{{pdfinput}}}}（PDF解析JSON）：
{pdf_json}

## 核心概念

### 号码类型定义
- **业务号码**：申诉核心关联的号码（如套餐签约、费用产生的手机号/账号），需与报告首次提及的核心业务号码一致
- **联系号码**：辅助沟通的备用/家人号码，无需与业务号码一致，但需与报告、图片及PDF中明确标注匹配

## 执行步骤

### 第一步：三变量解析
1. 解析{{{{picinput}}}}：提取每个附件的图片状态、关键信息（号码类、业务类、数字类）
2. 解析{{{{pdfinput}}}}：提取PDF状态、关键信息
3. 解析{{{{input}}}}：拆分段落（标题→编号→一至四段），提取文本关键信息

### 第二步：信息融合
将文本与对应附件图片、PDF解析信息合并，形成关联链

### 第三步：9项核验
1. 附件名格式与笔误校验
2. 号码类型判定（业务号码/联系号码）
3. 业务号码三方交叉校验（文本、图片、PDF一致性）
4. 联系号码三方交叉校验
5. 专有名词与数字校验（套餐名称、金额三方一致性）
6. 关联性校验
7. 图片状态校验
8. 文本-图片一致性校验
9. PDF与文本/图片一致性校验

## 输出格式

请严格按以下Markdown格式输出：

# 定则报告核验结果（文本+图片+PDF三维度）

## 一、三变量基础信息与段落拆分结果

### 标题
[从input提取的报告标题]

### 编号
[从input提取的报告编号]

### 图片+PDF整体状态
- 可识别图片：X张（附件1、2、3）
- 模糊/无法识别图片：X张（附件X：模糊）
- 无核心业务信息图片：X张（附件X）
- PDF状态：[可识别/部分页面模糊/损坏/无核心业务信息]

### 第一段（用户申诉原文）
[拆分后的完整内容]
**本段关键信息（文本+图片+PDF融合）**：
- 核心业务号码：[文本号码]；[对应附件图片提取号码]；[PDF提取号码]
- 申诉内容：[文本申诉内容]

### 第二段（申诉核查情况）
[拆分后的完整内容]
**本段关键信息（文本+图片+PDF融合）**：
- 业务号码：[文本号码]；[对应附件图片提取号码]；[PDF提取号码]
- 联系号码：[文本号码]；[对应附件图片提取号码]；[PDF提取号码]
- 专有名词：[文本名词]；[对应附件图片提取名词]；[PDF提取名词]
- 数字信息：[文本数字]；[对应附件图片提取数字]；[PDF提取数字]

### 第三段（申诉后处理情况）
[拆分后的完整内容]
**本段关键信息（文本+图片+PDF融合）**：[融合信息]

### 第四段（涉及的证明材料）
[拆分后的完整内容]
**本段关键信息**：[附件说明汇总]

## 二、附件+PDF全维度核验报告（三维交叉校验）

| 载体全称 | 载体类型 | 对应状态 | 号码类型 | 错误类型/状态 | 具体核验描述及依据（文本+图片+PDF交叉） | 前文关联情况 | 修正建议 |
|----------|----------|----------|----------|---------------|----------------------------------------|--------------|----------|
| [附件名] | [图片/PDF] | [可识别/模糊] | [业务号码/联系号码/无号码] | [错误类型或无错误] | [详细核验描述] | [关联段落] | [修正建议] |

## 三、整体核验结论（按维度分类）

### 1. 三维度一致性结论
- 完全一致项：X项（列出）
- 部分一致项：X项（列出）
- 冲突项：X项（列出）
- 载体异常项：X项（列出）

### 2. 业务号码核验结果（三维交叉）
- 异常项：X项
- 整改要求：[具体要求]

### 3. 联系号码核验结果（三维交叉）
- 异常项：X项
- 整改要求：[具体要求]

### 4. 载体相关处理建议
- 紧急：[需要紧急处理的项目]
- 常规：[常规处理项目]
- 剔除：[可剔除项目]

### 5. 核心注意事项
[列出关键注意事项]

---

【重要提醒】
1. 优先级：业务系统数据＞PDF清晰信息＞图片清晰信息＞文本
2. 图片/PDF状态异常不终止流程，仅标注并提示人工复核
3. 所有差异必须标注具体来源（如"文本第二段第3行"、"附件1图片提取"、"PDF提取"）
'''
        
        return prompt
    
    def _call_ai_validation(self, prompt: str) -> Dict[str, Any]:
        """调用AI执行核验"""
        
        try:
            logger.info("调用AI模型进行三维度核验...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "你是定则报告'文本+图片+PDF'三维度全核验专家，精准区分'业务号码'与'联系号码'，执行严格的三维度交叉核验，输出规范Markdown格式结果。"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                timeout=self.timeout
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 调试输出
            logger.info("=" * 60)
            logger.info("【调试】三维度核验AI响应：")
            logger.info("=" * 60)
            logger.info(result_text[:3000])
            logger.info("=" * 60)
            
            return {
                "success": True,
                "markdown_report": result_text,
                "raw_response": result_text
            }
            
        except Exception as e:
            logger.error(f"三维度核验AI调用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": str(e),
                "markdown_report": self._generate_fallback_report()
            }
    
    def _generate_fallback_report(self) -> str:
        """生成降级报告"""
        return """# 定则报告核验结果（文本+图片+PDF三维度）

## ⚠️ 核验异常

AI核验调用失败，请检查：
1. API密钥是否正确
2. 网络连接是否正常
3. 输入数据是否完整

请稍后重试或联系技术支持。
"""


class ImageInfoExtractor:
    """图片信息提取器（生成picinput）"""
    
    def __init__(self, ai_client: OpenAI, model: str = "qwen3-vl-plus"):
        """
        初始化提取器
        
        Args:
            ai_client: AI客户端
            model: 视觉模型名称
        """
        self.client = ai_client
        self.model = model
        self.timeout = 60
    
    def extract_from_vision_results(self, vision_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        从视觉模型识别结果中提取结构化信息
        
        Args:
            vision_results: 视觉模型识别结果列表
            
        Returns:
            picinput格式的JSON
        """
        logger.info(f"从{len(vision_results)}个附件中提取图片信息...")
        
        pic_input = {
            "图片信息提取结果": [],
            "整体状态": {
                "可识别图片": 0,
                "模糊图片": 0,
                "无核心信息图片": 0,
                "总数": len(vision_results)
            }
        }
        
        for idx, result in enumerate(vision_results, 1):
            filename = result.get('file_name', f'附件{idx}')
            file_type = result.get('file_type', '')
            
            # 判断是PDF还是图片
            is_pdf = file_type.lower() == 'pdf' or file_type.lower() == '.pdf'
            
            # 根据类型获取内容
            if is_pdf:
                # PDF文本提取结果
                content = result.get('filtered_text', result.get('full_text', ''))
            else:
                # 图片视觉识别结果
                content = result.get('content', '')
            
            # 提取关键信息
            extracted = self._extract_key_info(content, idx, filename)
            
            # 判断状态
            if result.get('error') or result.get('status') == 'failed':
                status = "识别失败"
                pic_input["整体状态"]["模糊图片"] += 1
            elif len(content.strip()) < 20:
                status = "无核心业务信息"
                pic_input["整体状态"]["无核心信息图片"] += 1
            else:
                status = "可识别"
                pic_input["整体状态"]["可识别图片"] += 1
            
            pic_info = {
                "图片变量名": f"file{idx}",
                "对应附件": f"附件{idx}",
                "文件名": filename,
                "载体类型": "PDF" if is_pdf else "图片",
                "图片状态": status,
                "内容清晰度": "可识别" if status == "可识别" else "模糊/无法识别",
                "提取的关键信息": extracted,
                "原始识别内容": content[:500]  # 保留部分原始内容用于调试
            }
            
            pic_input["图片信息提取结果"].append(pic_info)
        
        # 调试输出
        logger.info("=" * 60)
        logger.info("【调试】生成的picinput：")
        logger.info("=" * 60)
        logger.info(json.dumps(pic_input, ensure_ascii=False, indent=2)[:2000])
        logger.info("=" * 60)
        
        return pic_input
    
    def _extract_key_info(self, content: str, idx: int, filename: str) -> Dict[str, Any]:
        """从内容中提取关键信息"""
        
        # 提取号码类
        phone_numbers = list(set(re.findall(r'1[3-9]\d{9}', content)))
        
        # 尝试区分业务号码和联系号码
        business_numbers = []
        contact_numbers = []
        
        for phone in phone_numbers:
            # 简单规则：如果号码前后有"业务"、"签约"等关键词，判定为业务号码
            pattern = rf'(业务|签约|办理|开通|套餐).{{0,20}}{phone}|{phone}.{{0,20}}(业务|签约|办理|开通|套餐)'
            if re.search(pattern, content):
                business_numbers.append(phone)
            # 如果有"联系"、"备用"、"家人"等关键词，判定为联系号码
            elif re.search(rf'(联系|备用|家人|沟通).{{0,20}}{phone}|{phone}.{{0,20}}(联系|备用|家人|沟通)', content):
                contact_numbers.append(phone)
            else:
                # 默认第一个号码为业务号码
                if not business_numbers:
                    business_numbers.append(phone)
                else:
                    contact_numbers.append(phone)
        
        # 提取业务类
        套餐名称 = re.findall(r'[沃畅冰神]派?\d+元\d*套餐?|[沃畅冰神]派\w+套餐|\d+元套餐', content)
        业务类型 = re.findall(r'(宽带|流量|话费|短信|彩铃|视频会员|合约)', content)
        
        # 提取数字类
        金额 = list(set(re.findall(r'\d+\.?\d*元', content)))
        日期 = list(set(re.findall(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}[日号]?', content)))
        
        # 从文件名提取附件名称
        附件名称 = self._parse_attachment_name(filename)
        
        return {
            "号码类": {
                "业务号码": business_numbers,
                "联系号码": contact_numbers,
                "所有号码": phone_numbers
            },
            "业务类": {
                "套餐名称": list(set(套餐名称)),
                "业务类型": list(set(业务类型))
            },
            "数字类": {
                "金额": 金额,
                "日期": 日期
            },
            "附件名称": 附件名称
        }
    
    def _parse_attachment_name(self, filename: str) -> Dict[str, str]:
        """解析附件文件名"""
        # 格式：编号-名称.扩展名
        if '.' in filename:
            name_without_ext = filename.rsplit('.', 1)[0]
        else:
            name_without_ext = filename
        
        pattern = r'^(\d+)-(.*)$'
        match = re.match(pattern, name_without_ext)
        
        if match:
            return {
                "编号": match.group(1),
                "名称": match.group(2).strip('-').strip(),
                "原始文件名": filename
            }
        else:
            return {
                "编号": "",
                "名称": filename,
                "原始文件名": filename
            }


class PDFInfoExtractor:
    """PDF信息提取器（生成pdfinput）"""
    
    def __init__(self):
        pass
    
    def extract_from_vision_results(self, vision_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        从视觉模型识别结果中提取PDF信息
        
        Args:
            vision_results: 视觉模型识别结果列表
            
        Returns:
            pdfinput格式的JSON
        """
        pdf_input = {
            "PDF信息提取结果": [],
            "整体状态": {
                "可识别PDF": 0,
                "部分模糊PDF": 0,
                "无核心信息PDF": 0,
                "总数": 0
            }
        }
        
        for idx, result in enumerate(vision_results, 1):
            file_type = result.get('file_type', '')
            
            # 只处理PDF文件
            is_pdf = file_type.lower() == 'pdf' or file_type.lower() == '.pdf'
            if not is_pdf:
                continue
            
            pdf_input["整体状态"]["总数"] += 1
            
            filename = result.get('file_name', f'PDF附件{idx}')
            
            # 获取PDF文本提取结果（优先使用过滤后的文本）
            content = result.get('filtered_text', result.get('full_text', ''))
            
            # 如果有key_info，直接使用
            key_info = result.get('key_info', {})
            
            # 提取关键信息
            if key_info:
                # 使用PDF提取器已经提取的信息
                extracted = {
                    "号码类": {
                        "业务号码": key_info.get('phone_numbers', [])[:1],  # 第一个作为业务号码
                        "联系号码": key_info.get('phone_numbers', [])[1:],  # 其余作为联系号码
                        "所有号码": key_info.get('phone_numbers', [])
                    },
                    "业务类": {
                        "套餐名称": [],
                        "业务类型": key_info.get('business_info', [])
                    },
                    "数字类": {
                        "金额": key_info.get('amounts', []),
                        "日期": key_info.get('dates', [])
                    },
                    "附件名称": {"原始名称": filename}
                }
            else:
                # 降级：从内容中提取
                extractor = ImageInfoExtractor(None, None)
                extracted = extractor._extract_key_info(content, idx, filename)
            
            # 判断状态
            if result.get('error') or result.get('status') == 'failed':
                status = "识别失败"
                pdf_input["整体状态"]["部分模糊PDF"] += 1
            elif len(content.strip()) < 20:
                status = "无核心业务信息"
                pdf_input["整体状态"]["无核心信息PDF"] += 1
            else:
                status = "可识别"
                pdf_input["整体状态"]["可识别PDF"] += 1
            
            pdf_info = {
                "PDF变量名": f"pdf{pdf_input['整体状态']['总数']}",
                "对应附件": f"PDF附件{pdf_input['整体状态']['总数']}",
                "文件名": filename,
                "载体类型": "PDF",
                "PDF状态": status,
                "内容清晰度": "可识别" if status == "可识别" else "部分模糊/无法识别",
                "提取的关键信息": extracted,
                "原始识别内容": content[:500]
            }
            
            pdf_input["PDF信息提取结果"].append(pdf_info)
        
        return pdf_input
