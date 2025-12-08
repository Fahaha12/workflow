"""
AI信息提取器
使用千问AI从文档和附件中提取关键信息
使用优化的提示词
"""
import json
import re
from typing import Dict, List, Any
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class AIExtractor:
    """AI信息提取器"""
    
    def __init__(self, ai_client: OpenAI, model: str):
        """
        初始化提取器
        
        Args:
            ai_client: AI客户端
            model: 模型名称
        """
        self.client = ai_client
        self.model = model
        self.timeout = 120  # 超时时间（秒）
    
    def extract_user_complaint_info(self, section1_text: str) -> Dict[str, Any]:
        """
        从用户申诉原文中提取关键信息
        
        Args:
            section1_text: 第一部分文本
            
        Returns:
            提取的关键信息
        """
        logger.info("使用AI提取用户申诉关键信息...")
        
        # 简化的提示词
        prompt = f"""从以下申诉原文中提取关键信息，返回JSON格式：

申诉原文：
{section1_text[:1500]}

提取内容：
1. 号码类：业务号码、联系号码
2. 业务类：套餐名称、业务类型
3. 数字类：金额、日期
4. 用户诉求

返回格式：
{{"号码类":{{"业务号码":"","联系号码":[]}},"业务类":{{"套餐名称":"","业务类型":""}},"数字类":{{"金额":[],"日期":[]}},"用户诉求":[]}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是申诉文档信息提取专家，只返回JSON。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                timeout=self.timeout
            )
            
            result_text = response.choices[0].message.content.strip()
            # 提取JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            extracted_info = json.loads(result_text)
            logger.info("✓ 用户申诉信息提取完成")
            return extracted_info
            
        except Exception as e:
            logger.error(f"AI提取用户申诉信息失败: {e}")
            # 降级到正则提取
            return self._regex_extract_section1(section1_text)
    
    def extract_attachment_info(self, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        从附件OCR结果中提取关键信息
        
        Args:
            ocr_results: OCR识别结果列表
            
        Returns:
            图片信息提取结果（JSON格式）
        """
        logger.info(f"使用AI提取 {len(ocr_results)} 个附件的关键信息...")
        
        # ========== 调试：输出OCR原始结果 ==========
        logger.info("=" * 60)
        logger.info("【调试】OCR识别原始结果：")
        logger.info("=" * 60)
        for idx, ocr_result in enumerate(ocr_results, 1):
            filename = ocr_result.get('file_name', f'附件{idx}')
            content = ocr_result.get('content', '')
            file_type = ocr_result.get('file_type', '')
            logger.info(f"\n--- 附件{idx}: {filename} ({file_type}) ---")
            logger.info(f"内容长度: {len(content)} 字符")
            logger.info(f"内容预览(前500字):\n{content[:500]}")
            logger.info("-" * 40)
        logger.info("=" * 60)
        
        # 构建附件内容
        attachments_content = []
        for idx, ocr_result in enumerate(ocr_results, 1):
            filename = ocr_result.get('file_name', f'附件{idx}')
            content = ocr_result.get('content', '')[:800]  # 限制长度
            attachments_content.append(f"附件{idx}（{filename}）内容：\n{content}")
        
        all_content = "\n\n".join(attachments_content)
        
        # 使用你提供的提示词格式
        prompt = f"""你是图片关键信息提取专家，核心任务是读取以下附件内容，提取结构化信息。

附件内容：
{all_content}

核心提取内容（必须提取，无则标注"无"）：
1. 号码类：业务号码、联系号码、备用号码（需区分标注，无明确标注则统称"疑似号码"）
2. 业务类：套餐名称、业务类型、协议编号、凭证编号
3. 数字类：金额、年份、日期、次数等关键数字
4. 基础信息：载体类型（办理协议/联系记录/投诉记录/凭证）、内容清晰度（可识别/模糊/无法识别）

异常处理规则：
- 模糊/无法识别标注"图片状态：模糊/无法识别，无有效信息"
- 无业务相关信息标注"图片状态：无核心业务信息"
- 损坏/格式错误标注"图片状态：损坏/格式异常，无法提取信息"

输出格式（强制JSON）：
{{"图片信息提取结果":[{{"图片变量名":"file1","对应附件":"附件1","图片状态":"可识别","提取的关键信息":{{"号码类":["18638511201（业务号码）"],"业务类":["沃派39元套餐"],"数字类":["39元","2024年5月"],"载体类型":"办理协议","内容清晰度":"可识别"}},"异常说明":"无"}}]}}

只返回JSON，不要其他说明。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是图片关键信息提取专家，只返回JSON格式结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                timeout=self.timeout
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # ========== 调试：输出AI原始响应 ==========
            logger.info("=" * 60)
            logger.info("【调试】AI原始响应：")
            logger.info("=" * 60)
            logger.info(result_text[:2000])  # 限制输出长度
            logger.info("=" * 60)
            
            # 提取JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            extracted_info = json.loads(result_text)
            
            # ========== 调试：输出解析后的JSON ==========
            logger.info("=" * 60)
            logger.info("【调试】AI提取结果（解析后JSON）：")
            logger.info("=" * 60)
            logger.info(json.dumps(extracted_info, ensure_ascii=False, indent=2)[:3000])
            logger.info("=" * 60)
            
            logger.info(f"✓ {len(ocr_results)} 个附件信息提取完成")
            return extracted_info
            
        except Exception as e:
            logger.error(f"AI提取附件信息失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            # 降级到正则提取
            logger.info("【调试】降级使用正则提取...")
            return self._regex_extract_attachments(ocr_results)
    
    def cross_validate_with_ai(self, 
                              section1_info: Dict[str, Any],
                              section2_text: str,
                              section3_text: str,
                              section4_text: str,
                              attachment_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用AI进行三维度交叉验证
        
        Args:
            section1_info: 第一部分提取的信息
            section2_text: 第二部分文本
            section3_text: 第三部分文本
            section4_text: 第四部分文本
            attachment_info: 附件提取的信息
            
        Returns:
            交叉验证结果
        """
        logger.info("使用AI进行三维度交叉验证...")
        
        # 构建输入
        section1_json = json.dumps(section1_info, ensure_ascii=False)
        attachment_json = json.dumps(attachment_info, ensure_ascii=False)
        
        prompt = f"""你是"文本+图片+PDF"三维度全核验专家，执行以下核验任务：

## 输入变量

### 用户申诉关键信息：
{section1_json}

### 第二部分-申诉核查情况：
{section2_text[:1000]}

### 第三部分-申诉后处理情况：
{section3_text[:1000]}

### 第四部分-附件名称：
{section4_text[:500]}

### 附件提取信息：
{attachment_json}

## 核验任务

执行以下核验，输出JSON：
1. 附件名格式与笔误校验
2. 号码类型判定（业务号码/联系号码）
3. 业务号码三方交叉校验
4. 联系号码三方交叉校验
5. 专有名词与数字校验（套餐名称、金额）
6. 附件关联性校验
7. 图片/PDF状态校验
8. 文本-图片一致性校验
9. PDF与文本/图片一致性校验

## 输出格式

{{"validation_results":[{{"check_type":"核验类型","severity":"critical/warning/info","issue_description":"问题描述","evidence":{{"text":"文本信息","attachment":"附件信息"}},"suggestion":"修正建议"}}],"summary":{{"total_issues":0,"critical_issues":0,"warnings":0}}}}

只返回JSON。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是三维度交叉验证专家，只返回JSON。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                timeout=self.timeout
            )
            
            result_text = response.choices[0].message.content.strip()
            # 提取JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            validation_result = json.loads(result_text)
            logger.info("✓ 三维度交叉验证完成")
            return validation_result
            
        except Exception as e:
            logger.error(f"AI交叉验证失败: {e}")
            return {
                "validation_results": [],
                "summary": {
                    "total_issues": 0,
                    "critical_issues": 0,
                    "warnings": 0
                }
            }
    
    def _regex_extract_section1(self, text: str) -> Dict[str, Any]:
        """正则提取第一部分信息（降级方案）"""
        phones = list(set(re.findall(r'1[3-9]\d{9}', text)))
        amounts = list(set(re.findall(r'¥?\s*\d+\.?\d*\s*元', text)))
        dates = list(set(re.findall(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?', text)))
        
        return {
            "号码类": {
                "业务号码": phones[0] if phones else "",
                "联系号码": phones[1:] if len(phones) > 1 else []
            },
            "业务类": {
                "套餐名称": "",
                "业务类型": ""
            },
            "数字类": {
                "金额": amounts,
                "日期": dates
            },
            "用户诉求": []
        }
    
    def _regex_extract_attachments(self, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """正则提取附件信息（降级方案）"""
        results = []
        
        for idx, ocr_result in enumerate(ocr_results, 1):
            filename = ocr_result.get('file_name', f'附件{idx}')
            content = ocr_result.get('content', '')
            
            # 提取号码
            phones = list(set(re.findall(r'1[3-9]\d{9}', content)))
            # 提取金额
            amounts = list(set(re.findall(r'¥?\s*\d+\.?\d*\s*元', content)))
            # 提取日期
            dates = list(set(re.findall(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?', content)))
            
            results.append({
                "图片变量名": f"file{idx}",
                "对应附件": f"附件{idx}",
                "文件名": filename,
                "图片状态": "可识别" if content else "无内容",
                "提取的关键信息": {
                    "号码类": [f"{p}（疑似号码）" for p in phones] if phones else ["无"],
                    "业务类": ["无"],
                    "数字类": amounts + dates if (amounts or dates) else ["无"],
                    "载体类型": "未知",
                    "内容清晰度": "可识别" if content else "无法识别"
                },
                "异常说明": "无" if content else "无内容"
            })
        
        return {"图片信息提取结果": results}
