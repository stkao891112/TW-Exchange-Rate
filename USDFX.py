import requests
import urllib3
from flask import Flask, jsonify
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor

# 隱藏 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── 抓取邏輯 ──────────────────────────────────────────────────────────

def fetch_max():
    try:
        resp = requests.get("https://max-api.maicoin.com/api/v2/tickers", timeout=5)
        data = resp.json()
        return {"usdt": float(data["usdttwd"]["last"]), "usdc": float(data["usdctwd"]["last"]), "name": "MAX"}
    except: return None

def fetch_bitopro():
    try:
        resp = requests.get("https://api.bitopro.com/v3/tickers", timeout=5)
        tickers = resp.json()["data"]
        usdt = next(t["lastPrice"] for t in tickers if t["pair"] == "usdt_twd")
        usdc = next(t["lastPrice"] for t in tickers if t["pair"] == "usdc_twd")
        return {"usdt": float(usdt), "usdc": float(usdc), "name": "BitoPro"}
    except: return None

def fetch_hoyabit():
    """HOYABIT API 抓取 USDT 與 USDC"""
    # 這裡必須提供更完整的 Headers，否則 HOYABIT 的伺服器會拒絕連線
    hoya_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://hoyabit.com",
        "Referer": "https://hoyabit.com/"
    }
    try:
        # 1. 抓取 USDT
        usdt_url = "https://guest-apis.hoyabit.com/guest/apis/v2/trades/symbol/1/target/4/price?type=1"
        res_usdt = requests.get(usdt_url, headers=hoya_headers, timeout=5)
        
        # 2. 抓取 USDC
        usdc_url = "https://guest-apis.hoyabit.com/guest/apis/v2/trades/symbol/1/target/10/price?type=1"
        res_usdc = requests.get(usdc_url, headers=hoya_headers, timeout=5)
        
        # 檢查 HTTP 狀態
        if res_usdt.status_code == 200 and res_usdc.status_code == 200:
            data_usdt = res_usdt.json()
            data_usdc = res_usdc.json()
            
            return {
                "usdt": float(data_usdt["data"]["target_price"]),
                "usdc": float(data_usdc["data"]["target_price"]),
                "name": "HOYABIT"
            }
        else:
            print(f"❌ HOYABIT 回傳錯誤碼: USDT({res_usdt.status_code}), USDC({res_usdc.status_code})")
            return None
            
    except Exception as e:
        print(f"❌ HOYABIT 抓取發生例外: {e}")
        return None

def fetch_line_bank():
    try:
        url = "https://www.linebank.com.tw/cob/v1/foreign/exchange-rate"
        data = requests.get(url, headers=HEADERS, timeout=5).json()
        rates = data['content']['exchangeRateList']
        usd_item = next(item for item in rates if item['currency'] == 'USD' and item['baseCurrency'] == 'TWD')
        return {"usd": float(usd_item['sellExchangeRate']), "name": "LINE Bank"}
    except: return None

def fetch_next_bank():
    url = "https://api.nextbank.com.tw/ap6/open/forex/v1.0/GetFXRate"
    headers = {"Content-Type": "application/json", "Referer": "https://www.nextbank.com.tw/", "User-Agent": HEADERS["User-Agent"]}
    try:
        res = requests.post(url, headers=headers, json={}, verify=False, timeout=5)
        data = res.json()
        usd_item = next(item for item in data['data']['currencyList'] if item['currency'] == 'USD')
        return {"usd": float(usd_item['buyRate']), "name": "NEXT Bank"}
    except: return None

# ── API 端點 ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return "API 伺服器運行中，請訪問 <a href='/api/rates'>/api/rates</a>"

@app.route("/api/rates")
def get_rates():
    # 同時執行 5 個抓取任務
    with ThreadPoolExecutor(max_workers=5) as executor:
        f_max = executor.submit(fetch_max)
        f_bito = executor.submit(fetch_bitopro)
        f_hoya = executor.submit(fetch_hoyabit)
        f_line = executor.submit(fetch_line_bank)
        f_next = executor.submit(fetch_next_bank)
        
        max_d = f_max.result()
        bito_d = f_bito.result()
        hoya_d = f_hoya.result()
        line_d = f_line.result()
        next_d = f_next.result()

    result = {
        "USDT": [
            {"provider": max_d["name"], "rate": max_d["usdt"]} if max_d else None,
            {"provider": bito_d["name"], "rate": bito_d["usdt"]} if bito_d else None,
            {"provider": hoya_d["name"], "rate": hoya_d["usdt"]} if hoya_d else None,
        ],
        "USDC": [
            {"provider": max_d["name"], "rate": max_d["usdc"]} if max_d else None,
            {"provider": bito_d["name"], "rate": bito_d["usdc"]} if bito_d else None,
            {"provider": hoya_d["name"], "rate": hoya_d["usdc"]} if hoya_d else None,
        ],
        "USD_BANK": [
            {"provider": line_d["name"], "rate": line_d["usd"]} if line_d else None,
            {"provider": next_d["name"], "rate": next_d["usd"]} if next_d else None,
        ]
    }
    
    # 清除 None
    for key in result:
        result[key] = [i for i in result[key] if i]
        
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, port=5000)