"""Write `claims/` from the quotation inventory, one file per source and artifact.

Each file names the artifact the quotation is checked against, its sha256, and the tier
that artifact reached (full text, abstract, or metadata only). `citations verify --claims
claims` reads these and reports found / not found / unchecked per quotation.

Some sources are stored twice: the PubMed record of the published version, and the author
manuscript deposited in PubMed Central, which is the accepted text before copyediting and
differs from the published wording. A quotation taken from the published abstract does not
resolve in the author manuscript and the reverse also holds, so each quotation is pinned to
the artifact it was taken from and a source with quotations from both gets two files,
`<key>.yaml` and `<key>--<tier>.yaml`. A quotation present in neither is pinned to the
primary artifact, where the check reports it not found.

Quotations come from `paper/QUOTES_TO_PIN.md`, which carries the two hand-corrections the
automatic extraction got wrong; re-extracting from the .tex would lose them. Section labels
come from the .tex, located by matching each quotation against the source.
"""
from __future__ import annotations

import json
import pathlib
import re
import unicodedata

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "paper" / "QUOTES_TO_PIN.md"
STEM = (ROOT / "paper" / "CURRENT_VERSION").read_text().strip()
TEX = ROOT / "paper" / f"{STEM}.tex"
LEDGER = ROOT / "reference" / "FETCH_LOG.json"
OUT = ROOT / "claims"

TIER_NOTE = {
    "fulltext": "Europe PMC open-access full text. A quotation that resolves here is "
                "checked against the paper.",
    "abstract": "PubMed record: title, abstract and metadata. A quotation that resolves "
                "here is checked against the abstract and against nothing else.",
    "openalex-abstract": "Abstract reconstructed from the OpenAlex inverted index, which "
                         "stores each word with its positions. Word order is recovered "
                         "exactly; sentence spacing and some punctuation are not, so a "
                         "quotation crossing a sentence boundary may fail to resolve here "
                         "and no quotation should be drawn across one. This is the weakest "
                         "artifact in the repository and is not the paper.",
    "registry": "ClinicalTrials.gov API v2 protocol record: title, status, design, "
                "verbatim eligibility criteria and outcome measures. A quotation that "
                "resolves here is checked against what the sponsor registered, which is "
                "not always what the published paper reports.",
    "pdf": "Text extracted from the publisher PDF of record. A quotation that "
           "resolves here is checked against the full published article, including "
           "its tables and panels; column and line breaks are collapsed by the "
           "extraction, so whitespace inside a resolved quotation is normalized.",
    "metadata": "Title, authors and indexing terms, no abstract and no body. The title "
                "resolves; nothing else in the source is present to resolve against, so a "
                "quotation of anything the paper says is a quotation of the title.",
}

AUTHOR_MANUSCRIPT = (" The full text stored for this source is the author manuscript "
                     "deposited in PubMed Central, which is the accepted text before "
                     "copyediting and differs in wording from the published version.")


def fold(s: str) -> str:
    """Match the way `citations verify` compares a quotation to a stored file."""
    s = unicodedata.normalize("NFKC", s)
    for a, b in [("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'),
                 ("\u2014", "-"), ("\u2013", "-"), ("\u2212", "-")]:
        s = s.replace(a, b)
    return " ".join(s.split()).lower()


def contains(hay: str, needle: str) -> bool:
    if fold(needle) in fold(hay):
        return True
    thin = lambda t: re.sub(r"[^a-z0-9]", "", fold(t))
    return bool(thin(needle)) and thin(needle) in thin(hay)


def artifacts_for(key: str, rec: dict, ref: pathlib.Path) -> list[dict]:
    """The stored copies of one source, primary first."""
    out = []
    for r, label in ((rec, ""), (rec.get("alt") or {}, "alt")):
        if not r.get("file"):
            continue
        note = TIER_NOTE.get(r.get("tier", ""), "No artifact retrieved for this source.")
        if not label and (rec.get("alt") or {}).get("tier") == "abstract":
            note += AUTHOR_MANUSCRIPT
        out.append({
            "which": label,
            "tier": r.get("tier", "none"),
            "text": (ref / r["file"]).read_text(errors="replace")
                    if (ref / r["file"]).exists() else "",
            "block": {
                "citation": key,
                "local": f"reference/{r['file']}",
                "sha256": r.get("sha256", ""),
                "tier": r.get("tier", "none"),
                "retrieved_from": r.get("note", ""),
                "extract_cmd": r.get("extract_cmd", ""),
                "xml": f"reference/{r['xml']}" if r.get("xml") else "",
                "xml_sha256": r.get("xml_sha256", ""),
                "read_in_full": r.get("tier") == "fulltext",
                "note": note,
            },
        })
    return out


def straighten(s: str) -> str:
    """LaTeX quote marks to the characters a downloaded record actually contains."""
    s = s.replace("``", '"').replace("''", '"')
    s = re.sub(r"(?<![a-zA-Z])`", "'", s)
    return s


def parse_inventory(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    key = None
    for line in text.splitlines():
        m = re.match(r"^### `([^`]+)`", line)
        if m:
            key = m.group(1)
            out[key] = []
            continue
        if key and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4 or not cells[0].isdigit():
                continue
            q = cells[1].strip()
            if q.startswith('"') and q.endswith('"'):
                q = q[1:-1]
            out[key].append(straighten(q))
    return {k: v for k, v in out.items() if v}


def skeleton(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def section_index(tex: str) -> list[tuple[int, str]]:
    marks = []
    for m in re.finditer(r"\\(section|subsection|paragraph)\{([^}]*)\}", tex):
        marks.append((m.start(), m.group(2)))
    return marks


def locate(tex: str, marks: list[tuple[int, str]], quote: str) -> str:
    flat = skeleton(tex)
    # Offsets in the skeleton are not offsets in the source, so walk the source instead and
    # keep a running skeleton position for each section mark.
    at = flat.find(skeleton(quote))
    if at < 0:
        return "unlocated"
    running, cut = 0, "unlocated"
    for pos, name in marks:
        running = len(skeleton(tex[:pos]))
        if running <= at:
            cut = name
        else:
            break
    return cut


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "body"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    inv = parse_inventory(INVENTORY.read_text())
    tex = TEX.read_text()
    marks = section_index(tex)
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    ref = ROOT / "reference"

    kept, missing_artifact, split = set(), [], []
    for key, quotes in sorted(inv.items()):
        arts = artifacts_for(key, ledger.get(key, {}), ref)
        if not arts:
            missing_artifact.append(key)
            arts = [{"which": "", "tier": "none", "text": "",
                     "block": {"citation": key, "local": "", "sha256": "", "tier": "none",
                               "read_in_full": False,
                               "note": "No artifact retrieved for this source."}}]

        grouped: dict[int, dict[str, dict]] = {}
        for q in quotes:
            sec = slugify(locate(tex, marks, q))
            # A quotation printed with an ellipsis is two passages, and the elided words are
            # in the source between them. Checked as one string it reads as absent; checked as
            # two it says what it should, that both halves are there and something was cut.
            parts = [x.strip() for x in re.split(r"\s*(?:\u2026|\\ldots|\.\.\.)\s*", q) if x.strip()]
            at = 0
            for i, a in enumerate(arts):
                if a["text"] and all(contains(a["text"], p) for p in parts):
                    at = i
                    break
            for part in parts:
                entry = {"exact": part, "page": None}
                if len(parts) > 1:
                    entry["elided"] = "one half of a quotation the paper prints with an ellipsis"
                grouped.setdefault(at, {}).setdefault(sec, {"quotes": []})["quotes"].append(entry)

        if len(grouped) > 1:
            split.append(key)
        for i, secs in sorted(grouped.items()):
            a = arts[i]
            name = key if not a["which"] else f"{key}--{a['tier']}"
            doc = {
                "claim": key,
                "title": f"Quotations from {key} used in {STEM}.tex",
                "source": a["block"],
                "claims": secs,
            }
            (OUT / f"{name}.yaml").write_text(
                yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100))
            kept.add(f"{name}.yaml")

    stale = [p for p in OUT.glob("*.yaml") if p.name not in kept]
    for p in stale:
        p.unlink()

    print(f"  wrote {len(kept)} claim files, {sum(len(v) for v in inv.values())} quotations")
    if split:
        print(f"  quoted from two stored copies: {', '.join(split)}")
    if stale:
        print(f"  removed {len(stale)} stale claim files")
    if missing_artifact:
        print(f"  no artifact on disk for {len(missing_artifact)}: {', '.join(missing_artifact)}")


if __name__ == "__main__":
    main()
