/**
 * Cloudflare Worker — Yahoo 財經報價代理(給 GitHub Pages 的網頁版用)
 *
 * 作用:瀏覽器不能直接抓 Yahoo(沒有 CORS),這支 Worker 由伺服器端去抓,
 *       再補上 CORS 標頭回傳,網頁就能穩定取得即時報價。
 *
 * 用法:GET https://你的名稱.workers.dev/?symbol=2330.TW&range=5y&interval=1d
 *       回傳 Yahoo 原始 JSON(與網頁的 parseYahoo 相容)。
 *
 * 部署(免費,約 5 分鐘):
 *   1. 登入 https://dash.cloudflare.com → 左側 Workers & Pages → Create → Create Worker。
 *   2. 取個名字(例:stock-proxy)→ Deploy。
 *   3. 進該 Worker → Edit code,把本檔內容整個貼上 → Deploy。
 *   4. 複製網址(https://stock-proxy.你的帳號.workers.dev),貼到網頁的
 *      「資料來源 Worker 網址」欄位即可。
 */
export default {
  async fetch(request) {
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "*",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    const url = new URL(request.url);

    // === 台股即時報價(證交所 MIS)===  用 ?twse=2330
    const twse = (url.searchParams.get("twse") || "").trim();
    if (twse) {
      if (!/^\d{3,7}$/.test(twse)) {
        return new Response(JSON.stringify({ error: "bad twse" }),
          { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
      }
      const ch = `tse_${twse}.tw|otc_${twse}.tw`;  // 同時查上市與上櫃
      const mu = `https://mis.twse.com.tw/stock/api/getStockInfo.jsp` +
                 `?ex_ch=${encodeURIComponent(ch)}&json=1&delay=0&_=${Date.now()}`;
      try {
        const r = await fetch(mu, {
          headers: {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://mis.twse.com.tw/stock/index.jsp",
          },
          cf: { cacheTtl: 3, cacheEverything: true },
        });
        const body = await r.text();
        return new Response(body, {
          status: r.status,
          headers: { ...cors, "Content-Type": "application/json; charset=utf-8" },
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: String(e) }),
          { status: 502, headers: { ...cors, "Content-Type": "application/json" } });
      }
    }

    // === 美股 / 歷史日線(Yahoo)===  用 ?symbol=AAPL
    const symbol = (url.searchParams.get("symbol") || "").trim();
    const range = url.searchParams.get("range") || "5y";
    const interval = url.searchParams.get("interval") || "1d";

    // 只允許合法的股票代碼字元,避免被當成萬能代理濫用
    if (!symbol || !/^[A-Za-z0-9.\-]{1,15}$/.test(symbol) ||
        !/^[0-9a-z]{1,4}$/.test(range) || !/^[0-9a-z]{1,4}$/.test(interval)) {
      return new Response(JSON.stringify({ error: "bad params" }),
        { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
    }

    const y = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}` +
              `?range=${range}&interval=${interval}`;
    try {
      const r = await fetch(y, {
        headers: { "User-Agent": "Mozilla/5.0", "Accept": "application/json" },
        cf: { cacheTtl: 5, cacheEverything: true },   // 只快取 5 秒,支援約 10 秒的即時更新
      });
      const body = await r.text();
      return new Response(body, {
        status: r.status,
        headers: { ...cors, "Content-Type": "application/json; charset=utf-8" },
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }),
        { status: 502, headers: { ...cors, "Content-Type": "application/json" } });
    }
  },
};
