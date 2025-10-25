# Contributing

Thanks for helping improve **Manabi Grammar DB**!

## Allowed Content
- Only link to lawful resources. **No piracy/copyright-infringing sites**.
- **No adults-only content** or resources primarily intended for mature audiences.
- Prefer official docs, reputable blogs, reference dictionaries, and Q&A sites.

## Structure & Naming
- Grammar directories: `grammar-xx` where `xx` is a lowercase 2–3 letter language code (BCP-47 primary subtag), e.g. `grammar-ja` for Japanese.
- Each `<HEADWORD>.yaml` may have zero or more `<HEADWORD>.<yy>.md` files (reader language).
- Markdown formatting is constrained; see the validator for exact rules.

## Checks
- Run `mise run lint` before sending PRs. CI will block merges if checks fail.

## License
- All content in this repository is licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**. See `LICENSE`.
