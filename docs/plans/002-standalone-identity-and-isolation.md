---
plan_id: CHAT-002
status: reviewed
feature_name: "独立启动、身份凭据与会话数据隔离"
author: [Codex]
created_at: 2026-10-31
updated_at: 2026-11-01
plan_revision: 1
current_step: 7
total_steps: 9
base_branch: main
base_commit: 992067fc2313932e0a6683142630569f5f6df477
depends_on: ["CHAT-001"]
supersedes_spec_components: ["docs/specs/chat/basic-capabilities.md"]
new_spec_components: ["docs/specs/chat/standalone-runtime-and-identity.md"]
touched_goals: []
---

# CHAT-002：独立启动、身份凭据与会话数据隔离

## 0. 变更摘要

接续 CHAT-001 的真实联系人、消息、SQLite 历史及双端客户端，补齐独立运行的入口和身份/消息隔离。001 保持归档；不重做聊天产品、不要求先完成 OS 通讯框架。现有纯名字登录、可预测 token 和全员 SSE 不能作为下一版身份与私聊边界。

## 1. 目标

- 无 AutoOS 宿主时，按 README 从本仓准备依赖并启动 Vue 或原生 VM 客户端；两个身份真实互通、退出重开保持历史。
- 既有身份只能凭有效秘密证明恢复；同名输入不授予身份，token 不由用户编号/时间拼接。第三身份和未认证连接不能读写、订阅或收到私聊内容。
- 保留会话隔离、断网失败态、同意图幂等重发与联系人界面。认证拒绝不能损坏旧库或丢弃未发送文本。

非目标：群聊、语音视频、AI、端到端加密研发、公网部署/账号运营、OS 集成与 Linux。首个受验部署 profile 为本机回环后端＋独立客户端；扩大网络暴露面另立合同。

## 2. 架构方案

开发、内部检查和最终复审顺序使用同一个 `D:/autostack/auto-chat` 独立 clone、`main` 分支；不新建应用 worktree、不在 AutoOS 子模块中实现，一 app 一写入者，复审时暂停实现写入。框架变更必须在实际 owner 仓另走其 Plan/worktree 规约；本计划不自动取得框架源写入权。

用户本轮授权（2026-10-31）：建立后续计划、更新本 app README/roadmap、提交与推送这些文档；**暂不实施，不更新 AutoOS 子模块**。后续实施需另行进入 work。应用验收与交付不以 AutoOS 装配或 Linux 为前置；Linux 仍 `WAIT_DISTRO_M1`。OS 组合版本由未来统一集成计划接收，本计划 merge 只交付 app，不改父仓 gitlink、manifest 或 `.gitmodules`。

实现保持纯 `.at`，复用公开 SDK 与既有测试；不手写业务 Rust、不改生成 Rust/Vue 或临时生成目录来交付修复。`docs/specs/` 是现实现单源；下面的规范增量只是提案，本轮不写 canonical Spec、旧 ledger 或手工索引。原始截图/日志/报告本地保存，Plan 记录命令、退出码、版本/hash 和摘要；不提交新的非 Markdown 证据附件。

复用 `src/back/api.at` → `db.at` → `repository.at` 的服务端归属校验和 SQLite 数据，不自建第二套消息仓储。身份秘密、会话访问和流订阅均在服务器验证；UI 过滤不能充当权限边界。

T-00 优先核验当前 SDK 认证、随机数、摘要与会话能力，冻结一条可运行的最小凭据 profile（已有安全认证方案，或受支持的高熵恢复凭据）。若选择密码，必须使用已有密码 KDF，不能用普通 SHA256 充当密码哈希；不得自创密码学、用 shell 拼 token。缺少必需公开原语时，只阻塞对应任务并向实际 owner 提最小前置。

消息送达可使用已鉴权的按会话轮询。只有服务器真正支持鉴权/定向分发时才保留携带私聊数据的 SSE；否则移除该公开流/私密自动广播，用现有轮询完成基本实时体验，不要求先改造整个 SSE 生态。必须检查实际生成的 HTTP 路由与字节流，不能只删除前端订阅代码。

## 3. 技术栈

应用 `.at`、现有 Rust 生成后端、SQLite；Vue/Playwright 与原生 AutoUI MCP。复用 `tests/basic/verify_basic.py`、`vm-basic.mjs`、`tests/smoke.spec.ts`。生成 HTTP/SSE 的当前实现已在 auto-web，不沿历史路径误派 auto-lang；公共语言原语仍按真实 owner 分工。

## 4. 需求分析与背景调查

- 已观察：`repository.at::login_row` 按名字复用身份并写 `tok-<uid>-<epoch>`；nonce 只转交这个 token，没有证明既有身份所有权。
- 已观察：`api.at::SendResult` 含完整 Message；auto-web `api_gen.rs::generate_events_rs` 用单一全局 BUS，POST 自动广播返回载荷，stream 直接 subscribe。001 的写入 token 校验不覆盖流泄漏。
- 已观察：现有验收依赖预先运行的固定端口后端；`test_mode_on` 只看 reset HTTP 200，而普通模式也可能空操作返回 200，不能据此确认隔离。新门须绑定本次启动 PID、数据根、测试模式及随机端口，不向现有服务发 reset 探针。
- 已交付能力：001 的双客户端收发、持久化、幂等、Vue 8/8 与 VM 4/4 是回归输入；本轮不宣称已在新身份方案下通过。

| 源文件 | SHA256（完整值） |
|---|---|
| `docs/specs/chat/basic-capabilities.md` | `432bfb7d5755a99053c9c163f18403f25a17341783cf299880fb31cafe0badf2` |
| `docs/plans/archived/001-real-conversations.md` | `f0d5144f84b3421c10ed27d2212bc2fa62d1c09c3fbb4f5c674a3ac2962600bd` |
| `src/back/api.at` | `f60601b469fecfc6fc2341d6cd0f109f0b710082d90d665aacb9a0973da17292` |
| `src/back/repository.at` | `39c0c1733619772bfe3788f0c87fc235c0170442710f66bc30a4af9b43e50b6a` |
| `src/front/chat_store.at` | `9bfdefb4e86b134b02328cff98917982f7e9857f0d9778e999cc5e35953106a4` |
| `tests/basic/verify_basic.py` | `0183e1a1ae9d90c8cf124f42af6116b0480f8d46e637b149561f9205b7233567` |
| `auto-web` 观察版本 | `c48924f3381e775b8435c3989e739df347570f2c` |
| `D:/autostack/auto-web/crates/auto-web/src/api_gen.rs` | `364d347f22f72290d1595ca887867e458294f6092fb5776d6cbcac1c4aeb1aa5` |
| `D:/autostack/auto-web/crates/auto-web/src/http_server/server_route.rs` | `5e5ccda16f1c242e5772e537ff1db8616b148e081a2db0c07486f9398e4b1a45` |

## 5. 详细设计

1. **T-00 决策稿（新增）**：`docs/plans/evidence/002/standalone-decision.md`，冻结 CLI/tool 身份、公开 SDK/实际 owner、回环监听、凭据生命周期、旧库迁移和送达方案；记录冷准备/就绪的有界超时、可见阶段与失败分类。来源版本已前进时重核本计划证据，不沿旧缓存推定能力。
2. **身份与会话**：新注册与既有身份恢复明确区分；新秘密至少具备受支持的 128-bit 安全随机强度，不进入公开身份/nonce 广播、日志或 URL；退出撤销本次会话，旧凭据不能继续访问。具体公开接口在 T-00 固定，服务端负责所有权，不相信前端 sender。
3. **旧数据**：用户/会话/消息 ID 保留，原库先备份并验证迁移；旧弱 token 不能作为无条件长期登录通行证。无法证明归属的历史身份须走明确的本机受控恢复流程，不能把身份授给首个输同名的客户端；拒绝/取消保留原库。T-00 必须把这一流程写清后才能实施迁移。
4. **消息与订阅**：A↔B 私聊时 C 与无凭据订阅者不能取得正文、私密会话标识或凭据；订阅建立及失效后继续消费都按冻结方案验证。轮询方案须删除可旁路的私密广播面，SSE 方案须在服务器按成员筛选；同时验证正常双向收发和断线恢复。
5. **独立运行**：提供一条文档化准备＋启动流程，原生 profile 自动孵化或显式复用本 app 后端，不能必须先开 Vue；测试自管后端/前端及随机端口，仅清理本次进程，不停止已有 Chat 后端。冷准备可耗时但有明确进度/超时/失败，不把 120s 后端失败当成功。

### 规范增量

| delta_id | add/modify/retire | docs/specs/... target | before/after rule | rationale | acceptance IDs |
|---|---|---|---|---|---|
| SD-01 | modify | docs/specs/chat/basic-capabilities.md | 名字即登录/全员流 → 有秘密的身份恢复＋服务端会话隔离＋凭据不入对端可见元数据；旧数据迁移与退出语义；API v3（register/login/logout/adopt，me+stream 退役） | 消除可冒名与跨会话字节泄漏（含复审 F-1 元数据面） | AC-02/03/04 |
| SD-02 | add | docs/specs/chat/standalone-runtime-and-identity.md | 新增独立准备/启动、冷缓存与凭据/送达 profile、版本证据、已知边界 | 不依赖 OS 或手动先开另一端 | AC-01/05 |

## 6. 测试设计

当前命令 `python tests/basic/verify_basic.py --profile vue|vm` 由 T-05 扩展为自管隔离门；认证/原始流补充入口 `tests/basic/verify_identity.py` 为**拟新增**，T-05 负责使其可执行。运行态/旧库夹具由 T-01/T-02 准备，不能将提案样本记为已验。

| Case ID | AC / invariant | 输入/状态与真实入口 | 区分性 oracle / 预期 | owner_stage / 边界 |
|---|---|---|---|---|
| C-01 | AC-01/05 | 本 app 无 target 缓存的准备＋Vue/VM 启动；坏 tool/占用端口各一例 | 页面/窗口实际可操作；本次后端身份和数据根正确；失败非零且仅收割自己子树 | work；不承诺构建时长 |
| C-02 | AC-02 | A 建立身份；C 输入 A 的名字、伪凭据/旧弱 token；A 合法凭据重开 | C 不得取得 A；A 可恢复相同历史；新秘密不由 uid/time 预测 | work；最小 profile |
| C-03 | AC-03 | A→B 发送唯一正文哨兵；C/匿名直接访问 HTTP 与原始 SSE，含重连/退出后旧会话 | C/匿名字节流和响应均无正文、私密标识、凭据；A/B 正常收发；不能只看 UI 隐藏 | work；使用隔离第三身份 |
| C-04 | AC-04 | 旧库迁移成功/取消/中途拒绝、同 client_msg_id 重发、后端强杀重开 | 旧 ID/正文逐字一致，失败原件哈希不变；同意图只一条，恢复后下一次发送成功 | work；用户库不参与 |
| C-05 | AC-05 | 去掉服务端隔离或让认证拒绝被判 pass 的受控反例（仅隔离测试树/夹具） | 对应断言必须红且总门非零；恢复合法控制通过；无 token 写入 raw 日志 | work；先证明负控触发 |

工作自检不替代最终独立上下文复审。用户未指定其他 agent/model，本计划不自动创建或联系新会话。最终 review 冻结同一 clone 与二进制版本，亲核 C-02/C-03 的原始 HTTP/流证据。

## 7. 验收标准

- AC-01（owner_stage=work）：准备后的 Vue、原生 VM 可独立启动并完成两客户端联系人→收发→重开；冷准备及错误有可观察结果，C-01 通过。
- AC-02（owner_stage=work）：合法凭据恢复，冒名/旧弱凭据拒绝且不改用户数据；退出后凭据失效，C-02/C-04 通过。
- AC-03（owner_stage=work）：第三身份/匿名的 HTTP、SSE 和重连字节面隔离；正常 A/B 送达保留，C-03 通过。
- AC-04（owner_stage=work）：旧库可控迁移、幂等重发、会话隔离和重启后下一次发送成立，C-04 通过。
- AC-05（owner_stage=work）：两个 profile 与补充认证入口均无必需 skip/pending/零场景，负控非零；Spec 候选、README 与实际 profile 一致。
- AC-06（owner_stage=review）：冻结提交独立复审 AC-01..05 与 SD-01/02，记录依赖版本及局限。
- AC-07（owner_stage=merge）：app canonical 文档按复审结果落地、计划归档/计数和链接真实、提交 push 可核验；AutoOS pin 留待统一计划。

## 8. 执行步骤

- [x] T-00（owner_stage=work；依赖001已交付；AC-01/02/03）：在本 clone 冻结当前源/工具，完成 §5 决策稿和最小可行性探针；先关闭身份/迁移/送达及冷准备决策，缺项转实际 owner 最小前置。 [✅ 2026-11-01] 决策稿 `D:/autostack/plan-artifacts/plan-002/standalone-decision.md`（sha256 `26fe4456…`）；§4 六项源 hash 逐字零漂移；auto-web HEAD 前进至 `ec9c4ba` 但被引 api_gen.rs/server_route.rs 字节一致，SSE 单总线结论重核成立。关键裁定：后端轨（a2r-std，path-pin 同源 auto-lang `b1a4871`）无 rand/无 digest/无 KDF（lib.rs 模块面实证；uuid()=epoch 纳秒 hex；simple_hash=SipHash）；bundled SQLite（libsqlite3-sys 0.27）PRNG 为 ChaCha20 但 winRandomness 种子仅 SYSTEMTIME+PID+tick+QPC（SQLITE_WIN32_USE_UUID 未定义，无 CSPRNG 输入）→ 非受支持 128-bit 熵源；VM 轨 Random 实为 SystemTime 纳秒 Xorshift64。**受支持安全随机原语缺失 → T-02 及下游阻塞，P-REQ-1 已提请 auto-lang owner（见 §10）**。
- [x] T-01（owner_stage=work；依赖T-00；AC-01/05）：复用既有调度器，补独立准备/启动与本次 PID/端口/数据根身份检查、无副作用的测试模式验证，提供空缓存与错误记录。 [✅ 2026-11-01] `tests/basic/verify_basic.py` 重构为自管隔离门（有界 auto build/cargo build 准备、随机空闲端口、隔离 CHAT_DATA_DIR、端口→PID 归属断言、只读就绪探针、仅收割本次子树）；`tests/basic/vm-basic.mjs` 硬编码 17823 改为 env 透传。冷构建实测 210s（≤300s 门）。vue 8/8、vm 4/4 经新调度器全绿（证据 `plan-002/verify-{vue,vm}.json`）。VM 轨 `auto run` 每次重生成触发 relink 文件锁 → 调度器以副本 exe 启动后端规避。事故记录：一次 VM 预跑因本脚本未传 AUTO_HTTP_PORT，auto run 在 ：17823 以默认 APPDATA 数据根拉起后端写入测试身份两行；已备份至 `plan-002/appdata-pollution-backup-chat.db` 并逐表清零复核（APPDATA 现为 0 行）。
- [x] T-02（owner_stage=work；依赖T-00；AC-02/04）：在 repository/API 及现有前端 store 接入冻结凭据/会话、受控旧库迁移，先建立 C-02/C-04 反例再实现并回放。 [✅ 2026-11-01] P-REQ-1 已解除（auto-lang Plan 907 `secure_hex` 归档 `6ee01e0a6`+merge `9381e0746`，i64 修正 `ed38cf973`，codegen face `eda930b09`；auto-man CLI 死 feature 修复 `55c98c7`——均按各自 owner 仓 worktree 规约）。反例先行：`probe-baseline.out`（同名接管 True、旧 token 可读、SSE 泄私文）+ `c04-prefix.out`（legacy 库同名接管/旧 token 读私文）。实现：repository.at v2（secret/status/legacy_token 列、`identities_v2_ready` PRAGMA 检测、`migrate_to_v2` VACUUM INTO 备份→事务 ALTER→legacy 锁（token→legacy_token 后清空）、register/login/logout/adopt_legacy_row，凭据=secure_hex(32)）；api.at register/login/logout/legacy-adopt（/api/me+pending_login 退役）；db.at 委托；前端 store/App（登录=名+secret、注册一次性展示 secret、退出撤销）。工具链集成三处消费者侧修复均已落地 owner 仓。
- [x] T-03（owner_stage=work；依赖T-02及必要已交付前置；AC-03）：落实定向流或鉴权轮询，关闭公开私密广播旁路；保存 C-03 原始字节级证据。 [✅ 2026-11-01 复审修复后闭合] SSE 旁路已关（流 404、零广播调用方；baseline/post 字节证据存证）。F-1 修复双层：(i) chat_store.at client_msg_id 改为 seq+my_id（公开标识，绝不嵌 token）；(ii) repository.message_rows CASE 擦除非发送者 cmid（纵深防御，旧客户端形状也安全）。新门断言 4 条：源检 tripwire + 探针（甲以自身 token 为 cmid 发送）→ 乙字节面零 token + 甲本人视图保留 cmid（去重键不破坏）。identity 门 45/45。
- [x] T-04（owner_stage=work；依赖T-01/02/03；AC-01/04）：真实双客户端 Vue/VM 联系人、失败重发、退出重开与下一次发送；保持输入/幂等/历史回归。 [✅ 2026-11-01] 双端测试更新至凭据模型（smoke.spec.ts claimIdentity 注册/登录+secret 输入、T6 正名"鉴权轮询送达"；vm-basic.mjs claimIdentity+双输入框+登录按钮）；自管门复跑 **Vue 8/8、VM 4/4**（verify-{vue,vm}.json，随机端口+隔离数据根+PID 归属，APPDATA 复核 0 行）。幂等/历史/断线重发由 T3/T5 用例与 C-04 幂等断言覆盖。
- [x] T-05（owner_stage=work；依赖T-04；AC-05）：使补充入口可执行、跑 C-01..05、原有双端任务与负控；整理 SD 候选，不以已有总数盖住新失败。 [✅ 2026-11-01 复审修复后闭合] 门更新：C-03 增 F-1 双层回归断言（共 45 断言），C-05 负控阈值收紧 red==4。**修复基线重跑：identity 45/45、Vue 8/8、VM 4/4**。SD-01 增补规则"凭据不得出现在对端可见的消息元数据中"（随 merge 沉淀）。
- [x] T-06（owner_stage=work；依赖T-05；AC-01..05）：核对源/依赖漂移、凭据零泄漏、所有必需 oracle 与 README/roadmap，提交 execution_done 交接。 [✅ 2026-11-01] 漂移盘点：auto-lang master `eda930b0`（Plan 907+2 riders）、auto-man `55c98c7`、auto-web `ec9c4ba`（被引文件与 §4 一致）、auto-ui `6ab7f2d`；本仓交付面 hash 记录于 §9。零泄漏审计：后端 .at 无任何日志/打印；secret 不进 URL（0 命中）、不进日志；生成 main.rs 仅启动/绑定消息；GET query 携 token 为 CHAT-001 已记录框架边界（无自定义 header），随 SD-01 如实声明。README/roadmap 已同步凭据模型+验收入口+框架前置解除。必需 oracle 全部绑定实际入口（verify_basic 双 profile + verify_identity 41 断言 + 负控），无占位/跳过/历史总数顶替。
- [ ] T-07（owner_stage=review；依赖T-06；AC-06）：同一 clone 的独立上下文最终复审，未满足项返回 work。
- [ ] T-08（owner_stage=merge；依赖T-07 pass；AC-07）：仅 app 文档/Spec/归档/提交 push 与恢复记录收尾；不更新 AutoOS。

## 9. 复审记录

- stage: new | plan_id: CHAT-002 | plan_revision: 1 | outcome: pass（仅有界 T-00 就绪，产品与双端验收未执行） | next: work/T-00（等待后续实施指令）。
- 现有归档计划、Spec 与源码保持原样；旧验收只证明其冻结版本与已声明范围。应用提交/push 不升级 AutoOS 组合版本。
- stage: work | plan_id: CHAT-002 | plan_revision: r1 | round: 2 | from: work（blocked 续做） | to: review | status: reviewed | outcome: pass（T-02/03/04/05/06 全交付；T-07/T-08 归 review/merge） | worktree: D:/autostack/auto-chat（main，本计划约定 clone） | base_commit: 4c1639c | dependency_revisions: auto-lang master `eda930b0`（Plan 907 `9381e0746`/`6ee01e0a6` + riders `ed38cf973`/`eda930b09`）、auto-man `55c98c7`、auto-web `ec9c4ba`、auto-ui `6ab7f2d`；工具链二进制重建（auto.exe、auto-ui-tools） | task_ids: T-02, T-03, T-04, T-05, T-06 | evidence: C-04 反例先行 c04-prefix.out + probe-baseline.out（迁移前接管/泄露）；迁移/凭据回放 C04 ALL-PASS 18/18（replay_c04.py）；认证门 verify-identity.json **41/41**（C-02 15/C-03 7/C-04 18/C-05 负控 red=4）；双端回归 verify-vue.json 8/8、verify-vm.json 4/4（凭据模型更新后的 smoke/vm 脚本）；smoke fresh 11/11 + legacy-closed 2/2（smoke_v2_auth.py）；零泄漏审计（secret 不入 URL/日志；GET query token 为 001 已记录边界）；交付 hash：api.at 8773ac4e、db.at 9b595df8、repository.at 73396d86、chat_store.at f51a8e2a、app.at 57541ce2、smoke.spec.ts 55a73d6c、verify_identity.py 299cfab3、vm-basic.mjs ce737a00 | blockers: 无（P-REQ-1 已解除并记录于 §10） | next_responsible_role: review（T-07 独立上下文最终复审，AC-06）
- stage: work | plan_id: CHAT-002 | plan_revision: r1 | round: 1 | from: drafting | to: work（继续） | status: reviewed | outcome: blocked（部分交付：T-00/T-01/T-03 完成，T-02 及下游阻塞） | worktree: D:/autostack/auto-chat（main，本计划约定 clone） | commit: （本轮交付提交） | base_commit: 270e659 | dependency_revisions: auto-lang `b1a4871`、auto-web `ec9c4ba`（被引文件与 §4 一致）、auto-ui `6ab7f2d`、auto.exe `0.1.0+plan-890…`、rustc/cargo 1.98.0 | task_ids: T-00, T-01, T-03 | evidence: 决策稿 plan-002/standalone-decision.md sha256 26fe4456…；probe-baseline.out（C-02 同名接管 True、匿名/第三身份 SSE 收到私聊哨兵）；probe-post.out（流 404、零泄露、B 轮询收取 True）；verify-vue.json 8/8；verify-vm.json 4/4；api.at sha256 8c2cec4c…；verify_basic.py sha256 da8985a5…；vm-basic.mjs sha256 f466a1cb… | blockers: P-REQ-1（后端轨受支持 ≥128-bit 安全随机原语缺失——a2r-std 无 rand/digest/KDF；bundled SQLite Windows 种子非 CSPRNG；VM 轨 Xorshift 时间种子；本计划无框架写入权）→ T-02/T-04/T-05/T-06 阻塞 | incident: VM 预跑污染 APPDATA 默认库两行身份，已备份并清零复核（APPDATA 现 0 行） | next_responsible_role: auto-lang owner（P-REQ-1）→ work（T-02 起解阻续做）。

- stage: review | review_scope: final | reviewer_identity: independent subagent context（非实现会话；亲核原始 HTTP 证据 + 自跑三道门） | plan_id: CHAT-002 | plan_revision: r1 | outcome: needs_fix | worktree_path: D:/autostack/auto-chat（本计划约定 clone） | branch: main | reviewed_commit: 5e50763 | base_commit: 4c1639c | dependency_revisions: auto-lang eda930b0、auto-man 55c98c7、auto-web ec9c4ba、auto-ui 6ab7f2d（HEAD 前进至 6d7fc69 为 docs-only，被验版本为其祖先） | spec_inputs: §5 SD-01/SD-02 措辞与实现一致（pass） | acceptance_results: AC-01 pass（vue 8/8、vm 4/4 复跑于冻结提交）；AC-02 pass（原始证据 a/b/c/f + 41 断言门）；AC-03 **fail（F-1）**；AC-04 pass；AC-05 pass-with-finding（F-2 负控阈值偏松；F-3 陈旧注释） | pending_closeout_gates: 修复后受影响门重跑（identity+vue+vm）；统一回归归 merge | findings: **F-1（high, AC-03/SD-01）**：chat_store.at:234 起 client_msg_id='cm-'+seq+'-'+my_token，服务器经 /api/messages 把 client_msg_id 回给全部参与者——对端字节面获得发送方活会话 token（复审者实测乙响应含甲完整 token）；现有门不可检（C-03 手选 cmid 且只测丙/匿名）。F-2（low）：C-05 阈值 red>=3 应收紧 red==4。F-3（info）：SSE 时代陈旧注释（api.at:156 广播措辞、store 头注/死 handler、app.at 17823 提示）。F-4（info）：auto-ui docs-only 漂移，merge 记录 | evidence: plan-002/review/（baseline.txt、verify-*.json、raw-evidence.json、raw_evidence.py、review-record.json） | next: work（F-1/F-2/F-3 修复→受影响门重跑→复审）

- stage: work（repair F-1/F-2/F-3） | plan_id: CHAT-002 | plan_revision: r1 | round: 3 | from: review（needs_fix） | to: review（复检请求） | status: reviewed | outcome: pass（修复基线全绿） | worktree_path: D:/autostack/auto-chat | branch: main | base_commit: 1d21951 | code_commit: （修复提交） | task_ids: T-03, T-05（受影响重开→闭合） | repair: F-1 双层（cmid=seq+my_id；message_rows CASE 擦除他人 cmid）；F-2 red==4；F-3 api.at/store 头注/死 handler/SendResult+TypingEvent 镜像/app.at 端口提示清理 | gates_rerun: identity 45/45（+4 新断言）、vue 8/8、vm 4/4 | findings_closed: F-1/F-2/F-3；F-4 留 merge 记录 | next: review（同一独立复审者复检受影响判定）

- stage: review（复检） | review_scope: final（受影响判定） | reviewer_identity: 同一独立复审者上下文（repair re-review） | plan_id: CHAT-002 | plan_revision: r1 | outcome: **pass** | reviewed_commit: 2dc7836 | acceptance_results: F-1 双层闭合（源检+生成物核对；最坏向量实测：甲以活 token 为 cmid 发送，乙字节面零 token、甲本人视图保留去重键、幂等重发同 id；raw-evidence-r2.json 14/14）；AC-05 门重跑 identity 45/45、vue 8/8、vm 4/4（base=2dc7836）；F-2 red==4；F-3 全清 | findings: F-5（info，非阻塞）：types.at LoginAck 死类型遗留——随下次 docs pass；F-4 merge 记录 | evidence: plan-002/review/（raw-evidence-r2.json、review-record-r2.json、refreshed verify-*.json） | next: merge（T-08）

## 10. 待澄清事项

本次规划没有待用户重新确认的产品方向。T-00 负责核实技术能力与实际 owner，决策稿必须先闭合再进入依赖实现。若探针显示必须改变目标、降低必需验收或扩大跨仓写入范围，报告具体证据并保留受影响任务未完成；不得用占位、跳过、API 预操作或历史总数替代必需用户任务。

**已解除（2026-11-01）**：P-REQ-1 经用户目标指令授权后由实际 owner 仓按其规约交付——auto-lang Plan 907（`a2r_std::rand::secure_hex`，OS CSPRNG；归档 `6ee01e0a6`）+ i64 签名修正 `ed38cf973` + codegen standalone face `eda930b09`；auto-man CLI 死 feature 消费修复 `55c98c7`。本计划凭据/迁移/门禁全部落地（见 §9 round 2 回执）。可选 P-REQ-2（KDF）仍非必需——当前 profile 不选密码。
