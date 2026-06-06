"""
Lunden ÖBK P2013 – Komplett Statistikapp v2
============================================
Kombinerar:
  • Fogis  – matchstatistik per serie + spelare
  • laget.se – närvaro per spelare (synkas manuellt via admin)
  • Planeringsverktyg – välj spelare per kommande match med matchbalans-vy

Driftsätt på Render.com (se README.md).
"""

import os, json, re
from datetime import datetime
from collections import defaultdict
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)

# ── Fogis-klient ──────────────────────────────────────────────────────────────
try:
    from fogis_api_client import FogisApiClient
    from fogis_api_client.fogis_api_client import FogisLoginError, FogisAPIRequestError
    FOGIS_AVAILABLE = True
except ImportError:
    FOGIS_AVAILABLE = False

# ── BeautifulSoup för laget.se-scraping ───────────────────────────────────────
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

import requests as req_lib   # för laget.se HTTP-anrop

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "lunden-obk-p2013-v2-byt-mig")
APP_USERNAME = os.environ.get("APP_USERNAME", "lunden")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "obk2013")

# ── Konfiguration ─────────────────────────────────────────────────────────────

CLUB_NAME  = "Lunden"
LAGETSE_SLUG = os.environ.get("LAGETSE_SLUG", "Lundenobkpf13")   # din laget.se-URL

# ── Spelarstatistik (hämtad från MinFotboll, uppdateras via SvFF API) ────────
# Format: {namn: {serie_id: {mal, assist, gult, rott, matcher}}}
# Synkas via /sync/spelstat (POST) eller redigeras manuellt här som fallback
SPELSTAT_FALLBACK = [
    # === LATT C (Gron lag) - Varserie 2026 ===
    {"namn":"Lionel Chougui Hulle",    "serie":"latt_c","mal":2,"assist":1,"gult":0,"rott":0,"matcher":2},
    {"namn":"William Palicka",         "serie":"latt_c","mal":2,"assist":0,"gult":0,"rott":0,"matcher":3},
    {"namn":"William Darhoff",         "serie":"latt_c","mal":2,"assist":1,"gult":0,"rott":0,"matcher":2},
    {"namn":"Zlatan Muslimovic",       "serie":"latt_c","mal":2,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Nathan Lichtneckert",     "serie":"latt_c","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Morris Lind-Myrbeck",     "serie":"latt_c","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Wilhelm Gillmor",         "serie":"latt_c","mal":1,"assist":1,"gult":0,"rott":0,"matcher":1},
    {"namn":"Frans Meurling Bigestans","serie":"latt_c","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Veiron Stickfors",        "serie":"latt_c","mal":0,"assist":2,"gult":0,"rott":0,"matcher":2},
    {"namn":"Holger Weiler",           "serie":"latt_c","mal":0,"assist":1,"gult":0,"rott":0,"matcher":1},
    {"namn":"Alexander Johansson",     "serie":"latt_c","mal":0,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Anton Klasgren",          "serie":"latt_c","mal":0,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Liam Laveback",           "serie":"latt_c","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    # === LATT E (Svart lag) - Varserie 2026 ===
    {"namn":"Algot Bergman",           "serie":"latt_e","mal":3,"assist":1,"gult":0,"rott":0,"matcher":3},
    {"namn":"Holger Weiler",           "serie":"latt_e","mal":2,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Sam Hossein Khodadai",    "serie":"latt_e","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"William Andren",          "serie":"latt_e","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Rasmus Hammarstrom",      "serie":"latt_e","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Amadeus Dalerstedt",      "serie":"latt_e","mal":1,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"William Darhoff",         "serie":"latt_e","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Liam Laveback",           "serie":"latt_e","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"John Wiklund",            "serie":"latt_e","mal":1,"assist":1,"gult":0,"rott":0,"matcher":1},
    {"namn":"El Kadi",                 "serie":"latt_e","mal":0,"assist":1,"gult":0,"rott":0,"matcher":1},
    {"namn":"Veiron Stickfors",        "serie":"latt_e","mal":0,"assist":0,"gult":0,"rott":1,"matcher":2},
    {"namn":"Elias Rocha",             "serie":"latt_e","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    # === MEDEL A (Vit lag) - Varserie 2026 ===
    {"namn":"Alexander Johansson",     "serie":"medel_a","mal":7,"assist":0,"gult":0,"rott":0,"matcher":4},
    {"namn":"Lionel Chougui Hulle",    "serie":"medel_a","mal":4,"assist":1,"gult":0,"rott":0,"matcher":3},
    {"namn":"Anton Klasgren",          "serie":"medel_a","mal":4,"assist":0,"gult":0,"rott":0,"matcher":3},
    {"namn":"William Palicka",         "serie":"medel_a","mal":3,"assist":1,"gult":0,"rott":0,"matcher":3},
    {"namn":"Adrian Simunovic",        "serie":"medel_a","mal":3,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Veiron Stickfors",        "serie":"medel_a","mal":2,"assist":2,"gult":0,"rott":0,"matcher":2},
    {"namn":"Algot Bergman",           "serie":"medel_a","mal":2,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Holger Weiler",           "serie":"medel_a","mal":2,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Sander Wallin",           "serie":"medel_a","mal":1,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Addi Fazlic",             "serie":"medel_a","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Nils Dahlqvist",          "serie":"medel_a","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Frans Meurling Bigestans","serie":"medel_a","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"William Darhoff",         "serie":"medel_a","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"John Wiklund",            "serie":"medel_a","mal":0,"assist":1,"gult":0,"rott":0,"matcher":1},
    {"namn":"Liam Laveback",           "serie":"medel_a","mal":0,"assist":0,"gult":0,"rott":0,"matcher":2},
    # === FAIR PLAY-SERIEN 2026 ===
    {"namn":"Liam Laveback",           "serie":"fair_play","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Sam Hossein Khodadai",    "serie":"fair_play","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"William Palicka",         "serie":"fair_play","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Algot Bergman",           "serie":"fair_play","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Wilhelm Gillmor",         "serie":"fair_play","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    # === TRANINGSMATCHER / HOST 2025 ===
    {"namn":"Frans Meurling Bigestans","serie":"traning","mal":4,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Alexander Johansson",     "serie":"traning","mal":3,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Armand Kurti",            "serie":"traning","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Liam Laveback",           "serie":"traning","mal":1,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"William Palicka",         "serie":"traning","mal":1,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Adrian Simunovic",        "serie":"traning","mal":1,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Nathan Lichtneckert",     "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Holger Weiler",           "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Lionel Chougui Hulle",    "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"William Darhoff",         "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Hugo Sallstrom",          "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":2},
    {"namn":"Veiron Stickfors",        "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Leon Gullmarsvik",        "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Sander Wallin",           "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Amadeus Dalerstedt",      "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
    {"namn":"Morris Lind-Myrbeck",     "serie":"traning","mal":0,"assist":0,"gult":0,"rott":0,"matcher":1},
]

SERIER = {
    "latt_e":    {"etikett": "Lätt E",    "nyckelord": ["lätt", "grupp e"],  "färg": "#a8e063"},
    "latt_c":    {"etikett": "Lätt C",    "nyckelord": ["lätt", "grupp c"],  "färg": "#7ec8e3"},
    "medel_a":   {"etikett": "Medel A",   "nyckelord": ["medel", "grupp a"], "färg": "#f0a868"},
    "fair_play": {"etikett": "Fair Play", "nyckelord": ["fair play"],        "färg": "#c084fc"},
    "traning":   {"etikett": "Träning",   "nyckelord": ["träning","träningsmatch"], "färg": "#94a3b8"},
}

# Fil för att spara synkad laget.se-data och planeringsdata
DATA_FILE     = os.environ.get("DATA_FILE", "lunden_data.json")
PLANNING_FILE = os.environ.get("PLANNING_FILE", "lunden_planning.json")

# ── Datalagring (enkel JSON-fil) ──────────────────────────────────────────────

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"narvaro": {}, "spelare": [], "synkad": None}

def save_data(d: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def load_planning() -> dict:
    if os.path.exists(PLANNING_FILE):
        with open(PLANNING_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"matcher": {}}   # {match_id: {serie, datum, motstandare, spelare: [namn]}}

def save_planning(p: dict):
    with open(PLANNING_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)

# ── Fogis-hjälpfunktioner ─────────────────────────────────────────────────────

def är_lunden(m: dict) -> bool:
    return CLUB_NAME.lower() in (m.get("hemmalag","") or "").lower() or \
           CLUB_NAME.lower() in (m.get("bortalag","")  or "").lower()

def är_hemma(m: dict) -> bool:
    return CLUB_NAME.lower() in (m.get("hemmalag","") or "").lower()

def serie_id(m: dict) -> str | None:
    serie = ""
    for k in ("tavling","tavlingNamn","serie","tavlingsnamn"):
        v = m.get(k)
        if v: serie = str(v).lower(); break
    for sid, info in SERIER.items():
        if all(nk.lower() in serie for nk in info["nyckelord"]):
            return sid
    return None

def hämta_mål(m: dict):
    hm = bm = None
    for k in ("hemamål","hemmamål","hemmamal","homeGoals"):
        v = m.get(k)
        if v is not None: hm = v; break
    for k in ("bortamål","bortamal","awayGoals"):
        v = m.get(k)
        if v is not None: bm = v; break
    try: return int(hm), int(bm)
    except: return None, None

def är_spelad(m: dict) -> bool:
    hm, bm = hämta_mål(m)
    if hm is not None: return True
    return "spelade" in (m.get("status","") or "").lower()

def beräkna_stats(matcher):
    sp=v=o=f=gj=ins=0
    for m in matcher:
        if not är_spelad(m): continue
        hm, bm = hämta_mål(m)
        if hm is None: continue
        hemma = är_hemma(m)
        våra = hm if hemma else bm
        mot  = bm if hemma else hm
        sp+=1; gj+=våra; ins+=mot
        if våra>mot: v+=1
        elif våra==mot: o+=1
        else: f+=1
    return dict(spelade=sp,vinster=v,oavgjorda=o,förluster=f,
                gjorda=gj,insläppta=ins,skillnad=gj-ins,poäng=v*3+o)

def formatera_match(m: dict) -> dict:
    hm_raw, bm_raw = hämta_mål(m)
    spelad  = är_spelad(m)
    hemma   = är_hemma(m)
    sid     = serie_id(m)
    serie   = SERIER[sid]["etikett"] if sid else "Okänd serie"

    if spelad and hm_raw is not None:
        våra = hm_raw if hemma else bm_raw
        mot  = bm_raw if hemma else hm_raw
        vof  = "V" if våra>mot else ("O" if våra==mot else "F")
        css  = {"V":"win","O":"draw","F":"loss"}[vof]
        res  = f"{hm_raw}–{bm_raw}"
    else:
        vof,css,res = "–","upcoming","–"

    datum_raw = m.get("datum") or m.get("matchDatum","")
    try:
        dt = datetime.strptime(datum_raw[:10], "%Y-%m-%d")
        datum_vis = dt.strftime("%-d %b")
        mån       = dt.month
        datum_sort = datum_raw[:10]
    except:
        datum_vis = datum_raw[:10]
        mån = 0
        datum_sort = datum_raw[:10]

    tid = (m.get("tid") or m.get("matchTid",""))[:5]

    return dict(datum=datum_vis, datum_sort=datum_sort, mån=mån, tid=tid,
                hemmalag=m.get("hemmalag","?"), bortalag=m.get("bortalag","?"),
                resultat=res, vof=vof, css=css, hemma=hemma,
                arena=m.get("arena") or m.get("anlaggning",""),
                spelad=spelad, serie=serie, serie_id=sid or "")

def bygg_fogis_spelares(matcher: list) -> list:
    """Räknar Fogis matchprotokoll-närvaro per spelare per serie."""
    data = defaultdict(lambda: defaultdict(int))
    for m in matcher:
        if not är_spelad(m): continue
        sid = serie_id(m)
        if not sid: continue
        hemma = är_hemma(m)
        key   = "hemmalagSpelare" if hemma else "bortalagSpelare"
        lista = m.get("spelare") or m.get(key) or m.get("players") or []
        for sp in lista:
            namn = (sp.get("namn") or sp.get("name") or
                    f"{sp.get('fornamn','')} {sp.get('efternamn','')}".strip() or "?")
            if namn and namn != "?":
                data[namn][sid] += 1
    rows = []
    for namn, serier in sorted(data.items()):
        totalt = sum(serier.values())
        rows.append(dict(namn=namn, serier=dict(serier), totalt=totalt))
    return sorted(rows, key=lambda x: -x["totalt"])

# ── laget.se-hjälpfunktioner ──────────────────────────────────────────────────

def hämta_laget_spelare(slug: str) -> list:
    """Hämtar spelarförteckning från publik laget.se-sida."""
    url = f"https://www.laget.se/{slug}/Troop"
    try:
        resp = req_lib.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        return []
    if not BS4_AVAILABLE:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    spelare = []
    for row in soup.select("table.troop tr, .player-row, tr[class*='player']"):
        cells = row.find_all("td")
        if len(cells) < 2: continue
        nummer = cells[0].get_text(strip=True)
        namn   = cells[1].get_text(strip=True)
        pos    = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        if namn:
            spelare.append(dict(nummer=nummer, namn=namn, position=pos))
    return spelare

def parsea_narvaro_text(text: str) -> dict:
    """
    Parsear get_page_text-output från Calendar/Edit/{id}.
    Returnerar {namn: "Deltar"|"Deltar ej"|"Ej svarat"}.
    """
    narvaro = {}
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    i = 0
    STATUS_ORD = {"Deltar", "Deltar ej", "Ej svarat"}
    while i < len(lines):
        line = lines[i]
        # Hoppa över rubrik-rader
        if line in ("Namn","Kommentar","Anmälan","Närvaro","Deltagare","Ledare",
                    "Lägg till gäst","Sätt alla 'Deltar' som närvarande"):
            i += 1; continue
        # Kolla om nästa rad (hoppa kommentarer) är status
        j = i + 1
        kommentar = ""
        while j < len(lines) and lines[j] not in STATUS_ORD and j < i + 3:
            kommentar = lines[j]
            j += 1
        if j < len(lines) and lines[j] in STATUS_ORD:
            namn = line
            # Filtrera bort lag-suffixer (- LundenOBK-P-14 etc.)
            if " - " in namn:
                namn = namn.split(" - ")[0].strip()
            if namn and len(namn) > 2:
                narvaro[namn] = lines[j]
            i = j + 1
        else:
            i += 1
    return narvaro

# ── Routes: Auth ──────────────────────────────────────────────────────────────

@app.route("/", methods=["GET","POST"])
def login():
    if "inloggad" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        if username == APP_USERNAME and password == APP_PASSWORD:
            session["inloggad"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        else:
            flash("Fel användarnamn eller lösenord.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── Route: Dashboard ──────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    if "inloggad" not in session:
        return redirect(url_for("login"))

    # SvFF API ansluts nar nyckeln godkants - tills dess tomma listor
    alla_matcher = []
    lunden = []

    # Per serie
    serie_data = {}
    for sid, info in SERIER.items():
        sm = [m for m in lunden if serie_id(m) == sid]
        spelade  = [m for m in sm if är_spelad(m)]
        kommande = [m for m in sm if not är_spelad(m)]
        fm_alla  = sorted([formatera_match(m) for m in sm], key=lambda x: x["datum_sort"])
        serie_data[sid] = dict(
            etikett=info["etikett"], färg=info["färg"],
            stats=beräkna_stats(sm),
            matcher=fm_alla,
            spelade_antal=len(spelade),
            kommande_antal=len(kommande),
            kommande=[formatera_match(m) for m in kommande],
        )

    # Fogis spelarstatistik
    fogis_spelare = bygg_fogis_spelares(lunden)

    # laget.se-data (från cach)
    cached      = load_data()
    laget_narav = cached.get("narvaro", {})   # {namn: {total_pct, traning, match}}
    laget_spl   = cached.get("spelare", [])   # [{nummer, namn, position}]
    synkad      = cached.get("synkad")

    # Slå ihop spelar-info: laget.se + Fogis
    alla_spelare = slå_ihop_spelare(fogis_spelare, laget_narav, laget_spl)

    # Planering
    planning = load_planning()
    kommande_matcher = bygg_kommande_matcher(serie_data)
    spelstat = bygg_spelstat(cached)

    return render_template("dashboard.html",
        serie_data=serie_data,
        serier=SERIER,
        alla_spelare=alla_spelare,
        spelstat=spelstat,
        synkad=synkad,
        planning=planning,
        kommande_matcher=kommande_matcher,
        username=session.get("username",""),
        uppdaterad=datetime.now().strftime("%H:%M"),
    )

def slå_ihop_spelare(fogis_spl, laget_narav, laget_spl) -> list:
    """Kombinerar data från Fogis och laget.se per spelare."""
    # Bygg namnindex från laget.se spelarförteckning
    laget_index = {sp["namn"].lower(): sp for sp in laget_spl}

    # Samla alla namn
    alla_namn = set(sp["namn"] for sp in fogis_spl)
    alla_namn |= set(laget_narav.keys())
    alla_namn |= set(sp["namn"] for sp in laget_spl)

    resultat = []
    for namn in sorted(alla_namn):
        fogis_row = next((s for s in fogis_spl if s["namn"]==namn), None)
        laget_row = laget_index.get(namn.lower(), {})
        narav_row = laget_narav.get(namn, {})

        resultat.append(dict(
            namn=namn,
            nummer=laget_row.get("nummer",""),
            position=laget_row.get("position",""),
            # Fogis: matcher per serie
            fogis_serier=fogis_row["serier"] if fogis_row else {},
            fogis_totalt=fogis_row["totalt"]  if fogis_row else 0,
            # laget.se: närvaro
            narvaro_pct=narav_row.get("pct", None),
            narvaro_traning=narav_row.get("traning", None),
            narvaro_match=narav_row.get("match", None),
            # Planerade matcher (räknas in i planeringsverktyget)
            planerade=0,
        ))
    return sorted(resultat, key=lambda x: (x["nummer"] or "99").zfill(3))

def bygg_spelstat(cached_data: dict) -> list:
    """
    Bygger samlad spelarstatistik (mal, assist, kort) per spelare totalt + per serie.
    Kalla fran cached spelstat om tillganglig, annars fallback.
    """
    rader = cached_data.get("spelstat", SPELSTAT_FALLBACK)
    # Aggregera per spelare
    index = {}
    for r in rader:
        namn = r["namn"]
        serie = r.get("serie","")
        if namn not in index:
            index[namn] = {
                "namn": namn,
                "nummer": r.get("nummer",""),
                "serier": {},
                "mal_tot": 0, "assist_tot": 0,
                "gult_tot": 0, "rott_tot": 0, "matcher_tot": 0
            }
        sp = index[namn]
        sid = serie
        if sid:
            if sid not in sp["serier"]:
                sp["serier"][sid] = {"mal":0,"assist":0,"gult":0,"rott":0,"matcher":0}
            sp["serier"][sid]["mal"]     += r.get("mal",0)
            sp["serier"][sid]["assist"]  += r.get("assist",0)
            sp["serier"][sid]["gult"]    += r.get("gult",0)
            sp["serier"][sid]["rott"]    += r.get("rott",0)
            sp["serier"][sid]["matcher"] += r.get("matcher",0)
        sp["mal_tot"]     += r.get("mal",0)
        sp["assist_tot"]  += r.get("assist",0)
        sp["gult_tot"]    += r.get("gult",0)
        sp["rott_tot"]    += r.get("rott",0)
        sp["matcher_tot"] += r.get("matcher",0)
    # Sortera pa mal totalt
    return sorted(index.values(), key=lambda x: (-x["mal_tot"], -x["assist_tot"]))

def bygg_kommande_matcher(serie_data: dict) -> list:
    """Returnerar platt lista med kommande matcher från alla serier."""
    matcher = []
    for sid, data in serie_data.items():
        for m in data["kommande"]:
            matcher.append(dict(
                id=f"{sid}_{m['datum_sort']}_{m['bortalag'][:10]}".replace(" ","_"),
                serie_id=sid,
                serie=data["etikett"],
                datum=m["datum"],
                datum_sort=m["datum_sort"],
                tid=m["tid"],
                hemmalag=m["hemmalag"],
                bortalag=m["bortalag"],
                hemma=m["hemma"],
                arena=m["arena"],
            ))
    return sorted(matcher, key=lambda x: x["datum_sort"])

# ── Route: Spara planering ────────────────────────────────────────────────────

@app.route("/planering/spara", methods=["POST"])
def spara_planering():
    if "inloggad" not in session:
        return jsonify({"ok": False, "msg": "Inte inloggad"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "msg": "Ingen data"}), 400
    planning = load_planning()
    match_id = data.get("match_id")
    spelare  = data.get("spelare", [])
    if match_id:
        planning["matcher"][match_id] = dict(
            serie_id=data.get("serie_id",""),
            serie=data.get("serie",""),
            datum=data.get("datum",""),
            motstandare=data.get("motstandare",""),
            spelare=spelare,
            uppdaterad=datetime.now().isoformat(),
        )
    save_planning(planning)
    return jsonify({"ok": True})

# ── Route: Synka laget.se-närvaro (kallas från admin-fliken) ─────────────────

@app.route("/sync/narvaro", methods=["POST"])
def sync_narvaro():
    """
    Tar emot närvaro-JSON från Claude-i-Chrome-sessionen och sparar den.
    Payload: {"spelare": [{namn, pct, traning, match, ovrig}], "laget_spelare": [{nummer, namn, position}]}
    """
    if "inloggad" not in session:
        return jsonify({"ok": False, "msg": "Inte inloggad"}), 401
    payload = request.get_json()
    if not payload:
        return jsonify({"ok": False, "msg": "Tom payload"}), 400

    narvaro = {}
    for sp in payload.get("spelare", []):
        namn = sp.get("namn","").strip()
        if namn:
            narvaro[namn] = dict(
                pct=sp.get("pct"),
                traning=sp.get("traning"),
                match=sp.get("match"),
                ovrig=sp.get("ovrig"),
            )

    cached = load_data()
    cached["narvaro"] = narvaro
    cached["synkad"]  = datetime.now().isoformat()
    if payload.get("laget_spelare"):
        cached["spelare"] = payload["laget_spelare"]
    save_data(cached)
    return jsonify({"ok": True, "antal": len(narvaro)})

# ── Route: Synka månadstrend ──────────────────────────────────────────────────

@app.route("/sync/trend", methods=["POST"])
def sync_trend():
    """
    Tar emot månadsvis närvaro.
    Payload: {"trend": [{namn, månader: [pct|null, ...]}, ...], "månadsLabels": [...]}
    """
    if "inloggad" not in session:
        return jsonify({"ok": False, "msg": "Inte inloggad"}), 401
    payload = request.get_json()
    if not payload:
        return jsonify({"ok": False, "msg": "Tom payload"}), 400

    cached = load_data()
    cached["trend"]         = payload.get("trend", [])
    cached["månadsLabels"]  = payload.get("månadsLabels", [])
    cached["trend_synkad"]  = datetime.now().isoformat()
    save_data(cached)
    return jsonify({"ok": True})

# ── Route: API – spelardata (för planeringsverktyget) ─────────────────────────

@app.route("/api/spelare")
def api_spelare():
    """Returnerar alla spelares nuvarande matchantal + planerade."""
    if "inloggad" not in session:
        return jsonify([]), 401
    cached   = load_data()
    planning = load_planning()

    # Räkna planerade matcher per spelare per serie
    planerade = defaultdict(lambda: defaultdict(int))
    for mid, mdata in planning["matcher"].items():
        sid = mdata.get("serie_id","")
        for namn in mdata.get("spelare",[]):
            planerade[namn][sid] += 1

    narvaro  = cached.get("narvaro", {})
    spelare  = cached.get("spelare", [])

    # Fogis behöver vi inte re-fetcha – returnera bara cached om det finns
    fogis_spl = cached.get("fogis_spelare", [])

    alla = slå_ihop_spelare(fogis_spl, narvaro, spelare)
    for sp in alla:
        sp["planerade_serier"] = dict(planerade.get(sp["namn"], {}))
        sp["planerade_totalt"] = sum(sp["planerade_serier"].values())

    return jsonify(alla)

# ── Route: Fogis-cache (spara vid dashboard-laddning) ─────────────────────────

@app.route("/sync/fogis", methods=["POST"])
def sync_fogis():
    """Cachelagrar Fogis spelarlistan."""
    if "inloggad" not in session:
        return jsonify({"ok": False}), 401
    payload = request.get_json()
    cached  = load_data()
    cached["fogis_spelare"] = payload.get("spelare", [])
    save_data(cached)
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
