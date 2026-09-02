#!/usr/bin/env python3
"""
Anker watcher.

Runs on a schedule (GitHub Actions), reads the same sources as the app,
and pushes real notifications to your phone through ntfy.sh. Works with
the app closed and the screen off, which a browser PWA cannot do on iOS.

Modes:
  news    poll feeds, push anything new
  lesson  generate and push the daily lesson (--side morning|evening)

Environment:
  NTFY_TOPIC          required. Your private topic name, e.g. anker-tim-9f3k2x
  NTFY_SERVER         optional, default https://ntfy.sh
  ANTHROPIC_API_KEY   optional. Without it you get headlines and a fixed
                      per-category note. With it, Claude writes the briefing
                      and the daily lessons.
  ANTHROPIC_MODEL     optional, default claude-sonnet-5
  BRIEF_LENGTH        optional: kort | normaal | lang. Default normaal.
  MAX_PUSH            optional, default 6. Cap per run so one busy hour
                      cannot empty your battery.
"""

import json, os, re, sys, time, hashlib, argparse, urllib.parse
from datetime import datetime, timezone, timedelta
from html import unescape

import requests
import feedparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state", "seen.json")
FEEDS_FILE = os.path.join(ROOT, "feeds.txt")
CURRICULUM = os.path.join(ROOT, "curriculum.json")

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
LENGTH = os.environ.get("BRIEF_LENGTH", "normaal")
MAX_PUSH = int(os.environ.get("MAX_PUSH", "6"))
TZ = timezone(timedelta(hours=2))  # Europe/Amsterdam; see local_hour()

CATS = ["MARKT", "NL WONEN", "GEOPOLITIEK", "MACRO", "NEDERLAND", "CRYPTO"]

KW = {
 "NL WONEN": ["huizenmarkt","woningmarkt","huurprijs","huurmarkt","huurwoning","koopwoning","hypotheek",
              "makelaar","kadaster","nvm","woningtekort","verhuurder","huurder","huurverhoging",
              "woningcorporatie","erfpacht","nieuwbouw","betaalbare huur","puntensysteem","woz",
              "overdrachtsbelasting","box 3","vastgoed","stikstof"],
 "MACRO": ["inflatie","rente","centrale bank","ecb","federal reserve","dnb","imf","goud","obligatie",
           "staatsschuld","begroting","dollar","valuta","recessie","monetair","bbp"],
 "MARKT": ["aandeel","aandelen","beurs","index","aex","s&p","nasdaq","dow","koers","kwartaalcijfers",
           "overname","fusie","ipo","olieprijs","futures","belegger","dividend","winstwaarschuwing"],
 "GEOPOLITIEK": ["oorlog","aanval","raket","invasie","sancties","militair","conflict","staakt-het-vuren",
                 "navo","terreur","luchtaanval","drone","escalatie","handelsoorlog","importheffing"],
 "CRYPTO": ["bitcoin","ethereum","solana","crypto","memecoin","stablecoin","blockchain","mica"],
 "NEDERLAND": ["kabinet","tweede kamer","eerste kamer","minister","den haag","gemeente","cbs",
               "belastingdienst","coalitie","verkiezing","prinsjesdag"],
}

HIGH = ["oorlog","invasie","aanval","noodtoestand","crash","rentebesluit","renteverlaging","renteverhoging",
        "faillissement","aangenomen","verbod","recordhoogte","ingestort","sancties","staakt-het-vuren",
        "kabinet gevallen","recessie","wetsvoorstel"]

MEANS = {
 "MARKT": "Koersnieuws is meestal al verwerkt. Kijk of dit iets verandert aan winstgroei, rente of risicobereidheid over maanden.",
 "NL WONEN": "Weegt door op huurniveau, leegstandsduur, financierbaarheid en regeldruk. Wetgeving werkt vertraagd, maar bijna nooit terug.",
 "GEOPOLITIEK": "Directe marktimpact is meestal kort en overdreven. Wat blijft: energieprijzen, handelsroutes, defensie-uitgaven.",
 "MACRO": "Raakt hypotheek, waarderingen en beleggingen tegelijk. Rente en inflatie doen meer met vastgoed dan lokaal nieuws.",
 "NEDERLAND": "Vertaalt zich pas naar geld via wetgeving en begroting. Zoek de ingangsdatum; dat is wat telt voor planning.",
 "CRYPTO": "Scheid regelgeving (blijvend) van prijsbeweging (ruis).",
}

WORDS = {"kort": "ongeveer 110 woorden", "normaal": "ongeveer 220 woorden", "lang": "ongeveer 420 woorden"}


# ─────────────────────────── helpers ───────────────────────────

def local_hour():
    """Hour in Europe/Amsterdam. Uses zoneinfo when available, else a DST guess."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Amsterdam")).hour
    except Exception:
        return datetime.now(TZ).hour


def clean(s, limit=900):
    s = unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()[:limit]


def norm_key(title):
    return hashlib.sha1(re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()[:80].encode()).hexdigest()[:16]


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {"seen": {}, "lessons": {}}


def save_state(st):
    cutoff = time.time() - 14 * 86400
    st["seen"] = {k: v for k, v in st["seen"].items() if v > cutoff}
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=0, sort_keys=True)


def load_feeds():
    try:
        with open(FEEDS_FILE) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except Exception:
        return []
    out = []
    for l in lines:
        parts = [p.strip() for p in l.split("|")]
        out.append((parts[0], parts[1] if len(parts) > 1 and parts[1] in CATS else None))
    return out


def classify(title, desc, hint):
    hay = (title + " " + desc).lower()
    best, score = (hint or "NEDERLAND"), (1.0 if hint else 0.0)
    for c in CATS:
        s = sum(1 for k in KW[c] if k in hay)
        if c == hint:
            s += 1.5
        if s > score:
            best, score = c, s
    return best, any(k in hay for k in HIGH)


# ─────────────────────────── push ───────────────────────────

def push(title, body, url=None, priority="default", tags=None):
    if not TOPIC:
        print("NTFY_TOPIC not set, printing instead:\n", title, "\n", body[:400])
        return
    headers = {"Title": title.encode("utf-8"), "Priority": priority}
    if url:
        headers["Click"] = url
    if tags:
        headers["Tags"] = ",".join(tags)
    try:
        r = requests.post(f"{NTFY_SERVER}/{TOPIC}", data=body.encode("utf-8"),
                          headers=headers, timeout=20)
        if r.status_code >= 300:
            print("ntfy error", r.status_code, r.text[:200])
    except Exception as e:
        print("ntfy failed:", e)


# ─────────────────────────── claude ───────────────────────────

def claude(system, user, max_tokens=3000):
    if not API_KEY:
        raise RuntimeError("no api key")
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": max_tokens, "system": system,
              "messages": [{"role": "user", "content": user}]},
        timeout=120)
    r.raise_for_status()
    d = r.json()
    return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")


BRIEF_SYSTEM = """Je bent een nuchtere Nederlandse economieredacteur die schrijft voor één lezer: een 21-jarige ondernemer in Den Haag met een verhuurmakelaarskantoor in opbouw, vastgoedbeheerwerk, een futures-handelsaccount en beleggingen in indexfondsen.

Regels:
- Nederlands, direct, zonder opsmuk. Geen uitroeptekens, geen "belangrijk om te weten".
- Herschrijf volledig in eigen woorden. Citeer nooit uit de bron en volg de zinsbouw van de bron niet.
- Is de brontekst te dun voor een goed verhaal, zeg dat in één zin en vul aan met context die je zelf hebt.
- Bij de betekenis: concreet, en durf te zeggen dat iets waarschijnlijk niets betekent. Geen handelsadvies.
- Antwoord UITSLUITEND met geldige JSON. Geen markdown, geen toelichting."""


def write_briefs(items):
    if not API_KEY or not items:
        return
    body = "\n\n".join(
        f"[{i}] ({it['cat']} · {it['src']}) {it['title']}\n{it['desc'][:600]}"
        for i, it in enumerate(items))
    user = (f"Schrijf per bericht een samenvatting van {WORDS.get(LENGTH, WORDS['normaal'])} "
            f"en daarna 2 tot 3 zinnen over wat het betekent, toegespitst op de categorie.\n\n"
            f'Antwoordformaat: {{"r":[{{"i":0,"s":"samenvatting","m":"betekenis"}}]}}\n\n'
            f"Berichten:\n{body}")
    try:
        txt = claude(BRIEF_SYSTEM, user, 4000).replace("```json", "").replace("```", "").strip()
        data = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
        for r in data.get("r", []):
            i = r.get("i")
            if isinstance(i, int) and 0 <= i < len(items):
                items[i]["brief"] = r.get("s", "")
                items[i]["means"] = r.get("m", "")
    except Exception as e:
        print("briefing failed:", e)


# ─────────────────────────── modes ───────────────────────────

def run_news():
    st = load_state()
    seen = st["seen"]
    fresh = []
    for url, hint in load_feeds():
        try:
            d = feedparser.parse(url, agent="Anker/1.0")
        except Exception as e:
            print("feed failed", url, e)
            continue
        src = clean(getattr(d.feed, "title", "") or urllib.parse.urlparse(url).netloc, 60)
        for e in d.entries[:25]:
            title = clean(getattr(e, "title", ""), 300)
            if not title:
                continue
            k = norm_key(title)
            if k in seen:
                continue
            desc = clean(getattr(e, "summary", "") or getattr(e, "description", ""))
            cat, high = classify(title, desc, hint)
            fresh.append({"k": k, "title": title, "desc": desc, "src": src,
                          "link": getattr(e, "link", ""), "cat": cat, "high": high})
            seen[k] = time.time()

    if not fresh:
        print("nothing new")
        save_state(st)
        return

    # First run on a clean state would push hundreds of items. Prime instead.
    if len(seen) == len(fresh):
        print(f"first run, primed {len(fresh)} items without pushing")
        save_state(st)
        return

    fresh.sort(key=lambda x: (not x["high"], x["cat"]))
    batch = fresh[:MAX_PUSH]
    write_briefs(batch)

    for it in batch:
        text = it.get("brief") or it["desc"][:400] or "Geen samenvatting beschikbaar."
        means = it.get("means") or MEANS.get(it["cat"], "")
        body = f"{text}\n\nWAT DIT BETEKENT\n{means}"
        push(f"{it['cat']} · {it['src']}", body, url=it["link"],
             priority="high" if it["high"] else "default",
             tags=["rotating_light"] if it["high"] else None)

    rest = len(fresh) - len(batch)
    if rest > 0:
        push("Anker", f"Nog {rest} andere berichten binnengekomen. Open de app voor de rest.",
             priority="low")

    save_state(st)
    print(f"pushed {len(batch)}, held back {rest}")


LESSON_SYSTEM = """Je schrijft één dagelijkse les voor één lezer: een 21-jarige Nederlandse ondernemer die een luxe verhuurmakelaarskantoor opbouwt in de Haaglanden, daarnaast vastgoedbeheer doet en futures handelt.

Domein: {domain}
Stijl: {voice}
Overkoepelend thema van de reeks: {theme}. {theme_line}

Lengte: 260 tot 340 woorden. Nederlands. Vier tot zes korte alinea's, gescheiden door een lege regel. Geen koppen, geen opsommingstekens, geen inleidende zin die het onderwerp aankondigt: begin meteen met de inhoud. Sluit af met één alinea die begint met "{closer}" en precies één uitvoerbare actie bevat."""


def run_lesson(side, force=False):
    want = 8 if side == "morning" else 22
    if not force and local_hour() != want:
        print(f"not {want}:00 local, skipping")
        return

    with open(CURRICULUM) as f:
        cur = json.load(f)
    c = cur[side]
    st = load_state()
    day = (datetime.now(timezone.utc) - datetime(2026, 1, 1, tzinfo=timezone.utc)).days
    stamp = f"{side}-{datetime.now(timezone.utc).date()}"
    if st["lessons"].get(stamp) and not force:
        print("already sent today")
        return

    all_lessons = [(m["name"], l) for m in c["modules"] for l in m["lessons"]]
    module, title = all_lessons[day % len(all_lessons)]

    body = None
    if API_KEY:
        try:
            sysmsg = LESSON_SYSTEM.format(
                domain=c["domain"], voice=c["voice"],
                theme=cur["theme"]["title"], theme_line=cur["theme"]["line"],
                closer="**Vandaag:**" if side == "morning" else "**Let morgen op:**")
            body = claude(sysmsg, f"Onderwerp: {title}\nModule: {module}", 1200).strip()
        except Exception as e:
            print("lesson generation failed:", e)
    if not body:
        seed = c["seed"][day % len(c["seed"])]
        title, body = seed["title"], seed["body"]
        module = "Uit de basisreeks"

    label = "Ochtendles" if side == "morning" else "Avondles"
    push(f"{label} · {title}", body.replace("**", ""),
         tags=["sunrise"] if side == "morning" else ["crescent_moon"])

    st["lessons"][stamp] = int(time.time())
    st["lessons"] = dict(sorted(st["lessons"].items())[-60:])
    save_state(st)
    print("sent", stamp, "|", title)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["news", "lesson"])
    p.add_argument("--side", choices=["morning", "evening"], default="morning")
    p.add_argument("--force", action="store_true", help="ignore the hour check")
    a = p.parse_args()
    if a.mode == "news":
        run_news()
    else:
        run_lesson(a.side, a.force)
