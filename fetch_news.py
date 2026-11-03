import feedparser
import requests
import json
import re
import os
from datetime import datetime

# 你的 Google Apps Script 翻譯 API 網址
GAS_API_URL = "https://script.google.com/macros/s/AKfycbxcjyqA9fKv65j53MGHgi-o28Z--uGuL4EMl6CmPTUb8fIpkEa3AgdxgaNDyxu3TA/exec"

# 我們要抓取的 RSS 來源清單
RSS_FEEDS = [
    {
        "source": "Google News (Coatings)",
        "url": 'https://news.google.com/rss/search?q="coatings+industry"+OR+"paint+industry"&hl=en-US&gl=US&ceid=US:en'
    },
    {
        "source": "Coatings World",
        "url": "https://www.coatingsworld.com/rss"
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
    
    for feed_info in RSS_FEEDS:
        print(f"正在抓取來源: {feed_info['source']}")
        feed = feedparser.parse(feed_info['url'])
        
        # 每個來源我們只取前 5 篇最新文章，避免 API 翻譯時間過長
        for entry in feed.entries[:5]:
            original_title = entry.title
            original_summary = clean_html(entry.get('summary', ''))
            
            # 為了節省 API 呼叫次數，我們把標題和摘要合併成一段一起翻譯，中間用特殊符號隔開
            combined_text = f"{original_title} ||| {original_summary}"
            translated_combined = translate_text(combined_text)
            
            # 拆解回標題與摘要
            parts = translated_combined.split("|||")
            zh_title = parts[0].strip() if len(parts) > 0 else original_title
            zh_summary = parts[1].strip() if len(parts) > 1 else original_summary
            
            # 處理發布時間
            pub_date = entry.get('published', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            news_item = {
                "source": feed_info['source'],
                "title": zh_title,
                "summary": zh_summary,
                "url": entry.link,
                "publishedAt": pub_date
            }
            all_news.append(news_item)
            print(f"已處理: {zh_title}")

    # 將結果儲存為 JSON 檔案
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(all_news, f, ensure_ascii=False, indent=4)
    print("✅ 所有新聞已成功更新並儲存至 news.json")

if __name__ == "__main__":
    main()
