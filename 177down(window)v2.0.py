import os
import requests
from bs4 import BeautifulSoup
from lxml import etree
import re
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox, filedialog, scrolledtext

def log(message, widget=None):
    print(message)
    if widget:
        widget.configure(state='normal')
        widget.insert(tk.END, message + "\n")
        widget.see(tk.END)
        widget.update()
        widget.configure(state='disabled')

def comic_downloader(url, save_to, log_widget=None, failed_imgs=None):
    headers = {'user-agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        log(f"首页请求失败：{e}", log_widget)
        if failed_imgs is not None:
            failed_imgs.append({
                "comic_title": url,
                "page": "首页",
                "img_url": url,
                "img_path": "",
                "err": str(e)
            })
        return

    soup = BeautifulSoup(resp.text, 'html.parser')
    title_tag = soup.find('h1', class_='entry-title')
    if title_tag and title_tag.get_text(strip=True):
        comic_title = title_tag.get_text(strip=True)
    else:
        comic_title = soup.title.string.strip() if soup.title else 'Comic'
    for ch in '\\/:*?"<>|':
        comic_title = comic_title.replace(ch, '_')

    save_dir = os.path.join(save_to, comic_title, 'images')
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
        numbers = re.findall(r'/(\d+)[/">]', resp.text)
        if numbers:
            end_page = max([int(n) for n in numbers])

    log(f"开始爬取：《{comic_title}》，共 {end_page} 页，保存到 {save_dir}", log_widget)

    img_count = 1
    for page in range(1, end_page + 1):
        if page == 1:
            pageurl = url
        else:
            pageurl = f'{url}/{page}'
        log(f'抓取第{page}页: {pageurl}', log_widget)
        try:
            resp = requests.get(pageurl, headers=headers, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            log(f"第{page}页请求失败：{e}", log_widget)
            if failed_imgs is not None:
                failed_imgs.append({
                    "comic_title": comic_title,
                    "page": page,
                    "img_url": pageurl,
                    "img_path": "",
                    "err": str(e)
                })
            continue

        html = resp.text
        ele = etree.HTML(html)
        img_urls = ele.xpath("//div[@class='single-content']//img/@data-lazy-src")
        if not img_urls:
            img_urls = ele.xpath("//div[@class='single-content']//img/@src")
        if not img_urls:
            log(f"第{page}页未找到图片。", log_widget)
            if failed_imgs is not None:
                failed_imgs.append({
                    "comic_title": comic_title,
                    "page": page,
                    "img_url": pageurl,
                    "img_path": "",
                    "err": "未找到图片"
                })
            continue

        for img_url in img_urls:
            original_img_url = img_url
            # 拼接完整URL
            if img_url.startswith('//'):
                img_url = 'http:' + img_url
            elif img_url.startswith('/'):
                img_url = 'http://www.177pica.com' + img_url
            elif not img_url.startswith('http'):
                img_url = 'http://' + img_url

            img_name = f"{img_count:03d}.jpg"
            img_path = os.path.join(save_dir, img_name)
            if os.path.exists(img_path):
                log(f"{img_name} 已存在，跳过。", log_widget)
                img_count += 1
                continue

            try:
                log(f"下载 {img_name} : {img_url}", log_widget)
                img_resp = requests.get(img_url, headers=headers, timeout=15)
                img_resp.raise_for_status()
                with open(img_path, 'wb') as f:
                    f.write(img_resp.content)
                img_count += 1
            except Exception as e:
                log(f"图片下载失败: {img_url}，原因：{e}", log_widget)
                if failed_imgs is not None:
                    failed_imgs.append({
                        "comic_title": comic_title,
                        "page": page,
                        "img_url": original_img_url,
                        "img_path": img_path,
                        "err": str(e)
                    })

def retry_failed_imgs(failed_imgs, log_widget=None):
    if not failed_imgs:
        return []
    log("==== 开始尝试重下失败图片 ====", log_widget)
    still_failed = []
    headers = {'user-agent': 'Mozilla/5.0'}
    for item in failed_imgs:
        img_url = item["img_url"]
        img_path = item["img_path"]
        # 拼接完整URL
        if img_url.startswith('//'):
            img_url_full = 'http:' + img_url
        elif img_url.startswith('/'):
            img_url_full = 'http://www.177pica.com' + img_url
        elif not img_url.startswith('http'):
            img_url_full = 'http://' + img_url
        else:
            img_url_full = img_url
        # 页面请求失败和找不到图片没有img_path，跳过
        if not img_path:
            still_failed.append(item)
            continue
        try:
            log(f"重试下载：{img_url_full}", log_widget)
            resp = requests.get(img_url_full, headers=headers, timeout=15)
            resp.raise_for_status()
            with open(img_path, 'wb') as f:
                f.write(resp.content)
        except Exception as e:
            log(f"重试失败：{img_url_full}，原因：{e}", log_widget)
            item["err"] = str(e)
            still_failed.append(item)
    log(f"重试完成，剩余失败数量：{len(still_failed)}", log_widget)
    return still_failed

def choose_dir(entry):
    path = filedialog.askdirectory(title='选择保存目录')
    if path:
        entry.delete(0, tk.END)
        entry.insert(0, path)

def import_urls_from_file(url_box):
    filepath = filedialog.askopenfilename(title='选择包含URL的文本文件',
                                          filetypes=[('Text Files', '*.txt'), ('All Files', '*')])
    if filepath:
        with open(filepath, encoding='utf-8') as f:
            urls = f.read()
        url_box.delete('1.0', tk.END)
        url_box.insert(tk.END, urls)

def start_download(url_box, path_entry, log_box):
    urls = url_box.get('1.0', tk.END).strip().splitlines()
    urls = [u.strip() for u in urls if u.strip()]
    save_to = path_entry.get().strip()
    if not urls or not save_to:
        messagebox.showerror("错误", "请填写完整URL和保存目录！")
        return
    log_box.configure(state='normal')
    log_box.delete(1.0, tk.END)
    log_box.configure(state='disabled')
    def run_all():
        all_failed_imgs = []
        for i, url in enumerate(urls, 1):
            log(f"\n===== 开始下载第{i}个漫画: {url} =====", log_box)
            comic_downloader(url, save_to, log_box, all_failed_imgs)
        # 一次失败后重试
        if all_failed_imgs:
            log(f"\n以下图片初次下载失败，开始尝试重试...\n", log_box)
            still_failed = retry_failed_imgs(all_failed_imgs, log_box)
        else:
            still_failed = []
        # 剩余失败写入txt
        if still_failed:
            txt_path = os.path.join(save_to, "download_failed.txt")
            with open(txt_path, 'w', encoding='utf-8') as f:
                for item in still_failed:
                    f.write(f"{item['comic_title']}\t第{item['page']}页\t{item['img_url']}\t{item['img_path']}\t{item.get('err','')}\n")
            log(f"有{len(still_failed)}个图片下载失败，详情见 {txt_path}", log_box)
            messagebox.showwarning("下载完成", f"有{len(still_failed)}个图片下载失败，详情见 {txt_path}")
        else:
            log("全部任务完成，无下载失败图片！", log_box)
            messagebox.showinfo("完成", "全部任务完成，无下载失败图片！")
    root.after(100, run_all)

# ------ GUI 部分 ------
root = tk.Tk()
root.title("漫画下载器")

frame = ttk.Frame(root, padding=12)
frame.grid(row=0, column=0, sticky='nsew')

ttk.Label(frame, text="漫画首页URL(支持多行):").grid(row=0, column=0, sticky='e')
url_box = scrolledtext.ScrolledText(frame, height=5, width=60)
url_box.grid(row=0, column=1, sticky='we', pady=4)

url_file_btn = ttk.Button(frame, text="选择文件", command=lambda: import_urls_from_file(url_box))
url_file_btn.grid(row=0, column=2, sticky='w', padx=4)

ttk.Label(frame, text="保存目录:").grid(row=1, column=0, sticky='e')
path_entry = ttk.Entry(frame, width=45)
path_entry.grid(row=1, column=1, sticky='w', pady=4)
browse_btn = ttk.Button(frame, text="浏览", command=lambda: choose_dir(path_entry))
browse_btn.grid(row=1, column=2, sticky='w', padx=4)

download_btn = ttk.Button(frame, text="开始下载", command=lambda: start_download(url_box, path_entry, log_box))
download_btn.grid(row=2, column=1, pady=8)

log_box = scrolledtext.ScrolledText(frame, height=16, width=75, state='disabled')
log_box.grid(row=3, column=0, columnspan=3, pady=8)

# 窗口尺寸自适应
frame.columnconfigure(1, weight=1)
root.geometry("700x400")
root.mainloop()
