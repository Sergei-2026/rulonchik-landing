"""
Сервер личного бюджета с REST API.
Данные хранятся в data.json — общие для всех устройств в сети.

API:
  GET  /api/data        — вернуть все транзакции
  POST /api/data        — сохранить все транзакции (тело: JSON-массив)
"""
import http.server
import socketserver
import socket
import os
import json
import base64
import io
import webbrowser
import threading
import qrcode
import urllib.request
import urllib.error

# Многопоточный сервер — каждое соединение в отдельном потоке
class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True  # потоки завершаются вместе с сервером

PORT     = 3500
DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DIR, "data.json")

# ── Локальный IP ─────────────────────────────────────────────────────
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()
APP_URL  = f"http://{LOCAL_IP}:{PORT}"

# ── QR base64 ────────────────────────────────────────────────────────
def make_qr_b64(url):
    qr = qrcode.QRCode(version=3,
                       error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=8, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

QR_B64 = make_qr_b64(APP_URL)

# ── Обновить qr.html с актуальным IP и QR ────────────────────────────
QR_HTML = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Открыть на телефоне</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#F0F4F8;
         min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
    .card{{background:#fff;border-radius:16px;padding:36px 32px;max-width:400px;width:100%;
           text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.10)}}
    h1{{font-size:22px;color:#1F4E79;margin-bottom:6px}}
    .sub{{font-size:14px;color:#999;margin-bottom:24px}}
    img{{display:block;margin:0 auto 20px;border-radius:8px;border:6px solid #EFF6FF}}
    .url{{background:#EFF6FF;border:2px solid #BDD7EE;border-radius:10px;padding:12px 16px;
          font-size:20px;font-weight:700;color:#1F4E79;margin-bottom:12px;word-break:break-all}}
    .btn{{width:100%;padding:12px;border:none;border-radius:8px;font-size:15px;
          font-weight:600;cursor:pointer;margin-bottom:8px}}
    .blue{{background:#2E75B6;color:#fff}}
    .green{{background:#C6EFCE;color:#375623}}
    #msg{{color:#375623;font-size:13px;height:18px;margin-bottom:6px}}
    .steps{{background:#F0F7FF;border-radius:10px;padding:16px 18px;text-align:left;
            font-size:14px;line-height:1.9;color:#333;margin-top:8px}}
    .steps b{{color:#1F4E79}}
    .tag{{display:inline-block;background:#1F4E79;color:#fff;border-radius:4px;
          padding:1px 7px;font-size:12px;font-weight:700}}
  </style>
</head>
<body>
<div class="card">
  <h1>Открыть на телефоне</h1>
  <p class="sub">Наведите камеру телефона на QR-код</p>
  <img src="data:image/png;base64,{QR_B64}" width="220" height="220" alt="QR">
  <div class="url">{APP_URL}</div>
  <div id="msg"></div>
  <button class="btn blue" onclick="copyUrl()">Скопировать адрес</button>
  <button class="btn green" onclick="location='{APP_URL}'">Открыть приложение</button>
  <div class="steps">
    <b>Android Chrome:</b> меню <span class="tag">...</span> &rarr; Добавить на главный экран<br><br>
    <b>iPhone Safari:</b> кнопка <span class="tag">поделиться</span> &rarr; На экран Домой<br><br>
    Телефон должен быть в той же Wi-Fi сети.
  </div>
</div>
<script>
function copyUrl(){{
  navigator.clipboard.writeText('{APP_URL}')
    .then(()=>{{document.getElementById('msg').textContent='Скопировано!';
               setTimeout(()=>document.getElementById('msg').textContent='',2000)}});
}}
</script>
</body></html>"""

with open(os.path.join(DIR, "qr.html"), "w", encoding="utf-8") as f:
    f.write(QR_HTML)

# ── Конфиг (токен + Pages URL) ───────────────────────────────────────
CONFIG_FILE = os.path.join(DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ── GitHub Pages автопубликация ───────────────────────────────────────
def gh_api(token, method, path, body=None):
    url = "https://api.github.com" + path
    headers = {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "BudgetApp/1.0",
        "Accept": "application/vnd.github+json",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8")), e.code
    except Exception as e:
        return {"message": str(e)}, 500

def upload_to_repo(token, owner, repo, path, content_str):
    import base64
    existing, status = gh_api(token, "GET", f"/repos/{owner}/{repo}/contents/{path}")
    sha = existing.get("sha") if status == 200 else None
    b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    body = {"message": f"Update {path}", "content": b64}
    if sha:
        body["sha"] = sha
    _, st = gh_api(token, "PUT", f"/repos/{owner}/{repo}/contents/{path}", body)
    return st in (200, 201)

def publish_to_github_pages(token):
    import time as _t
    print(">>> Публикация на GitHub Pages...")
    user_data, status = gh_api(token, "GET", "/user")
    if status != 200:
        print(f"    Ошибка: {user_data.get('message', status)}")
        print("    (нужен токен с правом public_repo)")
        return None
    owner = user_data["login"]
    repo  = "budget-app"

    _, status = gh_api(token, "POST", "/user/repos", {
        "name": repo, "description": "Личный бюджет — мобильное приложение",
        "private": False, "auto_init": True,
    })
    if status not in (200, 201, 422):
        print(f"    Ошибка создания репозитория: {status}")
        return None
    _t.sleep(4)

    manifest = json.dumps({
        "name": "Личный бюджет", "short_name": "Бюджет",
        "start_url": "./", "display": "standalone",
        "background_color": "#F5F5F5", "theme_color": "#1F4E79",
    })
    upload_to_repo(token, owner, repo, "manifest.json", manifest)

    sw = ("const CACHE='budget-v5';\n"
          "const BASE=new URL('.',self.location).pathname.replace(/\\/$/,'');\n"
          "const SHELL=[BASE+'/index.html',BASE+'/manifest.json'];\n"
          "self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)));self.skipWaiting();});\n"
          "self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim();});\n"
          "self.addEventListener('fetch',e=>{const url=new URL(e.request.url);"
          "if(url.pathname.includes('/api/')||url.hostname==='api.github.com')return;"
          "e.respondWith(caches.match(e.request).then(cached=>{"
          "const net=fetch(e.request).then(res=>{if(res.ok)caches.open(CACHE).then(c=>c.put(e.request,res.clone()));return res;}).catch(()=>cached);"
          "return cached||net;}));});")
    upload_to_repo(token, owner, repo, "sw.js", sw)

    try:
        with open(os.path.join(DIR, "index.html"), "r", encoding="utf-8") as f:
            html = f.read()
        upload_to_repo(token, owner, repo, "index.html", html)
    except Exception as e:
        print(f"    Ошибка загрузки index.html: {e}")
        return None

    gh_api(token, "POST", f"/repos/{owner}/{repo}/pages",
           {"source": {"branch": "main", "path": "/"}})

    pages_url = f"https://{owner}.github.io/{repo}/"
    cfg = load_config()
    cfg["pages_url"]   = pages_url
    cfg["pages_owner"] = owner
    cfg["pages_repo"]  = repo
    cfg["gh_token"]    = token
    save_config(cfg)
    print(f"OK  GitHub Pages: {pages_url}")
    print(f"    Ссылка активируется через 1-2 минуты")
    return pages_url

# ── Загрузить / сохранить данные ─────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            # Поддержка старого формата (массив) и нового ({transactions, deleted, updatedAt})
            if isinstance(raw, list):
                return {"transactions": raw, "deleted": [], "updatedAt": 0}
            return raw
    return {"transactions": [], "deleted": [], "updatedAt": 0}

def save_data(payload):
    # Перед перезаписью — сохранить резервную копию (хранится 10 последних)
    if os.path.exists(DATA_FILE):
        import time, glob
        backup_dir = os.path.join(DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"data_{ts}.json")
        with open(DATA_FILE, "r", encoding="utf-8") as src, \
             open(backup_path, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        # Удалить старые бэкапы, оставить 10 свежих
        backups = sorted(glob.glob(os.path.join(backup_dir, "data_*.json")))
        for old in backups[:-10]:
            try: os.remove(old)
            except: pass
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

# ── Прокси к GitHub API (телефон → сервер → GitHub) ──────────────────
def github_proxy(method, path, token, body_str=None):
    url = "https://api.github.com" + path
    headers = {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "BudgetApp/1.0",
        "Accept": "application/vnd.github+json",
    }
    data = body_str.encode("utf-8") if body_str else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8"), resp.status
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8"), e.code
    except Exception as e:
        return json.dumps({"message": str(e)}), 500

# ── HTTP-обработчик ───────────────────────────────────────────────────
class Handler(http.server.SimpleHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def handle_error(self, request, client_address):
        pass

    def end_headers(self):
        # Запрет кеша для всех файлов — телефоны всегда загружают свежую версию
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/gist"):
            # Прокси GET к GitHub Gist API
            # Ожидает заголовок X-GH-Token и X-GH-Path
            token = self.headers.get("X-GH-Token", "")
            path  = self.headers.get("X-GH-Path", "")
            if not token or not path:
                self.send_response(400); self._cors(); self.end_headers()
                self.wfile.write(b'{"message":"missing headers"}'); return
            body, status = github_proxy("GET", path, token)
            b = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(b))
            self._cors(); self.end_headers(); self.wfile.write(b)
            return

        if self.path == "/api/config":
            cfg  = load_config()
            safe = {"pages_url": cfg.get("pages_url", "")}
            body = json.dumps(safe).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self._cors(); self.end_headers(); self.wfile.write(body)
            return

        if self.path.startswith("/api/data"):
            data = load_data()
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/gist"):
            # Прокси POST/PATCH к GitHub Gist API
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length).decode("utf-8")
            try:
                req   = json.loads(raw)
                token = req.get("token", "")
                path  = req.get("path", "")
                method= req.get("method", "POST")
                body  = json.dumps(req.get("body", {})) if req.get("body") else None
                if not token or not path:
                    raise ValueError("missing token or path")
                resp_body, status = github_proxy(method, path, token, body)
                b = resp_body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", len(b))
                self._cors(); self.end_headers(); self.wfile.write(b)
            except Exception as e:
                self.send_response(400); self._cors(); self.end_headers()
                self.wfile.write(json.dumps({"message": str(e)}).encode())
            return

        if self.path == "/api/autosetup":
            length = int(self.headers.get("Content-Length", 0))
            try:
                req   = json.loads(self.rfile.read(length).decode("utf-8"))
                token = req.get("token", "").strip()
                if not token:
                    raise ValueError("no token")
                # Запускаем публикацию в фоне — не блокируем телефон
                threading.Thread(
                    target=publish_to_github_pages, args=(token,), daemon=True
                ).start()
                self.send_response(200); self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true,"msg":"publishing in background"}')
            except Exception as e:
                self.send_response(400); self._cors(); self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "msg": str(e)}).encode())
            return

        if self.path == "/api/data":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
                # Принять как старый формат (массив), так и новый (объект)
                if isinstance(data, list):
                    payload = {"transactions": data, "deleted": [], "updatedAt": 0}
                else:
                    payload = data
                save_data(payload)
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.send_response(400)
                self._cors()
                self.end_headers()
                self.wfile.write(b'{"ok":false}')
        else:
            self.send_response(404)
            self.end_headers()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

# ── Запуск ────────────────────────────────────────────────────────────
os.chdir(DIR)

_cfg = load_config()
print(f"OK  Local IP : {LOCAL_IP}")
print(f"OK  Phone URL: {APP_URL}")
if _cfg.get("pages_url"):
    print(f"OK  Pages URL: {_cfg['pages_url']}")
    # Обновляем GitHub Pages при каждом запуске (актуальный index.html)
    if _cfg.get("gh_token"):
        threading.Thread(
            target=publish_to_github_pages, args=(_cfg["gh_token"],), daemon=True
        ).start()
print(f">>> Browser  : http://localhost:{PORT}/qr.html")
print(f"    Ctrl+C to stop\n")

def open_browser():
    import time; time.sleep(1)
    webbrowser.open(f"http://localhost:{PORT}/qr.html")

threading.Thread(target=open_browser, daemon=True).start()

ThreadingHTTPServer.allow_reuse_address = True

# Если порт занят — подождать и попробовать снова
import time as _time
for attempt in range(10):
    try:
        httpd = ThreadingHTTPServer(("", PORT), Handler)
        break
    except OSError:
        print(f"Port {PORT} busy, retrying ({attempt+1}/10)...")
        _time.sleep(2)
else:
    print(f"ERROR: cannot bind port {PORT}.")
    input("Press Enter to exit...")
    raise SystemExit(1)

print(f"Server running at {APP_URL}")
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("Server stopped.")
