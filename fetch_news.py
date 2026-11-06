import feedparser
import requests
import json
import re
import os
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Google Apps Script 翻譯 API 網址
GAS_API_URL = "https://script.google.com/macros/s/AKfycbxcjyqA9fKv65j53MGHgi-o28Z--uGuL4EMl6CmPTUb8fIpkEa3AgdxgaNDyxu3TA/exec"

# 1. 傳統 RSS 與 Google News 代理來源
RSS_FEEDS = [
    {"source": "Google News (Coatings)", "url": 'https://news.google.com/rss/search?q="coatings+industry"+OR+"paint+industry"&hl=en-US&gl=US&ceid=US:en'},
    {"source": "Coatings World", "url": "https://www.coatingsworld.com/rss"},
    {"source": "PCI Magazine", "url": "https://news.google.com/rss/search?q=site:pcimag.com&hl=en-US&gl=US&ceid=US:en"},
    {"source": "European Coatings", "url": "https://www.european-coatings.com/rss"},
    {"source": "中外塗料網", "url": "https://news.google.com/rss/search?q=site:27580.cn&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"source": "慧聰塗料網", "url": "https://news.google.com/rss/search?q=site:hzeyun.com&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"source": "中國塗料", "url": "https://news.google.com/rss/search?q=site:chinacoatings.com.cn&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"}
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
}

def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def translate_text(text):
    if not text: return ""
    try:
        response = requests.post(GAS_API_URL, json={"text": text}, timeout=15)
        data = response.json()
        if data.get("success"):
            return data.get("translatedText")
        return text 
    except Exception as e:
        return text

def parse_custom_nippon_paint():
    """客製化解析：日本塗料控股 (只抓研發與產品)"""
    print(f"\n正在客製化抓取: Nippon Paint Holdings")
    news_list = []
    try:
        res = requests.get("https://www.nipponpaint-holdings.com/en/news_release/", headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 尋找所有可能包含新聞的區塊 (啟發式搜尋)
        articles = soup.find_all(['div', 'li', 'tr', 'dl'])
        
        for article in articles:
            text_content = article.get_text(separator=' ', strip=True)
            # 過濾：只抓取研發(Research)與產品(Products)
            if 'Research and Development' in text_content or 'Products' in text_content:
                link_tag = article.find('a')
                if link_tag and link_tag.get('href'):
                    title = link_tag.get_text(strip=True)
                    if not title or len(title) < 10: 
                        continue
                        
                    url = link_tag['href']
                    if url.startswith('/'): url = "https://www.nipponpaint-holdings.com" + url
                    
                    # 嘗試抓取日期 YYYY.MM.DD
                    date_match = re.search(r'20\d{2}\.\d{2}\.\d{2}', text_content)
                    pub_date = date_match.group(0).replace('.', '-') if date_match else datetime.now().strftime("%Y-%m-%d")
                    
                    # 去重複
                    if not any(n['url'] == url for n in news_list):
                        news_list.append({"title": title, "url": url, "pub_date": pub_date})
                        if len(news_list) >= 5: break
    except Exception as e:
        print(f"Nippon Paint 解析失敗: {e}")
    return [{"source": "日本塗料控股", "title": n["title"], "summary": "", "url": n["url"], "publishedAt": n["pub_date"]} for n in news_list]

def parse_custom_specialchem():
    """客製化解析：SpecialChem"""
    print(f"\n正在客製化抓取: SpecialChem")
    news_list = []
    try:
        res = requests.get("https://coatings.specialchem.com/news", headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 尋找新聞區塊
        for item in soup.find_all('div', class_=re.compile(r'news|item|article', re.I)):
            link_tag = item.find('a')
            if link_tag and link_tag.get('href') and 'news' in link_tag['href']:
                title = link_tag.get_text(strip=True)
                if len(title) > 15:
                    url = link_tag['href']
                    if url.startswith('/'): url = "https://coatings.specialchem.com" + url
                    pub_date = datetime.now().strftime("%Y-%m-%d") # SpecialChem 日期格式較複雜，預設為抓取當日
                    
                    if not any(n['url'] == url for n in news_list):
                        news_list.append({"title": title, "url": url, "pub_date": pub_date})
                        if len(news_list) >= 5: break
    except Exception as e:
        print(f"SpecialChem 解析失敗: {e}")
    return [{"source": "SpecialChem", "title": n["title"], "summary": "", "url": n["url"], "publishedAt": n["pub_date"]} for n in news_list]

def parse_custom_coating_media():
    """客製化解析：Coating Media"""
    print(f"\n正在客製化抓取: Coating Media")
    news_list = []
    try:
        res = requests.get("https://www.coatingmedia.com/", headers=headers, timeout=15)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 尋找網頁中的所有連結，利用文字長度和日期特徵過濾
        for link_tag in soup.find_all('a'):
            title = link_tag.get_text(strip=True)
            parent_text = link_tag.parent.get_text(separator=' ', strip=True)
            
            # 尋找 YYYY年MM月DD日 的特徵
            date_match = re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', parent_text)
            
            if date_match and len(title) > 10 and link_tag.get('href'):
                url = link_tag['href']
                if url.startswith('/'): url = "https://www.coatingmedia.com" + url
                
                # 格式化日期
                pub_date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
                
                if not any(n['url'] == url for n in news_list):
                    news_list.append({"title": title, "url": url, "pub_date": pub_date})
                    if len(news_list) >= 5: break
    except Exception as e:
        print(f"Coating Media 解析失敗: {e}")
    return [{"source": "Coating Media", "title": n["title"], "summary": "", "url": n["url"], "publishedAt": n["pub_date"]} for n in news_list]

def main():
    all_news = []
    now = datetime.now()
    
    # --- 1. 處理一般 RSS 來源 ---
    for feed_info in RSS_FEEDS:
        print(f"\n正在抓取來源 (RSS): {feed_info['source']}")
        try:
            res = requests.get(feed_info['url'], headers=headers, timeout=15)
            if res.status_code != 200: continue
            
            feed = feedparser.parse(res.content)
            if not feed.entries: continue
                
            valid_entries = []
            fallback_entries = []
            
            for entry in feed.entries:
                parsed_date = entry.get('published_parsed')
                if parsed_date:
                    dt = datetime.fromtimestamp(time.mktime(parsed_date))
                    age_days = (now - dt).days
                    pub_date_str = dt.strftime("%Y-%m-%d")
                else:
                    age_days = 0
                    pub_date_str = now.strftime("%Y-%m-%d")
                
                if len(fallback_entries) < 5:
                    fallback_entries.append((entry, pub_date_str))
                    
                if age_days <= 30:
                    valid_entries.append((entry, pub_date_str))
                    if len(valid_entries) >= 5: break
            
            if not valid_entries:
                valid_entries = fallback_entries
                    
            for entry, pub_date in valid_entries:
                original_title = entry.get('title', '')
                original_summary = clean_html(entry.get('summary', ''))
                
                zh_title = translate_text(original_title)
                zh_summary = translate_text(original_summary) if original_summary else ""
                
                all_news.append({
                    "source": feed_info['source'],
                    "title": zh_title,
                    "summary": zh_summary,
                    "url": entry.get('link', '#'),
                    "publishedAt": pub_date
                })
                print(f"✅ 已處理: {zh_title}")
                
        except Exception as e:
            print(f"❌ 抓取 {feed_info['source']} 失敗: {e}")

    # --- 2. 處理客製化爬蟲來源 ---
    custom_news_raw = []
    custom_news_raw.extend(parse_custom_nippon_paint())
    custom_news_raw.extend(parse_custom_specialchem())
    custom_news_raw.extend(parse_custom_coating_media())
    
    for item in custom_news_raw:
        # 進行翻譯
        zh_title = translate_text(item['title'])
        all_news.append({
            "source": item['source'],
            "title": zh_title,
            "summary": "", # 客製化爬蟲通常難以穩定抓取摘要，保留空白讓版面維持整潔
            "url": item['url'],
            "publishedAt": item['publishedAt']
        })
        print(f"✅ 已處理 (客製化): {zh_title}")

    # 將結果儲存為 JSON
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(all_news, f, ensure_ascii=False, indent=4)
    print("\n🎉 所有新聞已成功更新並儲存！")

if __name__ == "__main__":
    main()
