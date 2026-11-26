#!/usr/bin/env python3
"""Create plain public-link QR assets and independently decode exported images.

No network requests, browser access, redirects, shortening, or credentials.
Requires qrcode, Pillow and zxing-cpp; see references/qr-code-workflow.md.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import ipaddress
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

DEFAULT_HOSTS = {"ptp.or.kr", "www.ptp.or.kr"}
DENIED_QUERY = re.compile(
    r"token|secret|password|passwd|session|credential|authorization|signature|"
    r"api[_-]?key|access[_-]?key|^code$|^state$|^otp$|^ticket$|^sso$|^auth$|"
    r"^fbclid$|^gclid$|^utm[_-]", re.I
)
DENIED_PATH = re.compile(r"(?:^|/)(?:login|signin|sign-in|oauth|sso|authorize|callback)(?:[/.;]|$)", re.I)


def checked_url(value: str, allowed_hosts: list[str]) -> str:
    """Validate syntax only; the caller must verify public destination separately."""
    if value != value.strip() or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("URL must not contain whitespace/control characters")
    if "\\" in value or len(value) > 2048:
        raise ValueError("URL contains a backslash or exceeds 2048 characters")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("Only a complete HTTPS URL is accepted")
    if parts.username is not None or parts.password is not None or parts.fragment:
        raise ValueError("Credentials and URL fragments are not allowed")
    if parts.port not in (None, 443):
        raise ValueError("Only the default HTTPS port is accepted")
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
        raise ValueError("The destination must have a public hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP-address destinations are not allowed")
    approved = DEFAULT_HOSTS | {h.lower() for h in allowed_hosts}
    if host not in approved:
        raise ValueError("Host is not allowlisted; verify the public source before using --allow-host")
    decoded_path = unquote(parts.path)
    if DENIED_PATH.search(decoded_path):
        raise ValueError("Login/authentication destinations are not allowed")
    for key, _ in parse_qsl(parts.query, keep_blank_values=True):
        if DENIED_QUERY.search(key):
            raise ValueError("Credential, authentication or tracking query parameters are not allowed")
    return value


def libraries():
    try:
        import qrcode
        import qrcode.image.svg
        from PIL import Image
        import zxingcpp
    except ImportError as exc:
        raise RuntimeError("Install qrcode[pil]==8.2 Pillow==11.3.0 zxing-cpp==2.3.0 in an isolated Python environment") from exc
    return qrcode, Image, zxingcpp


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata() -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dependencies": {name: importlib.metadata.version(name) for name in ("qrcode", "Pillow", "zxing-cpp")},
        "network_access_performed": False,
        "destination_public_access_verified": False,
        "source_verification_note": "Syntax/allowlist check only. Confirm current public source separately; this tool never opens the URL.",
    }


def decode_checks(path: Path, expected_url: str, scales: list[float], Image, zxingcpp) -> dict:
    with Image.open(path) as opened:
        opened.load()
        image = opened.convert("RGB")
    checks = []
    for scale in scales:
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        sample = image if scale == 1 else image.resize(size, Image.Resampling.LANCZOS)
        results = zxingcpp.read_barcodes(sample, formats=zxingcpp.BarcodeFormat.QRCode)
        # Do not copy unrelated or potentially sensitive decoded data into reports.
        decoded = [{"matches_expected_url": r.text == expected_url,
                    "decoded_text_sha256": hashlib.sha256(r.text.encode("utf-8")).hexdigest()} for r in results]
        passed = len(results) == 1 and results[0].text == expected_url
        checks.append({"scale": scale, "width": size[0], "height": size[1],
                       "qr_count": len(results), "decoded": decoded, "passed": passed})
    return {"image": str(path.resolve()), "sha256": sha256(path),
            "decoder": "zxing-cpp (independent from qrcode encoder)",
            "checks": checks, "passed": all(c["passed"] for c in checks)}


def write_json_exclusive(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def generate(args) -> int:
    url = checked_url(args.url, args.allow_host)
    if args.label != "상세 공고 보기":
        raise ValueError("Notice QR label must be '상세 공고 보기'; a notice is not a direct application form")
    if not 4 <= args.box_size <= 32:
        raise ValueError("--box-size must be an integer from 4 to 32; default 8 is recommended")
    qrcode, Image, zxingcpp = libraries()
    output = Path(args.output_dir).resolve()
    # A fresh directory is mandatory, including an existing empty directory.
    output.mkdir(parents=True, exist_ok=False)
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=args.box_size, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    png_path, svg_path = output / "qr.png", output / "qr.svg"
    png = qr.make_image(fill_color="black", back_color="white").get_image().convert("RGB")
    with png_path.open("xb") as stream:
        png.save(stream, format="PNG")
    svg = qr.make_image(image_factory=qrcode.image.svg.SvgPathFillImage)
    with svg_path.open("xb") as stream:
        svg.save(stream)
    verification = decode_checks(png_path, url, [1.0, 0.5], Image, zxingcpp)
    report = {
        **metadata(), "kind": "qr-generation", "url": url,
        "label": args.label, "label_rendered_in_qr": False,
        "label_instruction": "Place this label outside the white quiet zone during card composition.",
        "qr_version": qr.version, "data_modules_per_side": qr.modules_count,
        "quiet_zone_modules": 4, "pixels_per_module": args.box_size,
        "width": png.width, "height": png.height, "error_correction": "M",
        "colors": {"foreground": "#000000", "background": "#FFFFFF"},
        "files": [{"path": str(p), "sha256": sha256(p)} for p in (png_path, svg_path)],
        "png_verification": verification,
        "svg_verification": "Generated from the same matrix; SVG rasterization has not been independently decoded.",
        "final_card_export_verified": False,
        "passed": verification["passed"],
    }
    report_path = output / "qr-report.json"
    write_json_exclusive(report_path, report)
    print(json.dumps({"passed": report["passed"], "report": str(report_path),
                      "png": str(png_path), "svg": str(svg_path)}, ensure_ascii=False))
    return 0 if report["passed"] else 2


def verify(args) -> int:
    url = checked_url(args.expected_url, args.allow_host)
    if not args.scales or any(not 0.05 <= scale <= 1 for scale in args.scales):
        raise ValueError("Verification scales must be between 0.05 and 1")
    scales = sorted(set([1.0] + args.scales), reverse=True)
    path, report_path = Path(args.image).resolve(), Path(args.report).resolve()
    if report_path.exists():
        raise FileExistsError("Verification report already exists; choose a new path")
    _, Image, zxingcpp = libraries()
    result = decode_checks(path, url, scales, Image, zxingcpp)
    report = {**metadata(), "kind": "export-image-decode", "expected_url": url,
              "image_verification": result, "passed": result["passed"],
              "scope": "Entire supplied image at actual and downscaled dimensions; not a physical-phone or platform-compression test."}
    write_json_exclusive(report_path, report)
    print(json.dumps({"passed": report["passed"], "report": str(report_path)}, ensure_ascii=False))
    return 0 if report["passed"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="Generate PNG, SVG, and independent PNG decode report into a NEW directory")
    gen.add_argument("--url", required=True)
    gen.add_argument("--output-dir", required=True)
    gen.add_argument("--label", default="상세 공고 보기")
    gen.add_argument("--box-size", type=int, default=8)
    gen.add_argument("--allow-host", action="append", default=[], help="Explicitly verified public host, exact match only")
    gen.set_defaults(run=generate)
    check = sub.add_parser("verify", help="Independently decode a final exported card or platform-downloaded image")
    check.add_argument("--image", required=True)
    check.add_argument("--expected-url", required=True)
    check.add_argument("--report", required=True, help="New JSON path; never overwrite")
    check.add_argument("--scales", nargs="+", type=float, default=[1.0, 0.5])
    check.add_argument("--allow-host", action="append", default=[])
    check.set_defaults(run=verify)
    args = parser.parse_args()
    try:
        return args.run(args)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
