"""Shared utilities for the 2026-09-04 provider feasibility probes.

Isolation contract (probes/README.md):
- Loads ONLY the explicitly requested credential NAMES from an explicit
  .env file. Nothing is copied anywhere; values never appear in printed
  or written output.
- Every string that leaves this process (stdout, evidence files) passes
  through `redact()`, which replaces the loaded secret values and any
  key-shaped token with placeholders.
- Request headers are deliberately NOT part of any captured record (they
  carry the credential); only response headers are captured.
- Pure standard library. No app/benchmark imports.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

# Key-shape patterns redacted regardless of source (defense in depth).
_KEY_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{10,}"),
    re.compile(r"csk-[0-9A-Za-z_\-]{10,}"),
    re.compile(r"gsk_[0-9A-Za-z_\-]{10,}"),
    re.compile(r"sk-[0-9A-Za-z_\-]{10,}"),
    re.compile(r"Bearer\s+[0-9A-Za-z_\-.]+"),
]


def load_credentials(env_file: Path, names: list[str]) -> dict[str, str]:
    """Load ONLY `names` from a .env-style file. Values are never printed."""
    env_file = Path(env_file)
    if not env_file.exists():
        raise SystemExit(f"env file not found: {env_file}")
    found: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip().strip("'\"")
        if key in names and key not in found and value:
            found[key] = value
    missing = [n for n in names if n not in found]
    if missing:
        raise SystemExit("credential(s) not present in env file: " + ", ".join(missing))
    return found


def make_redactor(secrets: dict[str, str]):
    """Return a redact(text) that masks loaded secrets + key-shaped tokens."""

    def redact(text: str) -> str:
        for name, value in secrets.items():
            if value:
                text = text.replace(value, f"<REDACTED:{name}>")
        for pattern in _KEY_PATTERNS:
            text = pattern.sub("<REDACTED:key-shape>", text)
        return text

    return redact


def http_json(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict | None = None,
    timeout: float = 90.0,
) -> dict:
    """One HTTP call, fully captured. No retries — by design.

    The returned record never includes the request headers (credential
    carrier). Response headers ARE included (rate-limit evidence).
    """
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in headers.items():
        req.add_header(key, value)
    start = time.perf_counter()
    record: dict = {
        "method": method,
        "url": url,
        "status": None,
        "headers": {},
        "body": None,
        "elapsed_ms": None,
        "error": None,
    }
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            record["status"] = resp.status
            record["headers"] = dict(resp.headers.items())
            record["body"] = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:  # 4xx/5xx carry the useful headers/bodies
        record["status"] = exc.code
        record["headers"] = dict(exc.headers.items()) if exc.headers else {}
        record["body"] = exc.read().decode("utf-8", "replace")
    except Exception as exc:  # URLError, timeout, TLS, ...
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return record


def body_json(record: dict) -> dict | list | None:
    """Best-effort JSON parse of a captured response body."""
    if record.get("body") is None:
        return None
    try:
        return json.loads(record["body"])
    except (TypeError, ValueError):
        return None


class Evidence:
    """Appends sanitized machine records to <stem>.json and a human
    summary to <stem>.txt; prints the summary."""

    def __init__(self, stem: Path, redact) -> None:
        self.stem = Path(stem)
        self.redact = redact
        self.records: list[dict] = []
        self.stem.parent.mkdir(parents=True, exist_ok=True)

    def add(self, label: str, record: dict | None = None, note: str | None = None) -> None:
        self.records.append({"label": label, "record": record, "note": note})

    def dump(self, summary_lines: list[str]) -> None:
        safe_records = json.loads(self.redact(json.dumps(self.records, indent=2, default=str)))
        self.stem.with_suffix(".json").write_text(
            json.dumps(safe_records, indent=2, default=str) + "\n", encoding="utf-8"
        )
        lines = [self.redact(line) for line in summary_lines]
        self.stem.with_suffix(".txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
