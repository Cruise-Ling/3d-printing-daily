# -*- coding: utf-8 -*-
"""链接批量导出 · 本地服务（127.0.0.1:8765）

为什么需要它
------------
专栏页托管在 GitHub Pages（https 静态页），没有后端：
· YouTube API key 不能写进页面源码；
· 翻译端点 translate.googleapis.com 不返回 CORS 头，浏览器直连必被拦；
· xlsx 要零依赖生成，也不能把库塞进页面。
所以抓取与翻译必须落在本机进程，页面只负责收集参数和下载。

浏览器侧的两个硬要求
------------------
1) https 页面请求 http://127.0.0.1 属于 Private Network Access，
   Chrome 会先发 OPTIONS 预检，服务端必须回 Access-Control-Allow-Private-Network: true；
2) 回显 Origin（不能用 *），否则 PNA 预检不通过。

安全边界
--------
只绑定 127.0.0.1；校验 Origin 必须是 *.github.io / 127.0.0.1 / localhost / file://(null)；
不接收任意路径，下载只认 job 里登记的文件。
"""
import datetime
import io
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _link_export_core as CORE

PORT = 8765
EXPORT_DIR = os.path.join(HERE, "_exports")
JOBS = {}
LOCK = threading.Lock()
VERSION = "1.0"


def _origin_ok(origin):
    if not origin or origin == "null":
        return True
    try:
        host = urllib.parse.urlparse(origin).hostname or ""
    except Exception:
        return False
    return host.endswith("github.io") or host in ("127.0.0.1", "localhost")


def _job_view(j):
    return {"id": j["id"], "status": j["status"], "logs": j["logs"][-12:],
            "file": os.path.basename(j["file"]) if j["file"] else "",
            "size": j["size"], "error": j["error"],
            "elapsed": int(time.time() - j["started"])}


def _worker(job_id, payload):
    j = JOBS[job_id]

    def log(msg):
        with LOCK:
            j["logs"].append({"t": time.strftime("%H:%M:%S"), "m": str(msg)})
            if len(j["logs"]) > 300:
                j["logs"] = j["logs"][-300:]

    try:
        path = CORE.run(payload["text"], payload["format"], payload["maxComments"],
                        payload["translate"], payload["replies"], None, log)
        with LOCK:
            j["status"] = "done"
            j["file"] = path
            j["size"] = os.path.getsize(path)
    except Exception as e:
        with LOCK:
            j["status"] = "error"
            j["error"] = str(e)
            j["logs"].append({"t": time.strftime("%H:%M:%S"), "m": "失败：" + str(e)})


class Handler(BaseHTTPRequestHandler):
    server_version = "LinkExport/" + VERSION

    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        o = self.headers.get("Origin")
        if o:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "86400")

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if not _origin_ok(self.headers.get("Origin")):
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        o = self.headers.get("Origin")
        if not _origin_ok(o):
            self._json({"error": "origin not allowed"}, 403)
            return

        if p.path == "/api/ping":
            self._json({"ok": 1, "version": VERSION, "port": PORT,
                        "exportDir": EXPORT_DIR})
            return

        if p.path == "/api/job":
            jid = (q.get("id") or [""])[0]
            j = JOBS.get(jid)
            if not j:
                self._json({"error": "job not found"}, 404)
                return
            self._json(_job_view(j))
            return

        if p.path == "/api/download":
            jid = (q.get("id") or [""])[0]
            j = JOBS.get(jid)
            if not j or j["status"] != "done" or not j["file"]:
                self._json({"error": "file not ready"}, 404)
                return
            if not os.path.exists(j["file"]):
                self._json({"error": "file missing"}, 410)
                return
            with io.open(j["file"], "rb") as f:
                data = f.read()
            name = os.path.basename(j["file"])
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition",
                             "attachment; filename*=UTF-8''" + urllib.parse.quote(name))
            self._cors()
            self.end_headers()
            self.wfile.write(data)
            return

        if p.path == "/":
            body = (u"<meta charset='utf-8'><body style='font-family:sans-serif;padding:40px'>"
                    u"<h2>链接批量导出服务已启动</h2>"
                    u"<p>回到专栏页「明细反馈流」，点右上角「批量导出」。</p>"
                    u"<p style='color:#666'>导出文件目录：%s</p></body>" % EXPORT_DIR).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return

        self._json({"error": "not found"}, 404)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        if not _origin_ok(self.headers.get("Origin")):
            self._json({"error": "origin not allowed"}, 403)
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception as e:
            self._json({"error": "bad json: %s" % e}, 400)
            return

        if p.path == "/api/parse":
            links = CORE.parse_links(payload.get("text") or "")
            self._json({"count": len(links), "links": links})
            return

        if p.path == "/api/export":
            text = (payload.get("text") or "").strip()
            if not text:
                self._json({"error": "没有链接"}, 400)
                return
            with LOCK:
                if any(x["status"] == "running" for x in JOBS.values()):
                    self._json({"error": "已有任务在跑，请等它结束"}, 409)
                    return
                jid = datetime.datetime.now().strftime("%H%M%S") + "-%03d" % (len(JOBS) % 1000)
                JOBS[jid] = {"id": jid, "status": "running", "logs": [], "file": "",
                             "size": 0, "error": "", "started": time.time()}
            args = {"text": text,
                    "format": payload.get("format") or "xlsx",
                    "maxComments": int(payload.get("maxComments") or 300),
                    "translate": bool(payload.get("translate", True)),
                    "replies": bool(payload.get("replies", True))}
            threading.Thread(target=_worker, args=(jid, args), daemon=True).start()
            self._json({"jobId": jid})
            return

        self._json({"error": "not found"}, 404)


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as e:
        print(u"端口 %d 被占用：%s" % (PORT, e))
        print(u"请关掉占用该端口的程序后重试。")
        input(u"按回车退出…")
        return
    print(u"=" * 56)
    print(u" 链接批量导出服务  http://127.0.0.1:%d" % PORT)
    print(u" 导出目录  %s" % EXPORT_DIR)
    print(u" 关闭此窗口即停止服务")
    print(u"=" * 56)
    print(u"就绪，等待页面调用…")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(u"\n已停止")


if __name__ == "__main__":
    main()
