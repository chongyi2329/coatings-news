import feedparser
import requests
import json
import re
import os
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import cloudscraper

# 初始化反爬蟲瀏覽器 (取代一般的 requests)
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

# Google Apps Script 翻譯 API 網址
GAS_API_URL = "https://script.google.com/macros/s/AKfycbxcjyqA9fKv65j53MGHgi-o28Z--uGuL4EMl6CmPTUb8fIpkEa3AgdxgaNDyxu3TA/exec"

# 1. 傳統 RSS 與 Google News 代理來源 (強制加上 when:30d)
RSS_FEEDS = [
    {"source": "Google News (Coatings)", "url": 'https://news.google.com/rss/search?q="coatings+industry"+OR+"paint+industry"+when:30d&hl=en-US&gl=US&ceid=US:en'},
    {"source": "Coatings World", "url": "https://www.coatingsworld.com/rss"},
    {"source": "PCI Magazine", "url": "https://news.google.com/rss/search?q=site:pcimag.com+when:30d&hl=en-US&gl=US&ceid=US:en"},
    {"source": "European Coatings", "url": "https://www.european-coatings.com/rss"}
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
        response = scraper.post(GAS_API_URL, json={"text": text}, timeout=15)
        data = response.json()
        if data.get("success"):
            return data.get("translatedText")
        return text 
    except Exception as e:
        return text

def parse_custom_nippon_paint():
    """客製化解析：日本塗料控股 (暴力破解連結法)"""
    print(f"\n正在客製化抓取: Nippon Paint Holdings")
    news_list = []
    try:
        # 使用 cloudscraper 繞過部分限制
        res = scraper.get("https://www.nipponpaint-holdings.com/en/news_release/", timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 尋找所有 <a> 標籤，透過網址特徵抓取
        for link in soup.find_all('a', href=True):
            url = link['href']
            title = link.get_text(strip=True)
            
            # 日本塗料的新聞網址通常包含年份如 /2026/ 或 /news/
            if '/en/news_release/20' in url and len(title) > 15:
                if url.startswith('/'): url = "https://www.nipponpaint-holdings.com" + url
                
                # 從網址或標題推測日期，若無則標記今日
                pub_date = datetime.now().strftime("%Y-%m-%d")
                
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
        # 使用 cloudscraper 對抗 Cloudflare
        res = scraper.get("https://coatings.specialchem.com/news", timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for item in soup.find_all('a', href=True):
            url = item['href']
            if '/news/' in url and item.get_text(strip=True):
                title = item.get_text(strip=True)
                if len(title) > 15:
                    if url.startswith('/'): url = "https://coatings.specialchem.com" + url
                    pub_date = datetime.now().strftime("%Y-%m-%d")
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
        res = scraper.get("https://www.coatingmedia.com/", timeout=15)
        res.encoding = res.apparent_encoding # 自動偵測日文編碼
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for link_tag in soup.find_all('a', href=True):
            title = link_tag.get_text(strip=True)
            parent_text = link_tag.parent.get_text(separator=' ', strip=True)
            
            # 放寬日期特徵比對 (支援 2026/10/05 或 2026年10月5日)
            date_match = re.search(r'(20\d{2})[年/](\d{1,2})[月/](\d{1,2})', parent_text)
            
            if date_match and len(title) > 10:
                url = link_tag['href']
                if url.startswith('/'): url = "https://www.coatingmedia.com" + url
                pub_date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
                
                # 嚴格審查 30 天
                dt = datetime.strptime(pub_date, "%Y-%m-%d")
                if (datetime.now() - dt).days <= 30:
                    if not any(n['url'] == url for n in news_list):
                        news_list.append({"title": title, "url": url, "pub_date": pub_date})
                        if len(news_list) >= 5: break
    except Exception as e:
        print(f"Coating Media 解析失敗: {e}")
    return [{"source": "Coating Media", "title": n["title"], "summary": "", "url": n["url"], "publishedAt": n["pub_date"]} for n in news_list]

def parse_chinese_sites():
    """客製化解析：中國塗料網"""
    print(f"\n正在客製化抓取: 中外塗料網")
    news_list = []
    try:
        res = scraper.get("http://www.27580.cn/important", timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for link in soup.find_all('a', href=True):
            title = link.get_text(strip=True)
            if len(title) > 12 and ('news' in link['href'] or 'article' in link['href']):
                url = link['href']
                if url.startswith('/'): url = "http://www.27580.cn" + url
                pub_date = datetime.now().strftime("%Y-%m-%d")
                if not any(n['url'] == url for n in news_list):
                    news_list.append({"title": title, "url": url, "pub_date": pub_date})
                    if len(news_list) >= 3: break
    except Exception as e:
        print(f"中外塗料網 解析失敗: {e}")
    return [{"source": "中外塗料網", "title": n["title"], "summary": "", "url": n["url"], "publishedAt": n["pub_date"]} for n in news_list]

def main():
    all_news = []
    now = datetime.now()
    
    # --- 1. 處理一般 RSS 來源 ---
    for feed_info in RSS_FEEDS:
        print(f"\n正在抓取來源 (RSS): {feed_info['source']}")
        try:
            res = scraper.get(feed_info['url'], timeout=15)
            if res.status_code != 200: continue
            
            feed = feedparser.parse(res.content)
            if not feed.entries: continue
                
            valid_entries = []
            
            for entry in feed.entries:
                parsed_date = entry.get('published_parsed')
                if parsed_date:
                    dt = datetime.fromtimestamp(time.mktime(parsed_date))
                    age_days = (now - dt).days
                    pub_date_str = dt.strftime("%Y-%m-%d")
                else:
                    age_days = 0 # 無法解析時間視為最新
                    pub_date_str = now.strftime("%Y-%m-%d")
                
                # 嚴格執行 30 天規定 (移除備胎機制)
                if age_days <= 30:
                    valid_entries.append((entry, pub_date_str))
                    if len(valid_entries) >= 5: break
                    
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
    custom_news_raw.extend(parse_chinese_sites())
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
