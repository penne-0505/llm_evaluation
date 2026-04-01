"""ローカル配布向け launcher"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn

import server
from core.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def _pick_port(host: str, preferred_port: int = 8000) -> tuple[int, bool]:
    for port in (preferred_port, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
                candidate = sock.getsockname()[1]
            if candidate:
                return candidate, port != preferred_port
        except OSError:
            continue
    raise RuntimeError("ローカルで利用可能なポートが見つかりません")


def _wait_until_ready(url: str, timeout_seconds: float = 15.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                return response.status < 500
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.2)
    return False


def main(argv: list[str] | None = None) -> int:
    log_file = configure_logging()
    parser = argparse.ArgumentParser(
        description="Start the local LLM Benchmark app and open it in a browser."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    diagnostics = server.get_runtime_diagnostics()
    if diagnostics["issues"]:
        logger.error(
            "preflight failed issues=%s log_file=%s",
            diagnostics["issues"],
            log_file,
        )
        print("起動前チェックで問題が見つかりました。", file=sys.stderr)
        for issue in diagnostics["issues"]:
            print(f"- {issue}", file=sys.stderr)
        return 1

    port, port_changed = _pick_port(args.host, args.port if args.port > 0 else 8000)

    url = f"http://{args.host}:{port}/"
    logger.info("launcher starting url=%s log_file=%s", url, log_file)
    config = uvicorn.Config(
        server.app,
        host=args.host,
        port=port,
        log_level="info",
        access_log=False,
    )
    uvicorn_server = uvicorn.Server(config)

    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()

    if not _wait_until_ready(url):
        logger.error("launcher startup failed url=%s", url)
        print(
            "アプリの起動に失敗しました。画面内のログと resource 配置を確認してください。",
            file=sys.stderr,
        )
        uvicorn_server.should_exit = True
        thread.join(timeout=2.0)
        return 1

    if port_changed:
        logger.warning(
            "preferred port unavailable preferred=%s actual=%s",
            args.port,
            port,
        )
        print(
            f"ポート {args.port} は使用中だったため、空いていたポート {port} で起動します。",
            file=sys.stderr,
        )

    logger.info("launcher ready url=%s", url)
    print(f"Prism LLM Eval is running at {url}")
    print("終了するにはこのウィンドウで Ctrl+C を押してください。")

    if not args.no_browser:
        try:
            opened = webbrowser.open(url)
        except Exception as exc:
            logger.warning("browser auto-open failed url=%s error=%s", url, exc)
            print(
                f"ブラウザを自動で開けませんでした: {exc}. 手動で {url} を開いてください。",
                file=sys.stderr,
            )
        else:
            if not opened:
                logger.warning("browser auto-open returned false url=%s", url)
                print(
                    f"ブラウザを自動で開けませんでした。手動で {url} を開いてください。",
                    file=sys.stderr,
                )

    try:
        while thread.is_alive():
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        logger.info("launcher interrupted by user")
        print("\n終了しています...")
        uvicorn_server.should_exit = True
        thread.join(timeout=5.0)

    logger.info("launcher exited normally")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
