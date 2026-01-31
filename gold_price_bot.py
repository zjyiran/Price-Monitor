import yfinance as yf
import requests
import json
import re
from datetime import datetime

# User Configuration
FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/865c3b28-d2eb-4d5d-ab7e-582ad42414cd"

def get_gold_prices():
    """
    Fetches gold prices using yfinance.
    """
    results = {}
    symbols = {"GC=F": "Gold Futures (COMEX)", "GLD": "SPDR Gold Shares (ETF)"}
    
    for sym, name in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            data = ticker.history(period="2d")
            if len(data) >= 2:
                current_price = data['Close'].iloc[-1]
                prev_price = data['Close'].iloc[-2]
                change = current_price - prev_price
                change_percent = (change / prev_price) * 100
                results[name] = {
                    "price": current_price,
                    "change": change,
                    "change_percent": change_percent,
                    "unit": "$"
                }
            elif len(data) == 1:
                current_price = data['Close'].iloc[-1]
                results[name] = {
                    "price": current_price,
                    "change": 0,
                    "change_percent": 0,
                    "unit": "$"
                }
        except Exception as e:
            print(f"Error fetching {sym}: {e}")
            
    return results

def get_lipf6_price():
    """
    Scrapes LiPF6 price from SMM English site (metal.com).
    """
    url = "https://www.metal.com/Lithium/202110220001"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        matches = re.findall(r'([\d,]+)</div><div class=[^>]+>yuan/tonne', response.text)
        if matches:
            price_str = matches[0].replace(',', '')
            return {
                "name": "六氟磷酸锂 (LiPF6)",
                "price": float(price_str),
                "unit": "元/吨",
                "source": "SMM"
            }
    except Exception as e:
        print(f"Error fetching LiPF6: {e}")
    return None

def send_to_feishu(gold_prices, material_prices):
    """
    Sends the price data to Feishu via Webhook.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f"📊 **Daily Price Monitoring Update**\n🕒 Time: {now}\n\n"
    
    # Gold Section
    content += "🏆 **Precious Metals**\n"
    if not gold_prices:
        content += "⚠️ Failed to fetch gold price data.\n"
    else:
        for name, info in gold_prices.items():
            trend = "📈" if info['change'] >= 0 else "📉"
            content += f"🔹 {name}\n"
            content += f"   Price: `{info['unit']}{info['price']:.2f}`\n"
            content += f"   Change: {trend} `{info['change']:+.2f}` (`{info['change_percent']:+.2f}%`)\n"
    
    content += "\n🔋 **Battery Materials**\n"
    if not material_prices:
        content += "⚠️ Failed to fetch material price data.\n"
    else:
        for item in material_prices:
            if "error" in item:
                content += f"🔸 {item['name']}: `Unavailable` ({item['error']})\n"
            else:
                content += f"🔸 {item['name']}\n"
                content += f"   Price: `{item['price']:,.2f} {item['unit']}`\n"
                content += f"   Source: {item['source']}\n"
    
    content += "\n---"

    payload = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }
    
    try:
        response = requests.post(
            FEISHU_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        if response.status_code == 200:
            print("Successfully sent to Feishu.")
        else:
            print(f"Failed to send to Feishu. Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error sending to Feishu: {e}")

if __name__ == "__main__":
    print("Starting price fetch...")
    gold_data = get_gold_prices()
    
    material_data = []
    lipf6 = get_lipf6_price()
    if lipf6:
        material_data.append(lipf6)
    
    # Placeholder for VC as it's currently blocked
    material_data.append({"name": "碳酸亚乙烯酯 (VC)", "error": "Source blocked (100ppi)"})
    
    send_to_feishu(gold_data, material_data)
