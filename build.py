#!/usr/bin/env python3
"""Copies the HTML of the Wikeutral wiki (every article page, the home page, pictures) from its tunnel into a folder
that GitHub Pages serves.   python3 build.py OUTDIR [SERVER_URL]"""
import concurrent.futures, gzip, json, os, re, sys, time, urllib.parse, urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else "site"
BASE = os.environ.get("PAGES_BASE", "/wikeutral")
UA = {"User-Agent": "wikeutral-pages-build/1.0 (github.com/Luishae07/wikeutral)"}


def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


SERVER = (sys.argv[2] if len(sys.argv) > 2 else get("https://raw.githubusercontent.com/Luishae07/groundcheck/HEAD/wikeutral-url.txt").decode().split()[0]).rstrip("/")
print("server:", SERVER, flush=True)

titles, off = [], 0
while True:
    found = re.findall(r"^Title: (.*)$", gzip.decompress(get(f"{SERVER}/file?offset={off}")).decode("utf-8", "replace"), re.M)
    titles += found
    if len(found) < 200:
        break
    off += 200
print(len(titles), "articles", flush=True)

STYLE = re.compile(r"<style>.*?</style>", re.S)
FORM = re.compile(r"<form class=s .*?</form>", re.S)
TABS = re.compile(r"<div class=tabs>.*?</div>", re.S)
DEAD = re.compile(r'<a href="/(?:random|new|images|statistics|docs|news|download|recent|api)[^"]*">[^<]*</a>')
THEME = re.compile(r"<button[^>]*id=theme[^>]*>.*?</button>", re.S)
IMAGES, CSS = set(), []


def save(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    open(path, "wb").write(data)


def fix(html):
    m = STYLE.search(html)
    if m:
        if not CSS:
            CSS.append(m.group(0)[7:-8])
        html = html[:m.start()] + f'<link rel=stylesheet href="{BASE}/style.css">' + html[m.end():]
    html = FORM.sub(f'<a href="{BASE}/search.html" style="margin-left:auto">Search</a>', html)
    html = TABS.sub("", html)
    html = DEAD.sub("", html)
    html = THEME.sub("", html)
    IMAGES.update(re.findall(r'(?:src|href)="/image/([^"]+)"', html))
    return re.sub(r'(href|src)="/(?!/)', rf'\1="{BASE}/', html)


def page(title):
    if "/" in title or "\0" in title:
        return False
    try:
        raw = get(f"{SERVER}/wiki/{urllib.parse.quote(title.replace(' ', '_'))}").decode("utf-8", "replace")
    except Exception:
        return False
    save(os.path.join(OUT, "wiki", title.replace(" ", "_"), "index.html"), fix(raw).encode())
    return True


save(os.path.join(OUT, "index.html"), fix(get(SERVER + "/").decode("utf-8", "replace")).encode())
done = 0
with concurrent.futures.ThreadPoolExecutor(8) as pool:
    for n, ok in enumerate(pool.map(page, titles), 1):
        done += ok
        if n % 500 == 0:
            print(f"  {n}/{len(titles)}", flush=True)
print(f"pages: {done}/{len(titles)}", flush=True)
if CSS:
    save(os.path.join(OUT, "style.css"), CSS[0].encode())


def image(name):
    try:
        save(os.path.join(OUT, "image", urllib.parse.unquote(name)), get(f"{SERVER}/image/{name}"))
        return True
    except Exception:
        return False


with concurrent.futures.ThreadPoolExecutor(8) as pool:
    ok = sum(pool.map(image, sorted(IMAGES)))
print(f"images: {ok}/{len(IMAGES)}", flush=True)

save(os.path.join(OUT, "titles.json"), json.dumps(sorted(titles), ensure_ascii=False).encode())
save(os.path.join(OUT, "search.html"), f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Search – Wikeutral</title>
<style>body{{margin:0;font:16px/1.6 Georgia,serif;background:#f8f9fa;color:#202122}}main{{max-width:760px;margin:0 auto;padding:24px 16px}}
input{{width:100%;padding:10px;font:16px system-ui;border:1px solid #a2a9b1;box-sizing:border-box}}a{{color:#36c;text-decoration:none}}li{{margin:4px 0}}</style>
<main><p><a href="{BASE}/">Wikeutral</a></p><h1>Search</h1><input id=q placeholder="Search article titles" autofocus><ul id=r></ul></main>
<script>
fetch('{BASE}/titles.json').then(r=>r.json()).then(t=>{{
  const q=document.getElementById('q'),r=document.getElementById('r');
  const go=()=>{{const s=q.value.trim().toLowerCase();r.innerHTML='';if(!s)return;
    t.filter(x=>x.toLowerCase().includes(s)).sort((a,b)=>a.toLowerCase().indexOf(s)-b.toLowerCase().indexOf(s)).slice(0,100)
     .forEach(x=>{{const li=document.createElement('li'),a=document.createElement('a');a.textContent=x;a.href='{BASE}/wiki/'+encodeURIComponent(x.replace(/ /g,'_'));li.appendChild(a);r.appendChild(li)}})}};
  q.oninput=go;go();}});
</script>""".encode())
save(os.path.join(OUT, "404.html"), f'<!doctype html><meta charset=utf-8><title>Not found</title><p>No such page. <a href="{BASE}/search.html">Search</a></p>'.encode())
open(os.path.join(OUT, ".nojekyll"), "w").close()
print("done")
