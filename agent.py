import os
import json
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = "mf220374@gmail.com"
SEEN_FILE = "seen_ids.json"

SEARCHES = [
    {
        "label": "וינוהראדי / דייביצה — 1+kk",
        "params": {
            "category_main_cb": 1,
            "category_sub_cb": 2,
            "category_type_cb": 1,
            "region_entity_id": [5006, 5007],
            "price_max": 6000000,
            "per_page": 20,
            "page": 1,
        }
    },
    {
        "label": "קרלין / סמיחוב / נוסלה — 2+kk",
        "params": {
            "category_main_cb": 1,
            "category_sub_cb": 3,
            "category_type_cb": 1,
            "region_entity_id": [5003, 5009, 5013],
            "price_max": 6000000,
            "per_page": 20,
            "page": 1,
        }
    }
]

INVESTMENT_PROMPT = """אתה יועץ נדל"ן מומחה בפראג. משקיעה זרה ראשונה מחפשת דירה להשקעה יציבה עם שוכרים לטווח ארוך.

קריטריונים קשים:
- מחיר מקסימלי: 6,000,000 CZK
- קומה קרקע (0) — הורד 25 נקודות
- ללא מעלית בבניין מעל קומה 3 — הורד 20 נקודות
- מחיר למ"ר מעל 130,000 CZK — הורד 20 נקודות

קריטריונים מועדפים:
- אזור מבוקש (וינוהראדי, קרלין) — עד +15
- קומה 2-4 עם מעלית — +10
- תיאור מציין שיפוץ / מצב טוב — +15
- מחיר למ"ר מתחת ל-100,000 CZK — +10

החזר JSON בלבד ללא markdown:
[{"index":1,"investmentScore":78,"pricePerM2":95000,"estimatedRent":12000,"grossYield":2.4,"pros":["קומה 3"],"cons":["אין מרפסת"],"foreignInvestorNote":"הערה","analysis":"ניתוח"}]"""


def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(ids), f)


def get_price(listing):
    price = listing.get("price")
    if price is None:
        return 0
    if isinstance(price, dict):
        val = price.get("value_raw", 0)
        return int(val) if val else 0
    if isinstance(price, (int, float)):
        return int(price)
    return 0


def get_str(obj, default=""):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return str(obj.get("value", default))
    return str(obj)


def get_label(listing, key):
    labels = listing.get("labelsReplaced", [])
    if not isinstance(labels, list):
        return "?"
    for item in labels:
        if isinstance(item, dict) and item.get("key") == key:
            return str(item.get("value", "?"))
    return "?"


def fetch_listings(search):
    params = []
    for k, v in search["params"].items():
        if isinstance(v, list):
            for item in v:
                params.append((k, item))
        else:
            params.append((k, v))
    url = "https://www.sreality.cz/api/cs/v2/estates"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.sreality.cz/"
    }
    r = requests.get(url, params=params, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    embedded = data.get("_embedded", {})
    return embedded.get("estates", []) if isinstance(embedded, dict) else []


def analyze_with_claude(listings, label):
    summaries = []
    for i, l in enumerate(listings):
        price = get_price(l)
        area = get_label(l, "usable_area")
        floor = get_label(l, "floor_number")
        name = get_str(l.get("name"), default="דירה")
        locality = get_str(l.get("locality"), default="")
        desc = str(l.get("perex", "") or "")[:150]
        summaries.append(
            f"{i+1}. \"{name}\" | {locality} | {price:,} CZK | {area}m² | קומה {floor} | {desc}"
        )

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "messages": [{
            "role": "user",
            "content": INVESTMENT_PROMPT + f"\n\nקבוצה: {label}\n\n" + "\n".join(summaries)
        }]
    }
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=60
    )
    r.raise_for_status()
    text = r.json()["content"][0]["text"].replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def score_color(score):
    if score >= 75:
        return "#2d6a1f", "#e8f5e2"
    if score >= 55:
        return "#7a5200", "#fff8e1"
    return "#8b1a1a", "#fdecea"


def build_html_email(sections):
    today = date.today().strftime("%d.%m.%Y")
    cards_html = ""
    for section_label, cards in sections:
        if not cards:
            continue
        cards_html += f'<h2 style="font-family:sans-serif;font-size:16px;color:#333;margin:24px 0 12px;direction:rtl;">{section_label}</h2>'
        for c in cards:
            score = c.get("investmentScore", 0)
            tc, bc = score_color(score)
            cards_html += f"""
            <div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:16px 20px;margin-bottom:16px;direction:rtl;font-family:sans-serif;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <strong style="font-size:15px;color:#111;">{c.get('name','דירה')}</strong>
                <span style="background:{bc};color:{tc};padding:4px 10px;border-radius:20px;font-size:13px;font-weight:600;">{score}/100</span>
              </div>
              <div style="font-size:13px;color:#555;margin-bottom:10px;">{c.get('locality','')}</div>
              <table style="width:100%;font-size:13px;">
                <tr>
                  <td style="color:#777;">מחיר למ"ר</td>
                  <td>{int(c.get('pricePerM2',0)):,} CZK</td>
                  <td style="color:#777;">שכ"ד משוער</td>
                  <td>{int(c.get('estimatedRent',0)):,} CZK/חודש</td>
                </tr>
                <tr>
                  <td style="color:#777;">תשואה ברוטו</td>
                  <td>{c.get('grossYield',0)}%</td>
                  <td></td><td></td>
                </tr>
              </table>
              <div style="margin-top:10px;font-size:13px;">{c.get('analysis','')}</div>
              <div style="margin-top:8px;font-size:13px;color:#2e7d32;">✔ {' | '.join(c.get('pros',[]))}</div>
              <div style="font-size:13px;color:#c62828;">✘ {' | '.join(c.get('cons',[]))}</div>
              <div style="margin-top:8px;font-size:12px;background:#f5f5f5;border-radius:6px;padding:8px;">💡 {c.get('foreignInvestorNote','')}</div>
              <a href="{c.get('url','#')}" style="display:inline-block;margin-top:12px;font-size:13px;color:#1565c0;">פתח ב-Sreality ↗</a>
            </div>"""

    body = cards_html if cards_html else '<p style="font-family:sans-serif;direction:rtl;">לא נמצאו דירות חדשות היום.</p>'
    return f"""<html><body style="background:#f9f9f9;padding:24px;">
      <div style="max-width:600px;margin:0 auto;">
        <h1 style="font-family:sans-serif;font-size:20px;direction:rtl;">דוח דירות להשקעה — {today}</h1>
        {body}
        <p style="font-family:sans-serif;font-size:11px;color:#aaa;direction:rtl;">נשלח אוטומטית על ידי Sreality Investment Agent</p>
      </div>
    </body></html>"""


def send_email(html, new_count):
    today = date.today().strftime("%d.%m.%Y")
    subject = f"🏠 {new_count} דירות חדשות להשקעה בפראג — {today}" if new_count > 0 else f"אין דירות חדשות היום — {today}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
    print(f"Email sent: {subject}")


def main():
    seen_ids = load_seen_ids()
    sections = []
    all_new_count = 0

    for search in SEARCHES:
        print(f"Fetching: {search['label']}")
        try:
            raw = fetch_listings(search)
        except Exception as e:
            print(f"Error fetching: {e}")
            continue

        new_listings = [l for l in raw if str(l.get("hash_id", "")) not in seen_ids]
        print(f"  {len(raw)} total, {len(new_listings)} new")

        if not new_listings:
            sections.append((search["label"], []))
            continue

        try:
            analysis = analyze_with_claude(new_listings[:8], search["label"])
            print(f"  Analysis OK: {len(analysis)} results")
        except Exception as e:
            print(f"Error analyzing: {e}")
            sections.append((search["label"], []))
            continue

        cards = []
        for i, l in enumerate(new_listings[:8]):
            ai = next((a for a in analysis if a.get("index") == i + 1), {})
            if ai.get("investmentScore", 0) < 50:
                continue
            hash_id = str(l.get("hash_id", ""))
            seen_ids.add(hash_id)
            cards.append({
                **ai,
                "name": get_str(l.get("name"), default="דירה"),
                "locality": get_str(l.get("locality"), default=""),
                "url": f"https://www.sreality.cz/detail/prodej/byt/{hash_id}" if hash_id else "#"
            })
            all_new_count += 1

        sections.append((search["label"], cards))

    save_seen_ids(seen_ids)
    html = build_html_email(sections)
    send_email(html, all_new_count)
    print(f"Done. {all_new_count} listings sent.")


if __name__ == "__main__":
    main()
