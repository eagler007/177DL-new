#自动识别分页栏最大数字作为end_page，无需手动输入。
#只需设置base_url为你的漫画首页地址。
#支持断点续传。
#自动创建保存目录。save_dir默认d:根目录下

import os
import requests
from bs4 import BeautifulSoup
from lxml import etree
import re

# ====== 配置 ======
base_url = 'http://www.177pica.com/html/2025/05/6870528.html'  # 替换为你的漫画首页链接
start_page = 1
headers = {
    'user-agent': 'Mozilla/5.0'
}

# 获取首页
resp = requests.get(base_url, headers=headers, timeout=15)
resp.raise_for_status()
soup = BeautifulSoup(resp.text, 'html.parser')

# 获取 entry-title 作为目录名
title_tag = soup.find('h1', class_='entry-title')
if title_tag and title_tag.get_text(strip=True):
    comic_title = title_tag.get_text(strip=True)
else:
    comic_title = soup.title.string.strip() if soup.title else 'Comic'

# 清理非法字符
for ch in '\\/:*?"<>|':
    comic_title = comic_title.replace(ch, '_')

save_dir = os.path.join('d:\\', comic_title, 'images')
os.makedirs(save_dir, exist_ok=True)

# 自动获取end_page
pagination = soup.find('div', class_='page-links')
end_page = 1
if pagination:
    page_links = pagination.find_all('a')
    page_numbers = [int(a.get_text()) for a in page_links if a.get_text().isdigit()]
    if page_numbers:
        end_page = max(page_numbers)
else:
    # 后备，正则页面内所有 /数字" 或 /数字/ 或 /数字> 结构
    numbers = re.findall(r'/(\d+)[/">]', resp.text)
    if numbers:
        end_page = max([int(n) for n in numbers])

print(f"开始爬取：《{comic_title}》，共 {end_page} 页，保存到 {save_dir}")

img_count = 1
for page in range(start_page, end_page + 1):
    if page == 1:
        pageurl = base_url
    else:
        pageurl = f'{base_url}/{page}'
    print(f'抓取第{page}页: {pageurl}')

    try:
        resp = requests.get(pageurl, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"第{page}页请求失败：{e}")
        continue

    html = resp.text
    ele = etree.HTML(html)
    # 优先data-lazy-src，再用src
    img_urls = ele.xpath("//div[@class='single-content']//img/@data-lazy-src")
    if not img_urls:
        img_urls = ele.xpath("//div[@class='single-content']//img/@src")
    if not img_urls:
        print(f"第{page}页未找到图片。")
        continue

    for img_url in img_urls:
        # 补全图片链接
        if img_url.startswith('//'):
            img_url = 'http:' + img_url
        elif img_url.startswith('/'):
            img_url = 'http://www.177pica.com' + img_url
        elif not img_url.startswith('http'):
            img_url = 'http://' + img_url

        img_name = f"{img_count:03d}.jpg"
        img_path = os.path.join(save_dir, img_name)
        # 断点续传：如果图片已经存在则跳过
        if os.path.exists(img_path):
            print(f"{img_name} 已存在，跳过。")
            img_count += 1
            continue

        try:
            print(f"下载 {img_name} : {img_url}")
            img_resp = requests.get(img_url, headers=headers, timeout=15)
            img_resp.raise_for_status()
            with open(img_path, 'wb') as f:
                f.write(img_resp.content)
            img_count += 1
        except Exception as e:
            print(f"图片下载失败: {img_url}，原因：{e}")

print("全部图片下载完成，保存在：", save_dir)

