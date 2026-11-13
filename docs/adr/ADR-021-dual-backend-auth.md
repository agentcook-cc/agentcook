# ADR-021：双后端共用身份

Java 管理账号、密码、角色和额度。Python 运行时用同一个用户 UUID 隔离会话和 Agent 实例。两个后端使用同一个 HS256 密钥和 `agentcook-java` 签发者，客户端将 access token 发送给所访问的后端。

注册和登录返回 access token 与 refresh token。access token 的 `sub` 为用户 UUID，`typ=access`，并携带 `roles`、`scope` 和 `preferred_username`。refresh token 的 `typ=refresh`，带独立 `jti`，只发给 Java 的续期接口。Java 续期时重新检查账号状态和角色，返回新的一对令牌。已签发的 access token 在有效期内仍可通过签名校验，续期也不会主动撤销旧 refresh token。

Java 对管理操作检查管理员角色，对会话检查归属。管理端同步使用角色声明控制界面入口。Python 在允许匿名的开发环境提供匿名体验，生产环境要求鉴权。Helm 从同一个 Secret 注入两端密钥，管理员列表默认空。生产环境关闭自动建号，配置管理员身份前应在私有环境完成账号注册。

运行时完成一轮聊天后，将调用者的 access token 传给 Java 扣减额度。Java 在事务内锁定用户行，达到上限后返回当前状态供运行时降级。gRPC 入口沿用同一调用者身份，将 Authorization 元数据转交给 HTTP 运行时。
