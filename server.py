"""小跌小買・大跌大買 — 本機伺服器。

只用 Python 標準函式庫,不需安裝任何套件。
職責:
  1. 提供網頁儀表板 (index.html)。
  2. /api/quote?symbol=XXX  向 Yahoo 財經抓「現價」與「每日收盤價序列」
     (高點 = 期間內最高收盤價,由前端依所選期間計算)。
     - 台股:輸入 4~6 位數字(如 2330),自動嘗試 .TW(上市)→ .TWO(上櫃)。
     - 美股:直接輸入代碼(如 AAPL、VOO)。
     - 也可自行輸入完整代碼(如 2330.TW、BRK-B)。

執行:python server.py  (或直接用 start.bat)
"""

import json
import os
import socket
import threading
import webbrowser
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PREFERRED_PORTS = [8777, 8778, 8799, 8808, 0]  # 0 = 讓系統挑一個可用埠

YAHOO_HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def normalize_symbols(raw: str):
    """回傳要嘗試的代碼清單(依序嘗試)。"""
    s = (raw or "").strip().upper()
    if not s:
        return []
    if "." in s:            # 已含市場後綴,如 2330.TW / 2330.TWO
        return [s]
    if s.isdigit():         # 純數字 → 台股,先上市再上櫃
        return [s + ".TW", s + ".TWO"]
    return [s]              # 其餘視為美股/國際代碼


def _fetch_one(symbol: str):
    """向 Yahoo 抓單一代碼,成功回傳 dict,失敗回傳 None。"""
    path = "/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=5y&interval=1d"
    for host in YAHOO_HOSTS:
        url = "https://" + host + path
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.load(resp)
        except Exception:
            continue
        try:
            result = data["chart"]["result"][0]
            meta = result["meta"]
            price = meta.get("regularMarketPrice")
            if price is None:
                continue
            ts = result.get("timestamp") or []
            closes_raw = []
            for q in result.get("indicators", {}).get("quote", [{}]):
                closes_raw = q.get("close") or []
                break
            # 對齊時間與「收盤價」,濾掉缺漏日
            ts_out, cl_out = [], []
            for t, c in zip(ts, closes_raw):
                if t is not None and c is not None:
                    ts_out.append(int(t))
                    cl_out.append(round(float(c), 4))
            if not cl_out:   # 後備:至少給目前價一筆
                ts_out = [int(meta.get("regularMarketTime") or 0)]
                cl_out = [float(price)]
            # 昨收 = 日線倒數第二根收盤(最後一根是今天/最新)。
            # 不可用 meta.chartPreviousClose:那是「整段抓取範圍起點之前」的收盤,
            # 在 range=5y 下等於約 5 年前的價格,會害今日跌幅算錯。
            prev = cl_out[-2] if len(cl_out) >= 2 else None
            return {
                "symbol": meta.get("symbol", symbol),
                "price": float(price),
                "prevClose": (float(prev) if prev is not None else None),
                "currency": meta.get("currency", ""),
                "exchange": meta.get("exchangeName", ""),
                "ts": ts_out,
                "closes": cl_out,
            }
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return None


def get_quote(raw_symbol: str):
    tried = normalize_symbols(raw_symbol)
    if not tried:
        return {"ok": False, "error": "請輸入股票代碼。"}
    for sym in tried:
        q = _fetch_one(sym)
        if q:
            q["ok"] = True   # 高點/跌幅由前端依所選期間計算
            return q
    return {"ok": False,
            "error": "查不到此代碼的股價(試過:%s)。請確認代碼,或檢查網路。"
                     % ", ".join(tried)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # 安靜

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, "index.html not found", "text/plain; charset=utf-8")
            return
        if parsed.path == "/api/quote":
            qs = urllib.parse.parse_qs(parsed.query)
            symbol = (qs.get("symbol", [""])[0])
            try:
                result = get_quote(symbol)
            except Exception as e:
                result = {"ok": False, "error": "伺服器錯誤:%s" % e}
            self._send(200, json.dumps(result, ensure_ascii=False))
            return
        self._send(404, json.dumps({"ok": False, "error": "not found"}))


def pick_port():
    for p in PREFERRED_PORTS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((HOST, p))
            port = s.getsockname()[1]
            s.close()
            return port
        except OSError:
            continue
    return 8777


def main():
    port = pick_port()
    url = "http://%s:%d/" % (HOST, port)
    httpd = ThreadingHTTPServer((HOST, port), Handler)
    print("=" * 48)
    print("  小跌小買・大跌大買 試算儀表板")
    print("  已啟動:" + url)
    print("  關閉:在此視窗按 Ctrl+C")
    print("=" * 48)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已關閉。")
        httpd.shutdown()


if __name__ == "__main__":
    main()
