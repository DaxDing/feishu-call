# 飞书踩坑

按域分段，只记官方文档里不显眼、实际踩过的。

## 认证

- 权限不足先看 `feishu auth scopes`：scope 不在列表里就要去开放平台后台申请并发布，这和 token 过期不是一回事，重新授权解决不了。妙记默认没开 `minutes:minutes:readonly`，调用会 403。
- `feishu init` 切换应用后要重跑 `feishu auth ensure`，否则 user token 还属于旧应用。
- 不要把 `auth ensure` 放后台跑：父 shell 一退出，轮询子进程会被一起带走，token 续不上。要异步授权时分两步：
  1. `lark-cli auth login --no-wait --json --recommend`，拿到 verification URL 和 device_code；
  2. `nohup lark-cli auth login --device-code {code} > /tmp/feishu-poll.log 2>&1 & disown`，起一个独立的轮询进程；
  3. 另外 `open {url}` 打开浏览器授权，完成后用 `lark-cli auth status` 确认。

## 多维表格

- `--table-id` 可以传 ID（`tbl_xxx`），也可以传表名。
- `+record-upsert` 带 `--record-id` 就更新，不带就创建。超过 10 条用 `+record-batch-create` / `+record-batch-update`，逐条写容易触发限流。
- `+record-delete` 不加 `--yes` 不执行。
- `+record-list` 默认输出 markdown，要 JSON 加 `--format json`；`--field-id` 可以只取需要的列。
- base 不接 `--url`：要从链接拆出 `--base-token` `--table-id` `--view-id`。
- base 翻页不支持 `--page-all`，会报 unknown flag：用 `--limit 200`（上限 200）加 `--offset N` 循环，用 `.data.has_more` 判断是否结束。

## 电子表格

- 旧的 `+read` / `+write` / `+append` / `+find` 已从 lark-cli 删除（报 unknown subcommand）。读用 `+cells-get`（值、公式、样式）或 `+csv-get`（读成 CSV，`--range` 可省，省了读整页）；写用 `+cells-set` / `+csv-put`；查找用 `+cells-search`；样式用 `+cells-set-style` / `+cells-batch-set-style`。命令名随版本变，以 `feishu sheets --help` 为准。
- 选页必须传 `--sheet-id`（链接里 `sheet=` 的值）或 `--sheet-name`，二选一；`--range` 只写 `A1:D10`，不带 sheet 前缀。
- `--url` 可以传表格链接，也可以直接传 wiki 链接，不用先查 `obj_token`。
- 要公式而不是计算结果：`+cells-get --include formula`。
- 大表加 `--output-path ./out.json` 落盘，看回执里的 `complete` 判断是否读全，不要只看 stdout。

## 消息

- `+messages-send` 默认 bot 身份（应用要开机器人能力），`+messages-search` 默认 user 身份。
- `--markdown` 会自动包成富文本、解析图片 URL；`--content` 直接传原始 JSON。
- 高频发送加 `--idempotency-key`：同一个 key 24 小时内只发一次。

## Wiki

- 先 `wiki spaces get_node` 拿到 `obj_type`，再按类型调 docs / sheets / base 的命令。它是 resource action 形态，不是 `+xxx` 快捷命令。
- 写 wiki 里的文档要文档级协作者权限：bot 就算有写 scope 也会报 1770032 forbidden。改用 `--as user`（文档 owner），或在后台把应用加为 wiki 空间协作者。
- 删单个节点用 `feishu wiki delete-node {url|token} --yes`，这是包装层补的命令，异步生效，返回 task_id 就算成功。`wiki +delete-space` 会删掉整个空间，不要用来删节点。
- 自己调原始删除 API 时有三个坑：路径末段用 `obj_token` 而不是 `node_token`（用错报 131005）；`obj_type` 放请求体而不是 query（放错报 99992402）；schema 里查不到这个端点。

## 文档

- 文档用 `--doc` 传链接或 token（不是 `--url`）。`+fetch --scope outline` 先看目录，再按 `section` / `keyword` 读局部，长文不用整篇拉。
- `+update --command` 选操作：局部改用 `str_replace`（配 `--pattern`）或 `block_*`（先 `+fetch --detail with-ids` 拿 block id）；`append` 追加到末尾；`overwrite` 整篇替换，会丢掉无关的富文本，只在确实要整篇重写时用。
- `--content` 默认是 DocxXML；直接写 Markdown 加 `--doc-format markdown`。

## 通讯录

- `+get-user` 查自己必须 `--as user`，bot 身份会报错；查指定用户传 `--user-id` 即可。
- `+search-user` 只有 user 身份能用。

## 邮件

- `+send` / `+reply` / `+forward` 默认只存草稿，加 `--confirm-send` 才真发。自动化场景默认不加，留给人确认。

## 通用

- 快捷命令带 `+` 前缀（`+record-list`、`+csv-get`）。漏了 `+` 会打出 lark-cli 的帮助列表，看着像「没装这个域」，其实只是命令写错了。
- 不确定参数时加 `--dry-run` 看实际请求体。
- `--page-all` 只有部分 sheets / im / wiki 命令支持，其余手动 `--limit` + `--offset` 循环，可加 `--page-delay 500` 降低频率。
