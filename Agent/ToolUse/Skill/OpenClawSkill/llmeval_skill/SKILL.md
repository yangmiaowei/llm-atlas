---
name: llmeval_skill
description: 对Excel数据进行LLM自动评分。整合了读取Excel、配置提示词、逐行调用LLM、解析评分、返回结果的完整流程。支持多维度评估，可自定义评估场景、评分标准和评分步骤。
---

# llmeval_skill

## 使用场景（When to use）
- 需要对Excel中的AI助手回复进行批量自动评分
- 需要多维度评估（准确性、全面性、逻辑性等）
- 需要对比标准答案和待评估答案的质量
- 需要基于知识库片段进行上下文评估
- 需要生成详细的评分报告和维度分析

## 执行

把参数写成 JSON，从标准输入传给脚本：

```bash
python {baseDir}/scripts/tool.py
```

## 参数（Parameters）
必须用 JSON Schema 格式：

```json
{
  "type": "object",
  "properties": {
    "excel_file_path": {
      "type": "string",
      "description": "Excel文件路径"
    },
    "data_columns": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "数据列列表，指定需要从Excel中读取的列名，如 [\"question\", \"answer\", \"ref_answer\", \"chunks\", \"ref_chunks\"]，默认[\"question\", \"answer\"]"
    },
    "evaluation_scene": {
      "type": "string",
      "description": "评估场景名称，如 \"问答咨询类\"、\"内容创作类\" 等"
    },
    "scene_desc": {
      "type": "string",
      "description": "场景描述，详细说明评估场景的定义和特点"
    },
    "evaluation_metric": {
      "type": "string",
      "description": "评估指标，描述各个评估维度及其权重，格式为多行文本，每行一个维度"
    },
    "max_score": {
      "type": "integer",
      "description": "最大分数，每个维度的评分上限（如 10、100）"
    },
    "score_details": {
      "type": "string",
      "description": "评分标准详情，详细说明各档次的评分标准（如优秀、及格、不及格）"
    },
    "steps": {
      "type": "string",
      "description": "评分步骤，描述评估的具体流程和步骤"
    },
    "api_key": {
      "type": "string",
      "description": "LLM API密钥，用于调用模型接口"
    },
    "model_name": {
      "type": "string",
      "description": "模型名称，默认使用 glm-4.7",
      "default": "glm-4.7"
    },
    "file_content": {
      "type": "string",
      "description": "可选的源文件内容，用于提供额外的上下文信息",
      "default": ""
    },
    "delay_seconds": {
      "type": "number",
      "description": "每次API调用之间的延迟时间（秒），用于控制API请求速率，默认0.2秒（并发模式下此参数不再使用）",
      "default": 0.2
    },
    "max_workers": {
      "type": "integer",
      "description": "最大并发线程数，用于控制同时处理的线程数量，默认5。增大此值可提升处理速度，但需注意API调用频率限制",
      "default": 5
    }
  },
  "required": [
    "excel_file_path",
    "data_columns",
    "evaluation_scene",
    "scene_desc",
    "evaluation_metric",
    "max_score",
    "score_details",
    "steps",
    "api_key"
  ]
}
```
