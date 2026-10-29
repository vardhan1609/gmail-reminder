"""
Email body parser and HTML sanitizer.
Safely extracts plain-text, links, tables, and strips malicious scripts,
iframes, event handlers, and flags prompt-injection patterns.
"""
import re
from typing import Dict, List, Any
from bs4 import BeautifulSoup

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Common prompt injection patterns to neutralize
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE),
    re.compile(r"you\s+must\s+output\s+the\s+secret", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?prior\s+rules", re.IGNORECASE),
    re.compile(r"act\s+as\s+an\s+unrestricted\s+ai", re.IGNORECASE),
]


def sanitize_html(html: str) -> str:
    """
    Sanitizes HTML by removing dangerous tags (<script>, <iframe>, <object>, <embed>, <form>),
    inline event handlers (onload, onclick, onerror), and javascript: URIs.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")

    # Remove dangerous elements completely
    for tag in soup(["script", "style", "iframe", "object", "embed", "applet", "form"]):
        tag.decompose()

    # Clean attributes from all remaining tags
    for tag in soup.find_all(True):
        # Remove any on* event handler attributes
        attrs_to_remove = [attr for attr in tag.attrs if attr.lower().startswith("on")]
        for attr in attrs_to_remove:
            del tag[attr]

        # Check href / src for javascript: or data: URIs
        for attr in ["href", "src"]:
            val = tag.get(attr, "")
            if isinstance(val, str) and (val.strip().lower().startswith("javascript:") or val.strip().lower().startswith("vbscript:")):
                del tag[attr]

    return str(soup)


def html_to_text(html: str) -> str:
    """Converts sanitized HTML to clean readable plain text."""
    if not html:
        return ""
    sanitized = sanitize_html(html)
    soup = BeautifulSoup(sanitized, "lxml")
    # Replace block level elements with newlines, inline tags with empty/space
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"]):
        p.append("\n")
    text = soup.get_text(separator="")
    # Collapse multiple blank lines and whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_links(html: str) -> List[str]:
    """Extracts valid HTTP/HTTPS URLs from HTML body."""
    if not html:
        return []
    soup = BeautifulSoup(sanitize_html(html), "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("http://") or href.startswith("https://"):
            links.append(href)
    return links


def extract_tables(html: str) -> List[List[List[str]]]:
    """Extracts tabular data from HTML."""
    if not html:
        return []
    soup = BeautifulSoup(sanitize_html(html), "lxml")
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


def neutralize_prompt_injection(text: str) -> str:
    """Neutralizes recognized prompt injection attempts by neutralizing keywords."""
    sanitized = text
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub("[FILTERED INJECTION ATTEMPT]", sanitized)
    return sanitized


def parse_email(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses a raw email dict, ensuring sanitized text, sanitized HTML, links, and tables are populated.
    """
    html_content = raw.get("html") or ""
    plain_content = raw.get("plain_text") or raw.get("snippet") or ""

    parsed = dict(raw)

    if html_content:
        sanitized_html = sanitize_html(html_content)
        parsed["html"] = sanitized_html
        body_text = html_to_text(sanitized_html)
        if plain_content and plain_content.strip() not in body_text:
            body_text += "\n" + plain_content.strip()
        links = extract_links(sanitized_html)
        tables = extract_tables(sanitized_html)
    else:
        body_text = plain_content
        links = []
        tables = []

    body_text = neutralize_prompt_injection(body_text)

    parsed["body_text"] = body_text
    parsed["links"] = links
    parsed["tables"] = tables
    return parsed
