# 类别二：高并发、流式响应与异步处理



## 1. 场景：服务端SSE代理的断线重连、消息去重与网络抖动处理

**核心思路：** 后端作为客户端（前端）与上游AI服务之间的代理，需实现一个健壮的、有状态的连接管理器，负责维护与AI服务的长连接，并处理下游客户端的重连。

1. **会话与连接管理：**
   - 为每个前端SSE连接创建一个 `SSESession`，为其分配唯一 `sessionId`。该会话内部维护与上游AI服务的HTTP客户端连接（如使用 `WebClient` 或异步 `HttpClient`）。
   - 将会话及对应的 `lastEventId` 等状态存储于分布式缓存（如Redis），键为 `sessionId`，并设置合理的TTL。

2. **处理前端断线重连：**
   - 前端重连时，携带之前连接中断时收到的最后一个事件的ID（`Last-Event-ID` 头）。
   - 后端根据 `sessionId` 从缓存中恢复会话状态。**关键操作：** 后端需基于恢复的 `lastEventId`，重新向上游AI服务建立连接，并在请求头中设置 `Last-Event-ID`，以实现从断点续传。这要求上游AI服务支持此标准。

3. **消息去重：**
   - **目的：** 防止因网络抖动或客户端重连导致下游收到重复消息。
   - **实现：** 后端在转发从AI服务收到的SSE事件时，为每个事件附加一个内部单调递增的序列号（如 `localSeq`），并与会话状态一起缓存。当前端重连时，后端在转发新事件前，会比较前端传来的 `Last-Event-ID` 与本地缓存的序列号，只转发序列号更大的事件。

4. **应对网络抖动：**
   - 在代理层设置合理的**读超时**和**响应超时**，避免因上游AI服务响应缓慢而长时间占用后端线程。
   - **实现背压（Backpressure）：** 当下游客户端处理缓慢（表现为TCP缓冲区满）时，后端应能感知并暂停从上游读取数据，或缓冲少量数据后断开上游连接，避免内存溢出。Spring WebFlux的 `Flux` 能天然支持背压。

5. **关键考量：** 此设计的核心是**会话状态外部化**，使服务端具备无状态扩容能力，同时通过代理层实现了上游协议与下游客户端的解耦和增强。



## 2. 场景：服务端的流式Markdown分片与转发

**核心思路：** 后端不负责渲染，但负责将AI的流式输出智能地切割为完整的Markdown片段，以结构化的形式（如JSON）分块发送给前端，便于其安全渲染。

1. **流式分词与边界检测：**
   - 后端在消费上游AI服务的字符流时，实时进行Markdown语法解析，识别块级元素的边界，如代码块（```）、标题（#）、列表、表格等。
   - 使用一个状态机或轻量级解析库（如 `commonmark-java` 的流式解析器），在内存中累积字符，直到检测到一个**完整的Markdown块**形成。

2. **结构化分片转发：**

   - 一旦检测到完整块（例如，一个完整的代码块，包含开始标记、内容和结束标记），立即将其封装为一个JSON对象，例如：

     ```
     {
     	"type": "code_block",
     	"language": "java",
     	"content": "public class Main {...}",
     	"complete": true
     }
     ```

   - 通过SSE或WebSocket将整个JSON对象作为一个消息发送给前端。对于段落文本，可以按句子或自然段进行分片。

**3. 优势：**

- **避免标签截断：** 因每次发送的都是语法完整的片段，前端可直接将其转换为DOM，无需担心破损的HTML标签。
- **提升前端体验：** 前端可按"块"为单位进行渲染，可以实现更流畅的逐块出现效果，而非逐字抖动。
- **富结构化：** 附带元数据（如代码语言），使前端能进行精准高亮。



## 3. 场景：服务端对多独立片段流式响应的Chunk合并算法

**核心思路**：在后端设计一个缓冲区与状态机，负责将上游可能零碎到达的、属于不同逻辑片段的数据进行暂存、排序和合并，确保向下游转发时每个数据包的完整性。

1. **协议定义与识别**：与上游AI服务约定，或在接收流时识别片段边界。例如，每个数据块可包含 `fragment_id` 和 `sequence` 字段。或者，通过内容特征识别（如特定分隔符）。
2. **内存合并缓冲区**：
   - 维护一个 `Map<String, FragmentBuffer>`。键为 `fragment_id`，值为一个缓冲区对象，包含 `StringBuilder content` 和 `int expectedSequences`。
   - 收到一个Chunk后，根据其 `fragment_id` 找到对应缓冲区，将内容按 `sequence` 顺序插入或追加。
3. **完整性判断与转发**：
   - 当收到某个片段的 `is_final` 标识块，或缓冲区已按序收齐该片段的所有序列块时，认为该片段完整。
   - 将缓冲区内的完整内容取出，作为一个逻辑单元（可包装为 `{"type": "fragment", "id": "x", "data": "完整内容"}`）转发给下游客户端。
4. **超时与清理**：为每个 `fragment_id` 设置计时器。如果长时间未收到后续块，应清理该缓冲区，并可选择向上游重试或向下游发送错误通知，防止内存泄漏。



## 4. 场景：服务端支持“优先级调度”的流式请求队列

**核心思路**：在后端实现一个任务队列，将用户请求封装为任务，根据优先级进行调度执行，并支持高优先级任务抢占低优先级任务的资源。

1. **任务抽象与队列**：
   - 定义 `StreamingJob` 类，包含请求参数、优先级、创建时间、所属用户/会话、以及一个 `Future` 或 `Cancellable` 句柄。
   - 使用 `PriorityBlockingQueue` 存放待执行的 `StreamingJob`，排序规则基于优先级和创建时间。
2. **线程池与任务执行**：
   - 使用一个固定大小的线程池执行任务。工作线程从优先级队列中获取任务。
   - 每个任务执行时，首先与上游AI服务建立连接，并开始转发数据。同时，将控制该连接的 `Cancellable` 对象（如 `WebClient` 的 `Disposable`）保存到 `StreamingJob` 中。
3. **抢占式调度**：
   - 当一个新的高优先级任务到达时，调度器检查正在运行的任务。
   - 如果存在正在运行的、优先级更低的任务，调度器调用其 `Cancellable.cancel()` 方法，中断其与上游AI服务的连接。将被中断的任务（标记为 `INTERRUPTED`）重新放回队列或放入等待队列，稍后重试。
   - 随后立即开始执行高优先级任务。
4. **状态持久化与恢复**：对于被抢占的任务，可将其当前进度（如已生成的文本）保存起来，以便重试时能从断点开始，或至少能向用户反馈部分结果。



## 5. 场景：在Spring WebFlux中优化AI流式响应的处理与资源隔离

**核心思路**：利用响应式编程模型和非阻塞IO，避免线程阻塞，并通过隔离的调度器处理不同类型的工作负载。

1. **全链路非阻塞**：
   - 使用 `WebClient`（而非阻塞式的 `RestTemplate`）调用上游AI服务的流式接口，返回 `Flux<DataBuffer>`。
   - Controller直接返回 `Flux<ServerSentEvent>` 或 `application/stream+json`。Spring WebFlux会负责将响应式流写回网络，整个过程不占用额外线程，并发能力极强。
2. **隔离与调度器**：
   - **计算密集型处理**：如果需要对流式数据做复杂转换（如实时翻译、敏感词过滤），应使用 `publishOn(Schedulers.boundedElastic())` 将工作调度到专门的弹性线程池，避免阻塞用于IO的Event Loop线程。
   - **阻塞调用隔离**：如果必须集成一个阻塞的AI客户端SDK，使用 `Mono.fromCallable(() -> blockingCall()).subscribeOn(Schedulers.boundedElastic())` 将其调用隔离到弹性线程池，再将其结果转换为 `Flux`。
3. **背压传导**：确保从 `WebClient` 到Controller返回的 `Flux`，背压信号能正确地从下游客户端传导至上游AI服务，防止数据积压。`WebClient` 的 `retrieve().bodyToFlux()` 默认支持背压。
4. **关键优势**：此模式能用少量线程支撑极高并发（数千甚至上万）的流式连接，系统资源利用率高，且通过调度器实现了天然的隔离。



## 6. 场景：服务端的流式数据缓存与断点续传支持

**核心思路**：在后端缓存已生成的流式数据，并为每个会话维护一个写入指针，以支持离线续写和历史回放查询。

1. **缓存设计**：
   - 使用Redis的 `List` 或 `Stream` 数据结构为每个 `sessionId` 缓存流式事件。每个事件包含序列号、内容、时间戳。
   - 也可以使用本地缓存（如Caffeine）加速最新数据的读取，但Redis保证了分布式下的访问一致性。
2. **写入与指针**：
   - 在从上游AI服务接收并向下游转发数据的同时，将每个事件异步追加到对应 `sessionId` 的Redis `List` 中。
   - 在Redis中存储一个指针（`String` 类型），键如 `session:{id}:offset`，值始终指向最新写入事件的序列号。
3. **断点续传**：
   - 客户端重连携带 `Last-Event-ID`（即序列号N）。
   - 后端根据 `sessionId` 从Redis `List` 中获取所有序列号大于N的事件，先发送给客户端，以"追赶上"进度。
   - 之后，再切换到实时转发模式，并继续缓存新事件。
4. **历史回放**：提供单独的REST接口，如 `GET /sessions/{id}/events?from=0&to=100`，从Redis `List` 中分页查询历史事件，实现完整的回放功能。
5. **清理策略**：设置会话过期时间，或当会话明确结束后，启动后台任务删除对应的Redis数据。



## 7. 场景：利用Java并发工具并行处理多个AI流式响应

**核心思路**：使用 `CompletableFuture` 或 `Project Loom` 的虚拟线程，为每个独立的AI流式调用创建并发任务，并在主线程中协调结果的聚合与同步。

1. **并行调用**：
   - 为每个需要并行的AI请求创建一个 `CompletableFuture<Flux<String>>`。在每个Future中，使用 `WebClient` 发起非阻塞的流式调用，并将得到的 `Flux` 收集到一个 `List` 中（或直接开始消费）。
   - 使用 `CompletableFuture.allOf(future1, future2).join()` 等待所有流式连接就绪。
2. **流式聚合**：
   - 更高级的模式是使用反应式组合运算符。例如，使用 `Flux.merge(future1.join(), future2.join())` 将多个 `Flux` 合并为一个，但会丢失来源信息。
   - 若需区分来源，可使用 `Flux.zip(f1, f2)` 将多个流的最新元素配对，或为每个流的事件打上标签后再合并。
3. **状态同步与回调**：
   - 每个并行任务（`CompletableFuture`）在运行时，可以通过线程安全的容器（如 `ConcurrentHashMap`）或原子类更新共享进度状态。
   - 主线程可以定时轮询此状态，或由每个任务在关键节点（如每收到10个Chunk）时发布事件，来聚合生成整体进度。
4. **资源控制**：使用 `Semaphore` 或固定大小的线程池来限制并行调用的最大数量，防止对上游AI服务造成洪水攻击。



## 8. 场景：解析AI服务端返回的流式数据中的自定义事件

**核心思路**：在HTTP客户端层或流式数据处理链中插入一个事件解复用器，将控制事件与数据事件分离，并路由到不同的处理器。

1. **事件识别**：

   - 在读取SSE响应行时，不仅解析 `data:`，也解析 `event:` 字段。如果 `event:` 字段值为 `DONE` 或 `ERROR`，则将其识别为控制事件。
   - 如果数据格式是自定义的（如 `[DONE]`），则需要在解析 `data:` 内容时进行字符串匹配。

2. **构建处理管道**：

   - 使用响应式编程模型，将原始的 `Flux<ServerSentEvent>` 通过 `handle` 或 `filter` 操作符进行分流。

     ```
     Flux<DataEvent> dataFlux = sseFlux
             .filter(sse -> "message".equals(sse.event())) // 过滤出数据事件
             .map(sse -> new DataEvent(sse.id(), sse.data()));
     Flux<ControlEvent> controlFlux = sseFlux
             .filter(sse -> "done".equals(sse.event()) || "error".equals(sse.event()))
             .map(sse -> new ControlEvent(sse.event(), sse.data()));
     ```

3. **触发回调**：

   - 订阅 `controlFlux`，并在收到事件时，调用预先注册的回调处理器。这些处理器可以执行清理资源、更新数据库状态、发送WebHook通知等操作。
   - 订阅 `dataFlux`，进行常规的数据处理与转发。

4. **确保可靠性**：控制事件的处理逻辑必须幂等，因为网络重试可能导致事件重复接收。



## 9. 场景：服务端实现“流式进度估算”并推送给客户端

**核心思路**：服务端作为中间层，有能力收集更精确的元数据，从而进行更可靠的进度估算，并通过SSE或WebSocket主动推送。

1. **多维度数据收集**：
   - **从上游**：尝试从AI服务的响应头或首个Chunk中获取 `total_tokens` 预估。
   - **在代理层**：准确统计已接收的 `tokens_received`（从内容解析或从上游元数据获得）和已消耗的时间 `time_elapsed`。
2. **动态估算模型**：
   - 如果获取到 `total_tokens`，则进度 = `tokens_received / total_tokens`。
   - 如果未获取到，可采用移动平均预测：根据近期（如过去10秒）的平均Token生成速率，预测剩余时间。也可结合历史同类型任务的数据进行贝叶斯修正。
3. **进度推送**：
   - 单独开辟一个轻量级的SSE事件流（`event: progress`），或在与数据相同的SSE连接中穿插发送进度事件。
   - 定期（如每秒）或在进度有显著变化（如增加5%）时，将估算结果（`{"progress": 0.65, "eta_seconds": 30}`）发送给客户端。
4. **处理不确定性**：当无法获取总量时，进度条可设计为"不确定模式"（indeterminate），或显示已处理的Token数和当前速率。



## 10. 场景：协调AI流式输出与语音合成(TTS)的服务端同步

**核心思路**：服务端作为协调者，管理文本流和语音流两个独立的异步过程，并确保它们的同步状态。

1. **管道设计**：
   - **文本流**：接收AI的文本流，并进行句子切分（Sentence Segmentation）。
   - **TTS任务队列**：将切分出的完整句子，封装为TTS任务，提交给一个异步任务队列（如通过 `@Async`、线程池或消息队列）。
2. **同步状态管理**：
   - 为每个会话维护一个"当前朗读句索引"和"TTS任务完成状态"的映射。
   - TTS服务（可能是另一个微服务）处理完一个句子的语音合成后，回调通知后端，或后端轮询TTS服务状态。
3. **客户端协调**：
   - 后端通过两条下行通道与客户端通信：
     - i. **文本流SSE**：推送被切分后的文本句子。
     - ii. **控制信令WebSocket/SSE**：推送语音同步信令，如 `{"type": "tts_start", "sentence_index": 1}` 和 `{"type": "tts_end", "sentence_index": 1}`。
   - 客户端根据信令，高亮当前正在朗读的文本句子。
4. **处理用户交互**：当用户点击"暂停"时，后端暂停向TTS任务队列提交新句子，并通知TTS服务暂停当前合成。当用户"跳过"时，后端取消当前及后续已提交的TTS任务，并清理相关状态，然后从新的句子开始提交。
5. **复杂度**：此方案涉及多个异步服务的协调，状态管理复杂，通常需要一个状态机（如Spring State Machine）来清晰地管理会话的整体状态（`PLAYING`，`PAUSED`，`SKIPPING`）。



## 11. 场景：从数据库分页读取海量数据，分批流式发送给AI处理

**核心思路**：采用基于游标的惰性读取与生产者-消费者模型，实现可控制、可观察的批处理管道，避免一次性加载导致内存溢出。

1. **游标与分页策略**：
   - 避免使用传统的 `OFFSET-LIMIT` 分页，在数据量极大时深度分页性能极差。应使用基于游标的分页，即查询条件中附带 `id > lastId ORDER BY id LIMIT batchSize`。这需要表有一个单调递增的主键或索引列。
   - 使用Spring Data JPA的 `Streamable` 或MyBatis的 `Cursor` 接口进行数据库游标读取，实现逐批从数据库拉取数据，而非一次性加载到内存。
2. **可控的并行处理管道**：
   - 设计一个 `BatchProcessor`，它包含一个生产者线程（负责从游标读取数据并分块）和一个由线程池管理的消费者组。
   - 生产者将每批数据（如1000条记录）封装为一个 `ProcessTask`，提交到一个有界阻塞队列（`BlockingQueue`）中。
   - 消费者线程从队列中获取任务，调用AI服务进行批处理，并更新处理进度（如写入Redis）。
3. **进度管理与容错**：
   - 在Redis中使用 `Hash` 结构记录当前任务的总批次数、已处理批次数、最后处理的游标位置。
   - 每个 `ProcessTask` 处理成功后，原子性地更新进度。若处理失败，可将该任务重新放入队列重试（需注意幂等性），或移入死信队列人工介入。
4. **背压与资源保护**：有界队列的大小和消费者线程池的大小共同构成了系统的处理能力上限。当队列满时，生产者线程会被阻塞，从而自然形成背压，防止任务积压过快导致内存溢出。



## 12. 场景：异步处理“翻译整本电子书”的长时、可分解任务

**核心思路**：将宏观任务分解为独立的原子子任务，利用工作队列进行并行调度，并通过工作流引擎或状态机管理总体进度与子任务依赖。

1. **任务分解与定义**：
   - 接收任务后，首先将电子书按章节或固定大小进行切分，生成N个独立的 `TranslationSubTask`，每个子任务包含原文片段、目标语言等上下文。
   - 在数据库中创建主任务记录（`BookTranslationJob`）和所有子任务记录，状态均为 `PENDING`。
2. **并行调度与执行**：
   - 将所有子任务发布到分布式消息队列（如Kafka、RabbitMQ）或提交到 `ExecutorService`。
   - 多个消费者（或工作线程）并行处理子任务：调用AI翻译API，将结果保存至数据库或对象存储，并将子任务状态更新为 `SUCCESS`。
3. **进度汇总与最终合并**：
   - 每次子任务状态更新时，触发一个"完成检查"。可以通过数据库查询 `COUNT` 已完成子任务，或更高效地，在Redis中使用 `INCR` 命令累计成功数。
   - 当所有子任务成功，触发一个"合并阶段"任务，将所有子任务的译文按顺序拼接，生成最终的电子书文件，并更新主任务状态为 `COMPLETED`。
4. **处理部分失败**：
   - 为子任务设置重试机制和失败上限。超过重试次数后，标记为 `FAILED`。
   - 主任务状态可变为 `PARTIALLY_FAILED`，并记录失败的具体章节，允许人工干预或重新提交特定失败子任务。



## 13. 场景：针对AI服务的分布式平滑限流

**核心思路**：利用Redis的原子操作和高性能特性，实现一个集群共享的、精确的令牌桶或漏桶算法。

1. **算法选择（令牌桶）**：实现一个分布式令牌桶。核心参数：`capacity`（桶容量）、`refillRate`（每秒补充的令牌数）。
2. **Redis Lua脚本实现**：为保证原子性，使用Lua脚本在Redis端一次性完成计算。脚本逻辑通常包含：
   - 使用 `TIME` 命令获取当前时间戳。
   - 根据 `lastRefillTime` 和 `refillRate` 计算应补充的新令牌数，更新当前令牌数（不超过 `capacity`）。
   - 如果当前令牌数 >= 1，则减1，返回 `true`（允许通过），并更新 `lastRefillTime`。
   - 否则，返回 `false`（拒绝通过）。
3. **Java客户端集成**：
   - 在Spring应用中，通过 `RedisTemplate.execute(RedisScript)` 调用上述Lua脚本。
   - 在网关（如Spring Cloud Gateway）的过滤器或业务服务的切面中，对需要限流的AI服务调用前执行此脚本。
4. **维度扩展**：限流键（Key）可设计为 `rate_limit:{apiEndpoint}:{tenantId}`，从而实现对不同API、不同租户的差异化限流。通过配置中心动态管理 `capacity` 和 `refillRate` 参数。



## 14. 场景：在WebFlux中将流式`Flux<String>`聚合为`Mono<CompleteResponse>`

**核心思路**：利用Reactor操作符对流进行收集、超时控制和异常处理，实现同步与异步调用模式的统一。

1. **响应聚合**：
   - 使用 `Flux.collectList()` 操作符，可以将流中的所有元素（数据块）收集到一个 `List<String>` 中。
   - 然后使用 `map` 操作符，将这个列表合并成一个完整的字符串，并构造为 `CompleteResponse` 对象。最终返回类型为 `Mono<CompleteResponse>`。
2. **超时控制**：
   - 在流上使用 `timeout(Duration)` 操作符，为整个流式响应过程设置总超时。超时会发出 `TimeoutException`。
   - 可以使用 `onErrorResume` 捕获超时异常，返回一个部分结果或错误响应的 `Mono`。
3. **背压与缓冲区策略**：
   - 当聚合完整响应时，需注意背压。如果生产速度远快于消费（收集）速度，可能导致内存压力。
   - 可使用 `Flux.bufferTimeout(int maxSize, Duration maxTime)` 进行缓冲，每收集到一定数量或经过一定时间，就将缓冲区的数据向下游推送一次，在聚合场景下，这通常意味着最后合并一次。
4. **统一接口设计**：可以设计一个服务方法，同时支持流式和非流式返回。通过一个布尔参数（如 `stream: boolean`）控制。若 `stream` 为 `true`，直接返回 `Flux<String>`；若为 `false`，则调用上述聚合逻辑返回 `Mono<CompleteResponse>`。



## 15. 场景：实现用户中断AI生成请求的信号传递

**核心思路**：建立"请求-中断"信令通道，并在服务端实现优雅的资源清理链。

1. **中断信令接收**：为用户会话提供另一个端点，如 `POST /generations/{taskId}/cancel`。前端在用户点击停止时调用此端点。
2. **任务管理与中断触发**：
   - 服务端维护一个 `ConcurrentHashMap<String, CancellableTask>`，键为 `taskId`，值为一个包含 `WebClient.RequestHeadersUriSpec` 或其他可取消句柄的任务对象。
   - 创建AI生成任务时，将 `taskId` 和对应的 `CancellableTask` 存入此Map。
   - 当收到中断请求时，从Map中获取对应的 `CancellableTask`，调用其 `cancel()` 或 `dispose()` 方法。这将断开与上游AI服务的HTTP连接，停止数据拉取。
3. **清理与状态同步**：
   - 中断后，向上游AI服务的中断也可能需要调用特定API（如果支持）。
   - 清理服务端为该任务分配的资源（如缓冲区、内部状态），并将任务最终状态更新为 `CANCELLED`。
   - 向客户端（前端）发送一个明确的任务终止事件（可通过原SSE连接发送 `[DONE]`，或通过WebSocket），并附中中断原因。
4. **处理已生成部分**：在清理前，可以选择将已生成的部分内容保存下来，关联到该任务，允许用户查看"未完成的草稿"。



## 16. 场景：基于消息触发，并行调用多个AI服务并聚合结果

核心思路：利用 `CompletableFuture` 或反应式编程实现并行调用，并利用回调或 `CompletableFuture.allOf()` 进行结果聚合。

1. **消息监听与任务触发**：使用 `@KafkaListener` 或 `@RabbitListener` 监听消息队列。当收到图片处理消息时，触发处理流程。
2. **并行调用封装**：
   - 将"描述图片"和"审核图片"两个AI调用分别封装为返回 `CompletableFuture<DescriptionResult>` 和 `CompletableFuture<AuditResult>` 的方法。
   - 在方法内部，使用 `@Async` 注解（需配合 `@EnableAsync`）或手动提交到线程池，执行具体的HTTP请求。
3. **结果聚合**：

```
CompletableFuture<DescriptionResult> future1 = imageDescriptionService.describeAsync(imageUrl);
CompletableFuture<AuditResult> future2 = imageAuditService.auditAsync(imageUrl);
CompletableFuture.allOf(future1, future2)
        .thenAccept(void -> {
            DescriptionResult desc = future1.join(); // 此时已经完成，不会阻塞
            AuditResult audit = future2.join();
            CombinedResult result = combine(desc, audit);
            // 将聚合结果发送到响应队列
            responseSender.send(result);
        }).exceptionally(ex -> {
            // 处理任一任务失败的情况
            return null;
        });
```

4. **超时与熔断**：为每个 `CompletableFuture` 配置 `orTimeout`，并为每个AI服务调用配置熔断器（如Resilience4j），避免单个服务故障导致整体流程长时间挂起。



## 17. 场景：对低优先级AI任务实现基于优先级的延迟调度

**核心思路**：实现一个支持优先级的延迟队列，并结合定时任务或调度线程池执行。

1. **任务与队列定义**：
   - 定义 `DelayedTask` 实现 `Delayed` 接口，包含 `Runnable` 任务、`priority`、`executeTime`（执行时间戳）。
   - 使用 `PriorityBlockingQueue<DelayedTask>` 作为延迟队列。排序规则：先按 `executeTime`（越早到期越靠前），`executeTime` 相同时按 `priority`（优先级越高越靠前）。
2. **调度器核心**：
   - 创建一个 `PriorityTaskScheduler`，内部包含一个 `Thread`，其 `run` 方法循环从队列中取任务（`queue.take()` 会阻塞直到有任务到期）。
   - 取到到期任务后，将其提交到一个通用的工作线程池执行。
3. **任务提交**：
   - 高优先级任务：`executeTime` 设置为 `now`，直接放入队列，会很快被执行。
   - 低优先级任务：`executeTime` 设置为 `now + delay`（如5分钟后），放入队列，实现延迟处理。
4. **资源感知与动态调整**：调度器可以监控系统负载（如CPU、活跃线程数）。当系统负载高时，动态增加低优先级任务的 `delay` 时间，实现自适应降级。



## 18. 场景：解析AI流式响应中的自定义控制事件

**核心思路**：在流式处理管道中，对Server-Sent Event进行解复用，将控制事件与数据事件分离，并派发到不同的事件处理器。

1. **SSE事件解析**：使用Spring的 `org.springframework.http.codec.ServerSentEvent` 对象来解析原始的SSE流。它会自动处理 `event`，`data`，`id`，`retry` 等字段。
2. **构建处理管道**：

```
Flux<ServerSentEvent<String>> sseFlux = webClient.get()
        .uri("/ai-stream")
        .retrieve()
        .bodyToFlux(ServerSentEvent.class);
// 分离数据流
Flux<String> dataStream = sseFlux
        .filter(sse -> sse.event() == null || "message".equals(sse.event())) // 默认或无事件类型的数据
        .map(ServerSentEvent::data);
// 分离控制流
Flux<ControlEvent> controlStream = sseFlux
        .filter(sse -> "done".equals(sse.event()) || "error".equals(sse.event()))
        .map(sse -> new ControlEvent(sse.event(), sse.data())));
```

3. **事件派发**：
   - 分别订阅 `dataStream` 和 `controlStream`。
   - 订阅 `controlStream` 时，根据事件类型（`done`，`error`）调用注册的处理器。处理器可以更新数据库状态、发送通知、记录日志等。

4. **确保可靠性**：控制事件处理应设计为幂等的，因为网络重试可能导致同一事件被多次接收。可以在处理前检查事件ID是否已处理过。



## 19. 场景：使用Project Loom虚拟线程重构阻塞式AI任务服务

**核心思路**：将传统线程池替换为虚拟线程执行器，以极低的资源消耗支持超高数量的并发阻塞任务。

1. **执行器服务创建**：
   - Java 19+ 中，使用 `Executors.newVirtualThreadPerTaskExecutor()` 创建一个为每个任务创建虚拟线程的执行器。
   - 相比于固定大小的平台线程池，虚拟线程池允许你同时"阻塞"地处理数万甚至数十万个AI任务，而底层仅需要少量平台线程支持。
2. **重构注意事项**：
   - **同步锁（`synchronized`）**：在虚拟线程内持有 `synchronized` 锁会阻塞其承载的平台线程，严重损害吞吐量。必须将 `synchronized` 替换为 `ReentrantLock`。
   - **线程局部变量**：`ThreadLocal` 在虚拟线程中仍然工作，但需注意清理，因为虚拟线程生命周期可能很短。考虑使用 `ScopedValue`（预览API）。
   - **原生代码与IO**：虚拟线程在等待IO（如数据库查询、HTTP请求）时会被挂起，这是其优势所在。但若任务中调用了阻塞式原生代码，仍会阻塞平台线程。
3. **资源限制**：虽然可以创建海量虚拟线程，但仍需限制对某些有限资源（如数据库连接、外部API的QPS）的并发访问。可使用 `Semaphore` 进行控制。
4. **可观测性**：虚拟线程的线程栈和ID与传统线程不同，需确保日志框架和监控工具能正确识别和追踪虚拟线程。



## 20. 场景：设计用于AI服务HTTP/2长连接的连接池

**核心思路**：利用高性能HTTP客户端（如基于Netty的 `Reactor Netty` 或 `OkHttp`）内置的连接池管理，并针对AI流式场景进行优化配置。

1. **客户端选型与配置**：以Spring `WebClient`（底层为Reactor Netty）为例：

```
spring:
  webclient:
    reactor-netty:
      pool:
        max-connections: 1000 # 连接池最大连接数
        max-idle-time: 60s # 连接最大空闲时间
        max-life-time: 300s # 连接最大存活时间
        eviction-interval: 60s # 清理空闲连接的时间间隔
        pending-acquire-timeout: 60s # 从池中获取连接的最大等待时间
```

2. **针对流式场景的优化**：
   - **连接复用**：HTTP/2支持多路复用，一个连接上可以并发多个请求。对于频繁的、小的流式请求，应充分利用此特性，避免频繁建连。
   - **超时设置**：为流式响应设置更长的 `responseTimeout`（如几分钟），而为连接获取、读取等操作设置较短超时。

3. **健康检查与熔断**：
   - 配置连接池的健康检查机制，定期清理无效连接。
   - 结合熔断器（如Resilience4j），当某个上游AI服务端点连续失败时，熔断该端点对应的连接池，避免向故障实例发送请求。

4. **监控**：暴露连接池指标（如活跃连接数、空闲连接数、等待获取连接的请求数）到监控系统（如Prometheus），便于容量规划和故障排查。`Reactor Netty` 的 `Micrometer` 集成可以自动提供这些指标。