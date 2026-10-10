#!/usr/bin/env bash
# 完成检查：宣布「完成」之前一次跑完所有检查，输出汇总，作为完成证据。
#
# 检查项：测试、lint、类型检查、模块边界、密钥扫描、调试代码、改动范围。
# 自动识别 Node（package.json）、Python（pyproject.toml / requirements.txt / setup.cfg）、
# Go（go.mod）、Java（pom.xml / build.gradle）项目。
#
# 用法：
#   bash scripts/check_done.sh            # 在项目根目录运行
#   bash scripts/check_done.sh --quick    # 跳过测试，只做静态检查
#
# 自定义命令（环境变量，设置后覆盖自动识别；设为 skip 表示跳过该项）：
#   DONE_TEST_CMD      测试命令
#   DONE_LINT_CMD      lint 命令
#   DONE_TYPE_CMD      类型检查命令
#   DONE_BOUNDARY_CMD  模块边界检查命令
#   DONE_BASE_REF      对比改动范围的基准分支（默认 origin/main，没有就用 main）
#
# 退出码：0 = 全部通过；1 = 有检查失败。「跳过」不算失败，但会在汇总里列出。

set -u

QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 1

LOG_DIR="$(mktemp -d 2>/dev/null || echo /tmp/check_done_$$)"
mkdir -p "$LOG_DIR"

RESULTS=()   # 每项：状态|名称|说明
FAILED=0

has() { command -v "$1" >/dev/null 2>&1; }

record() { RESULTS+=("$1|$2|$3"); [ "$1" = "失败" ] && FAILED=1; }

# 运行一项检查：run_check 名称 命令
run_check() {
  local name="$1" cmd="$2" log="$LOG_DIR/$(echo "$1" | tr ' /' '__').log"
  if [ -z "$cmd" ]; then
    record "跳过" "$name" "没有识别到对应命令，可用环境变量指定"
    return
  fi
  if [ "$cmd" = "skip" ]; then
    record "跳过" "$name" "已通过环境变量设为跳过"
    return
  fi
  echo "▶ $name：$cmd"
  if bash -c "$cmd" >"$log" 2>&1; then
    record "通过" "$name" "$cmd"
  else
    record "失败" "$name" "$cmd（输出见下方）"
    echo "---- $name 输出（最后 40 行）----"
    tail -n 40 "$log"
    echo "--------------------------------"
  fi
}

# ---------- 识别项目类型 ----------

pkg_script() {  # package.json 里有没有这个 script
  [ -f package.json ] && grep -Eq "\"$1\"[[:space:]]*:" package.json
}

node_runner() {
  if [ -f pnpm-lock.yaml ]; then echo "pnpm"
  elif [ -f yarn.lock ]; then echo "yarn"
  else echo "npm run"; fi
}

is_python() { [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f setup.cfg ] || [ -f setup.py ]; }

detect_test() {
  local cmds=()
  if [ -f package.json ] && pkg_script test; then
    if [ "$(node_runner)" = "npm run" ]; then cmds+=("npm test --silent"); else cmds+=("$(node_runner) test"); fi
  fi
  if is_python && has pytest; then cmds+=("pytest -q"); elif is_python && has python3 && python3 -c "import pytest" 2>/dev/null; then cmds+=("python3 -m pytest -q"); fi
  [ -f go.mod ] && has go && cmds+=("go test ./...")
  [ -f pom.xml ] && { [ -x ./mvnw ] && cmds+=("./mvnw -q test") || { has mvn && cmds+=("mvn -q test"); }; }
  { [ -f build.gradle ] || [ -f build.gradle.kts ]; } && { [ -x ./gradlew ] && cmds+=("./gradlew test -q") || { has gradle && cmds+=("gradle test -q"); }; }
  local IFS="&"; echo "${cmds[*]}" | sed 's/&/ \&\& /g'
}

detect_lint() {
  local cmds=()
  [ -f package.json ] && pkg_script lint && cmds+=("$(node_runner) lint")
  if is_python; then
    if has ruff; then cmds+=("ruff check ." "ruff format --check .")
    elif has flake8; then cmds+=("flake8"); fi
  fi
  [ -f go.mod ] && has go && cmds+=("go vet ./...")
  local IFS="&"; echo "${cmds[*]}" | sed 's/&/ \&\& /g'
}

detect_type() {
  local cmds=()
  if [ -f package.json ]; then
    if pkg_script typecheck; then cmds+=("$(node_runner) typecheck")
    elif pkg_script type-check; then cmds+=("$(node_runner) type-check")
    elif [ -f tsconfig.json ]; then cmds+=("npx --no-install tsc --noEmit"); fi
  fi
  if is_python && has mypy && { [ -f mypy.ini ] || grep -q "\[tool.mypy\]" pyproject.toml 2>/dev/null; }; then
    cmds+=("mypy .")
  fi
  local IFS="&"; echo "${cmds[*]}" | sed 's/&/ \&\& /g'
}

detect_boundary() {
  local f py
  py="$(has python3 && echo python3 || echo python)"
  for f in tests/test_module_boundaries.py test/test_module_boundaries.py scripts/test_module_boundaries.py \
           backend/tests/test_module_boundaries.py; do
    [ -f "$f" ] && { echo "$py $f ."; return; }
  done
  f="$(git ls-files '*test_module_boundaries.py' 2>/dev/null | head -n 1)"
  [ -n "$f" ] && echo "$py $f ."
}

# ---------- 1–4：测试、lint、类型、边界 ----------

if [ $QUICK -eq 1 ]; then
  record "跳过" "测试" "使用了 --quick"
else
  run_check "测试" "${DONE_TEST_CMD-$(detect_test)}"
fi
run_check "lint" "${DONE_LINT_CMD-$(detect_lint)}"
run_check "类型检查" "${DONE_TYPE_CMD-$(detect_type)}"
run_check "模块边界" "${DONE_BOUNDARY_CMD-$(detect_boundary)}"

# ---------- 5–7：改动相关的检查 ----------

BASE_REF="${DONE_BASE_REF:-}"
if [ -z "$BASE_REF" ]; then
  if git rev-parse --verify -q origin/main >/dev/null; then BASE_REF="origin/main"
  elif git rev-parse --verify -q main >/dev/null; then BASE_REF="main"
  elif git rev-parse --verify -q origin/master >/dev/null; then BASE_REF="origin/master"
  elif git rev-parse --verify -q master >/dev/null; then BASE_REF="master"; fi
fi

CHANGED=""
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ -n "$BASE_REF" ] && [ "$(git rev-parse HEAD 2>/dev/null)" != "$(git rev-parse "$BASE_REF" 2>/dev/null)" ]; then
    MB="$(git merge-base HEAD "$BASE_REF" 2>/dev/null)"
    CHANGED="$( { git diff --name-only "$MB" 2>/dev/null; git ls-files --others --exclude-standard; } | sort -u)"
  else
    CHANGED="$( { git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard; } | sort -u)"
  fi
fi
EXISTING=""
while IFS= read -r f; do [ -n "$f" ] && [ -f "$f" ] && EXISTING="$EXISTING$f"$'\n'; done <<< "$CHANGED"

# 5. 密钥扫描
if has gitleaks; then
  run_check "密钥扫描" "gitleaks detect --no-banner --redact -v"
elif [ -n "$EXISTING" ]; then
  SECRET_RE='(AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[baprs]-[0-9A-Za-z-]{10,}|gh[pousr]_[0-9A-Za-z]{30,}|sk-[A-Za-z0-9_-]{20,}|(password|passwd|secret|api[_-]?key|access[_-]?token)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"'[:space:]]{8,}["'"'"'])'
  HITS="$(printf '%s' "$EXISTING" | grep -v -E '(^|/)(check_done\.sh|.*\.lock|package-lock\.json|pnpm-lock\.yaml)$' \
          | tr '\n' '\0' | xargs -0 grep -n -I -i -E "$SECRET_RE" 2>/dev/null | head -n 20)"
  ENVF="$(printf '%s' "$EXISTING" | grep -E '(^|/)\.env(\.[a-z]+)?$' | grep -v -E '\.env\.(example|sample|template)$')"
  if [ -n "$HITS$ENVF" ]; then
    record "失败" "密钥扫描" "改动的文件里疑似有密钥（输出见下方）"
    echo "---- 密钥扫描 ----"; [ -n "$ENVF" ] && echo "不应提交的 .env 文件：$ENVF"; echo "$HITS"; echo "------------------"
  else
    record "通过" "密钥扫描" "简易规则扫描改动文件（建议安装 gitleaks 获得完整扫描）"
  fi
else
  record "跳过" "密钥扫描" "没有改动的文件，且未安装 gitleaks"
fi

# 6. 调试代码
if [ -n "$EXISTING" ]; then
  CODE_FILES="$(printf '%s' "$EXISTING" | grep -E '\.(py|ts|tsx|js|jsx|mjs|vue|go|java|kt)$' \
                | grep -v -E '(^|/)(tests?|__tests__|scripts)/|\.(test|spec)\.|(^|/)test_[^/]*\.py$|_test\.(py|go)$')"
  if [ -n "$CODE_FILES" ]; then
    DEBUG_RE='(console\.log\(|debugger;|^[[:space:]]*print\(|breakpoint\(\)|pdb\.set_trace|fmt\.Println\(|System\.out\.println|\.only\()'
    DHITS="$(printf '%s' "$CODE_FILES" | tr '\n' '\0' | xargs -0 grep -n -E "$DEBUG_RE" 2>/dev/null | head -n 20)"
    if [ -n "$DHITS" ]; then
      record "失败" "调试代码" "改动的业务代码里有调试语句（输出见下方，确实需要的请改用日志）"
      echo "---- 调试代码 ----"; echo "$DHITS"; echo "------------------"
    else
      record "通过" "调试代码" "改动的业务代码里没有 console.log / print / debugger 等"
    fi
  else
    record "跳过" "调试代码" "改动里没有业务代码文件"
  fi
else
  record "跳过" "调试代码" "没有检测到改动"
fi

# 7. 改动范围（只列出，不判定，由人对照计划确认）
if [ -n "$CHANGED" ]; then
  N="$(printf '%s\n' "$CHANGED" | grep -c .)"
  record "请确认" "改动范围" "共 $N 个文件，对照计划确认没有越界改动（列表见下方）"
else
  record "跳过" "改动范围" "不是 git 仓库或没有改动"
fi

# ---------- 汇总 ----------

echo ""
echo "================ 完成检查汇总 ================"
printf '%s\n' "${RESULTS[@]}" | while IFS='|' read -r st name note; do
  case "$st" in
    通过) mark="✓" ;; 失败) mark="✗" ;; 跳过) mark="-" ;; *) mark="?" ;;
  esac
  printf '%s %-6s %-8s %s\n' "$mark" "$st" "$name" "$note"
done
if [ -n "$CHANGED" ]; then
  echo ""
  echo "改动文件${BASE_REF:+（相对 $BASE_REF）}："
  printf '%s\n' "$CHANGED" | sed 's/^/  /'
fi
echo "=============================================="
if [ $FAILED -ne 0 ]; then
  echo "结论：未通过。请修复失败项后重新运行，不要报告完成。"
  exit 1
fi
echo "结论：检查通过。「跳过」和「请确认」的项需要在完成汇报里说明。"
exit 0
