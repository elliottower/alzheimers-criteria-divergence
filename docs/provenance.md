# Provenance

How the sources behind the manuscript were obtained and checked. This record lives here
rather than in the paper.

## Retrieval

Sources were retrieved with `scripts/fetch_sources.py`, which pins each one by SHA-256 in
`reference/FETCH_LOG.json` along with its retrieval tier. Three tiers appear:

| tier | meaning |
|---|---|
| full text | the whole article is held locally and any passage in it can be checked |
| abstract only | only the abstract was obtainable; nothing outside it may be quoted |
| record | bibliographic metadata retrieved from a public API, no text held |

Retrieval used public APIs — Europe PMC, Crossref, OpenAlex, ClinicalTrials.gov, the NLM
Clinical Table Search Service — and publisher pages where those are open. No browser
automation and no spoofed user agents were used; where a publisher refused a plain request,
the source is recorded at the tier actually obtained rather than inferred from an abstract.

## Checking

`scripts/audit_tex_quotes.py` walks every quotation in the manuscript, locates the cited
keys in its neighbourhood, and searches the stored text of each for the quoted string after
normalizing quotation marks, dashes, soft hyphens and whitespace. A quotation that cannot be
found is reported with its line number. Ellipsis is treated as omitted text: each fragment
must appear, contiguity is not required.

Two extraction pitfalls are worth recording because both produced false failures:

- **Two-column PDFs.** `pdftotext -layout` interleaves the columns, so a sentence that reads
  continuously on the page is not contiguous in the text layer. Plain `pdftotext` handles the
  columns correctly. Where both extractions are held, the plain one is authoritative.
- **Reference markers inside sentences.** Superscript citation numbers land in the text layer
  between words, so a quotation spanning them will not match. Quote a fragment that avoids
  them rather than editing the quotation.

## Scope of what is held

60 sources are cited. 24 carry pinned quotation records in `claims/`. The stored source text
itself is third-party copyrighted and is not redistributed; the ledger's hashes allow an
independently retrieved copy to be checked against the one used.
