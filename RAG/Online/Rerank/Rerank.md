# Rerank

[TOC]



对初步检索结果做精排。

```
# 使用 sentence-transformers 中的 Cross-Encoder 进行重排序
from sentence_transformers import CrossEncoder

# 加载预训练的重排序模型
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# 初步检索得到的文档列表和原始查询
query = "企业如何实施数据治理？"
retrieved_docs = [
    "文档A内容：数据治理框架包括组织、政策、流程...",
    "文档B内容：IT技术选型指南...",
    "文档C内容：数据治理的核心是确保数据质量与安全...",
]

# 构建 query-doc 对用于评分
pairs = [[query, doc] for doc in retrieved_docs]

# 预测相关性分数
scores = reranker.predict(pairs)

# 将分数与文档绑定并排序
ranked_results = sorted(zip(retrieved_docs, scores), key=lambda x: x[1], reverse=True)

print("重排序后结果：")
for doc, score in ranked_results:
    print(f"分数: {score:.4f} | 文档摘要: {doc[:80]}...")
```





## 作用

Rerank 的核心作用是对初步检索得到的候选文档进行重新评分与排序，提高最终进入 LLM 上下文的证据相关性。

- 改善候选文档的排序质量： 初始检索通常优先保证召回效率与候选覆盖率，但检索分数高不代表文档一定最能回答当前问题。Rerank 通过更细致地评估 Query 与 Document 的相关性，将更有价值的候选排在前面。
- 统一不同检索方式的结果排序： RAG 可以使用多种检索方法获取候选文档。这些方法的评分机制和排序依据不同，可以通过 Rerank 对合并后的候选集进行统一的相关性评估。
- 弥补单一向量检索的局限： Embedding 模型将文本压缩为向量，再通过向量相似度进行检索，难以完整表达 Query 与 Document 之间的细粒度交互。即使相关文档已经被召回，其排名仍可能受到模型能力、领域差异、语言特点和文本粒度等因素影响。Rerank 可以进一步判断候选文档与当前查询的实际相关性。
- 利用更强的相关性判断能力： 例如，Cross-Encoder 将 Query 与候选 Document 联合输入模型，通过跨文本交互计算相关性分数。由于每个候选都需要进行联合推理，其计算成本通常高于向量相似度计算，因此一般用于对初步召回的候选集进行精排，而非直接扫描整个文档库。





## 为什么向量检索不够准？

bi-encoder vs cross-encoder

#### embedding 用的 bi-encoder

**（双塔，分开编码）+ 向量 DB [召回] （recall高）10 ms**

问题和文档分别编码成向量，再算相似度。问题和文档在编码时互不知道对方的存在，所以只能算 "大概相关"。适合大规模候选集的高效召回。

#### reranker 用的 cross-encoder

**（交互式，合并编码）[精排]（precision高）100～200 ms**

把问题和文档拼在一起送进模型，模型可以同时看到双方内容，做更精确的相关性判断。

代价是慢 ，Cross-Encoder 不能预计算，每个 (问题，文档) 对都要过一遍模型，所以只能对少量候选做精排。





<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 850" width="100%" style="display:block;background:#ffffff;font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">
  <defs>
    <marker id="biArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#3478D4"/></marker>
    <marker id="crossArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#159B78"/></marker>
    <marker id="neutralArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#7C64BD"/></marker>
    <linearGradient id="biHead" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#EAF3FF"/><stop offset="100%" stop-color="#D8E8FF"/></linearGradient>
    <linearGradient id="crossHead" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#E5F8F1"/><stop offset="100%" stop-color="#D0F0E4"/></linearGradient>
  </defs>
  <rect x="0" y="0" width="1200" height="850" fill="#FFFFFF"/>
  <text x="600" y="38" text-anchor="middle" font-size="27" font-weight="750" fill="#1D3557">Bi-Encoder vs Cross-Encoder</text>
  <text x="600" y="64" text-anchor="middle" font-size="14" fill="#64748B">两种文本相关性建模方式：独立编码 vs 联合编码</text>
  <rect x="24" y="84" width="568" height="54" rx="12" fill="#EAF2FF" stroke="#C5DAFC"/>
  <rect x="608" y="84" width="568" height="54" rx="12" fill="#E5F7EF" stroke="#B8E7D4"/>
  <text x="308" y="108" text-anchor="middle" font-size="22" font-weight="750" fill="#245DA9">Bi-Encoder · 双编码器</text>
  <text x="308" y="127" text-anchor="middle" font-size="13" fill="#4C6F9F">分别编码 → 向量相似度</text>
  <text x="892" y="108" text-anchor="middle" font-size="22" font-weight="750" fill="#147655">Cross-Encoder · 交叉编码器</text>
  <text x="892" y="127" text-anchor="middle" font-size="13" fill="#41846D">联合编码 → 相关性打分</text>
  <rect x="42" y="153" width="532" height="51" rx="10" fill="#F3F7FF" stroke="#B8D1F5" stroke-width="1.5"/>
  <text x="308" y="174" text-anchor="middle" font-size="14" font-weight="700" fill="#245DA9">Query</text>
  <text x="308" y="192" text-anchor="middle" font-size="16" fill="#29496F">如何申请退款？</text>
  <rect x="42" y="216" width="532" height="51" rx="10" fill="#F0FAF5" stroke="#B8E7D4" stroke-width="1.5"/>
  <text x="308" y="237" text-anchor="middle" font-size="14" font-weight="700" fill="#147655">Document</text>
  <text x="308" y="255" text-anchor="middle" font-size="16" fill="#286A54">退款申请流程是什么？</text>
  <path d="M308 204 V278" fill="none" stroke="#3478D4" stroke-width="2.5" marker-end="url(#biArrow)"/>
  <path d="M308 267 V278" fill="none" stroke="#159B78" stroke-width="2.5" marker-end="url(#crossArrow)"/>
  <rect x="42" y="285" width="253" height="81" rx="12" fill="url(#biHead)" stroke="#9FC2F4" stroke-width="1.5"/>
  <rect x="321" y="285" width="253" height="81" rx="12" fill="url(#biHead)" stroke="#9FC2F4" stroke-width="1.5"/>
  <text x="168" y="312" text-anchor="middle" font-size="18" font-weight="700" fill="#245DA9">Query Encoder</text>
  <text x="168" y="335" text-anchor="middle" font-size="14" fill="#426B9E">独立编码 Query</text>
  <text x="168" y="354" text-anchor="middle" font-size="12" fill="#6380A9">不读取当前候选文档</text>
  <text x="448" y="312" text-anchor="middle" font-size="18" font-weight="700" fill="#245DA9">Document Encoder</text>
  <text x="448" y="335" text-anchor="middle" font-size="14" fill="#426B9E">独立编码 Document</text>
  <text x="448" y="354" text-anchor="middle" font-size="12" fill="#6380A9">可预先计算并缓存向量</text>
  <path d="M168 366 V387" fill="none" stroke="#3478D4" stroke-width="2" marker-end="url(#biArrow)"/>
  <path d="M448 366 V387" fill="none" stroke="#3478D4" stroke-width="2" marker-end="url(#biArrow)"/>
  <text x="168" y="404" text-anchor="middle" font-size="15" font-weight="700" fill="#245DA9">Query Embedding · q</text>
  <text x="448" y="404" text-anchor="middle" font-size="15" font-weight="700" fill="#245DA9">Document Embedding · d</text>
  <g stroke="#A9C8F3" stroke-width="1">
    <rect x="53" y="414" width="57" height="29" rx="4" fill="#EAF2FF"/><rect x="112" y="414" width="57" height="29" rx="4" fill="#EAF2FF"/><rect x="171" y="414" width="57" height="29" rx="4" fill="#EAF2FF"/><rect x="230" y="414" width="57" height="29" rx="4" fill="#EAF2FF"/>
    <rect x="333" y="414" width="57" height="29" rx="4" fill="#EAF2FF"/><rect x="392" y="414" width="57" height="29" rx="4" fill="#EAF2FF"/><rect x="451" y="414" width="57" height="29" rx="4" fill="#EAF2FF"/><rect x="510" y="414" width="57" height="29" rx="4" fill="#EAF2FF"/>
  </g>
  <g font-size="12" text-anchor="middle" fill="#245DA9">
    <text x="81" y="433">0.21</text><text x="140" y="433">−0.43</text><text x="199" y="433">0.18</text><text x="258" y="433">…</text>
    <text x="361" y="433">0.19</text><text x="420" y="433">−0.41</text><text x="479" y="433">0.20</text><text x="538" y="433">…</text>
  </g>
  <path d="M168 443 V462 H308 V477" fill="none" stroke="#3478D4" stroke-width="2" stroke-linejoin="round" marker-end="url(#biArrow)"/>
  <path d="M448 443 V462 H308" fill="none" stroke="#3478D4" stroke-width="2" stroke-linejoin="round"/>
  <rect x="112" y="481" width="392" height="53" rx="11" fill="#F1EBFF" stroke="#C7B3F0" stroke-width="1.5"/>
  <text x="308" y="503" text-anchor="middle" font-size="17" font-weight="700" fill="#6941A5">Cosine Similarity / Dot Product</text>
  <text x="308" y="522" text-anchor="middle" font-size="14" fill="#7657A6">sim(q, d) · 向量空间中的相似度</text>
  <path d="M308 534 V555" fill="none" stroke="#7C64BD" stroke-width="2.5" marker-end="url(#neutralArrow)"/>
  <rect x="112" y="559" width="392" height="45" rx="10" fill="#F1EBFF" stroke="#C7B3F0" stroke-width="1.5"/>
  <text x="308" y="587" text-anchor="middle" font-size="17" font-weight="700" fill="#6941A5">候选文档排序 / Top-K 召回</text>
  <rect x="42" y="618" width="532" height="97" rx="11" fill="#F5F8FE" stroke="#D3E0F3"/>
  <text x="60" y="643" font-size="15" font-weight="700" fill="#245DA9">核心机制</text>
  <text x="60" y="666" font-size="14" fill="#405B7D">• 两段文本在编码时互不交互</text>
  <text x="60" y="687" font-size="14" fill="#405B7D">• 可复用文档向量，适合大规模 ANN 检索</text>
  <text x="60" y="706" font-size="13" fill="#64748B">优势：吞吐高、易于建立向量索引</text>
  <rect x="626" y="153" width="532" height="51" rx="10" fill="#F3F7FF" stroke="#B8D1F5" stroke-width="1.5"/>
  <text x="892" y="174" text-anchor="middle" font-size="14" font-weight="700" fill="#245DA9">联合输入 · Query + Document</text>
  <text x="892" y="193" text-anchor="middle" font-size="15" fill="#29496F">[CLS] Query Tokens [SEP] Document Tokens [SEP]</text>
  <path d="M892 204 V225" fill="none" stroke="#159B78" stroke-width="2.5" marker-end="url(#crossArrow)"/>
  <rect x="626" y="229" width="532" height="77" rx="12" fill="url(#crossHead)" stroke="#9BD9C2" stroke-width="1.5"/>
  <text x="892" y="254" text-anchor="middle" font-size="19" font-weight="700" fill="#147655">同一个 Transformer Encoder</text>
  <text x="892" y="278" text-anchor="middle" font-size="14" fill="#286A54">Self-Attention：两个文本的 Token 可相互交互</text>
  <text x="892" y="296" text-anchor="middle" font-size="12" fill="#41846D">逐层形成依赖于 Query–Document 配对的上下文表示</text>
  <path d="M892 306 V326" fill="none" stroke="#159B78" stroke-width="2.5" marker-end="url(#crossArrow)"/>
  <rect x="626" y="330" width="532" height="190" rx="12" fill="#F5FBF8" stroke="#B8E7D4" stroke-width="1.5"/>
  <text x="892" y="354" text-anchor="middle" font-size="16" font-weight="700" fill="#147655">跨文本注意力交互 · 概念示意</text>
  <text x="740" y="377" text-anchor="middle" font-size="13" font-weight="700" fill="#245DA9">Query Tokens</text>
  <text x="1045" y="377" text-anchor="middle" font-size="13" font-weight="700" fill="#147655">Document Tokens</text>
  <g stroke="#FFFFFF" stroke-width="2">
    <rect x="665" y="389" width="35" height="22" rx="3" fill="#8DB7F3"/><rect x="702" y="389" width="35" height="22" rx="3" fill="#D4E4FB"/><rect x="739" y="389" width="35" height="22" rx="3" fill="#A8C9F7"/><rect x="776" y="389" width="35" height="22" rx="3" fill="#E1EDFC"/>
    <rect x="665" y="413" width="35" height="22" rx="3" fill="#D4E4FB"/><rect x="702" y="413" width="35" height="22" rx="3" fill="#79A9EF"/><rect x="739" y="413" width="35" height="22" rx="3" fill="#E1EDFC"/><rect x="776" y="413" width="35" height="22" rx="3" fill="#A8C9F7"/>
    <rect x="665" y="437" width="35" height="22" rx="3" fill="#A8C9F7"/><rect x="702" y="437" width="35" height="22" rx="3" fill="#E1EDFC"/><rect x="739" y="437" width="35" height="22" rx="3" fill="#79A9EF"/><rect x="776" y="437" width="35" height="22" rx="3" fill="#D4E4FB"/>
  </g>
  <path d="M820 400 H853" fill="none" stroke="#159B78" stroke-width="2.5" marker-end="url(#crossArrow)"/>
  <path d="M853 448 H820" fill="none" stroke="#159B78" stroke-width="2.5" marker-end="url(#crossArrow)"/>
  <g stroke="#FFFFFF" stroke-width="2">
    <rect x="870" y="389" width="35" height="22" rx="3" fill="#D0F0E4"/><rect x="907" y="389" width="35" height="22" rx="3" fill="#68C7A5"/><rect x="944" y="389" width="35" height="22" rx="3" fill="#E2F6EE"/><rect x="981" y="389" width="35" height="22" rx="3" fill="#A2DEC7"/>
    <rect x="870" y="413" width="35" height="22" rx="3" fill="#A2DEC7"/><rect x="907" y="413" width="35" height="22" rx="3" fill="#D0F0E4"/><rect x="944" y="413" width="35" height="22" rx="3" fill="#68C7A5"/><rect x="981" y="413" width="35" height="22" rx="3" fill="#E2F6EE"/>
    <rect x="870" y="437" width="35" height="22" rx="3" fill="#E2F6EE"/><rect x="907" y="437" width="35" height="22" rx="3" fill="#A2DEC7"/><rect x="944" y="437" width="35" height="22" rx="3" fill="#D0F0E4"/><rect x="981" y="437" width="35" height="22" rx="3" fill="#68C7A5"/>
  </g>
  <path d="M740 465 V478 H1044 V465" fill="none" stroke="#159B78" stroke-width="1.8" stroke-dasharray="4 4"/>
  <text x="892" y="495" text-anchor="middle" font-size="13" fill="#286A54">注意力权重随输入、层与注意力头而变化</text>
  <text x="892" y="512" text-anchor="middle" font-size="12" fill="#64748B">局部概念示意，非完整注意力矩阵</text>
  <path d="M892 520 V540" fill="none" stroke="#159B78" stroke-width="2.5" marker-end="url(#crossArrow)"/>
  <rect x="704" y="544" width="376" height="47" rx="10" fill="#E8F7F0" stroke="#A9DDC8" stroke-width="1.5"/>
  <text x="892" y="564" text-anchor="middle" font-size="16" font-weight="700" fill="#147655">模型输出头</text>
  <text x="892" y="581" text-anchor="middle" font-size="12" fill="#41846D">例如分类头或单分数回归头</text>
  <path d="M892 591 V612" fill="none" stroke="#7C64BD" stroke-width="2.5" marker-end="url(#neutralArrow)"/>
  <rect x="704" y="616" width="376" height="43" rx="10" fill="#F1EBFF" stroke="#C7B3F0" stroke-width="1.5"/>
  <text x="892" y="643" text-anchor="middle" font-size="17" font-weight="700" fill="#6941A5">Relevance Score · 相关性分数</text>
  <rect x="626" y="674" width="532" height="97" rx="11" fill="#F2FAF6" stroke="#C5E8D9"/>
  <text x="644" y="699" font-size="15" font-weight="700" fill="#147655">核心机制</text>
  <text x="644" y="722" font-size="14" fill="#286A54">• Query 与 Document 在 Transformer 内直接交互</text>
  <text x="644" y="743" font-size="14" fill="#286A54">• 每个候选对都需单独推理，难以预先缓存配对分数</text>
  <text x="644" y="762" font-size="13" fill="#64748B">优势：细粒度匹配能力强，适合候选集精排</text>
  <rect x="24" y="785" width="1152" height="49" rx="11" fill="#F3F5F9" stroke="#DDE3EC"/>
  <text x="600" y="805" text-anchor="middle" font-size="16" font-weight="750" fill="#334155">典型 RAG 流程：Bi-Encoder / 其他检索器召回候选 → Cross-Encoder 重排序</text>
  <text x="600" y="824" text-anchor="middle" font-size="13" fill="#64748B">相似度分数与重排序分数的尺度不一定相同；示意数值不代表真实模型输出</text>
</svg>



bi-encoder 和 cross-encoder 不是替代关系。embedding 不会被 reranker 取代 — cross-encoder 没法在百万文档里 10ms 跑一遍。它们是架构性互补：bi-encoder 不准但快 — 不交互所以不准；cross-encoder 准但慢 — 每对都要算。





## Rerank 常见方法

### 1. Cross-Encoder Reranking（主流方法）

**原理：** 将 Query 与每个候选 Document / Chunk 联合输入模型，直接预测相关性分数，再按分数排序。由于模型可以建模 Query 与 Document 之间的细粒度交互，通常比直接计算两个独立 Embedding 的相似度更适合候选集精排。

- **常见模型：**
  - BGE Reranker：如 `bge-reranker-v2-m3`。
  - Cohere Rerank：如 `rerank-v3.5`、更新版本的 Rerank 系列。
  - MS MARCO Cross-Encoder：如 `cross-encoder/ms-marco-MiniLM-L-6-v2`。
  - 其他模型：如 `mxbai-rerank` 系列。
- **优点：** 相关性判断细致，适合对初步检索结果进行精排。
- **缺点：** 每个候选文档都需要与 Query 联合计算，延迟和推理成本通常高于向量相似度计算。
- **适用场景：** 通用 RAG、知识库问答、混合检索后的候选集精排。

### 2. Late-Interaction Reranking（细粒度交互）

**原理：** 分别编码 Query 与 Document 的多个 Token 向量，再通过 MaxSim 等交互机制计算相关性，而不是将整段文本压缩为单个向量，也不必像 Cross-Encoder 一样对每对文本进行完整的联合编码。

- **代表方法：** ColBERT、ColBERTv2；BGE-M3 也支持多向量的 ColBERT 式交互。
- **优点：** 保留 Token 级别的细粒度匹配信息；文档向量可预先计算，适合在大规模检索中复用。
- **缺点：** 需要存储多向量表示，索引和检索计算通常比单向量检索更复杂。
- **适用场景：** 大规模检索、需要精细词项匹配、希望兼顾检索效率与相关性质量的场景。

### 3. LLM-based Reranking（大模型重排序）

**原理：** 通过提示词让 LLM 根据 Query 和候选文档判断相关性，可以输出分数、相关性等级或排序列表。

- **实现方式：** 逐个文档打分、成组比较，或采用 listwise 排序。
- **优点：** 可自定义相关性标准，适合复杂约束、多维度判断和推理型查询。
- **缺点：** 推理成本和延迟可能较高；输出稳定性、评分一致性及长候选列表的处理效果需要评估。
- **适用场景：** 复杂查询、高价值问答、专用领域评估，以及需要灵活定义排序规则的场景。

### 4. Learning-to-Rank（学习排序）

**原理：** 利用标注的 Query–Document 相关性数据训练排序模型，综合多个特征预测文档的排序位置或相关性。

- **常见算法：** LambdaMART、基于梯度提升树的排序模型，以及其他 Pointwise、Pairwise、Listwise 排序方法。
- **常见特征：** BM25 分数、Embedding 相似度、Reranker 分数、关键词匹配、文档类型、时效性和权威性等。
- **优点：** 可结合业务特征和人工标注数据优化排序，推理成本可控。
- **缺点：** 需要构建训练数据和特征体系，并持续评估、维护模型。
- **适用场景：** 搜索平台、企业知识检索，以及具有稳定标注数据和明确业务排序目标的系统。

### 5. Rule-based / Feature-based Reranking （基于规则与业务特征）

**原理：** 根据明确的规则或业务信号调整候选文档的顺序，例如文档时效性、权威性、版本状态、权限、文档类型或字段匹配情况。

- **常见方式：** 规则加权、分数融合、过滤与优先级调整。
- **优点：** 可解释、可控，容易融入业务约束。
- **缺点：** 规则需要维护；过度加权可能压制语义相关但不符合表面规则的结果。
- **适用场景：** 企业知识库、时效性要求高的搜索、版本敏感的文档检索。





## 案例

在实际项目中，常见现象包括： 

- 文档里明明有答案，但模型没答出来 


- 换一种问法，回答质量差异很大 


- LLM 经常说“根据提供的信息，无法确定……” 


- 回答逻辑通顺，但事实不对（hallucination） 

根因通常是： 真正能回答问题的 chunk，被 embedding 召回了，但排在 Top-5 甚至 Top-10 之后， 最终没有被喂给 LLM。 

而 LLM极度依赖上下文，上下文质量很重要。
