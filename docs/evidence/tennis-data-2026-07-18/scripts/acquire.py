"""Tennis-Data.co.uk historical acquisition (founder-approved, 2026-07-18).

Downloads all ATP (2000-2026) and WTA (2007-2026) yearly files. Per year, probes the
known format variants and takes the first that exists. Raw bytes preserved exactly;
sorted SHA-256 manifest + manifest digest; retrieval timestamp, source URL, and HTTP
headers (Last-Modified/ETag = observable provider version) recorded per file.
Vintage discipline: files land under vintage-2026-07-18/; a later re-download goes to a
NEW vintage directory, never overwriting.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time

BASE = "http://www.tennis-data.co.uk"
ROOT = os.path.dirname(os.path.abspath(__file__))
VINTAGE = os.path.join(ROOT, "raw", "vintage-2026-07-18")
FORMATS = ["{y}.xlsx", "{y}.xls", "{y}.zip", "{y}.csv"]


def try_download(url: str, dest: str) -> dict | None:
    headers_file = dest + ".headers"
    r = subprocess.run(
        ["curl", "-sS", "-o", dest, "-D", headers_file, "-w", "%{http_code}", "--max-time", "120", url],
        capture_output=True,
        text=True,
    )
    code = r.stdout.strip()
    if code != "200":
        for p in (dest, headers_file):
            if os.path.exists(p):
                os.remove(p)
        return None
    headers = open(headers_file).read()
    hdr = {}
    for line in headers.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if k.lower() in ("last-modified", "etag", "content-length", "content-type"):
                hdr[k.lower()] = v.strip()
    os.remove(headers_file)
    return hdr


def main() -> None:
    os.makedirs(VINTAGE, exist_ok=True)
    provenance = []
    for tour, years, sub in (
        ("ATP", range(2000, 2027), "{y}"),
        ("WTA", range(2007, 2027), "{y}w"),
    ):
        for y in years:
            got = False
            for fmt in FORMATS:
                fname = fmt.format(y=y)
                url = f"{BASE}/{sub.format(y=y)}/{fname}"
                dest = os.path.join(VINTAGE, f"{tour.lower()}-{fname}")
                hdr = try_download(url, dest)
                if hdr is not None:
                    digest = hashlib.sha256(open(dest, "rb").read()).hexdigest()
                    provenance.append(
                        {
                            "tour": tour,
                            "year": y,
                            "source_url": url,
                            "source_file_name": fname,
                            "stored_as": os.path.basename(dest),
                            "sha256": digest,
                            "size_bytes": os.path.getsize(dest),
                            "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "provider_version_headers": hdr,
                        }
                    )
                    got = True
                    break
            if not got:
                provenance.append(
                    {"tour": tour, "year": y, "source_url": None, "error": "NO_FORMAT_FOUND"}
                )
            time.sleep(0.4)  # polite pacing
    with open(os.path.join(ROOT, "PROVENANCE.json"), "w") as f:
        json.dump(provenance, f, indent=1)
    ok = [p for p in provenance if p.get("sha256")]
    miss = [p for p in provenance if not p.get("sha256")]
    print(f"downloaded {len(ok)} files; missing: {[(m['tour'], m['year']) for m in miss]}")
    # sorted manifest + digest of manifest
    lines = sorted(f"{p['sha256']}  {p['stored_as']}" for p in ok)
    manifest = "\n".join(lines) + "\n"
    with open(os.path.join(ROOT, "MANIFEST.sha256"), "w") as f:
        f.write(manifest)
    print("manifest digest:", hashlib.sha256(manifest.encode()).hexdigest())
    print("file count:", len(lines))


if __name__ == "__main__":
    main()
