"""
AI审核模块
使用AI模型比对Word文档和附件内容
发现笔误和不一致
"""
import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AIReviewer:
    """AI审核器，支持多种AI模型"""
    
    def __init__(self, 
                 api_key: str = None,
                 model: str = "gpt-4-turbo-preview",
                 api_type: str = "openai",
                 base_url: str = None):
        """
        初始化AI审核器
        
        Args:
            api_key: API密钥
            model: 模型名称
            api_type: API类型 (openai, anthropic, qwen, local)
            base_url: 自定义API地址（用于本地模型）
        """
        self.api_key = api_key
        self.model = model
        self.api_type = api_type.lower()
        self.base_url = base_url
        
        # 初始化客户端
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """初始化API客户端"""
        try:
            if self.api_type == "openai":
                from openai import OpenAI
                if self.base_url:
                    self.client = OpenAI(api_key=self.api_key or "dummy", base_url=self.base_url)
                else:
                    self.client = OpenAI(api_key=self.api_key)
                logger.info(f"使用OpenAI API，模型: {self.model}")
            
            elif self.api_type == "anthropic":
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
                logger.info(f"使用Anthropic API，模型: {self.model}")
            
            elif self.api_type == "qwen":
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
                )
                logger.info(f"使用千问API，模型: {self.model}")
            
            elif self.api_type == "local":
                from openai import OpenAI
                self.client = OpenAI(
                    api_key="dummy",
                    base_url=self.base_url or "http://localhost:11434/v1"
                )
                logger.info(f"使用本地API: {self.base_url}，模型: {self.model}")
            
            else:
                raise ValueError(f"不支持的API类型: {self.api_type}")
        
        except ImportError as e:
            logger.error(f"导入API库失败: {str(e)}")
            raise
    
    def review_document(self, 
                       doc_content: str,
                       attachments_content: List[Dict[str, Any]],
                       review_type: str = "comprehensive") -> Dict[str, Any]:
        """
        审核文档和附件内容
        
        Args:
            doc_content: Word文档内容
            attachments_content: 附件内容列表
            review_type: 审核类型 (comprehensive, typo, consistency)
            
        Returns:
            审核结果
        """
        logger.info(f"开始AI审核，类型: {review_type}")
        
        # 构建审核提示
        prompt = self._build_review_prompt(doc_content, attachments_content, review_type)
        
        # 调用AI模型
        try:
            response = self._call_ai_model(prompt)
            
            # 解析响应
            result = self._parse_ai_response(response, review_type)
            
            logger.info(f"AI审核完成，发现 {len(result.get('issues', []))} 个问题")
            
            return result
        
        except Exception as e:
            logger.error(f"AI审核失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "issues": []
            }
    
    def _build_review_prompt(self, 
                            doc_content: str,
                            attachments_content: List[Dict[str, Any]],
                            review_type: str) -> str:
        """构建审核提示词"""
        
        # 准备附件内容摘要
        attachments_summary = []
        for i, att in enumerate(attachments_content, 1):
            summary = f"\n### 附件 {i}: {att.get('file_name', 'Unknown')}\n"
            summary += f"类型: {att.get('file_type', 'Unknown')}\n"
            summary += f"内容:\n{att.get('content', '')[:2000]}\n"  # 限制长度
            attachments_summary.append(summary)
        
        attachments_text = "\n".join(attachments_summary)
        
        # 根据审核类型构建不同的提示
        if review_type == "typo":
            task_description = """
请仔细比对Word文档和附件内容，重点检查：
1. **拼写错误**：检查是否有错别字、拼写错误
2. **数字错误**：检查数字是否一致（如日期、金额、数量等）
3. **标点符号**：检查标点符号使用是否正确
"""
        
        elif review_type == "consistency":
            task_description = """
请仔细比对Word文档和附件内容，重点检查：
1. **内容一致性**：文档中引用的内容是否与附件一致
2. **数据一致性**：表格、图表中的数据是否与附件匹配
3. **引用准确性**：文档中对附件的引用是否准确
"""
        
        else:  # comprehensive
            task_description = """
请全面审核Word文档和附件内容，检查：
1. **拼写和语法**：检查错别字、语法错误
2. **数字和数据**：检查数字、日期、金额等是否一致
3. **内容一致性**：文档内容与附件是否一致
4. **逻辑连贯性**：内容是否逻辑清晰、前后连贯
5. **格式规范**：检查格式是否规范统一
"""
        
        prompt = f"""你是一位专业的文档审核专家。{task_description}

## Word文档内容：
{doc_content[:10000]}  

## 附件内容：
{attachments_text}

请按以下JSON格式返回审核结果：
{{
  "summary": "审核总结",
  "issues": [
    {{
      "severity": "高/中/低",
      "type": "拼写错误/内容不一致/格式错误/逻辑错误/其他",
      "location": "问题位置描述",
      "description": "问题详细描述",
      "original": "原文内容",
      "suggestion": "修改建议",
      "reference": "相关附件引用（如果有）"
    }}
  ],
  "statistics": {{
    "total_issues": 0,
    "high_severity": 0,
    "medium_severity": 0,
    "low_severity": 0
  }}
}}

请仔细审核并返回JSON格式的结果。"""
        
        return prompt
    
    def _call_ai_model(self, prompt: str) -> str:
        """调用AI模型"""
        
        if self.api_type in ["openai", "local", "qwen"]:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的文档审核专家，擅长发现文档中的错误和不一致之处。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            return response.choices[0].message.content
        
        elif self.api_type == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        
        else:
            raise ValueError(f"不支持的API类型: {self.api_type}")
    
    def _parse_ai_response(self, response: str, review_type: str) -> Dict[str, Any]:
        """解析AI响应"""
        try:
            # 尝试提取JSON
            import re
            
            # 查找JSON代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析
                json_str = response
            
            result = json.loads(json_str)
            result["status"] = "success"
            result["review_type"] = review_type
            
            return result
        
        except json.JSONDecodeError as e:
            logger.warning(f"解析JSON失败，返回原始响应: {str(e)}")
            
            # 如果解析失败，返回基本结构
            return {
                "status": "partial",
                "review_type": review_type,
                "summary": response,
                "issues": [],
                "raw_response": response,
                "parse_error": str(e)
            }
    
    def batch_review(self,
                    doc_result: Dict[str, Any],
                    ocr_results: List[Dict[str, Any]],
                    review_types: List[str] = None) -> Dict[str, Any]:
        """
        批量审核（支持多种审核类型）
        
        Args:
            doc_result: Word文档解析结果
            ocr_results: OCR结果列表
            review_types: 审核类型列表
            
        Returns:
            综合审核结果
        """
        if review_types is None:
            review_types = ["comprehensive"]
        
        doc_content = doc_result.get("content", "")
        
        all_results = {
            "document": doc_result.get("file_name", "Unknown"),
            "timestamp": self._get_timestamp(),
            "reviews": {},
            "summary": {
                "total_issues": 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0
            }
        }
        
        for review_type in review_types:
            logger.info(f"执行 {review_type} 审核")
            
            result = self.review_document(doc_content, ocr_results, review_type)
            all_results["reviews"][review_type] = result
            
            # 累计统计
            if "statistics" in result:
                stats = result["statistics"]
                all_results["summary"]["total_issues"] += stats.get("total_issues", 0)
                all_results["summary"]["high_severity"] += stats.get("high_severity", 0)
                all_results["summary"]["medium_severity"] += stats.get("medium_severity", 0)
                all_results["summary"]["low_severity"] += stats.get("low_severity", 0)
        
        return all_results
    
    def generate_report(self, review_result: Dict[str, Any], output_path: str):
        """
        生成审核报告
        
        Args:
            review_result: 审核结果
            output_path: 输出路径
        """
        output_path = Path(output_path)
        
        # 保存JSON格式
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(review_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"JSON报告已保存: {json_path}")
        
        # 生成Markdown格式报告
        md_path = output_path.with_suffix('.md')
        markdown_content = self._generate_markdown_report(review_result)
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"Markdown报告已保存: {md_path}")
    
    def _generate_markdown_report(self, review_result: Dict[str, Any]) -> str:
        """生成Markdown格式报告"""
        
        md = f"""# 文档审核报告

## 基本信息
- **文档名称**: {review_result.get('document', 'Unknown')}
- **审核时间**: {review_result.get('timestamp', 'Unknown')}

## 审核摘要
- **总问题数**: {review_result['summary']['total_issues']}
- **高严重性**: {review_result['summary']['high_severity']}
- **中严重性**: {review_result['summary']['medium_severity']}
- **低严重性**: {review_result['summary']['low_severity']}

"""
        
        # 添加各类审核结果
        for review_type, result in review_result.get('reviews', {}).items():
            md += f"\n## {review_type.upper()} 审核\n\n"
            
            if result.get('status') == 'success':
                md += f"**审核总结**: {result.get('summary', 'N/A')}\n\n"
                
                issues = result.get('issues', [])
                if issues:
                    md += "### 发现的问题\n\n"
                    
                    for i, issue in enumerate(issues, 1):
                        severity_emoji = {
                            'high': '🔴',
                            'medium': '🟡',
                            'low': '🟢'
                        }.get(issue.get('severity', 'low'), '⚪')
                        
                        md += f"#### {i}. {severity_emoji} {issue.get('type', 'Unknown').upper()}\n\n"
                        md += f"- **严重性**: {issue.get('severity', 'N/A')}\n"
                        md += f"- **位置**: {issue.get('location', 'N/A')}\n"
                        md += f"- **描述**: {issue.get('description', 'N/A')}\n"
                        
                        if issue.get('original'):
                            md += f"- **原文**: `{issue['original']}`\n"
                        
                        if issue.get('suggestion'):
                            md += f"- **建议**: {issue['suggestion']}\n"
                        
                        if issue.get('reference'):
                            md += f"- **参考**: {issue['reference']}\n"
                        
                        md += "\n"
                else:
                    md += "*未发现问题*\n\n"
            else:
                md += f"**状态**: {result.get('status', 'Unknown')}\n"
                if 'error' in result:
                    md += f"**错误**: {result['error']}\n"
        
        md += "\n---\n*报告由AI自动生成*\n"
        
        return md
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
