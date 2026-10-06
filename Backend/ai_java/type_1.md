# 类别一：数据、接口与类型契约



## 1. 场景：异构AI模型“工具调用”响应的统一处理

**核心思路**：采用“两层模型”+“多态反序列化”+“工厂模式”进行转换。

1. **统一内部模型**：首先，定义公司内部统一的`AgentAction`（或`ToolCall`）领域对象，包含工具名、参数映射、调用ID等必需字段。
2. **中间适配层**：为每个AI服务商（OpenAI、Claude等）创建专用的`XXXToolCallResponse`DTO类，准确映射其独有的JSON结构（如OpenAI的`tool_calls`数组，Claude的`tool_use`块）。
3. **智能反序列化**：利用Jackson的`@JsonTypeInfo`和`@JsonSubTypes`注解，或自定义`JsonDeserializer`，根据响应中的某个特征字段（如`object`字段值为`chat.completion`）将原始的JSON反序列化到对应的中间DTO。
4. **转换工厂**：定义一个`ToolCallAdapter`接口及其多个类实现。每个实现类负责将特定中间DTO转换成统一的`AgentAction`对象。通过一个注册表或Spring的`Map<String, ToolCallAdapter>`注入，根据服务商类型选择正确的转换器。
5. **关键考量**：此设计保证了核心业务逻辑只处理统一对象，新增AI服务商时，只需新增“中间DTO”和“转换器”，符合开闭原则。



## 2. 场景：AI API升级，新增可选字段的向后兼容

**核心思路**：利用Jackson的忽略未知属性特性，并设计可降级的透传策略。

1. **反序列化兼容**：在用于反序列化AI响应的DTO类上，始终标注`@JsonIgnoreProperties(ignoreUnknown = true)`。这样，当新版本API返回旧版DTO中不存在的`reasoning`字段时，Jackson会静默忽略，不会报错。
2. **字段透传设计**：
   - **方案A（内部升级）**：如果后端服务自身也希望利用新字段，则直接在后端DTO中添加新字段`reasoning`。由于是可选字段，处理旧版响应时其为`null`，完全兼容。
   - **方案B（纯透传）**：如果后端无需处理，只需透传给新版客户端，可将整个反序列化后的`ObjectNode`（Jackson的树模型）与一个包含了已知字段的POJO组合使用，或使用`Map<Strting, Object>`接受原始数据。在返回给前端的响应中，将此`Map`或`ObjectNode`的原始内容包含进去。
3. **版本协商**：更精细的方案可通过请求头（如`Api-Version`）区分客户端版本。后端根据版本决定是否在逻辑中使用`reasoning`字段，或是否将其从响应中过滤掉。



## 3. 场景：复杂工作流配置的校验

**核心思路**：将工作流抽象为有向无环图，并利用JSR-380规范进行多层次校验。

1. **领域建模**：定义`WorkflowDefinition`、`Node`、`Connection`等核心类。`Node`应包含`id`、`type`（如AI处理、条件判断）、`inputSchema`、`outputSchema`。`Connection`包含`sourceId`、`targetId`、`sourcePort`、`targetPort`。
2. **图结构校验**：
   - **闭环检测**：通过深度优先搜索检查是否存在从任一节点出发又能回到该节点的环。
   - **连接合法性**：校验`Connection`中的`sourcePort`和`targetPort`在对应节点的输入输出模式中是否存在，且数据类型是否兼容（可通过字符串匹配或类型枚举）。
3. **集成校验框架**：
   - 声明式校验：在`WorkflowDefinition`的属性上使用`@NotNull`、`@Size`等标准注解。
   - 自定义校验器：创建`@ValidWorkflow`注解及其关联的`Validator`实现类。在该实现类中，调用上述图结构校验逻辑，并将违规处转换为`ConstraintViolation`。
4. **执行**：在接收用户配置的Controller方法参数上使用`@Valid`触发校验，错误信息会通过`MethodArgumentNotValidException`统一返回给前端。



## 4. 场景：AI绘画参数的复杂校验

**核心思路**：构建分层校验体系，结合标准注解、自定义校验器和业务规则引擎。

1. **基础DTO与标准注解**：创建`PaintingRequest`DTO，用`@Enum`注解限制`resolution`为`["512x512", "1024x1024"]`，用`@Size(max=500)`限制`negative_prompt`长度，用`@Pattern`校验某些参数格式。
2. **自定义组合校验**：创建`@MutuallyExclusive`注解，标注在互斥的字段（如`style`和`artist`）上。在其校验器实现中，编写逻辑判断：如果`style=="realistic" && artist=="Picasso"`，则返回校验失败，并给出友好消息。
3. **业务规则服务**：对于更复杂的、可能动态变化的规则（如“夏日风格不宜搭配暖色系”），将其抽离到独立的`RuleEngine`或`ValidationService`中。在Controller或Service层，`DTO`基础校验通过后，再调用此服务进行业务规则校验。
4. **全局异常处理**：通过`@ControllerAdvice`和`@ExceptionHandler`捕获`MethodArgumentNotValidException`和自定义的业务校验异常，统一包装为结构化的错误响应体，包含错误字段、错误码和提示信息。



## 5. 场景：长文本总结API的设计与校验

**核心思路**：设计清晰的资源模型，并利用Spring的校验机制实现前置业务规则校验。

1. **API设计**：
   - **端点**：`POST /api/v1/summarize`
   - **请求体**：`{"originalText": "...", "style": "concise|detailed", "targetLength": 200, "language": "zh"}`
   - **响应**：`{"summary": "...", "originalLength": 1500, "reducedTo": "13%"}`
2. **校验实现**：
   - **Bean Validation**：在请求体DTO上，`originalText`用`@NotBlank`，`style`用`@Pattern`，`targetLength`用`@Min(1)`。
   - **跨字段校验**：跨字段校验：创建自定义注解 `@TargetLengthValid`，应用于类级别。在其校验器中，比较 `targetLength` 与 `originalText.length()`。如果 `targetLength` 更大，则添加一个指向 `targetLength` 字段的约束违规。
3. **执行流程**：Spring MVC 会在参数绑定阶段自动触发校验。失败时请求不会进入业务方法，直接返回400状态码及错误详情。校验通过后，业务方法可安全地认为 `targetLength <= originalText.length()`。



## 6. 场景：类型安全的AI消息对象体系

**核心思路**：使用继承和多态反序列化来构建类型安全的领域模型。

1. **基类与子类**：
   - 定义抽象基类 `Message`，包含公共字段：`role`（`String` 或` Enum`）、`timestamp`。
   - 定义具体子类：`TextMessage`（包含 `String content`）、`MultiModalMessage`（包含 `List<ContentItem> content`，`ContentItem` 可为 `TextItem` 或 `ImageItem`）、`SystemMessage`（可能包含 `String instruction`）。

2. **多态反序列化**： 在基类 `Message` 上使用 Jackson 注解 `@JsonTypeInfo(use = Id.NAME, property = "role")` 和 `@JsonSubTypes` 来指定 `role` 值为 `"user"` 时对应 `TextMessage`，`"assistant"` 且 `content` 为数组时对应 `MultiModalMessage` 等。这样，Jackson 能根据 JSON 中的 `role` 和 `content` 结构自动实例化正确的子类。

3. **处理 null content**： 对于 `content` 为 null 的情况，可以在子类的构造函数或 setter 方法中将其初始化为空字符串或空集合，避免后续 NPE。

4. **优势**： 业务代码中可以使用 `instanceof` 或访问子类特定方法，编译器能提供类型安全支持，避免大量类型转换和条件判断。



## 7. 场景：RAG答案引用片段的响应设计

**核心思路**： 设计平衡可读性与性能的数据结构，并考虑序列化优化。

1. **数据结构**：
   - 定义 `AnswerWithCitation` 响应对象，包含核心字段：`answer` (String)、`citations` (List`<Citation>`) 。
   - `Citation` 对象包含：`text` (引用片段原文)、`documentId`、`documentTitle`、`startIndex`、`endIndex`、`score` (置信度)。

2. **序列化考量**：
   - **性能**： 当引用片段上百个时，直接序列化整个列表可能使响应体庞大。可考虑**分页**或**折叠**：首次响应只包含前N个最重要的引用，其余可通过额外接口"按需加载"。
   - **数据量**： `startIndex` 和 `endIndex` 使用 `int` 而非 `String`。如果原文很长，可考虑只返回片段，而非要求客户端自己根据下标去截取。
   - **Jackson配置**： 默认情况下，Jackson序列化大型集合没问题。但对于极大规模（上千），可考虑启用 `WRITE_SINGLE_ELEM_ARRAYS_UNWRAPPED` 等优化，或使用 `@JsonView` 控制不同API场景下返回的字段。
3. **前端协同**： 此设计使前端能轻松实现高亮显示。前端根据 `startIndex` 和 `endIndex` 在对应的源文档视图中高亮文本，或将 `text` 直接嵌入答案中并做样式处理。



## 8. 场景：同一接口支持JSON和Protobuf响应

**核心思路**： 利用Spring的内容协商机制，并配置相应的消息转换器。

1. **内容协商**： Spring MVC内置内容协商。客户端通过 `Accept` 请求头指定期望的媒体类型（`application/json` 或 `application/x-protobuf`）。

2. **配置Protobuf支持**：
   - 添加依赖，如 `protobuf-java` 和 `protobuf-java-format`（用于JSON转换），或使用 `spring-protobuf` 集成库。
   - 定义一个Protobuf的 `.proto` 文件，编译生成Java类，对应你的响应数据结构。
   - 配置 `HttpMessageConverter`。通常需要注册一个处理 `application/x-protobuf` 的转换器（如 `ProtobufHttpMessageConverter`），它会自动将Controller返回的Protobuf `Message` 对象序列化为二进制流；同时注册一个处理 `application/json` 的转换器（如 `MappingJackson2HttpMessageConverter`），它会将Protobuf `Message` 对象转为JSON（需要额外的jackson-datatype-protobuf模块支持，或手动转换）。

3. **Controller实现**： Controller方法可以统一返回Protobuf生成的Java对象（`Message` 子类）。Spring会根据 `Accept` 头，自动选择上述配置的对应转换器来生成响应。

4. **关键点**： 确保两种格式的响应在语义上完全一致。Protobuf的二进制格式更省带宽，JSON更易调试。



## 9. 场景：复杂AI审核响应到内部模型的映射

**核心思路：** 使用MapStruct实现声明式、编译时安全的对象映射，避免手写冗长易错的赋值代码。

1. **定义模型**：
   - `VendorAuditResponse`：映射第三方审核服务的原始响应，字段可能嵌套很深，如 `{"results": [{"category": "violence", "score": 0.9, "tags": ["weapon"]}]}`。
   - `AuditResult`：内部简洁领域对象，如包含 `boolean blocked`、`String mainCategory`、`Double maxScore`、`List<String> keywords`。
2. **使用MapStruct**：
   - 定义Mapper接口，如 `AuditResponseMapper`，并使用 `@Mapper` 注解。
   - 在接口中声明映射方法，如 `AuditResult toAuditResult(VendorAuditResponse response)`。
   - 对于简单字段，MapStruct自动映射同名属性。对于复杂逻辑（如从 `results` 数组中找出最高分并提取对应分类），在接口中定义 `default` 方法或使用 `@AfterMapping` 注解的方法来实现自定义映射逻辑。
3. **优势：** MapStruct在编译时生成具体的映射实现类，无反射开销，性能接近手写代码，且类型安全。代码简洁，将复杂的转换逻辑封装在Mapper中，业务服务只需调用 `mapper.toAuditResult(response)`。



## 10. 场景：内部服务从v1 API到v2 API的无感迁移

**核心思路：** 在API网关或一个独立的适配器服务中，实现请求转换与响应适配。

1. **适配器位置：** 最佳位置是在调用方（旧内部服务）和被调用方（新AI服务）之间引入一个"适配器服务"，或修改现有的API网关/路由层。
2. **请求适配**：适配器拦截对 `/v1/chat`的调用，将其转换为对 `/v2/chat`的调用。这包括：
   - **URL重写：** 将端点改为 `/v2/chat`。
   - **请求体转换：** 如果参数结构变化，将旧的 `{"prompt": "..."}` 转换为新的 `{"messages": [{"role": "user", "content": "..."}]}`。
3. **响应适配：** 接收 `/v2/chat` 返回的 `{"choices": [...]}`，从中提取出 `response` 文本，包装成旧的 `{"response": "..."}` 格式，返回给调用方。
4. **实现方式**：
   - 可使用Spring Cloud Gateway的 `RewritePath` 和自定义过滤器。
   - 或创建一个简单的Spring Boot服务，使用 `RestTemplate` 或 `WebClient` 代理请求，并在其中实现转换逻辑。
5. **优势：** 调用方无需任何修改，迁移风险低。适配器本身可作为一个临时组件，待所有调用方升级后下线，或作为长期的多版本兼容层。



## 11. 场景：AI模型支持多种输出格式（JSON/XML）的动态格式化

**核心思路：** 利用 Spring 的内容协商机制与策略模式，实现响应格式的动态适配。

1. **策略接口定义：** 首先，定义一个 `ResponseFormatter` 策略接口，包含 `format(Object data)` 和 `supportedMediaType()` 方法。
2. **多格式实现：** 创建多个实现类，如 `JsonResponseFormatter`（可能直接依赖 Jackson）和 `XmlResponseFormatter`（可能使用 JAXB 或 Jackson 的 XML 模块）。每个实现类负责将其输入的对象转换为特定格式的字符串（或字节流）。
3. **与内容协商集成**：
   - **方案 A（自动）：** 利用 Spring MVC 的 `ContentNegotiationManager`。当 Controller 方法返回 `ResponseEntity` 或带有 `@ResponseBody` 的对象时，Spring 会根据请求的 `Accept` 头，自动查找匹配的 `HttpMessageConverter` 进行序列化。我们只需确保配置了对应的转换器（如 `MappingJackson2HttpMessageConverter` 和 `MappingJackson2XmlHttpMessageConverter`），而无需手动调用 `Formatter`。
   - **方案 B（手动 - 更灵活）：** 在 Controller 中，可以注入一个 `Map<String, ResponseFormatter>`（Key 为媒体类型）。解析请求的 `Accept` 头后，手动选择合适的 `Formatter` 对业务方法返回的 DTO 进行格式化，再通过 `ResponseEntity` 返回。这种方式对格式化过程有完全控制权，适合需要复杂自定义逻辑的场景。
4. **关键考量：** 方案 A 是更符合 Spring Boot 惯例、更省心的做法。方案 B 则提供了最大灵活性，例如可以在格式化前对数据做最后一次转换或过滤。



## 12. 场景：服务端Prompt模板解析与安全变量替换

**核心思路：** 设计一个包含编译（解析）和渲染（替换）两阶段的模板引擎，并严格防范注入。

1. **模板定义与解析：** 定义模板语法，如 `"请用{style}风格翻译：{text}"`。创建 `Template` 类，其 `compile` 方法能解析模板字符串，提取出所有变量名（`style`，`text`）和固定文本片段，生成一个内部表示（如 AST）。
2. **安全的变量替换**：
   - **上下文提供：** 渲染时，传入一个 `Map<String, Object>` 作为上下文。`Template` 的 `render` 方法遍历内部表示，遇到变量时从上下文中取值。
   - **防注入关键：** 绝对不能直接将用户输入作为模板的一部分进行 "编译"。变量替换是发生在 "值" 的位置，而非 "模板结构" 本身。对于从上下文中取出的值，应视其为纯文本数据，在插入前进行 HTML 编码（如果最终输出到 Web）或进行严格的 JSON 转义（如果用于构造 JSON 请求体给 AI）。
3. **增强特性：** 可支持默认值语法（`{name:default}`）和简单的过滤器（如 `{text|truncate:100}`）。这些应在编译阶段被识别，并在渲染阶段调用相应的工具方法处理。
4. **执行流程：** 管理员在后台配置模板。用户触发请求时，业务逻辑根据场景选择模板，并提供包含用户输入的上下文 Map，调用 `template.render(context)` 得到安全的最终 Prompt。



## 13. 场景：支持多协议的ModelEndpoint配置对象

**核心思路：** 使用继承或组合模式，配合 Jackson 的多态反序列化，实现类型安全的配置。

1. **基类与公共字段：** 定义抽象基类 `ModelEndpoint`，包含公共字段如 `modelId`、`name`、`vendor`、`apiKeyRef`（指向密钥仓库的引用）。
2. **协议特定子类**：
   - 定义 `HttpEndpoint extends ModelEndpoint`，增加 `url`、`timeout`、`headers` 等字段。
   - 定义 `GrpcEndpoint extends ModelEndpoint`，增加 `host`、`port`、`stubClass` 等字段。
3. **配置的反序列化：** 在配置中心（如 Nacos）或 YAML 文件中，使用一个 `type` 字段来区分协议。利用 Jackson 的 `@JsonTypeInfo` 等注解，使 Spring 在从配置源绑定到 `List<ModelEndpoint>` 时，能根据 `type` 值实例化正确的子类。
4. **运行时使用：** 系统初始化时，加载所有 `ModelEndpoint` 配置到一个注册表（`Map<String, ModelEndpoint>`）。当需要调用特定模型时，根据 `modelId` 从注册表获取端点配置。通过判断对象类型（`instanceof`）来获取协议特定信息，并初始化对应的客户端（如 `RestTemplate` 或 gRPC Stub）。
5. **优势：** 此设计将配置的结构与代码中的类型系统对齐，在编译期就能捕获许多配置错误（如为 gRPC 端点误填了 `url` 字段），并通过 IDE 获得良好的代码提示。



## 14. 场景：处理包含循环引用的数据结构序列化

**核心思路：** 通过 Jackson 注解控制序列化行为，打破循环，或改变数据表示方式。

1. **使用注解打破引用**：
   - `@JsonIgnore`：在循环引用的一侧（如 `Message` 的 `parent` 字段）上添加此注解，直接忽略该字段的序列化。简单粗暴，但会丢失这部分信息。
   - `@JsonManagedReference` 和 `@JsonBackReference`：这是一对注解。在 "主" 方（如 `Message` 的 `children` 列表）标注 `@JsonManagedReference`，在 "从" 方（如 `ChildMessage` 的 `parent` 字段）标注 `@JsonBackReference`。Jackson 在序列化时会序列化 `@JsonManagedReference` 方，而将 `@JsonBackReference` 方替换为对其 ID 的引用（或忽略），从而打破循环。这是处理父子关系的推荐方式。
2. **控制序列化深度：** 使用 `@JsonView` 定制不同场景下序列化的深度。例如，定义 `Views.Public` 和 `Views.Internal`。在内部深链路上使用 `Internal` 视图，在返回给前端时使用 `Public` 视图，并在 `Public` 视图中排除可能导致循环的嵌套字段。
3. **改变领域模型：** 有时循环引用是设计问题。考虑引入 DTO 进行序列化。在服务层，将领域模型转换为专为 API 设计的 `MessageDTO`，其中 `parent` 字段只包含 ID 而非完整对象，从而避免循环。这是最清晰、职责分离最彻底的方法。
4. **综合建议：** 对于 AI 对话树，常用方法是序列化时采用 "平铺列表" 而非嵌套树结构。每条消息包含自己的 `id` 和可选的 `parentId`。前端收到列表后，再根据 ID 关系在内存中构建树。这既避免了循环引用，也给了前端更大的处理灵活性。



## 15. 场景：分页查询历史对话及其最后消息摘要

**核心思路：** 设计高效的数据传输对象和查询策略，避免 N+1 查询问题。

1. **API 与 DTO 设计**：
   - 请求：`GET /conversations?page=0&size=20&sort=updatedAt,desc`
   - 响应：`Page<ConversationSummaryDTO>`，其中 `Page` 包含分页元数据，`ConversationSummaryDTO` 包含对话核心信息（`id`，`title`，`updatedAt` 等）以及一个嵌套的 `LastMessageSummaryDTO`（`content` 的摘要、`sender`、`sentAt`）。
2. **避免 N+1 查询的关键**：
   - **JPA (Hibernate) 方案：** 使用 `@EntityGraph` 注解在查询 `Conversation` 列表时，通过一条外连接（LEFT JOIN FETCH）语句同时加载关联的 "最后一条消息"。这需要你在 `Conversation` 实体中明确管理这个关联关系（如 `@OneToOne` 或通过 `@OrderBy` 和 `@OneToMany` 取第一个）。或者，编写自定义 JPQL 查询，直接进行 JOIN 并 SELECT 所需字段到 DTO 中。
   - **MyBatis 方案：** 在 Mapper XML 中编写单条 SQL，通过 `<collection>` 或 `<association>` 标签定义结果映射，一次查询即可将对话及其最后消息的数据映射到嵌套的 DTO 结构中。
3. **消息摘要生成：**`content` 的摘要可以在**写入时生成**（在保存消息时，同步或异步地生成其摘要并存入数据库），也可以在**查询时计算**（在 SQL 中使用 `SUBSTRING` 函数或数据库特定函数截取）。前者以空间换时间，能保证查询性能；后者更灵活，但可能对数据库造成计算压力。通常建议采用写入时生成的策略。
4. **性能：** 此设计确保无论分页大小是多少，都只需执行 1（或 2，包含 count 查询）条数据库查询，是高效的分页实现。



## 16. 场景：Swagger生成复杂泛型接口的准确文档

**核心思路：** 正确使用 Swagger（SpringDoc OpenAPI）的注解，明确描述包装类型和泛型参数。

1. **问题根源：** SpringDoc 默认可处理 `ResponseEntity<AiStreamResponse>`，但对于 `CompletableFuture<ResponseEntity<AiStreamResponse>>` 这种多层包装，其内置的类型解析器可能无法准确推断出最终的 `AiStreamResponse` 模型。

2. **解决方案 - 使用 @Operation 和 @ApiResponse**：

   - 在 Controller 方法上，使用 `@Operation` 注解描述接口。
   - 使用 `@ApiResponse` 注解的 `content` 属性，明确指定成功响应（`responseCode = "200"`）的媒体类型和对应的 Schema 模型。关键是：`@Content(schema = @Schema(implementation = AiStreamResponse.class))`。
   - 通过 `@Schema(implementation = ...)` 明确告诉 SpringDoc，无论外层有多少层包装（`CompletableFuture`，`ResponseEntity`，`Mono` 等），最终的响应体模型都是 `AiStreamResponse`。

3. **示例代码：**

   ```
   @Operation(summary = "流式对话")
   @ApiResponse(responseCode = "200", description = "成功",
   						 content = @Content(mediaType = MediaType.TEXT_EVENT_STREAM_VALUE,
                                   schema = @Schema(implementation = AiStreamResponse.class)))
   @GetMapping("/stream")
   public CompletableFuture<ResponseEntity<Flux<AiStreamResponse>>> streamChat() {
   		// ...
   }
   ```

4. **验证：** 启动服务后，访问 `/v3/api-docs` 端点或 Swagger UI 界面，查看生成的 OpenAPI Spec，确认 `/stream` 接口的 200 响应 Schema 正确引用了 `AiStreamResponse` 的定义。



## 17. 场景：A/B测试信息的无侵入式透传

**核心思路：** 利用 `ThreadLocal` 和 Spring MVC 拦截器，在请求处理链的起始端保存信息，在终端（客户端或日志）获取信息，实现跨层透传。

1. **上下文持有器：** 创建一个 `AbTestContextHolder` 类，内部包含 `private static final ThreadLocal<AbTestContext> contextHolder = new ThreadLocal<>();`。`AbTestContext` 是一个简单的 POJO，包含 `experimentId`、`groupId` 等字段。
2. **信息提取与设置**：
   - 来源：信息可以来自请求头（如 `X-Experiment-ID`）、Cookie 或网关注入的参数。
   - 时机：创建一个实现 `HandlerInterceptor` 的 `AbTestInterceptor`，在其 `preHandle` 方法中，从 `HttpServletRequest` 中提取这些信息，封装为 `AbTestContext` 对象，并设置到 `AbTestContextHolder` 中。
3. **信息使用**：
   - **记录日志**：在日志框架的 MDC（Mapped Diagnostic Context）中放入这些信息，这样同一线程的所有日志都会自动带上实验标记。
   - **透传给 AI 服务**：在构造调用 AI 服务的客户端时（如 `RestTemplate` 或 `WebClient`），可以从 `AbTestContextHolder` 中获取信息，将其添加为请求头。
   - **业务逻辑分流**：在 Service 层，可以通过 `AbTestContextHolder` 获取分组信息，执行不同的业务逻辑。
4. **信息清理：** 在 `AbTestInterceptor` 的 `afterCompletion` 方法中，务必调用 `AbTestContextHolder.clear()`，防止线程池复用导致信息泄露。
5. **异步场景：** 如果涉及 `@Async` 或响应式编程，需要将 `ThreadLocal` 中的上下文手动传递到新线程或上下文（可使用 `TaskDecorator` 或 `Context` 传播机制）。



## 18. 场景：文件上传与附加文本指令的接口设计

**核心思路：** 合理设计 `multipart/form-data` 的请求结构，并在服务端进行统一解析。

1. **请求体设计**：前端构造一个 `FormData`对象，包含以下部分：
   - `file`：类型为 `File`，对应上传的文件。
   - `instruction`：类型为 `String`，对应文本指令。
   - `parameters`：类型为 `String`（JSON 字符串），对应其他处理参数（如 `{"mode": "extract"}`）。
2. **服务端接收 - @RequestPart**：
   - 在 Controller 方法中，使用 `@RequestPart("file") MultipartFile file` 来接收文件。
   - 使用 `@RequestPart("instruction") String instruction` 来接收指令字符串。
   - 使用 `@RequestPart("parameters") Parameters params` 来接收参数。这里 `Parameters` 可以是一个自定义的 DTO 类，Spring 会使用配置的 `HttpMessageConverter`（通常是 `MappingJackson2HttpMessageConverter`）将 JSON 字符串部分自动反序列化为该 DTO 对象。关键是确保请求的 `Content-Type` 为 `multipart/form-data`，且每个 part 的 `Content-Disposition` 正确。
3. **服务端接收 - 统一对象：** 另一种更简洁的方式是定义一个 `FileProcessRequest` DTO，包含 `MultipartFile file`、`String instruction`、`Parameters params` 三个字段，并用 `@ModelAttribute` 接收。Spring 会尝试将请求的各个 part 绑定到该对象的对应字段上。这种方式更面向对象，但需要确保字段名与 part 名一致。
4. **处理：** 接收到所有部分后，业务逻辑可以将文件内容（字节流或 Base64）、指令和参数组合，构造发送给 AI 服务的请求。



## 19. 场景：根据配置动态选择ModelService实现

**核心思路：** 利用 Spring 的 `@Conditional` 系列注解，基于配置文件决定 Bean 的创建。

1. **定义配置属性：** 在 `application.yml` 中定义属性，如 `ai.vendor.active: openai`。
2. **创建条件注解**：
   - **方案 A（使用内置注解）：** 在每个 `ModelService` 的实现类上，使用 `@ConditionalOnProperty(name = "ai.vendor.active", havingValue = "openai")`。这样，只有当配置匹配时，对应的实现类才会被实例化为 Spring Bean。
   - **方案 B（自定义条件）：** 创建自定义注解 `@ConditionalOnVendor`，并在其关联的 `Condition` 实现类中读取配置，进行更复杂的判断逻辑。
3. **注入与使用：** 在需要 `ModelService` 的类中，使用 `@Autowired` 或构造函数注入。因为最终只有**一个**满足条件的实现类被注册为 Bean，所以 Spring 可以成功完成依赖注入。如果配置错误导致没有或超过一个 Bean，启动时会报错。
4. **备选方案 - @Primary 与 @Qualifier：** 如果不希望用条件注解控制 Bean 的存在，也可以将所有实现都注册为 Bean，但为默认实现标注 `@Primary`。在其他地方注入时，通过 `@Qualifier("openaiModelService")` 来指定。这种方式更灵活，允许运行时存在多个 Bean，但需要注入方明确知道要哪个。
5. **推荐：** 对于 "根据全局配置选择唯一实现" 的场景，`@ConditionalOnProperty` 方案更清晰、更安全，能避免误注入。



## 20. 场景：实现AI模型列表接口的条件请求（ETag）

**核心思路：** 计算响应资源的版本标识（ETag），并在请求处理中实现条件逻辑判断。

1. **生成 ETag**：
   - **强验证：** 计算模型列表数据的哈希值（如 MD5 或 SHA-256）。由于模型列表可能来自数据库和动态配置，需要将它们聚合并序列化为一个确定的字节序列（如 JSON 字符串），再计算哈希。此哈希值作为 ETag。任何数据变化都会导致 ETag 改变。
   - **弱验证：** 如果允许细微的、语义不变的变化（如字段顺序改变），可以使用弱 ETag（以 `W/` 开头），通常基于数据的最后修改时间戳等。
2. **实现条件 GET**：
   - 在 Controller 方法中，注入 `WebRequest` 或 `HttpServletRequest`。
   - 首先，计算当前数据的 ETag（如 `currentETag`）。
   - 然后，检查请求头 `If-None-Match`。如果存在且其值包含 `currentETag`（ETag 比较需处理 `*` 和多个值的情况），则说明客户端缓存有效。此时，应返回状态码 `304 Not Modified`，且响应体为空。
   - 如果 ETag 不匹配或请求头不存在，则正常执行查询，将数据列表和 `ETag: currentETag` 响应头一并返回。
3. **性能优化：** 计算模型列表的完整哈希可能很重。一个优化策略是：为模型列表创建一个 "版本号" 字段，每当列表变化（管理员增删改）时，递增此版本号。将此版本号作为 ETag。这样，ETag 的生成和比较就变得非常轻量。`WebRequest.checkNotModified(version)` 方法可以简化此逻辑。
4. **Spring 的快捷支持：** Spring MVC 的 `Controller` 方法可以返回 `ResponseEntity`，并使用其 `eTag` 方法来设置 ETag。但更自动化的方式是，结合 `ShallowEtagHeaderFilter`（为响应体生成 ETag，但无法避免业务计算）或使用 Spring Data REST 等高级框架的支持。对于自定义业务，手动实现如步骤 2 所述更为常见和可控。


