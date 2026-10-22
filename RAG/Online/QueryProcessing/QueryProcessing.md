# Query Processing

[TOC]



## Query Translation

把用户原始 Query 转换成更适合检索的 Query。通过优化原始查询，使其更贴近知识库中的表述，从而提升检索的召回率。

| 问题类型                                              | 解决方法                | 核心思想            | Query 变化                                    | 典型检索流程                                        |
| ----------------------------------------------------- | ----------------------- | ------------------- | --------------------------------------------- | --------------------------------------------------- |
| **Query 表达不清晰**                                  | **Query Rewrite**       | 改写                | 原 Query → 更清晰、更适合检索的 Query         | Query → Rewrite Query → Retrieval                   |
| **Query 信息不足、关键词覆盖不足**                    | **Query Expansion**     | 扩展                | 原 Query → Query + 相关词/概念                | Query → Expanded Query → Retrieval                  |
| **Query 与文档表达风格/语义空间不一致**               | **HyDE**                | 假设文档            | Query → 假设答案/文档 → Embedding             | Query → Hypothetical Document → Retrieval           |
| **单一问法召回不稳定、语义覆盖不足**                  | **Multi-Query**         | 横向扩展            | 一个 Query → 多个不同表述 Query               | Query → Multi Queries → Multi Retrieval             |
| **不确定哪种 Query 表述最适合检索，需要综合多路结果** | **RAG Fusion**          | 多路检索 + 结果融合 | 一个 Query → 多个 Query → 多路检索 → 结果融合 | Query → Multi Queries → Retrieval × N → Fusion      |
| **Query 过于复杂，包含多个子问题/多跳任务**           | **Query Decomposition** | 纵向拆解            | 复杂 Query → 多个子 Query / 子问题            | Complex Query → Sub-Queries → Retrieval → Synthesis |
| **Query 过于具体，直接检索缺少背景语境**              | **Step-Back**           | 向上抽象            | 具体 Query → 更抽象、更高层的 Query           | Specific Query → Abstract Query → Retrieval         |





## Intent Routing





## Query Construction

把自然语言 Query 转换成某个检索系统真正需要的结构化查询。

例如用户：

```
“帮我找一下去年北京地区销售额超过100万的客户”
```

可能构造成：

```
{
  "year": 2025,
  "region": "北京",
  "sales": {
    "$gt": 1000000
  }
}
```

或者生成：

```
SELECT *
FROM customers
WHERE region = '北京'
  AND sales > 1000000
  AND year = 2025;
```



### 1. Structured Query Generation

把用户意图变成结构化的查询条件/查询语言

#### Metadata Filter Generation

从自然语言 Query 中提取结构化过滤条件

#### SQL Generation

Natural Language → SQL

#### Graph Query Generation

同样的思想，只不过目标数据库是知识图谱

| 类型                       | 目标                       |
| -------------------------- | -------------------------- |
| Metadata Filter Generation | Vector DB / Document Store |
| SQL Generation             | Relational Database        |
| Graph Query Generation     | Knowledge Graph            |



### 2. Search Query Construction

构造搜索引擎 / 向量数据库 / 混合检索器真正拿来“搜索”的 Query

#### Keyword Query

构造关键词然后交给 BM25 / Elasticsearch 等关键词检索

#### Semantic Query

生成一个适合 embedding / semantic retrieval 的查询表达

#### Hybrid Query

同时构造：

```
Keyword Query
    +
Semantic Query
```