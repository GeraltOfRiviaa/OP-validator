"""
Validátor obchodních podmínek e-shopu
Kontroluje HTML stránky s OP podle checklistu a právních předpisů.
"""

import http.server
import socketserver
import json
import csv
import io
import urllib.parse
import threading
import time
import re
from typing import Optional
import urllib.request
import urllib.error
import ssl
import html as html_module

# ─── DATABÁZE KONTROL ──────────────────────────────────────────────────────────

CHECKLIST = [
    {
        "id": "zakon_89_2012",
        "kategorie": "Základní náležitosti OP",
        "nazev": "Nový občanský zákoník (89/2012 Sb.)",
        "popis": "OP musí být dle nového OZ č. 89/2012 Sb.",
        "hledat": ["89/2012", "občanský zákoník"],
        "typ": "must_have",
    },
    {
        "id": "smernice_eu_2011",
        "kategorie": "Základní náležitosti OP",
        "nazev": "Předsmluvní informace dle 2011/83/EU",
        "popis": "Musí obsahovat povinné předsmluvní informace dle směrnice EU 2011/83/EU.",
        "hledat": ["2011/83", "předsmluvní informace", "práva spotřebitele"],
        "typ": "must_have",
    },
    {
        "id": "odstoupeni_14_dni",
        "kategorie": "Základní náležitosti OP",
        "nazev": "Právo odstoupení do 14 dnů",
        "popis": "Musí být uvedeno právo odstoupit od smlouvy do 14 dnů včetně formuláře.",
        "hledat": ["14 dnů", "14 dní", "odstoupit od smlouvy", "odstoupení od smlouvy"],
        "typ": "must_have",
    },
    {
        "id": "reklamace_proces",
        "kategorie": "Základní náležitosti OP",
        "nazev": "Proces reklamace dle ZOS",
        "popis": "Správně popsán proces reklamace dle zákona o ochraně spotřebitele.",
        "hledat": ["reklamace", "reklamační", "vada zboží", "odpovědnost za vady"],
        "typ": "must_have",
    },
    {
        "id": "digitalni_obsah",
        "kategorie": "Základní náležitosti OP",
        "nazev": "Pravidla pro digitální obsah",
        "popis": "Pravidla pro digitální obsah a služby (aktualizace, licence).",
        "hledat": ["digitální obsah", "digitální služby", "licence", "aktualizace"],
        "typ": "nice_to_have",
    },
    {
        "id": "coi_adr",
        "kategorie": "Ochrana spotřebitele",
        "nazev": "Odkaz na ČOI jako ADR subjekt",
        "popis": "Musí být uveden odkaz na ČOI jako subjekt alternativního řešení sporů.",
        "hledat": ["ČOI", "česká obchodní inspekce", "mimosoudní řešení", "ADR"],
        "typ": "must_have",
    },
    {
        "id": "slevy_30_dni",
        "kategorie": "Ochrana spotřebitele",
        "nazev": "Pravidla pro slevy (30 dní)",
        "popis": "Správná pravidla pro slevy – referenční cena z posledních 30 dní.",
        "hledat": ["30 dní", "30 dnů", "referenční cena", "sleva", "původní cena"],
        "typ": "nice_to_have",
    },
    {
        "id": "gdpr_politika",
        "kategorie": "Ochrana osobních údajů",
        "nazev": "Samostatná GDPR politika",
        "popis": "Musí existovat samostatná politika ochrany osobních údajů.",
        "hledat": ["GDPR", "osobní údaje", "ochrana osobních údajů", "2016/679", "110/2019"],
        "typ": "must_have",
    },
    {
        "id": "spravce_udaju",
        "kategorie": "Ochrana osobních údajů",
        "nazev": "Správce osobních údajů",
        "popis": "Musí být uveden správce osobních údajů (IČO, sídlo).",
        "hledat": ["správce osobních údajů", "správce údajů", "zpracovatel"],
        "typ": "must_have",
    },
    {
        "id": "cookies_zasady",
        "kategorie": "Ochrana osobních údajů",
        "nazev": "Zásady používání cookies",
        "popis": "Musí být popsány zásady cookies (cookie lišta + nastavení).",
        "hledat": ["cookies", "cookie", "soubory cookies"],
        "typ": "must_have",
    },
    {
        "id": "prava_subjektu",
        "kategorie": "Ochrana osobních údajů",
        "nazev": "Práva subjektů údajů",
        "popis": "Musí být popsána práva subjektů (přístup, výmaz, přenositelnost).",
        "hledat": ["právo na přístup", "právo na výmaz", "být zapomenut", "přenositelnost", "právo na opravu"],
        "typ": "must_have",
    },
    {
        "id": "ceny_s_dph",
        "kategorie": "Daňové povinnosti",
        "nazev": "Ceny včetně DPH",
        "popis": "Ceny musí být správně uvedeny včetně DPH.",
        "hledat": ["včetně DPH", "vč. DPH", "s DPH", "235/2004"],
        "typ": "must_have",
    },
    {
        "id": "identifikace_podnikatele",
        "kategorie": "Technické a informační povinnosti",
        "nazev": "Identifikační údaje podnikatele",
        "popis": "Musí být uvedeno IČO, sídlo a rejstříkové údaje.",
        "hledat": ["IČO", "IČ:", "sídlo", "zapsáno", "obchodní rejstřík"],
        "typ": "must_have",
    },
    {
        "id": "kontakt_email_telefon",
        "kategorie": "Technické a informační povinnosti",
        "nazev": "Kontaktní e-mail a telefon",
        "popis": "Musí být uvedena kontaktní e-mailová adresa a telefonní číslo.",
        "hledat": ["@", "tel:", "telefon", "e-mail", "email"],
        "typ": "must_have",
    },
    {
        "id": "formulare_ke_stazeni",
        "kategorie": "Technické a informační povinnosti",
        "nazev": "Obchodní a reklamační formuláře",
        "popis": "Formuláře pro reklamaci a odstoupení od smlouvy musí být ke stažení.",
        "hledat": ["formulář", "ke stažení", "stáhnout", "vzorový formulář"],
        "typ": "nice_to_have",
    },
    {
        "id": "wcag_eaa",
        "kategorie": "Technické a informační povinnosti",
        "nazev": "Přístupnost dle WCAG 2.1 / EAA",
        "popis": "Web musí být přístupný dle WCAG 2.1 (European Accessibility Act od 2025).",
        "hledat": ["WCAG", "přístupnost", "EAA", "European Accessibility Act"],
        "typ": "nice_to_have",
    },
    {
        "id": "dsa_compliance",
        "kategorie": "Nové regulace EU",
        "nazev": "DSA (transparentnost obsahu)",
        "popis": "Splňuje požadavky DSA – transparentnost, nahlášení obsahu.",
        "hledat": ["DSA", "Digital Services Act", "nahlásit obsah", "transparentnost"],
        "typ": "nice_to_have",
    },
]

# ─── ZASTARALÉ REFERENCE (nesmí být přítomny) ──────────────────────────────────

OBSOLETE_REFS = [
    {
        "id": "stary_obcz",
        "text": "40/1964 Sb.",
        "duvod": "Starý občanský zákoník zrušen od 1. 1. 2014, nahrazen zákonem č. 89/2012 Sb.",
    },
    {
        "id": "obchodni_zakonik",
        "text": "513/1991 Sb.",
        "duvod": "Obchodní zákoník zrušen k 1. 1. 2014, právně neexistuje.",
    },
    {
        "id": "stary_gdpr",
        "text": "101/2000 Sb.",
        "duvod": "Zákon o ochraně osobních údajů nahrazen zákonem č. 110/2019 Sb. a GDPR.",
    },
    {
        "id": "eet",
        "text": "EET",
        "duvod": "EET bylo zrušeno v roce 2023, odkaz na EET je zastaralý.",
    },
    {
        "id": "vraceni_15_dni",
        "text": "15 dnů",
        "duvod": "Lhůta 15 dní pro vrácení zboží je nesprávná – platná lhůta je 14 dní (§ 1829 OZ).",
    },
    {
        "id": "paragraf_52",
        "text": "§ 52",
        "duvod": "§ 52–57 zákona č. 40/1964 Sb. jsou zrušeny spolu s celým starým OZ.",
    },
    {
        "id": "paragraf_53",
        "text": "§ 53",
        "duvod": "§ 52–57 zákona č. 40/1964 Sb. jsou zrušeny spolu s celým starým OZ.",
    },
    {
        "id": "cookies_480",
        "text": "480/2004",
        "duvod": "Zákon č. 480/2004 Sb. neřeší cookies – pouze nevyžádaná obchodní sdělení (emaily). Odkaz ve spojitosti s cookies je nevhodný.",
    },
    {
        "id": "stary_89_odst3",
        "text": "§ 89 odst. 3",
        "duvod": "§ 89 odst. 3 zákona č. 127/2005 Sb. ve znění do 31. 12. 2021 je neplatný (cookie lišta se řídí novelizovaným zněním).",
    },
]

# ─── FETCH HTML ────────────────────────────────────────────────────────────────

def fetch_html(url: str, timeout: int = 15) -> tuple[bool, str, str]:
    """Stáhne HTML stránku. Vrátí (úspěch, html_text, chybová_zpráva)."""
    if not url.startswith("http"):
        url = "https://" + url

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; OP-Validator/1.0)",
            "Accept-Language": "cs,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            for enc in ("utf-8", "windows-1250", "iso-8859-2"):
                try:
                    return True, raw.decode(enc), ""
                except UnicodeDecodeError:
                    continue
            return True, raw.decode("utf-8", errors="replace"), ""
    except urllib.error.HTTPError as e:
        return False, "", f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, "", f"Chyba připojení: {e.reason}"
    except Exception as e:
        return False, "", str(e)


def strip_html(html_text: str) -> str:
    """Odstraní HTML tagy, vrátí čistý text."""
    # Odstraň skripty a styly
    text = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text


# ─── KONTROLA ──────────────────────────────────────────────────────────────────

def kontrolovat_url(url: str) -> dict:
    """Provede kompletní kontrolu jedné URL. Vrátí dict s výsledky."""
    result = {
        "url": url,
        "ok": False,
        "chyba": None,
        "skore": 0,
        "max_skore": 0,
        "checklist": [],
        "zastarale": [],
        "souhrn": "",
        "plainText": "",  # Store plain text for searching
    }

    ok, html_text, err = fetch_html(url)
    if not ok:
        result["chyba"] = err
        result["souhrn"] = f"Stránku se nepodařilo načíst: {err}"
        return result

    plain = strip_html(html_text)
    plain_lower = plain.lower()
    result["plainText"] = plain  # Store plain text

    # ── checklist ──
    splneno = 0
    celkem_must = 0

    for item in CHECKLIST:
        nalezeno = any(
            kw.lower() in plain_lower for kw in item["hledat"]
        )
        stav = "✅ Splněno" if nalezeno else ("❌ Chybí" if item["typ"] == "must_have" else "⚠️ Chybí (doporučeno)")

        result["checklist"].append({
            "id": item["id"],
            "kategorie": item["kategorie"],
            "nazev": item["nazev"],
            "popis": item["popis"],
            "typ": item["typ"],
            "nalezeno": nalezeno,
            "stav": stav,
            "hledat": item["hledat"],  # Include keywords for search
        })

        if item["typ"] == "must_have":
            celkem_must += 1
            if nalezeno:
                splneno += 1

    result["skore"] = splneno
    result["max_skore"] = celkem_must

    # ── zastaralé reference ──
    for ref in OBSOLETE_REFS:
        if ref["text"].lower() in plain_lower:
            result["zastarale"].append({
                "id": ref["id"],
                "text": ref["text"],
                "duvod": ref["duvod"],
            })

    # ── souhrn ──
    pct = round(splneno / celkem_must * 100) if celkem_must else 0
    zastar_count = len(result["zastarale"])
    result["ok"] = True
    result["souhrn"] = (
        f"Splněno {splneno}/{celkem_must} povinných položek ({pct} %). "
        + (f"Nalezeno {zastar_count} zastaralých/neplatných odkazů." if zastar_count else "Žádné zastaralé odkazy nebyly nalezeny.")
    )

    return result


# ─── HTTP SERVER ───────────────────────────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Validátor obchodních podmínek e-shopu</title>
<style>
:root {
  --bg: #f0f4f8;
  --card: #ffffff;
  --primary: #1d4ed8;
  --primary-dark: #1e3a8a;
  --green: #15803d;
  --green-bg: #dcfce7;
  --red: #b91c1c;
  --red-bg: #fee2e2;
  --yellow: #b45309;
  --yellow-bg: #fef3c7;
  --gray: #6b7280;
  --border: #e5e7eb;
  --text: #111827;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--text); }
header {
  background: linear-gradient(135deg, var(--primary-dark), var(--primary));
  color: white; padding: 28px 32px;
}
header h1 { font-size: 26px; margin-bottom: 6px; }
header p { opacity: .8; font-size: 14px; }
main { max-width: 960px; margin: 32px auto; padding: 0 20px; }

.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 14px; padding: 24px; margin-bottom: 20px;
  box-shadow: 0 4px 16px rgba(0,0,0,.06);
}
.card h2 { font-size: 17px; margin-bottom: 16px; color: var(--primary-dark); }

.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab-btn {
  padding: 9px 20px; border: 2px solid var(--border); border-radius: 8px;
  background: white; cursor: pointer; font-size: 14px; font-weight: 600;
  transition: all .15s;
}
.tab-btn.active { border-color: var(--primary); background: var(--primary); color: white; }

.tab-pane { display: none; }
.tab-pane.active { display: block; }

input[type=text], input[type=url] {
  width: 100%; padding: 10px 14px; border: 1px solid var(--border);
  border-radius: 8px; font-size: 14px; margin-bottom: 12px;
  transition: border-color .15s;
}
input[type=text]:focus, input[type=url]:focus {
  outline: none; border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29,78,216,.15);
}

.drop-zone {
  border: 2px dashed var(--border); border-radius: 10px;
  padding: 32px; text-align: center; cursor: pointer;
  transition: all .15s; margin-bottom: 12px;
  color: var(--gray); font-size: 14px;
}
.drop-zone:hover, .drop-zone.drag-over { border-color: var(--primary); background: #eff6ff; }
.drop-zone input { display: none; }

.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 11px 24px; background: var(--primary); color: white;
  border: none; border-radius: 9px; font-size: 15px; font-weight: 700;
  cursor: pointer; transition: background .15s;
}
.btn:hover { background: var(--primary-dark); }
.btn:disabled { opacity: .5; cursor: not-allowed; }

.url-list { font-size: 13px; color: var(--gray); margin-top: 8px; }
.url-pill {
  display: inline-block; background: #eff6ff; border: 1px solid #bfdbfe;
  border-radius: 6px; padding: 3px 10px; margin: 2px; font-size: 12px;
}

#progress-wrap { display: none; margin-top: 16px; }
.progress-bar-bg {
  background: var(--border); border-radius: 999px; height: 10px;
  overflow: hidden; margin-bottom: 8px;
}
.progress-bar-fill {
  height: 100%; background: var(--primary);
  border-radius: 999px; transition: width .3s;
}
#progress-text { font-size: 13px; color: var(--gray); }

/* results */
#results { margin-top: 24px; }
.result-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; margin-bottom: 16px; overflow: hidden;
}
.result-header {
  padding: 14px 18px; display: flex; align-items: center;
  justify-content: space-between; cursor: pointer; gap: 12px;
}
.result-header:hover { background: #f9fafb; }
.result-url { font-size: 14px; font-weight: 600; word-break: break-all; }
.result-summary { font-size: 12px; color: var(--gray); margin-top: 2px; }
.score-badge {
  flex-shrink: 0; padding: 5px 12px; border-radius: 999px;
  font-size: 13px; font-weight: 700;
}
.score-good { background: var(--green-bg); color: var(--green); }
.score-mid { background: var(--yellow-bg); color: var(--yellow); }
.score-bad { background: var(--red-bg); color: var(--red); }
.score-err { background: #f3f4f6; color: var(--gray); }
.result-body { display: none; padding: 0 18px 18px; }
.result-body.open { display: block; }

.section-title { font-size: 13px; font-weight: 700; margin: 14px 0 8px; text-transform: uppercase; letter-spacing: .05em; color: var(--gray); }

.check-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.check-table th { text-align: left; padding: 7px 10px; background: #f9fafb; color: var(--gray); font-size: 12px; border-bottom: 1px solid var(--border); }
.check-table td { padding: 7px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
.check-table tr:last-child td { border-bottom: none; }
.check-table tr:hover td { background: #fafafa; }

.tag-must { color: var(--red); font-size: 11px; font-weight: 700; }
.tag-nice { color: var(--yellow); font-size: 11px; }

.obsolete-item {
  background: var(--red-bg); border: 1px solid #fca5a5;
  border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; font-size: 13px;
}
.obsolete-item strong { color: var(--red); }

.no-obsolete {
  background: var(--green-bg); color: var(--green);
  border-radius: 8px; padding: 10px 14px; font-size: 13px;
}

.spinner {
  display: inline-block; width: 18px; height: 18px;
  border: 3px solid rgba(255,255,255,.4); border-top-color: white;
  border-radius: 50%; animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Search feature */
#search-wrap { display: none; margin-top: 32px; }
.search-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 14px; padding: 24px; margin-bottom: 20px;
  box-shadow: 0 4px 16px rgba(0,0,0,.06);
}
.search-input-group {
  display: flex; gap: 12px; margin-bottom: 16px;
}
.search-input-group input {
  flex: 1; padding: 10px 14px; border: 1px solid var(--border);
  border-radius: 8px; font-size: 14px;
  transition: border-color .15s;
}
.search-input-group input:focus {
  outline: none; border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29,78,216,.15);
}
.search-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px; background: var(--primary); color: white;
  border: none; border-radius: 8px; font-size: 14px; font-weight: 700;
  cursor: pointer; transition: background .15s;
}
.search-btn:hover { background: var(--primary-dark); }
.search-btn:disabled { opacity: .5; cursor: not-allowed; }

.search-results {
  margin-top: 16px;
}
.search-result-item {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
  font-size: 13px;
}
.search-result-item.found {
  border-left: 4px solid var(--green); background: #fafafa;
}
.search-result-item.not-found {
  border-left: 4px solid var(--red); background: #fafafa;
}
.search-result-url {
  font-weight: 600; color: var(--primary); word-break: break-all;
  margin-bottom: 4px; font-size: 12px;
}
.search-result-status {
  display: flex; align-items: center; gap: 6px; font-size: 13px;
}
.search-result-status.found { color: var(--green); }
.search-result-status.not-found { color: var(--red); }

.search-summary {
  background: #f9fafb; border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px; margin-bottom: 16px;
  font-size: 13px; font-weight: 600;
}
</style>
</head>
<body>
<header>
  <h1>Validátor obchodních podmínek e-shopu</h1>
  <p>Automatická kontrola OP podle platné legislativy ČR a EU</p>
</header>

<main>
  <div class="card">
    <h2>Zadejte URL obchodních podmínek</h2>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('url')">Zadat URL ručně</button>
      <button class="tab-btn" onclick="switchTab('csv')">Nahrát CSV soubor</button>
    </div>

    <!-- TAB: ruční URL -->
    <div class="tab-pane active" id="tab-url">
      <input type="url" id="manual-url" placeholder="https://www.example.cz/obchodni-podminky" />
      <div class="url-list" id="url-list-manual"></div>
    </div>

    <!-- TAB: CSV -->
    <div class="tab-pane" id="tab-csv">
      <div class="drop-zone" id="drop-zone" onclick="document.getElementById('csv-input').click()">
        <input type="file" id="csv-input" accept=".csv,.txt" onchange="handleFile(event)" />
        <div style="font-size:32px;margin-bottom:8px">📂</div>
        <strong>Klikněte nebo přetáhněte soubor CSV</strong><br>
        Jeden řádek = jedna URL obchodních podmínek
      </div>
      <div class="url-list" id="url-list-csv"></div>
    </div>

    <button class="btn" id="btn-run" onclick="spustit()">
      <span id="btn-icon">▶</span>
      <span id="btn-text">Spustit kontrolu</span>
    </button>

    <div id="progress-wrap">
      <div class="progress-bar-bg"><div class="progress-bar-fill" id="progress-fill" style="width:0%"></div></div>
      <div id="progress-text">Inicializuji…</div>
    </div>
  </div>

  <div id="results"></div>

  <div id="search-wrap">
    <div class="search-card">
      <h2>🔍 Hledat výrazy v OP</h2>
      <p style="font-size: 12px; color: var(--gray); margin-bottom: 16px;">Zadejte výraz (např. "89/2012"), který chcete vyhledat ve všech zkontrolovaných stránkách.</p>
      <div class="search-input-group">
        <input type="text" id="search-input" placeholder="Zadejte výraz k vyhledání..." />
        <button class="search-btn" onclick="performSearch()" id="search-btn">Hledat</button>
      </div>
      <div id="search-results-container"></div>
    </div>
  </div>
</main>

<script>
let csvUrls = [];
let validationResults = []; // Store all results for searching

function switchTab(t) {
  document.querySelectorAll('.tab-btn').forEach((b,i) => b.classList.toggle('active', (i===0&&t==='url')||(i===1&&t==='csv')));
  document.getElementById('tab-url').classList.toggle('active', t==='url');
  document.getElementById('tab-csv').classList.toggle('active', t==='csv');
}

function handleFile(e) {
  const f = e.target.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = ev => {
    const text = ev.target.result;
    csvUrls = parseCSV(text);
    const el = document.getElementById('url-list-csv');
    el.innerHTML = csvUrls.map(u => `<span class="url-pill">${u}</span>`).join('');
  };
  reader.readAsText(f, 'UTF-8');
}

function parseCSV(text) {
  const lines = text.split('\n');
  const urls = [];
  
  // Try to detect if it's a proper CSV with headers
  let isProperCSV = false;
  let urlColumnIndex = -1;
  
  // Check first line for headers (looking for 'URL', 'http' or similar)
  if (lines.length > 0) {
    const firstLine = lines[0].toLowerCase();
    if (firstLine.includes('url') || firstLine.includes('link') || firstLine.includes('op')) {
      isProperCSV = true;
      // Find which column contains URLs
      const headers = parseCSVLine(lines[0]);
      urlColumnIndex = headers.findIndex(h => 
        h.toLowerCase().includes('url') || 
        h.toLowerCase().includes('op') ||
        h.toLowerCase().includes('link')
      );
    }
  }
  
  // Process lines
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    
    if (isProperCSV && urlColumnIndex >= 0) {
      const fields = parseCSVLine(line);
      if (fields[urlColumnIndex]) {
        const url = fields[urlColumnIndex].trim();
        if (url && url.startsWith('http')) {
          urls.push(url);
        }
      }
    } else {
      // Fallback: simple parsing for plain text or single-column format
      const url = line.trim().replace(/^"|"$/g, '');
      if (url && url.startsWith('http')) {
        urls.push(url);
      }
    }
  }
  
  return urls;
}

function parseCSVLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;
  
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    const nextChar = line[i + 1];
    
    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  
  result.push(current);
  return result.map(f => f.trim());
}

// Drag & drop
const dz = document.getElementById('drop-zone');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
dz.addEventListener('drop', e => {
  e.preventDefault(); dz.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) {
    document.getElementById('csv-input').files = e.dataTransfer.files;
    handleFile({target: {files: [f]}});
  }
});

function getUrls() {
  const tab = document.getElementById('tab-url').classList.contains('active') ? 'url' : 'csv';
  if (tab === 'url') {
    const v = document.getElementById('manual-url').value.trim();
    return v ? [v] : [];
  }
  return csvUrls;
}

async function spustit() {
  const urls = getUrls();
  if (!urls.length) { alert('Zadejte alespoň jednu URL.'); return; }

  const btn = document.getElementById('btn-run');
  btn.disabled = true;
  document.getElementById('btn-icon').innerHTML = '<span class="spinner"></span>';
  document.getElementById('btn-text').textContent = 'Kontroluji…';
  document.getElementById('progress-wrap').style.display = 'block';
  document.getElementById('results').innerHTML = '';
  document.getElementById('search-wrap').style.display = 'none';
  validationResults = [];

  const results = [];
  for (let i = 0; i < urls.length; i++) {
    const url = urls[i];
    document.getElementById('progress-text').textContent = `Kontroluji ${i+1}/${urls.length}: ${url}`;
    document.getElementById('progress-fill').style.width = `${Math.round((i/urls.length)*100)}%`;

    try {
      const resp = await fetch('/api/check', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url})
      });
      const data = await resp.json();
      validationResults.push(data);
      results.push(data);
      renderResult(data);
    } catch(e) {
      const errResult = {url, ok: false, chyba: e.message, checklist: [], zastarale: [], souhrn: '', skore: 0, max_skore: 0, plainText: ''};
      validationResults.push(errResult);
      renderResult(errResult);
    }
  }

  document.getElementById('progress-fill').style.width = '100%';
  document.getElementById('progress-text').textContent = `Hotovo! Zkontrolováno ${urls.length} URL.`;
  btn.disabled = false;
  document.getElementById('btn-icon').textContent = '▶';
  document.getElementById('btn-text').textContent = 'Spustit kontrolu';
  
  // Show search section after validation
  document.getElementById('search-wrap').style.display = 'block';
  document.getElementById('search-input').value = '';
  document.getElementById('search-results-container').innerHTML = '';
}

function renderResult(data) {
  const pct = data.max_skore ? Math.round(data.skore/data.max_skore*100) : 0;
  let scoreClass = 'score-err', scoreLabel = 'Chyba';
  if (data.ok) {
    if (pct >= 80) { scoreClass = 'score-good'; scoreLabel = pct+'%'; }
    else if (pct >= 50) { scoreClass = 'score-mid'; scoreLabel = pct+'%'; }
    else { scoreClass = 'score-bad'; scoreLabel = pct+'%'; }
  }

  // Seskupit checklist podle kategorie
  const byKat = {};
  (data.checklist||[]).forEach(c => {
    if (!byKat[c.kategorie]) byKat[c.kategorie] = [];
    byKat[c.kategorie].push(c);
  });

  let checkHtml = '';
  for (const [kat, items] of Object.entries(byKat)) {
    checkHtml += `<div class="section-title">${kat}</div>
    <table class="check-table">
      <thead><tr><th>Stav</th><th>Položka</th><th>Typ</th></tr></thead>
      <tbody>`;
    items.forEach(c => {
      checkHtml += `<tr>
        <td>${c.stav}</td>
        <td><strong>${c.nazev}</strong><br><span style="color:#6b7280;font-size:12px">${c.popis}</span></td>
        <td>${c.typ === 'must_have' ? '<span class="tag-must">POVINNÉ</span>' : '<span class="tag-nice">doporučeno</span>'}</td>
      </tr>`;
    });
    checkHtml += '</tbody></table>';
  }

  let obsoleteHtml = '';
  if (data.zastarale && data.zastarale.length) {
    data.zastarale.forEach(z => {
      obsoleteHtml += `<div class="obsolete-item"><strong>⚠ Nalezeno: "${z.text}"</strong><br>${z.duvod}</div>`;
    });
  } else {
    obsoleteHtml = '<div class="no-obsolete">✅ Žádné zastaralé ani neplatné legislativní odkazy nebyly nalezeny.</div>';
  }

  const id = 'res_' + Math.random().toString(36).slice(2);
  const html = `
  <div class="result-card">
    <div class="result-header" onclick="toggleBody('${id}')">
      <div>
        <div class="result-url">${data.url}</div>
        <div class="result-summary">${data.chyba || data.souhrn}</div>
      </div>
      <div class="score-badge ${scoreClass}">${scoreLabel}</div>
    </div>
    <div class="result-body" id="${id}">
      ${data.ok ? `
        <div class="section-title">🗂 Checklist</div>
        ${checkHtml}
        <div class="section-title" style="margin-top:20px">🚫 Zastaralé / neplatné reference</div>
        ${obsoleteHtml}
      ` : `<p style="color:var(--red);padding:8px 0">Chyba: ${data.chyba}</p>`}
    </div>
  </div>`;

  document.getElementById('results').insertAdjacentHTML('beforeend', html);
}

function toggleBody(id) {
  document.getElementById(id).classList.toggle('open');
}

function performSearch() {
  const searchInput = document.getElementById('search-input').value.trim();
  if (!searchInput) {
    alert('Zadejte výraz k vyhledání.');
    return;
  }

  const searchLower = searchInput.toLowerCase();
  const resultsContainer = document.getElementById('search-results-container');
  resultsContainer.innerHTML = '';

  let foundCount = 0;
  let notFoundCount = 0;
  const resultItems = [];

  validationResults.forEach(result => {
    let isFound = false;

    if (result.ok) {
      // Use stored plainText as primary source
      if (result.plainText) {
        isFound = result.plainText.toLowerCase().includes(searchLower);
      }
      
      // Fallback: also check checklist items and obsolete references
      if (!isFound && result.checklist) {
        for (let item of result.checklist) {
          if (item.hledat && item.hledat.some(kw => kw.toLowerCase().includes(searchLower))) {
            isFound = true;
            break;
          }
        }
      }
      
      // Also check obsolete references
      if (!isFound && result.zastarale) {
        for (let obsolete of result.zastarale) {
          if (obsolete.text.toLowerCase().includes(searchLower)) {
            isFound = true;
            break;
          }
        }
      }
    }

    if (isFound) {
      foundCount++;
      resultItems.push({
        url: result.url,
        found: true
      });
    } else {
      notFoundCount++;
      resultItems.push({
        url: result.url,
        found: false
      });
    }
  });

  // Render summary
  const summary = document.createElement('div');
  summary.className = 'search-summary';
  summary.innerHTML = `
    Výraz <strong>"${escapeHtml(searchInput)}"</strong> byl nalezen v <strong>${foundCount}</strong> URL.
    ${notFoundCount > 0 ? `Nenalezen v <strong>${notFoundCount}</strong> URL.` : ''}
  `;
  resultsContainer.appendChild(summary);

  // Render found results
  if (foundCount > 0) {
    const foundTitle = document.createElement('div');
    foundTitle.className = 'section-title';
    foundTitle.style.marginBottom = '8px';
    foundTitle.innerHTML = '✅ Nalezeno v:';
    resultsContainer.appendChild(foundTitle);

    resultItems.filter(r => r.found).forEach(item => {
      const div = document.createElement('div');
      div.className = 'search-result-item found';
      div.innerHTML = `
        <div class="search-result-url">${escapeHtml(item.url)}</div>
        <div class="search-result-status found">✓ Nalezeno</div>
      `;
      resultsContainer.appendChild(div);
    });
  }

  // Render not found results
  if (notFoundCount > 0) {
    const notFoundTitle = document.createElement('div');
    notFoundTitle.className = 'section-title';
    notFoundTitle.style.marginBottom = '8px';
    notFoundTitle.style.marginTop = '16px';
    notFoundTitle.innerHTML = '❌ Nenalezeno v:';
    resultsContainer.appendChild(notFoundTitle);

    resultItems.filter(r => !r.found).forEach(item => {
      const div = document.createElement('div');
      div.className = 'search-result-item not-found';
      div.innerHTML = `
        <div class="search-result-url">${escapeHtml(item.url)}</div>
        <div class="search-result-status not-found">✗ Nenalezeno</div>
      `;
      resultsContainer.appendChild(div);
    });
  }
}

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

// Enter pro ruční URL
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('manual-url').addEventListener('keydown', e => {
    if (e.key === 'Enter') spustit();
  });
  document.getElementById('search-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') performSearch();
  });
});
</script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # potlač výstup do konzole

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/check":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                url = data.get("url", "").strip()
                if not url:
                    self._json({"error": "Chybí URL"}, 400)
                    return
                result = kontrolovat_url(url)
                self._json(result)
            except Exception as e:
                self._json({"error": str(e)}, 500)
        else:
            self._json({"error": "Not found"}, 404)

    def _json(self, data: dict, status: int = 200):
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    PORT = 8765
    print(f"\n{'='*55}")
    print(f"  Validátor obchodních podmínek e-shopu")
    print(f"{'='*55}")
    print(f"  Otevřete: http://localhost:{PORT}")
    print(f"  Ukončení: Ctrl+C")
    print(f"{'='*55}\n")

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer zastaven.")


if __name__ == "__main__":
    main()
