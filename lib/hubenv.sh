#!/usr/bin/env bash
# 07 tools 共用凭证加载（bash 版，与 hubenv.py 同语义）。
# 顺序：已有环境变量 > hub（~/.local/etc/obsidian.env）> cwd 向上各级项目 .env（近的优先），全部 setdefault。
# 只解析 `[export] KEY=VALUE`，不执行 shell。agent、cron、launchd 不读 ~/.zshrc，所以 CLI 必须自己加载。
# 用法：source ".../07 tools/lib/hubenv.sh"; hubenv_load

_hubenv_file() {
    local file="$1" key val
    [[ -f "$file" ]] || return 0
    while IFS='=' read -r key val; do
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key#export }"
        key="${key//[[:space:]]/}"
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
        [[ -n "${!key:-}" ]] || export "$key=$val"
    done < "$file"
}

hubenv_load() {
    local dir="$PWD"
    _hubenv_file "$HOME/.local/etc/obsidian.env"
    # macOS 路径大小写不敏感（/Users/Dax 与 /Users/dax 同一目录），比较时忽略大小写
    while shopt -s nocasematch; [[ "$dir" == "$HOME"/* ]]; do
        shopt -u nocasematch
        [[ -f "$dir/.env" ]] && _hubenv_file "$dir/.env"
        dir="$(dirname "$dir")"
    done
    shopt -u nocasematch
}
