# Dictionary data notice

The default Exact Match dictionary combines terms curated directly for Koguard
with a small selection of explicit terms from the MIT-licensed Korcen source:

- Project: https://github.com/Tanat05/korcen
- Pinned revision: `eecd9763dbdccce3dc96ddb578ef0b6396058fa9`
- Bundled license SHA-256: `71019ed51eada81b0a73069d0778a2a12d4d55754a24f2b0964e044145ff0af7`
- Pattern families consulted: `GENERAL`, `MINOR`, `BELITTLE`, and `PARENT`

Koguard selected individual literal terms from those pattern families, removed
duplicates, and stored one term per line. It does not copy Korcen's matching
implementation. Korcen's MIT license and copyright notice are preserved in
`KORCEN-MIT.txt`.

Four independently reviewed Korean Exact Match terms were promoted from the
MIT-licensed `2runo/Curse-detection-data` tuning source:

- Project: https://github.com/2runo/Curse-detection-data
- Pinned revision: `ff241621e103b6f220d30de324d0d07987887308`
- Promotion evidence: `evaluation/results/pf007-top-candidates.report.json`

The source corpus and private review text are not bundled. Only the four
approved literals and the source's copyright and MIT notice are distributed;
the notice is preserved in `CURSE-DETECTION-DATA-MIT.txt`.

The lowercase romanized literals `sibal`, `ssibal`, and `shibal` were selected
directly for Koguard under the project MIT license. Koguard does not perform
general romanization, case folding, or language detection.

Every bundled literal and Alias is linked to a stable candidate ID, source revision,
license decision, review status, and evaluation reference in the source distribution's
`evaluation/dictionary-provenance.v1.json`. This build-only manifest is not runtime
wheel data. The offline validator and promotion policy are documented in
`docs/dictionary-provenance.md` in the source distribution.

The small alias mapping in `aliases.tsv` was manually selected for Koguard from
user-reported false negatives. The following resource repository was consulted
while researching Korean profanity representations:

- https://github.com/Tanat05/korean-profanity-resources
- Reviewed revision: `289ed960d10a9e6e3096090fba012ca0796fc641`

That repository marks the license of its maintained `slang.csv` as needing
confirmation. Koguard therefore does not copy or bundle that dataset. The alias
rules remain independently selected regression rules rather than a redistribution
of `slang.csv`.

No third-party model is bundled. Applications should review their own policy,
context, and false-positive requirements before using the defaults for moderation
decisions.
