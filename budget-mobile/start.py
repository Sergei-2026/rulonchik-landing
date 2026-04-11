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

# ── Загрузить / сохранить данные ─────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── HTTP-обработчик ───────────────────────────────────────────────────
class Handler(http.server.SimpleHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # убрать лишние логи в консоль

    def handle_error(self, request, client_address):
        pass  # не падать при обрыве соединения (норма для мобильных браузеров)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/data":
            data = load_data()
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/data":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
                save_data(data)
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

print(f"OK  Local IP : {LOCAL_IP}")
print(f"OK  Phone URL: {APP_URL}")
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
