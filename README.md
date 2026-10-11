# my-skills

个人整理的 Claude Skills 合集。

## Skills 列表

| Skill | 用途 |
| --- | --- |
| [ai-engineering-guide](./ai-engineering-guide/) | AI 应用工程顾问：技术方案选型、提示词编写与改写、上下文工程、知识库/RAG、Agent 循环与工具设计、多 Agent、多模态、记忆、评测、安全与成本 |
| [code-topic-study-v2](./code-topic-study-v2/) | 主题式源码研读：单项目或 2–3 个项目对比，先广度定位再深挖关键机制，产出学习文章或可并入 skill 的规则 |
| [chart-talk](./chart-talk/) | 用图表说话：先定结论、判比较类型、再选图和配色，产出 Excel 原生图表、网页看板或静态图片；也能复核别人的图表 |
| [critical-reading](./critical-reading/) | 审读别人给的材料，判断论证能否站住、能否作为决策依据；也用于核查说法和数据、草稿发出前的预演追问 |
| [doc-to-ai-readable](./doc-to-ai-readable/) | 把写给人看的汇报、方案、纪要、制度等文档整理成 AI 可读格式（Agent 上下文或知识库） |
| [data-analysis-advisor](./data-analysis-advisor/) | 数据分析顾问：判断分析方法、指标和所需数据，能直接读数据跑分析、审查别人的分析，或在没有数据时估算 |
| [ops-strategy](./ops-strategy/) | 运营策略顾问：依据审定的运营策略库（供给、增长、补贴、定价、流量、销售运营、内容社区）出方案、诊断指标、审查方案 |
| [structured-writing](./structured-writing/) | 中文职场文档的起草、审阅与重构：金字塔原理、SCQA、MECE、结论先行，含结构反模式诊断和数据自洽检查 |
| [dev-standards](./dev-standards/) | 团队开发规范：契约先行、单任务开发、模块边界、测试、Git、完成标准，含前后端细则，附模块边界测试和完成检查脚本 |
| [prd-drafting](./prd-drafting/) | 把业务方模糊的口头表述转成研发能直接接的 PRD：先把「方案」还原成「需求」，再补齐边界、异常态、验收标准与数据口径 |

## 使用方式

每个文件夹是一个独立的 skill，结构为 `skill名/SKILL.md`（部分带 `references/`、`scripts/`、`assets/`）。把文件夹打包成 zip，就可以在 Claude 的 Skills 设置里上传使用。
