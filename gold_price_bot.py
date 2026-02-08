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
            # Fetch 2 days to calculate change
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

def get_semiconductor_prices():
    """
    Fetches semiconductor stock prices using yfinance.
    Covers: SK Hynix, Samsung Electronics, Kioxia.
    """
    results = {}
    # Tickers:
    # 000660.KS = SK Hynix (KRW)
    # 005930.KS = Samsung Electronics (KRW)
    # 285A.T    = Kioxia Holdings (JPY)
    symbols = {
        "000660.KS": {"name": "SK Hynix", "unit": "₩"},
        "005930.KS": {"name": "Samsung Electronics", "unit": "₩"},
        "285A.T":    {"name": "Kioxia", "unit": "¥"}
    }
    
    for sym, info in symbols.items():
        try:
            ticker = yf.Ticker(sym)
            data = ticker.history(period="2d")
            
            if len(data) >= 1:
                current_price = data['Close'].iloc[-1]
                # Calculate change if we have 2 days of data
                if len(data) >= 2:
                    prev_price = data['Close'].iloc[-2]
                    change = current_price - prev_price
                    change_percent = (change / prev_price) * 100
                else:
                    change = 0
                    change_percent = 0
                
                results[info['name']] = {
                    "price": current_price,
                    "change": change,
                    "change_percent": change_percent,
                    "unit": info['unit']
                }
        except Exception as e:
            print(f"Error fetching {sym}: {e}")
            results[info['name']] = {"error": str(e)}
            
    return results

def get_lipf6_price():
    """
    Scrapes LiPF6 price from SunSirs (生意社).
    URL: https://www.sunsirs.com/uk/prodetail-1432.html
    """
    url = "https://www.sunsirs.com/uk/prodetail-1432.html"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        
        # 1. Check for product name to ensure we are on the right page
        if "Lithium hexafluorophosphate" in response.text:
            # Regex to find the price in the table row corresponding to the product
            # Looking for: <td>Lithium hexafluorophosphate</td> ... <td>PRICE</td>
            match = re.search(r'Lithium hexafluorophosphate.*?</td>\s*<td>.*?</td>\s*<td>\s*([\d\.]+)\s*</td>', response.text, re.DOTALL)
            
            if match:
                price_str = match.group(1)
                return {
                    "name": "六氟磷酸锂 (LiPF6)",
                    "price": float(price_str),
                    "unit": "元/吨",
                    "source": "SunSirs (生意社)"
                }
            else:
                print("Could not find price pattern in SunSirs page.")
        else:
             print("Could not find product name in SunSirs page.")

    except Exception as e:
        print(f"Error fetching LiPF6 from SunSirs: {e}")
    
    return None

def send_to_feishu(gold_prices, semi_prices, material_prices):
    """
    Sends the price data to Feishu via Webhook.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f"📊 **Daily Price Monitoring Update**\n🕒 Time: {now}\n\n"
    
    # 1. Precious Metals Section
    content += "🏆 **Precious Metals**\n"
    if not gold_prices:
        content += "⚠️ Failed to fetch gold price data.\n"
    else:
        for name, info in gold_prices.items():
            trend = "📈" if info['change'] >= 0 else "📉"
            content += f"🔹 {name}\n"
            content += f"   Price: `{info['unit']}{info['price']:,.2f}`\n"
            content += f"   Change: {trend} `{info['change']:+.2f}` (`{info['change_percent']:+.2f}%`)\n"
    
    # 2. Semiconductor Section
    content += "\n💾 **Memory & Storage**\n"
    if not semi_prices:
        content += "⚠️ Failed to fetch semiconductor data.\n"
    else:
        for name, info in semi_prices.items():
            if "error" in info:
                 content += f"🔸 {name}: `Error` ({info['error']})\n"
            else:
                trend = "📈" if info['change'] >= 0 else "📉"
                # Formatting: KRW/JPY usually don't use decimals for large numbers
                content += f"🔸 {name}\n"
                content += f"   Price: `{info['unit']}{info['price']:,.0f}`\n"
                content += f"   Change: {trend} `{info['change']:+.0f}` (`{info['change_percent']:+.2f}%`)\n"

    # 3. Battery Materials Section
    content += "\n🔋 **Battery Materials**\n"
    if not material_prices:
        content += "⚠️ Failed to fetch material price data.\n"
    else:
        for item in material_prices:
            if "error" in item:
                content += f"🔹 {item['name']}: `Unavailable` ({item['error']})\n"
            else:
                content += f"🔹 {item['name']}\n"
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
    
    # Fetch Data
    gold_data = get_gold_prices()
    semi_data = get_semiconductor_prices()
    
    material_data = []
    
    # Fetch LiPF6 from SunSirs
    lipf6 = get_lipf6_price()
    if lipf6:
        material_data.append(lipf6)
    else:
        material_data.append({"name": "六氟磷酸锂 (LiPF6)", "error": "Fetch failed"})

    # Placeholder for VC (still blocked/no easy source)
    material_data.append({"name": "碳酸亚乙烯酯 (VC)", "error": "No Source"})
    
    # Send all data
    send_to_feishu(gold_data, semi_data, material_data)
