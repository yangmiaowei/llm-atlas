"""
LLM评估技能函数
整合了读取Excel、配置提示词、逐行调用LLM、解析评分、返回结果的完整流程
"""
import json
import time
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
from openpyxl import load_workbook
from zhipuai import ZhipuAI
from concurrent.futures import ThreadPoolExecutor


# 支持的列与展示标签
VALID_COLUMNS = {
    "question": "[用户指令]",
    "answer": "[待评估的AI助手回复]",
    "ref_answer": "[AI助手的标准回复]",
    "chunks": "[待评估AI助手回复所召回的知识库片段]",
    "ref_chunks": "[AI助手的标准回复召回的知识库片段]",
}


def _build_evaluation_prompt(
    data_columns: List[str],
    evaluation_scene: str,
    scene_desc: str,
    evaluation_metric: str,
    max_score: int,
    score_details: str,
    steps: str,
    file_content: str = "",
) -> str:
    """根据传入参数组装测评用 prompt 模板"""
    max_score_value = max_score if max_score is not None else 100

    # 组合上下文片段，包含需要在运行时被二次渲染的占位符
    context_blocks = []
    for col in data_columns:
        label = VALID_COLUMNS.get(col)
        if not label:
            continue
        context_blocks.append(label + ":")
        context_blocks.append("")
        context_blocks.append("{" + col + "}")
        context_blocks.append("")

    if file_content:
        context_blocks.append("[需要分析原文的上下文]:")
        context_blocks.append("")
        context_blocks.append(file_content)
        context_blocks.append("")

    context_section = "\n".join(context_blocks)

    role_line = (
        '你是一名公正的文本评分裁判，需要在'
        + (evaluation_scene or "")
        + "场景下(场景定义:"
        + (scene_desc or "")
        + ')，按照以下原则评估"AI助手回复"的质量。'
    )

    parts = [
        "<角色和任务>",
        role_line,
        "",
        "<评分原则>",
        "-根据以下维度对AI助手回复进行评价，按权重从高到低排序:",
        "***",
        evaluation_metric or "",
        "***",
        "",
        f"-每个维度的评分范围为0至{max_score_value} 分，评分标准如下:",
        "",
        "***",
        score_details or "",
        "***",
        "",
        "<评分步骤>",
        '-我将提供用户指令、待评估的AI助手回复、AI助手的标准回复（如有）及评估所需所有相关的数据，请按照以下流程对"AI助手回复"进行评价:',
        steps or "",
        "",
        "<必须遵循>",
        "-严格依据评分原则，必须赋整数分值。",
        "-禁止忽略任何维度或添加未提及的维度。",
        "",
        "<输出要求>",
        "-仅输出JSON格式内容，禁止任何无关说明。",
        "-JSON输出模板:",
        "",
        "{",
        '"综合评分":"[加权平均得分，取整]",',
        '"综合评分原因":"(总结综合评分原因)。具体表现如下:",',
        '"[维度1名称]":{',
        f'"score":"[0至{max_score_value}间的整数分]",',
        '"analysis":"(简要描述该维度的亮点或不足)"',
        "},",
        '"[维度2名称]":{',
        f'"score":"[0至{max_score_value}间的整数分]",',
        '"analysis":"(简要描述该维度的亮点或不足)"',
        "},",
        "//...其他维度表现",
        "}",
        "",
        "#需要分析的用户指令、待评估内容及评估所需所有相关的数据:",
        "***",
        context_section,
        "***",
    ]

    return "\n".join(parts)


def _render_prompt(template: str, values: Dict[str, Any]) -> str:
    """
    使用最简单的占位符替换渲染 prompt。
    支持 {question}/{answer} 这种写法，同时避免 str.format 因 JSON 大括号导致报错。
    """
    if not template:
        return ""
    rendered = template
    for key, val in values.items():
        rendered = rendered.replace("{" + str(key) + "}", "" if val is None else str(val))
    return rendered


def _try_parse_json_dict(text: Any) -> Dict[str, Any]:
    """
    尝试将模型返回的字符串解析为 dict：
    - 支持 ```json ... ``` 代码块
    - 支持前后有多余文本时，从第一个 { 到最后一个 } 截取
    解析失败则抛出 ValueError（让上层记录失败原因）。
    """
    if text is None:
        raise ValueError("模型返回为空，无法解析为 JSON")
    if isinstance(text, dict):
        return text
    s = str(text).strip()
    if not s:
        raise ValueError("模型返回为空字符串，无法解析为 JSON")

    # 去掉 Markdown 代码块包裹
    if "```" in s:
        if s.startswith("```"):
            first_nl = s.find("\n")
            if first_nl != -1:
                s = s[first_nl + 1 :]
            end = s.rfind("```")
            if end != -1:
                s = s[:end]
        else:
            start = s.find("```")
            end = s.rfind("```")
            if start != -1 and end != -1 and end > start:
                mid = s[start + 3 : end]
                mid = mid.lstrip()
                # 处理 ```json\n{...}\n``` 这种语言标记
                nl = mid.find("\n")
                if nl != -1:
                    first_line = mid[:nl].strip().lower()
                    if first_line in ("json", "javascript", "js"):
                        mid = mid[nl + 1 :]
                s = mid

    s = s.strip()

    # 直接解析
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # 截取第一个 { 到最后一个 } 再解析
    left = s.find("{")
    right = s.rfind("}")
    if left != -1 and right != -1 and right > left:
        candidate = s[left : right + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    short = s[:200].replace("\n", " ")
    raise ValueError(f"模型返回不是有效的 JSON: {short}")


def _call_model_api(
    prompt_text: str,
    api_key: str,
    model_name: str = "glm-4.7",
    max_tokens: int = 65536,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """调用模型接口，返回 JSON dict（模型输出可能是字符串，需要做解析）"""
    client = ZhipuAI(api_key=api_key)
    
    messages = [
        {
            "role": "system",
            "content": "你是一个专业的测评助手，能够根据给定的上下文规则进行测评打分。",
        },
        {"role": "user", "content": prompt_text},
    ]
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=temperature,
            top_p=0.9,
            messages=messages,
            max_tokens=max_tokens
        )
        
        content = response.choices[0].message.content
        
        if not content:
            raise ValueError("模型返回内容为空")
        
        # 模型常见返回是字符串 JSON（可能带 ```json```）
        return _try_parse_json_dict(content)
        
    except Exception as e:
        print(f"API调用失败：{str(e)}")
        raise ValueError(f"API调用失败：{str(e)}") from e


def _process_single_row(row_data_tuple: tuple) -> Dict[str, Any]:
    """
    处理单行数据的函数，用于并发处理
    
    Args:
        row_data_tuple: (row_index, row_data_dict, header_row, prompt_template, 
                        data_columns, api_key, model_name, max_score)
    
    Returns:
        结果字典，包含 row_index, question, answer, prompt, status, result, error_message
    """
    row_index, row_data, header_row, prompt_template, data_columns, api_key, model_name, max_score = row_data_tuple
    
    # 检查是否整行都为空
    if all(cell is None or (isinstance(cell, str) and not str(cell).strip()) for cell in row_data.values()):
        return {
            "row_index": row_index,
            "question": "",
            "answer": "",
            "prompt": "",
            "status": "skipped",
            "result": None,
            "error_message": "空行，已跳过",
        }
    
    question_val = row_data.get("question", "")
    answer_val = row_data.get("answer", "")
    question_str = (question_val if question_val is not None else "").strip()
    answer_str = (answer_val if answer_val is not None else "").strip()
    
    # 根据 data_columns 构建渲染字典
    prompt_values = {}
    for col in data_columns:
        prompt_values[col] = row_data.get(col, "")
    
    # 渲染提示词
    prompt = _render_prompt(prompt_template, prompt_values)
    
    # 构建结果项
    result_item = {
        "row_index": row_index,
        "question": question_str,
        "answer": answer_str,
        "prompt": prompt,
        "status": "failed",
        "result": None,
        "error_message": None,
    }
    
    try:
        # 调用LLM
        response_data = _call_model_api(
            prompt_text=prompt,
            api_key=api_key,
            model_name=model_name,
        )
        
        # 解析评分
        normalized = _normalize_result(response_data, max_score=max_score)
        
        result_item["status"] = "success"
        result_item["result"] = normalized
        result_item["error_message"] = None
        
    except Exception as e:
        result_item["status"] = "failed"
        result_item["result"] = None
        result_item["error_message"] = str(e)
    
    return result_item


def _normalize_result(data: Dict[str, Any], max_score: int) -> Dict[str, Any]:
    """
    规范化评测结果为统一结构:
    {
      "综合评分": int,
      "综合评分原因": str,
      "维度评分": {
         "维度名": {"score": int, "analysis": str},
         ...
      }
    }
    """
    result = {
        "综合评分": None,
        "综合评分原因": "",
        "维度评分": {}
    }
    # 综合评分
    overall = data.get("综合评分") or data.get("overall_score") or data.get("score")
    try:
        if overall is not None:
            overall = int(overall)
    except Exception:
        overall = None
    result["综合评分"] = overall

    # 综合评分原因
    overall_reason = data.get("综合评分原因") or data.get("overall_reason") or data.get("reason") or ""
    result["综合评分原因"] = str(overall_reason) if overall_reason is not None else ""

    # 维度评分
    dims = data.get("维度评分")
    if isinstance(dims, dict):
        # 如果模型已经返回了 { "维度评分": { "维度名": {"score":..,"analysis":..} } } 结构
        for key, value in dims.items():
            if not key:
                continue
            if isinstance(value, dict):
                score_val = value.get("score")
                analysis_val = value.get("analysis") or value.get("desc") or ""
            else:
                score_val = None
                analysis_val = value
            try:
                if score_val is not None:
                    score_val = int(score_val)
                    score_val = max(0, min(max_score, score_val))
            except Exception:
                score_val = None
            result["维度评分"][str(key)] = {
                "score": score_val,
                "analysis": "" if analysis_val is None else str(analysis_val),
            }
    else:
        # 否则把除固定字段外的 key 当作维度名
        ignore_keys = {
            "综合评分",
            "综合评分原因",
            "overall_score",
            "overall_reason",
            "score",
            "reason",
            "维度评分",
        }
        dimension_keys = set(data.keys()) - ignore_keys
        for key in dimension_keys:
            value = data.get(key)
            if isinstance(value, dict):
                score_val = value.get("score")
                analysis_val = value.get("analysis") or value.get("desc") or ""
            else:
                score_val = None
                analysis_val = value
            try:
                if score_val is not None:
                    score_val = int(score_val)
                    score_val = max(0, min(max_score, score_val))
            except Exception:
                score_val = None
            result["维度评分"][key] = {
                "score": score_val,
                "analysis": "" if analysis_val is None else str(analysis_val)
            }

    return result


def run_llm_evaluation(
    excel_file_path: str,
    data_columns: List[str],
    evaluation_scene: str,
    scene_desc: str,
    evaluation_metric: str,
    max_score: int,
    score_details: str,
    steps: str,
    api_key: str,
    model_name: str = "glm-4.7",
    file_content: str = "",
    delay_seconds: float = 2.0,
    max_workers: int = 5,
) -> List[Dict[str, Any]]:
    """
    完整的LLM评估流程函数（并发处理）
    
    流程：
    1. 读取Excel文件
    2. 配置提示词
    3. 并发调用LLM处理所有行
    4. 解析评分
    5. 返回结果
    
    Args:
        excel_file_path: Excel文件路径
        data_columns: 数据列列表，如 ["question", "answer", "ref_answer"]
        evaluation_scene: 评估场景
        scene_desc: 场景描述
        evaluation_metric: 评估指标（字符串，描述各个维度）
        max_score: 最大分数
        score_details: 评分标准详情
        steps: 评分步骤
        api_key: LLM API密钥
        model_name: 模型名称，默认 "glm-4.7"
        file_content: 可选的源文件内容（用于上下文）
        delay_seconds: 每次API调用之间的延迟（秒），默认2秒（并发模式下此参数不再使用）
        max_workers: 最大并发线程数，默认5
    
    Returns:
        评估结果列表，每个元素包含：
        {
            "row_index": int,  # 行索引（从1开始，Excel第3行对应row_index=3）
            "question": str,
            "answer": str,
            "prompt": str,  # 实际使用的提示词
            "status": str,  # "success" 或 "failed" 或 "skipped"
            "result": Dict,  # 规范化后的评估结果（成功时）
            "error_message": str,  # 错误信息（失败时）
        }
    """
    results = []
    
    # 1. 读取Excel文件
    if not Path(excel_file_path).exists():
        raise FileNotFoundError(f"Excel文件不存在: {excel_file_path}")
    
    wb = load_workbook(excel_file_path, read_only=True)
    ws = wb.active
    
    # 读取表头
    try:
        header_cells = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    except StopIteration:
        wb.close()
        raise ValueError("Excel文件为空，无法读取表头")
    
    header_row = []
    for cell in header_cells:
        if cell is not None:
            try:
                header_row.append(str(cell).lower())
            except Exception:
                # 处理编码异常
                header_row.append(str(cell).encode('utf-8', 'ignore').decode('utf-8').lower())
    
    # 验证必填列
    required_columns = ["question", "answer"]
    missing_required = [col for col in required_columns if col not in header_row]
    if missing_required:
        wb.close()
        raise ValueError(f"缺少必填列: {', '.join(missing_required)}")
    
    # 验证data_columns中指定的列是否存在
    missing_columns = [col for col in data_columns if col not in header_row]
    if missing_columns:
        wb.close()
        raise ValueError(f"数据集中缺少指定的列: {', '.join(missing_columns)}")
    
    # 2. 配置提示词模板
    prompt_template = _build_evaluation_prompt(
        data_columns=data_columns,
        evaluation_scene=evaluation_scene,
        scene_desc=scene_desc,
        evaluation_metric=evaluation_metric,
        max_score=max_score,
        score_details=score_details,
        steps=steps,
        file_content=file_content,
    )
    
    # 3. 收集所有行数据（标准格式：第1行表头，第2行说明，第3行开始是数据）
    row_data_list = []
    row_index = 3  # Excel行号从3开始（第1行是表头，第2行是说明）
    for row in ws.iter_rows(min_row=3, values_only=True):
        # 构建行数据字典
        row_data = {}
        for idx, cell in enumerate(row):
            if idx < len(header_row):
                row_data[header_row[idx]] = cell
        
        # 准备并发处理的数据元组
        row_data_list.append((
            row_index,
            row_data,
            header_row,
            prompt_template,
            data_columns,
            api_key,
            model_name,
            max_score,
        ))
        row_index += 1
    
    wb.close()
    
    # 4. 使用线程池并发处理所有行
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_process_single_row, row_data_list))
    
    # 5. 按 row_index 排序结果，确保顺序一致
    results.sort(key=lambda x: x["row_index"])
    
    # 6. 返回结果
    return results


if __name__ == "__main__":
    # 从标准输入读取JSON配置
    input_data = json.load(sys.stdin)
    
    # 解析输入参数，提供默认值
    excel_file_path = input_data.get("excel_file_path")
    if not excel_file_path:
        raise ValueError("缺少必需参数: excel_file_path")
    
    data_columns = input_data.get("data_columns", ["question", "answer"])
    evaluation_scene = input_data.get("evaluation_scene", "问答咨询类")
    scene_desc = input_data.get("scene_desc", "基于用户提出的问题，提供精准、有效的回答，涵盖知识解答、信息查询、问题分析等需求。")
    evaluation_metric = input_data.get("evaluation_metric", "- 准确性: 回答内容与问题核心匹配，信息真实可靠；避免错误、模糊或无关内容。\n- 全面性: 完整覆盖问题涉及的关键要点；避免信息缺失、片面回应。\n- 逻辑性: 表述条理清晰、论证合理；避免逻辑混乱、因果不清。")
    max_score = input_data.get("max_score", 10)
    score_details = input_data.get("score_details", "将分值从高到低划分为三档进行赋分，你的打分需要尽可能严格。作为示例，AI助手回复的标准答案（如有）可以给第一档。\n第一档，优秀：非常完美，各方面均严格符合标准，在给定标准答案时此档位代表优于标准答案的回复质量；\n第二档，及格：优缺点并存，在要求的评价标准内整体优点超过缺点；\n第三档，不及格：有重大缺陷，完全背离标准，在实际中不该出现。")
    steps = input_data.get("steps", "1.参照评分原则，仔细阅读并理解用户输入的待评估内容。\n2.识别出表现好的维度以及表现不足的维度。\n3.根据评分原则逐一对每个维度进行赋分，识别出各个维度具体优点和不足。\n4.根据各维度得分及重要性计算综合评分。")
    api_key = input_data.get("api_key")
    if not api_key:
        raise ValueError("缺少必需参数: api_key")
    model_name = input_data.get("model_name", "glm-4-air-250414")
    file_content = input_data.get("file_content", "")
    delay_seconds = input_data.get("delay_seconds", 0.2)
    max_workers = input_data.get("max_workers", 5)

    results = run_llm_evaluation(
        excel_file_path=str(excel_file_path),
        data_columns=data_columns,
        evaluation_scene=evaluation_scene,
        scene_desc=scene_desc,
        evaluation_metric=evaluation_metric,
        max_score=max_score,
        score_details=score_details,
        steps=steps,
        api_key=api_key,
        model_name=model_name,
        file_content=file_content,
        delay_seconds=delay_seconds,
        max_workers=max_workers,
    )
    
    print(f"共处理 {len(results)} 行数据")
    for i, result in enumerate(results, 1):
        print(f"\n第 {i} 行结果:")
        print(f"  状态: {result['status']}")
        if result['status'] == 'success':
            print(f"  综合评分: {result['result']['综合评分']}")
            print(f"  维度评分: {result['result']['维度评分']}")
        else:
            print(f"  错误: {result['error_message']}")
