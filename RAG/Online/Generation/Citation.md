# Citation Accuracy（引用准确性）

[TOC]

## 定义

引用指向的元数据映射是否准确。

比如，模型标注的引用，没有真的指向了支撑这句话的那个 chunk。一个引用可能指向了正确文档的错误段落，也可能指向了一个 re-chunking 后已经不存在的 chunk ID。引用存在不等于引用正确。

解法：工程层面的引用解析数据流组织与元数据管理问题





## 引用失效类别

1. **引用缺失（Missing Citation）**：模型给出了事实性陈述，但未标注任何出处。在非强约束系统里很常见。
2. **幽灵引用（Ghost Citation）**：模型标注的 Chunk ID 在当前向量数据库中不存在。这通常发生在索引重建、re-chunking 之后。这时候，旧的 chunk ID 失效了，但 prompt 里的引用格式没有更新。这是工程层面最容易触发、也最容易被忽略的引用错误。
3. **弱支撑/不相关引用（Unsupported Citation）**：引用指向了真实存在的 Chunk，但该 Chunk 文本与模型断言之间不存在语义蕴含（Entailment）关系。比如，模型说“该 API 的速率限制是每秒 100 次”，引用指向的 chunk 里只写了“该 API 支持批量调用”，完全是两回事。
4. **过度引用（Over-citation）**：一句简单的声明后叠加了大量语义沾边但低价值的引用。过度引用不算严重错误，但会稀释引用的可信度。
5. **粗粒度引用（Doc-level Citation）**：仅标明引用的文档级别如“参见文档 A”，未具体定位到段落级别的 Chunk-level。对于长文档系统，这会极大削弱引用的可验证性。





## Claim-level 评估：粒度引用拆解

做RAG评估，传统的 Answer-level 整体打分（如 1~5 分评分制）在生产环境评估中是不可靠的。一个长文本回答即使 90% 的内容都有据可查，但只要有 10% 涉及核心参数的凭空捏造，系统在业务线就不可用。

因为整体均分会严重掩盖高风险幻觉。



目前工业界更具参考价值的是**Claim-level（原子声明级）评估**，其标准流程包含四个步骤：

#### 第一步，原子声明提取 (Atomic Claim Extraction)。

利用大模型将系统的完整 Answer 拆解为若干条独立的事实性断言。

比如，把“XR-2048 是一款低功耗设备，功耗 150W，支持热插拔”拆成三条：(1) XR-2048 是低功耗设备；(2) 功耗 150W；(3) 支持热插拔。

#### 第二步，语义蕴含判断 (Entailment Judgment)。

针对每一条独立的 Claim，检查检索到的 Context 块中是否存在能完全推导该结论的证据。判断可以通过微调后的 NLI（自然语言推理）模型，或通过高认同度的专家模型（LLM-as-Judge）完成。

#### 第三步，指标量化，统计 supported / unsupported 比例。

Groundedness 分数 = supported claims / total claims.

#### 第四步，关键错误截断 (Critical Error Gating)。

在金融、医疗、法律等高风险业务中，对断言进行分类。一旦涉及关键参数、业务红线的 Claim 被判定为Unsupported，无论整体得分多高，均触发阻断机制。



Groundedness Rubric 可以参考以下标准：

- 1 分：大量声明无依据，关键陈述缺乏证据支撑，存在高风险幻觉
- 2 分：部分声明有证据，但多条声明缺少支撑或过度泛化
- 3 分：大部分声明有支撑，少数次要声明无依据或弱支撑
- 4 分：几乎所有声明都有支撑，少量空白低影响且明确标注了不确定性
- 5 分：所有事实性声明都有证据支撑，证据不明确的地方主动说明了不确定性



评估时的一个关键原则是：**按问题类型分桶统计，不要只看整体平均分**。平均 Groundedness 看起来不错，可能掩盖了某一类查询（比如数值型问题、多条件组合问题）的幻觉率远高于平均水平。

Claim-level 评估中的 entailment 判断，如果用 LLM-as-Judge 来做，涉及 judge prompt 怎么写、temperature 怎么设、打分 variance 怎么控制等一系列校准问题。





## Citation Resolver：三层防御架构

为了在工程流水线上对引用进行闭环校验，可以在模型输出后构建一个**Citation Resolver（引用校验模块）**，实施分层拦截策略。

这是三层递进的链路，每层的成本和覆盖范围不同。



<title>三级阶梯校验机制</title>
<svg viewBox="0 0 1200 800" width="100%" style="display:block;background:#ffffff;font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">
  <defs>
    <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#0891b2"/>
      <stop offset="0.5" stop-color="#6366f1"/>
      <stop offset="1" stop-color="#d97706"/>
    </linearGradient>
    <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0L10 5L0 10z" fill="#94a3b8"/>
    </marker>
  </defs>
  <!-- 标题 -->
  <text x="600" y="46" text-anchor="middle" fill="url(#tg)" font-size="30" font-weight="700">三级阶梯校验：从存在到语义，层层过滤，精准验证</text>
  <text x="600" y="76" text-anchor="middle" fill="#64748b" font-size="17">大量引用在第一层就被过滤，只有通过前两层的才进入第三层</text>
  <!-- 左侧竖排 -->
  <g fill="#475569" font-size="26" font-weight="600">
    <text x="34" y="150" text-anchor="middle">逐</text>
    <text x="34" y="180" text-anchor="middle">层</text>
    <text x="34" y="210" text-anchor="middle">过</text>
    <text x="34" y="240" text-anchor="middle">滤</text>
    <text x="34" y="270" text-anchor="middle">层</text>
    <text x="34" y="300" text-anchor="middle">层</text>
    <text x="34" y="330" text-anchor="middle">递</text>
    <text x="34" y="360" text-anchor="middle">进</text>
  </g>
  <!-- 第 01 层 -->
  <rect x="60" y="110" width="300" height="250" rx="18" fill="#ecfeff" stroke="#0891b2" stroke-width="2"/>
  <circle cx="108" cy="150" r="17" fill="#0891b2" opacity="0.15"/>
  <text x="108" y="155" text-anchor="middle" fill="#0e7490" font-size="14" font-weight="700">01</text>
  <text x="138" y="157" fill="#164e63" font-size="22" font-weight="700">存在性校验</text>
  <line x1="84" y1="178" x2="336" y2="178" stroke="#a5dce5" stroke-width="1"/>
  <text x="84" y="212" fill="#0e7490" font-size="15">检查</text>
  <text x="160" y="212" fill="#334155" font-size="15">检查 chunk ID 是否存在</text>
  <text x="84" y="250" fill="#0e7490" font-size="15">成本</text>
  <text x="160" y="250" fill="#334155" font-size="15">几乎为零</text>
  <text x="84" y="288" fill="#0e7490" font-size="15">覆盖</text>
  <text x="160" y="288" fill="#334155" font-size="15">引用失效</text>
  <!-- 第 02 层 -->
  <rect x="450" y="110" width="300" height="250" rx="18" fill="#f5f3ff" stroke="#7c3aed" stroke-width="2"/>
  <circle cx="498" cy="150" r="17" fill="#7c3aed" opacity="0.13"/>
  <text x="498" y="155" text-anchor="middle" fill="#6d28d9" font-size="14" font-weight="700">02</text>
  <text x="528" y="157" fill="#4c1d95" font-size="22" font-weight="700">Hash 匹配</text>
  <line x1="474" y1="178" x2="726" y2="178" stroke="#d8ccfa" stroke-width="1"/>
  <text x="474" y="212" fill="#6d28d9" font-size="15">检查</text>
  <text x="550" y="212" fill="#334155" font-size="15">检查文本内容是否一致</text>
  <text x="474" y="250" fill="#6d28d9" font-size="15">成本</text>
  <text x="550" y="250" fill="#334155" font-size="15">低</text>
  <text x="474" y="288" fill="#6d28d9" font-size="15">覆盖</text>
  <text x="550" y="288" fill="#334155" font-size="15">内容过期</text>
  <!-- 第 03 层 -->
  <rect x="840" y="110" width="300" height="250" rx="18" fill="#fffbeb" stroke="#d97706" stroke-width="2"/>
  <circle cx="888" cy="150" r="17" fill="#d97706" opacity="0.15"/>
  <text x="888" y="155" text-anchor="middle" fill="#b45309" font-size="14" font-weight="700">03</text>
  <text x="918" y="157" fill="#92400e" font-size="22" font-weight="700">Entailment 校验</text>
  <line x1="864" y1="178" x2="1116" y2="178" stroke="#f2d69a" stroke-width="1"/>
  <text x="864" y="212" fill="#b45309" font-size="15">检查</text>
  <text x="940" y="212" fill="#334155" font-size="15">检查语义蕴含关系</text>
  <text x="864" y="250" fill="#b45309" font-size="15">成本</text>
  <text x="940" y="250" fill="#334155" font-size="15">高</text>
  <text x="864" y="288" fill="#b45309" font-size="15">覆盖</text>
  <text x="940" y="288" fill="#334155" font-size="15">引用不支持</text>
  <!-- 层间箭头 -->
  <line x1="360" y1="235" x2="440" y2="235" stroke="#94a3b8" stroke-width="2" marker-end="url(#ar)"/>
  <line x1="750" y1="235" x2="830" y2="235" stroke="#94a3b8" stroke-width="2" marker-end="url(#ar)"/>
  <!-- 过滤标注 -->
  <text x="405" y="402" text-anchor="middle" fill="#dc2626" font-size="15" font-weight="600">× 大量引用在此被过滤</text>
  <text x="405" y="425" text-anchor="middle" fill="#64748b" font-size="14">（ID 不存在）</text>
  <text x="795" y="402" text-anchor="middle" fill="#dc2626" font-size="15" font-weight="600">× 部分引用在此被过滤</text>
  <text x="795" y="425" text-anchor="middle" fill="#64748b" font-size="14">（内容已变化）</text>
  <text x="990" y="402" text-anchor="middle" fill="#b45309" font-size="16" font-weight="600">通过全部校验 → 有效引用</text>
  <!-- 底部总结 -->
  <rect x="60" y="500" width="300" height="170" rx="16" fill="#f0fdff" stroke="#0891b2" stroke-opacity="0.65" stroke-width="1.5"/>
  <text x="210" y="548" text-anchor="middle" fill="#0e7490" font-size="17" font-weight="700">第一层 · 拦截绝大多数无效引用</text>
  <text x="210" y="582" text-anchor="middle" fill="#334155" font-size="15">成本几乎为零，快速过滤失效 ID</text>
  <rect x="450" y="500" width="300" height="170" rx="16" fill="#f5f3ff" stroke="#7c3aed" stroke-opacity="0.65" stroke-width="1.5"/>
  <text x="600" y="548" text-anchor="middle" fill="#6d28d9" font-size="17" font-weight="700">第二层 · 过滤内容不一致的引用</text>
  <text x="600" y="582" text-anchor="middle" fill="#334155" font-size="15">低成本校验，确保内容未过期</text>
  <rect x="840" y="500" width="300" height="170" rx="16" fill="#fffbeb" stroke="#d97706" stroke-opacity="0.65" stroke-width="1.5"/>
  <text x="990" y="548" text-anchor="middle" fill="#b45309" font-size="17" font-weight="700">第三层 · 语义级严格校验</text>
  <text x="990" y="582" text-anchor="middle" fill="#334155" font-size="15">高成本深度校验，确保引用被支持</text>
</svg>
### 第一层：规则与存在性校验（Existence Check）

这一层，做的是最基本的检查：模型输出的 citation ID 是否指向一个当前存在的 chunk。

这一层听起来简单，但在生产环境中经常出问题。最典型的场景是**索引重建**：知识库的文档更新了，重新做了 chunking 和 embedding，chunk ID 全部变了，但模型的 prompt 模板和 few-shot 示例里还在引用旧的 ID 格式。另一个场景是**文档删除**：某份文档被下线了，但引用它的 chunk ID 还残留在 prompt 历史或缓存里。

可以利用正则提取模型返回的所有 Citation ID，直接与当前的向量库索引或元数据缓存进行命中测试。这一步主要拦截由于 Few-shot 模板陈旧、大语言模型幻觉生成的“伪 ID”。

```
import re
from typing import Dict, List
def extract_citations(answer: str) -> List[str]:
    """提取答案中的引用标记，如 [DOC1], [CHUNK_42]"""
    return re.findall(r"\[(\w+)\]", answer)
def check_citation_existence(citations: List[str], chunk_store: Dict[str, str]) -> dict:
    """校验每个引用 ID 是否存在于当前 chunk 索引中"""
    results = {}
    for cite_id in citations:
        results[cite_id] = cite_id in chunk_store
    valid = sum(1 for v in results.values() if v)
    return {
        "total": len(citations),
        "valid": valid,
        "missing": [k for k, v in results.items() if not v],
        "existence_rate": valid / len(citations) if citations else 0.0
    }
```



### 第二层：元数据 Hash 一致性校验（Hash Matching）

存在性校验只能告诉你 chunk ID 还在，但有时候 chunk 的内容可能已经变了。

一个常见场景：文档做了小幅修订（修正了一个参数值、更新了一个链接），chunk ID 没变，但文本内容已经不同。如果模型的回答是基于旧版本内容生成的，引用虽然“存在”，但指向的内容和生成时不一致。

解决方式是在 chunk 入库时计算并存储文本的 hash 值。每次引用校验时，不仅检查 ID 是否存在，还检查当前 chunk 的 hash 是否和引用时记录的 hash 一致。

这要求在 chunk 的元数据中至少存储：chunk_id、text_hash、doc_id、创建时间、最后更新时间。当检测到 hash 不匹配时，说明引用的证据已经过期，需要标记为 stale citation。



### 第三层：语义蕴含校验漏斗（Semantic Entailment）

前两层解决的是“引用指向的东西还在不在、变了没有”，第三层解决的是“引用指向的内容是否真的支撑模型的声明”。

这是成本最高的一层。需要对每一条 claim-citation 对做语义蕴含判断：cited chunk 的文本是否能推导出这条声明。

实现方式有两种：

- **NLI 模型**：用一个自然语言推理模型判断 (premise=chunk_text, hypothesis=claim) 的关系是 entailment / contradiction / neutral。成本低、速度快，但对复杂推理能力有限。
- **LLM-as-Judge**：用一个 LLM 判断 chunk 是否支撑 claim。能力更强，但每次调用都有推理成本。

工程上的常见做法是分层处理：大部分引用走前两层的规则校验（成本几乎为零），只有通过了前两层的引用才进入第三层的 entailment 校验（控制 LLM 调用量）。对于 critical error 场景（高风险领域），第三层是必须的；对于一般场景，前两层加上抽样 entailment 就够了。



除了以上提到的三种引用本身的正确性，实践中，还有一个经常被忽略的问题：**引用来源过于集中**。

如果检索结果的前五个 chunk 全部来自同一份文档，模型的引用自然也只指向这一份文档。表面上看引用很充分——每句话后面都有 [DOC_A]，但实际上所有证据来自单一来源，缺少交叉验证。

这个问题的根源在检索层。当知识库中某份文档和 query 的相似度远高于其他文档时，top-k 结果会被这份文档的多个 chunk 占据，其他文档的相关 chunk 被挤出候选集。

解决这个问题，我们可以使用Milvus 的 grouping search 在检索阶段解决这个问题。

通过group_by_field参数指定按 doc_id 分组，检索结果会保证每个文档最多贡献指定数量的 chunk，避免让单一文档刷屏：

```
results = client.search(
    collection_name="knowledge_base",
    data=[query_vector],
    anns_field="dense_vector",
    limit=10,
    group_by_field="doc_id",   # 按文档分组
    group_size=2,               # 每个文档最多贡献 2 个 chunk
    output_fields=["content", "doc_id", "chunk_id", "text_hash"]
)
```

以上这段代码的效果是：即使文档 A 的五个 chunk 相似度都很高，检索结果里文档 A 也最多占两个位置，剩下的位置留给其他文档。这从源头上保证了引用来源的多样性。





## 如何用Milvus进一步优化Citation Resolver

构建**Citation Resolver（引用校验模块）时候，**要让这个校验器高效运转，第一层存在性校验需要chunk_id，第二层一致性校验需要text_hash，后续的审计追溯还需要doc_id、updated_at、甚至召回时的权重分数等。这个过程，核心的工程痛点在于**元数据（Metadata）的存取开销**。

如果为了校验引用而另起一套关系型数据库去同步这些元数据，不仅带来了双写一致性问题，还会让校验链路平添多次网络 I/O。

针对这个痛点，可以在 Milvus 中开启**Dynamic Field（动态字段）**特性。

把这些元数据需要和向量一起存储在同一个 collection 中，查询时通过 scalar filter 按 chunk_id 精确匹配：

```
# 批量校验引用的 chunk 是否存在且内容未变
cited_chunk_ids = ["CHUNK_42", "CHUNK_108", "CHUNK_215"]
results = client.query(
    collection_name="knowledge_base",
    filter=f'chunk_id in {cited_chunk_ids}',
    output_fields=["chunk_id", "text_hash", "doc_id", "updated_at"]
)
# 检查存在性和 hash 一致性
found_ids = {r["chunk_id"] for r in results}
missing = [cid for cid in cited_chunk_ids if cid not in found_ids]
```

通过动态字段，我们不需要在 Schema 中显式预定义所有可能用于校验和审计的属性，系统允许在插入向量时，直接注入text_hash、retrieval_rank、citation_count 等字段，查询时直接通过表达式过滤。

这意味着**检索链路和校验链路彻底共享同一套数据载体。从而为我们带来两大优势：**

- **零多表联查成本**：元数据随向量一同被索引、一并被检索出来。校验层通过布尔表达式过滤时，Milvus 的标量索引可以直接在内存中快速阻断。
- **极高的敏捷度**：未来如果校验算法升级，需要引入类似citation_count（引用热度计数）或source_authority（权威度评级）等新指标，研发团队无需下线修改 Collection Schema、无需重构迁移数据，直接在插入和查询时动态读写即可。

只有通过了前两层低成本规则过滤的引用，才会进入第三层**语义蕴含校验漏斗（Semantic Entailment）**。这种分层漏斗设计结合 Milvus 动态字段，能将 90% 以上的无效模型推理（Token 消耗）拦截在纯工程阶段。





## 决策框架

建立完备的 Claim-level 评估与三层引用校验需要投入不可忽视的研发与算力资源。企业应当根据具体的业务场景来决定工程实施的力度：

#### 需要严格评估的场景，通常具备这几个特征：

- 用户会基于 RAG 的答案做决策，而不只是浏览参考。医疗问诊、法律咨询、金融分析——一条错误声明可能导致严重后果
- 系统对外展示了引用标记。一旦系统承诺“有据可查”，你就有责任验证引用是否准确
- 知识库频繁更新，索引经常重建。re-chunking 破坏引用映射的风险持续存在

#### 可以用轻量评估的场景：

- 内部知识库问答，用户是领域专家，有能力自行验证答案正确性
- 答案主要用于辅助参考，不作为最终依据
- 知识库稳定，很少更新，chunk ID 不会频繁变化



对应的工程策略也不同：



严格模式下，每次生成后都跑 citation 三层校验，Groundedness 低于阈值的答案不展示给用户，CI 流水线中设置 critical error gate——只要高风险 bucket 中出现一条 unsupported 的关键声明，就阻断上线。

轻量模式下，只做 citation 存在性校验（成本几乎为零），每周抽样一批生产查询做人工 Groundedness 评估，重点关注用户反馈中的“答案不对”投诉。



决策可以简化成一个判断：**你的 RAG 系统有没有展示引用标记？**如果有，那你至少需要做到 citation 存在性校验和 hash 匹配——这两层成本几乎为零，但能拦住最常见的引用失效。如果连这两层都没有做，那系统展示的每一个引用标记都是未经验证的，它给了用户虚假的信任感。没有验证过的引用，比没有引用更危险。