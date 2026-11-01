# auto-chat：独立可用性路线图

更新：2026-11-01。现实现以 docs/specs 和实际交付为准，计划目标不表示已实现。

| 顺序 | 计划/成果 | 当前状态 | 进入条件与边界 |
|---|---|---|---|
| 1 | [CHAT-001：真实会话与历史](plans/archived/001-real-conversations.md) | 已交付归档/r3、7/7；Vue8/8、VM4/4是其冻结版本记录 | 保留联系人、持久化与幂等；旧认证/全员流边界不因此消失 |
| 2（当前） | [CHAT-002：独立启动、身份凭据与会话隔离](plans/002-standalone-identity-and-isolation.md) | executing 8/9（复审中）；T-00..T-06 交付：自管隔离验收门、SSE 私聊旁路移除（送达=已鉴权按会话轮询）、凭据模型（256-bit 恢复凭据+会话轮换+退出撤销）、受控旧库迁移（备份/legacy 锁/env 门控一次性 adopt）；Vue8/8、VM4/4、identity 门 41/41 为当前版本记录 | 依001；框架前置已解除（auto-lang Plan 907 `secure_hex` + auto-man CLI 修复，均按各自 owner 仓规约交付）；T-07 独立复审与 T-08 归档进行中 |
| 后续 | AutoOS统一装配 | 未启动，另立OS计划 | 接收各app已推送、单独运行验证的精确提交；本轮不更新pin |
| 后续 | Linux支持 | WAIT_DISTRO_M1 | 等auto-os-distro完成Nix＋COSMIC基础；不阻塞002的本机任务 |

002已交付面：服务端关闭冒名（同名不再授予身份）与公开流字节泄漏；合法凭据重开、A/B 互通、C/匿名无消息、迁移失败保全（备份+逐字一致+取消零写入）、重启后下一次发送均由 41 断言认证门与双端回归覆盖，负控（放行型 stub）证明断言区分性。

群聊、音视频、AI、端到端加密和公网账号运营不纳入本轮。框架只有经生产路径探针确认缺项时才提实际owner最小前置，不重建HTTP/SSE生态。工作位为独立clone main；不自动创建会话或开始work。

[README](../README.md) · [现实现规范](specs/chat/basic-capabilities.md)
