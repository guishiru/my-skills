"""模块边界测试：把「模块之间只能怎么依赖」变成会失败的测试。

检查 4 件事：
  1. 每个业务模块都在 ALLOWED 表里登记过。
  2. 模块只依赖 ALLOWED 表里允许的模块。
  3. 跨模块只用对方的公开入口（Python 的包本身 / __init__.py，前端的 index.ts），
     不直接引用对方的内部文件。
  4. 模块之间没有循环依赖。

支持 Python（.py）和前端（.ts .tsx .js .jsx .mjs .vue）的 import。

用法：
  - 复制到项目的 tests/ 目录，pytest 会自动收集 test_ 开头的函数；
  - 或直接运行：python test_module_boundaries.py [项目根目录]
接入时只需要改下面「配置」一节。
"""

from __future__ import annotations

import ast
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ============================================================================
# 配置：按项目实际修改
# ============================================================================

# 模块根目录：这个目录下的每个一级子目录就是一个业务模块。
#   path        相对项目根目录的路径
#   py_package  （Python）这个目录对应的包名，如 backend/app 对应 "app"；
#               目录本身就在 sys.path 上（模块直接 import order）时填 ""
#   aliases     （前端）路径别名，如 {"@/": "frontend/src/"}，值为相对项目根目录的路径
MODULE_ROOTS = [
    {"path": "src", "py_package": "", "aliases": {"@/": "src/"}},
    # {"path": "backend/app", "py_package": "app"},
    # {"path": "frontend/src", "aliases": {"@/": "frontend/src/"}},
]

# 依赖白名单：键是模块，值是它允许依赖的模块集合。
# 新增模块必须在这里登记；新增依赖方向必须改这张表，改表要有人评审。
ALLOWED: dict[str, set[str]] = {
    "order": {"user", "payment", "shared"},
    "payment": {"shared"},
    "user": {"shared"},
    "shared": set(),
}

# 公开模块：任何模块都可以依赖它，不用在每个模块的白名单里重复写。
# 公开模块本身仍然要在 ALLOWED 里登记，并受白名单约束。
SHARED_MODULES: set[str] = {"shared"}

# 除了包入口以外，还允许被其他模块直接引用的子模块名（如 "api"、"types"、"schemas"）。
# 留空表示只能通过包入口（__init__.py / index.ts）引用。
PUBLIC_SUBMODULES: set[str] = set()

# 模块根目录下不算业务模块的子目录（根目录下的单个文件如 main.py、App.tsx 不算模块，也不检查）。
IGNORE_NAMES: set[str] = {
    "__pycache__",
    "tests",
    "test",
    "__tests__",
    "node_modules",
    "migrations",
}

# 不扫描的文件：测试文件允许为了测试引用内部实现。
IGNORE_FILE_PATTERNS = [
    r"(^|/)tests?/",
    r"(^|/)__tests__/",
    r"\.test\.[jt]sx?$",
    r"\.spec\.[jt]sx?$",
    r"(^|/)test_[^/]*\.py$",
    r"_test\.py$",
    r"(^|/)conftest\.py$",
]

PY_EXT = {".py"}
JS_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue"}
JS_INDEX_NAMES = {"index"}

# ============================================================================
# 实现：一般不需要修改
# ============================================================================


@dataclass
class Root:
    path: Path
    rel: str
    py_package: str
    aliases: dict[str, Path]
    modules: set[str] = field(default_factory=set)


@dataclass
class Violation:
    kind: str
    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.file}:{self.line}  {self.message}"


def project_root() -> Path:
    env = os.environ.get("BOUNDARY_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    if len(sys.argv) > 1 and __name__ == "__main__" and Path(sys.argv[1]).is_dir():
        return Path(sys.argv[1]).resolve()
    # 默认：本文件在 tests/ 或 scripts/ 下，项目根目录是上一级
    here = Path(__file__).resolve().parent
    if here.name in {"tests", "test", "scripts"}:
        return here.parent
    return Path.cwd().resolve()


def load_roots(base: Path) -> list[Root]:
    roots = []
    for cfg in MODULE_ROOTS:
        p = (base / cfg["path"]).resolve()
        aliases = {k: (base / v).resolve() for k, v in cfg.get("aliases", {}).items()}
        r = Root(p, cfg["path"], cfg.get("py_package", ""), aliases)
        if p.is_dir():
            for child in p.iterdir():
                if (
                    child.is_dir()
                    and not child.name.startswith((".", "_"))
                    and child.name not in IGNORE_NAMES
                ):
                    r.modules.add(child.name)
        roots.append(r)
    return roots


def is_ignored_file(rel_path: str) -> bool:
    return any(re.search(p, rel_path) for p in IGNORE_FILE_PATTERNS)


def locate(path: Path, roots: list[Root]) -> tuple[Root, str, list[str]] | None:
    """返回 (所属根, 模块名, 模块内部的路径片段)；不在任何模块里返回 None。"""
    for r in roots:
        try:
            parts = path.resolve().relative_to(r.path).parts
        except ValueError:
            continue
        if parts and parts[0] in r.modules:
            return r, parts[0], list(parts[1:])
    return None


# ---------- 判断「是否走了公开入口」 ----------


def _strip_ext(parts: list[str]) -> list[str]:
    if not parts:
        return parts
    last = parts[-1]
    for ext in PY_EXT | JS_EXT:
        if last.endswith(ext):
            last = last[: -len(ext)]
            break
    return parts[:-1] + [last]


def is_public(inner: list[str]) -> bool:
    inner = [p for p in _strip_ext(inner) if p]
    if not inner:
        return True
    if inner == ["__init__"] or (len(inner) == 1 and inner[0] in JS_INDEX_NAMES):
        return True
    return len(inner) == 1 and inner[0] in PUBLIC_SUBMODULES


# ---------- Python ----------


def _submodule(r: Root, mod: str, name: str) -> bool:
    d = r.path / mod
    return (d / name).is_dir() or (d / f"{name}.py").is_file()


def py_targets(file: Path, root: Root, roots: list[Root]):
    """生成 (行号, 目标模块, 模块内部路径)。"""
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    except (SyntaxError, UnicodeDecodeError):
        return
    rel_dir = list(file.resolve().relative_to(root.path).parent.parts)
    py_roots = [(r, r.py_package.split(".") if r.py_package else []) for r in roots]

    def resolve_dotted(dotted: list[str]):
        for r, prefix in py_roots:
            if dotted[: len(prefix)] == prefix:
                rest = dotted[len(prefix) :]
                if rest and rest[0] in r.modules:
                    return r, rest[0], rest[1:]
        return None

    def expand(r: Root, mod: str, inner: list[str], names):
        # from order import service → service 可能是子模块，算作引用内部文件
        if inner:
            yield mod, inner
            return
        subs = [a.name for a in names if a.name != "*" and _submodule(r, mod, a.name)]
        if subs:
            for n in subs:
                yield mod, [n]
        else:
            yield mod, []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hit = resolve_dotted(alias.name.split("."))
                if hit:
                    yield node.lineno, hit[1], hit[2]
        elif isinstance(node, ast.ImportFrom):
            mod_parts = node.module.split(".") if node.module else []
            if node.level:  # 相对导入
                up = node.level - 1
                if up > len(rel_dir):
                    continue
                parts = rel_dir[: len(rel_dir) - up] + mod_parts
                if parts and parts[0] in root.modules:
                    for mod, inner in expand(root, parts[0], parts[1:], node.names):
                        yield node.lineno, mod, inner
                elif not parts:
                    for a in node.names:
                        if a.name in root.modules:
                            yield node.lineno, a.name, []
                continue
            hit = resolve_dotted(mod_parts)
            if hit:
                for mod, inner in expand(hit[0], hit[1], hit[2], node.names):
                    yield node.lineno, mod, inner
            else:
                # from app import order → 名字本身是模块
                for r, prefix in py_roots:
                    if mod_parts == prefix:
                        for a in node.names:
                            if a.name in r.modules:
                                yield node.lineno, a.name, []


# ---------- 前端 ----------

JS_IMPORT_RE = re.compile(
    r"""(?:import\s[^'"]*?from\s*|import\s*\(\s*|import\s+|export\s[^'"]*?from\s*|require\s*\(\s*)['"]([^'"]+)['"]""",
    re.DOTALL,
)


def js_targets(file: Path, root: Root, roots: list[Root]):
    try:
        text = file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    # 去掉注释，避免把注释里的示例当成依赖
    text_nc = re.sub(
        r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.DOTALL
    )
    text_nc = re.sub(r"(^|[^:])//[^\n]*", r"\1", text_nc)
    for m in JS_IMPORT_RE.finditer(text_nc):
        spec = m.group(1)
        line = text_nc.count("\n", 0, m.start()) + 1
        target: Path | None = None
        if spec.startswith("."):
            target = (file.parent / spec).resolve()
        else:
            for r in roots:
                for prefix, alias_path in r.aliases.items():
                    if spec.startswith(prefix):
                        target = (alias_path / spec[len(prefix) :]).resolve()
                        break
                if target:
                    break
        if target is None:
            continue  # 第三方包
        loc = locate(target, roots)
        if loc:
            _, mod, inner = loc
            yield line, mod, inner


# ---------- 主流程 ----------


def collect(base: Path | None = None):
    base = base or project_root()
    roots = load_roots(base)
    violations: list[Violation] = []
    edges: dict[str, set[str]] = {}
    all_modules: set[str] = set()

    for r in roots:
        all_modules |= r.modules
    for mod in sorted(all_modules):
        if mod not in ALLOWED:
            violations.append(
                Violation(
                    "未登记",
                    mod,
                    0,
                    f"模块 '{mod}' 没有登记在 ALLOWED 表里。新增模块请在 ALLOWED 里加一行，写明它可以依赖哪些模块。",
                )
            )

    for r in roots:
        if not r.path.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(r.path):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in {"node_modules", "__pycache__", ".git", "dist", "build"}
            ]
            for fn in filenames:
                f = Path(dirpath) / fn
                if f.suffix not in PY_EXT | JS_EXT:
                    continue
                rel = f.resolve().relative_to(base).as_posix()
                if is_ignored_file(rel):
                    continue
                loc = locate(f, roots)
                if not loc:
                    continue
                _, src_mod, _ = loc
                gen = (
                    py_targets(f, r, roots)
                    if f.suffix in PY_EXT
                    else js_targets(f, r, roots)
                )
                for line, dst_mod, inner in gen:
                    if dst_mod == src_mod:
                        continue
                    edges.setdefault(src_mod, set()).add(dst_mod)
                    allowed = ALLOWED.get(src_mod, set())
                    if dst_mod not in allowed and not (
                        dst_mod in SHARED_MODULES and src_mod not in SHARED_MODULES
                    ):
                        violations.append(
                            Violation(
                                "依赖越界",
                                rel,
                                line,
                                f"'{src_mod}' 不允许依赖 '{dst_mod}'。确实需要的话，在 ALLOWED['{src_mod}'] 里加上 '{dst_mod}' 并请人评审。",
                            )
                        )
                    if not is_public(inner):
                        violations.append(
                            Violation(
                                "绕过公开入口",
                                rel,
                                line,
                                f"直接引用了 '{dst_mod}' 的内部文件 '{'/'.join(inner)}'。请改为从 '{dst_mod}' 的公开入口导入，需要的东西先在入口里导出。",
                            )
                        )

    for cycle in find_cycles(edges):
        violations.append(
            Violation(
                "循环依赖",
                " → ".join(cycle),
                0,
                "模块之间形成了环。把共同依赖的部分下沉到更底层的模块，或者改用事件 / 回调解耦。",
            )
        )
    return violations, edges


def find_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    cycles, seen = [], set()
    state: dict[str, int] = {}
    stack: list[str] = []

    def dfs(n: str):
        state[n] = 1
        stack.append(n)
        for m in sorted(edges.get(n, ())):
            if state.get(m) == 1:
                cyc = stack[stack.index(m) :] + [m]
                key = frozenset(cyc)
                if key not in seen:
                    seen.add(key)
                    cycles.append(cyc)
            elif state.get(m) is None:
                dfs(m)
        stack.pop()
        state[n] = 2

    for n in sorted(edges):
        if state.get(n) is None:
            dfs(n)
    return cycles


# ---------- pytest 入口 ----------


def _check(kind: str):
    violations, _ = collect()
    hits = [v for v in violations if v.kind == kind]
    assert not hits, "\n" + "\n".join(str(v) for v in hits)


def test_all_modules_registered():
    _check("未登记")


def test_dependencies_follow_allowed_table():
    _check("依赖越界")


def test_only_public_entry_points_used():
    _check("绕过公开入口")


def test_no_circular_dependencies():
    _check("循环依赖")


# ---------- 命令行入口 ----------


def main() -> int:
    base = project_root()
    violations, edges = collect(base)
    print(f"项目根目录：{base}")
    print("模块依赖：")
    if edges:
        for src in sorted(edges):
            print(f"  {src} → {', '.join(sorted(edges[src]))}")
    else:
        print("  （没有发现跨模块依赖）")
    if not violations:
        print("✓ 模块边界检查通过")
        return 0
    print(f"✗ 发现 {len(violations)} 处问题：")
    for v in violations:
        print(f"  {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
