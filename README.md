# Manabi Grammar DB (vendor)

This repository stores the canonical grammar dataset (YAML + Markdown) that is compiled into a distributable SQLite file plus client bundles.

- Target language directories live under `grammar-xx/` (two or three letter target language code).
- Build the SQLite + JS client bundle: `mise run build-db`.
- Run structural + schema validation: `mise run lint`.
- Generated artifacts land in `dist/` (SQLite + JSON schemas) and `js-client/dist/`.
- Terms of Use: see [`TERMS_OF_USE.md`](./TERMS_OF_USE.md).
- Dataset license: [Creative Commons Attribution-ShareAlike 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## Authoring Workflow

1. **Scaffold** a new entry using the stub helper:
   ```sh
   # From vendor/manabi-grammar-db
   mise exec python -- python scripts/create_stub_entry.py \
     --headword が \
     --target-lang ja \
     --reader-lang en
   ```
   - `--target-lang` sets the grammar directory (e.g. `grammar-ja/`).
   - `--reader-lang` determines the Markdown filename (e.g. `が.en.md`).
   - Pass `--force` to overwrite existing files.
2. **Fill in the YAML** fields (matching the schema below) and update the Markdown sections:
   - `## Meaning` (optional) can contain rich markdown, including lower-level subheadings, but must not embed additional `#`/`##` headings.
   - Resource sections (`## Guides`, `## Q&A`, `## Related`) stay as structured dash lists.
3. **Validate** with `mise run lint` before opening a pull request.

## YAML Schema Cheat Sheet

Each YAML file is a single mapping. Alongside existing required fields (`headword`, `jmdictId`, `pattern`, `examples`, `variant`) the schema now supports richer metadata:

- `alternativeForms` *(optional array<string>)* — Alternate spellings/orthography for the headword.
- `exampleSentences` *(optional array<object>)* — Concrete sentences demonstrating usage.
  - `sentence` *(string, required)*
  - `translations` *(object, optional)* — Keys are language codes; values are translation strings.
  - `sourceUrl` *(string, optional)* — Cite where the sentence was sourced.
- `testData` *(optional object)* — Regression fixtures for automated checks.
  - `nonMatchingSentences` *(array<string>)* — Sentences expected **not** to match the grammar.

### Comprehensive Sample YAML Entry

```yaml
# File: grammar-ja/が.yaml
headword: が                             # Primary surface form
jmdictId: 1234560                       # JMDict identifier or opaque string
pattern:
  mecab: '助詞,格助詞,*,*,*,*,が,ガ,ガ'    # MeCab node sequence used for matching
examples:
  - https://example.com/corpus#text=彼が来た
  - https://example.org/entries#text=雨が降る
alternativeForms:
  - がは
  - か
exampleSentences:
  - sentence: 彼が来た。
    translations:
      en: He came.
      fr: Il est venu.
    sourceUrl: https://example.com/corpus#text=%E5%BD%BC%E3%81%8C%E6%9D%A5%E3%81%9F
  - sentence: 雨が降る。
    translations:
      en: It rains.
testData:
  nonMatchingSentences:
    - 彼は来た。
    - 雨は降った。
variant: 1
```

The build pipeline serialises the YAML verbatim (plus associated Markdown content) into the SQLite `grammar` table's JSON payload.
