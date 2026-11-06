import feedparser
import requests
import json
import re
import time
from datetime import datetime, timedelta
import cloudscraper

# 初始化反爬蟲瀏覽器
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

# Google Apps Script 翻譯 API 網址
GAS_API_URL = "https://script.google.com/macros/s/AKfycbxcjyqA9fKv65j53MGHgi-o28Z--uGuL4EMl6CmPTUb8fIpkEa3AgdxgaNDyxu3TA/exec"

# 替換 Coatings World 為 Google 代理版本
RSS_FEEDS = [
    {"source": "Google News (Coatings)", "url": 'https://news.google.com/rss/search?q="coatings+industry"+OR+"paint+industry"+when:30d&hl=en-US&gl=US&ceid=US:en'},
    {"source": "Coatings World", "url": "https://news.google.com/rss/search?q=site:coatingsworld.com+when:30d&hl=en-US&gl=US&ceid=US:en"},
    {"source": "PCI Magazine", "url": "https://news.google.com/rss/search?q=site:pcimag.com+when:30d&hl=en-US&gl=US&ceid=US:en"},
    {"source": "European Coatings", "url": "https://www.european-coatings.com/rss"}
]

def clean_html(raw_html):
    """清除 HTML 標籤，只保留純文字摘要"""
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def translate_text(text):
    """呼叫 GAS API 翻譯文字"""
    if not text: return ""
    try:
        response = scraper.post(GAS_API_URL, json={"text": text}, timeout=15)
        data = response.json()
        if data.get("success"):
            return data.get("translatedText")
        return text 
    except Exception as e:
        return text

def main():
    all_news = []
    now = datetime.now()
    
    for feed_info in RSS_FEEDS:
        print(f"\n正在抓取來源: {feed_info['source']}")
        try:
            res = scraper.get(feed_info['url'], timeout=15)
            if res.status_code != 200: 
                print(f"❌ 網頁回傳狀態碼錯誤: {res.status_code}")
                continue
            
            feed = feedparser.parse(res.content)
            if not feed.entries: 
                print("❌ 找不到任何新聞條目")
                continue
                
            valid_count = 0
            
            for entry in feed.entries:
                # 如果已經抓滿 5 篇合格的，就跳出迴圈
                if valid_count >= 5:
                    break

                # 處理發布時間
                parsed_date = entry.get('published_parsed')
                if parsed_date:
                    dt = datetime.fromtimestamp(time.mktime(parsed_date))
                    
                    # 【嚴格海關審查】檢查是否超過 30 天
                    if now - dt > timedelta(days=30):
                        print(f"⚠️ 跳過過期文章: {entry.get('title', '')}")
                        continue
                        
                    pub_date_str = dt.strftime("%Y-%m-%d")
                else:
                    # 如果沒有時間標籤，視為當天
                    pub_date_str = now.strftime("%Y-%m-%d")
                
                # 提取標題與摘要
                original_title = entry.get('title', '')
                original_summary = clean_html(entry.get('summary', ''))
                
                # 執行翻譯
                zh_title = translate_text(original_title)
                zh_summary = translate_text(original_summary) if original_summary else ""
                
                # 存入清單
                all_news.append({
                    "source": feed_info['source'],
                    "title": zh_title,
                    "summary": zh_summary,
                    "url": entry.get('link', '#'),
                    "publishedAt": pub_date_str
                })
                print(f"✅ 已處理: {zh_title}")
                valid_count += 1
                
        except Exception as e:
            print(f"❌ 抓取 {feed_info['source']} 失敗: {e}")

    # 將結果儲存為 JSON
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(all_news, f, ensure_ascii=False, indent=4)
    print("\n🎉 所有新聞已成功更新並儲存！")

if __name__ == "__main__":
    main()
