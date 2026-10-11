"""Run a temporary local preview; always stop it when verification ends."""
import subprocess
import sys
import time
from pathlib import Path
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
flags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0
log=(ROOT/'.local/frontend-preview-server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
try:
    for _ in range(50):
        if server.poll() is not None:raise RuntimeError('Temporary preview server failed to start')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1) as response:
                if response.status==200:break
        except Exception:time.sleep(.2)
    else:raise RuntimeError('Preview was not ready')
    result=subprocess.run([sys.executable,'scripts/check_browser.py','--skip-upload'],cwd=ROOT)
    if result.returncode:raise SystemExit(result.returncode)
finally:
    server.terminate()
    try:server.wait(timeout=10)
    except subprocess.TimeoutExpired:server.kill();server.wait()
    log.close()
    print('Temporary preview stopped.')
