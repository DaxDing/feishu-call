---
name: feishu-call
description: "读写飞书的默认入口：多维表格、电子表格、文档、Wiki、消息、日历、任务、邮件、云盘、通讯录、会议、妙记、OKR、审批考勤，底层调 feishu CLI（扫码登录一次，授权自动续期）。Use proactively when 用户发来飞书链接、要从飞书读数据、把数据写进飞书、发飞书消息、建日程或任务。Trigger on: 飞书, Feishu, Lark, 多维表格, bitable, 飞书表格, 飞书文档, 飞书 wiki, 发飞书消息, 飞书日历, 飞书任务, 读飞书, 写飞书, 同步到飞书。Does NOT trigger on: 抓外部公开网页（→ crawl-content）、yice 看板推送（→ yice 项目的 feishu-push）。"
allowed-tools: ["Bash", "Read"]
---

# 飞书

## 目标

用 `feishu` CLI 完成飞书上的读写，结果以命令返回的 JSON 为准；写操作做完再读回一次确认。

## 调用

`feishu` 是官方 `lark-cli` 的包装：凭证由包装层加载，其余命令原样透传，所以 lark-cli 的写法把 `lark-cli` 换成 `feishu` 就能用。

```bash
feishu --self-check --json          # 凭证、网络、bot 与 user 身份是否就绪
feishu auth ensure [DOMAIN]         # 跑 user 身份命令前调一次：有效秒退，待刷新自动续期，失效在后台自动授权
feishu {domain} +{action} …         # 快捷命令，如 feishu base +record-list、feishu sheets +csv-get
feishu api GET /open-apis/…         # 快捷命令覆盖不到时直调开放平台 API
```

- 某个域的完整用法：`feishu skills read lark-{域}` 读官方 skill（`lark-base`、`lark-sheets`、`lark-doc`、`lark-im`、`lark-calendar`…，`feishu skills list` 看全部；内容随 CLI 版本走），或 `feishu {domain} --help`。官方 skill 里的 `lark-cli` 换成 `feishu`。
- 身份用 `--as user` / `--as bot` 切换；输出默认 JSON，`--format` 可改，`--jq` 可直接过滤。
- 链接里取参数：

  ```
  多维表格  feishu.cn/base/{app_token}?table={table_id}&view={view_id}
  电子表格  feishu.cn/sheets/{spreadsheet_token}?sheet={sheet_id}
  文档      feishu.cn/docx/{document_id}
  Wiki      feishu.cn/wiki/{wiki_token}
  ```

  sheets 的快捷命令传 `--url`（表格或 wiki 链接都行），docs 传 `--doc`；base 不接链接，要拆出 token。命令名随 lark-cli 版本变，报 unknown subcommand 就看 `feishu {domain} --help`。

## 红线

- 不让用户手动登录：user 身份命令报授权错误（退出码 3、`99992x`）先跑 `feishu auth ensure`，成功后重试一次原命令。只有 `ensure` 明确提示要 `feishu auth bootstrap` 时，才请用户跑一次 bootstrap（会开一个专用浏览器，扫码登录飞书一次）。
- `--self-check` 报 lark-cli 未初始化：有应用凭证就 `feishu init`；没有就请用户扫码 `feishu init --new` 创建应用。命令会阻塞到扫码完成，放后台跑，把输出里的链接发给用户，扫码只能用户本人做。
- 删除、覆盖、真发邮件这类操作先 `--dry-run` 看请求体，并确认目标；删除类命令要显式 `--yes`，邮件默认只存草稿，不加 `--confirm-send`。
- 报权限不足时先分清是 scope 没开通还是 token 过期：scope 要去飞书开放平台后台申请，重新授权解决不了。
- 各域已踩过的坑（base 翻页、sheets 的 range、wiki 写权限、docs 的 v1 弃用等）见 [references/gotchas.md](./references/gotchas.md)，动手前扫一眼对应的段落。
