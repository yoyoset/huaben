# 话本 Huaben

AI 私人连载 + 听书(PWA)。先读 `README.md`,再按需读 `docs/`:

- `docs/architecture.md` — 已定的架构决策和理由;改决策要连同理由一起改
- `docs/v0-scope.md` — 第一版做/不做/验收标准;不在范围内的东西先不做
- `docs/lessons-from-sillytavern.md` — 前身实测踩坑,**写 LLM/TTS 相关代码前必读**

## 项目约定

- 部署目标:10.1.1.13(Docker Compose,`/opt/huaben`),沿用 13 上 vpsmon / opencode-usage 的惯例;
  远程执行用 `F:/my_ai/openwrt/tools/rsh.sh`(`rsh 13 ...`)。
- 用户的 PC 只做可选的增强算力(v1 高质量语音工人),**任何功能不得依赖 PC 在线**。
- LLM 默认 OpenRouter `deepseek/deepseek-v4.1-flash`,长文生成:关思考、frequency/presence penalty = 0。
- 用户偏好:新旧内容并行保留,不随手删除或替换;不可逆/对外操作先确认。
