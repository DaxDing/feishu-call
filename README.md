# feishu-call

让 AI（Claude Code / Codex）用你的身份读写飞书：多维表格、电子表格、文档、Wiki、消息、日历、任务、邮件、云盘、通讯录、妙记、审批等。

底层是飞书官方的 [`lark-cli`](https://www.npmjs.com/package/@larksuite/cli)。本仓库在外面包了一层 `feishu` 命令，补上两件事：**扫码登录一次，之后授权自动续期**；删除单个 Wiki 节点。另附一个 Agent Skill（[`feishu-call/SKILL.md`](feishu-call/SKILL.md)），AI 会按它选命令、先预览再写、写完读回确认。

## 准备

- **系统**：macOS（其他系统没验证过）。
- **先装好**：[Homebrew](https://brew.sh) 和 git（`brew install git`）。其余依赖由安装脚本检查，缺了会给出安装命令。
- **其余依赖**：Node.js、jq、uv、Google Chrome，以及飞书官方的 `lark-cli`（`npm i -g @larksuite/cli`）。Chrome 用来扫码登录和自动续期，必须是正式版 Google Chrome。
- **飞书账号**：只支持国内版飞书（feishu.cn），不支持海外版 Lark。安装时会用这个账号创建一个**只属于你自己的飞书应用**，不需要别人的 App Secret；已有应用也可以直接选它。公司如果不允许员工自己建应用，找管理员开通，或者请管理员给你一个现成应用的 App ID / App Secret。
- **网络**：能访问 `open.feishu.cn`、`accounts.feishu.cn`、GitHub 和 npm。

## 安装：一句话交给 AI

把下面这句发给你的 AI（Claude Code 或 Codex）：

```text
请安装飞书 skill：按 https://github.com/DaxDing/feishu-call 的 README「AI 安装步骤」操作
```

中途 AI 会请你**扫两次码**：第一次创建你的飞书应用，第二次登录。之后直接对 AI 说「读一下这个多维表格 <链接>」就行，不用再登录。更多说法见 [examples/prompts.md](examples/prompts.md)。

### AI 安装步骤

写给 AI：按顺序执行，任何一步失败就停下，把原因告诉用户。扫码只能用户本人做，你负责把链接或窗口交给用户，然后等。

1. 克隆到固定目录（安装是软链，删了这个目录就失效）：

   ```bash
   git clone https://github.com/DaxDing/feishu-call.git ~/.local/share/feishu-call
   ```

   目录已存在就改为 `git -C ~/.local/share/feishu-call pull`。

2. 运行安装脚本：

   ```bash
   ~/.local/share/feishu-call/install.sh
   ```

   - 退出码 3：缺依赖。按输出里的命令装好（`brew install …`、`npm i -g @larksuite/cli`），再重跑。
   - 退出码 1：目标位置已有别的文件或软链。把输出给用户看，问清楚怎么处理，不要自己删。
   - 提示 `~/.local/bin` 不在 PATH：按提示加到 shell 启动文件；本次会话里用 `~/.local/bin/feishu` 的完整路径继续。

3. 看是否已经有应用：

   ```bash
   feishu --self-check --json
   ```

   `checks.credentials.ok` 为 `true` 就跳到第 5 步，否则做第 4 步。

4. 创建应用（第一次扫码）：

   - 用户给了现成应用的 App ID / App Secret：把它们作为环境变量传给 `feishu init`，不要打印、不要写进任何仓库或聊天记录：

     ```bash
     LARK_APP_ID='<App ID>' LARK_APP_SECRET='<App Secret>' feishu init
     ```

   - 否则让用户扫码创建。这个命令会一直等到扫码完成，所以放后台跑：

     ```bash
     feishu init --new > "${TMPDIR:-/tmp}/feishu-init.log" 2>&1 &
     ```

     几秒后从日志里取出 `https://open.feishu.cn/page/cli?…` 这条链接发给用户，请用户用电脑浏览器打开：没登录飞书的话先用飞书 App 扫码登录，然后在「创建飞书 CLI 应用」页面点「创建」；已经有应用的点「选择已有应用」。等这个后台命令自己退出、退出码为 0，再继续。

5. 登录（第二次扫码）：

   ```bash
   feishu auth bootstrap
   ```

   它会打开一个专用的 Chrome 窗口，请用户在窗口里用飞书 App 扫码登录；之后的授权确认会自动点掉，最多等 5 分钟。

6. 验证：

   ```bash
   feishu --self-check --json
   feishu contact +get-user --as user
   ```

   第一条返回 `"ok":true`，第二条能看到用户本人的名字，就装好了。告诉用户：以后不用再登录。

### 手动安装

不用 AI 的话，在终端里按上面第 1–6 步执行。`feishu init --new` 不用放后台：终端里会显示二维码和链接，用飞书 App 扫码或在电脑浏览器打开链接，再点「创建」或「选择已有应用」。

## 登录怎么一直保持

- **只扫两次码**：`feishu init --new` 创建应用、`feishu auth bootstrap` 登录，都只做一次。
- **自动续期**：AI 每次用你的身份前先跑 `feishu auth ensure`。token 有效就直接用；快过期就续期；失效了就在后台用那个专用 Chrome 重新授权并自动确认，不弹窗、不打扰你。
- **7 天内用过就不会掉**：授权按 7 天滚动，期间有过一次调用就一直有效。
- **什么时候要再扫码**：只有专用 Chrome 里的飞书网页登录也失效了（很久没用、改了密码、被踢下线），`ensure` 才会提示重新跑 `feishu auth bootstrap`。
- **存在哪**：应用凭证和 token 由 `lark-cli` 存在你本机；专用 Chrome 的登录目录在 `~/.local/state/feishu/`。不会上传到任何地方。

## 常用命令

```bash
feishu --self-check --json                               # 应用、网络、登录状态
feishu auth ensure                                       # 用你的身份调用前跑一次
feishu contact +get-user --as user                       # 我是谁
feishu base +record-list --base-token <app_token> --table-id <table_id> --format json
feishu im +messages-send --chat-id <oc_xxx> --text '你好'  # 以应用机器人身份发群消息
feishu api GET /open-apis/calendar/v4/calendars          # 快捷命令没覆盖的接口直接调
```

其余命令和官方 `lark-cli` 完全一样，把 `lark-cli` 换成 `feishu` 即可：`feishu --help-cli` 看全部命令，`feishu skills list` 看官方各模块的用法说明。各模块踩过的坑见 [feishu-call/references/gotchas.md](feishu-call/references/gotchas.md)。

## 安全

- 本仓库不含任何凭证。你的应用凭证和登录 token 只在你自己电脑上。
- AI 以你的身份操作，能做的事等于你在飞书里的权限。删除、覆盖、真发邮件之前，skill 会先预览请求并让你确认；邮件默认只存草稿。
- 不要把 App Secret 发进聊天，也不要提交进 Git。怀疑泄露就去 [飞书开放平台](https://open.feishu.cn/app) 重置。

## 常见问题

- **提示权限不足 / scope 没开通**：这不是登录过期。到 [飞书开放平台](https://open.feishu.cn/app) 找到你的应用，在「权限管理」里开通对应权限并发布新版本，再跑一次 `feishu auth bootstrap` 重新授权。
- **公司不让建应用**：请管理员给你一个现成应用的 App ID / App Secret，用 `feishu init` 代替 `feishu init --new`；或者在创建页面点「选择已有应用」。
- **用的是海外版 Lark**：暂不支持，扫码登录只认 feishu.cn。
- **自动授权失败**：失败时的截图在 `~/.local/state/feishu/screenshots/`；照提示重跑 `feishu auth bootstrap` 即可。
- **更新**：`git -C ~/.local/share/feishu-call pull`。
- **卸载**：删掉 `~/.local/bin/feishu`、`~/.claude/skills/feishu-call`、`~/.codex/skills/feishu-call` 这几个软链和 `~/.local/share/feishu-call`；登录状态在 `~/.local/state/feishu/`。

## 目录

| 路径 | 内容 |
|---|---|
| `feishu-call/` | Agent Skill：`SKILL.md` 和踩坑笔记 |
| `feishu_cli/` | `feishu` 命令：`bin/feishu` 入口，`cli/auth_browser.py` 负责扫码登录和自动授权 |
| `lib/` | 命令用到的凭证加载、uv 运行脚本 |
| `install.sh` | 安装脚本，只建软链、检查依赖 |
| `examples/prompts.md` | 可以直接对 AI 说的话 |

## License

[MIT](LICENSE)
