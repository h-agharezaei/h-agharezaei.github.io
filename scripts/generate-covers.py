#!/usr/bin/env python3
"""Generate 1200x630 social/cover images for posts (headless Chrome, Vazirmatn for Persian).

Usage (from anywhere):
  python3 scripts/generate-covers.py               # create missing covers for all posts
  python3 scripts/generate-covers.py <slug> ...    # only these posts (re-renders them)
  python3 scripts/generate-covers.py --default     # site default cards (og-default[.fa].png)
  python3 scripts/generate-covers.py --front-matter  # add the `cover = {...}` line to posts that lack it

Images go to static/images/covers/<slug>.png and <slug>.fa.png. Needs Google Chrome (override with CHROME=...).
Series names/colors are in SER below; add new series there.
"""
import glob,re,os,sys,json,html,subprocess,collections
import tempfile
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
S=tempfile.mkdtemp(prefix="covergen-")  # throwaway Chrome profile dir
OUT=R+"/static/images/covers"
CHROME=os.environ.get("CHROME","/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FONT="file://"+R+"/static/fonts/Vazirmatn-Variable.woff2"
FA_DIG=str.maketrans("0123456789","۰۱۲۳۴۵۶۷۸۹")
SER={"Go Fundamentals":("GO FUNDAMENTALS","مبانی Go","#00ADD8"),"Go Backend":("GO BACKEND","بک‌اند با Go","#00ADD8"),
"NATS JetStream":("NATS JETSTREAM","NATS JetStream","#2FBF71"),"Rust":("RUST","Rust","#F2663B"),"Go + Rust":("GO + RUST","Go + Rust","#A78BFA")}
def parse(path):
    t=open(path).read(); g=lambda k:(lambda m:(m.group(1) if m.group(1) is not None else m.group(2)) if m else None)(re.search(r"^%s = (?:'([^']*)'|\"([^\"]*)\")"%k,t,re.M))
    se=re.search(r'^series = \["([^"]+)"\]',t,re.M); ca=re.search(r'^categories = \[(.*?)\]',t,re.M); tg=re.search(r'^tags = \[(.*?)\]',t,re.M)
    return dict(title=g("title"),date=g("date")[:10],series=se.group(1) if se else None,cat=[c.strip().strip('"') for c in ca.group(1).split(",")] if ca else [],tags=[x.strip().strip('"') for x in tg.group(1).split(",")] if tg else [],has_cover="cover" in t)
posts={}
for f in sorted(glob.glob(R+"/content/posts/*.en.md")):
    slug=os.path.basename(f)[:-6]; fa=f.replace(".en.md",".fa.md")
    if not os.path.exists(fa): continue
    posts[slug]={"en":parse(f),"fa":parse(fa)}
bys=collections.defaultdict(list)
for s,p in posts.items():
    if p["en"]["series"]: bys[p["en"]["series"]].append((p["en"]["date"],s))
idx={}
for se,l in bys.items():
    l.sort()
    for i,(d,s) in enumerate(l): idx[s]=(i+1,len(l))
TAGHIDE={"beginner","intermediate","advanced","go","rust"}
def card(slug,lang,p):
    fa=lang=="fa"; se=p["series"]; cat=p["cat"]
    if se in SER: name=SER[se][1 if fa else 0]; color=SER[se][2]; n,N=idx[slug]; num=(f"{n} از {N}" if fa else f"{n} / {N}")
    elif "Meta" in cat: name="مرور سال ۱۴۰۵" if fa else "YEAR RECAP 1405"; color="#A78BFA"; num=""
    else: name="وبلاگ" if fa else "BLOG"; color="#9AA4B2"; num=""
    if fa: num=num.translate(FA_DIG)
    tags=[t for t in p["tags"] if t.lower() not in TAGHIDE][:3]
    chips="".join(f'<span class="chip">{html.escape(t)}</span>' for t in tags)
    badge='<bdi>'+html.escape(name)+'</bdi>'+(f' <i>·</i> <bdi>{num}</bdi>' if num else "")
    site="روهام" if fa else "Roham"
    return f'''<!doctype html><html lang="{lang}" dir="{'rtl' if fa else 'ltr'}"><meta charset="utf-8"><style>
@font-face{{font-family:V;src:url("{FONT}") format("woff2");font-weight:100 900}}
*{{box-sizing:border-box;margin:0}} html,body{{width:1200px;height:630px;overflow:hidden}}
body{{background:#0f1014;font-family:{'V,' if fa else ''}-apple-system,"Helvetica Neue",Helvetica,Arial,sans-serif;color:#fff;position:relative;
background-image:linear-gradient(#ffffff0b 1px,transparent 1px),linear-gradient(90deg,#ffffff0b 1px,transparent 1px);background-size:40px 40px}}
.bar{{position:absolute;top:0;bottom:0;{'right' if fa else 'left'}:0;width:16px;background:{color}}}
.wrap{{position:absolute;top:70px;bottom:60px;{'right' if fa else 'left'}:80px;{'left' if fa else 'right'}:80px;display:flex;flex-direction:column;align-items:flex-start}}
.badge{{background:{color};color:#0b0c10;font-weight:800;font-size:30px;padding:14px 30px;border-radius:999px;letter-spacing:{'0' if fa else '1px'}}} .badge i{{font-style:normal;opacity:.7;margin:0 6px}}
#t{{font-weight:800;line-height:{'1.45' if fa else '1.12'};margin:44px 0 28px;flex:1;display:flex;align-items:center;width:100%}}
.row{{display:flex;gap:14px;align-items:center;width:100%;justify-content:space-between}}
.chips{{display:flex;gap:12px}} .chip{{border:2px solid #ffffff33;color:#c9d1dc;font-size:26px;padding:6px 20px;border-radius:12px;direction:ltr}}
.site{{color:#8b95a5;font-size:28px;font-weight:600}} .site b{{color:{color}}}
</style><div class="bar"></div><div class="wrap"><div class="badge">{badge}</div><div id="t"><span id="tt">{html.escape(p["title"])}</span></div>
<div class="row"><div class="chips">{chips}</div><div class="site"><b>{site}</b> · justroham.ir</div></div></div>
<script>(function(){{var t=document.getElementById('t'),s=document.getElementById('tt'),max=t.clientHeight,z=92;
function f(){{s.style.fontSize=z+'px'}}f();while(z>38&&(s.offsetHeight>max||s.scrollWidth>t.clientWidth+2)){{z-=2;f()}}}})();</script></html>'''
def default_card(lang):
    fa=lang=="fa"; color="#00ADD8"
    name="روهام" if fa else "Roham"
    sub="مهندس نرم‌افزار ارشد · Go و Node.js" if fa else "Senior Software Engineer · Go &amp; Node.js"
    line2="مقاله‌هایی درباره‌ی Go، Rust، NATS و بک‌اند" if fa else "Articles on Go, Rust, NATS and backend engineering"
    return f'''<!doctype html><html lang="{lang}" dir="{'rtl' if fa else 'ltr'}"><meta charset="utf-8"><style>
@font-face{{font-family:V;src:url("{FONT}") format("woff2");font-weight:100 900}}
*{{box-sizing:border-box;margin:0}} html,body{{width:1200px;height:630px;overflow:hidden}}
body{{background:#0f1014;font-family:{'V,' if fa else ''}-apple-system,"Helvetica Neue",Helvetica,Arial,sans-serif;color:#fff;position:relative;
background-image:linear-gradient(#ffffff0b 1px,transparent 1px),linear-gradient(90deg,#ffffff0b 1px,transparent 1px);background-size:40px 40px}}
.bar{{position:absolute;top:0;bottom:0;{'right' if fa else 'left'}:0;width:16px;background:{color}}}
.wrap{{position:absolute;top:0;bottom:0;{'right' if fa else 'left'}:80px;{'left' if fa else 'right'}:80px;display:flex;flex-direction:column;justify-content:center}}
h1{{font-size:150px;font-weight:800;line-height:1.1}} p{{font-size:46px;color:#c9d1dc;margin-top:18px;font-weight:600}} p.s{{font-size:34px;color:#8b95a5;font-weight:500}}
.site{{position:absolute;bottom:52px;{'right' if fa else 'left'}:80px;color:{color};font-size:30px;font-weight:700}}
</style><div class="bar"></div><div class="wrap"><h1>{name}</h1><p>{sub}</p><p class="s">{line2}</p></div><div class="site">justroham.ir</div></html>'''
def render(htmlsrc,outpng):
    hp=outpng+".html"; open(hp,"w").write(htmlsrc)
    for attempt in range(4):
        if os.path.exists(outpng) and os.path.getsize(outpng)>8000 and attempt>0: break
        try:
            subprocess.run([CHROME,"--headless=new","--disable-gpu","--hide-scrollbars","--force-device-scale-factor=1","--user-data-dir="+S+"/profile","--window-size=1200,630","--virtual-time-budget=3000","--screenshot="+outpng,"file://"+hp],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
        except subprocess.TimeoutExpired: pass
        if os.path.exists(outpng) and os.path.getsize(outpng)>8000: break
    os.remove(hp)
    if not (os.path.exists(outpng) and os.path.getsize(outpng)>8000): print("FAILED",outpng)
if __name__=="__main__":
    os.makedirs(OUT,exist_ok=True)
    if "--front-matter" in sys.argv:
        n=0
        for f in sorted(glob.glob(R+"/content/posts/*.md")):
            t=open(f).read()
            if re.search(r"^cover\s*=",t,re.M): continue
            lang="fa" if f.endswith(".fa.md") else "en"; slug=os.path.basename(f)[:-6]
            m=re.search(r"^title = (?:'([^']*)'|\"([^\"]*)\")",t,re.M); title=m.group(1) if m.group(1) is not None else m.group(2)
            alt=title.replace("\\","\\\\").replace('"','\\"')
            line=f'cover = {{ image = "/images/covers/{slug}{".fa" if lang=="fa" else ""}.png", alt = "{alt}", hiddenInSingle = true }}\n'
            parts=t.split("+++\n",2); fm=parts[1] if parts[1].endswith("\n") else parts[1]+"\n"
            open(f,"w").write("+++\n"+fm+line+"+++\n"+parts[2]); n+=1; print("cover line added:",os.path.basename(f))
        print(n,"files updated"); sys.exit(0)
    only=[a for a in sys.argv[1:] if a!="--default"]
    if "--default" in sys.argv:
        for lang in ("en","fa"):
            out=f"{R}/static/images/og-default{'.fa' if lang=='fa' else ''}.png"; render(default_card(lang),out); print(out)
        sys.exit(0)
    for slug,p in posts.items():
        if only and slug not in only: continue
        if p["en"]["has_cover"] and slug in ("php-critical-rce-cve-2026-109618","gitlab-critical-rce-cve-2026-110264"): continue
        for lang in ("en","fa"):
            out=f"{OUT}/{slug}{'.fa' if lang=='fa' else ''}.png"
            if os.path.exists(out) and os.path.getsize(out)>8000: continue
            render(card(slug,lang,p[lang]),out); print(out)
