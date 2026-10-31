# Leogent 开发清单

目标：完成一个 Python 编写、可安装、可运行、可逐层阅读的第一阶段 Agent Runtime。第一阶段的验收终点是一次真实的 MCP 文件任务、Session 恢复、长期记忆、上下文压缩和 Skill 加载均可在同一条代码路径中完成。

正式设计见 [docs/superpowers/specs/2026-10-28-leogent-phase1-design.md](docs/superpowers/specs/2026-10-28-leogent-phase1-design.md)。

## 已确认决策

- [x] 项目显示名为 **Leogent**，Python 导入包为 `leogent`，CLI 为 `leogent`。
- [x] 使用 Python，不使用 TypeScript。
- [x] 第一阶段以教学可读性和完整调用链为优先。
- [x] 第二阶段再发展完整 coding agent 和高级 Agent 算法。
- [x] 外部能力工具通过 MCP 接入。
- [x] 使用 SQLite 保存 Session 事件和长期记忆。
- [x] 短期记忆由每轮构造的 Working Context 表示。
- [x] Provider 同时支持云 API、本地 OpenAI-compatible 服务和可选 Transformers。
- [x] Skill 使用渐进式加载。
- [x] 第一阶段提供滚动式 CLI TUI，品牌符号暂定 `◈`，后续可替换。
- [x] 第一阶段不处理 OS、文件、进程或网络沙箱；沙箱与强制权限模型留到第二阶段。

## Milestone 0：仓库基础

- [x] 创建 `pyproject.toml`，确定 Python 最低版本、项目元数据、依赖和 optional extras。
- [x] 建立 `src/leogent` 包和 `leogent` CLI 入口。
- [x] 配置 Ruff、Pyright、pytest 和默认测试路径。
- [x] 建立 `unit`、`integration`、`e2e`、`fixtures` 四类测试目录。
- [x] 添加 GitHub Actions，执行格式检查、类型检查和离线测试。
- [x] 添加 MIT LICENSE、`.gitignore`、`.env.example` 和基础贡献说明。
- [x] 在 README 首屏写明教学定位、第一阶段非目标和“无沙箱”安全假设。

## Milestone 1：领域模型与配置

- [x] 定义 `Message`、`ModelRequest`、`ModelResponse` 和 usage 模型。
- [x] 定义 `Action`、`ToolCall`、`ToolResult` 和错误分类。
- [x] 定义 `Event`、`Session`、`RunState` 和终止原因。
- [x] 定义 `MemoryItem`、`SkillDescriptor` 和 `ContextPlan`。
- [x] 为所有领域对象添加序列化、反序列化和非法输入测试。
- [x] 实现全局配置、项目配置和环境变量覆盖。
- [x] 实现 provider profile 的密钥引用校验，禁止示例配置包含真实密钥。
- [x] 实现数据目录解析和 `LEOGENT_HOME` 覆盖。
- [x] 为配置合并、相对路径和缺失值添加单元测试。

## Milestone 2：Provider 与单轮请求

- [x] 定义 `ModelProvider`、流式 chunk 和 `ModelCapabilities` 协议。
- [x] 实现 OpenAI-compatible Provider 的非流式请求。
- [x] 实现 OpenAI-compatible Provider 的流式请求。
- [x] 实现 native tool call 与文本内容的响应归一化。
- [x] 实现 Anthropic 原生 Provider 的消息和工具调用。
- [x] 实现脚本化 `MockProvider`，支持预定义响应和请求录制。
- [x] 添加上下文窗口、输出长度、temperature 和 top-p 校验。
- [x] 实现 `leogent run --no-tui` 的单轮模型回答。
- [x] 使用 MockProvider 完成请求转换、usage 和错误路径测试。
- [ ] 使用真实云服务完成一次手动验收；live 测试入口已添加，但当前未执行真实 API 调用。

## Milestone 3：Session 与事件

- [x] 实现 SQLite schema、版本表和初始化逻辑。
- [x] 实现 append-only EventStore。
- [x] 实现 Session 创建、查询和状态更新。
- [x] 实现从事件重建 RunState。
- [x] 实现 `sessions list` 和 `sessions show`。
- [x] 实现 `resume`，恢复后继续同一 Session。
- [x] 实现 `fork`，从指定事件创建独立 Session。
- [x] 确保工具事件与相关 Session 元数据更新在同一事务中提交。
- [x] 添加进程异常中断后的恢复测试。
- [x] 添加事件顺序、重复写入和 schema 迁移测试。

## Milestone 4：MCP 与 Action 执行

- [ ] 定义内部控制动作：`remember`、`search_memory`、`load_skill` 和 `finish`。
- [ ] 定义 `ToolRuntime` 和 `ToolRegistry` 协议。
- [ ] 接入官方 Python MCP SDK 的 `stdio` transport。
- [ ] 实现 MCP Server 生命周期和连接关闭。
- [ ] 实现工具发现、namespace 和 JSON Schema 注册。
- [ ] 实现工具参数校验、调用、返回内容归一化、超时和取消。
- [ ] 实现长工具输出截断及截断元数据。
- [ ] 为 MCP 调用生成完整事件和耗时信息。
- [ ] 实现 `tools list`。
- [ ] 使用内存 MCP mock 完成工具发现、未知工具、超时和错误测试。
- [ ] 提供一个只依赖官方参考 Server 的示例 MCP 配置。
- [ ] 完成一次读取文件、修改文件和执行测试的真实手动验收。

## Milestone 5：ReAct Runtime

- [ ] 定义 `DecisionPolicy`、`ContextPolicy` 和 `TerminationPolicy` 协议。
- [ ] 实现基础 `AgentLoop` 和最大步骤预算。
- [ ] 实现 `ReActPolicy` 的 native tools 路径。
- [ ] 实现无 native tools 时的 JSON Action 降级路径。
- [ ] 实现 Action 校验、未知 Action 和格式错误恢复。
- [ ] 实现工具结果回灌、循环继续和最终回答。
- [ ] 实现取消、超时和最大 token 预算。
- [ ] 将每个关键步骤映射为 UI 事件和 Session 事件。
- [ ] 使用固定 Mock 响应完成完整 ReAct 轨迹测试。
- [ ] 使用同一 Runtime 跑通云模型、本地 OpenAI-compatible 服务和 Mock 模型。

## Milestone 6：ContextBuilder 与压缩

- [ ] 实现 ContextBuilder 的基础上下文装配。
- [ ] 实现 token 估算器和 Provider tokenizer 接口。
- [ ] 实现必需内容、最近事件和未闭环 Action 的保护规则。
- [ ] 实现工具输出 head/tail 截断。
- [ ] 实现 75% 阈值检查。
- [ ] 实现 `RollingSummaryPolicy` 结构化摘要。
- [ ] 生成带源事件范围的 `context_compacted` 事件。
- [ ] 确保压缩后原始事件仍可查询。
- [ ] 实现 `ContextPlan` 调试输出。
- [ ] 添加预算边界、压缩连续触发、恢复后压缩和失败摘要测试。
- [ ] 运行一次长轨迹，手动检查压缩前后的执行结果。

## Milestone 7：长期记忆

- [ ] 定义 Memory Store 和 Ranker 协议。
- [ ] 实现 SQLite Memory Store。
- [ ] 创建 `memory_items` 表及 FTS5 索引。
- [ ] 实现 `semantic`、`episodic`、`procedural` 和 `preference` 类型。
- [ ] 实现 scope、来源事件、置信度和时间字段。
- [ ] 实现明确的 `remember` Action。
- [ ] 实现 scope 过滤和 FTS 检索。
- [ ] 将检索结果接入 ContextBuilder。
- [ ] 实现真实删除和 FTS 索引清理。
- [ ] 添加持久化、检索排序、scope、删除和敏感值不回显测试。
- [ ] 演示跨 Session 召回一条明确写入的记忆。

## Milestone 8：Skill

- [ ] 定义 Skill 目录和 `SKILL.md` frontmatter 格式。
- [ ] 实现 Skill 发现和名称去重。
- [ ] 启动时只加载名称、描述和资源清单。
- [ ] 实现 `load_skill` Action。
- [ ] 选择后才加载正文，资源再按需读取。
- [ ] 加上文件大小、编码和路径规范化检查。
- [ ] 记录 Skill 选择和加载事件。
- [ ] 实现 `skills list`。
- [ ] 添加重复名称、缺失文件、非法 frontmatter 和按需加载测试。
- [ ] 提供至少一个示例 Skill 和一次完整加载演示。

## Milestone 9：CLI 与 TUI

- [ ] 实现 `chat`、`run`、`resume`、`sessions`、`tools`、`skills`、`config` 和 `doctor` 子命令。
- [ ] 实现 `run --json` 的机器可读输出。
- [ ] 实现 `run --no-tui`，确保管道和 CI 可用。
- [ ] 实现 `◈` 品牌头和运行状态。
- [ ] 实现流式文本、Markdown 和代码高亮。
- [ ] 实现用户、Agent、工具和错误消息布局。
- [ ] 实现输入历史、slash command 补全和取消。
- [ ] 实现底部模型、Session、上下文和耗时状态。
- [ ] 实现 `NO_COLOR` 和 ASCII fallback。
- [ ] 实现 Renderer 快照测试和 PTY 启动冒烟测试。
- [ ] 保留独立 theme/renderer 文件，方便后续重新设计 TUI。

## Milestone 10：Trace、回放与本地模型

- [ ] 实现基于 Session 事件的轨迹查看。
- [ ] 实现标准请求和标准响应的 fixture 录制格式。
- [ ] 实现 `MockProvider` 回放。
- [ ] 实现可选 `leogent[local]` 依赖组。
- [ ] 实现 Transformers Provider 的模型加载、chat template 和流式输出。
- [ ] 为本地模型实现 JSON Action 降级。
- [ ] 实现 `doctor` 的配置、数据库、MCP 和模型检查。
- [ ] 添加 OpenAI-compatible 与 Transformers 共用的 Provider 合同测试。
- [ ] 完成本地 OpenAI-compatible 服务的手动验收。
- [ ] 完成可选 Transformers 模型的手动验收。

## Milestone 11：文档与发布

- [ ] 编写 README：安装、配置、第一个任务、TUI、本地模型和无沙箱警告。
- [ ] 编写总体架构文档和一条完整 Agent 执行路径。
- [ ] 编写 Session、Memory、Context、MCP、Skill 和 Provider 专题文档。
- [ ] 编写九章渐进式教程，并链接到真实源文件。
- [ ] 提供云端、本地 OpenAI-compatible、Transformers、MCP 和 Skill 示例配置。
- [ ] 添加贡献指南、开发命令、代码边界和测试要求。
- [ ] 检查所有示例不包含密钥，本地数据库默认被忽略。
- [ ] 从干净环境按 README 完成一次全新安装验收。
- [ ] 执行全部离线测试、类型检查、格式检查和一次真实端到端验收。
- [ ] 打 `v0.1.0` 标签并撰写发布说明。

## 第一阶段完成定义

- [ ] 新用户安装后能运行 `leogent doctor`。
- [ ] 能通过真实 MCP 工具读取文件、修改文件并执行测试。
- [ ] 能恢复中断的 Session。
- [ ] 能从历史事件 fork 并独立继续。
- [ ] 能触发滚动摘要并保留原始事件。
- [ ] 能写入并跨 Session 检索一条长期记忆。
- [ ] 能按需加载 Skill。
- [ ] 能用 Mock 轨迹离线复现一次完整运行。
- [ ] 能在云端 Provider、本地 OpenAI-compatible Provider 和可选 Transformers Provider 之间切换。
- [ ] 没学过 Agent 的读者能沿教程从 CLI 输入追到最终回答。

## 第二阶段候选方向

- [ ] Plan-and-Execute、Reflexion 和可替换搜索 Agent。
- [ ] 多级摘要、检索式压缩和其他上下文压缩算法对比。
- [ ] RoPE 外推、YaRN、本地推理和长上下文实验。
- [ ] 文件、进程、网络和容器沙箱。
- [ ] 强制工具审批、降权执行和权限策略。
- [ ] 多 Agent 编排、任务委派和冲突解决。
- [ ] Web UI、远程 Session 和分布式任务。
- [ ] 面向真实仓库的 coding agent 工作流、评审和长期项目记忆。
