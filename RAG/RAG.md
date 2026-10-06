

RAG优化是一整个系统问题，强业务耦合，各场景优化方向不一致。

RAG 调优 = Error Decomposition → 定位瓶颈 → 局部优化 → 系统 tradeoff → 重新评估。

## Query Translation

## Routing

## Query Construction

1. Query Rewrite（双路召回）?怎么评估 (原 query 表达不清晰)
    
2. multi-query (单一问法召回不稳定)
    
3. RAG Fusion (多路结果如何稳定合并)✅ 长期存在
    
4. Decomposition (问题本身是多跳/多子任务)✅ 长期存在
    
5. Step Back (细节问题缺少抽象语境)
    
6. HyDE (query 和文档风格不一致)
    
7. Structured Query Generation (非纯语义检索（结构化数据）)✅ 长期存在
    

## Indexing

1. 文档切分chunk策略为什么这么设计？chunk size？按段落/按条？父子切分？overlap？
    
2. embedding 维度 vs 成本？
    
3. embedding为什么这么选择？
    
4. 向量库设计？为什么 pgvector 换 milvus？[https://chatgpt.com/c/69312d72-d000-8327-ab46-22529508ea92](https://chatgpt.com/c/69312d72-d000-8327-ab46-22529508ea92)
    
5. 向量库优化？
    
6. B+树
    
7. Dify Parent-child vs RAGFlow RAPTOR？
    

## Retrieval

1. recall vs precision tradeoff ?
    
2. 检索？hybird search？（BM25+向量，es + milvus）？
    
3. rerank 是否值得？✅ 长期存在
    
4. rerank? cross-encoder / bge-reranker / colbert类 对TopK做精排
    
    有了基于向量索引与语义相似度的检索，为什么还需要Rerank？RAG应用中有多种索引类型，很多索引技术并非基于语义与向量构建，其检索的结果希望借助独立的Rerank实现语义重排。在一些复杂RAG范式中，很多时候会使用多路混合检索来获取更多相关知识；这些来自不同源、不同检索算法的chunks要借助Rerank做重排。即使是完全基于向量构建的索引，由于不同的嵌入模型、相似算法、语言环境、领域知识特点等影响，其语义检索的相关度排序也可能发生较大的偏差；此时借助独立的Rerank模型做纠正也非常有意义。
    
5. Multi Retriever?
    
6. topk=3?为什么？topK vs latency
    
7. 评估召回指标？Recall@K，MRR，NDCG？（搜索算法方法论）
    

### Sparse

1. 倒排？[https://chatgpt.com/c/69313610-f64c-832a-b666-215e4f520495](https://chatgpt.com/c/69313610-f64c-832a-b666-215e4f520495)
    
2. BM25？[https://chatgpt.com/c/693137b4-255c-8328-b3c3-df5e666471cd](https://chatgpt.com/c/693137b4-255c-8328-b3c3-df5e666471cd)
    

### Dense

#### ANN

（向量检索不是全盘跑）

1. IVF聚类
    
2. HNSW
    
3. PQ/OPQ
    
4. graph index
    
5. treeindex高维不用（KD / Ball Tree））
    

## Generation

1. 提示：prompt结构设计？system instruction 强化？
    
2. 提示工程优化？幻觉控制？
    
3. 对齐：hallucination 如何控制？citation 约束？
    
4. 上下文组织：context window 排布顺序？证据优先排序？
    
5. alignment 与 recall 的 tradeoff？
    

## Evaluation

1. offline eval怎么设计？怎么定义指标（关键）？
    
2. Recall@K？Hit rate？人工标注小集合？线上反馈闭环？
    
3. 自动化评测？评估体系？
    
4. 优化回答实际是优化哪些流程（检索/生成...）？
    
5. 优化速度？
    
6. badcase 如何分层？检索错还是生成错？retrieval recall 分析
    
7. factuality？grounding rate？hallucination rate？
    

### 评估指标

1. Recall@k
    
2. Precision@k
    
3. MRR（Mean Reciprocal Rank）
    
4. Hit Rate@k
    
5. IoU（Intersection over Union）
    

## Infrastructure

1. 批量embedding？
    
2. cache层？
    
3. streaming生成？
    
4. 异步pipeline？
    
5. 分布式Milvus？
    
6. 多轮对话缓存策略？