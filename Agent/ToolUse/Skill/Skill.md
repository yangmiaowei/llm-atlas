Skill

[TOC]

## 0. Skills 与各个方法适用场景差异对比

| 方法            | 核心区别                                           | 适用场景                                   | 什么时候优先考虑                                    |
| --------------- | -------------------------------------------------- | ------------------------------------------ | --------------------------------------------------- |
| **Prompt**      | 直接向模型提供指令和上下文                         | 简单任务、角色设定、输出格式约束           | 任务简单，直接描述要求就能完成                      |
| **Skill**       | 将特定任务的知识、方法和规范封装起来，按需复用     | 多种任务需要不同的专业知识和执行方法       | 指令复杂、需要复用，或希望按需加载任务知识          |
| **Tool**        | 提供模型可以调用的具体操作能力                     | 查询数据库、调用 API、读写文件、执行代码   | 模型需要获取外部信息或执行实际操作                  |
| **Plugin**      | 将一类外部能力封装为可集成的扩展模块               | 集成第三方服务，集中提供相关工具           | 需要模块化接入和管理一组外部能力                    |
| **MCP**         | 标准化模型应用与外部服务之间的交互协议             | Agent 需要通过统一协议接入不同服务         | 希望降低不同模型应用与外部工具之间的集成成本        |
| **Workflow**    | 显式定义任务步骤、执行顺序和条件分支               | 固定业务流程、标准化多步骤任务             | 流程相对确定，要求执行路径可控、易测试              |
| **Agent**       | 根据目标和执行反馈动态决定下一步行动               | 任务路径不确定，需要自主规划、迭代和调整   | 预先难以确定完整执行路径，需要动态决策              |
| **RAG**         | 检索外部知识，为模型提供相关信息                   | 企业知识问答、文档查询、需要外部知识的任务 | 问题依赖模型参数之外的知识，或需要获取更新的信息    |
| **Fine-tuning** | 通过训练调整模型参数，使模型适应特定任务或行为要求 | 特定任务适配、输出风格统一、行为模式优化   | Prompt 等方法不足以稳定实现目标，且有合适的训练数据 |



## 1. Skill工具定义

Skill是一种可扩展能力模块，每个 skill 封装了一套专门的指令和领域知识，让Agent能够更好地执行特定类型的任务。

Skill 不只是几段提示词，它更接近一个围绕任务组织起来的文件夹。 这个文件夹里可以放 SKILL.md ，也可以放参考文档、脚本、模板、示例、hooks，甚至放会 被后续任务继续读取的数据。Claude 调用 Skill 时，拿到的其实是一套完成任务所需的工作材料。 

把一次性的对话技巧沉淀为可组合、可迁移、可持续迭代的智能体能力。不是“再补一段提示词”，而是把那些已经验证过的做法、容易错的细节、常用脚本和固定流程，一次整理好，后面反复复用。

### Skill 在 Claude Code

实际上，"skill" 在Claude Code框架中也是一个工具。

`skill` 工具定义：

```
Execute a skill within the main conversation

When users ask you to perform tasks, check if any of the available skills match. Skills provide specialized capabilities and domain knowledge.When users reference a "slash command" or "/<something>", they are referring to a skill. Use this tool to invoke it.

How to invoke:
- Set `skill` to the exact name of an available skill (no leading slash). For plugin-namespaced skills use the fully qualified `plugin:skill` form.
- Set `args` to pass optional arguments.

Important:
- Available skills are listed in system-reminder messages in the conversation
- Only invoke a skill that appears in that list, or one the user explicitly typed as `/<name>` in their message. Never guess or invent a skill name from training data; otherwise do not call this tool
- When a skill matches the user's request, this is a BLOCKING REQUIREMENT: invoke the relevant Skill tool BEFORE generating any other response about the task
- NEVER mention a skill without actually calling this tool
- Do not invoke a skill that is already running
- Do not use this tool for built-in CLI commands (like /help, /clear, etc.)
- If you see a <command-name> tag in the current conversation turn, the skill has ALREADY been loaded - follow the instructions directly instead of calling this tool again"
```

逐段拆解：

```
When users ask you to perform tasks, check if any of the available skills match. Skills provide specialized capabilities and domain knowledge.When users reference a "slash command" or "/<something>", they are referring to a skill. Use this tool to invoke it.
```

从这里看出，有两种情况可能会触发Skill：

① Claude 有义务主动匹配。用户不需要显式输入 `/skill-name`，Claude会根据任务的语义自动判断是否需要调用 skill

② 用户显式输入`/skill-name`。这是skill 的触发语法，harness 看到后，实际上就是让Claude 调用 Skill tool。

后面又写了一些重要的规则：

规则①：只用已声明的 skill，避免幻觉

```
- Available skills are listed in system-reminder messages in the conversation
- Only invoke a skill that appears in that list, or one the user explicitly typed as `/<name>` in their message. Never guess or invent a skill name from training data; otherwise do not call this tool
```

从这里我们知道，Skill 列表是动态注入到system-reminder中的。Claude 不能猜测 skill 名字，只能用两个来源：1.中列出的；2. 用户显式输入的 `/<name>`。这防止 Claude 幻觉出不存在的 skill。

规则②：BLOCKING REQUIREMENT（阻塞要求）

```
- When a skill matches the user's request, this is a BLOCKING REQUIREMENT: invoke the relevant Skill tool BEFORE generating any other response about the task
- NEVER mention a skill without actually calling this tool
```

这是一个很强的约束：如果任务匹配某个 skill，Claude 必须先调用 Skill tool，再说任何话。为什么这么设计呢？因为 skill 的指令可能会完全改变 Claude 的行为方式。如果先输出内容再加载skill，之前的输出可能与 skill 指令矛盾。

那么Skill这个Tool做了什么事情呢？实际上，Skill这个工具本质上就是一个运行时注入的 system prompt 片段。它不是代码，不是函数调用，而是一段指令文本，在需要时被注入到对话上下文中，让 Claude临时获得该领域的专业行为模式。

规则③：不能重复调用

```
- Do not invoke a skill that is already running
- Do not use this tool for built-in CLI commands (like /help, /clear, etc.)
- If you see a <command-name> tag in the current conversation turn, the skill has ALREADY been loaded - follow the instructions directly instead of calling this tool again"
```

Skill 注入是有状态的，重复注入会造成上下文冗余。此外，`<command-name>`标签是一个"已加载Skill"的标志，防止无限循环调用。



## 2. Skills 的构成

Skill不是代码逻辑，而是一套关于如何做某类任务的文本。根据官方的规范，Skill的本质就是一个存放在固定位置的文件夹。

| 组成部分    | 说明                                                | 状态   |
| :---------- | :-------------------------------------------------- | :----- |
| SKILL.md    | 核心说明文档 / ，包含元数据（Metadata）和执行步骤。 | ✅ 必选 |
| scripts/    | 可执行的脚本文件（如 Python、Node.js 脚本）。       | ⚪ 可选 |
| references/ | 参考文档、详细指南或长篇幅的上下文背景。            | ⚪ 可选 |
| assets/     | 模板、图片等静态资源文件。                          | ⚪ 可选 |

Agent Skills 通常以标准化的文件夹结构进行组织，示例如下：

```
.joycode/skills/my-skill-folder/ 
├── SKILL.md           # 核心：包含指令和元数据 
├── scripts/           # 可选：辅助脚本 
│   └── process.py 
├── references/        # 可选：详细参考文档 
│   └── guide.md 
├── assets/            # 可选：资源文件
│   └── template.pdf
└── ...  # 其他
```



## 3. SKILL.md标准格式

`SKILL.md` 是技能的核心，由顶部的 YAML 元数据（给 AI 路由看）和下方的 Markdown 主体（给 AI 执行看）组成。

```
# === 必需字段 === 
name: skill-name        # 技能唯一标识，建议使用 kebab-case，仅限小写字母、数字和连字符，且必须与父目录名一致
description: >
   简洁但精确的描述，这是给 Skill Router (路由) 看的。说明：
   1. 这个技能做什么
   2. 什么时候应该使用它
   3. 它的核心价值是什么
# === 可选字段 === 
version: 1.0.0 
author: Your Name 
tags: [database, analysis, sql] 
# 技能标题  
## 概述
 （对技能的详细介绍与背景说明）  
## 工作流程
 自我纠错机制，在 Skill 中要求 AI 验证自己的输出：
 1. 分析代码...
 2. Self-Correction: 再次检查是否遗漏安全漏洞
 3. 生成报告... （详细的步骤说明）  
## 最佳实践
 （经验总结、执行该任务的注意事项）  
## 示例
 （具体的使用案例与输入输出参考）
```

Markdown正文包含目标、详细的步骤、输入输出示例、边界情况处理以及明确的“什么不要做”。官方建议 `SKILL.md` 控制在 500 行以内，更详细的参考材料应拆分到 `references/` 目录下的独立文件中(即“渐进式披露”)。



## 4. 渐进式披露 (Progressive Disclosure)

为了优化 Token 使用和 AI 的上下文窗口，Skills 采用了“渐进式披露”的设计模式：



**第一层：元数据（Metadata）**

• 系统启动时仅加载技能名称（Name）和简要描述（Description）。

• 用于快速识别任务与技能的匹配度。

• 消耗：每个技能仅约 100 个 Token。



**第二层：技能主体（Instructions）**

• 当任务匹配时，加载完整的 `SKILL.md` 文档。

• 用于理解输入参数、使用约束和执行方式。

• 消耗：通常在 1000 - 5000 个 Token 之间。



**第三层：附加资源（Scripts & References）**

• 真正执行具体步骤、需要深度上下文时才加载。

• 包含脚本、配置文件、长篇参考文档等。

• 优势：按需访问，避免浪费上下文空间。



渐进式披露的核心是：**按需加载，分层读取**。

使用渐进式披露的原因：上下文管理问题。

渐进式披露加载：

第一层：只加载每个 Skill 的名称（name）和简短描述（description），大概几百个 Token。目的是告诉模型有哪些可用的技能、每个技能可以解决什么样的问题。此时模型只知道模型“会什么”，还不知道“具体怎么做”，占用的上下文窗口很少。

下面Claude Code框架中Skills描述被注入的位置，具体来说，是在第一个user的system reminder中注入的（而不是全局的system）：

```
"<system-reminder>
The following skills are available for use with the Skill tool:- web-search-plus: Unified search skill with Intelligent Auto-Routing. Uses multi-signal analysis to automatically select between Serper (Google), Tavily (Research), Querit (Multilingual AI Search), Exa (Neural), Perplexity (AI Answers), You.com (RAG/Real-time), and SearXNG (Privacy/Self-hosted) with confidence scoring.- jina-ai: Web reading and searching via Jina AI APIs. Fetch clean markdown from URLs (r.jina.ai), web search (s.jina.ai), or deep multi-step research (DeepSearch).......SKIP: file imports `openai`/other-provider SDK, filename like `*-openai.py`/`*-generic.py`, provider-neutral code, general programming/ML.- init: Initialize a new CLAUDE.md file with codebase documentation- review: Review a pull request- security-review: Complete a security review of the pending changes on the current branch</system-reminder>
```

第二层：当用户发出某个请求，而Claude 发现这个事归某个技能管的时候；或者当用户显式地使用斜杠命令（`/<skill>`）的时候；Claude才会去读取那个skill的 `SKILL.md` 文件。只有在这个时候，那些详细的操作步骤、注意事项才会进入上下文。

那么，SKILL.md文件具体是怎么被注入的，这和"Skill"这个工具又有什么关系呢？（Skill本身就是一个工具）

以Claude Code框架为例：

```
User: 帮我把这个论文做一个中文说明文档docx。

Assistant: Let me run the docx skill to make the doc.<tool_call>Skill<param_key>skill</
param_key><param_value>docx</param_value></tool_call>,

Observation: "Launching skill: docx"

User: {docx 这个技能对应的skill.md} 
```

可以看到，Skill 工具调用后，系统会把该 skill 对应的完整`SKILL.md`作为一条 user 消息注入到对话中，然后 bot 就按这个注入的指令继续执行。所以说，**Skill这个工具本质上就是一个运行时注入的 system prompt 片段。它不是代码，不是函数调用，而是一段指令文本，在需要时被注入到对话上下文中，让 Claude临时获得该领域的专业行为模式。**

第三层：动态加载其它内容

Skill.md的字数也是有限制的，不能太多，否则直接注入到user system reminder里面也会对上下文造成很大的压力。所以，一些很详细的步骤不一定都在 `SKILL.md` 中，可以分开放在`reference`文件夹下面的不同文件中。当Agent识别到用户要做的是某个任务时，才会去查阅相关的reference。（SKILL.md中引用Reference.md）

还有一些处理脚本会放在`scripts/`文件夹下，在 `SKILL.md` 或者`reference`下具体的文件中会告诉模型什么时候应该调用、如何调用这些脚本。Agent只会按照指引执行脚本，而脚本本身的代码是不会塞给模型去读的，因此完全不用担心一个超大代码文件会消耗Token。

SKILL.md中引用若干scripts/下面的脚本，这样模型就可以直接使用了

为什么Skills能够带来这样大的提升呢？

首先，Skill.md中花了很多篇幅写了一些方法论，这个是模型本身不具备的能力。这就像给了它一个很全面的说明文档一样，可以有效防止它踩很多坑，把几十次试错才能积累的经验压缩成一次性的指令注入，让模型从"可能会做"变成"一定做对"。

另外，Skill的`scripts/`文件夹下还可能会有很多的相关脚本，这些如果直接让模型自己来写，很难保证它每次都写得好。因此Skill中先把这些脚本写好，之后告诉它如何使用即可。



## 5. Skills 种类

### 前三类：给模型补知识、补验证、补数据 

#### 1\. Library and API reference

第一类是 library 和 API reference，给模型解释某个库、CLI 或 SDK 在团队内部到底该怎么用，把容易用错的规则和 gotchas 写清楚。

These are skills that explain how to correctly use a library, CLI, or SDKs. They could be both for internal libraries or common libraries that Claude Code sometimes struggles to handle. These skills often included a folder of reference code snippets and a list of gotchas for Claude to avoid when writing a script.

Examples include:

*   `billing-lib` — your internal billing library: edge cases, footguns, etc.
*   `internal-platform-cli` — every subcommand of your internal CLI wrapper with examples on when to use them.
*   `sandbox-proxy` — configuring your org's egress gateway for dev work: which hosts are reachable, how to debug "connection refused" errors, how to add an allowlist entry.

#### 2\. Product verification

第二类是 product verification，负责判断产出有没有真的工作，比如在无头浏览器里完整跑一遍注册和结账流程。这类对输出质量提升最明显，值得让工程师专门花一周打磨。

These are skills that describe how to test or verify that your code is working. They are often paired with playwright, tmux, or other external tools for verification.

Verification skills have had the most measurable impact on Claude’s output quality internally. It can be worth having an engineer spend a week just making your verification skills excellent.

Consider techniques like having Claude record a video of its output so you can see exactly what it tested, or enforcing programmatic assertions on state at each step. These are often done by including a variety of scripts in the skill.

Examples include:

*   `signup-flow-driver` — runs through signup → email verify → onboarding in a headless browser, with hooks for asserting state at each step
*   `checkout-verifier` — drives the checkout UI with Stripe test cards, verifies the invoice actually lands in the right state
*   `tmux-cli-driver` — for interactive CLI testing where the thing you're verifying needs a TTY

#### 3\. Data fetching and analysis

第三类是 data fetching and analysis，连着数据仓库和监控系统，把取数方法、字段约定和常见分析路径封装好，模型不用再去猜表结构和字段名。

These are skills that connect to your data and monitoring stacks. These skills might include libraries to fetch your data with credentials, specific dashboard ids, etc., as well as instructions on common workflows or ways to get data.

Examples include:

*   `funnel-query` — "which events do I join to see signup → activation → paid" plus the table that actually has the canonical user\_id
*   `cohort-compare` — compare two cohorts' retention or conversion, flag statistically significant deltas, link to the segment definitions
*   `grafana` — datasource UIDs, cluster names, problem → dashboard lookup table
*   `datadog` — field reference (@request\_id vs trace\_id), service list, metric prefix conventions

### 中间三类：开始接住团队里的日常流程

#### 4\. Business process and team automation

第四类是 business process and team automation，把重复发生的团队流程压成一个命令就能跑的工作流，比如只输出相对昨天增量的 standup，或固定格式的周报。能看出来，Skill 接住的不只是代码任务，也包括协作任务。

These are skills that automate repetitive workflows into one command. These skills are usually fairly simple instructions but might have more complicated dependencies on other skills or MCPs. For these skills, saving previous results in log files can help the model stay consistent and reflect on previous executions of the workflow.

Examples include:

*   `standup-post` — aggregates your ticket tracker, GitHub activity, and prior Slack → formatted standup, delta-only
*   `create-<ticket-system>-ticket` — enforces schema (valid enum values, required fields) plus post-creation workflow (ping reviewer, link in Slack)
*   `weekly-recap` — merged PRs + closed tickets + deploys → formatted recap post

#### 5\. Code scaffolding and templates

第五类是 code scaffolding and templates，生成那些有固定骨架、但又带着大量自然语言约束的代码，比如新 service 或迁移文件。这正是纯模板引擎覆盖不了的部分。

These are skills that generate framework boilerplates for a specific function in a codebase. You might combine these skills with scripts that can be composed. They are especially useful when your scaffolding has natural language requirements that can’t be purely covered by code. 

Examples include:

*   `new-<framework>-workflow` — scaffolds a new service/workflow/handler with your annotations
*   `new-migration` — your migration file template plus common gotchas
*   `create-app` — new internal app with your auth, logging, and deploy config pre-wired

#### 6\. Code quality and review

第六类是 code quality and review，让代码尽量符合团队的质量标准。典型例子是拉一个“新鲜视角”subagent 来挑错的 adversarial-review ，这类能力还能做成 hook 接进 CI。

These are skills that enforce code quality inside of your org and help review code. These can include deterministic scripts or tools for maximum robustness. You may want to run these skills automatically as part of hooks or inside of a GitHub Action. 

*   `adversarial-review` — spawns a fresh-eyes subagent to critique, implements fixes, iterates until findings degrade to nitpicks
*   `code-style` — enforces code style, especially styles that Claude does not do well by default.
*   `testing-practices` — instructions on how to write tests and what to test.

### 后三类：已经连到生产环境了

#### 7\. CI/CD and deployment

第七类是 CI/CD and deployment，把代码从开发态推到上线态。比如 babysit-pr 会盯完一个 PR 的全过程， deploy- 会把 build、放量、错误率对比和回滚条件串成一条链路。

These are skills that help you fetch, push, and deploy code inside of your codebase. These skills may reference other skills to collect data.

Examples include:

*   `babysit-pr` — monitors a PR → retries flaky CI → resolves merge conflicts → enables auto-merge
*   `deploy-<service>` — build → smoke test → gradual traffic rollout with error-rate comparison → auto-rollback on regression
*   `cherry-pick-prod` — isolated worktree → cherry-pick → conflict resolution → PR with template

#### 8\. Runbooks

第 八 类 是 runbooks ， 入口不是“我要写什么”，而是“现在出了什么症状”。报 警 、Slack thread、request ID 进来，它负责映射到该用哪些工具、查哪些路径，最后给出结构化结论。

These are skills that take a symptom (such as a Slack thread, alert, or error signature), walk through a multi-tool investigation, and produce a structured report.

Examples include:

*   `<service>-debugging` — maps symptoms → tools → query patterns for your highest-traffic services
*   `oncall-runner` — fetches the alert → checks the usual suspects → formats a finding
*   `log-correlator` — given a request ID, pulls matching logs from every system that might have touched it

#### 9\. Infrastructure operations

第九类是 infrastructure operations，处理资源清理、依赖治理和成本排查这类例行操作。这些动作常带破坏性，所以 Skill 里要写清 guardrail，先通知、再确认，最后才真正执行。

These are skills that perform routine maintenance and operational procedures, some of which involve destructive actions that benefit from guardrails. These make it easier for engineers to follow best practices in critical operations.

Examples include:

*   `<resource>-orphans` — finds orphaned pods/volumes → posts to Slack → soak period → user confirms → cascading cleanup
*   `dependency-management` — your org's dependency approval workflow
*   `cost-investigation` — "why did our storage/egress bill spike" with the specific buckets and query patterns



## 6. 设计 Skills 的准则

### 单一职责（一个 Skill 只做一件事）

✅ / query-data / ✅ / generate-chart

❌ / data-tool（范围太大）

最好的 Skill 往往都很聚焦。能清楚落进某一类里的 Skill，通常更稳；试图同时覆盖太多目标的 Skill，反而更容易把模型带乱。

### 精准描述  

WHAT + WHEN

### 命名规范

❌避免模糊、无意义的命名  

✅ / name: jd-me-sender / name: frontend-design / name: pdf-text-extractor

### verification 验证

直接影响结果质量。示例：一个是让 Claude 录下自己测试过程的视频，这样你能清楚看到它到底测了什么。 另一个是在关键节点加程序化断言。状态有没有变化，事件有没有真正落库，最终页面是不是到了目标状态，都尽量不要只靠“看起来差不多”。

### Don’t state the obvious

 ✅ Use pdfplumber

❌ PDF是常见文件格式...

Skill 不是给人看的摘要，它要补的是模型默认拿不到、或者默认容易走偏的信息。 Anthropic 提到过一个前端设计 Skill 的例子。它的价值不在于教 Claude 怎么写前端，而在于补充团队通过和客户反复迭代后沉淀下来的“设计品味”和避坑点，比如少用一些过于套路化的字体和配色选择。

### gotchas

The highest-signal content in any skill is the Gotchas section. These sections should be built up from common failure points that Claude runs into when using your skill. Ideally, you will update your skill over time to capture these gotchas.

真正值得写的，是那些会把模型从默认思路里拽出来的细节：

"The `subscriptions` table is append-only. The row you want is the one with the highest version, not the most recent `created_at`." "This field is called `@request_id` in the API gateway and `trace_id` in the billing service. They're the same value." "Staging returns 200 even when the Stripe webhook didn't actually process. Check `payment_events` for the real state."

### Use the file system and progressive disclosure

```
目录：
queue-debugging/
├─ SKILL.md
├─ stuck-jobs.md
├─ dead-letters.md
├─ retry-storms.md
└─ consumer-lag.md


queue-debugging/SKILL.md：
---
name: queue-debugging
description: Debug stuck, slow, or failing queue workers.
---

# Queue Debugging

Match the symptom below and read the linked file for investigation steps.

| Symptom | Read |
| ---- | ---- |
| Jobs sit pending, never run | stuck-jobs.md |
| Messages in DLQ, no retries | dead-letters.md |
| Same job retried in a loop | retry-storms.md |
| Queue depth keeps climbing | consumer-lag.md |
```

可以创建文件夹，存放参考资料、模板、脚本、示例等，分目录放好，让 Claude 需要时再去取。

### Skill 不要写太死

需要给 Claude 关键规则，但也要给它足够的适应空间， 不然 Skill 一复用，就容易在别的具体情境里卡住。

### setup 要提前想好

```
---
name: standup-post
description: Post your daily standup.Triggers on "standup","daily".
---

## Your config
!`cat ${CLAUDE_SKILL_DIR}/config.json 2>/dev/null || echo "NOT_CONFIGURED"`

## Instructions
If the config above is NOT_CONFIGURED, ask the user:
- Which Slack channel?
- Paste a sample standup you liked
Then write the answers to ${CLAUDE_SKILL_DIR}/config.json.

Otherwise, post to the saved channel using the saved format.
```

很多 Skill 真跑起来时，会缺一些来自用户的上下文，比如 Slack 要发到哪个频道。 原文建议把这类配置放进 config.json 。如果配置还没建好，Claude 就先问用户；如果需要结构化、多选式提问，还可以直接调用 AskUserQuestion 工具。

### Write descriptions for the model, not for humans

```
---❌
name: babysit-pr
description: A comprehensive tool for
monitoring pull request status across
the development lifecycle.
---


---✅
name: babysit-pr
description: Monitors a PR until it
merges. Trigger on 'babysit',
'watch CI', 'make sure this lands'.
---
```

Claude Code 一开局会先扫描所有 Skill 的名称和 description，再判断这次请求有没有可用 Skill。 所以 description 不是摘要，而是触发条件说明。用户可能会说什么关键词，会上传什么文件，什么场景下应该激活这个 Skill，都应该直接写进去。像“babysit”这种触发词，就应该直接出现在description里。

### Help Claude remember

很多 Skill 一开始只是几行说明，越用越多之后，最先长出来的就是记忆、脚本和 hooks 这三样。 先说记忆。像 standup-post 这种 Skill，可以把每次输出都记进 standups.log ，下次运行时先读历史，再判断今天和昨天相比到底变了什么。 这种记忆可以很简单，用 append-only 文本或 JSON 就够了；也可以复杂一点，直接用 SQLite。也可以用 ${CLAUDE_PLUGIN_DATA} 环境变量，拿到一个稳定的持久化目录来存这些数据。

### Store scripts and generate code

能给 Claude 的最强工具之一，其实就是代码本身。 如果你把常用的数据抓取函数、分析函数或者操作脚本预先放进去，Claude 就不用每次从零重写样板代码，而是把更多回合花在“怎么编排”和“下一步做什么”上。 

### Use on-demand hooks 

它们只在 Skill 被调用时生效，而且只在当前会话里存在。 

Skills can include hooks that are only activated when the skill is called, and that only last for the duration of the session. Use this for more opinionated hooks that you don’t want to run all the time, but are extremely useful sometimes.

For example:

*   `/`**`careful`** — blocks rm -rf, DROP TABLE, force-push, kubectl delete via PreToolUse matcher on Bash. You only want this when you know you're touching prod — having it always on would drive you insane.
*   `/`**`freeze`** — blocks any Edit/Write that's not in a specific directory. Useful during debugging: "I want to add logs but I keep accidentally 'fixing' unrelated code.”



## 7. 在项目中创建和使用 Skill

### 7.1 AI编程工具使用Skills

不同的 AI 编程工具对 Skills 目录的位置有不同的默认约定：

| 工具名称    | 默认目录位置 (全局或项目级)                      |
| :---------- | :----------------------------------------------- |
| Claude Code | ~/.claude/skills/ / 或项目级 / .claude/skills/   |
| Cursor      | ~/.cursor/skills/ / 或项目级 / .cursor/skills/   |
| OpenCode    | ~/.opencode/skills/ / 或 / .opencode/skills/     |
| joycode     | ~/.joycode/skills/ / 或项目级 / .joycode/skills/ |

推荐使用 openskills 在不同AI工具和项目中进行skills同步：

```
# 1. 安装“连接器” openskills 
npm install -g openskills 
# 2. 进货“技能包”, 默认 project-local (./.agent/skills). Use --global for ~/.agent/skills. 
openskills install anthropics/skills --global 
# 3. 注入灵魂（关键！）进入对应目录后执行，会生成一个AGENTS.md文件，让你的AI看见技能 
openskills sync
```



### 7.2 openclaw 使用skills

**步骤1：通过ClawHub安装Word文档生成技能插件**

OpenClaw的扩展功能均通过Skills实现，Word生成插件需从官方技能市场ClawHub一键安装。打开终端（PowerShell或CMD命令提示符），运行以下命令安装官方Word文档生成技能：

```
# 安装最新版Word文档生成技能 
npx clawhub@latest install word-docx
```

技能安装完成后会自动热重载生效，无需手动重启 OpenClaw。



**步骤2：启用技能并关联至智能体**

安装完成后，需要将word-docx技能启用并绑定到你的OpenClaw智能体，才能正常调用。

① 打开智能体配置文件：notepad $env:USERPROFILE.openclaw\agents\assistant-agent.yaml

② 在文件中找到skills:配置项，添加word-docx技能：

```
skills:
   - word-docx   # 新增Word文档生成技能
   - filesystem
   - websearch   # 保留你已启用的其他技能
```

③ 配置修改后，需要重启OpenClaw Gateway使设置生效。



**步骤3：验证插件安装与启用状态**

执行命令检查Word生成技能是否正常可用，确认状态为Ready/active即为成功。

```
# 查看所有已安装的技能列表 openclaw skills list
# 单独查看word-docx技能详情 openclaw skills info word-docx
```

在输出结果中，可看到word-docx技能信息、版本、状态及支持功能（创建文档、编辑内容、设置格式、导出文件等）。



## 8. Skill 的分发和治理

There are two ways you might want to share skills with others:

*   check your skills into your repo (under `./.claude/skills`)
*   make a **plugin** and have a Claude Code Plugin marketplace where users can upload and install plugins

For smaller teams working across relatively few repos, checking your skills into repos works well. But every skill that is checked in also adds a little bit to the context of the model. As you scale, an internal plugin marketplace allows you to distribute skills and let your team decide which ones to install, as well as include a setup flow.



## 9. coding agent skills 示例：superpower

Superpowers不是一个Skill，而是一整套给 Coding Agent使用的技能框架和开发方法论。

它解决的问题：普通的AI编程工具经常急于写代码却缺乏系统性，经常拿到用户的需求之后就开始写代码，不问需求、不做设计、不写测试，写完了我们还得花大量时间 Review 和修 Bug。Superpowers可以让AI编程助手遵循标准化软件工程流程，让它先想清楚再动手。

Superpowers 的核心是一套可组合的Skills，装好之后会自动触发。其具备的14 个内置技能如下所示：

| 类别   | 技能                           | 干啥的                     |
| :----- | :----------------------------- | :------------------------- |
| 测试   | test-driven-development        | 红绿循环 TDD，附反模式参考 |
| 调试   | systematic-debugging           | 4 阶段根因分析             |
|        | verification-before-completion | 确保真的修好了             |
| 协作   | brainstorming                  | 苏格拉底式需求对话         |
|        | writing-plans                  | 详细实现计划               |
|        | executing-plans                | 分批执行+人工检查点        |
|        | dispatching-parallel-agents    | 并发子 Agent 工作流        |
|        | subagent-driven-development    | 两阶段 Review 的快速迭代   |
|        | requesting-code-review         | 提交前自检清单             |
|        | receiving-code-review          | 响应 Review 反馈           |
| Git    | using-git-worktrees            | 并行开发分支（互不干扰）   |
|        | finishing-a-development-branch | 合并/PR/丢弃决策           |
| 元技能 | writing-skills                 | 教 AI 怎么创建新技能       |
|        | using-superpowers              | 技能系统使用入门           |

整个工作流：

（1） 当会话启动时，会读取 `skills/using-superpowers/SKILL.md`的全文，并把它包在 `<EXTREMELY_IMPORTANT>`标签里，并且注入到会话的上下文中。这个的目的就是告诉 agent，它有 superpowers，在做任何事之前必须先检查是否有相关的 skill。

（2）调度层（using-superpowers Skill）的规则是：在任何回复或行动之前，先调用相关的 skill。它还定义了优先级，比如"Let's build X" 会先触发 `brainstorming`这个skill；"Fix this bug" 会先触发`systematic-debugging`这个skill。 并且还有一个"Red Flags"反思表，当 agent 想跳过 skill 时（比如说"这太简单了"、"让我先看看代码"），会强制它停下来检查。

（3）技能层（各个 SKILL.md）中，不仅有我们之前说的`name` ，`description` ，以及详细的检查清单、流程图、约束规则等信息，还包括对其他 skill 的显式引用（比如 在brainstorming 结束后调用 writing-plans）。每个 skill 的 SKILL.md 里明确写了下一步调用哪个skill，agent读到这段指令就会去调用下一个，就像接力赛一样。也就是说，不同skill的合作不是靠外部调度器，而是靠每个skill自身。

使用superpower效果：

当用户提出问题，它不会直接写代码，而是会先退后一步，先理清需求，并且把设计文档分段给用户看。设计确认后，它会把工作拆成 2-5 分钟一个的小任务。每个任务都精确到改哪个文件、写什么代码、怎么验证。（用作者 Jesse Vincent 的话说，“清晰到一个充满热情但品味堪忧、没有判断力、不了解项目背景、还讨厌写测试的初级工程师都能跟着做”）。

之后，它会为每个任务派出一个子 Agent 去实现，完成后自动做两轮 Review（规格合规 + 代码质量），然后继续下一个。整个实现过程强制执行 RED-GREEN-REFACTOR 测试驱动开发，即先写一个失败的测试（RED），然后写刚好让测试通过的代码（GREEN）、重构优化（REFACTOR），之后再提交。



## 10. Skill 改进工作

#### WikiSkill

https://arxiv.org/pdf/2608.27454

在经验与技能之间引入结构化知识层，让失败记录也能指导下一轮改进。

#### SKILL.state：把技能执行从聊天记录改成状态机

https://arxiv.org/pdf/2608.26263

用显式状态承接执行信息，减少历史对话反复进入上下文的负担。



## 八、参考链接

1. Anthropic官方 Skills 仓库：https://github.com/anthropics/skills

2. Skills 排行榜：[skills.sh](https://skills.sh/)

3. AI 技能市场： [SkillsMP.com](https://skillsmp.com/)

4. Anthropic Docs：https://code.claude.com/docs/zh-CN/skills

5. https://claude.com/resources/articles/lessons-from-building-claude-code-how-we-use-skills
