# Dictionary data notice

The default Exact Match dictionary combines terms curated directly for Koguard
with a small selection of explicit terms from the MIT-licensed Korcen source:

- Project: https://github.com/Tanat05/korcen
- Pinned revision: `eecd9763dbdccce3dc96ddb578ef0b6396058fa9`
- Pattern families consulted: `GENERAL`, `MINOR`, `BELITTLE`, and `PARENT`

Koguard selected individual literal terms from those pattern families, removed
duplicates, and stored one term per line. It does not copy Korcen's matching
implementation. Korcen's MIT license and copyright notice are preserved in
`KORCEN-MIT.txt`.

The small alias mapping in `aliases.tsv` was manually selected for Koguard from
user-reported false negatives. The following resource repository was consulted
while researching Korean profanity representations:

- https://github.com/Tanat05/korean-profanity-resources

That repository marks the license of its maintained `slang.csv` as needing
confirmation. Koguard therefore does not copy or bundle that dataset. The alias
rules remain independently selected regression rules rather than a redistribution
of `slang.csv`.

No third-party model is bundled. Applications should review their own policy,
context, and false-positive requirements before using the defaults for moderation
decisions.
