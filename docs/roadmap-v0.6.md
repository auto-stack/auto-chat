# auto-chat：独立可用性路线图

更新：2026-10-31。现实现以 docs/specs 和实际交付为准，计划目标不表示已实现。

| 顺序 | 计划/成果 | 当前状态 | 进入条件与边界 |
|---|---|---|---|
| 1 | [CHAT-001：真实会话与历史](plans/archived/001-real-conversations.md) | 已交付归档/r3、7/7；Vue8/8、VM4/4是其冻结版本记录 | 保留联系人、持久化与幂等；旧认证/全员流边界不因此消失 |
| 2（当前） | [CHAT-002：独立启动、身份凭据与会话隔离](plans/002-standalone-identity-and-isolation.md) | drafting/r1、0/9，未实施 | 依001；先T-00验证现有SDK、迁移/送达与冷准备；轮询可作为最小送达profile，不等整个SSE框架升级 |
| 后续 | AutoOS统一装配 | 未启动，另立OS计划 | 接收各app已推送、单独运行验证的精确提交；本轮不更新pin |
| 后续 | Linux支持 | WAIT_DISTRO_M1 | 等auto-os-distro完成Nix＋COSMIC基础；不阻塞002的本机任务 |

002需从服务端关闭冒名和跨会话字节泄漏，证明合法凭据重开、A/B互通、C/匿名无消息、迁移失败保全及重启后的下一次发送。旧历史保留，必需任务不因原001总数通过而免验。

群聊、音视频、AI、端到端加密和公网账号运营不纳入本轮。框架只有经生产路径探针确认缺项时才提实际owner最小前置，不重建HTTP/SSE生态。工作位为独立clone main；不自动创建会话或开始work。

[README](../README.md) · [现实现规范](specs/chat/basic-capabilities.md)
