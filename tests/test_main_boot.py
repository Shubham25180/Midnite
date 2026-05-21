import subprocess
import sys
import time
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent


def test_main_boots_and_serves():
    proc = subprocess.Popen(
        [sys.executable, "-m", "Skynet.main"],
        cwd=str(_PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(15)
        if proc.poll() is not None:
            out, err = proc.communicate()
            raise AssertionError(
                f"Server exited early (code {proc.returncode}):\n{err.decode(errors='replace')}"
            )
        req = urllib.request.Request("http://127.0.0.1:7799/api/status")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            import json
            body = json.loads(resp.read())
            assert "runtime_mode" in body
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
