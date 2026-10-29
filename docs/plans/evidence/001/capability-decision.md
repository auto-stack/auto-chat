# CHAT-001 T-01 能力决策（capability-decision）

日期：2026-10-29。状态：T-01 完成，冻结下述唯一最小连接 profile；T-02..T-05 按此实现。
产品定位（用户 2026-10-29 已确认）：真实人与人聊天，沿用现有联系人界面；非 AI 客户端/联邦/加密研发。

## 1. 基线与工具链版本（执行前核对记录）

| 项 | 值 |
|---|---|
| 本仓基线 | `main` @ `9046d95`（计划冻结观察基线 `8df3f33` 之后仅 plan 文档 3 提交；工作树干净，无 WIP 代码） |
| auto CLI | `D:/autostack/auto-man/target/debug/auto.exe`，`auto 0.1.0+v0.0.20-117-g873fa23`（auto-man 独立仓构建于 2026-10-28；auto-man HEAD `e6cc06f` 略新于二进制，本轮以该二进制实证通过为准） |
| AutoUI | `D:/autostack/auto-ui` @ `7b64303`（生成后端编译按路径依赖消费同仓 crates） |
| auto-lang | `D:/autostack/auto-lang` @ `93c488a89`（仅提供 auto-lang-core 等库，`auto` CLI 不再由此仓产出） |
| 端口 | 前端 `17822`（Vite dev server，绑定 localhost） / 后端 `17823`（pac.at 固定，沿用） |
| 探针日志 | `D:/autostack/logs/chat-t01-vue3.log`（本地证据，不入库）；首次冷构建超过 `auto run` 120s 后端就绪门限，需先 `cargo build -p auto-chat-back` 预热 `rust-workspace/target` 后再 `auto run`（实测 30s 内就绪） |

## 2. 真实通道全路径探针（实测，非文档推断）

对运行中的生成后端（17823）逐一实测：

| 探针 | 命令 | 结果 |
|---|---|---|
| 健康读取 | `GET /api/contacts` | 200，返回 4 条种子联系人 JSON |
| 历史读取 | `GET /api/messages` | 200，返回 5 条种子消息 |
| 真实写入 | `POST /api/messages {"sender":"Prober","text":"t01-probe-中文换行\nsecond"}` | 200，返回 `id:5` 消息；**中文与 `\n` 换行完整往返** |
| 实时广播 | `GET /api/stream`（SSE）期间 `POST /api/messages {"text":"sse-check"}` | SSE 收到 `data: {"id":6,...,"event":"NewMessage"}` —— **跨客户端实时推送真实可用** |
| typing | `POST /api/typing {"sender":"Prober"}` | 200（广播 `{"event":"Typing","name":...}`） |
| 前端 | `http://localhost:17822/` | Vite ready（日志确认） |

codegen 机制（源码实证，`auto-api-gen/src/api_gen.rs`）：

- POST 端点返回**已声明类型** `T` 且模块含 SSE 流端点时，生成处理器落库后向总线广播 `{"event":"New<T>", ...T}`（全部订阅者可达，事件含完整载荷）。
- void POST 且函数名含 `typing` 时广播 `{"event":"Typing","name":<第一个str体参数>}`（仅首参数进载荷）。
- void POST 其他情况**不广播**。
- 端点体必须是 `return db.FN(args)` 薄委托（`resolve_db_call` 按体/名字启发匹配 db.rs 导出函数）；参数来源：路径 `:x`→Path，GET/DELETE 非路径→Query 结构体，POST→Json 体字段，`meta str` 参数→请求头注入（cookies+Authorization）。
- Vue 轨 store composable 为每个流端点生成一条 EventSource：按 `pub tag ChatEvent` 变体（区分字段默认 `event`）逐一派发到同名 store handler；**未声明的事件静默忽略**；`onerror` 自动重连（CLOSED 后 2s 退避重建）。

## 3. 冻结的唯一最小连接 profile（T-02..T-04 实现合同）

**拓扑**：单共享后端 = 应用自身生成 Rust 服务器（17823），即聊天服务器。两个独立客户端 = 两个独立前端实例（Vue：同浏览器两个标签/窗口，各自独立登录；VM：`auto run -r vm` 两实例经 `AUTO_REUSE_BACKEND=1 AUTO_HTTP_PORT=17823 AUTO_HTTP_BASE=http://127.0.0.1:17823` 复用外部后端）。通道 = HTTP(SSE) 局域回环，无中继/联邦。

**身份与访问控制**：
- `POST /api/login {name}`：按名字 find-or-create 身份，签发 token（`auto.rand` 随机、SQLite 持久化、同名会话共享当前 token），返回 `LoginAck{name,id}` 并广播 `NewLoginAck`（**不含 token**，兼作在线名单变更信号）。
- `GET /api/me?name=`：返回 `MeInfo{id,name,avatar,token}`（仅 GET 响应携带 token，不进任何广播）。
- 之后所有调用携带 `{token,...}`；服务器从 token 注册表解析发送者身份，**不接受任何客户端 sender 字段**；token 无效/缺失 → 错误形状返回（不落库、不广播）。伪造 sender 无法越权投递。
- 在线判定：客户端每秒 `POST /api/heartbeat {token}`；`GET /api/identities` 按最近心跳（≤15s）计算 online。

**会话与消息**：
- conversation_id 稳定派生：`cv-<小id>-<大id>`（双人会话按身份 id 排序），`POST /api/conversations/open` 幂等。
- message_id 服务器单调分配（SQLite 自增）；消息带客户端 `client_msg_id`，`UNIQUE(conversation_id, client_msg_id)` —— **重试不重复落库**（重复命中返回已存消息）。
- 发送状态机（客户端）：sending →（POST 返回 ok）sent（= 服务器已落库=已确认）；网络失败/非2xx → failed（composer 保留文本可重发）；**确认语义 = 服务器持久化 + 广播/轮询可见**。不另设服务器侧已读回执以外的送达等级；已读用 `POST /api/read` 记 last_read，侧栏 unread 相应计算。
- **送达语义分轨**：Vue 轨经 SSE `NewSendResult` 实时推送（含整条消息，各客户端按 conversation_id 过滤展示）；VM 轨无 SSE 源（见 §5 缺口），以 1s 定时器轮询当前会话 `GET /api/messages` + `GET /api/contacts` 送达。两轨刷新同为断线重连兜底。
- **历史恢复**：消息/身份/token/会话/last_read 全部 SQLite 持久化；退出重开 → 同名登录 → 同一身份 id → 历史按合同恢复（含中文/换行）。客户端发送中（未确认）消息不跨重启保留（重开后状态为空，需重发）——此为本合同明确冻结的边界。
- **取消**：发送为短请求，无进行中取消；失败态即取消等价（文本保留可改可重发）。

**数据目录**：`CHAT_DATA_DIR` env 覆盖 → 否则 `%APPDATA%/auto-chat/data`（Windows）→ `XDG_DATA_HOME`/`HOME` 兜底；目录由后端确保存在（SQLite 对缺父目录会静默退化为内存库，必须先建目录）。测试隔离：`CHAT_DATA_DIR` 指向临时目录 + `CHAT_TEST_MODE=1` 启用 `POST /api/test/reset`（仅测试模式可用，普通模式 403 形状返回）；凭据/数据不进日志与导出。

**资源边界（冻结）**：单会话历史**全量返回**（v1 合同，无分页；不隐藏硬上限）；身份列表全量（本地规模）。大历史分页/联档为后续增强，不在本计划成功声明内。

## 4. API 面（v2，替换演示期端点）

| 端点 | 方法 | 请求 | 返回/广播 |
|---|---|---|---|
| `/api/login` | POST | `{name}` | `LoginAck`；广播 `NewLoginAck` |
| `/api/me` | GET | `?name=` | `MeInfo`（含 token，仅此一处） |
| `/api/identities` | GET | - | `[]Identity`（公开字段，无 token） |
| `/api/heartbeat` | POST | `{token}` | void（不广播） |
| `/api/contacts` | GET | `?token=` | `[]Contact`（按调用者视角的会话摘要，供侧栏） |
| `/api/conversations/open` | POST | `{token,peer_id}` | `Conversation` |
| `/api/messages` | GET | `?token=&conversation_id=` | `[]Message`（校验参与者） |
| `/api/messages` | POST | `{token,conversation_id,text,client_msg_id}` | `SendResult`；广播 `NewSendResult` |
| `/api/typing` | POST | `{name,token,conversation_id}` | void；广播 `Typing`（codegen 约束：首参数 name 进载荷；token 服务端校验后才广播） |
| `/api/read` | POST | `{token,conversation_id}` | void |
| `/api/test/reset` | POST | - | void；仅 `CHAT_TEST_MODE=1` |

`pub tag ChatEvent` 扩展为：`NewMessage(Message)`（保留兼容）、`Typing(TypingEvent)`（保留）、`NewLoginAck(LoginAck)`、`NewSendResult(SendResult)`。

移除：`/api/bot_reply`（固定回复）、种子 Alice/Bob/AutoBot/Support 数据、`Message.mine` 服务器字段（气泡方向由客户端以 `sender_id == my_id` 派生）。

## 5. 缺项与不支持项（具名 owner 与关闭条件）

| 缺口 | 影响 | owner / 关闭条件 |
|---|---|---|
| 前端 `Http.*` 无自定义 header 能力（Vue fetch 映射固定 Content-Type；VM 默认头注册表仅宿主可设） | token 只能走请求体字段 | auto-ui `ts_adapter.rs` Http 映射 + auto-lang stdlib `auto.http`；关闭条件：`Http` 支持显式 header 参数后 token 迁 Authorization 头 |
| SSE 为单总线全员广播，无按会话流路由 | 跨会话消息文本流经所有连接（UI 层按会话过滤，写入侧强校验） | auto-lang `auto-api-gen`；关闭条件：流端点支持路径参数/按通道订阅 |
| VM 轨无 SSE 源（P-15，vue codegen 特性） | VM 实时性退化为 1s 轮询 | auto-ui/auto-lang VM renderer；关闭条件：VM 轨接通 `~Stream` 派发 |
| `auto run` 后端 120s 就绪门限 vs 冷构建耗时 | 首次构建需预热 | 工具链体验问题，不阻塞交付；以预热流程绕过 |
| meta str 头注入（cookies+Authorization）已存在但前端发不出对应头 | 与缺口1同根 | 同缺口1 |

明确不做（计划 §1 非目标）：AI 对话、联邦、多端同步、E2E 加密、群管理、音视频、Linux 适配。

## 6. 双端验收入口（T-05 据此制作永久回放）

- Vue 轨：`auto run`（本仓根）→ 两个浏览器上下文分别登录甲/乙 → 中文/换行互发、会话隔离、断网失败态、重启恢复。驱动：既有 Playwright（`tests/`）。
- VM 轨：先有 17823 后端（可由 `auto run` 提供），再 `AUTO_REUSE_BACKEND=1 AUTO_HTTP_PORT=17823 AUTO_HTTP_BASE=http://127.0.0.1:17823 auto run -r vm` 起 VM 实例 → AutoUI MCP（9261）驱动同一任务集。
- 汇总入口（T-05 新建）：`python tests/basic/verify_basic.py --profile vue|vm`，隔离数据目录 + 独立端口，记录版本/hash/结果。

——以上为 T-01 唯一连接 profile 冻结文本；后续任务不得静默偏离，偏离需走计划修订。

---

## 7. 执行期增补（T-02..T-05 实测新发现，2026-10-29）

实现过程中实测确认/新发现的框架事实（全部已绕开，缺口按 §5 具名）：

1. **VM 轨登录/GET Unicode query 不可靠**：`GET /api/me?name=甲` 在 VM 轨返回
   空结果（reqwest URL 非 ASCII 处理）——token 认领改为 ASCII 一次性 nonce 两步式
   （login 携带 nonce → me?nonce 认领并清除 pending）。
2. **VM `Http.post` record body 落调试转储**：post_json 弹栈 String，record 实参
   被 `format!("{:?}")` 序列化——VM 臂一律手拼 JSON 字符串（文本先转义）；Vue 臂
   用对象字面量（JSON.stringify(字符串) 会二次编码，实测登录失败根因）。
3. **`Env.track()` 构建期折叠**：Vue 构建折叠为 'vue'，分支比较必须写
   `!= "vue"`（写 == "vm" 触发 TS2367 无交集报错）；视图模板内不可用
   （Env 未绑定），经 store 布尔字段（App.Init/ProbeTrack）中转。
4. **store 限制**：不允许 fn 块（UI 校验 "got 'fn'"）；跨模块自由函数
   （use module: fn）对 store 不可解析——数据变换全部内联。
5. **字符串 + int 直接拼接在 VM 抛错**（"cm-" + .send_seq）：数字一律
   `.to_string()`（musk secretary_helpers 先例）或 f-string。
6. **`use back.api` 在 VM 轨链接失败**（Undefined symbol: SqliteDb.exec，P-15
   变体）——api 契约直调仅 Vue 可用，双轨统一走裸 Http。
7. **VM/iced 渲染崩溃三连**：空文本节点、`bg-x/10` slash 类、方括号任意类
   （max-w-[75%]）触发 container.rs unwrap 崩溃——已改非空守卫与 VM 安全等价类；
   VM 轨会话列表条目暂隐藏（show_conv_list 按轨折叠），切换经联系人按钮（幂等）。
8. **服务器单 token 语义**：同名重登重签 token 并作废旧 token（blog 同款）——
   测试辅助进程 re-claim 会作废被测客户端 token（vm-basic D 失败根因），
   测试用 identities 列表解析 id，不 re-claim 被测身份。
9. **空文本节点/空串渲染**：侧栏会话 last_message/time 为空串时渲染空文本参与
   iced 容器布局（崩溃诱因之一）——空值不渲染（非空守卫）。
10. **工具链**：`time.now_ms/now_sec` 后端转译目标在当前平铺 a2r_std 不存在
    （E0433）——时间取 SQLite strftime（秒级）；`to_int` 是点方法重映射保留名
    （E0423）——用 parse_int；下标赋值 `.at` 不支持——排序下沉 SQL。
