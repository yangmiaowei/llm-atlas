# 🌺 Agent - 能力视角

[TOC]

## Memory（记忆）

系统怎么保存上下文。

包括：

- conversation history
- vector memory
- episodic memory
- long-term memory
- scratchpad

Memory 在工程里被拆成三块：

① State Management（短期记忆）

- 当前对话
- tool结果
- scratchpad / working state
- agent loop state

👉 本质：**运行时状态**

② Context Engineering（工作记忆 + 压缩）

- prompt assembly
- RAG
- summarization
- context window control
- token budgeting

👉 本质：**“喂给模型什么”**

③ Long-term Memory（长期记忆）

- vector DB
- user profile
- episodic memory
- knowledge base

👉 本质：**外部存储系统**

------

所以：

> memory = state + context + storage 三件事拼起来的系统能力
>  不是一个单独模块

## Planning（规划）

这是 Agent 差异最大的地方。

包括：

- task decomposition
- goal planning
- subtask scheduling
- search
- reasoning

ReAct/ReWOO/ToT 的核心区别其实都在这里。

ReAct：边想边做 Thought -> Action -> Observation 没有全局规划。

ReWOO：先规划，再执行
Plan
  -> Worker1
  -> Worker2
  -> Solver

Tree of Thoughts：搜索多个推理分支 Reasoning Search Algorithm

LLM Compiler：任务 DAG 化 + 并行执行 Query Planner



## Reasoning（推理）



## State（状态流转）

## 调度机制







## Tool use



## Reflection / Feedback（反馈优化）

输出后再修正。

包括：

- Reflexion
- self-critique
- retry
- evaluator
- verifier
- reward model



## Perception（感知）

系统怎么获取信息。

包括：

- 用户输入
- RAG
- Browser
- OCR
- Environment observation
- Tool result



## Action（行动）

系统怎么执行任务。

包括：

- tool call
- code execution
- browser action
- computer use
- shell
- API call

Claude Code/OpenHands/Codex 很多差异其实主要在这里。



## Control Flow（控制流）

包括：

- workflow
- DAG
- FSM
- event loop
- retry
- timeout
- checkpoint
- state transition

LangGraph 本质：State Machine Runtime

CrewAI 本质：Multi-agent orchestration framework



## Coordination（协作）

## Environment（环境）





