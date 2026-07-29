# Cleaning Stage

The cleaning stage deterministically transforms each raw document's Markdown
without modifying the original `Document`. Its implementation is in
`pipeline/cleaning/cleaner.py` and `pipeline/cleaning/steps.py`.

Every document first receives line-ending and whitespace normalization. Repeated
blank lines are also collapsed at the end of every cleaning run.

| `cleaning_level` | Additional transformations |
| --- | --- |
| `0` | Normalize Markdown and collapse repeated whitespace. |
| `1` | Remove cookie/consent blocks and duplicate paragraphs. |
| `2` | Remove navigation, footer, and advertisement blocks; remove duplicate headings. |
| `3` | Remove headings without meaningful body content. |

Block removal uses keyword matching, so it is intentionally deterministic but
can remove content whose text contains the relevant boilerplate terms. Code
fences are preserved while cookie, navigation, footer, and advertisement blocks
are filtered.

The output is a `CleanDocument`, which retains every raw document field and
adds `cleaned_markdown`, token counts, tokens removed, reduction percentage,
cleaning latency, and the ordered list of applied steps. Token counts use
Quarry's lightweight regex tokenizer rather than a model-specific tokenizer.

If an individual document cannot be cleaned, its original Markdown is returned
as `cleaned_markdown` and `cleaning_steps_applied` is set to
`["cleaning_failed"]`.
