"""Download the artifact each citation is checked against.

One file per citation key under `reference/`, chosen in this order:

    1. Europe PMC full text XML, when the work is in the PMC open-access subset
    2. NCBI PMC full text XML, which also serves NIH-funded author manuscripts that
       Europe PMC returns 404 for because they sit outside the open-access subset
    3. PubMed record XML (title + abstract + metadata), via NCBI efetch
    4. Crossref metadata JSON, when there is a DOI but no PMID

The abstract tier is an abstract, not a paper. A quote that resolves against an abstract
file is verified as a quotation of the abstract and nothing more. The tier is written into
each record so the distinction survives.

Writes after every fetch, so an interrupted run keeps what it got, and skips keys whose
file already exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import time
import subprocess
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIB = ROOT / "paper" / "references.bib"
OUT = ROOT / "reference"
LEDGER = ROOT / "reference" / "FETCH_LOG.json"
UA = {"User-Agent": "neurology-nosology citations pass (elliot@elliottower.ai)"}

EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
CROSSREF = "https://api.crossref.org/works/"


class FetchError(Exception):
    pass


def get(url: str, timeout: int = 40) -> bytes:
    """Retrieve a URL with curl.

    Python's urllib fails here with CERTIFICATE_VERIFY_FAILED: a TLS-inspecting proxy sits
    in front of this machine and signs with a root certifi does not carry. curl reads the
    system keychain, which has it.
    """
    r = subprocess.run(
        ["curl", "-sSL", "--max-time", str(timeout), "-A", UA["User-Agent"],
         "-w", "\n%{http_code}", url],
        capture_output=True)
    if r.returncode != 0:
        raise FetchError(r.stderr.decode(errors="replace").strip()[:120])
    body, _, code = r.stdout.rpartition(b"\n")
    if code.strip() != b"200":
        raise FetchError(f"HTTP {code.decode(errors='replace').strip()}")
    return body


def parse_bib(text: str) -> dict[str, dict]:
    """Citation key -> {pmid, doi, title}. Entries are read whole, not line by line."""
    out: dict[str, dict] = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        start = m.end()
        depth, i = 1, m.start()
        i = text.index("{", m.start())
        depth, j = 1, i + 1
        while j < len(text) and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[start:j]
        key = m.group(2)
        pmid = re.search(r"PMID[:\s]*(\d{5,9})", body)
        doi = re.search(r"doi\s*=\s*\{([^}]+)\}", body, re.I)
        title = re.search(r"title\s*=\s*\{(.+?)\}\s*,\s*\n", body, re.S)
        out[key] = {
            "pmid": pmid.group(1) if pmid else "",
            "doi": doi.group(1).strip() if doi else "",
            "title": " ".join(title.group(1).split()) if title else "",
            "kind": m.group(1),
        }
    return out


def pmcid_for(pmid: str) -> str:
    try:
        data = json.loads(get(f"{IDCONV}?ids={pmid}&format=json&tool=citations&email=elliot@elliottower.ai"))
    except (FetchError, json.JSONDecodeError):
        return ""
    for rec in data.get("records", []):
        if rec.get("pmcid"):
            return rec["pmcid"]
    return ""


def fetch(key: str, meta: dict) -> tuple[str, str, str] | None:
    """(filename, tier, note), or None when nothing could be retrieved."""
    pmid = meta["pmid"]
    if pmid:
        pmcid = pmcid_for(pmid)
        time.sleep(0.4)
        if pmcid:
            try:
                body = get(f"{EPMC}/{pmcid}/fullTextXML")
                if len(body) > 2000:
                    (OUT / f"{key}.xml").write_bytes(body)
                    return f"{key}.xml", "fulltext", f"Europe PMC {pmcid}"
            except FetchError:
                pass
            time.sleep(0.4)
            try:
                body = get(f"{EFETCH}?db=pmc&id={pmcid[3:] if pmcid.startswith('PMC') else pmcid}&retmode=xml")
                if b"<body" in body and len(body) > 20000:
                    (OUT / f"{key}.xml").write_bytes(body)
                    return f"{key}.xml", "fulltext", f"NCBI PMC {pmcid}"
            except FetchError:
                pass
            time.sleep(0.4)
        try:
            body = get(f"{EFETCH}?db=pubmed&id={pmid}&retmode=xml")
            if len(body) > 500:
                (OUT / f"{key}.xml").write_bytes(body)
                return f"{key}.xml", "abstract", f"PubMed {pmid}"
        except FetchError:
            return None
    if meta["doi"]:
        try:
            body = get(CROSSREF + urllib.parse.quote(meta["doi"], safe=""))
            (OUT / f"{key}.json").write_bytes(body)
            return f"{key}.json", "metadata", f"Crossref {meta['doi']}"
        except FetchError:
            return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="one citation key")
    ap.add_argument("--refetch", action="store_true", help="re-download keys already on disk")
    ap.add_argument("--bib", default=str(BIB),
                    help="bibliography to read keys from (default: paper/references.bib)")
    a = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    entries = parse_bib(pathlib.Path(a.bib).read_text())
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}

    keys = [a.only] if a.only else sorted(entries)
    for key in keys:
        meta = entries.get(key)
        if meta is None:
            print(f"  {key:28s} not in the bibliography")
            continue
        if meta["kind"] == "unpublished" and not meta["pmid"] and not meta["doi"]:
            continue
        if key in ledger and not a.refetch and (OUT / ledger[key]["file"]).exists():
            print(f"  {key:28s} have it ({ledger[key]['tier']})")
            continue
        got = fetch(key, meta)
        if got is None:
            print(f"  {key:28s} NOTHING  (pmid={meta['pmid'] or '-'} doi={meta['doi'] or '-'})")
            ledger[key] = {"file": "", "tier": "none", "note": "no identifier resolved"}
        else:
            fname, tier, note = got
            digest = hashlib.sha256((OUT / fname).read_bytes()).hexdigest()
            ledger[key] = {"file": fname, "tier": tier, "note": note, "sha256": digest}
            print(f"  {key:28s} {tier:9s} {note}")
        LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True))
        time.sleep(0.5)

    tiers: dict[str, int] = {}
    for v in ledger.values():
        tiers[v["tier"]] = tiers.get(v["tier"], 0) + 1
    print("\n  " + "  ".join(f"{k} {v}" for k, v in sorted(tiers.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
