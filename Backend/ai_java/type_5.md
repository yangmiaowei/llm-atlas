# 类别五：工程化、运维与可观测性



## 1. 场景：我们需要在Kubernetes中部署AI代理服务，该服务需要访问多个外部AI API。请设计ConfigMap和Secret来管理不同环境的配置（如API端点、密钥），并描述如何通过环境变量或Volume挂载到Pod中。

**核心思路**：

1. **配置分类**：将配置分为两类：非敏感的配置（如API端点、超时时间、重试策略等）使用ConfigMap管理；敏感的配置（如API密钥、访问令牌等）使用Secret管理。
2. **ConfigMap设计**：
   - 为每个外部AI服务定义配置项，例如`openai.base-url`、`openai.timeout`、`anthropic.base-url`等。
   - 可以按环境（开发、测试、生产）创建不同的ConfigMap，或使用同一个ConfigMap但通过Kustomize或Helm在不同环境部署时替换值。
3. **Secret设计**：
   - 每个AI服务的API密钥以Secret存储，使用base64编码（注意：base64不是加密，需配合RBAC确保安全）。
   - 例如创建名为`ai-api-secrets`的Secret，包含`openai-api-key`、`anthropic-api-key`等键。
4. **挂载方式**：
   - 环境变量：在Pod的容器配置中，通过`valueFrom`引用ConfigMap和Secret的键值。例如，将`openai.base-url`和`openai-api-key`分别设置为环境变量`OPENAI_BASE_URL`和`OPENAI_API_KEY`。这种方式简单，但配置更新后需要重启Pod才能生效。
   - Volume挂载：将ConfigMap和Secret以文件形式挂载到容器内。ConfigMap和Secret的每个键值对都会成为一个文件，键是文件名，值是文件内容。应用程序可以通过读取文件来获取配置。这种方式支持动态更新：更新ConfigMap或Secret后，Kubernetes会自动更新Volume中的文件（有一定延迟），应用程序可以监听文件变化并重新加载配置。
5. **实践建议**：对于AI代理服务，通常配置不会频繁变动，使用环境变量方式更简单。但如果配置项很多，或者希望支持不重启Pod更新配置，可以使用Volume挂载。注意Secret挂载需要确保文件权限，避免泄漏。



## 2. 场景：请设计一个完整的Java应用监控指标方案，使用Micrometer暴露给Prometheus。需要包含哪些关键指标？（如：各AI接口的QPS、P99延迟、Token消耗速率、不同状态码的计数、JVM内存和线程池状态）。

**核心思路**：

1. **集成 Micrometer**：在 Spring Boot 应用中添加 `micrometer-registry-prometheus` 依赖，并配置 Prometheus Registry。通过 `/actuator/prometheus` 端点暴露指标。
2. **关键指标设计**：
   - **HTTP 请求指标**：利用 Micrometer 的 `@Timed` 注解或自动配置，记录每个 AI 接口的请求数（QPS）、延迟分布（包括 P50、P95、P99）、响应状态码计数。这些指标可以按接口路径、HTTP 方法、状态码等维度标签（tag）区分。
   - **自定义业务指标**：
     - Token 消耗：使用 `Counter` 或 `Timer` 记录每次 AI 调用的请求 Token 数和响应 Token 数，并计算总和、速率。可以按 AI 模型、用户等打标签。
     - 成本指标：根据 Token 消耗和模型单价，计算每次调用的成本，使用 `Counter` 累加。
   - **JVM 指标**：Micrometer 自动提供 JVM 内存使用、线程状态、GC 次数和时间、类加载数等。
   - **线程池指标**：如果使用了线程池（如异步调用 AI），可以使用 `ExecutorServiceMetrics` 监控线程池队列大小、活跃线程数、完成任务数等。
   - **缓存指标**：如果使用了缓存（如 Caffeine），可以暴露缓存命中率、大小等。
   - **数据库连接池指标**：如 HikariCP，提供连接数、空闲连接、使用中连接等。
3. **指标标签设计**：合理使用标签（如 `model`、`endpoint`、`status`）以便于筛选和聚合，但避免标签值基数过高（如用户 ID）导致指标爆炸。
4. **暴露端点**：确保 Spring Boot Actuator 的 `/actuator/prometheus` 端点开放，并配置 Prometheus 抓取。
5. **Grafana 展示**：在 Grafana 中创建 Dashboard，将上述指标可视化，设置必要的告警阈值。



## 3. 场景：当AI服务调用发生大量超时或4xx/5xx错误时，需要触发告警。请描述如何在Prometheus中配置相关的告警规则（Alerting Rule），并通过Alertmanager将通知发送到钉钉/企业微信。

**核心思路**：

1. **定义Prometheus告警规则**：在Prometheus的配置文件中定义告警规则文件，或通过Prometheus Operator的`PrometheusRule`资源定义。告警规则基于指标和条件。

2. **关键告警规则**：
   
   - **错误率告警**：计算一段时间内（如5分钟）AI接口调用错误（状态码为5xx或超时）的比例。例如，当错误率超过5%时触发告警。
   
     ```
     expr: sum(rate(http_client_requests_seconds_count{job="ai-proxy", status=~"5.."}[5m])) / sum(rate(http_client_requests_seconds_count{job="ai-proxy"}[5m]))
     ```
   
   - **超时告警**：可以基于延迟百分位数，例如P99延迟超过10秒。
   
     ```
     expr: histogram_quantile(0.99, rate(http_client_requests_seconds_bucket{job="ai-proxy"}[5m])) > 10
     ```
   
   - 连续错误计数：也可以使用`increase`函数统计错误数量的增长。
   
3. **告警规则注解**：为每个告警规则添加注解，描述告警内容、建议处理措施，并设置标签（如`severity: warning`）。

4. **Alertmanager配置**：在Alertmanager中配置路由（route）和接收器（receiver）。将告警路由到钉钉或企业微信的Webhook接收器。

5. **集成钉钉/企业微信**：
   
   - 钉钉：创建钉钉群机器人，获取Webhook地址。在Alertmanager中配置`webhook`接收器，指向该地址，并按照钉钉的消息格式构造请求体。
   - 企业微信：类似，创建企业微信机器人，获取Webhook地址，配置接收器。
   
6. **告警分组与抑制**：在Alertmanager中设置合理的分组、抑制和静默规则，避免告警风暴。



## 4. 场景：请为AI网关服务设计结构化日志。日志中应包含哪些关键字段（如traceId，userId，model，promptLength，responseLength，latency，costTokens，statusCode）？如何与ELK（Elasticsearch, Logstash, Kibana）栈集成进行日志分析？

**核心思路**：

1. **结构化日志格式**：使用JSON格式记录日志，每个日志事件是一个JSON对象。关键字段包括：
   - `timestamp`：日志时间戳。
   - `level`：日志级别（INFO、ERROR等）。
   - `logger`：日志记录器名称。
   - `message`：简要描述。
   - `traceId`：分布式追踪ID，用于串联一次请求的所有日志。
   - `spanId`：当前跨度ID。
   - `userId`：用户标识。
   - `model`：调用的AI模型。
   - `promptLength`：提示词长度（字符数或Token数）。
   - `responseLength`：响应长度。
   - `latency`：请求耗时（毫秒）。
   - `costTokens`：本次调用消耗的Token总数（请求+响应）。
   - `statusCode`：HTTP状态码或业务状态码。
   - `error`：错误详情（如果有）。
   - 其他业务相关字段。
2. **日志输出**：使用Logback或Log4j2，并配置JSON编码器（如 `logstash-logback-encoder`）将日志输出为JSON格式。日志可以输出到控制台（stdout）或文件。
3. **ELK集成**：
   - **收集**：在Kubernetes中，通常使用Fluentd或Filebeat作为日志收集代理，监控Pod的stdout，将日志发送到Logstash或直接到Elasticsearch。
   - **传输**：Logstash可以对日志进行过滤、解析和转换，然后输出到Elasticsearch。
   - **存储与索引**：Elasticsearch存储日志，并建立索引。建议按时间创建索引（如 `logs-ai-gateway-YYYY.MM.DD`），便于管理和清理。
   - **可视化**：在Kibana中创建索引模式，然后可以搜索日志、创建Dashboard，例如：统计各模型的平均延迟、错误率，追踪特定用户的请求等。

4. **日志采样**：对于高流量服务，全量日志可能成本过高，可以考虑对成功请求采样记录，但错误请求全量记录。

   

## 5. 场景：你需要实现一个“动态功能开关”，在不重启服务的情况下，控制某些AI功能（如“启用DeepSeek模型”、“使用新的Prompt模板”）的开启或关闭。请基于配置中心或数据库实现此开关，并保证在集群中快速生效。

**核心思路**：

1. **开关存储**：将功能开关配置存储在配置中心（如Nacos、Apollo）或数据库中。配置中心支持实时推送，数据库则需要结合定时轮询或变更监听。
2. **开关设计**：每个功能开关有唯一键（如 `feature.deepseek.enabled`），值为布尔类型，还可以包含其他配置（如新Prompt模板的内容）。
3. **客户端实现**：
   - 如果使用配置中心，利用其提供的Java客户端，注册监听器，当开关配置变更时，客户端会收到通知，更新本地内存中的开关值。
   - 如果使用数据库，可以定时（如每30秒）查询开关表，或者使用数据库的CDC（变更数据捕获）工具（如Debezium）将变更发布到消息队列，服务监听消息更新开关。
4. **开关使用**：在代码中，通过一个 `FeatureToggleService` 获取开关状态，根据状态决定是否启用新功能。注意开关变更后，已经存在的请求可能仍然使用旧逻辑，新请求才使用新逻辑，这通常是可接受的。
5. **灰度发布**：开关可以支持更复杂的策略，如按用户ID、租户、流量百分比等灰度开启。这需要开关配置包含灰度规则，客户端根据当前请求上下文判断是否启用。
6. **降级**：当配置中心或数据库不可用时，服务应使用最后一次正确的配置或默认配置，保证可用性。



## 6. 场景：我们的AI应用依赖一个内部的“敏感词过滤”服务。请设计一个健康检查接口（/actuator/health的扩展），能检测该依赖服务的状态，并在其不可用时将应用整体健康状态标记为DOWN或OUT_OF_SERVICE。

**核心思路**：

1. **Spring Boot Actuator健康检查扩展**：Spring Boot Actuator的 `/actuator/health` 端点可以聚合多个健康指示器（HealthIndicator）。我们可以实现一个自定义的 `HealthIndicator` 来检查敏感词过滤服务的状态。
2. **自定义HealthIndicator实现**：创建类实现 `HealthIndicator` 接口，在 `health()` 方法中调用敏感词过滤服务的健康检查接口（或一个简单的测试接口）。根据调用结果返回 `Health.up()` 或 `Health.down()`。还可以记录详细的错误信息。
3. **健康检查策略**：为了避免对依赖服务造成压力，健康检查可以缓存结果，每隔一段时间（如30秒）检查一次，而不是每次请求 `/actuator/health` 都去调用。同时，健康检查调用应该设置超时时间。
4. **应用整体健康状态**：Spring Boot会根据所有 `HealthIndicator` 的结果聚合应用整体状态。默认情况下，只要有一个组件是 `DOWN`，整体状态就是 `DOWN`。也可以通过配置 `management.health.status.order` 来调整，例如将敏感词过滤服务标记为 `OUT_OF_SERVICE`，而不影响整体为 `DOWN`。
5. **集成到Kubernetes就绪探针**：可以将 `/actuator/health` 用作Kubernetes的readinessProbe。当敏感词过滤服务不可用时，应用健康状态变为 `OUT_OF_SERVICE`，Kubernetes会将Pod从服务负载均衡中移除，避免请求被路由到该Pod。



## 7. 场景：请设计CI/CD流水线（如GitLab CI），实现：代码提交时触发代码规范检查、单元测试、集成测试（使用Testcontainers模拟Redis等）、构建Docker镜像、安全扫描，并自动部署到测试环境。

**核心思路**：

1. **流水线阶段划分**：在GitLab CI配置文件中定义多个阶段（stage），例如：`build`、`test`、`security-scan`、`docker-build`、`deploy-to-test`。
2. **各阶段任务**：
   - **代码规范检查**：在 `build` 阶段，使用Maven插件（如checkstyle、pmd）或SpotBugs进行代码规范检查。
   - **单元测试**：在 `test` 阶段，运行单元测试，生成测试报告。
   - **集成测试**：在 `test` 阶段，使用Testcontainers启动Redis等依赖服务，运行集成测试。Testcontainers会管理容器的生命周期。
   - **安全扫描**：在 `security-scan` 阶段，使用OWASP Dependency-Check扫描依赖漏洞，或使用Trivy扫描镜像漏洞。
   - **构建Docker镜像**：在 `docker-build` 阶段，使用Dockerfile构建镜像，并推送到镜像仓库（如GitLab Container Registry）。
   - **自动部署到测试环境**：在 `deploy-to-test` 阶段，使用kubectl或Helm将新镜像部署到测试环境的Kubernetes集群。
3. **触发条件**：配置流水线在代码提交到特定分支（如develop）时触发，或者合并请求时触发。
4. **环境变量与凭证**：敏感信息（如镜像仓库密码、Kubernetes凭证）存储在GitLab CI的Variables中，并设置为Protected。
5. **测试报告与制品**：将测试报告和构建的镜像作为制品（artifacts）保存，便于查看。
6. **优化**：可以使用缓存（cache）加速依赖下载，使用 `only` / `except` 控制任务执行条件。



## 8. 场景：AI服务的API密钥需要定期轮换以提高安全性。请设计一个自动化的轮换方案：如何生成新密钥、更新到配置中心、并让所有服务实例无感知地、平滑地切换到新密钥（避免在轮换期间出现请求失败）？

**核心思路**：

1. **密钥轮换策略**：为每个AI服务配置两个密钥：当前使用的密钥（active）和即将启用的密钥（standby）。密钥轮换时，先生成新密钥，将其设置为standby，然后逐步将流量切换到新密钥，最后废弃旧密钥。
2. **密钥存储**：将密钥存储在配置中心（如Nacos、Spring Cloud Config）或专用的密钥管理服务（如HashiCorp Vault）。每个密钥有版本标识。
3. **轮换流程**：
   - 生成新密钥：通过AI服务提供商的控制台或API生成新密钥。
   - 更新配置：将新密钥写入配置中心，标记为standby，旧密钥保持active。此时服务实例会收到配置变更通知，加载新密钥，但继续使用active密钥。
   - 切换流量：通过动态配置，将服务实例使用的密钥从active切换到standby。可以分批次进行：先更新一部分实例，观察是否有错误，再全部切换。
   - 验证与清理：确认新密钥工作正常后，删除旧密钥，并将新密钥设为active。
4. **客户端实现**：在AI客户端中，支持多个密钥，并根据配置选择当前使用的密钥。当配置变更时，客户端可以同时持有新旧两个密钥，并在请求失败时尝试另一个密钥（自动重试）。
5. **监控**：轮换过程中，监控AI调用错误率，如有异常立即回滚。
6. **自动化脚本**：编写脚本自动执行上述步骤，并结合审批流程（如人工确认）提高安全性。



## 9. 场景：在微服务调用链中，如何集成OpenTelemetry来实现分布式追踪？请描述从网关接收请求，到调用业务服务，再到调用AI服务，这个过程中Trace和Span是如何传递和记录的。

**核心思路**：

1. **OpenTelemetry集成**：在每个微服务中添加OpenTelemetry的Java agent或通过依赖库集成。配置TracerProvider，定义采样率、导出器（如导出到Jaeger或Zipkin）。
2. **Trace上下文传递**：
   - 网关接收到客户端请求时，如果请求中没有Trace上下文，则创建一个新的Trace（生成TraceId），并创建第一个Span（代表网关处理）。如果已有Trace上下文（例如客户端已生成），则继续使用。
   - 网关调用业务服务时，通过HTTP头（如 `traceparent`、`tracestate`）将TraceId和SpanId传递给业务服务。
   - 业务服务从HTTP头中提取Trace上下文，创建新的Span（作为网关Span的子Span）。
   - 业务服务调用AI服务时，同样将Trace上下文注入到HTTP头中，AI服务创建另一个子Span。
3. **Span记录**：每个Span记录操作名称、开始时间、结束时间、标签（如HTTP方法、URL、状态码）、事件和异常。例如，业务服务调用AI服务的Span会记录AI服务的端点、请求参数、响应状态、耗时等。
4. **导出与可视化**：每个服务将Span数据导出到收集器（如OpenTelemetry Collector），然后转发到后端存储（如Jaeger、Zipkin、Elasticsearch），最后通过UI（如Jaeger UI）查看完整的调用链。
5. **自动注入**：使用OpenTelemetry的自动instrumentation库，可以无侵入地为常用框架（如Spring MVC、WebClient、RestTemplate）添加追踪。



## 10. 场景：我们的Spring Boot应用引入了多个AI SDK，导致JAR包体积巨大。请给出优化方案：如何通过依赖分析、排除未使用的传递依赖、以及使用spring-boot-thin-launcher来减小镜像大小？

**核心思路**：

1. **依赖分析**：使用Maven的 `dependency:tree` 命令分析依赖树，找出哪些传递依赖是不必要的。特别关注AI SDK可能引入了大型依赖（如完整的Python运行时、本地库）。尝试排除不需要的传递依赖，例如某个SDK引用了多个HTTP客户端，但只需要一个。
2. **选择轻量级替代**：检查是否有更轻量级的替代SDK，或者是否可以直接使用HTTP客户端调用AI服务的API，而不使用官方SDK。
3. **使用Spring Boot Thin Launcher**：Spring Boot Thin Launcher将应用本身和依赖分离开打包。应用JAR很小，依赖在运行时从Maven仓库下载或从本地缓存加载。这样可以减小Docker镜像的大小，因为依赖可以被缓存层共享。
   - 配置：在pom.xml中添加 `spring-boot-thin-maven-plugin`，并设置 `thin.output` 目录。
   - 构建：使用 `mvn package` 会生成一个thin JAR，同时生成一个 `thin.properties` 文件列出所有依赖。
   - 运行：通过 `java -Dthin.root=. -jar app.jar` 运行，launcher会自动下载依赖。
4. **Docker镜像优化**：
   - 使用多阶段构建：第一阶段用Maven构建，第二阶段只复制thin JAR和依赖列表，然后运行。
   - 使用Alpine Linux基础镜像减小体积。
   - 注意：Thin Launcher在第一次运行时会下载依赖，可能导致启动变慢，但后续启动会利用缓存。可以在构建镜像时预下载依赖。
5. **模块化设计**：如果应用功能复杂，可以考虑拆分为多个微服务，每个服务只引入必要的SDK。



## 11. 场景：请设计一个金丝雀发布（Canary Release）方案：新版本AI服务先部署一个实例，将10%的流量导入这个新实例，监控其错误率和延迟。若无异常，再逐步增加流量比例。如何实现流量切分（如通过网关的权重路由）？

**核心思路**：

1. **部署策略**：在Kubernetes中部署新版本AI服务的一个Pod，与旧版本Pod共存。通过Service或Ingress将流量按权重路由到新旧版本。
2. **流量切分**：
   - 使用服务网格（如Istio）：定义VirtualService，设置路由规则，将10%的流量路由到新版本，90%到旧版本。
   - 使用API网关（如Spring Cloud Gateway、Nginx Ingress）：配置权重路由，根据权重将请求分发到不同版本的服务实例。
   - 使用负载均衡器（如Ribbon）配合自定义规则，但权重路由支持不如前两者。
3. **监控与评估**：收集新版本Pod的监控指标，包括错误率、延迟、CPU/内存使用率等。设置评估标准，例如错误率<1%、P99延迟<2秒。观察一段时间（如30分钟）。
4. **逐步发布**：如果新版本符合标准，逐步增加流量比例，例如30%、50%、100%。每个阶段都需要观察和评估。
5. **回滚策略**：如果新版本出现异常，立即将流量切回旧版本，并回滚新版本的部署。可以通过快速修改路由规则实现。
6. **用户体验**：为了保持用户体验一致性，同一用户的请求应尽量路由到同一版本（会话亲和性），但金丝雀发布通常不要求，因为要测试新版本的普遍表现。
7. **自动化**：结合CI/CD流水线，自动化金丝雀发布流程，包括部署、流量切换、监控和决策。



## 12. 场景：AI模型文件（如.onnx，.bin）很大，不适合打包进Docker镜像。在K8s部署时，如何通过InitContainer或持久化卷（Persistent Volume）在Pod启动时下载模型文件到本地？

核心思路：

1. **模型存储**：将模型文件存储在对象存储（如S3、MinIO）或模型仓库中。模型文件按版本管理。
2. **使用InitContainer下载模型**：
   - 在Pod定义中，添加一个InitContainer，该容器使用包含下载工具（如awscli、wget）的镜像。
   - InitContainer通过命令行工具从对象存储下载模型文件到共享的Volume中。
   - 主容器启动时，从该Volume读取模型文件。
3. **使用持久化卷（PV）和持久化卷声明（PVC）**：
   - 创建PVC，动态或静态供给PV。
   - Pod挂载该PVC到模型目录。
   - InitContainer将模型下载到PVC中，主容器从同一PVC读取。
4. **缓存与共享**：如果多个Pod需要使用相同的模型，可以使用ReadWriteMany（RWX）的存储卷，让多个Pod共享同一份模型文件，避免重复下载。但需要注意模型文件的只读性，避免被修改。
5. **版本管理**：模型文件可以按版本存储在不同的路径。Pod启动时，根据配置的模型版本下载对应的文件。可以通过环境变量或ConfigMap传递模型版本。
6. **下载重试与校验**：InitContainer下载模型时，应该校验文件完整性（如MD5），如果下载失败，Pod启动失败，Kubernetes会重启Pod，重新下载。
7. **预热**：可以在部署前预先将模型文件下载到节点本地，然后使用HostPath卷，但这样增加了节点耦合，不推荐。
8. **边车容器（Sidecar）模式**：也可以使用Sidecar容器持续监听模型更新，但初始化下载使用InitContainer更简单。



## 13. 场景：你需要编写一个集成测试，验证“从用户提问到收到AI回复”的完整流程。请描述如何用@SpringBootTest和Mock Server（如MockWebServer）来模拟外部AI服务的响应。

**核心思路**：

1. **测试目标**：验证业务服务能够正确处理用户提问，调用AI服务，并返回正确的响应。

2. **使用MockWebServer**：MockWebServer是OkHttp提供的一个库，可以模拟HTTP服务器。在测试中启动MockWebServer，并让其监听一个随机端口。然后，将业务服务中AI客户端的Base URL指向MockWebServer的地址。

3. **测试步骤**：

   - 使用 `@SpringBootTest` 启动Spring Boot应用，但通过 `@TestConfiguration` 覆盖AI客户端的Bean，将其Base URL指向MockWebServer。
   - 在测试方法中，通过MockWebServer定义期望的请求和响应。例如，当收到POST请求到 `/v1/chat/completions` 时，返回一个模拟的AI响应JSON。
   - 调用业务服务的接口，传入用户提问。
   - 验证业务服务返回的结果是否符合预期，同时可以验证MockWebServer是否收到了预期的请求（如请求体、请求头）。

4. **模拟异常情况**：可以测试AI服务返回错误、超时等情况，验证业务服务的容错逻辑。

5. **清理**：每个测试结束后，关闭MockWebServer。

6. **示例代码结构**：

   ```
   @SpringBootTest
   class AIServiceIntegrationTest {
       @Autowired
       private MyService myService;
   
       private MockWebServer mockWebServer;
   
       @BeforeEach
       void setup() throws IOException {
           mockWebServer = new MockWebServer();
           mockWebServer.start();
           // 将AI客户端Base URL指向mock server
           String baseUrl = String.format("http://localhost:%s", mockWebServer.getPort());
           // 通过@TestPropertySource设置属性，或者通过@MockBean替换AI客户端
       }
   
       @Test
       void testFullProcess() {
           // 准备模拟响应
           String mockResponse = "...";
           mockWebServer.enqueue(new MockResponse()
                   .setBody(mockResponse)
                   .addHeader("Content-Type", "application/json"));
   
           // 调用业务服务
           String result = myService.processUserQuestion("Hello");
   
           // 验证结果
           assertThat(result).isEqualTo("expected response");
           // 验证请求
           RecordedRequest request = mockWebServer.takeRequest();
           assertThat(request.getPath()).isEqualTo("/v1/chat/completions");
       }
   
       @AfterEach
       void tearDown() throws IOException {
           mockWebServer.shutdown();
       }
   }
   ```

7. **Testcontainers结合**：如果需要测试真实数据库等，可以结合Testcontainers启动数据库容器。但AI服务用MockWebServer模拟。



## 14. 场景：请设计一个优雅关机的处理逻辑。在收到SIGTERM信号时，应用应：1）停止接收新请求；2）等待正在处理的AI流式请求完成或超时；3）关闭连接池；4）然后退出。如何在Spring Boot中实现？

**核心思路**：

1. **监听停机信号**：Spring Boot支持优雅关机，通过 `server.shutdown=graceful` 开启。在application.properties中设置 `spring.lifecycle.timeout-per-shutdown-phase=30s`，定义关机阶段超时时间。
2. **停止接收新请求**：当应用收到SIGTERM信号，Spring Boot会开始优雅关机流程。首先，Web服务器停止接收新请求，但继续处理正在进行中的请求。
3. **等待处理中的请求完成**：对于同步请求，Spring Boot会等待其完成。但对于异步请求（如流式响应），需要特殊处理：
   - 对于流式响应，服务器会尝试完成响应，但客户端可能断开连接。可以设置一个超时时间，超过后强制关闭。
   - 对于正在进行的AI流式请求，可以在业务代码中监听关机事件，尝试完成或中断处理。例如，在 `@PreDestroy` 方法中，等待流式请求完成，或者向AI服务发送取消请求。
4. **关闭连接池**：Spring Boot会自动关闭DataSource等连接池。如果有自定义的连接池（如HTTP客户端连接池），需要实现 `DisposableBean` 或在 `@PreDestroy` 方法中关闭。
5. **自定义关机逻辑**：可以实现 `SmartLifecycle` 或 `ApplicationListener<ContextClosedEvent>`，在Spring上下文关闭时执行自定义清理。例如，关闭AI客户端、释放模型资源等。
6. **超时控制**：如果等待时间超过配置的超时时间，Spring Boot会强制关闭。需要根据业务设置合理的超时时间。
7. **Kubernetes配合**：在Kubernetes中，Pod的 `terminationGracePeriodSeconds` 应大于Spring Boot的优雅关机超时时间，以确保应用有足够时间完成关机。
8. **示例配置**：

```
server.shutdown=graceful
spring.lifecycle.timeout-per-shutdown-phase=30s
```

9. **测试**：可以通过发送SIGTERM信号测试优雅关机是否正常工作。



## 15. 场景：如何监控AI调用成本？请设计一个指标，实时计算每分钟的Token消耗费用（假设不同模型单价不同），并通过Grafana面板展示费用趋势和模型用量排行。

**核心思路**：

1. **数据收集**：在每次AI调用后，记录使用的模型、请求Token数、响应Token数。通过Micrometer的 `Counter` 或 `Timer` 记录Token消耗，并打上模型标签。
2. **费用计算**：每个模型有单价（如每千Token的费用）。可以在业务代码中计算每次调用的费用，或者通过监控系统（如Prometheus）查询Token消耗，然后乘以单价。
3. **实时指标**：
   - 定义计数器 `ai_token_cost_total`，包含标签 `model`，值为累积费用（单位：分或元）。
   - 每次调用后，根据Token总数和模型单价计算费用，累加到该计数器。
   - 在Prometheus中，使用 `rate(ai_token_cost_total[1m])` 计算每分钟的费用速率。
4. **Grafana面板**：
   - 费用趋势：使用折线图展示每分钟的费用变化，可以按模型拆分。
   - 模型用量排行：使用条形图展示各个模型的总费用或总Token消耗，排序。
   - 今日累计费用：通过 `sum(ai_token_cost_total) - sum(ai_token_cost_total offset 1d)` 计算今日费用。
5. **成本告警**：可以设置告警，当每分钟费用超过阈值时触发，避免意外成本。
6. **数据持久化**：费用数据也可以写入数据库，用于月度账单和审计。
7. **示例代码**：

```
// 定义计数器
Counter costCounter = Counter.builder("ai.token.cost")
        .description("AI调用成本")
        .tag("model", model)
        .register(meterRegistry);

// 每次调用后
double cost = calculateCost(promptTokens, completionTokens, model);
costCounter.increment(cost);
```

8. **单价配置**：模型的单价可以配置在配置中心，便于调整。



## 16. 场景：在A/B测试新老Prompt模板的效果时，你需要收集两组在响应质量、用户满意度等指标上的差异。如何在代码中埋点，并将实验分组信息（如group=A）关联到具体的请求日志和业务指标中？

**核心思路**：

1. **实验分组**：用户进入实验时，随机分配分组（A组或B组）。分组信息可以存储在用户会话中，或者通过Cookie/本地存储保持一致性。
2. **埋点设计**：
   - 在业务代码中，在执行Prompt模板前，确定用户的分组，然后使用对应的模板。
   - 在日志中记录实验分组信息，将分组信息添加到MDC（Mapped Diagnostic Context）中，这样每条日志都会包含分组标签。
   - 在监控指标中，为相关指标添加实验分组标签。例如，记录AI调用延迟的Timer，添加标签 `exp_group`。
3. **指标收集**：
   - 响应质量：可以通过后续的业务指标衡量，如用户是否采纳AI的回答、用户评分等。
   - 用户满意度：通过用户反馈（如点赞、点踩）收集。
   - 技术指标：延迟、错误率等。
4. **数据分析**：将日志和指标发送到ELK和Prometheus，在Kibana和Grafana中按实验分组筛选，比较两组的差异。
5. **实验一致性**：同一用户在整个实验过程中应保持同一分组，除非实验重置。
6. **示例**：

```
// 确定分组
String group = experimentService.getGroup(userId, "prompt_template_v2");
MDC.put("exp_group", group);

// 使用对应模板
String prompt = group.equals("A") ? oldTemplate : newTemplate;

// 记录指标
Timer.builder("ai.request.duration")
        .tag("exp_group", group)
        .record(...);
```

7. **实验结束**：实验结束后，移除相关代码，或者将获胜的模板推送给所有用户。



## 17. 场景：当线上出现“AI返回内容格式错误导致解析失败”的问题时，如何快速定位？请描述你会在异常捕获和日志中记录哪些上下文信息，以及如何通过TraceId快速找到相关的用户请求和AI原始响应。

**核心思路**：

1. **异常捕获**：在解析AI响应的代码处，捕获格式错误异常（如JSON解析异常）。在捕获异常时，记录详细的上下文信息。
2. **日志记录的关键信息**：
   - TraceId：分布式追踪ID，可以串联整个请求链路。
   - 用户ID、会话ID。
   - AI服务名称、模型、请求参数（脱敏后）。
   - AI原始响应内容（注意敏感信息，可以截断或脱敏）。
   - 异常堆栈。
3. **原始响应存储**：对于解析失败的响应，可以将原始响应存储到对象存储或数据库中，并记录存储路径。这样可以在排查时查看原始响应。
4. **通过TraceId定位**：
   - 在日志系统中，通过TraceId搜索所有相关日志，包括网关、业务服务、AI客户端的日志。
   - 如果集成了分布式追踪系统（如Jaeger），可以通过TraceId查看完整的调用链，包括每个步骤的耗时和状态。
5. **告警**：当解析失败率超过阈值时，触发告警，及时发现问题。
6. **示例代码**：

```
try {
    return parseAIResponse(rawResponse);
} catch (JsonParseException e) {
    log.error("AI响应解析失败，traceId: {}, userId: {}, model: {}, rawResponse: {}",
        traceId, userId, model,
        StringUtils.substring(rawResponse, 0, 1000), // 截断
        e);
    // 存储原始响应到S3
    String s3Key = storeRawResponse(rawResponse);
    log.info("原始响应已存储到S3：{}", s3Key);
    throw new BusinessException("AI响应解析失败");
}
```

7. **监控面板**：在Grafana中监控AI响应解析失败率，按模型、时间等维度查看。



## 18. 场景：为方便问题排查，我们需要在界面上能“重放”任意一次用户与AI的历史对话。请描述后端如何存储足够的信息（包括原始请求、响应、中间结果）来支持对话的精确重放。

**核心思路**：

1. **数据存储设计**：为每次对话（session）存储完整的交互记录。每条记录包括：
   - 用户消息：用户输入的原始内容。
   - AI响应：AI返回的原始响应。
   - 中间结果：如调用AI服务的请求参数、模型、温度等参数，以及可能的分步结果。
   - 上下文：对话的上下文信息，如之前的历史消息。
   - 时间戳、对话轮次。
2. **存储介质**：
   - 结构化数据（如对话元数据）存储在关系型数据库。
   - 原始请求和响应等较大数据，可以存储在对象存储（如S3）或NoSQL数据库（如MongoDB）中，数据库中存储引用指针。
3. **重放接口**：提供重放接口，接收对话ID和轮次，返回该轮次的完整交互信息，包括原始请求和响应。重放时，可以使用存储的原始请求再次调用AI服务（如果AI服务支持相同输出），或者只是展示历史记录。
4. **数据一致性**：确保每次对话的完整记录被保存，包括异常情况（如AI调用失败）。
5. **性能考虑**：对于高频对话，存储所有数据可能成本较高，可以考虑只存储最近一段时间的完整数据，过期后归档。
6. **安全与隐私**：存储的对话数据可能包含敏感信息，需要加密存储，并确保只有授权用户能访问自己的对话重放。
7. **示例表结构**：
   - `dialogue_sessions`: session_id, user_id, start_time, end_time, status
   - `dialogue_turns`: turn_id, session_id, turn_number, user_message, ai_response, request_params, response_raw, timestamp
8. **重放实现**：重放时，从数据库中获取该轮次的请求参数，重新构造请求，但注意AI服务可能无法保证完全相同的响应（特别是非确定性模型）。



## 19. 场景：请设计一个简单的容量规划模型。假设单个AI请求平均耗时2秒，消耗0.1核心CPU，你的Pod配置为2核心。你想要维持P95延迟在5秒以内，预估需要支持100 QPS。你需要部署多少个Pod实例？请给出估算思路。

**核心思路**：

1. **单个Pod的处理能力**：Pod配置为2核心，但应用可能无法完全利用，假设CPU利用率上限为80%（避免节点负载过高），则可用CPU为2 * 0.8 = 1.6核心。
2. **单个请求CPU消耗**：每个请求消耗0.1核心CPU，耗时2秒。在2秒内，单个请求占用0.1核心，但CPU是时间片轮转，所以实际上，一个核心每秒可以处理10个请求（1 / 0.1 = 10）。但这是假设CPU是唯一瓶颈，且忽略上下文切换开销。
3. **单个Pod的QPS**：可用CPU为1.6核心，每秒可处理1.6 * 10 = 16个请求。但这是理想情况，实际上，由于请求处理耗时2秒，如果并发请求过多，会导致排队，增加延迟。需要根据延迟要求计算。
4. **排队模型**：使用M/M/c排队模型估算。c为Pod实例数，服务速率μ = 1/2 = 0.5请求/秒，到达率λ = 100请求/秒。需要满足P95延迟小于5秒。
5. **粗略估算**：每个Pod每秒处理0.5个请求，100 QPS需要至少200个Pod（100 / 0.5 = 200）。但这是假设无限并行，实际上Pod有2核心，可以并行处理多个请求。考虑并行处理能力，每个Pod可以同时处理2个请求（2核心，每个请求0.1核心，理论上可以处理20个，但受限于CPU调度和IO）。但这里平均耗时2秒，所以每个Pod的并发处理能力为2核心 / 0.1核心 = 20个请求同时处理。那么每个Pod的QPS = 并发数 * (1 / 平均耗时) = 20 * 0.5 = 10 QPS。要达到100 QPS，需要10个Pod。
6. **延迟验证**：10个Pod，总处理能力100 QPS，刚好达到需求。但需要考虑波动和容错，通常需要预留一些缓冲，增加Pod数量。
7. **结论**：需要部署至少10个Pod，但考虑到P95延迟要求，可能需要更多。可以通过压力测试，确定在100 QPS下，10个Pod的P95延迟是否小于5秒。
8. **自动伸缩**：可以配置HPA，基于CPU使用率或QPS自动伸缩Pod数量。



## 20. 场景：在K8s中，如何为AI服务配置水平Pod自动伸缩（HPA）？基于什么指标（如CPU使用率、内存使用率、还是自定义的QPS指标）？如何设置合理的目标值和边界？

**核心思路**：

1. **HPA配置**：在Kubernetes中创建HorizontalPodAutoscaler资源，指定目标Deployment、最小和最大副本数，以及目标指标。

2. **指标选择**：

   - CPU使用率：AI服务通常是CPU密集型，但可能也消耗内存。但CPU使用率可能不是最佳指标，因为AI请求可能涉及IO等待（如调用外部AI服务）。
   - 内存使用率：如果服务内存使用与负载正相关，也可以作为指标。
   - 自定义指标：如QPS、并发请求数、平均延迟等。自定义指标需要通过Metrics Server和Prometheus Adapter提供。

3. **推荐指标**：对于AI服务，QPS是最直接的业务指标。可以通过Prometheus收集服务的请求数，然后通过Adapter转换为Kubernetes可识别的自定义指标。

4. **目标值设置**：

   - 如果使用CPU使用率，目标值可以设置为70%（预留30%缓冲）。
   - 如果使用QPS，需要根据单个Pod能处理的QPS来设定。例如，单个Pod能处理10 QPS，目标值可以设置为8 QPS，预留20%缓冲。

5. **边界设置**：最小副本数根据可用性要求设置（如2个），最大副本数根据资源预算和集群容量设置。

6. **冷却时间**：设置适当的缩放冷却时间，避免频繁伸缩。

7. **示例HPA配置**：

   ```
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: ai-service-hpa
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: ai-service
     minReplicas: 2
     maxReplicas: 20
     metrics:
     - type: Pods
       pods:
         metric:
           name: qps
         target:
           type: AverageValue
           averageValue: 10
   ```

8. **压力测试**：通过压力测试确定单个Pod的处理能力，从而设置合理的目标值。

9. **监控**：监控HPA行为，确保自动伸缩符合预期。

