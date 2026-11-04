import feedparser
import requests
import json
import re
import os
from datetime import datetime

# 你的 Google Apps Script 翻譯 API 網址
GAS_API_URL = "https://script.google.com/macros/s/AKfycbxcjyqA9fKv65j53MGHgi-o28Z--uGuL4EMl6CmPTUb8fIpkEa3AgdxgaNDyxu3TA/exec"

# 我們要抓取的 RSS 來源清單 (新增 PCI Magazine 與 European Coatings)
RSS_FEEDS = [
    {
        "source": "Google News (Coatings)",
        "url": 'https://news.google.com/rss/search?q="coatings+industry"+OR+"paint+industry"&hl=en-US&gl=US&ceid=US:en'
    },
    {
        "source": "Coatings World",
        "url": "https://www.coatingsworld.com/rss"
    },
    {
        "source": "PCI Magazine",
        "url": "https://www.pcimag.com/rss/articles"
    },
    {
        "source": "European Coatings",
        "url": "https://www.european-coatings.com/rss"
    }
]

def clean_html(raw_html):
    """清除摘要中不必要的 HTML 標籤"""
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def translate_text(text):
    """呼叫你的 GAS API 進行翻譯"""
    if not text:
        return ""
    try:
        response = requests.post(GAS_API_URL, json={"text": text}, timeout=10)
        data = response.json()
        if data.get("success"):
            return data.get("translatedText")
        else:
            print(f"翻譯失敗: {data.get('error')}")
            return text # 失敗則回傳原文
    except Exception as e:
        print(f"API 請求錯誤: {e}")
        return text

def main():
    all_news = []
    
    # 建立一個更完整的偽裝 Header，模擬真實瀏覽器的所有行為特徵
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
        "Referer": "https://www.google.com/"
    }
    
    for feed_info in RSS_FEEDS:
        print(f"\n正在抓取來源: {feed_info['source']}")
        try:
            # 先用 requests 帶上偽裝標頭去抓取網頁內容
            res = requests.get(feed_info['url'], headers=headers, timeout=15)
            
            # 檢查是否被伺服器阻擋 (例如 403 Forbidden 錯誤)
            if res.status_code != 200:
                print(f"⚠️ 伺服器拒絕連線: {feed_info['source']} 回傳狀態碼 {res.status_code}，可能被高級防火牆阻擋。")
                continue
            
            # 將抓下來的內容交給 feedparser 解析
            feed = feedparser.parse(res.content)
            
            # 如果抓不到資料 (可能網址失效或阻擋)，印出警告並跳過
            if not feed.entries:
                print(f"⚠️ 警告: 從 {feed_info['source']} 抓不到任何文章，跳過此來源。")
                continue
                
            # 每個來源我們取前 5 篇最新文章
            for entry in feed.entries[:5]:
                original_title = entry.get('title', '')
                original_summary = clean_html(entry.get('summary', ''))
                
                # 合併翻譯
                combined_text = f"{original_title} ||| {original_summary}"
                translated_combined = translate_text(combined_text)
                
                # 拆解
                parts = translated_combined.split("|||")
                zh_title = parts[0].strip() if len(parts) > 0 else original_title
                zh_summary = parts[1].strip() if len(parts) > 1 else original_summary
                
                # 處理時間
                pub_date = entry.get('published', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                
                news_item = {
                    "source": feed_info['source'],
                    "title": zh_title,
                    "summary": zh_summary,
                    "url": entry.get('link', '#'),
                    "publishedAt": pub_date
                }
                all_news.append(news_item)
                print(f"✅ 已處理: {zh_title}")
                
        except Exception as e:
            print(f"❌ 抓取 {feed_info['source']} 時發生錯誤: {e}")

    # 將結果儲存為 JSON 檔案
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(all_news, f, ensure_ascii=False, indent=4)
    print("\n🎉 所有新聞已成功更新並儲存至 news.json")

if __name__ == "__main__":
    main()
