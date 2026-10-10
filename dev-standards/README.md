# dev-standards：团队开发规范 Skill

> 一句话：一个给 Claude 等 AI 编程工具用的 Agent Skill，把通用开发原则、前端规范、后端规范写成分级规则，并用脚本把关键规则变成 CI 里的硬性检查。
> 来源：参考 obra/superpowers、vercel-labs/agent-skills、addyosmani/web-quality-skills、affaan-m/everything-claude-code、supabase/agent-skills、trailofbits/skills、zalando/restful-api-guidelines、OWASP Cheat Sheet Series，合并改写，2026-10-10
> 相关：[Skill 主文件](SKILL.md)
> 更新于：2026-10-10

## 解决什么问题

AI 辅助写代码时常见几类问题：顺手改了无关文件、跳过测试、跨模块乱引用、没验证就说「完成了」。这个 skill 把团队规范写成 AI 能执行的规则，并且不只靠自觉：模块边界、完成标准、提交规范都有脚本在提交和 CI 时检查。

## 包含什么

| 部分 | 内容 | 文件 |
|---|---|---|
| 通用开发原则 | 7 步开发流程、契约先行、单任务开发、变更范围控制、按业务组织目录、模块边界、测试规则、Git 要点、完成标准（DoD）、调试方法、安全底线 | [SKILL.md](SKILL.md) |
| 前端规范 | 组件架构、状态管理、请求三态、性能指标（Core Web Vitals）、设计 token、可访问性、表单、安全、国际化、测试 | [references/frontend.md](references/frontend.md) |
| 后端规范 | 分层架构、数据库迁移与并发、错误处理、幂等与重试、鉴权、缓存、可观测性、配置与密钥、测试 | [references/backend.md](references/backend.md) |
| 接口契约 | 契约文件、URL 命名、字段约定、响应格式、统一错误码、版本与兼容 | [references/api-contract.md](references/api-contract.md) |
| Git 规范 | 分支、Conventional Commits、提交粒度、禁止提交的内容、危险操作、PR 模板、评审关注点 | [references/git.md](references/git.md) |
| 自动化强制 | 模块边界测试、完成检查脚本、pre-commit 配置、GitHub Actions 配置 | `scripts/`、`assets/` |

## 设计要点

- **规则分三级**：禁止、必须、建议。AI 对前两级严格执行，第三级可按情况取舍但要说明。
- **按需加载**：主文件只放所有任务都要守的规则；前端、后端、接口、Git 细则放在 `references/`，做对应任务时才读，节省上下文。
- **规则能被检查**：
  - `scripts/test_module_boundaries.py`：检查模块是否登记、依赖方向是否在 `ALLOWED` 白名单内、是否绕过公开入口、有没有循环依赖。支持 Python 和 TS/JS/Vue。
  - `scripts/check_done.sh`：一次跑完测试、lint、类型检查、边界检查、密钥扫描、调试代码扫描，列出改动范围，输出汇总作为完成证据。自动识别 Node、Python、Go、Java 项目。
- **完成要有证据**：没跑检查不能说完成，检查失败不能报成功。

## 安装

**Claude 桌面 App / claude.ai**：把整个 `dev-standards` 文件夹打包成 zip，在 Claude 设置里的 Skills 页面上传。

**Claude Code**：

```bash
# 个人级（所有项目可用）
cp -r dev-standards ~/.claude/skills/
# 项目级（只对当前项目生效，可提交到仓库与团队共享）
cp -r dev-standards .claude/skills/
```

## 接入一个项目

```bash
cp dev-standards/scripts/test_module_boundaries.py  你的项目/tests/
cp dev-standards/scripts/check_done.sh               你的项目/scripts/
cp dev-standards/assets/pre-commit-config.yaml       你的项目/.pre-commit-config.yaml
mkdir -p 你的项目/.github/workflows
cp dev-standards/assets/github-ci.yml                你的项目/.github/workflows/check.yml
```

然后：

1. 打开 `tests/test_module_boundaries.py`，按项目修改 `MODULE_ROOTS`（模块所在目录）和 `ALLOWED` 表。
2. 在项目根目录运行 `bash scripts/check_done.sh`，确认能跑通。
3. 执行 `pre-commit install && pre-commit install --hook-type commit-msg`。
4. 在 GitHub 仓库设置里把「完成检查」设为合并 PR 的必要条件。
5. 在 `references/frontend.md` 和 `references/backend.md` 的「技术栈约定」表里填上团队选型。

## 目录结构

```
dev-standards/
├── SKILL.md                     # 通用原则 + 流程 + DoD
├── references/
│   ├── frontend.md              # 前端规范
│   ├── backend.md               # 后端规范
│   ├── git.md                   # Git 细则与 PR 模板
│   └── api-contract.md          # 契约与错误码规范
├── scripts/
│   ├── test_module_boundaries.py
│   └── check_done.sh
└── assets/
    ├── pre-commit-config.yaml
    └── github-ci.yml
```
