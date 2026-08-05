# Dictionary data notice

The default dictionary contains a small, manually curated Exact Match fixture.
The entries were written directly for Koguard and were not copied from a
third-party dataset.

The small alias mapping in `aliases.tsv` was manually selected for Koguard from
user-reported false negatives. The following resource repository was consulted
while researching Korean profanity representations:

- https://github.com/Tanat05/korean-profanity-resources

That repository currently marks the license of its maintained `slang.csv` as
needing confirmation. Koguard therefore does not copy or bundle that dataset;
only the five independently selected regression rules in `aliases.tsv` are
included. No third-party model is bundled. Applications should review their own
policy, context, and false-positive requirements before using the defaults for
moderation decisions.
