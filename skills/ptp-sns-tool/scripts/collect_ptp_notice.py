#!/usr/bin/env python3
"""Collect the newest public PTP business notice; Python 3.10+ standard library only.

No login, document execution, extraction, or SNS publication is performed. Original
HTML and attachment bytes are retained with SHA-256 evidence in source.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable


BASE = "https://www.ptp.or.kr"
LIST_URL = BASE + "/main/board/index.do?menu_idx=116&manage_idx=15"
ALLOWED_EXTENSIONS = {".pdf", ".hwp", ".hwpx", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".txt", ".csv", ".rtf"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self) -> str:
        if self.tag in {"script", "style"}:
            return ""
        return re.sub(r"\s+", " ", " ".join(c.text() if isinstance(c, Node) else c for c in self.children)).strip()

    def has_class(self, name: str) -> bool:
        return name in self.attrs.get("class", "").split()


class Document(HTMLParser):
    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict((k, v or "") for k, v in attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def first_class(root: Node, name: str) -> Node | None:
    return next((n for n in root.walk() if n.has_class(name)), None)


def parse_listing(html: str, listing_url: str) -> dict:
    doc = Document(html).root
    listing = first_class(doc, "board-list")
    if listing is None:
        raise ValueError("Business notice listing container not found; site structure may have changed")
    values = {n.attrs.get("name"): n.attrs.get("value") for n in doc.walk() if n.tag == "input"}
    if values.get("order_name") != "add_date" or values.get("order_type") != "DESC":
        raise ValueError("The server did not confirm registration-date descending order")
    rows = []
    for row in listing.walk():
        if row.tag != "tr":
            continue
        link = next((n for n in row.walk() if n.tag == "a" and re.search(r"viewBoard\(\s*\d+", n.attrs.get("onclick", ""))), None)
        if link is None:
            continue
        board_id = re.search(r"viewBoard\(\s*(\d+)", link.attrs["onclick"]).group(1)
        date_node = first_class(row, "date")
        if date_node is None or not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", date_node.text()):
            raise ValueError(f"Registration date missing or changed for board {board_id}")
        registered = datetime.strptime(date_node.text(), "%Y.%m.%d").date().isoformat()
        title = row.attrs.get("title") or link.text()
        rows.append({"board_id": board_id, "title": title.strip(), "registration_date": registered,
                     "date_precision": "day", "pinned": first_class(row, "ico-notice") is not None,
                     "listing_url": listing_url,
                     "detail_url": f"{BASE}/main/board/view.do?menu_idx=116&manage_idx=15&board_idx={board_id}"})
    if not rows and first_class(doc, "list_nodata") is None:
        raise ValueError("Listing has no parseable rows and no explicit empty-list marker")
    regular = [r for r in rows if not r["pinned"]]
    dates = [r["registration_date"] for r in regular]
    if dates != sorted(dates, reverse=True):
        raise ValueError("Regular rows are not registration-date descending; cannot establish latest notice")
    pages = [int(n.attrs["keyvalue"]) for n in doc.walk() if n.tag == "a" and n.attrs.get("keyvalue", "").isdigit()]
    return {"rows": rows, "regular_rows": regular, "has_next": max(pages, default=1) > int(values.get("viewPage") or 1)}


def select_latest(rows: list[dict]) -> tuple[dict, dict]:
    unique = {}
    for row in rows:
        key = row["board_id"]
        if key in unique and any(unique[key][k] != row[k] for k in ("registration_date", "title")):
            raise ValueError(f"Conflicting metadata for duplicated board {key}")
        unique.setdefault(key, row)
    if not unique:
        raise ValueError("No public business notices were found")
    ordered = sorted(unique.values(), key=lambda r: (r["registration_date"], int(r["board_id"])), reverse=True)
    latest = dict(ordered[0])
    same_day = [r["board_id"] for r in ordered if r["registration_date"] == latest["registration_date"]]
    return latest, {"rule": "registration_date descending; for same-day posts, numeric board_id descending as a deterministic tie-break only",
                    "date_precision": "day", "exact_registration_time_known": False,
                    "same_day_board_ids": same_day, "same_day_tie": len(same_day) > 1,
                    "tie_rationale": "The public listing exposes a date, not a registration timestamp. A higher board ID does not establish an exact posting time.",
                    "rows_observed": len(rows), "unique_notices": len(unique), "duplicates_removed": len(rows) - len(unique)}


def parse_detail(html: str, selected: dict) -> dict:
    if not isinstance(selected.get("title"), str) or not selected["title"].strip():
        raise ValueError("Selected notice requires a nonempty title")
    doc = Document(html).root
    identity_fields = {}
    for node in doc.walk():
        if node.tag == "input" and node.attrs.get("name") in {"board_idx", "manage_idx"}:
            name, value = node.attrs["name"], node.attrs.get("value", "")
            expected = selected["board_id"] if name == "board_idx" else "15"
            if value and value != expected:
                raise ValueError(f"Detail {name} differs from the selected business notice")
            if value:
                identity_fields[name] = value
    view = first_class(doc, "board-view")
    body = first_class(doc, "view-cont-biz")
    if view is None or body is None:
        raise ValueError("Business notice detail container missing")
    title = first_class(body, "subject")
    if title is None or title.text() != selected["title"]:
        raise ValueError("Detail title differs from the selected listing; refresh source before continuing")
    fields = {}
    for dl in body.walk():
        if dl.tag == "dl":
            terms = [n for n in dl.walk() if n.tag == "dt"]
            definitions = [n for n in dl.walk() if n.tag == "dd"]
            if terms and definitions:
                fields[terms[0].text()] = definitions[0].text()
    attachments = []
    attach = first_class(view, "board-view-attach")
    if attach:
        for link in attach.walk():
            if link.tag != "a":
                continue
            url = urllib.parse.urljoin(BASE, link.attrs.get("href", ""))
            validate_url(url)
            match = re.fullmatch(rf"/board/boardFile/download/15/{selected['board_id']}/(\d+)\.do", urllib.parse.urlsplit(url).path)
            if not match:
                raise ValueError("Unexpected attachment endpoint; explicit review is required")
            label = link.text()
            name = re.sub(r"\s*\([\d.,]+\s*[KMGT]?B\)\s*$", "", label, flags=re.I)
            attachments.append({"file_id": match.group(1), "source_name": name, "label": label, "url": url, "status": "pending"})
    images = []
    for node in body.walk():
        if node.tag == "img":
            url = urllib.parse.urljoin(BASE, node.attrs.get("src", ""))
            if urllib.parse.urlsplit(url).path.startswith(f"/data/board/15/{selected['board_id']}/"):
                validate_url(url)
                images.append(url)
    return {"title": title.text(), "body_text": body.text(), "fields": fields,
            "detail_identity_fields": identity_fields,
            "registration_date_verified_from": "listing",
            "registration_date_detail_verified": False,
            "body_image_urls": list(dict.fromkeys(images)), "body_may_require_image_or_attachment_reading": bool(images),
            "attachments": attachments}


def validate_detail_url(url: str, board_id: str) -> None:
    """Confirm the actual response URL still identifies the selected public notice."""
    validate_url(url)
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    expected = {"menu_idx": "116", "manage_idx": "15", "board_idx": board_id}
    if (parts.path != "/main/board/view.do" or parts.fragment or len(query) != len(expected)
            or dict(query) != expected):
        raise ValueError("Detail response URL differs from the selected business notice identity")


def select_inventory_candidate(board_id: str, inventory_path: Path) -> dict:
    if not isinstance(board_id, str) or not re.fullmatch(r"[1-9][0-9]*", board_id):
        raise ValueError("Explicit board selection requires a canonical positive numeric --board-id")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
    if not isinstance(inventory, dict) or not isinstance(inventory.get("notices"), list):
        raise ValueError("Inventory must be a JSON object containing a notices list")
    if any(not isinstance(item, dict) for item in inventory["notices"]):
        raise ValueError("Each inventory notice must be an object")
    matches = [item for item in inventory["notices"] if str(item.get("board_id")) == board_id]
    if len(matches) != 1:
        raise ValueError("Selected board must occur exactly once in the inventory snapshot")
    row = matches[0]
    expected_url = f"{BASE}/main/board/view.do?menu_idx=116&manage_idx=15&board_idx={board_id}"
    if row.get("detail_url") != expected_url or row.get("source_key") != f"ptp:15:{board_id}":
        raise ValueError("Inventory source identity or official detail URL differs")
    if not isinstance(row.get("title"), str) or not row["title"].strip():
        raise ValueError("Inventory candidate requires a nonempty title")
    date = row.get("registration_date")
    if not isinstance(date, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date):
        raise ValueError("Inventory registration_date must be a canonical YYYY-MM-DD date")
    datetime.strptime(date, "%Y-%m-%d")
    return {"board_id": board_id, "title": row["title"], "registration_date": date,
            "detail_url": expected_url, "date_precision": "day"}


def validate_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "www.ptp.or.kr" or parts.port not in (None, 443) or parts.username or parts.password:
        raise ValueError("Only public HTTPS URLs on www.ptp.or.kr are allowed")
    path = urllib.parse.unquote(parts.path)
    if "\\" in path or any(p == ".." for p in path.split("/")):
        raise ValueError("Unsafe URL path")
    if not (path in {"/main/board/index.do", "/main/board/view.do"} or path.startswith("/board/boardFile/download/15/") or path.startswith("/data/board/15/")):
        raise ValueError("URL outside the public business-notice paths")


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicClient:
    def __init__(self, timeout: int, max_bytes: int):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.warnings = []
        self.legacy_used = False
        self.opener = self._opener(False)

    @staticmethod
    def _opener(legacy: bool):
        context = ssl.create_default_context()
        if legacy:
            context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        return urllib.request.build_opener(PublicRedirect(), urllib.request.HTTPSHandler(context=context))

    def fetch(self, url: str) -> tuple[bytes, dict]:
        validate_url(url)
        request = urllib.request.Request(url, headers={"User-Agent": "PTP-Public-Notice-Collector/1.0", "Accept": "*/*"})
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.URLError as exc:
            if not self.legacy_used and "UNSAFE_LEGACY_RENEGOTIATION_DISABLED" in str(exc):
                self.legacy_used = True
                self.opener = self._opener(True)
                self.warnings.append("PTP required legacy TLS server-connect compatibility. HTTPS certificate and hostname verification remained enabled; redirects are restricted to PTP notice paths.")
                response = self.opener.open(request, timeout=self.timeout)
            else:
                raise
        with response:
            validate_url(response.url)
            declared = response.headers.get("Content-Length", "")
            if declared.isdigit() and int(declared) > self.max_bytes:
                raise ValueError("Response exceeds the configured size limit")
            data = response.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                raise ValueError("Response exceeds the configured size limit")
            return data, {"final_url": response.url, "content_type": response.headers.get("Content-Type", ""),
                          "content_disposition": response.headers.get("Content-Disposition", ""), "http_status": response.status}


def safe_filename(name: str, file_id: str) -> str:
    if not file_id.isdigit():
        raise ValueError("Invalid attachment ID")
    name = unicodedata.normalize("NFC", name)
    name = re.split(r"[/\\]", name)[-1]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", name).strip(" .")
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported or executable attachment extension")
    stem = name[:-len(suffix)].strip(" .")[:120] or "attachment"
    return f"{file_id}_{stem}{suffix}"


def validate_attachment(data: bytes, filename: str, content_type: str) -> None:
    if not data:
        raise ValueError("Empty attachment response")
    start = data[:1024].lstrip(b"\xef\xbb\xbf \r\n\t").lower()
    if "text/html" in content_type.lower() or re.search(br"<(?:!doctype\s+html|html|head|body|script)\b", start):
        raise ValueError("Attachment endpoint returned an HTML/error page")
    suffix = Path(filename).suffix.lower()
    ole = data.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
    zipped = data.startswith(b"PK\x03\x04")
    checks = {
        ".pdf": data.startswith(b"%PDF-"), ".jpg": data.startswith(b"\xff\xd8\xff"),
        ".jpeg": data.startswith(b"\xff\xd8\xff"), ".png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        ".gif": data.startswith((b"GIF87a", b"GIF89a")), ".webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
        ".hwp": ole or data.startswith(b"HWP Document File"), ".doc": ole, ".xls": ole, ".ppt": ole,
        ".hwpx": zipped, ".docx": zipped, ".xlsx": zipped, ".pptx": zipped, ".zip": zipped,
        ".rtf": data.startswith(b"{\\rtf"),
    }
    if suffix in checks and not checks[suffix]:
        raise ValueError(f"Downloaded bytes do not match the {suffix} file signature")
    if suffix in {".txt", ".csv"} and (data.startswith(b"MZ") or b"\x00" in data[:1024]):
        raise ValueError("Unexpected binary content in a text attachment")


def save_evidence(directory: Path, name: str, data: bytes) -> dict:
    target = directory / name
    if target.exists():
        raise FileExistsError(f"Evidence file already exists: {target}; use a fresh output directory")
    target.write_bytes(data)
    return {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def download_attachment(item: dict, output_dir: Path, fetch: Callable) -> dict:
    result = dict(item)
    try:
        filename = safe_filename(item["source_name"], item["file_id"])
        directory = output_dir / "attachments"
        directory.mkdir(exist_ok=True)
        target = directory / filename
        if not target.resolve().is_relative_to(output_dir.resolve()):
            raise ValueError("Attachment path escapes output directory")
        data, metadata = fetch(item["url"])
        validate_attachment(data, filename, metadata.get("content_type", ""))
        evidence = save_evidence(directory, filename, data)
        evidence["path"] = "attachments/" + filename
        result.update(metadata, **evidence, status="downloaded")
    except (OSError, ValueError) as exc:
        result.update(status="failed", error=str(exc))
    return result


def collect(output_dir: Path, timeout: int = 30, max_bytes: int = 25 * 1024 * 1024,
            board_id: str | None = None, inventory_path: Path | None = None) -> dict:
    if (board_id is None) != (inventory_path is None):
        raise ValueError("--board-id and --inventory must be used together")
    candidate = select_inventory_candidate(board_id, inventory_path) if board_id is not None else None
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty to preserve collection evidence")
    client = PublicClient(timeout, max_bytes)
    all_rows, listings = [], []
    # Default results prioritize ongoing notices. Explicit supported status partitions
    # are necessary to include newly registered closed or not-yet-open notices.
    for status in ("", "before", "ongoing", "after"):
        previous_tail = None
        for page in range(1, 11):
            query = {"menu_idx": "116", "manage_idx": "15", "bid_search": status, "order_name": "add_date", "order_type": "DESC", "viewPage": str(page)}
            url = BASE + "/main/board/index.do?" + urllib.parse.urlencode(query)
            data, metadata = client.fetch(url)
            evidence = save_evidence(output_dir, f"listing-{status or 'default'}-{page}.html", data)
            listing = parse_listing(data.decode("utf-8-sig"), url)
            rows = listing["rows"]
            regular = listing["regular_rows"]
            if previous_tail and regular and regular[0]["registration_date"] > previous_tail:
                raise ValueError("Registration-date order changed across listing pages")
            all_rows.extend(rows)
            listings.append({"status_filter": status or "default", "page": page, "url": url,
                             "row_count": len(rows), **metadata, **evidence})
            latest_date = max((r["registration_date"] for r in all_rows), default="")
            if not regular or not listing["has_next"] or regular[-1]["registration_date"] < latest_date:
                break
            previous_tail = regular[-1]["registration_date"]
        else:
            raise ValueError("Same-day pagination exceeded 10 pages; latest selection requires manual review")
    selected, selection = select_latest(all_rows)
    if board_id is not None:
        selected = candidate
        observed = [row for row in all_rows if row["board_id"] == board_id]
        if any(row["registration_date"] != selected["registration_date"] for row in observed):
            raise ValueError("Inventory registration date differs from the current listing; refresh the inventory")
        selection = {"rule": "Explicit inventory candidate; current detail title and identity rechecked",
                     "inventory_path": str(inventory_path.resolve()), "latest_overall_board_id": select_latest(all_rows)[0]["board_id"],
                     "registration_date_current_listing_verified": bool(observed),
                     "publication_eligibility_verified": False}
    data, metadata = client.fetch(selected["detail_url"])
    validate_detail_url(metadata.get("final_url", ""), selected["board_id"])
    detail_evidence = save_evidence(output_dir, "detail.html", data)
    detail = parse_detail(data.decode("utf-8-sig"), selected)
    if board_id is not None and not selection["registration_date_current_listing_verified"]:
        detail["registration_date_verified_from"] = "inventory snapshot; not present in current latest-only listing sample"
    attachments = [download_attachment(item, output_dir, client.fetch) for item in detail.pop("attachments")]
    failed = [item for item in attachments if item["status"] != "downloaded"]
    report = {"schema_version": "1.0", "collected_at": datetime.now(timezone.utc).isoformat(),
              "status": "partial" if failed else "collected", "source_url": LIST_URL,
              "selected": selected, "selection": selection,
              "listing_scope": "Default plus all three public status filters (before, ongoing, after), registration-date descending; later pages followed while they can contain same-day candidates.",
              "listing_evidence": listings, "detail_evidence": {**metadata, **detail_evidence},
              **detail, "attachments": attachments, "warnings": client.warnings,
              "publication_ready": False,
              "next_required_action": "Read the original PDF/HWP and image content, reconcile facts and dates, then prepare and review SNS content. Collection alone is not factual or publishing approval."}
    (output_dir / "source.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New or empty evidence directory")
    parser.add_argument("--timeout", type=int, default=30, help="Per HTTP request timeout in seconds")
    parser.add_argument("--max-download-mib", type=int, default=25, help="Maximum bytes per response, in MiB")
    parser.add_argument("--board-id", help="Explicit eligible/unpublished notice selected from an inventory snapshot")
    parser.add_argument("--inventory", type=Path, help="inventory.json containing the explicitly selected notice")
    args = parser.parse_args()
    if args.timeout < 1 or not 1 <= args.max_download_mib <= 200:
        parser.error("timeout must be positive and max-download-mib must be 1..200")
    if bool(args.board_id) != bool(args.inventory):
        parser.error("--board-id and --inventory must be used together")
    try:
        report = collect(args.output_dir, args.timeout, args.max_download_mib * 1024 * 1024, args.board_id, args.inventory)
        selected = report["selected"]
        print(json.dumps({"status": report["status"], "board_id": selected["board_id"], "title": selected["title"],
                          "registration_date": selected["registration_date"], "attachments_downloaded": sum(a["status"] == "downloaded" for a in report["attachments"]),
                          "attachments_failed": sum(a["status"] == "failed" for a in report["attachments"]),
                          "source_json": str((args.output_dir / "source.json").resolve())}, ensure_ascii=False))
        return 0 if report["status"] == "collected" else 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
