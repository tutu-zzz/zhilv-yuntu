# 更新日志

> 这里只记录项目功能、架构和工程能力相关的更新，不记录简历、面试文档等个人整理内容。

## 2026-09-10

### 三栏旅行工作台

- 前端重构为 Trip Workspace：左侧导航、中栏 Overview / Itinerary / Places / Notes、右侧 AI 助手，替代原结果页（旧页保留可回退）。
- AI 助手升级为对话窗口：自然语言调整行程、快捷指令、分阶段状态提示；可收起为悬浮按钮，不占布局空间。

### 对话式行程编辑

- 新增 `POST /trip/chat`：解析用户意图（修改行程 / 问答）后复用既有单日编辑链路，保留 POI 固化等真实性约束；两阶段 token 合并统计。
- 模型额度错误（如 DashScope 免费额度耗尽）返回 403 与明确提示，前端直接展示，不再静默降级为模糊失败。

### 性能与工程

- 关闭 qwen3.x 思考模式（`enable_thinking: false`），完整生成链路实测 96.9s → 22.3s；Query Rewrite 增加超长输出回退防护。
- Vite proxy 统一同源 `/api` 转发，动态探测本机 IP，换网络零配置，并绕开 VS Code 端口转发抢占。
- 高德 JS API 降级 1.4.15 修复底图白图；前端 axios 超时放宽至 300s。
- 测试基建：前端 vitest 挂载测试（`npm test`）+ 后端 chat 接口测试；修复 AI 面板因缺失 import 不渲染的问题。

### 验证说明

- 前端挂载测试 3 passed、构建通过；后端定向测试 12+4 passed。
- 对话历史暂存于前端内存，刷新即失，属后续改进项。

## 2026-07-26

### 热门城市动态规划

- 新增城市覆盖分级与名称规范化：已有本地攻略的 6 个城市继续走 `curated` RAG 路径；地图服务可确认的未沉淀城市进入 `dynamic` 路径；无法解析或候选不足时返回明确错误。
- 新增 `city_resolver_service.py`，结合本地城市注册表和高德行政区接口处理城市别名、直辖市与普通省份边界。
- 新增 `place_candidate_service.py`，按景点、餐饮和住宿采集高德 POI，过滤跨城市、无坐标和重复结果，并执行最低候选覆盖校验。
- `/trip/generate` 已接通动态城市同步规划。用户在实际页面手工尝试多个未沉淀城市并确认能够生成完整方案；该结果属于探索性验收，尚未替代正式 30 城基准评估。

### POI ID 受约束规划

- 新增独立动态 Planner 协议：模型只返回候选池中的景点、餐饮和住宿 POI ID、时间块与选择理由，不直接生成地点名称。
- `trip_service.py` 在服务层二次校验所有 ID，再从候选池回填名称、地址、坐标和图片；模型不可用或返回越界 ID 时，仅从本次真实候选池生成规则方案。
- `MealItem` 与 `HotelItem` 增加 POI ID、地址、坐标和图片字段；结果页增加餐饮和住宿地址展示。
- 智能调整会保留已经绑定 POI 的实体名称和 ID，避免出现“名称被模型改写但 ID 仍指向旧地点”的不一致。
- 普通省级目的地不再误入单城市候选链路，返回 `unsupported_destination_scope` 并提示输入具体城市；北京、上海、天津、重庆等直辖市仍按城市处理。

### 边界行为加固

- 动态候选筛选从仅比较 `cityname` 升级为结合行政区层级比较 `adcode`：地级市按前 4 位、区县级目的地按完整 6 位过滤，避免敦煌等区县级旅游城市被上级城市名称误过滤。
- “不要安排景点”等明确取消指令不再创建“自由活动 / 弹性安排”占位 POI，而是清空当天景点及关联交通，避免地图补全把占位文本绑定到无关地点；“不要安排太满”不会触发清空。
- 高德接口超时、HTTP 错误、网络错误、无效响应和业务 `infocode` 会转换为脱敏错误原因；城市解析与候选采集的 503 响应保留失败阶段，不记录或返回 API Key。

### 验证说明

- 城市注册表、城市解析、候选池和接口错误分支已有定向测试覆盖。
- 用户已完成上海及其他多个城市的页面手工生成验证；本次边界加固尚待用户本地回归，Codex 未运行项目、构建或测试。

## 2026-07-18

### RAG 数据一致性与目的地隔离

- 知识库扩展为北京、大理、成都、西安、厦门、三亚 6 个目的地，并在 `guide_catalog.py` 中集中维护攻略文件与目的地映射。
- 为每个攻略 Chunk 增加 `destination` metadata；Chroma 向量检索、关键词 fallback、Rerank、RAG 缓存和跨目的地污染评估均按该字段传递或过滤。
- `evaluate_rag_retrieval.py` 不再维护静态目的地列表，改为从评估 case 自动收集目的地，避免遗漏北京等新增城市。
- 检索扩展规则迁移到 `backend/data/retrieval_rules.json`，清理已不存在于当前攻略中的旧 POI 扩展词；规则按全局和目的地配置加载。
- RAG 评估集更新为 18 条，并新增静态校验，保证每个评估必需词都能命中对应城市的当前攻略。

### 行程回退与知识库校验

- `trip_service.py` 移除模板化景点、餐饮、住宿 fallback。模型不可用或候选不足时，只使用本次 RAG 上下文中的真实名称；没有候选则保持为空并返回明确说明。
- 新增 `fallback_candidates.py`，将运行时 fallback 提取规则集中复用：景点需包含位置字段，餐饮需包含“招牌菜”，住宿需包含“酒店预算”。
- 新增 `validate_knowledge_base.py` 与对应测试，离线校验攻略目录映射、规则扩展词、每城景点/餐饮/住宿 fallback 候选、评估正向断言和 Chunk destination metadata。
- 修正无数据支撑的“轻松/休闲”全局检索扩展词；旅行节奏仍通过 `pace` 参数参与查询，不再伪装为攻略事实词。

### 开发与验证

- 新增 `start.ps1`：构建并启动 Docker Compose 后打印前端、后端和 API 文档地址。
- 新增 `test_model_connection.py`，可独立检测 Chat 与 Embedding 模型连通性。
- 已完成定向验收：fallback 回归 `1 passed`、RAG 规则 `3 passed`、评估断言 `2 passed`、目的地 metadata `5 passed`、知识库一致性 `2 passed`；知识库校验脚本输出“知识库一致性校验通过”。
- 当前本地 Markdown 攻略仍属于参考知识，不应被视为实时、逐条核验的商户、价格或营业状态数据。

## 2026-06-11

### Docker 容器化部署

- 新增 `backend/Dockerfile`：基于 Python 3.11-slim 镜像，先复制 `requirements.txt` 安装依赖（利用层缓存），再复制应用代码，运行 uvicorn。
- 新增 `frontend/Dockerfile`：两阶段构建——Node 20 编译 Vue 应用，Nginx alpine 托管静态文件，最终镜像不含 Node.js，体积从几百 MB 缩小到几十 MB。
- 新增 `frontend/nginx.conf`：Nginx 配置，负责静态文件托管 + API 反向代理到后端容器，`try_files` 支持 Vue SPA 路由。
- 新增 `docker-compose.yaml`：编排 Redis、后端、前端三个服务，定义依赖关系、端口映射、数据卷持久化和环境变量注入。
- 新增 `.dockerignore`：排除 `__pycache__`、`.env`、`node_modules` 等不需要打包的文件。
- 后端 `main.py` 新增 Docker 环境的 CORS 允许源（`http://localhost`、`http://localhost:80`）。

## 2026-05-19

### Token 消耗统计

- 在 `schemas.py` 中为 `Itinerary` 增加 `token_usage` 字段，记录单次行程生成过程中的 token 消耗。
- 在 `rag_tool.py` 中提取 LLM-based Query Rewrite 的输入/输出 token。
- 在 `vector_db.py` 中提取在线 Query Embedding 的官方 `usage`，仅统计在线检索 query embedding，不统计离线知识库入库 embedding。
- 在 `retriever.py` 中提取 DashScope qwen3-rerank 官方 `usage`，记录 Rerank 输入/输出 token。
- 在 `trip_planner_agent.py` 中提取 Planner 行程生成的输入/输出 token。
- 在 `trip_service.py` 中汇总 Query Rewrite、Query Embedding、Rerank、Planner 四段 token，并在后端终端打印分项与总量。
- 新增 `/trip/stats` 接口，可统计已保存行程的 token 消耗汇总。

**本次前端输入**

```text
目的地城市：大理
开始日期：2026-05-19
结束日期：2026-05-21
人数：2
旅行天数：3 天
节奏偏好：轻松
住宿偏好：舒适型
预算：3200
旅行偏好：自然风景、拍照、美食
饮食偏好：少辣
额外要求：不想太早起床，希望安排一个适合看日落的地点。
```

**本次验证日志**

```text
[embedding] query embedding token: prompt=20, completion=0, source=api
[rerank] qwen3-rerank token: prompt=1703, completion=0, source=api
[trip_planner_agent] 大模型调用完成。token: prompt=1159, completion=437
[token_usage] Query Rewrite: prompt=134, completion=19
[token_usage] Rerank: prompt=1703, completion=0
[token_usage] Query Embedding: prompt=20, completion=0
[token_usage] Planner: prompt=1159, completion=437
[token_usage] Total: prompt=3016, completion=456, all=3472
```

**四种模型调用的 token 消耗**

| 调用 | 模型 | 输入 token | 输出 token | 原因 |
|------|------|-----------|-----------|------|
| Query Rewrite | qwen-max | ✅ 有 | ✅ 有 | 生成式 LLM，输入 prompt，输出关键词文本 |
| Query Embedding | text-embedding-v4 | ✅ 有 | ❌ 0 | 只把文本转向量，不生成文本 |
| Rerank | qwen3-rerank | ✅ 有 | ❌ 0 | 只算相关性分数，不生成文本 |
| 行程生成 | qwen-max | ✅ 有 | ✅ 有 | 生成式 LLM，输入 prompt，输出 JSON 行程 |

**说明**

- `source=api` 表示 Query Embedding 和 Rerank token 均来自 DashScope 官方响应字段，不是本地估算。
- 本次统计只覆盖在线请求成本：Query Rewrite、Query Embedding、Rerank、Planner；离线知识库切片入库时的 document embedding 不计入单次 `/trip/generate`。
- Rerank 和 Embedding 的 `completion=0` 属于正常现象，因为 Embedding 输出向量、Rerank 输出分数，都不生成自然语言正文。
- `/trip/generate` 返回结果中会同步包含 `token_usage`，便于前端或调试工具查看本次生成成本。

## 2026-05-07

### Cross-encoder Rerank

- 接入 DashScope qwen3-rerank 模型，替代规则级 Rerank 做语义级重排序。
- 在 `retriever.py` 中新增 `_rerank_with_dashscope()`，通过 httpx 调用 DashScope Reranker API。
- 保留规则级 `_score_chunk_for_rerank()` 作为 fallback，API 不可用时自动降级。
- 添加 `instruct` 参数引导模型优先选择具体、详细的旅行攻略片段，避免泛化介绍。
- 在 rerank 前过滤已知噪声片段（"文档开头"），避免浪费 rerank 名额。

**优化效果对比**

| 指标 | Baseline（规则级） | LLM Rewrite | + Cross-encoder | 变化（vs Baseline） |
|------|-------------------|-------------|-----------------|-------------------|
| Top1 Hit Rate | 12/15 (80.0%) | 13/15 (86.7%) | 14/15 (93.3%) | +13.3% |
| TopK Hit Rate | 15/15 (100.0%) | 15/15 (100.0%) | 15/15 (100.0%) | - |
| MRR | 0.889 | 0.922 | 0.967 | +8.8% |
| Keyword Coverage | 59/63 | 60/63 | 61/63 | +2 |
| Noise Rate | 0.0% | 0.0% | 0.0% | - |
| Cross-destination Pollution | 0 | 0 | 0 | - |
| Avg Latency | 461.8ms | 347.7ms | 728.4ms | +57.7% |

经过 LLM Query Rewrite + Cross-encoder Rerank + 噪声预过滤三阶段优化，Top1 命中率从 80% 提升到 93.3%，MRR 从 0.889 提升到 0.967，噪声率保持为 0。Latency 增加主要来自 rerank API 调用，后续可通过缓存优化。

### Rerank 缓存优化

- 在 `retriever.py` 的 `rerank_guide_chunks` 中新增 Rerank 结果缓存，命中时跳过 DashScope API 调用。
- 缓存 key 由 normalized query + chunks 内容哈希组成，确保相同 query 配相同候选集时复用缓存。
- 缓存值只存索引和分数 `[{"i", "s"}]`，不重复存 chunk 文本，节省存储。
- 在 `config.py` 中新增 `REDIS_RERANK_TTL_SECONDS` 配置项，与现有 Redis 缓存共享开关。
- 在 `.env` 和 `.env.example` 中同步新增 `REDIS_RERANK_TTL_SECONDS=21600`。

**本次验证到的 Rerank 缓存 key**

```text
trip_planner:rerank:成都 熊猫基地 美食 休闲 轻松 适合家庭:86281a27592a
trip_planner:rerank:大理 自然风景 拍照 美食 轻松 日落地点:feaeff944221
trip_planner:rerank:西安 回民街 美食 小吃 夜市 特色小吃:6aca260efd77
trip_planner:rerank:三亚 海滩 度假 放松 高级酒店 沙滩休闲:aa3ac37f0667
trip_planner:rerank:厦门 厦门大学 南普陀寺 拍照 文化 建筑:6e5f7b5d1ae0
trip_planner:rerank:三亚 美食 海鲜 南山寺 文化 适中节奏 新鲜海鲜:610d238b719e
trip_planner:rerank:大理 古镇 文化体验 慢节奏 白族文化 轻松旅行:25c88c579b45
trip_planner:rerank:成都 自然风景 徒步 文化 都江堰 青城山 户外:e651b63c9ec0
trip_planner:rerank:大理 美食 小吃 预算 特色餐饮 花费:edd9f0093e5f
trip_planner:rerank:厦门 鼓浪屿 海岛 文艺 美食 情调 轻松 旅行:229afa03f280
trip_planner:rerank:西安 亲子 研学 文化 轻松 教育意义 不赶:7184d33a1e75
trip_planner:rerank:成都 美食 小吃 火锅 特色美食 吃货 探店:584c7e41a41b
trip_planner:rerank:三亚 亲子 水上乐园 海洋动物 轻松:ca99c53ae7e7
trip_planner:rerank:西安 历史 文化 古迹 深度游:480addc7dfe9
trip_planner:rerank:厦门 骑行 海景 休闲 日落 放松:14207650ed1a
```

**优化效果**

| 指标 | 无 Rerank | + Cross-encoder | + Rerank 缓存 |
|------|-----------|-----------------|---------------|
| Top1 Hit Rate | 12/15 (80.0%) | 14/15 (93.3%) | 14/15 (93.3%) |
| MRR | 0.889 | 0.967 | 0.967 |
| Noise Rate | 0.0% | 0.0% | 0.0% |
| Avg Latency（首次） | 461.8ms | 728.4ms | 654.6ms |
| Avg Latency（缓存命中） | - | - | **424.8ms** |

缓存命中后延迟降低 41.6%，回到接近 LLM Rewrite 阶段水平，同时保留 Cross-encoder Rerank 的质量提升。

## 2026-05-06

### RAG 评估指标体系完善

- 在 `evaluate_rag_retrieval.py` 中新增 4 个量化指标，建立完整的 RAG 检索质量评估体系。
- **MRR（Mean Reciprocal Rank）**：衡量命中结果的排序质量，标准 IR 指标。
- **Noise Rate**：噪声片段占 Top-K 的百分比，比绝对数量更直观。
- **Latency（检索耗时）**：单次检索耗时（ms），体现工程优化价值。
- **Cross-destination Pollution**：跨目的地污染片段数，量化之前的优化成果。

**Baseline 数据（规则级 RAG）**

| 指标 | 数值 |
|------|------|
| Top1 Hit Rate | 12/15 (80.0%) |
| TopK Hit Rate | 15/15 (100.0%) |
| MRR | 0.889 |
| Keyword Coverage | 59/63 |
| Noise Rate | 0.0% |
| Cross-destination Pollution | 0 |
| Avg Latency | 461.8ms |

3 个 Top1 miss 均为同目的地内的排序竞争（西安美食→期望回民街、西安亲子→期望景点、厦门骑行→期望环岛路），需引入语义级优化进一步提升。

### LLM-based Query Rewrite

- 用 qwen-max 替代手写规则，将用户旅行需求自动改写成向量检索 query。
- 在 `rag_tool.py` 中新增 `llm_rewrite_query()`，遵循项目已有的 LangChain + ChatOpenAI 调用模式。
- 保留规则级 `_rule_based_query()` 作为 fallback，LLM 不可用时自动降级。
- Prompt 设计：System 指定输出格式（纯关键词、空格分隔、无解释），Human 包含目的地/偏好/节奏/备注。

**优化效果对比**

| 指标 | Baseline（规则级） | LLM-based | 变化 |
|------|-------------------|-----------|------|
| Top1 Hit Rate | 12/15 (80.0%) | 13/15 (86.7%) | +6.7% |
| TopK Hit Rate | 15/15 (100.0%) | 15/15 (100.0%) | - |
| MRR | 0.889 | 0.922 | +3.7% |
| Keyword Coverage | 59/63 | 60/63 | +1 |
| Noise Rate | 0.0% | 0.0% | - |
| Cross-destination Pollution | 0 | 0 | - |
| Avg Latency | 461.8ms | 347.7ms | -24.7% |

LLM Rewrite 将 Top1 命中从 12 提升到 13，MRR 从 0.889 提升到 0.922。西安美食场景从 RR=0.5 提升到 RR=1.0（LLM 直接生成"回民街"关键词）。剩余 2 个 Top1 miss 为同目的地内排序竞争，需引入 Cross-encoder Rerank 进一步优化。

## 2026-04-29

### 地图路线可视化

- 在高德地图上用虚线箭头连接各天行程点位，展示完整路线走向。
- 每个目的地用 🚩 旗帜图标标记，直观体现打卡风格。
- 鼠标悬停时展示景点图片气泡窗口（含景区图片和地名），无图片时显示占位提示。
- 气泡窗口采用轻量卡片设计，尺寸紧凑，不遮挡地图主体内容。

### RAG 知识库扩充

- 新增 4 个目的地攻略文档：`chengdu_guide.md`、`xian_guide.md`、`xiamen_guide.md`、`sanya_guide.md`。
- 与原有 `dali_guide.md` 共同覆盖 5 个目的地，写入后 ChromaDB 共 49 个检索片段。
- 每个攻略统一采用：目的地简介 → 核心景点（含门票/位置/时长） → 特色餐饮（含人均预算） → 住宿区域（含价格区间） → 经典行程参考的结构。

### RAG 评估样例集扩充

- `rag_eval_cases.json` 从 3 条扩充到 15 条，每个目的地 3 条。
- 覆盖不同人群（情侣、亲子、带父母）、不同节奏（轻松、适中）、不同偏好（美食、文化、自然、度假）。

### RAG 在线阶段规则级优化

本轮在不引入模型的前提下，通过规则优化 RAG 在线阶段的检索排序质量。

**Query Rewrite 目的地过滤**

- 在 `rag_tool.py` 的 `_extract_note_keywords` 中引入目的地过滤机制。
- 目的地特定关键词（如"洱海、双廊"只在大理时注入，"回民街"只在西安时注入）不再跨目的地泄漏。
- 新增成都（大熊猫）、西安（古镇→回民街）、厦门（古镇→鼓浪屿/曾厝垵、骑行→环岛路）、三亚（潜水→蜈支洲岛、海鲜→第一市场）等目的地规则。

**Rerank 多层降权**

- 在 `retriever.py` 的 `_score_chunk_for_rerank` 中新增三层降权机制：
  - 行程参考片段降权（-4）：防止"经典行程参考"因内容过于全面而霸占 Top1。
  - 目的地简介降权（-2）：防止过于泛化的简介片段排到 Top1。
  - 目的地不匹配降权（-5）：对来源目的地与查询目的地不一致的片段做大幅降权，解决跨目的地污染。
- `rerank_guide_chunks` 和 `retrieve_travel_guide_chunks` 全链路传递 `destination` 参数。

**优化效果**

| 指标 | 基线 | 优化后 |
|------|------|--------|
| Top1 命中率 | 13/15 (87%) | 12/15 (80%) |
| TopK 命中率 | 15/15 (100%) | 15/15 (100%) |
| 跨目的地污染 | 存在 | 已消除 |
| 噪声片段 | 0 | 0 |

Top1 命中率看似下降，实际是基线中"行程片段"霸榜导致的虚高。优化后专题片段（餐饮、景点、住宿）能正确排到 Top1，排序质量实质提升。剩余 3 个 Top1 miss 均为同目的地内的排序竞争，需引入语义级 rerank 进一步优化。

**优化路线总览**

```text
已完成（规则级）                    下一步（模型级）
┌─────────────────────┐      ┌──────────────────────┐
│ Query Rewrite       │      │ LLM-based Rewrite    │
│  └ 目的地过滤        │ ──→  │  └ qwen-max 改写 query│
├─────────────────────┤      ├──────────────────────┤
│ Rerank              │      │ Cross-encoder Rerank │
│  └ 关键词打分        │ ──→  │  └ bge-reranker-base │
│  └ 行程/简介降权     │      │  └ 语义相关性打分    │
│  └ 目的地不匹配降权  │      │                      │
└─────────────────────┘      └──────────────────────┘
```

## 2026-04-25

### RAG 在线阶段优化

- 接入轻量化 Query Rewrite，不再直接拼接整句备注，而是从用户偏好、节奏与备注中提炼更适合检索的关键词。
- 在 `rag_tool.py` 中补充旅行场景规则词，例如日落、傍晚、洱海、双廊、慢节奏等，提升旅行规划类 query 的检索聚焦度。
- 在 `retriever.py` 中加入第一版轻量 Rerank，对标题命中、正文命中、行程类标题和已知噪声片段做启发式打分。
- 对”文档开头”这类低信息量片段做强惩罚，并对与当前主目标弱相关的餐饮 / 预算类片段做轻量降权。
- 新增 `debug_rag_retrieval.py` 调试脚本，可直接观察检索 query、top-k 召回片段、`rerank_score` 与 `rerank_reasons`。

**优化效果**

以大理日落+拍照+轻松场景为例：

| 优化前 Top5 | 优化后 Top5（含 rerank_score） |
|-------------|-------------------------------|
| 1. 经典三日行程参考 | 1. 经典三日行程参考 (score: 10) |
| 2. 目的地简介 | 2. 大理古城 (score: 5) |
| 3. 特色餐饮与预算参考 | 3. 洱海生态廊道 (score: 5) |
| 4. 住宿区域建议 | 4. 目的地简介 (score: 3) |
| 5. 文档开头 | 5. 住宿区域建议 (score: 3) |

优化前 Top5 中”目的地简介”和”文档开头”等低信息量片段占据位置；优化后通过 Rerank 打分，”大理古城”和”洱海生态廊道”等与场景强相关的片段被排到前面，”文档开头”被过滤。

## 2026-04-15

### Redis 缓存优化

- 新增 Redis 缓存层，并支持 Redis 不可用时自动降级，不影响主流程运行。
- 接入天气查询缓存，减少同城天气的重复外部请求。
- 接入高德地图地理编码、POI 搜索和路线估算缓存，减少重复地图查询开销。
- 接入 RAG 检索结果缓存，复用高频 query 的攻略片段召回结果。
- 增加基础 `cache hit / cache miss` 日志，便于本地验证缓存命中情况。
- 通过本地 Docker Redis 容器验证缓存 key 写入成功。

**本次验证到的缓存 key**

```text
trip_planner:weather:forecast:大理
trip_planner:rag:guide:大理 自然风景 拍照 美食 轻松 不想太早起床，希望安排一个适合看日落的地点。 景点 行程 攻略 推荐:5
trip_planner:map:place:大理 舒适型住宿 2:大理:1
trip_planner:map:place:双廊古镇:大理:1
trip_planner:map:route:100.323501,25.647149:100.131582,25.852950
trip_planner:map:place:大理 舒适型住宿 1:大理:1
trip_planner:map:place:大理 舒适型住宿 3:大理:1
trip_planner:map:route:100.323501,25.647149:100.164000,25.694836
trip_planner:map:place:大理古城:大理:1
trip_planner:map:geocode:大理:大理
trip_planner:map:place:大理 出发点:大理:1
trip_planner:map:route:100.323501,25.647149:100.194322,25.908323
trip_planner:map:place:喜洲古镇:大理:1
```
