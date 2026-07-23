from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = BASE_DIR / "template.html"
OUTPUT_FILE = BASE_DIR / "index.html"
DATA_DIR = BASE_DIR / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"

CLUB_PATTERN = re.compile(r"\bTTC\s+Gransee(?:\s+II)?\b", re.I)
MAX_ITEMS = 5
TIMEOUT = 30

LEAGUES = [
    {
        "team": "1. Herren",
        "url": "https://www.mytischtennis.de/click-tt/TTVB/26--27/ligen/1._Kreisklasse/gruppe/521568/tabelle/gesamt",
    },
    {
        "team": "2. Herren",
        "url": "https://www.mytischtennis.de/click-tt/TTVB/26--27/ligen/5._Kreisklasse/gruppe/521539/tabelle/gesamt",
    },
    {
        "team": "Nachwuchsmannschaft",
        "url": "https://www.mytischtennis.de/click-tt/TTVB/26--27/ligen/Kreisliga/gruppe/521582/tabelle/gesamt",
    },
]

# Zum Üben mit der abgeschlossenen Saison. Nach erfolgreichem Test kann
# GENERATE_REPORTS_FROM_TEST_LEAGUE in der .env auf false gesetzt werden.
TEST_LEAGUE = {
    "team": "1. Mannschaft",
    "url": "https://www.mytischtennis.de/click-tt/TTVB/25--26/ligen/1._Kreisklasse/gruppe/493634/tabelle/gesamt",
}

MONTHS = {
    "Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6,
    "Juli": 7, "August": 8, "September": 9, "Oktober": 10, "November": 11, "Dezember": 12,
}


@dataclass
class Match:
    match_id: str
    team: str
    date: str  # ISO
    time: str
    home: str
    away: str
    result: str | None
    report_url: str | None
    league_url: str


@dataclass
class Article:
    match_id: str
    date: str
    title: str
    body_html: str
    source_url: str


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "TTC-Gransee-Webseitenpflege/1.0 (+https://ttcgransee.de)",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    })
    return s


def fetch(s: requests.Session, url: str) -> str:
    logging.info("Lade %s", url)
    response = s.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def parse_short_date(text: str, season_hint: str) -> datetime | None:
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2})", text)
    if not m:
        return None
    day, month, year = map(int, m.groups())
    return datetime(2000 + year, month, day)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def find_schedule_table(soup: BeautifulSoup) -> Tag | None:
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        if "Spielplan" in heading.get_text(" ", strip=True):
            table = heading.find_next("table")
            if table:
                return table
    for table in soup.find_all("table"):
        text = normalize_space(table.get_text(" ", strip=True))
        if "Heimmannschaft" in text and "Gastmannschaft" in text:
            return table
    return None


def infer_date_from_row(cells: list[str], last_date: datetime | None) -> datetime | None:
    joined = " ".join(cells[:2])
    parsed = parse_short_date(joined, "")
    return parsed or last_date


def parse_matches(page_html: str, league_url: str, team_label: str) -> list[Match]:
    soup = BeautifulSoup(page_html, "html.parser")
    table = find_schedule_table(soup)
    if not table:
        raise RuntimeError(f"Keine Spielplantabelle gefunden: {league_url}")

    matches: list[Match] = []
    last_date: datetime | None = None
    for row in table.find_all("tr"):
        cells_tags = row.find_all(["td", "th"])
        cells = [normalize_space(c.get_text(" ", strip=True)) for c in cells_tags]
        if len(cells) < 4 or "Heimmannschaft" in " ".join(cells):
            continue

        row_text = normalize_space(row.get_text(" ", strip=True))
        if not CLUB_PATTERN.search(row_text):
            continue

        current_date = infer_date_from_row(cells, last_date)
        if current_date is None:
            logging.warning("Datum nicht erkennbar, Zeile übersprungen: %s", row_text)
            continue
        last_date = current_date

        time_match = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", row_text)
        time_text = time_match.group(0) if time_match else ""

        # Mannschaftslinks sind die Links mit Mannschaftsnamen; Ergebnislinks enthalten n:n.
        anchors = row.find_all("a")
        team_links = [a for a in anchors if re.search(r"[A-Za-zÄÖÜäöüß]", normalize_space(a.get_text(" ", strip=True)))
                      and not re.fullmatch(r"\d+", normalize_space(a.get_text(" ", strip=True)))]
        result_anchor = next((a for a in anchors if re.fullmatch(r"\d+\s*:\s*\d+", normalize_space(a.get_text(" ", strip=True)))), None)

        # Robuster Fallback: Namen anhand der Zellen nahe dem Ende bestimmen.
        names = []
        for a in team_links:
            txt = normalize_space(a.get_text(" ", strip=True))
            if txt and txt not in names and not txt.lower().startswith("pdf"):
                names.append(txt)
        names = [n for n in names if not re.fullmatch(r"\d+\s*:\s*\d+", n)]
        if len(names) < 2:
            # Tabellenzellen mit Vereinsnamen suchen.
            candidates = [c for c in cells if re.search(r"(?:TTC|SV|TSV|TTV|FSV|Kremmener|Motor|Empor|TT-Freunde)", c)]
            names = candidates[:2]
        if len(names) < 2:
            logging.warning("Mannschaften nicht erkennbar, Zeile übersprungen: %s", row_text)
            continue

        home, away = names[-2], names[-1]
        result = normalize_space(result_anchor.get_text(" ", strip=True)) if result_anchor else None
        report_url = urljoin(league_url, result_anchor.get("href")) if result_anchor and result_anchor.get("href") else None
        raw_id = report_url or f"{current_date.date()}|{time_text}|{home}|{away}"
        match_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]
        matches.append(Match(
            match_id=match_id,
            team=team_label,
            date=current_date.date().isoformat(),
            time=time_text,
            home=home,
            away=away,
            result=result,
            report_url=report_url,
            league_url=league_url,
        ))
    return matches


def extract_report_text(report_html: str) -> str:
    soup = BeautifulSoup(report_html, "html.parser")
    # Werbung, Navigation und Footer entfernen; Tabelleninhalt bleibt erhalten.
    for tag in soup.select("script, style, nav, footer, header, aside"):
        tag.decompose()
    main = soup.find("main") or soup.body or soup
    text = normalize_space(main.get_text(" | ", strip=True))
    marker = text.find("Spielbericht")
    if marker >= 0:
        text = text[marker:]
    return text[:14000]


def call_deepseek(match: Match, report_text: str) -> tuple[str, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    api_base = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "deepseek-chat")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY fehlt. Bitte .env anhand von .env.example anlegen.")

    system_prompt = (
        "Du schreibst sachliche, lebendige Vereinsnachrichten für den Tischtennisverein TTC Gransee 98 e.V. "
        "Nutze ausschließlich die gelieferten Spieldaten. Erfinde keine Zitate, Verletzungen, Stimmungen, "
        "Tabellenstände oder Ereignisse. Gib ausschließlich valides JSON mit den Schlüsseln title und body_html zurück. "
        "body_html enthält 3 bis 5 kurze HTML-Absätze (<p>...</p>), keine Überschrift, kein Markdown und keine Scripts."
    )
    user_prompt = f"""Erstelle einen Spielbericht auf Deutsch.
Mannschaft: {match.team}
Datum: {match.date}
Heim: {match.home}
Gast: {match.away}
Endstand: {match.result}
Quelldaten des vollständigen Spielberichts:
{report_text}

Titel: maximal 90 Zeichen. Im Text sollen Ergebnis, entscheidende Begegnungen und auffällige Fünfsatzspiele genannt werden, soweit aus den Daten belegbar."""

    response = requests.post(
        f"{api_base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.35,
            "response_format": {"type": "json_object"},
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    data = json.loads(content)
    title = normalize_space(str(data["title"]))[:120]
    body_html = sanitize_article_html(str(data["body_html"]))
    return title, body_html


def sanitize_article_html(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    allowed = {"p", "strong", "em", "br"}
    for tag in list(soup.find_all(True)):
        if tag.name not in allowed:
            tag.unwrap()
        else:
            tag.attrs = {}
    cleaned = str(soup).strip()
    if not cleaned:
        raise ValueError("Die API lieferte keinen Artikeltext.")
    return cleaned


def load_articles() -> list[Article]:
    if not ARTICLES_FILE.exists():
        return []
    raw = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    return [Article(**item) for item in raw]


def save_articles(articles: list[Article]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    ARTICLES_FILE.write_text(
        json.dumps([asdict(a) for a in articles], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def generate_new_articles(s: requests.Session, completed: Iterable[Match], articles: list[Article]) -> list[Article]:
    known = {a.match_id for a in articles}
    candidates = [m for m in completed if m.report_url and m.match_id not in known]
    candidates.sort(key=lambda m: (m.date, m.time), reverse=True)

    # Höchstens fünf Berichte pro Lauf; schützt vor hohen API-Kosten beim ersten Test.
    for match in candidates[:5]:
        logging.info("Erzeuge Bericht: %s – %s (%s)", match.home, match.away, match.result)
        try:
            report_html = fetch(s, match.report_url or "")
            report_text = extract_report_text(report_html)
            title, body_html = call_deepseek(match, report_text)
            articles.append(Article(
                match_id=match.match_id,
                date=match.date,
                title=title,
                body_html=body_html,
                source_url=match.report_url or match.league_url,
            ))
        except Exception as exc:
            logging.exception("Bericht konnte nicht erzeugt werden: %s", exc)

    articles.sort(key=lambda a: a.date, reverse=True)
    return articles[:MAX_ITEMS]


def render_news(articles: list[Article]) -> str:
    if not articles:
        return '<li class="text-gray-400">Noch keine Spielberichte vorhanden.</li>'
    items = []
    for article in articles[:MAX_ITEMS]:
        date_de = datetime.fromisoformat(article.date).strftime("%d.%m.%Y")
        items.append(f'''<li class="border-l-4 border-accent pl-4">
<button type="button" class="article-open text-left hover-accent font-bold" data-article-id="{html.escape(article.match_id)}">{html.escape(article.title)}</button>
<div class="text-sm text-gray-400 mt-1">{date_de}</div>
</li>''')
    return "\n".join(items)


def render_dates(upcoming: list[Match]) -> str:
    if not upcoming:
        return '<li class="text-gray-400">Derzeit sind keine kommenden Punktspiele eingetragen.</li>'
    items = []
    for match in upcoming[:MAX_ITEMS]:
        dt = datetime.fromisoformat(match.date)
        label = f"{match.home} – {match.away}"
        date_text = dt.strftime("%d.%m.%y") + (f", {match.time} Uhr" if match.time else "")
        items.append(f'''<li class="flex justify-between gap-4 items-start border-b border-gray-700 pb-2">
<span>{html.escape(label)}<span class="block text-sm text-gray-400">{html.escape(match.team)}</span></span>
<span class="text-accent whitespace-nowrap">{html.escape(date_text)}</span>
</li>''')
    return "\n".join(items)


def render_modal(articles: list[Article]) -> str:
    article_nodes = []
    for article in articles[:MAX_ITEMS]:
        date_de = datetime.fromisoformat(article.date).strftime("%d.%m.%Y")
        article_nodes.append(f'''<article id="article-{html.escape(article.match_id)}" class="article-content hidden">
<h2 class="text-2xl font-bold text-accent mb-2">{html.escape(article.title)}</h2>
<p class="text-sm text-gray-400 mb-5">{date_de}</p>
<div class="space-y-4 text-gray-200">{article.body_html}</div>
<p class="mt-6 text-xs text-gray-500">Quelle: <a class="hover-accent underline" href="{html.escape(article.source_url)}" target="_blank" rel="noopener noreferrer">myTischtennis.de</a></p>
</article>''')
    return f'''<!-- Vereinsnachrichten-Dialog -->
<div id="articleModal" class="fixed inset-0 bg-black bg-opacity-80 z-50 hidden items-center justify-center p-4" role="dialog" aria-modal="true" aria-hidden="true">
  <div class="bg-gray-900 border border-accent rounded-lg max-w-3xl w-full max-h-screen overflow-y-auto p-6 relative">
    <button id="articleModalClose" type="button" class="absolute top-3 right-3 text-accent text-2xl" aria-label="Artikel schließen"><i class="fas fa-times"></i></button>
    {''.join(article_nodes)}
  </div>
</div>'''


def replace_information_lists(soup: BeautifulSoup, news_html: str, dates_html: str) -> None:
    news_heading = next((h for h in soup.find_all(re.compile(r"^h[1-6]$")) if "Vereinsnachrichten" in h.get_text(" ", strip=True)), None)
    dates_heading = next((h for h in soup.find_all(re.compile(r"^h[1-6]$")) if "Nächste Termine" in h.get_text(" ", strip=True)), None)
    if not news_heading or not dates_heading:
        raise RuntimeError("Die Bereiche 'Vereinsnachrichten' oder 'Nächste Termine' fehlen im Template.")

    news_list = news_heading.find_next("ul")
    dates_list = dates_heading.find_next("ul")
    if not news_list or not dates_list:
        raise RuntimeError("Listen unter den Informationsüberschriften nicht gefunden.")

    news_list.clear()
    for node in BeautifulSoup(news_html, "html.parser").contents:
        news_list.append(node)
    dates_list.clear()
    for node in BeautifulSoup(dates_html, "html.parser").contents:
        dates_list.append(node)


def inject_modal_and_script(soup: BeautifulSoup, modal_html: str) -> None:
    old_modal = soup.find(id="articleModal")
    if old_modal:
        old_modal.decompose()
    modal_soup = BeautifulSoup(modal_html, "html.parser")
    soup.body.append(modal_soup)

    script = soup.new_tag("script")
    script.string = r'''
// Vereinsnachrichten im eingebetteten Dialog öffnen.
(() => {
    const modal = document.getElementById('articleModal');
    const closeButton = document.getElementById('articleModalClose');
    if (!modal || !closeButton) return;

    const closeArticle = () => {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        modal.querySelectorAll('.article-content').forEach(el => el.classList.add('hidden'));
    };

    document.querySelectorAll('.article-open').forEach(button => {
        button.addEventListener('click', () => {
            const article = document.getElementById(`article-${button.dataset.articleId}`);
            if (!article) return;
            modal.querySelectorAll('.article-content').forEach(el => el.classList.add('hidden'));
            article.classList.remove('hidden');
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            modal.setAttribute('aria-hidden', 'false');
            document.body.style.overflow = 'hidden';
            closeButton.focus();
        });
    });

    closeButton.addEventListener('click', closeArticle);
    modal.addEventListener('click', event => { if (event.target === modal) closeArticle(); });
    window.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !modal.classList.contains('hidden')) closeArticle();
    });
})();
'''
    soup.body.append(script)


def build_website(articles: list[Article], upcoming: list[Match]) -> None:
    if not TEMPLATE_FILE.exists():
        raise FileNotFoundError(f"Template fehlt: {TEMPLATE_FILE}")
    soup = BeautifulSoup(TEMPLATE_FILE.read_text(encoding="utf-8"), "html.parser")
    replace_information_lists(soup, render_news(articles), render_dates(upcoming))
    inject_modal_and_script(soup, render_modal(articles))
    OUTPUT_FILE.write_text(str(soup), encoding="utf-8")


def main() -> int:
    load_dotenv(BASE_DIR / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    s = session()
    today = datetime.now().date()

    all_current_matches: list[Match] = []
    for league in LEAGUES:
        try:
            all_current_matches.extend(parse_matches(fetch(s, league["url"]), league["url"], league["team"]))
        except Exception as exc:
            logging.exception("Liga konnte nicht verarbeitet werden: %s", exc)

    upcoming = sorted(
        [m for m in all_current_matches if datetime.fromisoformat(m.date).date() >= today],
        key=lambda m: (m.date, m.time),
    )[:MAX_ITEMS]

    article_source_matches = list(all_current_matches)
    use_test = os.getenv("GENERATE_REPORTS_FROM_TEST_LEAGUE", "true").lower() in {"1", "true", "yes", "ja"}
    if use_test:
        try:
            article_source_matches.extend(parse_matches(fetch(s, TEST_LEAGUE["url"]), TEST_LEAGUE["url"], TEST_LEAGUE["team"]))
        except Exception as exc:
            logging.exception("Testliga konnte nicht verarbeitet werden: %s", exc)

    completed = [m for m in article_source_matches if m.result and m.report_url]
    articles = generate_new_articles(s, completed, load_articles())
    save_articles(articles)
    build_website(articles, upcoming)
    logging.info("Fertig: %s", OUTPUT_FILE)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        logging.exception("Abbruch: %s", exc)
        raise SystemExit(1)
