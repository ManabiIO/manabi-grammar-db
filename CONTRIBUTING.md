# Contributing

Thanks for helping improve **Manabi Grammar DB**!

## Allowed Content
- Only link to lawful resources. **No piracy/copyright-infringing sites**.
- **No adults-only content** or resources primarily intended for mature audiences.
- Prefer official docs, reputable blogs, reference dictionaries, and Q&A sites.

## Structure & Naming
- Grammar directories: `grammar-xx` where `xx` is a lowercase 2–3 letter language code (BCP-47 primary subtag), e.g. `grammar-ja` for Japanese.
- Variant 1 uses `<HEADWORD>.yaml` and `<HEADWORD>.<yy>.md`. Additional variants use `<HEADWORD>.v2.yaml` and `<HEADWORD>.v2.<yy>.md`, etc. The terminal `.vN` suffix is reserved. Markdown never automatically carries across variants.
- Markdown requires exactly one matching H1; H2 sections are Meaning, Guides, Q&A and Related. Duplicate sections/groups fail. Meaning supports H3–H6 and fenced code; resources use structured HTTP(S) dash links. See README for the complete subset.
- YAML uses strict camelCase fields. Duplicate keys, aliases, merges, non-string map keys and unknown fields fail. Only true/false resolve as implicit booleans.
- External citations belong in `references/registry.json`: commit keys, pins, selectors and attribution metadata, never external explanation bodies. Bind references explicitly to a content identity/version and reader language.

## Checks
- Run `mise run lint` before sending PRs. CI will block merges if checks fail.

## License
- All content in this repository is licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**. See `LICENSE`.

Matching definitions and regression fixtures belong in the private implementation repository. Public changes must not add executable matching fields or generated rule catalogs.
