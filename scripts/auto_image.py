#!/usr/bin/env python3
"""Auto-image: 从 Pexels 搜索免费图片，插入文章，推送到微信草稿箱。"""
import sys, os, re, argparse, subprocess, shutil, requests, tempfile, yaml

SKILL_DIR = r'C:\Users\许俊昌\.openclaw\workspace\skills\wewrite'

def load_config():
    config_path = os.path.join(SKILL_DIR, 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path, encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}

CONFIG = load_config()
PEXELS_API_KEY = CONFIG.get('pexels', {}).get('api_key', '')

KEYWORD_MAP = {
    "AI": "artificial intelligence", "人工智能": "artificial intelligence",
    "学习": "learning", "入门": "beginner", "工具": "tools",
    "写作": "writing", "整理": "organize", "信息": "information",
    "提问": "question", "坑": "warning", "工作": "office",
    "流程": "workflow", "未来": "future", "选择": "choice",
    "效率": "productivity", "手机": "smartphone", "电脑": "laptop",
    "对话": "conversation", "科技": "technology", "办公": "office desk",
    "普通人": "person", "新手": "beginner", "用法": "usage",
    "融入": "integrate", "方向": "direction", "定义": "definition",
    "最强": "powerful", "知道": "know", "写东西": "writing",
}

def translate_keyword(kw):
    for cn, en in KEYWORD_MAP.items():
        if cn in kw:
            return en
    parts = re.findall(r'[a-zA-Z]+', kw)
    return ' '.join(parts) if parts else "technology"

def search_pexels(query, per_page=3):
    if not PEXELS_API_KEY:
        print("  ⚠️ Pexels API key 未配置，请在 config.yaml 中设置 pexels.api_key")
        return []
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": per_page, "orientation": "landscape"}
    try:
        resp = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=15)
        data = resp.json()
        return [p["src"]["large"] for p in data.get("photos", [])]
    except:
        return []

def download_image(url, path):
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        with open(path, 'wb') as f:
            f.write(r.content)
        return os.path.getsize(path) > 10000
    except:
        return False

def extract_keywords(content):
    kws = []
    for line in content.split('\n'):
        if line.startswith('## '):
            t = line.lstrip('# ').strip()
            en = translate_keyword(t)
            kws.append((t, en))
    return kws

def insert_images(content, paths):
    lines = content.split('\n')
    h2s = [i for i, l in enumerate(lines) if l.startswith('## ')]
    offset = 0
    for idx, (h2, img) in enumerate(zip(h2s[:len(paths)], paths)):
        pos = h2 + 1
        while pos < len(lines) and lines[pos].strip() and not lines[pos].startswith('## '):
            pos += 1
        lines.insert(pos + offset, f"\n![配图{idx+1}]({img})\n")
        offset += 1
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('-t', '--theme', default='sspai')
    parser.add_argument('--author', default='肉松')
    parser.add_argument('--no-publish', action='store_true')
    args = parser.parse_args()

    with open(args.input, encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, count=1, flags=re.DOTALL)

    title = ''
    for line in content.split('\n'):
        if line.startswith('# '):
            title = line.strip().lstrip('# ').strip()
            break

    kw_pairs = extract_keywords(content)
    print(f"文章: {title}")
    for cn, en in kw_pairs[:4]:
        print(f"  {cn} → {en}")

    img_dir = tempfile.mkdtemp(prefix='wewrite_img_')
    paths = []
    for cn, en in kw_pairs[:4]:
        print(f"  搜索: {en}...", end=" ", flush=True)
        urls = search_pexels(en)
        if urls:
            p = os.path.join(img_dir, f'img_{len(paths)+1}.jpg')
            if download_image(urls[0], p):
                paths.append(p)
                print("✅")
            else:
                print("❌")
        else:
            print("❌")

    if not paths:
        print("没有找到图片")
        shutil.rmtree(img_dir, ignore_errors=True)
        return

    print(f"\n共 {len(paths)} 张图片")
    enhanced = insert_images(content, paths)
    enhanced_path = os.path.join(img_dir, 'enhanced.md')
    with open(enhanced_path, 'w', encoding='utf-8') as f:
        f.write(enhanced)

    if args.no_publish:
        print(f"图片: {img_dir}")
        return

    print("推送草稿箱...")
    cli = os.path.join(SKILL_DIR, 'toolkit', 'cli.py')
    covers = r'D:\桌面\jj\roai\公众号知识库\封面图'
    cover = ''
    for c in sorted(os.listdir(covers)):
        if c.endswith('.png'):
            cover = os.path.join(covers, c)
            break

    cmd = f'python {cli} publish "{enhanced_path}" --theme {args.theme} --title "{title}" --author {args.author}'
    if cover:
        cmd += f' --cover "{cover}"'

    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace', env=env)
    if 'Draft created' in r.stdout + r.stderr:
        print("✅ 推送成功!")
    else:
        print(f"❌ {(r.stdout + r.stderr)[-200:]}")

    shutil.rmtree(img_dir, ignore_errors=True)

if __name__ == '__main__':
    main()
