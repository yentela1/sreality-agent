import os, json, requests, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = "mf220374@gmail.com"
SEEN_FILE = "seen_ids.json"

SEARCHES = [
    {"label": "וינוהראדי / דייביצה — 1+kk", "sub": 2, "regions": [5006, 5007]},
    {"label": "קרלין / סמיחוב / נוסלה — 2+kk", "sub": 3, "regions": [5003, 5009, 5013]},
]

PROMPT = """אתה יועץ נדל"ן בפראג. החזר JSON בלבד ללא markdown, מערך של אובייקטים:
[{"index":1,"investmentScore":75,"pricePerM2":95000,"estimatedRent":12000,"grossYield":2.4,"pros":["יתרון"],"cons":["חסרון"],"foreignInvestorNote":"הערה","analysis":"ניתוח"}]

כללים: קומה 0 מוריד 25 נקודות. מחיר מעל 130000 למ"ר מוריד 20. קומה 2-4 עם מעלית מוסיף 10. שיפוץ מוסיף 15."""


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(ids), f)

def val(obj, default=""):
    if isinstance(obj, dict):
        return str(obj.get("value", default))
    return str(obj) if obj else default

def get_price(l):
    p = l.get("price")
    if isinstance(p, dict):
        return int(p.get("value_raw") or 0)
    return int(p or 0)

def get_label(l, key):
    for x in (l.get("labelsReplaced") or []):
        if isinstance(x, dict) and x.get("key") == key:
            return str(x.get("value", "?"))
    return "?"

def fetch(search):
    params = [("category_main_cb",1),("category_sub_cb",search["sub"]),
              ("category_type_cb",1),("price_max",6000000),("per_page",20),("page",1)]
    for r in search["regions"]:
        params.append(("region_entity_id", r))
    r = requests.get("https://www.sreality.cz/api/cs/v2/estates", params=params,
                     headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}, timeout=15)
    r.raise_for_status()
    emb = r.json().get("_embedded", {})
    return emb.get("estates", []) if isinstance(emb, dict) else []

def analyze(listings, label):
    rows = []
    for i, l in enumerate(listings):
        rows.append(f"{i+1}. {val(l.get('name'),'דירה')} | {val(l.get('locality'))} | {get_price(l):,} CZK | {get_label(l,'usable_area')}m2 | קומה {get_label(l,'floor_number')} | {str(l.get('perex','') or '')[:120]}")
    body = {"model":"claude-sonnet-4-20250514","max_tokens":2000,
            "messages":[{"role":"user","content":PROMPT+f"\n\nקבוצה: {label}\n\n"+"\n".join(rows)}]}
    r = requests.post("https://api.anthropic.com/v1/messages",
                      headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","Content-Type":"application/json"},
                      json=body, timeout=60)
    r.raise_for_status()
    text = r.json()["content"][0]["text"].replace("```json","").replace("```","").strip()
    return json.loads(text)

def color(score):
    if score >= 75: return "#2d6a1f","#e8f5e2"
    if score >= 55: return "#7a5200","#fff8e1"
    return "#8b1a1a","#fdecea"

def make_email(sections):
    today = date.today().strftime("%d.%m.%Y")
    body = ""
    for lbl, cards in sections:
        if not cards: continue
        body += f'<h2 style="direction:rtl;font-family:sans-serif;">{lbl}</h2>'
        for c in cards:
            tc,bc = color(c.get("investmentScore",0))
            body += f'''<div style="background:#fff;border:1px solid #ddd;border-radius:10px;padding:16px;margin-bottom:12px;direction:rtl;font-family:sans-serif;">
<div style="display:flex;justify-content:space-between;">
  <strong>{c.get("name","דירה")}</strong>
  <span style="background:{bc};color:{tc};padding:3px 10px;border-radius:20px;">{c.get("investmentScore",0)}/100</span>
</div>
<div style="color:#555;font-size:13px;">{c.get("locality","")}</div>
<div style="font-size:13px;margin-top:8px;">מחיר למ"ר: {int(c.get("pricePerM2",0)):,} CZK | שכ"ד: {int(c.get("estimatedRent",0)):,} CZK | תשואה: {c.get("grossYield",0)}%</div>
<div style="margin-top:8px;font-size:13px;">{c.get("analysis","")}</div>
<div style="color:#2e7d32;font-size:13px;">✔ {" | ".join(c.get("pros",[]))}</div>
<div style="color:#c62828;font-size:13px;">✘ {" | ".join(c.get("cons",[]))}</div>
<div style="background:#f5f5f5;border-radius:6px;padding:8px;font-size:12px;margin-top:6px;">💡 {c.get("foreignInvestorNote","")}</div>
<a href="{c.get("url","#")}" style="font-size:13px;color:#1565c0;">פתח ב-Sreality ↗</a>
</div>'''
    if not body:
        body = '<p style="direction:rtl;font-family:sans-serif;">לא נמצאו דירות חדשות היום.</p>'
    return f'<html><body style="background:#f9f9f9;padding:24px;"><div style="max-width:600px;margin:0 auto;"><h1 style="direction:rtl;font-family:sans-serif;">דוח דירות להשקעה — {today}</h1>{body}</div></body></html>'

def send(html, count):
    today = date.today().strftime("%d.%m.%Y")
    subj = f"🏠 {count} דירות חדשות — {today}" if count else f"אין דירות חדשות — {today}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        s.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
    print(f"Sent: {subj}")

def main():
    seen = load_seen()
    sections = []
    total = 0
    for search in SEARCHES:
        print(f"Fetching: {search['label']}")
        try:
            raw = fetch(search)
        except Exception as e:
            print(f"Fetch error: {e}")
            continue
        new = [l for l in raw if str(l.get("hash_id","")) not in seen]
        print(f"  {len(raw)} total, {len(new)} new")
        if not new:
            sections.append((search["label"], []))
            continue
        try:
            results = analyze(new[:8], search["label"])
            print(f"  Analyzed: {len(results)}")
        except Exception as e:
            print(f"Analyze error: {e}")
            sections.append((search["label"], []))
            continue
        cards = []
        for i, l in enumerate(new[:8]):
            ai = next((a for a in results if a.get("index")==i+1), {})
            if ai.get("investmentScore",0) < 50:
                continue
            hid = str(l.get("hash_id",""))
            seen.add(hid)
            cards.append({**ai,
                "name": val(l.get("name"), "דירה"),
                "locality": val(l.get("locality")),
                "url": f"https://www.sreality.cz/detail/prodej/byt/{hid}"})
            total += 1
        sections.append((search["label"], cards))
    save_seen(seen)
    send(make_email(sections), total)
    print(f"Done: {total} sent.")

if __name__ == "__main__":
    main()
