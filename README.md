# alzheimers-criteria-divergence

Verification apparatus for a reading of the two 2024 Alzheimer's disease diagnostic
criteria, which finds that neither rule is a function of the amyloid/tau/neurodegeneration
profile both parties accept.

## The claim

The Alzheimer's Association workgroup criteria and the International Working Group
recommendation, applied to the same amyloid and tau results, place the same cognitively
unimpaired, biomarker-positive person on opposite sides of the disease boundary. Both
accept the A/T/N profile, which records three binary axes. Neither rule is recoverable
from it.

The Association rule reads **which assay found the tau**: a Core 1 fluid result
establishes the diagnosis where tau imaging does not, and the two amyloid-negative,
tau-positive profiles that follow are resolved on different grounds — the imaging case
excluded as primary age-related tauopathy, the fluid case retained because amyloid may
sit below the detection threshold. The same document places a carrier of a deterministic
mutation, whose amyloid, tau and neurodegeneration results are all normal, inside the
disease continuum.

The Working Group rule reads **where in the brain the tau sits, which gene the person
carries, and whether there are symptoms**. The three axes carry none of these.

## Archive

The manuscript and this apparatus are deposited at
[zenodo.org/doi/10.5281/zenodo.22981854](https://zenodo.org/doi/10.5281/zenodo.22981854),
which always resolves to the latest version.

## What is here

    claims/                    quotation records, one per cited source
    reference/FETCH_LOG.json   artifact ledger: the SHA-256 and retrieval tier of each
    references.bib             bibliography
    scripts/audit_tex_quotes.py  checks every quotation against its stored source
    scripts/build_claims.py      rebuilds the claims records from the bibliography
    scripts/fetch_sources.py     retrieves and pins a source

The manuscript is not in this repository. The apparatus is: every quotation in the paper
resolves against a pinned copy of the source it cites, and the ledger records the SHA-256
of each, so an independently retrieved copy can be checked against it. The stored copies
are third-party copyrighted text and are not redistributed.

## Verifying

With the sources retrieved into `reference/`:

    python3 scripts/audit_tex_quotes.py <manuscript>.tex

reports the number of quotations found, the number that resolve, and any that do not. A
quotation that cannot be located in its source is reported by line number rather than
passed over.

## Scope

60 sources cited, 24 carrying pinned quotation records. The ledger holds the retrieval
tier for each: a full text held locally, an abstract only, or a record retrieved from a
public API.
