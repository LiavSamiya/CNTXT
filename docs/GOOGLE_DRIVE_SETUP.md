# חיבור Google Drive אמיתי ל־CNTXT

המדריך הזה מחבר את ה־Google Drive שלך ל־gateway המקומי. ההרשאה היא
**read-only** בלבד (`drive.readonly`); הקוד לא מעלה, מוחק או משנה קבצים ב־Drive.
התוכן נמשך אל המחשב המקומי, מסונן ב־CNTXT ורק לאחר מכן מוחזר כ־safe context.

## לפני שמתחילים

- הרץ את ה־dashboard מקומית ב־`http://127.0.0.1:8787`.
- ודא ש־MarkItDown מותקן, כדי שגם PDF וקבצי Office מ־Drive יעברו המרה מקומית:

```powershell
cd C:\path\to\shieldai
& "C:\Users\liavs\anaconda3\python.exe" -m pip install -r requirements.txt
```

- השתמש בפרויקט Google Cloud אישי לבדיקות, ולא במפתח או token של אדם אחר.
- אל תשלח את קובץ ה־OAuth JSON בצ'אט ואל תעלה אותו ל־GitHub.

## הפעולות ב־Google Cloud Console

1. פתח את [Google Cloud Console](https://console.cloud.google.com/) והתחבר
   לחשבון Google שלך.
2. בחלק העליון לחץ על בורר הפרויקטים, בחר **New Project**, תן שם כגון
   `CNTXT Local Demo`, ולחץ **Create**. לאחר מכן ודא שהפרויקט החדש נבחר.
3. פתח **APIs & Services → Library**, חפש `Google Drive API`, פתח אותו ולחץ
   **Enable**.
4. פתח **Google Auth Platform → Branding**. אם מוצג **Get Started**, לחץ עליו
   ומלא:
   - **App name**: `CNTXT Local`.
   - **User support email**: כתובת המייל שלך.
   - **Audience**: בחר **External** לחשבון אישי; בארגון Google Workspace אפשר
     לבחור **Internal** אם רק משתמשי הארגון ישתמשו בו.
   - **Contact information**: כתובת המייל שלך.
   - אשר את מדיניות Google ולחץ **Create**.
5. לחשבון אישי במצב **Testing**: פתח **Audience**, תחת **Test users** לחץ
   **Add users**, הוסף את כתובת ה־Google שלך ולחץ **Save**. בלי שלב זה Google
   לא תאפשר לחשבון שלך לאשר את האפליקציה החיצונית במצב בדיקה.
6. פתח **Data Access → Add or Remove Scopes**. הוסף רק את
   `https://www.googleapis.com/auth/drive.readonly`, ואז שמור. זהו ה־scope
   היחיד שהקוד מבקש.
7. פתח **Google Auth Platform → Clients**, לחץ **Create client**, ובחר
   **Desktop app**. תן שם כגון `CNTXT desktop`, ולחץ **Create**.
8. ליד ה־client החדש לחץ על **Download JSON**.

ב־Desktop app אין צורך להגדיר ידנית redirect URI: CNTXT פותחת callback זמני על
`127.0.0.1` עם פורט מקומי אקראי ומשתמשת ב־PKCE. אל תיצור Web application עבור
הזרימה הזו.

Google מתעדת שצריך להגדיר את מסך ההסכמה וה־scopes ב־Cloud Console, ושאפליקציית
External במצב Testing חייבת Test Users. ראו
[תיעוד הגדרת מסך ההסכמה של Google](https://developers.google.com/workspace/guides/configure-oauth-consent)
ו־[בחירת scopes ל־Drive API](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

## הפעולות בתיקיית הפרויקט

1. צור תיקייה בשם `secrets` בשורש הפרויקט אם אינה קיימת.
2. העבר את הקובץ שהורד לשם המדויק:

```text
shieldai\secrets\google-oauth-client.json
```

3. ודא שהוא לא נכנס ל־Git:

```powershell
git status --short
```

לא אמור להופיע שם הקובץ. התיקייה `secrets/` כבר מוחרגת ב־`.gitignore`.

4. הפעל מחדש את dashboard:

```powershell
& "C:\Users\liavs\anaconda3\python.exe" backend\app.py
```

5. פתח `http://127.0.0.1:8787`, עבור ל־**MCP connections**, ולחץ
**Connect Google Drive**.
6. הדפדפן ייפתח. בחר את החשבון שהוספת כ־Test User, בדוק שמוצגת הרשאת
**View and download all your Google Drive files**, ולחץ **Allow**.
7. לאחר ההצלחה יופיע דף `ShieldAI connected to Google Drive`. חזור ל־CNTXT;
ה־connector אמור להציג **Connected · Read-only OAuth connection**.
8. עבור ל־**Live firewall**, בחר **Google Drive MCP · search documents**, הזן
מילות חיפוש ולחץ **Protect context**. אם התוצאה כוללת PDF או קובץ Office,
MarkItDown ממיר אותו מקומית לפני שה־sanitizer רואה את הטקסט.

## היכן נשמר המידע

| פריט | מיקום | נכנס ל־Git? |
| --- | --- | --- |
| OAuth client JSON | `secrets/google-oauth-client.json` | לא |
| Google refresh/access token | `data/google_token.json` | לא |
| placeholder mappings | `data/project_memory.db` | לא |
| audit | `data/audit.jsonl` | לא; ללא raw content |

## פתרון תקלות

- **OAuth client file not found** — בדוק את שם הנתיב והפעל מחדש את ה־dashboard.
- **Access blocked / app has not completed verification** — ודא שהחשבון שלך
  נמצא תחת Test users. עבור דמו אישי אין צורך לפרסם את האפליקציה.
- **Google Drive session expired** — לחץ שוב **Connect Google Drive**. במצב
  Testing הרשאות עשויות לפוג; Google מתעדת את מגבלות מצב הבדיקה.
- **Could not convert file locally** — התקן מחדש `requirements.txt`; ודא שהקובץ
  עד 10 MB ובאחד הפורמטים הנתמכים.
- **No matching documents** — השתמש במילים שמופיעות בשם או בתוכן המסמך ובדוק
  שהקובץ אינו ב־Trash.

לשימוש צוותי/ארגוני אמיתי, כדאי לעבור לפרויקט Google Cloud ארגוני, לבחור
Internal כשאפשר, לנהל tokens ב־vault מוצפן, ולהשלים את דרישות האימות של Google
לפני שמאפשרים משתמשים חיצוניים.
