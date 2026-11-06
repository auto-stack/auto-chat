---
plan_id: CHAT-003
status: execution_done
feature_name: 重开后新消息与失败重试编号隔离
author: [Codex]
created_at: 2026-11-06
updated_at: 2026-11-06
plan_revision: 1
current_step: 2
total_steps: 4
base_branch: main
base_commit: 378a7f2fb99eb2f8954f13ec73ae2d4346ec20da
supersedes_spec_components: [docs/specs/chat/standalone-runtime-and-identity.md]
new_spec_components: []
touched_goals: []
---

# CHAT-003：重开后新消息与失败重试编号隔离

## 0. 变更摘要

OS054真实原生双端互发后，关闭重开甲、恢复登录、再发送不同正文，数据库仍只有两条：新消息重用了cm-0-u-2。CHAT-002归档不重开，本计划补齐既有新意图与重试的生命周期区分。

## 1. 目标

新登录客户端从零计数也不与旧消息编号碰撞；失败重试继续使用同一编号，服务端UNIQUE与权限校验不变。Vue与原生真实关闭重开继续发送；不把身份/token放入公开消息元数据。

## 2. 架构方案

使用独立D:/autostack/auto-chat main，一app一个写入者；OS054授权补必要app前置并最终交付，包含本有界修复/检查/提交/push/组合消费。无新worktree、链接、服务supervisor或认证模式；只改纯.at。认证结果新增公开send_nonce字段，后端用既有rand.secure_hex(32)独立抽取，绝不由secret/token派生。普通登录/注册前若随机失败，返回ok=false具名错误且不调用仓储写入。成功时新前缀+当前序号+身份ID构成client_msg_id；前端登录/注册赋新前缀并重置序号，退出清前缀。该前缀不是授权能力，读写仍由token及参与者关系裁决。

## 3. 技术栈

现有api.at→db.at→repository.at/SQLite，既有Rust HTTP服务、Vue与iced。公共UI060bcacacf7补回调发射，是原生消费前置，不在本app内改生成代码。

## 4. 需求与证据

源378a7f2；src/front/chat_store.at SendText拼cm-seq-my_id，send_seq仅实例内。实际反例native-chat-reopen-probe-r152.json在plan054/t04，已接受控制甲乙两条可读且发送者正确。目标同原054 AC03；原始截图/日志仅plan-artifacts/plan-003，父消费证据保留054，不入Git。依赖根显式OS054组，保留旧库，无迁移/reset真实用户数据。

## 5. 详细设计与规范增量

register/login响应分别新增send_nonce str，不删除旧字段；旧客户端可忽略新字段。新客户端缺前缀时不发送新意图，避免连接旧后端时静默复用编号；显示具名兼容错误。重试沿pending.client_msg_id，不生成新key。随机失败在仓储之前，数据库无身份/token变化。对同一消息的retry幂等，不宣称无限计数或跨版本新认证兼容。Spec记录当前会话前缀、零计数重开和旧后端拒绝。

## 6. 验证设计

| ID | 路径/不变量 | 输入与区分oracle | owner |
|---|---|---|---|
| C01 | 生成Rust后端实际认证响应 | 注册与同身份恢复两次，独立send_nonce不同、64hex、不等于secret/token；失败凭据无有效身份响应 | work |
| C02 | 真UI新意图与retry | Vue真实界面两身份发信→重载/凭据登录→不同正文发送，数据库新增恰一条；断网retry原key不多写，沿既有失败流程 | work |
| C03 | 原生指针+键盘+共享Rust | 同上新会话序号0仍新增，历史可读；甲乙归属和C读写拒绝保持 | work/OS054 |
| C04 | 兼容与失败 | 无send_nonce应答不发送新消息且可见错误；真实旧编号碰撞反例为red，不删除旧消息使测试绿 | work |

实施/内部检查/最终app artifact复审顺序同clone；同上下文复审须明确局限，不冒充OS054要求的独立最终复审。代码冻结后复审绑定修订与提交；通过后push、组合pin消费，清理仅本计划独占证据/输出，父验收所需建立具名hold。

## 7. 验收标准

- AC01：成功注册/登录返回独立CSPRNG公开前缀；随机失败不得先修改仓储。
- AC02：两端真实重开恢复后新消息新增一次，retry保留原编号与幂等。
- AC03：C隔离/无token泄漏/旧历史不变；旧后端兼容错误可见。
- AC04：Spec、README、修订绑定复审、push与OS消费可追溯。

## 8. 任务清单

- [x] T00(work)：纯.at后端前缀与前端新意图/缺前缀拒绝，永久复现测试。实际C01 8断言、Vue T5/T9/T10 3通过，原生和最终artifact审查仍待T01/T02。
- [x] T01(work)：C01..04实际双端/数据库控制，Spec更新，冻结提交。原生r5失败气泡→恢复→点击重发保留原key且只增一行，确切边界/哈希见round3。
- [ ] T02(review)：绑定当前修订/提交的最终artifact复审，限制作实声明。待MX01修复后当前基线复审；同实施上下文，非独立，不能替代054最终独立复审。
- [ ] T03(merge)：push、归档、消费hold与清理回执，OS054更新固定pin。

## 9. 复审记录

- stage: new | plan_id: CHAT-003 | plan_revision: r1 | outcome: pass | next: work/T00
  原生实际red与源码一致；现有CSPRNG在repository成功使用，采用相同Rust生成支持。保持认证/幂等/隔离标准和repo范围。用户完整054目标授权必要前置，未新增用户决策。

## 10. 待决事项

无；原生054整体验收和独立最终复审仍由父计划承担。

- stage: work | plan_id: CHAT-003 | plan_revision: r1 | round: 1 | outcome: T00 passed; native pending | next: work/T01
  .at additive auth response send_nonce independently generated before repository register/login; failed auth clears it; UI assigns new prefix/resetseq, logout clears, missing prefix hides composer and displays compatibility error while retaining registration secret banner. Retry path unchanged. Real generated Rust backend prepare exit0/1m54s. First auto run cold backend exceeded existing120s readiness window; owned children absent afterward, then explicit Cargo preparation completed, retry uses same now-built profile and becomes ready; not treated as a test pass from timeout.
  Owner service17827 PID28972/Vite3414 PID32148 are isolated CHAT_DATA_DIR plan003/data/chat, CHAT_TEST_MODE=1, no legacy mode. C01 permanent Python response contract8assertions pass; first harness incorrectly parsed void logout as JSON, corrected without weakening payload assertions. Vue permanent smoke T5 offline/retry, T9 new page/recovery/next message/full reload, T10 response missing nonce all3passed/8.7s, session-intents-playwright.log. Windows .cmd grep quoting rejected before tests; final uses direct Node Playwright CLI, not a hidden skip. Playwright artifacts are outside checkout; trace/video/failure screenshot disabled to avoid credentials. No native task or app delivery/push claimed.

- stage: work | plan_id: CHAT-003 | plan_revision: r1 | round: 2 | outcome: native reopen and old-backend compatibility closed; native retry waits scoped UI060r5 | next: work/T01
  Formal owner native first build hits existing gpu-allocator0.27/windows0.57 versus wgpu0.58 type mismatch10errors. Aligned only that generated Cargo.lock dependency edge to allowed0.58, preserving all package versions/checksums; locka832e6aa349a952ad9f2692933f78e4804397ff0af517b3de77d0c56ec8ecb7a→023eab722de1fd91e68644a9aafa08eb1eec309efd162e2997a677ad2a78c6cf. cargo metadata--locked validates; formal retry exit0/2m13s. SDKbcacacf7/toolv11, source5b9725fbf06959148bec4facf4dcd3a01a741369, owner port17827, receipt/published/targete6b714f042cafd8c21ab16f514c359b58ed2d3c05762b84e170a1c39e91c4bff. Explicit native owner preview via existing desktop adoption, not a fixed-pin OS acceptance or registry launch claim. No generated business-source edits.
  True pointer registration A(u2)/B(u3), UI one-time secrets optically captured only in worker46904 memory; original/crop frames deleted, banner dismissed by visible button. A real recoverylogin0→1; click B/send C003 原生重开前54.25 persists; child25060 normal close0 with handle captured before Close, backend28972 and Blog observer42120 live. Reopen child36588, actual credentiallogin, actual contact click restores first message, next distinct C003 原生重开后新意图8.125 persists. Both keys match cm-[64hex]-0-u-2 with different nonce; extra empty Send does not duplicate. Independent native-final-oracle.json SHA562ee2f4848acedd7a8cf55f7026304d37608715f8a157c0ccfdb6195cd3385c, exact2 messages. Visible history9d7f99c236aa8ed6cd32336fd4941cf1eaa338a13e772fadf4178f7ddafa3c47 and final860e63ce4374dc4589074249321b549dfd1381aaecf1f509d3733886cba0313b inspected. First reopened probe used stale bottom contact coordinates after the list moved, leaving no active conversation; excluded that no-write probe, corrected from observed actual contact position, expected DB2 criterion unchanged. Child36588 normal close0 afterward.
  Native old-backend control: formal profile17823 rebuild exit0/8.82s changes nativeSHAc8456311fb45fd47c84db08765a9b412f3ef0ee42c7d237b6fb28010f6bb07d6. New client uses real retained054-A credential to old source378a backend42272, shows explicit service-version incompatibility and no composer; old private messages unchanged exactly2. native-compatibility-oracle.json SHA2079bfdc003fdf40b4670b709295b8d85badbd905deb5b2e50b159ebf0e6b6b7; screenshot506093f9dbb37828068ead0e635c42372605e40e5e7bf355b3b3cc9de8ed37d0 inspected; child27972 normal close0 and direct exec78870 terminal0. Automatic review rejected editing the test launch helper with only blocked by policy; no retry of that edit. Used the already-supported executable foreground CLI with fixed argv instead, preserving actual source/profile receipt separately; no denied cleanup/input bypass. Formal profile17827 restored exit0/11.08s, three-way artifact identity rechecked. Owner46904 credentials cleared/worker exit0; only parent054 A/B/C workers retain their separate test credentials.
  Repository send/read/member/auth logic unchanged byte-for-byte from378a (git diff repository.at empty), so unaffected AB/C isolation evidence from parent054 round151 is retained within that boundary. Native failed-retry original key is not yet declared passed: UI060 known concat client_msg_id numeric projection can corrupt it. UI060r5 now records and tests that compiler invariant before this app's final acceptance. C01 response8/Vue scoped3 and native reopen/C04 are closed; T01 stays open pending real native offline→failed→recovery→same-key retry on fixed SDK, then T02 final artifact review. No app push, archive or OS pin upgrade yet.

- stage: work | plan_id: CHAT-003 | plan_revision: r1 | round: 3 | outcome: execution_done | next: review/T02
  UI0608774c1c8/r5 closes known JSON failure-key/object-shape and source-input freshness gaps: actual red compiler1/tools1, final compiler9/.14s + tools2/.62s including real managed regeneration gate. Immutable toolv12 SHA001b47383c3cedf3c3f72b2961d0bd9bb96c47cbeea056d1a0afe4516ba9ddb9 built41.45s; formal owner Chat build49.95s/exit0, input receipt includes all src/back.at file SHA, published/target/receipt1ae9764a06dedcb5dfe6e11407baf47effb360d2128e0e2e34a643fd11ffeaec. Exact native-v12-identity.json binds app sourcef98b2b78b4aba30d80dcd8e9c5628f3a86bcb7b8 (implementation5b9725f), SDK8774c1c8, hostc035. Framework060 remains separately unlanded; no upstream framework delivery claim. Earlier restored v11 profile artifact was4ef9b01ff814d3436aa57ea1719a2f54b804e0a894515fd58b8fad9260988e1f, correctly only a build identity; latest actual runtime evidence is v12/1ae.
  Real native retry actor u4/N003-Retry-r154 registers by pointer and one-time credential stays worker82088 memory. User restored physical desktop after screenshot returned zero size; no further clicks before actual fresh image4624d6fdbbe0ef10323a6db47ed3a4e66cedee60dbb286755fab4fde0fe46d26. First offline typing probe restored service before queued input reached failed state; afterward it persisted as an ordinary send, so excluded from failure/retry proof and retained explicitly as baseline rowseq1. No false failure pass. Corrected fixture pretypes visible draft while connected, records expected key seq2 from current session prefix, then intentionally stops exact owned backend25340 (creation13:10:51/parent40284/path checked, exit-1), clicks visible Send and keeps service absent until actual red failed bubble appears. Native27208, Blog42120 and other backend42272 survive. Failed phase image3b4d3ff7713caa0890948636259f97f729922e82c691637faf33011df3843c09 inspected; DB still2 baseline rows for u4 and other conversation unchanged.
  Recovery starts same compiled backend with same isolated data and CHAT_TEST_MODE=0/legacy off; PID5640, readiness GET identities200, no automatic resend before click. Real pointer1140,370 on failed bubble invokes child retry callback→parent→store; DB adds exactly1 row with original cm-[same64hex]-2-u-4 key, exact C003-offline-retry-2 text and senderu4, retains both baseline rows and other conversation2 rows. Initial post-write frame was still the prior failed frame; waited for actual settled sent state rather than calling it UI success. Final normal bubble image9a46ee06cad08a1a39960de27098aece2b621873cd1ad2fe9a0f93963747f261 inspected. Final oracle native-retry-final-oracle-r2.json SHA9a21d18f7a60393b5715c80cb4ad58a3d3cb50027151ca86c2303a3f78053b0b binds data, key, images and SDK; extra click/settle count remains3. This closes native retry C02 and callback/JSON consumer together, not a wholeOS resource gate.
  R actual logout revokes its token to0; child27208 normal close0 with handle retained before Close, backend5640/Blog42120/old backend42272 live. Worker82088 credentials cleared/exit0; prior46904 cleared too. privacy-oracle.json checked37 text/log/JSON/HTML artifacts against currently stored synthetic secret/token values, zero matches; credentials never used from database for auth, private frames removed, trace/video/screenshots disabled. Coverage is current stored values plus controlled capture policy, not a universal retrospective audit of erased tokens.
  Scope evidence C01 real response8pass, C02 Vue T5/native observed failed→manual same-key recovery, C03 actual new-page/native normal close/reopen/newmessage keyprefixes0 differ, C04 Vue mocked missing field and actual native old source378a backend error/no composer; source/API auth/member/read/write functions unchanged in repository.at, so prior054 AB/C isolation retained within that unchanged boundary. Native old-backend control was on v11, its affected login/nonce/conditional code is unchanged by r5; reused scoped proof rather than restarting unrelated campaign. Added nonce RNG failure branch is before repository call by source inspection; no OS entropy fault-injection claimed, no broader new promise for pre-existing credential RNG/meta counter behavior.
  Implementation frozen and committed; tracked source clean, .auto is generated untracked cache only. Parent054 fixed pin still378a; owner preview is not launcher/fixed-pin acceptance. Parent054 owns final frozen SDK/mixed/failure/independent review, production backend provision and remaining framework landing. App T02 review will reconstruct from current artifacts in this same clone/context with that limitation explicitly stated; no independent app review is fabricated.

- stage: review | review_scope: final app artifact | reviewer_identity: current Codex implementation session (same-context limitation; no independence claim) | plan_id: CHAT-003 | plan_revision: r1 | outcome: pass | worktree_path: D:/autostack/auto-chat | branch: main | reviewed_commit: 69b093bde01cfc6fe66413036847fe0bb7bbbd60 | base_commit: 378a7f2fb99eb2f8954f13ec73ae2d4346ec20da | next: merge/T03
  Reconstructed from committed diff + actual oracle JSON/hashes + inspected public frames, not merely executor status. App-rule independent clone exception honored, only main tree listed, no tracked implementation drift; .auto is generated untracked runtime cache and not delivered. Sources5b9725f, subsequent docs-only; dependency Lang23f3a031/Man03bb65ef/UI8774c1c8 with hostc035; formal native1ae metadata/source inputs three-way match. Auth response independent secure_hex call and nonce-empty return precede repository invocation in both register/login; failed auth clears nonce. No schema/membership/send/read source changes (repository.at exact base equality). No token-derived IDs or new credential RNG. Input-level typed params, response extras and old-backend missing/null field path cover actual two profiles.
  AC01→T00/C01 pass: actual response8 assertions plus static rejection-before-repository ordering for newly added nonce RNG failure; OS entropy injection not executed or claimed. AC02→T01/C02/C03 pass: Vue T5/T9, native normal close/reopen two different prefixes with seq0, native observed failed bubble→backend recovery→actual pointer retry preserves exact original seq2 key/text/sender and adds one row, final normal bubble and no duplicate after settle. AC03→C04/auth/privacy pass: Vue missing-field control + actual native old-backend error/no composer, scoped reuse of unchanged repository AB/C isolation from054r151, data preserved, secret/token artifact audit boundary explicitly recorded. AC04 implementation/Spec/docs ready: canonical Spec a4dc2b009c6b0ac3f756ba25a58a7555af89b1206ee43b43757021944af2d1f8 matches current tree, README links and delta reflect current behavior; touched_goals empty because this repairs existing app semantics with no registered new goal IDs. Publication/archive/consumer pin are merge-owned, not falsely marked done here.
  Review reconstruction artifact review-reconstruction.json records the same69b baseline and verified oracle hashes. No implementation/Spec edits during review. Remaining merge gate: frozen affected auth/message/composer UI union (all10 smoke cases are justified by shared auth response/new-intent composer gating) + C01 on a newly isolated owned test backend; repository migration/legacy machinery and language full suites unchanged/out of this gate. Parent054 production backend lifetime, mixed/failure union, UI060/949 actual landing and independent final review remain parent-owned open criteria; this pass grants no parent completion or upstream framework delivery. Named parent-consumer retention will be recorded before app closeout. No outstanding work-owned finding is moved into debt.

- stage: merge | plan_id: CHAT-003 | plan_revision: r1 | round: 4 | outcome: needs_fix | finding: MX01 | next: work/T01 scoped fixture diagnosis
  Frozen gate C01 again8passed; full affected auth/message UI10-case union on new isolated data returned9pass/1fail/33.2s. T5 lacked expected failed bubble; gate NOT waived or archived. Owned backend30960 runs explicit existing development service config at17827 with fresh data/final-gate-r155 and CHAT_TEST_MODE=1, ready identitysvc-30960-18e55da711c602c8. Earlier manual recovery5640 intentionally ended exit-1 as fixture cleanup (not a normal production-release pass), native evidence data/chat preserved, other backend42272/Blog42120 alive.
  MX01 diagnosis entry: helper openConversationWith clicks peer then waits first peer text, which may already be the sidebar rather than loaded thread. Source OpenIdentity sets active ID only after async POST returns; SendText drops without active ID. Failed DOM context shows connected empty thread/no pending, so no proof that intended send reached the active-conversation branch. Correctness requirement is unchanged: actual active conversation + aborted POST must produce failed bubble and manual retry. Before calling this a product failure, run deterministic open-response delay with counted aborted send requests, then bind readiness to actual thread heading. Retain9 passing cases and native/API/source proofs; reopen T01/T02 only for fixture repair/review. New baseline will include test changes; original69b review is historical, not blanket pass for changed tests.

- stage: work | plan_id: CHAT-003 | plan_revision: r1 | round: 5 | outcome: execution_done (MX01 fixture repair) | next: affected review/T02
  Deterministic legitimate control delays conversations/open response1000ms. With original helper, counted aborted-send requests remained0 and test failed before the intended HTTP-failure branch (fixture-conversation-red.log); confirms the sidebar-name wait did not establish active conversation. Corrected shared helper waits actual thread title .text-base.font-bold with exact peer text. T5 retains same failed-bubble/manual-retry assertions and8s budgets, adds positive aborted-request count, no skip/timeout weakening.
  Targeted T5 then passed; T9 exposed second fixture oracle error: whole-page exact text count2 includes legitimate sidebar last-message preview. Actual DB showed old and new message counts1 each. T9 now counts actual sent bubbles and independently reads peer contacts/history with legitimate peer login; no API message/conversation prewrite. Both persisted old/new texts must each occur exactly1. Final T5/T9 both2passed/8.7s (fixture-conversation-final.log). Old partial fixture-green run1pass/1fail retained, not counted as final green. Product source/API/SDK/Spec unchanged from69b baseline; native retry/reopen/C04 and C01 evidence reused under that explicit unchanged boundary.
  Final merge union must run again after affected review on committed fixture baseline; no archive or push claimed while gate was red. Existing global plan003 also contains independently held auto-database namespace; no root deletion permitted. Chat-owned top-level files/directories will have an explicit ownership manifest and OS054-CHAT003-CONSUMER hold until parent054 independent review/final gates, without touching auto-database or its hold.
