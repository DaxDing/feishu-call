#!/usr/bin/env bash
# 07 tools 共用：用 uv 运行带 PEP 723 依赖声明的 Python 脚本；依赖首次解析后走本地缓存。
# 入口脚本里：source ".../07 tools/lib/uvrun.sh"; uv_exec "$SCRIPT" "$@"（替换当前进程）
#            或 uv_run "$SCRIPT" "$@"（子进程，继续执行后续命令）
# launchd / cron 的 PATH 常常没有 uv，所以按常见安装位置兜底查找。

uv_find() {
    local c
    command -v uv 2>/dev/null && return 0
    for c in "$HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv /Library/Frameworks/Python.framework/Versions/*/bin/uv; do
        [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
    done
    return 1
}

_uv_or_die() {
    local uv
    uv="$(uv_find)" || { printf '[%s %s] error 缺 uv（brew install uv）\n' "$(basename "$1" .py)" "$(date +%H:%M:%S)" >&2; exit 3; }
    printf '%s' "$uv"
}

uv_exec() {
    local script="$1" uv; shift
    uv="$(_uv_or_die "$script")" || exit 3
    exec "$uv" run --quiet --script "$script" "$@"
}

uv_run() {
    local script="$1" uv; shift
    uv="$(_uv_or_die "$script")" || exit 3
    "$uv" run --quiet --script "$script" "$@"
}
