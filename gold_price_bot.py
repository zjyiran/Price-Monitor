import yfinance as yf
import requests
import json
import pandas as pd
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

def get_semiconductor_prices():
    """
    Fetches semiconductor stock prices (SK Hynix, Samsung, Kioxia).
    """
    results = {}
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
    Scrapes LiPF6 price from SunSirs (生意社) using Pandas.
    Target: https://www.sunsirs.com/uk/prodetail-1432.html
    """
    url = "https://www.sunsirs.com/uk/prodetail-1432.html"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        
        # 1. Fetch raw HTML
        # verify=False is important for GitHub Actions to avoid SSL errors with some CN sites
        response = requests.get(url, headers=headers, timeout=30, verify=False)
        
        if response.status_code != 200:
            print(f"SunSirs Error: Status Code {response.status_code}")
            # print(response.text[:200]) # Debug: Print first 200 chars if failed
            return None

        # 2. Parse tables using Pandas (Robust to whitespace/formatting changes)
        dfs = pd.read_html(response.text)
        
        # 3. Iterate through tables to find the one with our product
        for df in dfs:
            # Check if any string column contains the product name
            # SunSirs table usually has columns like: [Product, Sector, Price, Date]
            # We convert the dataframe to string to search easily
            mask = df.apply(lambda x: x.astype(str).str.contains("Lithium hexafluorophosphate", case=False, regex=False)).any(axis=1)
            
            if mask.any():
                target_row = df[mask].iloc[0]
                # Usually Price is in the 3rd column (index 2), but let's look for a number
                # Convert row to list
                row_values = target_row.tolist()
                
                for val in row_values:
                    # Look for a value that looks like a price (float > 1000)
                    try:
                        price_val = float(str(val).replace(',', '').strip())
                        if price_val > 1000: # Simple filter to distinguish from small numbers
                            return {
                                "name": "六氟磷酸锂 (LiPF6)",
                                "price": price_val,
                                "unit": "元/吨",
                                "source": "SunSirs"
                            }
                    except ValueError:
                        continue
        
        print("SunSirs Warning: Product found but could not parse price from table.")

    except Exception as e:
        print(f"Error fetching LiPF6 from SunSirs: {e}")
    
    return None

def send_to_feishu(gold_prices, semi_prices, material_prices):
    """
    Sends the combined price data to Feishu.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f"📊 **Daily Price Monitoring Update**\n🕒 Time: {now}\n\n"
    
    # 1. Precious Metals
    content += "🏆 **Precious Metals**\n"
    if not gold_prices:
        content += "⚠️ Failed to fetch gold data.\n"
    else:
        for name, info in gold_prices.items():
            trend = "📈" if info['change'] >= 0 else "📉"
            content += f"🔹 {name}\n"
            content += f"   Price: `{info['unit']}{info['price']:,.2f}`\n"
            content += f"   Change: {trend} `{info['change']:+.2f}` (`{info['change_percent']:+.2f}%`)\n"
    
    # 2. Semiconductors
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

    # 3. Battery Materials
    content += "\n🔋 **Battery Materials**\n"
    if not material_prices:
        content += "⚠️ Failed to fetch material data.\n"
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
            print(f"Failed to send to Feishu. Status: {response.status_code}")
    except Exception as e:
        print(f"Error sending to Feishu: {e}")

if __name__ == "__main__":
    print("Starting price fetch...")
    
    gold_data = get_gold_prices()
    semi_data = get_semiconductor_prices()
    
    material_data = []
    
    # Fetch LiPF6
    lipf6 = get_lipf6_price()
    if lipf6:
        material_data.append(lipf6)
    else:
        # Fallback message
        material_data.append({"name": "六氟磷酸锂 (LiPF6)", "error": "Fetch Failed (Check Logs)"})
    
    # VC Placeholder
    material_data.append({"name": "碳酸亚乙烯酯 (VC)", "error": "No Source"})
    
    send_to_feishu(gold_data, semi_data, material_data)
