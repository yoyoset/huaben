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

## 工程约定(2026-10-02 用户明确要求)

按第一性原理做:先问"这件事本质要解决什么",再决定结构;按专业项目管理做:有路线、有验收、有日志。

- **单一职责**:一个模块只做一件事。读库(`context.py`)与渲染(`render.py`)分开;SQL 只在 `repo/`(`tests/test_structure.py` 强制,数据库基础设施除外)。
- **文件不无限增长**:`huaben/` 与 `tests/` 下单个 .py ≤ 200 行,由 `tests/test_structure.py` 强制。
  超限就按职责拆,**不要调高上限**。
- **可读性**:命名表意;注释写"为什么"(尤其踩坑依据),不复述代码;纯函数优先,I/O 留在边缘。
- **可扩展性**:外部依赖(LLM、TTS)走窄接口 + 可注入替身(`llm_fake.py`),不在业务里写死;
  但不为"以后可能需要"提前抽象——v1 的东西(导演脚本、PC 工人)到 v1 再做。
- **项目管理**:`BUILD_LOG.md` 只放当前状态 + 待办路线;每阶段的详细记录(做了什么/坑/暂不处理)归档到 `docs/build-log/`。每个切片:实现 → 测试 → 提交 → 记录。
