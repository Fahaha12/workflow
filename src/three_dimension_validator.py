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
        
        # 将字典转换为JSON字符串（精简版，只保留关键信息）
        pic_json_compact = self._compact_pic_input(pic_input)
        pdf_json_compact = self._compact_pdf_input(pdf_input) if pdf_input else "无PDF附件"
        
        # 获取当前时间
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 统计附件数量
        pic_count = pic_input.get("整体状态", {}).get("总数", 0) if pic_input else 0
        pdf_count = pdf_input.get("整体状态", {}).get("总数", 0) if pdf_input else 0
        
        prompt = f'''你是定则报告"文本+图片+PDF"三维度全核验专家，请执行核验任务并输出**简洁、清晰、易读**的报告。

## 输入数据

**当前核验时间**：{current_time}
**附件数量**：图片{pic_count}张 + PDF {pdf_count}份

**报告文本**：
{input_text[:8000]}

**图片附件信息**：
{pic_json_compact}

**PDF附件信息**：
{pdf_json_compact}

## 核验要求

1. **业务号码**：申诉核心关联的号码（套餐签约、费用产生的手机号）
2. **联系号码**：辅助沟通的备用/家人号码
3. **日期时间**：注意区分以下情况：
   - **套餐/合约结束日期**：可能是未来日期（如2029年、2050年），这是正常的长期套餐到期时间，不要标记为异常
   - **业务办理日期**：应该是过去的日期
   - **只有明显不合理的日期才标记为问题**（如1900年、3000年等）

## 输出格式要求

请输出**简洁清晰**的Markdown报告，格式如下：

---

# 📋 申诉文档核验报告

## 📌 基本信息

| 项目 | 内容 |
|------|------|
| **报告标题** | [从文本提取的标题，如"关于XX用户申诉处理情况报告"] |
| **报告编号** | [从文本提取的编号，如"部-2025080102010768"] |
| **核验时间** | {current_time} |
| **附件数量** | 图片{pic_count}张 + PDF {pdf_count}份 |

---

## 📊 核验结果摘要

| 核验维度 | 状态 | 说明 |
|---------|------|------|
| 业务号码一致性 | ✅/⚠️/❌ | [简要说明] |
| 联系号码一致性 | ✅/⚠️/❌ | [简要说明] |
| 金额数据一致性 | ✅/⚠️/❌ | [简要说明] |
| 日期时间一致性 | ✅/⚠️/❌ | [简要说明] |
| 附件完整性 | ✅/⚠️/❌ | [简要说明] |

> **整体结论**：[一句话总结核验结果，如"发现2处数据不一致，需要修正"]

---

## 🔍 详细核验结果

### 1️⃣ 关键号码核验

| 号码类型 | 文本中的号码 | 附件中的号码 | 核验结果 |
|---------|-------------|-------------|---------|
| 业务号码 | [号码] | [号码] | ✅一致/❌不一致 |
| 联系号码 | [号码] | [号码] | ✅一致/❌不一致 |

**问题说明**：[如有不一致，详细说明位置和差异]

### 2️⃣ 金额与数字核验

| 数据项 | 文本描述 | 附件证据 | 核验结果 |
|-------|---------|---------|---------|
| [金额/费用] | [文本中的金额] | [附件中的金额] | ✅/❌ |

### 3️⃣ 附件逐项核验

| 附件 | 文件名 | 类型 | 关键信息 | 核验说明 |
|-----|-------|------|---------|---------|
| 附件1 | [文件名] | 业务凭证/记录查询/操作指引/沟通记录 | [关键信息] | ✅/⚠️/❌ [说明] |
| 附件2 | [文件名] | [类型] | [关键信息] | [核验说明] |
| ... | ... | ... | ... | ... |

**附件类型处理规则**：
- **业务凭证**：需核验金额、日期、号码等与文本一致性
- **记录查询**：需核验查询结果与文本描述一致性
- **操作指引**：直接标记为 ✅ 通过，不需要核验其中的金额等信息（如销户入口截图中显示的费用是通用说明，与本次申诉无关）
- **沟通记录**：需核验沟通内容与文本描述一致性

**重要**：操作指引类附件（如销户入口截图、知识库截图）中的金额、费用等信息是通用说明，不是本次申诉的具体数据，不要对其发出警告或标记为问题。

---

## ⚠️ 发现的问题

> 如果没有问题，显示"✅ 未发现明显问题"

### 问题1：[问题标题]
- **位置**：[具体位置，如"第二段第3行" 或 "附件2"]
- **问题描述**：[具体描述]

### 问题2：[问题标题]
- **位置**：[具体位置]
- **问题描述**：[具体描述]

---

**注意**：
- 使用 ✅ 表示通过/一致
- 使用 ⚠️ 表示警告/需关注
- 使用 ❌ 表示错误/不一致
- 表格内容要简洁，每格不超过30字
- 如果某项没有数据，显示"-"而不是留空
- 手机号码必须是11位数字（1开头），不要把长数字串（如接触ID、工单号）误认为手机号
'''
        
        return prompt
    
    def _compact_pic_input(self, pic_input: Dict[str, Any]) -> str:
        """精简图片附件信息，确保所有附件都被包含"""
        if not pic_input:
            return "无图片附件"
        
        lines = []
        
        # 整体状态
        status = pic_input.get("整体状态", {})
        lines.append(f"**整体状态**: 共{status.get('总数', 0)}张图片，可识别{status.get('可识别图片', 0)}张，模糊{status.get('模糊图片', 0)}张")
        lines.append("")
        
        # 每个附件的精简信息
        for item in pic_input.get("图片信息提取结果", []):
            att_name = item.get("对应附件", "未知")
            filename = item.get("文件名", "")[:40]  # 限制文件名长度
            status = item.get("图片状态", "未知")
            
            # 提取关键信息
            key_info = item.get("提取的关键信息", {})
            phones = key_info.get("号码类", {}).get("所有号码", [])
            amounts = key_info.get("数字类", {}).get("金额", [])
            dates = key_info.get("数字类", {}).get("日期", [])
            
            # 精简格式
            info_parts = []
            if phones:
                info_parts.append(f"号码:{','.join(phones[:2])}")
            if amounts:
                info_parts.append(f"金额:{','.join(amounts[:2])}")
            if dates:
                info_parts.append(f"日期:{','.join(dates[:2])}")
            
            info_str = "; ".join(info_parts) if info_parts else "无关键信息"
            lines.append(f"- **{att_name}**({filename}): [{status}] {info_str}")
        
        return "\n".join(lines)
    
    def _compact_pdf_input(self, pdf_input: Dict[str, Any]) -> str:
        """精简PDF附件信息"""
        if not pdf_input or pdf_input.get("整体状态", {}).get("总数", 0) == 0:
            return "无PDF附件"
        
        lines = []
        
        # 整体状态
        status = pdf_input.get("整体状态", {})
        lines.append(f"**整体状态**: 共{status.get('总数', 0)}份PDF，可识别{status.get('可识别PDF', 0)}份")
        lines.append("")
        
        # 每个PDF的精简信息
        for item in pdf_input.get("PDF信息提取结果", []):
            filename = item.get("文件名", "")[:50]
            status = item.get("PDF状态", "未知")
            
            # 提取关键信息
            key_info = item.get("提取的关键信息", {})
            phones = key_info.get("号码类", {}).get("所有号码", [])
            amounts = key_info.get("数字类", {}).get("金额", [])
            
            info_parts = []
            if phones:
                info_parts.append(f"号码:{','.join(phones[:2])}")
            if amounts:
                info_parts.append(f"金额:{','.join(amounts[:3])}")
            
            info_str = "; ".join(info_parts) if info_parts else "无关键信息"
            lines.append(f"- **{filename}**: [{status}] {info_str}")
        
        return "\n".join(lines)
    
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
        phone_numbers = list(set(re.findall(r'(?<!\d)1[3-9]\d{9}(?!\d)', content)))
        
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
