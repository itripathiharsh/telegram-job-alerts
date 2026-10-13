from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# Broad discovery queries. Results are deliberately treated as leads, not verified vacancies.
QUERIES = [
    '"Python developer" fresher India jobs',
    '"backend developer" fresher India hiring',
    '"software engineer" graduate trainee India hiring',
    '"AI engineer" OR "machine learning engineer" India hiring',
    '"data analyst" OR "data scientist" fresher India jobs',
    '"Forward Deployed Engineer" OR "technical consultant" India hiring',
    'Lucknow IT jobs software developer Python AI hiring',
    'Lucknow walk-in interview IT developer fresher',
    'India government recruitment computer science IT project staff',
    'India research assistant project associate computer science recruitment',
    'India remote software developer internship AI ML',
    'India startup hiring Python backend developer',
    'India freelance Python automation AI project',
]

HEADERS = {"User-Agent": "HarshTelegramJobAlerts/1.0 (RSS reader)"}
MAX_ITEMS = 18
STATE_MAX = 1500


def now_ist() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).astimezone(IST)


def clean_text(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()


def parse_pubdate(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(IST)
    except Exception:
        return None


def load_state() -> dict:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("reported"), list):
            return data
    except Exception:
        pass
    return {"reported": []}


def save_state(state: dict) -> None:
    state["reported"] = state.get("reported", [])[-STATE_MAX:]
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch_query(query: str) -> list[dict]:
    params = {
        "q": f"{query} when:7d",
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en",
    }
    url = "https://news.google.com/rss/search?" + urlencode(params)
    try:
        response = requests.get(url, headers=HEADERS, timeout=18)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as exc:
        print(f"RSS fetch failed for {query!r}: {exc}", file=sys.stderr)
        return []

    items = []
    for node in root.findall(".//item"):
        title = clean_text(node.findtext("title", ""))
        link = clean_text(node.findtext("link", ""))
        source_node = node.find("source")
        source = clean_text(source_node.text if source_node is not None and source_node.text else "")
        published = parse_pubdate(node.findtext("pubDate", ""))
        description = clean_text(node.findtext("description", ""))
        if not title or not link:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", (title + " " + source).lower()).strip()
        items.append({
            "key": key[:220],
            "title": title,
            "link": link,
            "source": source or "Google News RSS",
            "published": published,
            "description": description[:320],
            "query": query,
        })
    return items


def telegram_send(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Telegram message length limit is 4096 characters; split safely by lines.
    chunks, current = [], ""
    for line in text.splitlines():
        candidate = (current + "\n" + line).strip() if current else line
        if len(candidate) > 3800:
            if current:
                chunks.append(current)
            current = line[:3800]
        else:
            current = candidate
    if current:
        chunks.append(current)
    for chunk in chunks:
        response = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": chunk, "disable_web_page_preview": True},
            timeout=20,
        )
        if not response.ok:
            raise RuntimeError(f"Telegram send failed ({response.status_code}): {response.text[:300]}")
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API rejected message: {payload}")


def main() -> int:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN secret or TELEGRAM_CHAT_ID repository variable.", file=sys.stderr)
        return 2

    now = now_ist()
    hour = now.hour
    report_name = "MORNING JOB SEARCH" if 4 <= hour < 15 else "EVENING JOB SEARCH"
    state = load_state()
    reported = set(state.get("reported", []))

    all_items: dict[str, dict] = {}
    for query in QUERIES:
        for item in fetch_query(query):
            # Use a title/source key so the same article from multiple queries is only listed once.
            key = item["key"]
            if key not in all_items or (
                item["published"] and
                (not all_items[key]["published"] or item["published"] > all_items[key]["published"])
            ):
                all_items[key] = item
        time.sleep(0.25)

    # Prefer recent items, then report only items not already sent.
    items = list(all_items.values())
    items.sort(key=lambda x: x["published"] or dt.datetime.min.replace(tzinfo=IST), reverse=True)
    new_items = [x for x in items if x["key"] not in reported][:MAX_ITEMS]

    lines = [
        f"{report_name} — {now.strftime('%d %b %Y, %I:%M %p IST')}",
        "",
        "Target: Lucknow + ~100 km, remote India, and suitable India-wide roles.",
        "Focus: software/backend, Python, AI/ML, data, FDE/technical consulting, research, government/PSU, startups, internships, walk-ins and paid projects.",
        "",
        "IMPORTANT: These are discovery leads from Google News RSS, NOT verified-open vacancies. Confirm eligibility, deadline, employer and application portal on the original source before applying.",
        "",
    ]

    if not new_items:
        lines.append("No new matching headlines were found in this run. This does not mean there are no open jobs.")
    else:
        lines.append(f"New leads: {len(new_items)}")
        for index, item in enumerate(new_items, 1):
            date_label = item["published"].strftime("%d %b %Y %I:%M %p IST") if item["published"] else "Date not supplied"
            lines.extend([
                "",
                f"{index}. {item['title']}",
                f"Publisher: {item['source']} | Published: {date_label}",
                f"Status: UNVERIFIED LEAD — deadline, eligibility and current application status not confirmed.",
                f"Discovery link: {item['link']}",
            ])
            if item["description"]:
                lines.append(f"Snippet: {item['description'][:240]}")
        lines.extend([
            "",
            "Next action: open each source, verify the original employer notice and deadline, then apply only if eligible.",
        ])

    lines.extend([
        "",
        "Searches use public Google News RSS queries. Coverage is broad but not exhaustive; login-only sources and some social posts are not indexed.",
    ])
    message = "\n".join(lines)
    telegram_send(message)

    # Persist keys only after successful Telegram delivery.
    state["reported"] = (state.get("reported", []) + [x["key"] for x in new_items])[-STATE_MAX:]
    state["last_success_ist"] = now.isoformat()
    state["last_report"] = report_name
    save_state(state)
    print(f"Sent {report_name}; new leads={len(new_items)}; queries={len(QUERIES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
