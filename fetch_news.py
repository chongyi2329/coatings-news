import feedparser
import requests
import json
import re
import os
import time
from datetime import datetime, timedelta

# 你的 Google Apps Script 翻譯 API 網址
GAS_API_URL = "https://script.google.com/macros/s/AKfycbxcjyqA9fKv65j53MGHgi-o28Z--uGuL4EMl6CmPTUb8fIpkEa3AgdxgaNDyxu3TA/exec"

# 我們要抓取的 RSS 來源清單 (保留舊有來源，並透過 Google News 代理新增亞洲與全球媒體)
RSS_FEEDS = [
    # ---- 原有來源 (歐美) ----
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
        "url": "https://news.google.com/rss/search?q=site:pcimag.com&hl=en-US&gl=US&ceid=US:en"
    },
    {
        "source": "European Coatings",
        "url": "https://www.european-coatings.com/rss"
    },
    
    # ---- 新增來源 (中國) ----
    {
        "source": "中外塗料網",
        "url": "https://news.google.com/rss/search?q=site:27580.cn&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    },
    {
        "source": "慧聰塗料網",
        "url": "https://news.google.com/rss/search?q=site:hzeyun.com&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    },
    {
        "source": "中國塗料",
        "url": "https://news.google.com/rss/search?q=site:chinacoatings.com.cn&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    },

    # ---- 新增來源 (日本) ----
    {
        "source": "塗料報知",
        "url": "https://news.google.com/rss/search?q=site:e-toryo.co.jp&hl=ja&gl=JP&ceid=JP:ja"
    },
    {
        "source": "Coating Media",
        "url": "https://news.google.com/rss/search?q=site:coatingmedia.com&hl=ja&gl=JP&ceid=JP:ja"
    },
    {
        "source": "日本塗料控股",
        "url": "https://news.google.com/rss/search?q=site:nipponpaint-holdings.com&hl=ja&gl=JP&ceid=JP:ja"
    },

    # ---- 新增來源 (全球材料) ----
    {
        "source": "SpecialChem",
        "url": "https://news.google.com/rss/search?q=site:specialchem.com+coatings&hl=en-US&gl=US&ceid=US:en"
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
                
            # 篩選出符合時間條件（30天內）的文章，最多取 5 篇
            valid_entries = []
            fallback_entries = [] # 備胎：無條件存放最新的 5 篇
            now = datetime.now()
            
            for entry in feed.entries:
                parsed_date = entry.get('published_parsed')
                if parsed_date:
                    # 將時間轉為 datetime 物件進行計算
                    dt = datetime.fromtimestamp(time.mktime(parsed_date))
                    age_days = (now - dt).days
                    pub_date_str = dt.strftime("%Y-%m-%d")
                else:
                    # 若無時間資訊，預設為今天
                    age_days = 0
                    pub_date_str = now.strftime("%Y-%m-%d")
                
                # 不管時間多舊，先存進備胎名單（最多存 5 個）
                if len(fallback_entries) < 5:
                    fallback_entries.append((entry, pub_date_str))
                    
                # 檢查是否符合 30 天內的條件
                if age_days <= 30:
                    valid_entries.append((entry, pub_date_str))
                    if len(valid_entries) >= 5:
                        break # 已經湊滿 5 篇近期文章，結束篩選
            
            # 檢查結果：如果連 1 篇近期新聞都沒有，就啟用備胎方案
            if not valid_entries:
                print(f"⚠️ 提示: {feed_info['source']} 沒有 30 天內的新聞，已切換為抓取最新的 {len(fallback_entries)} 篇。")
                valid_entries = fallback_entries
                    
            # 處理這批文章 (翻譯並存入清單)
            for entry, pub_date in valid_entries:
                original_title = entry.get('title', '')
                original_summary = clean_html(entry.get('summary', ''))
                
                # 合併翻譯
                combined_text = f"{original_title} ||| {original_summary}"
                translated_combined = translate_text(combined_text)
                
                # 拆解
                parts = translated_combined.split("|||")
                zh_title = parts[0].strip() if len(parts) > 0 else original_title
                zh_summary = parts[1].strip() if len(parts) > 1 else original_summary
                
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
