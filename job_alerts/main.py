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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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
MAX_ITEMS = 15
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
        raw_title = clean_text(node.findtext("title", ""))
        link = clean_text(node.findtext("link", ""))
        source_node = node.find("source")
        source = clean_text(source_node.text if source_node is not None and source_node.text else "")
        published = parse_pubdate(node.findtext("pubDate", ""))
        raw_description = clean_text(node.findtext("description", ""))

        if not raw_title or not link:
            continue

        # Clean source suffix from title if present
        title = raw_title
        if " - " in title:
            candidate_title, candidate_source = title.rsplit(" - ", 1)
            if not source:
                source = candidate_source.strip()
                title = candidate_title.strip()
            elif candidate_source.strip().lower() == source.lower():
                title = candidate_title.strip()

        source = source or "Google News RSS"

        # Discard description if it's merely repeating the title/source or empty
        desc = raw_description
        if desc and (desc.lower() == raw_title.lower() or desc.lower() == f"{raw_title} {source}".lower()):
            desc = ""
        elif len(desc) > 130:
            desc = desc[:127].rsplit(" ", 1)[0] + "..."

        key = re.sub(r"[^a-z0-9]+", " ", (title + " " + source).lower()).strip()
        items.append({
            "key": key[:220],
            "title": title,
            "link": link,
            "source": source,
            "published": published,
            "description": desc,
            "query": query,
        })
    return items


def format_card(index: int, item: dict) -> str:
    title = html.escape(item["title"])
    source = html.escape(item["source"])
    link = html.escape(item["link"], quote=True)
    date_str = item["published"].strftime("%d %b, %I:%M %p IST") if item["published"] else "Date not supplied"
    snippet = item.get("description", "").strip()

    lines = [
        f"<b>{index}. {title}</b>",
        f"🏢 <b>Source:</b> {source}  •  🕒 <i>{date_str}</i>",
        f"🏷️ <b>Status:</b> ⚠️ <i>Unverified Lead</i>",
    ]
    if snippet:
        lines.append(f"📝 <i>{html.escape(snippet)}</i>")
    lines.append(f"🔗 <a href=\"{link}\"><b>View Job Lead / Apply ↗</b></a>\n")
    return "\n".join(lines)


def build_messages(edition: str, now: dt.datetime, items: list[dict]) -> list[str]:
    header = (
        f"🎯 <b>JOB RADAR — {edition} EDITION</b>\n"
        f"📅 <i>{now.strftime('%d %b %Y • %I:%M %p IST')}</i>\n"
        f"📍 <i>Lucknow & ~100km • Remote India • Freshers & Tech</i>\n"
        f"{'━' * 28}\n\n"
    )

    footer = (
        f"{'━' * 28}\n"
        f"📡 <b>Scope:</b> Software, AI/ML, Data, Internships, Walk-ins, Govt/PSU\n"
        f"⚠️ <b>Note:</b> Automated leads via public RSS. Verify eligibility and official portal before applying."
    )

    if not items:
        next_edition = "8:00 PM IST" if edition == "MORNING" else "8:00 AM IST"
        return [
            f"🎯 <b>JOB RADAR — {edition} EDITION</b>\n"
            f"📅 <i>{now.strftime('%d %b %Y • %I:%M %p IST')}</i>\n"
            f"{'━' * 28}\n\n"
            f"ℹ️ <b>No new matching leads found in this scan.</b>\n"
            f"<i>All current listings have already been reported. Next automated scan at {next_edition}.</i>\n\n"
            f"{footer}"
        ]

    messages = []
    current_body = header
    current_count = 0

    for idx, item in enumerate(items, 1):
        card = format_card(idx, item)
        # Split into chunks of max 7 cards or ~3400 chars for mobile readability
        if len(current_body) + len(card) > 3400 or current_count >= 7:
            messages.append(current_body.strip())
            current_body = (
                f"🎯 <b>JOB RADAR — {edition} (Part {len(messages) + 1})</b>\n"
                f"{'━' * 28}\n\n{card}\n"
            )
            current_count = 1
        else:
            current_body += card + "\n"
            current_count += 1

    if len(current_body) + len(footer) > 3900:
        messages.append(current_body.strip())
        messages.append(footer)
    else:
        current_body += "\n" + footer
        messages.append(current_body.strip())

    return messages


def telegram_send(text: str, parse_mode: str = "HTML") -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    response = requests.post(url, json=payload, timeout=20)
    if not response.ok:
        # Fallback to plain text if Telegram rejects HTML entities
        if parse_mode == "HTML":
            print(f"Telegram HTML parse rejected ({response.status_code}), falling back to plain text...", file=sys.stderr)
            plain = re.sub(r"<[^>]+>", "", text)
            payload["text"] = plain
            payload.pop("parse_mode", None)
            retry_res = requests.post(url, json=payload, timeout=20)
            if not retry_res.ok:
                raise RuntimeError(f"Telegram send failed ({retry_res.status_code}): {retry_res.text[:300]}")
            return
        raise RuntimeError(f"Telegram send failed ({response.status_code}): {response.text[:300]}")

    payload_res = response.json()
    if not payload_res.get("ok"):
        raise RuntimeError(f"Telegram API rejected message: {payload_res}")


def main() -> int:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN secret or TELEGRAM_CHAT_ID repository variable.", file=sys.stderr)
        return 2

    now = now_ist()
    hour = now.hour
    edition = "MORNING" if 4 <= hour < 15 else "EVENING"
    report_name = f"JOB RADAR — {edition} EDITION"
    state = load_state()
    reported = set(state.get("reported", []))

    all_items: dict[str, dict] = {}
    for query in QUERIES:
        for item in fetch_query(query):
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

    messages = build_messages(edition, now, new_items)
    for msg in messages:
        telegram_send(msg)
        time.sleep(1)

    # Persist keys only after successful Telegram delivery.
    state["reported"] = (state.get("reported", []) + [x["key"] for x in new_items])[-STATE_MAX:]
    state["last_success_ist"] = now.isoformat()
    state["last_report"] = report_name
    save_state(state)
    print(f"Sent {report_name}; new leads={len(new_items)}; queries={len(QUERIES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
