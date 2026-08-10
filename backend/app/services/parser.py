"""
Converts the raw Gmail message dict (from gmail_service.get_message) into
clean plain text plus any structured bits (links, table rows) that the
classifier / deadline extractor might want.
"""
import re

from bs4 import BeautifulSoup

from app.utils.logger import get_logger

logger = get_logger(__name__)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # collapse excess blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    return [a["href"] for a in soup.find_all("a", href=True)]


def extract_tables(html: str) -> list[list[list[str]]]:
    """Returns a list of tables, each a list of rows, each a list of cell texts."""
    soup = BeautifulSoup(html, "lxml")
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def parse_email(raw: dict) -> dict:
    """
    raw: dict as returned by gmail_service.get_message()
    Returns a dict with normalized `body_text`, `links`, `tables` added.
    """
    if raw.get("html"):
        body_text = html_to_text(raw["html"])
        links = extract_links(raw["html"])
        tables = extract_tables(raw["html"])
    else:
        body_text = raw.get("plain_text", "") or raw.get("snippet", "")
        links = []
        tables = []

    parsed = dict(raw)
    parsed["body_text"] = body_text
    parsed["links"] = links
    parsed["tables"] = tables
    return parsed
