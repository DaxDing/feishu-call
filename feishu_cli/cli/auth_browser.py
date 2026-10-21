# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#   "playwright==1.49.0",
# ]
# ///
"""feishu auth 的浏览器自动授权：在专用 Chrome 登录目录里完成 lark-cli 设备授权，自动点确认。

由 bin/feishu 调用（feishu auth ensure / feishu auth bootstrap），不单独对外：
  auth_browser.py [--domain DOMAIN] [--bootstrap] [--timeout SECONDS]

--bootstrap 打开可见浏览器，等你在里面登录飞书（扫码一次），授权成功后标记登录目录可用；
不带 --bootstrap 时无界面运行，登录目录未标记可用或飞书登录态失效就以 3 退出，提示先 bootstrap。
成功时 stdout 输出一行 JSON；失败信息写 stderr，失败截图存 ~/.local/state/feishu/screenshots/。
环境变量 FEISHU_AUTH_PROFILE 可覆盖登录目录（默认 ~/.local/state/feishu/playwright-profile）。
退出码：0 成功 · 1 浏览器或网络失败 · 2 参数错 · 3 授权未就绪（需 bootstrap / 授权被拒 / 超时）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

STATE_ROOT = Path.home() / ".local" / "state" / "feishu"
PROFILE = Path(os.environ.get("FEISHU_AUTH_PROFILE") or STATE_ROOT / "playwright-profile").expanduser()
MARKER = PROFILE / ".feishu-auth-ready"
SCREENSHOTS = STATE_ROOT / "screenshots"
BUTTONS = ("确认授权", "同意授权", "允许授权", "授权", "确认", "允许", "继续",
           "Authorize", "Allow", "Confirm", "Continue")
SUCCESS = re.compile(r"授权成功|已完成授权|验证成功|登录成功|authorization\s+(?:is\s+)?(?:complete|successful)", re.I)
CONSENT = re.compile(r"设备授权|应用授权|请求授权|权限|authorize|authorization|allow this app", re.I)
LOGIN = re.compile(r"扫码登录|手机号登录|验证码|安全验证|登录飞书|scan.*(?:qr|code)|verification code", re.I)


class AuthError(RuntimeError):
    """授权未就绪，退出码 3。"""


def log(level: str, msg: str) -> None:
    print(f"[feishu {datetime.now():%H:%M:%S}] {level} {msg}", file=sys.stderr)


def lark_cli() -> str:
    path = shutil.which("lark-cli")
    if not path:
        raise AuthError("lark-cli 未安装（npm i -g @larksuite/cli）")
    return path


def start_device_flow(domain: str | None) -> tuple[str, str]:
    args = [lark_cli(), "auth", "login", "--no-wait", "--json"]
    args += ["--domain", domain] if domain else ["--recommend"]
    out = subprocess.run(args, capture_output=True, text=True, timeout=60)
    line = next((l for l in (out.stdout + "\n" + out.stderr).splitlines() if l.startswith("{")), "")
    if out.returncode != 0 or not line:
        raise AuthError("设备授权启动失败")
    data = json.loads(line)
    url = next((data[k] for k in ("verification_uri_complete", "verification_uri", "verification_url",
                                  "verificationUriComplete", "verificationUri", "verificationUrl") if data.get(k)), "")
    code = data.get("device_code") or data.get("deviceCode") or ""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "accounts.feishu.cn" or not code:
        raise AuthError("授权地址或 device_code 异常，已停止")
    return url, code


def feishu_page(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "feishu.cn" or host.endswith(".feishu.cn")


def click_consent(page) -> bool:
    if not CONSENT.search(page.locator("body").inner_text(timeout=5_000)):
        return False
    for name in BUTTONS:
        buttons = page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}$", re.I))
        for i in range(min(buttons.count(), 3)):
            try:
                if buttons.nth(i).is_visible(timeout=500) and buttons.nth(i).is_enabled(timeout=500):
                    buttons.nth(i).click(timeout=10_000)
                    return True
            except Exception:
                continue  # 按钮在授权完成瞬间被替换，交给外层循环看轮询结果
    return False


def finish(poller: subprocess.Popen, timeout: float) -> None:
    try:
        code = poller.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise AuthError("授权页已完成，但 lark-cli 没有落下 token") from exc
    if code != 0:
        out = (poller.stdout.read() if poller.stdout else "").strip()
        raise AuthError(out.splitlines()[-1] if out else "设备授权失败")


def authorize(url: str, device: str, bootstrap: bool, timeout: int) -> None:
    from playwright.sync_api import sync_playwright

    PROFILE.mkdir(parents=True, exist_ok=True)
    PROFILE.chmod(0o700)
    poller = subprocess.Popen([lark_cli(), "auth", "login", "--device-code", device],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    page = context = None
    clicks = 0
    deadline = time.monotonic() + timeout
    try:
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                str(PROFILE), channel="chrome", headless=not bootstrap, viewport={"width": 1280, "height": 900})
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            if bootstrap:
                log("info", "已打开专用浏览器：如需登录请在窗口里登录飞书，授权会自动确认")
            while time.monotonic() < deadline:
                if poller.poll() is not None or page.is_closed():
                    return finish(poller, 30)
                if not feishu_page(page.url):
                    raise AuthError(f"浏览器跳到了非飞书域名 {urlparse(page.url).hostname}")
                try:
                    body = page.locator("body").inner_text(timeout=5_000)
                except Exception:
                    body = ""
                if SUCCESS.search(body):
                    return finish(poller, 30)
                if click_consent(page):
                    clicks += 1
                    if clicks > 4:
                        raise AuthError("授权页连续出现超过 4 次确认，已停止")
                    page.wait_for_timeout(1_000)
                    continue
                if not bootstrap and LOGIN.search(body):
                    raise AuthError("专用浏览器的飞书登录态失效，运行 feishu auth bootstrap 重新登录一次")
                page.wait_for_timeout(500)
            raise AuthError("浏览器授权超时")
    except Exception as exc:
        if poller.poll() == 0:
            return
        if page is not None and not page.is_closed():
            SCREENSHOTS.mkdir(parents=True, exist_ok=True)
            shot = SCREENSHOTS / f"failed-{datetime.now():%Y%m%dT%H%M%S}.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
                shot.chmod(0o600)
                log("error", f"失败截图：{shot}")
            except Exception:
                pass
        raise
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if poller.poll() is None:
            poller.terminate()


def main() -> int:
    ap = argparse.ArgumentParser(prog="feishu auth", description=__doc__.split("\n\n")[0])
    ap.add_argument("--domain")
    ap.add_argument("--bootstrap", action="store_true")
    ap.add_argument("--timeout", type=int, default=0, help="默认 bootstrap 300 秒，自动授权 90 秒")
    args = ap.parse_args()
    timeout = args.timeout or (300 if args.bootstrap else 90)
    try:
        if not args.bootstrap and not MARKER.exists():
            raise AuthError("自动授权还没初始化，先运行一次 feishu auth bootstrap")
        url, device = start_device_flow(args.domain)
        log("info", f"{'bootstrap' if args.bootstrap else '后台自动授权'}：设备授权已发起")
        authorize(url, device, args.bootstrap, timeout)
        MARKER.touch()
        print(json.dumps({"ok": True, "mode": "bootstrap" if args.bootstrap else "auto",
                          "profile": str(PROFILE)}, ensure_ascii=False))
        return 0
    except AuthError as exc:
        log("error", str(exc))
        return 3
    except Exception as exc:  # 浏览器启动、网络等非授权类失败
        log("error", f"自动授权失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
