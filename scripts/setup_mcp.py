#!/usr/bin/env python3
"""MCP サーバ（scripts/mcp_server.py）用の venv を作り、クライアント設定の雛形を出す。

  python3 scripts/setup_mcp.py              .venv-mcp を作って mcp を入れ、設定例を表示
  python3 scripts/setup_mcp.py --print-only  venv には触らず設定例だけ表示

mcp SDK は Python 3.10 以降が要る。このスクリプト自体は 3.9 でも動き、3.10 以降の
python3.X を PATH から探して venv を作る（macOS 標準の 3.9 で venv を切って失敗するのを防ぐ）。
OpenCode / Codex の設定ファイルは個人のものなので書き換えない。貼り付ける内容を表示するだけ。
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import kb_paths as kb

VENV = kb.REPO / ".venv-mcp"
SERVER = kb.REPO / "scripts" / "mcp_server.py"
REQUIREMENT = "mcp>=2.0.0,<3"   # README「MCP サーバーとして使う」と揃えること
MIN_PY = (3, 10)


def py_version(exe: str) -> tuple:
    try:
        out = subprocess.run([exe, "-c", "import sys; print(*sys.version_info[:2])"],
                             capture_output=True, text=True, timeout=30).stdout.split()
        return tuple(int(x) for x in out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return ()


def find_python(explicit: str = None) -> str:
    """venv を作る Python を返す。3.10 以降が見つからなければ空文字。"""
    if explicit:
        return explicit if py_version(explicit) >= MIN_PY else ""
    if sys.version_info[:2] >= MIN_PY:
        return sys.executable
    for minor in range(14, MIN_PY[1] - 1, -1):
        exe = shutil.which(f"python3.{minor}")
        if exe and py_version(exe) >= MIN_PY:
            return exe
    return ""


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python3")


def setup(base: str) -> int:
    if venv_python().exists() and py_version(str(venv_python())) < MIN_PY:
        print(f"{VENV} は Python 3.10 未満で作られています。削除してから再実行してください。", file=sys.stderr)
        return 1
    if not venv_python().exists():
        print(f"venv を作成: {VENV}（{base}）")
        subprocess.run([base, "-m", "venv", str(VENV)], check=True)
    print(f"インストール: {REQUIREMENT}")
    subprocess.run([str(venv_python()), "-m", "pip", "install", "-q", "--disable-pip-version-check", REQUIREMENT], check=True)
    # 実際に読み込めるかで確かめる（mcp_server.py は v2系の MCPServer を前提にしている）
    r = subprocess.run([str(venv_python()), "-c", "from mcp.server import MCPServer"],
                       capture_output=True, text=True)
    if r.returncode:
        print(f"mcp の読み込みに失敗しました:\n{r.stderr.strip()}", file=sys.stderr)
        return 1
    print("OK: mcp を読み込めました")
    return 0


def print_config() -> None:
    py, server = str(venv_python()), str(SERVER)
    # KB を既定以外に置いているときだけ環境変数を足す。CLAUDE_PLUGIN_DATA は読まない（CLAUDE.md 参照）
    kb_dir = os.environ.get("F310_KB_DIR", "")
    env_json = f',\n      "environment": {{ "F310_KB_DIR": "{kb_dir}" }}' if kb_dir else ""
    env_toml = f'\n\n[mcp_servers.f310-kb.env]\nF310_KB_DIR = "{kb_dir}"' if kb_dir else ""
    print(f"""
== OpenCode（opencode.json の "mcp" に追加）==
"f310-kb": {{
      "type": "local",
      "command": ["{py}", "{server}"],
      "enabled": true{env_json}
    }}

== Codex CLI（~/.codex/config.toml に追加）==
[mcp_servers.f310-kb]
command = "{py}"
args = ["{server}"]{env_toml}
""")
    if not kb.is_built():
        print(f"※ 知識ベースが未構築です（{kb.kb_root()}）。先に python3 scripts/build.py を実行してください。")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python", help="venv を作る Python を明示する（3.10 以降）")
    ap.add_argument("--print-only", action="store_true", help="venv には触らず設定例だけ表示する")
    args = ap.parse_args()

    if not args.print_only:
        base = find_python(args.python)
        if not base:
            print("Python 3.10 以降が見つかりません（mcp SDK の要件）。\n"
                  "  macOS: brew install python@3.12 のあと再実行するか、--python で指定してください。",
                  file=sys.stderr)
            return 1
        rc = setup(base)
        if rc:
            return rc
    print_config()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
