# Sreality Investment Agent 🏠

אייג'נט אוטומטי שמחפש כל יום דירות להשקעה בפראג ב-Sreality.cz ושולח דוח במייל.

## התקנה — 4 צעדים בלבד

### צעד 1 — צור Repository ב-GitHub
לחץ על "+" בפינה הימנית העליונה ← "New repository"  
שם: `sreality-agent` ← Public או Private (לא משנה) ← Create

### צעד 2 — העלה את הקבצים
העלה את הקבצים הבאים לשורש ה-Repository:
- `agent.py`
- `.github/workflows/daily.yml`

### צעד 3 — הגדר Gmail App Password
1. כנסי ל-myaccount.google.com
2. Security ← 2-Step Verification (חייב להיות מופעל)
3. App passwords ← צרי סיסמה חדשה בשם "sreality"
4. שמרי את הסיסמה שתקבלי (16 תווים)

### צעד 4 — הוסיפי Secrets ב-GitHub
ב-Repository ← Settings ← Secrets and variables ← Actions ← New repository secret

הוסיפי שלושה Secrets:

| שם | ערך |
|---|---|
| `ANTHROPIC_API_KEY` | המפתח החדש שיצרת |
| `GMAIL_USER` | כתובת Gmail שממנה ישלח המייל |
| `GMAIL_APP_PASSWORD` | סיסמת האפליקציה מצעד 3 |

## הרצה ידנית (לבדיקה)
ב-Repository ← Actions ← Sreality Daily Agent ← Run workflow

## מה האייג'נט שולח
מייל HTML יומי עם:
- ציון השקעה לכל דירה (0-100)
- מחיר למ"ר
- שכר דירה חודשי משוער
- תשואה ברוטו משוערת
- יתרונות וחסרונות
- הערה למשקיע זר
- קישור ישיר לדירה ב-Sreality

## דיוק התוצאות
אם מגיעות דירות לא מתאימות — ערכי את `INVESTMENT_PROMPT` ב-`agent.py`  
והוסיפי כלל שלילי למשל: "דירות ללא חניה — הורד 10 נקודות"
