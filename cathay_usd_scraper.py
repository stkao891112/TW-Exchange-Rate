import requests
import re

def get_cathay_usd_digital_promo():
    """
    爬取國泰世華銀行 (Cathay United Bank) 美元 (USD) 數位通路優惠匯率
    傳回 dict: {
        "bank_buy": float,  # 銀行買進 (客戶賣出美金換台幣)
        "bank_sell": float, # 銀行賣出 (客戶拿台幣買美金)
        "all_rates": dict   # 所有美金匯率 (即期、數位通路優惠、現鈔)
    }
    """
    url = 'https://www.cathaybk.com.tw/cathaybk/personal/product/deposit/currency-billboard/'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    res = requests.get(url, headers=headers, timeout=10)
    res.encoding = 'utf-8'
    html = res.text

    # 定位美元 (USD) 卡片區塊 (select-id="1")
    usd_start = html.find('select-id="1"')
    if usd_start == -1:
        raise ValueError("無法找到國泰世華美元匯率數據區塊")
    
    usd_end = html.find('select-id="2"', usd_start)
    if usd_end == -1:
        usd_end = usd_start + 5000

    usd_html = html[usd_start:usd_end]

    # 正則表達式抓取各列 (項目名稱, 銀行買進, 銀行賣出)
    rows = re.findall(r'<tr>[\s\S]*?<div class="cubre-m-rateTable__name">([\s\S]*?)</div>[\s\S]*?<div>([\d\.]+)</div>[\s\S]*?<div>([\d\.]+)</div>[\s\S]*?</tr>', usd_html)

    all_rates = {}
    for name_raw, buy_str, sell_str in rows:
        name = name_raw.strip()
        all_rates[name] = {
            "bank_buy": float(buy_str),
            "bank_sell": float(sell_str)
        }

    digital_promo = all_rates.get("數位通路優惠匯率", {})

    return {
        "digital_promo_buy": digital_promo.get("bank_buy"),
        "digital_promo_sell": digital_promo.get("bank_sell"),
        "all_rates": all_rates
    }

if __name__ == "__main__":
    result = get_cathay_usd_digital_promo()
    promo_buy = result["digital_promo_buy"]
    promo_sell = result["digital_promo_sell"]

    print("==================================================")
    print("Cathay United Bank - USD Digital Promo Rates")
    print("國泰世華銀行 - 美元 (USD) 數位通路優惠匯率")
    print("==================================================")
    print(f"Bank Buy  (銀行買進 / 客戶賣出美金): {promo_buy} TWD")
    print(f"Bank Sell (銀行賣出 / 客戶買進美金): {promo_sell} TWD")
    print("--------------------------------------------------")
    print("Full USD Rate Table (完整美元匯率對照表):")
    for name, data in result["all_rates"].items():
        print(f"  [{name}] Buy: {data['bank_buy']} TWD | Sell: {data['bank_sell']} TWD")
    print("==================================================")
