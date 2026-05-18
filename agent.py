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

קריטריונים קשים — דירה שלא עומדת בהם תקבל ציון מתחת ל-40:
- מחיר מקסימלי: 6,000,000 CZK
- קומה קרקע (0) — הורד 25 נקודות
- ללא מעלית בבניין מעל קומה 3 — הורד 20 נקודות
- מחיר למ"ר מעל 130,000 CZK — לא כלכלי, הורד 20 נקודות
- בניין ישן ללא שיפוץ מוזכר — הורד 15 נקודות

קריטריונים מועדפים — מעלים ציון:
- אזור מבוקש (וינוהראדי, קרלין) — עד +15
- קומה 2-4 עם מעלית — +10
- תיאור מציין שיפוץ / מצב טוב — +15
- מחיר למ"ר מתחת ל-100,000 CZK — +10
- קרוב לתחבורה ציבורית — +5

עבור כל דירה החזר JSON בלבד (ללא markdown, ללא הסברים):
[
  {
    "index": 1,
    "investmentScore": 78,
    "pricePerM2": 95000,
    "estimatedRent": 12000,
    "grossYield": 2.4,
    "pros": ["קומה 3 עם מעלית", "אזור מבוקש"],
    "cons": ["אין מרפסת", "מחיר גבוה יחסית"],
    "foreignInvestorNote": "מתאים למשקיע זר — אין מגבלות רכישה לאזרחי EU",
    "analysis": "ניתוח של 2-3 משפטים"
  }
]"""


def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(ids), f)


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
    return r.json().get("_embedded", {}).get("estates", [])


def analyze_with_claude(listings, label):
    summaries = []
    for i, l in enumerate(listings):
        price_raw = l.get("price", {})
price = price_raw.get("value_raw", 0) if isinstance(price_raw, dict) else int(price_raw) if price_raw else 0
        labels = {x["key"]: x["value"] for x in l.get("labelsReplaced", [])}
        area = labels.get("usable_area", "?")
        floor = labels.get("floor_number", "?")
        name = l.get("name", {}).get("value", "דירה")
        locality = l.get("locality", {}).get("value", "")
        description = l.get("perex", "") or ""
        summaries.append(
            f"{i+1}. \"{name}\" | {locality} | מחיר: {price:,} CZK | שטח: {area} | קומה: {floor} | תיאור: {description[:200]}"
        )

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "messages": [{
            "role": "user",
            "content": INVESTMENT_PROMPT + f"\n\nקבוצה: {label}\n\nדירות:\n" + "\n".join(summaries)
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
        timeout=30
    )
    r.raise_for_status()
    text = r.json()["content"][0]["text"]
    text = text.replace("```json", "").replace("```", "").strip()
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
            text_color, bg_color = score_color(score)
            pros = "".join(f"<li>{p}</li>" for p in c.get("pros", []))
            cons = "".join(f"<li>{p}</li>" for p in c.get("cons", []))
            url = c.get("url", "#")
            rent = f'{c.get("estimatedRent", 0):,}'
            gross = c.get("grossYield", 0)
            ppm2 = f'{int(c.get("pricePerM2", 0)):,}'

            cards_html += f"""
            <div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:16px 20px;margin-bottom:16px;direction:rtl;font-family:sans-serif;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <strong style="font-size:15px;color:#111;">{c.get('name','דירה')}</strong>
                <span style="background:{bg_color};color:{text_color};padding:4px 10px;border-radius:20px;font-size:13px;font-weight:600;">{score}/100</span>
              </div>
              <div style="font-size:13px;color:#555;margin-bottom:10px;">{c.get('locality','')}</div>
              <table style="width:100%;font-size:13px;border-collapse:collapse;">
                <tr>
                  <td style="padding:3px 0;color:#777;">מחיר למ"ר</td>
                  <td style="padding:3px 0;font-weight:500;">{ppm2} CZK</td>
                  <td style="padding:3px 0;color:#777;">שכ"ד משוער</td>
                  <td style="padding:3px 0;font-weight:500;">{rent} CZK/חודש</td>
                </tr>
                <tr>
                  <td style="padding:3px 0;color:#777;">תשואה ברוטו</td>
                  <td style="padding:3px 0;font-weight:500;">{gross}%</td>
                  <td></td><td></td>
                </tr>
              </table>
              <div style="margin-top:10px;font-size:13px;color:#333;">{c.get('analysis','')}</div>
              <div style="margin-top:8px;font-size:13px;">
                <span style="color:#2e7d32;">✔ {' | '.join(c.get('pros',[]))}</span><br>
                <span style="color:#c62828;">✘ {' | '.join(c.get('cons',[]))}</span>
              </div>
              <div style="margin-top:8px;font-size:12px;color:#555;background:#f5f5f5;border-radius:6px;padding:8px;">
                💡 {c.get('foreignInvestorNote','')}
              </div>
              <a href="{url}" style="display:inline-block;margin-top:12px;font-size:13px;color:#1565c0;">פתח ב-Sreality ↗</a>
            </div>"""

    html = f"""
    <html><body style="background:#f9f9f9;padding:24px;">
      <div style="max-width:600px;margin:0 auto;">
        <h1 style="font-family:sans-serif;font-size:20px;color:#111;direction:rtl;">דוח דירות להשקעה — {today}</h1>
        <p style="font-family:sans-serif;font-size:13px;color:#777;direction:rtl;">דירות חדשות שנמצאו היום ועונות על הקריטריונים שלך</p>
        {cards_html if cards_html else '<p style="font-family:sans-serif;direction:rtl;color:#555;">לא נמצאו דירות חדשות היום.</p>'}
        <hr style="margin-top:32px;border:none;border-top:1px solid #e0e0e0;">
        <p style="font-family:sans-serif;font-size:11px;color:#aaa;direction:rtl;">נשלח אוטומטית על ידי Sreality Investment Agent</p>
      </div>
    </body></html>"""
    return html


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
        except Exception as e:
            print(f"Error analyzing: {e}")
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
                "name": l.get("name", {}).get("value", "דירה"),
                "locality": l.get("locality", {}).get("value", ""),
                "url": f"https://www.sreality.cz/detail/prodej/byt/{hash_id}" if hash_id else "#"
            })
            all_new_count += 1

        sections.append((search["label"], cards))

    save_seen_ids(seen_ids)
    html = build_html_email(sections)
    send_email(html, all_new_count)


if __name__ == "__main__":
    main()
