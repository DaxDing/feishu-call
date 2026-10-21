#!/usr/bin/env bash
# feishu-call 安装：把 feishu 命令挂到 ~/.local/bin，把 skill 挂到 Claude Code / Codex 的 skills 目录。
# 只建软链、检查依赖，不装依赖、不登录；重复运行安全。更新代码用 git pull，软链不用重建。
# 用法: ./install.sh
# 退出码: 0 完成 · 1 目标位置已有别的文件 · 3 缺依赖（已列出安装命令，装好后重跑）
set -euo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"

log() { printf '[feishu-call] %s\n' "$*" >&2; }

missing=0
need() {  # need 命令 安装方式
    command -v "$1" >/dev/null 2>&1 && return 0
    log "缺 $1：$2"
    missing=1
}

link() {  # link 源 目标
    local src="$1" dst="$2"
    if [[ -L "$dst" ]]; then
        [[ "$(readlink "$dst")" == "$src" ]] && { log "已链接 $dst"; return 0; }
        log "$dst 已是指向 $(readlink "$dst") 的软链：确认不再需要后移走它，再重跑"
        return 1
    fi
    if [[ -e "$dst" ]]; then
        log "$dst 已存在：确认不再需要后移走它，再重跑"
        return 1
    fi
    mkdir -p "$(dirname "$dst")"
    ln -s "$src" "$dst"
    log "已链接 $dst → $src"
}

need node "brew install node"
need jq "brew install jq"
need uv "brew install uv"
need lark-cli "npm i -g @larksuite/cli"
if [[ "$(uname -s)" == Darwin && ! -d "/Applications/Google Chrome.app" && ! -d "$HOME/Applications/Google Chrome.app" ]]; then
    log "缺 Google Chrome：扫码登录和自动续期要用它（https://www.google.com/chrome/）"
    missing=1
fi

chmod +x "$ROOT/feishu_cli/bin/feishu"
link "$ROOT/feishu_cli/bin/feishu" "$BIN_DIR/feishu"
skills=0
for home in "$HOME/.claude" "$HOME/.codex"; do
    [[ -d "$home" ]] || continue
    link "$ROOT/feishu-call" "$home/skills/feishu-call"
    skills=1
done
[[ "$skills" == 1 ]] || log "没找到 ~/.claude 或 ~/.codex：只装了 feishu 命令，装好 Claude Code / Codex 后重跑即可挂上 skill"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) log "$BIN_DIR 不在 PATH：在 shell 启动文件（zsh 是 ~/.zshrc）末尾加一行 export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

if [[ "$missing" == 1 ]]; then
    log "依赖没装全：按上面的命令装好后重跑 ./install.sh"
    exit 3
fi
log "安装完成。下一步：feishu init --new（扫码创建应用）→ feishu auth bootstrap（扫码登录）→ feishu --self-check"
