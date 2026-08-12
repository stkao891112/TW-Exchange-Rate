import requests
import re
import json
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
        usdt_last = float(data["usdttwd"]["last"])
        usdc_last = float(data["usdctwd"]["last"])
        return {
            "usdt": usdt_last,
            "usdt_buy": usdt_last,
            "usdt_sell": usdt_last,
            "usdc": usdc_last,
            "usdc_buy": usdc_last,
            "usdc_sell": usdc_last,
            "name": "MAX"
        }
    except: return None

def fetch_bitopro():
    try:
        resp = requests.get("https://api.bitopro.com/v3/tickers", timeout=5)
        tickers = resp.json()["data"]
        usdt_ticker = next(t for t in tickers if t["pair"] == "usdt_twd")
        usdc_ticker = next(t for t in tickers if t["pair"] == "usdc_twd")
        
        usdt_last = float(usdt_ticker["lastPrice"])
        usdc_last = float(usdc_ticker["lastPrice"])
        
        return {
            "usdt": usdt_last,
            "usdt_buy": usdt_last,
            "usdt_sell": usdt_last,
            "usdc": usdc_last,
            "usdc_buy": usdc_last,
            "usdc_sell": usdc_last,
            "name": "BitoPro"
        }
    except Exception as e:
        print(f"❌ BitoPro 抓取發生例外: {e}")
        return None

def fetch_hoyabit():
    """HOYABIT API 抓取 USDT 與 USDC 最新成交價"""
    hoya_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://hoyabit.com",
        "Referer": "https://hoyabit.com/"
    }
    try:
        res_usdt = requests.get("https://guest-apis.hoyabit.com/guest/apis/v2/trades/symbol/1/target/4/price?type=1", headers=hoya_headers, timeout=5)
        res_usdc = requests.get("https://guest-apis.hoyabit.com/guest/apis/v2/trades/symbol/1/target/10/price?type=1", headers=hoya_headers, timeout=5)
        
        if res_usdt.status_code == 200 and res_usdc.status_code == 200:
            usdt_last = float(res_usdt.json()["data"]["target_price"])
            usdc_last = float(res_usdc.json()["data"]["target_price"])
            return {
                "usdt": usdt_last,
                "usdt_buy": usdt_last,
                "usdt_sell": usdt_last,
                "usdc": usdc_last,
                "usdc_buy": usdc_last,
                "usdc_sell": usdc_last,
                "name": "HOYABIT"
            }
        else:
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
        # sellExchangeRate: 銀行賣美元給客戶（客戶用 TWD 買 USD）
        # buyExchangeRate: 銀行向客戶買美元（客戶賣 USD 換 TWD）
        return {
            "sell": float(usd_item['sellExchangeRate']),  # 客戶買入美元匯率
            "buy": float(usd_item.get('buyExchangeRate', usd_item['sellExchangeRate'])),  # 客戶賣出美元匯率
            "name": "LINE Bank"
        }
    except Exception as e:
        print(f"❌ LINE Bank 抓取失敗：{e}")
        return None

def fetch_next_bank():
    url = "https://api.nextbank.com.tw/ap6/open/forex/v1.0/GetFXRate"
    headers = {"Content-Type": "application/json", "Referer": "https://www.nextbank.com.tw/", "User-Agent": HEADERS["User-Agent"]}
    try:
        res = requests.post(url, headers=headers, json={}, verify=False, timeout=5)
        data = res.json()
        usd_item = next(item for item in data['data']['currencyList'] if item['currency'] == 'USD')
        # NEXT Bank API 中的命名為客戶視角：
        # buyRate: 客戶買入美金價（銀行賣出 32.3190）
        # sellRate: 客戶賣出美金價（銀行買入 32.1860）
        return {
            "sell": float(usd_item['buyRate']),   # 銀行賣出價（高價 32.3190）
            "buy": float(usd_item['sellRate']),   # 銀行買入價（低價 32.1860）
            "name": "NEXT Bank"
        }
    except Exception as e:
        print(f"❌ NEXT Bank 抓取失敗：{e}")
        return None

def fetch_cathay_bank():
    """抓取國泰世華銀行 (CU BANK) 數位通路美金優惠匯率"""
    url = 'https://www.cathaybk.com.tw/cathaybk/personal/product/deposit/currency-billboard/'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    try:
        res = requests.get(url, headers=headers, timeout=6)
        res.encoding = 'utf-8'
        html = res.text
        
        usd_start = html.find('select-id="1"')
        if usd_start == -1: return None
        usd_end = html.find('select-id="2"', usd_start)
        if usd_end == -1: usd_end = usd_start + 5000
        
        usd_html = html[usd_start:usd_end]
        rows = re.findall(r'<tr>[\s\S]*?<div class="cubre-m-rateTable__name">([\s\S]*?)</div>[\s\S]*?<div>([\d\.]+)</div>[\s\S]*?<div>([\d\.]+)</div>[\s\S]*?</tr>', usd_html)
        
        rates = {}
        for name_raw, buy_str, sell_str in rows:
            rates[name_raw.strip()] = {"buy": float(buy_str), "sell": float(sell_str)}
            
        digital_promo = rates.get("數位通路優惠匯率") or rates.get("即期匯率")
        if not digital_promo: return None
        
        return {
            "sell": digital_promo["sell"],  # 客戶買入美金匯率（銀行賣出）
            "buy": digital_promo["buy"],   # 客戶賣出美金匯率（銀行買入）
            "name": "CU BANK"
        }
    except Exception as e:
        print(f"[ERROR] CU BANK fetch failed: {e}")
        return None

def fetch_sinopac_bank():
    """抓取永豐銀行 (SinoPac Bank / 大戶 DAWHO) 美金即期匯率"""
    url = 'https://mma.sinopac.com/ws/share/rate/ws_exchange.ashx?exchangeType=REMIT'
    headers = {
        'User-Agent': HEADERS["User-Agent"],
        'Referer': 'https://bank.sinopac.com/MMA8/bank/html/rate/bank_ExchangeRate.html'
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        sub_info = data[0].get("SubInfo", [])
        usd_item = next(item for item in sub_info if item.get("DataValue4") == "USD" or "USD" in item.get("DataValue1", ""))
        
        return {
            "sell": float(usd_item["DataValue3"]),  # 銀行賣出
            "buy": float(usd_item["DataValue2"]),   # 銀行買入
            "name": "SinoPac Bank"
        }
    except Exception as e:
        print(f"[ERROR] SinoPac Bank fetch failed: {e}")
        return None

def fetch_richart_bank():
    """抓取台新銀行 (Richart Bank) 美金優惠匯率"""
    url = 'https://richart.tw/TSDIB_RichartWeb/foreign-currency/demand-deposit'
    headers = {
        'User-Agent': HEADERS["User-Agent"],
        'Referer': 'https://richart.tw/TSDIB_RichartWeb/foreign-currency/demand-deposit'
    }
    try:
        res = requests.get(url, headers=headers, timeout=6)
        res.encoding = 'utf-8'
        html_text = res.text
        
        tag_match = re.search(r'<input[^>]*id=["\']exchangeRateArray["\'][^>]*>', html_text)
        if not tag_match: return None
            
        full_tag = tag_match.group(0)
        val_match = re.search(r'value=(["\'])([\s\S]*?)\1', full_tag)
        if not val_match: return None
            
        raw_val = val_match.group(2)
        json_str = raw_val.replace("'", '"')
        rates_data = json.loads(json_str)
        
        usd_item = next(item for item in rates_data if item.get("code") == "USD")
        
        sell_rate = float(usd_item["richartSellRates"])
        buy_rate = float(usd_item["richartBuyRates"])
        
        return {
            "sell": sell_rate,  # 銀行賣出
            "buy": buy_rate,    # 銀行買入
            "name": "Taishin Bank"
        }
    except Exception as e:
        print(f"[ERROR] Taishin Bank fetch failed: {e}")
        return None

# ── API 端點 ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    """提供 HTML 文件"""
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return "API 伺服器運行中，請訪問 <a href='/api/rates'>/api/rates</a>"

@app.route("/api/rates")
def get_rates():
    import datetime
    # 同時執行 8 個抓取任務
    with ThreadPoolExecutor(max_workers=8) as executor:
        f_max = executor.submit(fetch_max)
        f_bito = executor.submit(fetch_bitopro)
        f_hoya = executor.submit(fetch_hoyabit)
        f_line = executor.submit(fetch_line_bank)
        f_next = executor.submit(fetch_next_bank)
        f_cathay = executor.submit(fetch_cathay_bank)
        f_sinopac = executor.submit(fetch_sinopac_bank)
        f_richart = executor.submit(fetch_richart_bank)
        
        max_d = f_max.result()
        bito_d = f_bito.result()
        hoya_d = f_hoya.result()
        line_d = f_line.result()
        next_d = f_next.result()
        cathay_d = f_cathay.result()
        sinopac_d = f_sinopac.result()
        richart_d = f_richart.result()

    result = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "success",
        "USDT": [
            {"provider": max_d["name"], "rate": max_d["usdt"], "buy": max_d["usdt_buy"], "sell": max_d["usdt_sell"]} if max_d else None,
            {"provider": bito_d["name"], "rate": bito_d["usdt"], "buy": bito_d["usdt_buy"], "sell": bito_d["usdt_sell"]} if bito_d else None,
            {"provider": hoya_d["name"], "rate": hoya_d["usdt"], "buy": hoya_d["usdt"], "sell": hoya_d["usdt"]} if hoya_d else None,
        ],
        "USDC": [
            {"provider": max_d["name"], "rate": max_d["usdc"], "buy": max_d["usdc_buy"], "sell": max_d["usdc_sell"]} if max_d else None,
            {"provider": bito_d["name"], "rate": bito_d["usdc"], "buy": bito_d["usdc_buy"], "sell": bito_d["usdc_sell"]} if bito_d else None,
            {"provider": hoya_d["name"], "rate": hoya_d["usdc"], "buy": hoya_d["usdc"], "sell": hoya_d["usdc"]} if hoya_d else None,
        ],
        "USD_BANK": [
            {"provider": line_d["name"], "sell": line_d["sell"], "buy": line_d["buy"]} if line_d else None,
            {"provider": next_d["name"], "sell": next_d["sell"], "buy": next_d["buy"]} if next_d else None,
            {"provider": cathay_d["name"], "sell": cathay_d["sell"], "buy": cathay_d["buy"]} if cathay_d else None,
            {"provider": sinopac_d["name"], "sell": sinopac_d["sell"], "buy": sinopac_d["buy"]} if sinopac_d else None,
            {"provider": richart_d["name"], "sell": richart_d["sell"], "buy": richart_d["buy"]} if richart_d else None,
        ]
    }
    
    # 清除 None
    for key in ["USDT", "USDC", "USD_BANK"]:
        result[key] = [i for i in result[key] if i]
        
    return jsonify(result)

if __name__ == "__main__":
    print("Starting TWD Exchange Rate Comparison Tool...")
    print("Local URL: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
