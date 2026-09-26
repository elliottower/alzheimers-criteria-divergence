"""Every ``...'' in the paper, checked against the stored artifacts of the sources cited near it.

This audits the manuscript directly, where `citations verify --claims claims` audits the
claims/ manifest. A quotation added to the .tex and not to the manifest is invisible to the
second and caught by the first.

What it does not catch: a quotation attributed to the wrong one of two sources cited in the
same paragraph. Matching is against every key in the neighbourhood, because the nearest key
is often not the source ("the same document restricts", "which the same paper asserts"), so
a passage present in either neighbour passes. Read the sentence for attribution.

An ellipsis is treated as omitted text: each fragment must appear, contiguity is not required.
"""
import pathlib, re, sys, unicodedata

# The repository this script sits in, whatever it is called and wherever it is checked out.
root = pathlib.Path(__file__).resolve().parent.parent

# The .tex to audit must be named. The filename is printed because auditing the wrong
# draft cleanly is indistinguishable from auditing the right one cleanly.
if len(sys.argv) < 2:
    sys.exit(f"usage: {pathlib.Path(sys.argv[0]).name} <manuscript.tex>")
texpath = pathlib.Path(sys.argv[1])
if not texpath.exists():
    sys.exit(f"no such file: {texpath}")
print(f"auditing {texpath.name}")
tex = texpath.read_text()

# strip comment lines so commented-out drafts are not audited
tex = "\n".join("" if l.lstrip().startswith("%") else l for l in tex.split("\n"))

def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    for a, b in [("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'),
                 ("\u2014", "--"), ("\u2013", "-"), ("\u2212", "-"), ("\u00a0", " "),
                 ("\u2010", "-"), ("\u2011", "-")]:
        t = t.replace(a, b)
    t = t.replace("``", '"').replace("''", '"')
    t = re.sub(r"\\%", "%", t)
    t = re.sub(r"\\&", "&", t)
    t = re.sub(r"\\-", "", t)
    t = re.sub(r"\\ldots\{\}?", " \u2026 ", t)
    for cmd, sym in [("varepsilon", "\u03b5"),
                     ("alpha", "\u03b1"), ("beta", "\u03b2"), ("pm", "\u00b1"), ("sim", "~"),
                     ("times", "\u00d7"), ("le", "\u2264"), ("ge", "\u2265")]:
        t = t.replace("\\" + cmd, sym)
    t = re.sub(r"\\emph\{([^}]*)\}", r"\1", t)
    t = re.sub(r"\$([^$]*)\$", r"\1", t)
    t = re.sub(r"[^A-Za-z0-9\u2026]+", " ", t)
    return t.lower().strip()

arts = {}
for f in (root / "reference").glob("*.txt"):
    arts.setdefault(f.stem.split(".")[0], []).append(norm(f.read_text()))

# Stored source text is third-party copyrighted and is not redistributed with this
# repository, so a fresh checkout has none. Say so, rather than reporting every
# quotation as a failure and leaving the reader to guess why.
if not arts:
    sys.exit(
        "no stored sources found in reference/\n"
        "The source text each quotation is checked against is third-party copyrighted\n"
        "and is not redistributed here. reference/FETCH_LOG.json records the SHA-256 and\n"
        "retrieval tier of each source; retrieve them with scripts/fetch_sources.py, or\n"
        "obtain your own copies and verify them against those hashes, then run this again."
    )

quotes = []
for m in re.finditer(r"``(.+?)''", tex, re.S):
    # A quotation is attributed to whichever cited source in its neighbourhood contains it.
    # The nearest key is often the wrong one: "the same document" and "which the same paper
    # asserts" both put the real source several sentences back, behind an intervening cite.
    window = tex[max(0, m.start() - 700):m.end() + 400]
    keys = []
    for g in re.findall(r"\\cite[a-z]*(?:\[[^]]*\])*\{([^}]*)\}", window):
        keys += [k.strip() for k in g.split(",")]
    quotes.append((tex[:m.start()].count("\n") + 1, keys, m.group(1)))

bad = 0
for line, keys, q in quotes:
    frags = [f.strip() for f in norm(q).split("\u2026") if f.strip()]
    if not keys:
        print(f"L{line}: NO CITATION KEY NEARBY  {q[:70]!r}"); bad += 1; continue
    hits = [k for k in keys if k in arts
            and any(all(f in a for f in frags) for a in arts[k])]
    if not hits:
        have = [k for k in keys if k in arts]
        print(f"L{line}: NOT FOUND in any of {have or keys}  {q[:100]!r}"); bad += 1
print(f"\n{len(quotes)} quotations, {len(quotes)-bad} resolve, {bad} problems")
sys.exit(1 if bad else 0)
