import os
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from lxml import etree

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def log(log_box, msg):
    log_box.config(state='normal')
    log_box.insert(tk.END, msg+'\n')
    log_box.see(tk.END)
    log_box.config(state='disabled')
    log_box.update()

def sanitize_filename(name):
    return re.sub(r'[\\/:*?"<>|]', '_', name)

def get_html(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.encoding = resp.apparent_encoding
        return resp.text
    except Exception as e:
        return ''

def get_total_pages(html):
    soup = BeautifulSoup(html, "lxml")
    page_links = soup.select('a.page-numbers')
    max_page = 1
    for link in page_links:
        href = link.get('href', '')
        m = re.search(r'/page/(\d+)/', href)
        if m:
            p = int(m.group(1))
            if p > max_page:
                max_page = p
    return max_page

def get_entries_from_page(html):
    soup = BeautifulSoup(html, "lxml")
    entries = []
    for h2 in soup.select("h2.grid-title"):
        a = h2.find('a')
        if a and a.get('href'):
            name = a.get_text(strip=True)
            url = a['href']
            entries.append((url, name))
    return entries

def get_entry_detail(entry_url):
    html = get_html(entry_url)
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find(class_="entry-title")
    title = sanitize_filename(title_tag.get_text(strip=True)) if title_tag else "UnknownEntry"
    # 自动识别分页最大数字
    pagination = soup.find('div', class_='page-links')
    end_page = 1
    if pagination:
        page_links = pagination.find_all('a')
        page_numbers = [int(a.get_text()) for a in page_links if a.get_text().isdigit()]
        if page_numbers:
            end_page = max(page_numbers)
    else:
        numbers = re.findall(r'/(\d+)[/">]', html)
        if numbers:
            end_page = max([int(n) for n in numbers])
    image_urls = get_image_urls_from_page(html)
    return title, end_page, image_urls

def get_image_urls_from_page(html):
    ele = etree.HTML(html)
    img_urls = ele.xpath("//div[@class='single-content']//img/@data-lazy-src")
    if not img_urls:
        img_urls = ele.xpath("//div[@class='single-content']//img/@src")
    return img_urls

def complete_img_url(img_url):
    if img_url.startswith('//'):
        img_url = 'http:' + img_url
    elif img_url.startswith('/'):
        img_url = 'http://www.177pica.com' + img_url
    elif not img_url.startswith('http'):
        img_url = 'http://' + img_url
    return img_url

def download_image(img_url, save_path, log_box):
    if os.path.exists(save_path):
        log(log_box, f"{os.path.basename(save_path)} 已存在，跳过。")
        return
    try:
        resp = requests.get(img_url, headers=HEADERS, stream=True, timeout=16)
        resp.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(1024):
                f.write(chunk)
        log(log_box, f"下载 {os.path.basename(save_path)} : {img_url}")
    except Exception as e:
        log(log_box, f"图片下载失败: {img_url}，原因：{e}")

def process_entry(entry_url, entry_name, base_save_dir, log_box):
    title, end_page, first_page_imgs = get_entry_detail(entry_url)
    save_dir = os.path.join(base_save_dir, title, 'images')
    os.makedirs(save_dir, exist_ok=True)

    # 统计目标图片数量
    target_imgs = len(first_page_imgs)
    page_imgs_list = []
    for page in range(2, end_page + 1):
        page_url = f"{entry_url}/{page}"
        html = get_html(page_url)
        imgs = get_image_urls_from_page(html)
        page_imgs_list.append(imgs)
        target_imgs += len(imgs)

    # 检查已下载图片数量
    existing_imgs = [f for f in os.listdir(save_dir) if f.lower().endswith(('.jpg','.jpeg','.png','.gif','.bmp','.webp'))]
    
    if len(existing_imgs) >= target_imgs and target_imgs > 0:
        log(log_box, f"【已完成】{title}（共{target_imgs}张），跳过下载。")
        return

    log(log_box, f"【开始】{title} 共{end_page}页，需下载{target_imgs}张，保存到 {save_dir}")
    idx = 1
    # 下载第一页的图片
    for img_url in first_page_imgs:
        img_url = complete_img_url(img_url)
        ext = os.path.splitext(urlparse(img_url).path)[-1]
        if not ext or len(ext) > 5:
            ext = ".jpg"
        save_path = os.path.join(save_dir, f"{idx:03d}{ext}")
        download_image(img_url, save_path, log_box)
        idx += 1
    # 下载剩余页图片
    for imgs in page_imgs_list:
        for img_url in imgs:
            img_url = complete_img_url(img_url)
            ext = os.path.splitext(urlparse(img_url).path)[-1]
            if not ext or len(ext) > 5:
                ext = ".jpg"
            save_path = os.path.join(save_dir, f"{idx:03d}{ext}")
            download_image(img_url, save_path, log_box)
            idx += 1
    log(log_box, f"【完成】{title} ：共{idx-1}张图片，已保存在 {save_dir}")

def choose_dir(path_entry):
    path = filedialog.askdirectory()
    if path:
        path_entry.delete(0, tk.END)
        path_entry.insert(0, path)

def start_download(url_entry, path_entry, log_box):
    url = url_entry.get().strip()
    save_dir = path_entry.get().strip()
    if not url or not save_dir:
        messagebox.showerror("错误", "请填写漫画分类首页URL和保存目录！")
        return
    log_box.config(state='normal')
    log_box.delete(1.0, tk.END)
    log_box.config(state='disabled')
    threading.Thread(target=download_main, args=(url, save_dir, log_box), daemon=True).start()

def download_main(base_url, save_dir, log_box):
    log(log_box, f"开始解析分类首页：{base_url}")
    html = get_html(base_url)
    if not html:
        log(log_box, "无法获取首页HTML，请检查网络或URL。")
        return
    total_pages = get_total_pages(html)
    log(log_box, f"发现分类总页数：{total_pages}")
    # 逐页提取条目
    all_entries = []
    for i in range(1, total_pages + 1):
        page_url = base_url if i == 1 else urljoin(base_url, f"page/{i}/")
        log(log_box, f"正在解析 {page_url}")
        page_html = get_html(page_url)
        entries = get_entries_from_page(page_html)
        log(log_box, f"第{i}页提取到{len(entries)}个条目")
        all_entries.extend(entries)
    log(log_box, f"总共提取到{len(all_entries)}个条目")
    # 下载每个条目图片
    for entry_url, entry_name in all_entries:
        log(log_box, f"\n开始处理：{entry_name} - {entry_url}")
        try:
            process_entry(entry_url, entry_name, save_dir, log_box)
        except Exception as e:
            log(log_box, f"处理失败：{entry_name}，原因：{e}")

# ------ GUI 部分 ------
root = tk.Tk()
root.title("漫画下载器")

frame = ttk.Frame(root, padding=12)
frame.grid(row=0, column=0, sticky='nsew')

ttk.Label(frame, text="漫画分类首页URL:").grid(row=0, column=0, sticky='e')
url_entry = ttk.Entry(frame, width=60)
url_entry.grid(row=0, column=1, sticky='we', pady=4)

ttk.Label(frame, text="保存目录:").grid(row=1, column=0, sticky='e')
path_entry = ttk.Entry(frame, width=45)
path_entry.grid(row=1, column=1, sticky='w', pady=4)
browse_btn = ttk.Button(frame, text="浏览", command=lambda: choose_dir(path_entry))
browse_btn.grid(row=1, column=2, sticky='w', padx=4)

download_btn = ttk.Button(frame, text="开始下载", command=lambda: start_download(url_entry, path_entry, log_box))
download_btn.grid(row=2, column=1, pady=8)

log_box = scrolledtext.ScrolledText(frame, height=16, width=75, state='disabled')
log_box.grid(row=3, column=0, columnspan=3, pady=8)

frame.columnconfigure(1, weight=1)
root.geometry("650x450")
root.mainloop()
