import os
import sqlite3
import requests
from datetime import datetime, timedelta

# 嘗試讀取同目錄下的 .env 檔案以載入環境變數
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

# ================= 配置設定 =================
API_KEY = os.getenv("API_KEY")

# 航線設定
FLY_FROM = os.getenv("FLY_FROM", "TPE")
FLY_TO = os.getenv("FLY_TO", "DAD")

# 模式選擇: "single" 表示查詢單一特定起迄日，"range" 表示查詢區間內固定天數的組合
SEARCH_MODE = os.getenv("SEARCH_MODE", "range")

# 1. 單一起迄日模式參數 (SEARCH_MODE = "single" 時使用)
DATE_FROM = os.getenv("DATE_FROM", "2026-10-03")
DATE_TO = os.getenv("DATE_TO", "2026-10-09")

# 2. 區間搜尋模式參數 (SEARCH_MODE = "range" 時使用)
RANGE_START = os.getenv("RANGE_START", "2026-10-03")
RANGE_END = os.getenv("RANGE_END", "2026-10-09")
TRAVEL_DURATION = int(os.getenv("TRAVEL_DURATION", "5"))
TOP_N_RESULTS = int(os.getenv("TOP_N_RESULTS", "3"))

# 通知的價格門檻
PRICE_THRESHOLD = int(os.getenv("PRICE_THRESHOLD", "8000"))

DB_NAME = os.getenv("DB_NAME", "flights_history.db")
# ============================================

def init_db():
    """初始化 SQLite 資料庫並升級舊欄位"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            fly_from TEXT,
            fly_to TEXT,
            outbound_date TEXT,
            return_date TEXT,
            price INTEGER,
            deeplink TEXT
        )
    ''')
    
    # 檢查是否需要升級舊資料庫結構
    cursor.execute("PRAGMA table_info(price_history)")
    columns = [info[1] for info in cursor.fetchall()]
    if "outbound_date" not in columns:
        cursor.execute("ALTER TABLE price_history ADD COLUMN outbound_date TEXT")
    if "return_date" not in columns:
        cursor.execute("ALTER TABLE price_history ADD COLUMN return_date TEXT")
        
    conn.commit()
    conn.close()

def get_lowest_price_from_db(outbound_date=None, return_date=None):
    """查詢資料庫中的歷史最低價"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if outbound_date and return_date:
        cursor.execute('''
            SELECT MIN(price) FROM price_history 
            WHERE fly_from=? AND fly_to=? AND outbound_date=? AND return_date=?
        ''', (FLY_FROM, FLY_TO, outbound_date, return_date))
    else:
        cursor.execute('SELECT MIN(price) FROM price_history WHERE fly_from=? AND fly_to=?', (FLY_FROM, FLY_TO))
    result = cursor.fetchone()[0]
    conn.close()
    return result if result is not None else float('inf')

def save_price_to_db(price, deeplink, outbound_date, return_date):
    """將本次查詢結果存入資料庫"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO price_history (timestamp, fly_from, fly_to, outbound_date, return_date, price, deeplink)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), FLY_FROM, FLY_TO, outbound_date, return_date, price, deeplink))
    conn.commit()
    conn.close()

def search_flight(outbound_date, return_date):
    """呼叫 SerpApi 查詢 Google Flights 最便宜機票"""
    if not API_KEY:
        print("錯誤：找不到 API_KEY，無法呼叫 SerpApi。")
        return None, None
        
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_flights",
        "departure_id": FLY_FROM,
        "arrival_id": FLY_TO,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "currency": "TWD",
        "hl": "zh-tw",
        "api_key": API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 取得最便宜的航班資訊（通常排序在第一個）
        best_flights = data.get("best_flights", [])
        if best_flights:
            best_deal = best_flights[0]
            price = best_deal.get("price")
            
            # SerpApi 會提供一個直接開啟 Google Flights 該行程的連結
            deeplink = data.get("search_metadata", {}).get("google_flights_url", "https://www.google.com/travel/flights")
            return price, deeplink
        else:
            print(f"[{outbound_date} -> {return_date}] 未找到最佳航班資料")
            return None, None
            
    except Exception as e:
        print(f"[{outbound_date} -> {return_date}] SerpApi 查詢失敗: {e}")
        return None, None

# ================= LINE API 設定 =================
# 請將這兩個變數設定到 .env、環境變數或 GitHub Secrets 中
LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
# ================================================

# ================= Brevo E-mail 設定 =============
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
# ================================================

def send_line_message(message_text):
    """使用 Messaging API 發送 LINE 官方帳號訊息"""
    if not LINE_ACCESS_TOKEN or not LINE_USER_ID:
        print("錯誤：找不到 LINE_ACCESS_TOKEN 或 LINE_USER_ID，無法發送 LINE 通知。")
        return
        
    url = "https://api.line.me/v2/bot/message/push"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print("LINE 官方帳號通知發送成功！")
    except Exception as e:
        print(f"LINE 發送失敗: {e}")

def send_email_notification(subject, message_text):
    """使用 Brevo API 發送 E-mail 通知"""
    if not BREVO_API_KEY or not SENDER_EMAIL or not RECIPIENT_EMAIL:
        print("錯誤：找不到 BREVO_API_KEY、SENDER_EMAIL 或 RECIPIENT_EMAIL，無法發送 E-mail 通知。")
        return
        
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    
    # 轉換換行符號以符合 HTML 格式
    html_content = f"<html><body><div style='font-family: sans-serif; line-height: 1.6;'>{message_text.replace(chr(10), '<br>')}</div></body></html>"
    
    payload = {
        "sender": {
            "name": "Flight Tracker",
            "email": SENDER_EMAIL
        },
        "to": [
            {
                "email": RECIPIENT_EMAIL,
                "name": "Flight Tracker Subscriber"
            }
        ],
        "subject": subject,
        "htmlContent": html_content,
        "textContent": message_text
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print("E-mail 通知發送成功！")
    except Exception as e:
        print(f"E-mail 發送失敗: {e}")

def main():
    init_db()
    
    # 根據模式生成查詢日期組合
    date_combinations = []
    if SEARCH_MODE == "single":
        date_combinations.append((DATE_FROM, DATE_TO))
        limit_n = 1
    elif SEARCH_MODE == "range":
        start_dt = datetime.strptime(RANGE_START, "%Y-%m-%d")
        end_dt = datetime.strptime(RANGE_END, "%Y-%m-%d")
        limit_n = TOP_N_RESULTS
        
        current_dt = start_dt
        while current_dt + timedelta(days=TRAVEL_DURATION) <= end_dt:
            outb = current_dt.strftime("%Y-%m-%d")
            ret = (current_dt + timedelta(days=TRAVEL_DURATION)).strftime("%Y-%m-%d")
            date_combinations.append((outb, ret))
            current_dt += timedelta(days=1)
    else:
        print("未知的搜尋模式。")
        return
        
    if not date_combinations:
        print("沒有可查詢的日期組合。")
        return

    print(f"模式: {SEARCH_MODE}，總共需要查詢 {len(date_combinations)} 組日期...")
    
    results = []
    for outbound, ret in date_combinations:
        print(f"正在查詢 {outbound} -> {ret}...")
        price, deeplink = search_flight(outbound, ret)
        if price is not None:
            # 查詢本次查詢前的歷史最低價
            historical_low = get_lowest_price_from_db(outbound, ret)
            
            results.append({
                "outbound_date": outbound,
                "return_date": ret,
                "price": price,
                "deeplink": deeplink,
                "historical_low": historical_low
            })
            
            # 紀錄本次價格到資料庫
            save_price_to_db(price, deeplink, outbound, ret)
            
    if not results:
        print("所有日期組合查詢均失敗。")
        return
        
    # 依票價從低到高排序
    results.sort(key=lambda x: x["price"])
    top_results = results[:limit_n]
    
    print("\n--- 查詢結果排行 ---")
    for idx, res in enumerate(top_results, 1):
        print(f"{idx}. {res['outbound_date']} -> {res['return_date']}: NT$ {res['price']} (歷史低價: {res['historical_low']})")
        
    # 判斷是否需要發送通知 (任一前幾名組合的票價低於門檻，或比該組合歷史低價便宜)
    should_notify = False
    for res in top_results:
        if res["price"] < res["historical_low"] or res["price"] <= PRICE_THRESHOLD:
            should_notify = True
            break
            
    if should_notify:
        print("觸發通知條件！")
        # 組合 LINE 訊息
        if SEARCH_MODE == "single":
            res = top_results[0]
            message_text = (
                f"✈️ 【機票降價通知】\n"
                f"航線：{FLY_FROM} ➡️ {FLY_TO}\n"
                f"日期：{res['outbound_date']} ➡️ {res['return_date']}\n"
                f"目前最低價：NT$ {res['price']}\n"
                f"立即查看：{res['deeplink']}"
            )
        else:
            message_lines = [
                "✈️ 【機票降價通知 (區間搜尋)】",
                f"航線：{FLY_FROM} ➡️ {FLY_TO} (旅遊天數: {TRAVEL_DURATION}天)",
                "最便宜的前幾名組合："
            ]
            for i, res in enumerate(top_results, 1):
                hist_low_str = f"NT$ {res['historical_low']}" if res['historical_low'] != float('inf') else "無"
                message_lines.append(
                    f"\n{i}. {res['outbound_date']} ➡️ {res['return_date']}"
                    f"\n   票價：NT$ {res['price']} (歷史最低: {hist_low_str})"
                    f"\n   連結：{res['deeplink']}"
                )
            message_text = "\n".join(message_lines)
            
        send_line_message(message_text)
        
        # 發送 E-mail 通知
        subject = f"✈️ 【機票降價通知】{FLY_FROM} ➡️ {FLY_TO}"
        send_email_notification(subject, message_text)
    else:
        print("價格均未達通知標準。")

if __name__ == "__main__":
    main()