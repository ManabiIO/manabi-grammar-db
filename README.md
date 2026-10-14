# Manabi Grammar DB

Public grammar explanations, page identities, multilingual content metadata and citation foreign keys. The library contains 646 points covering the 643 pinned Takoboto records and original families. External explanation bodies are resolved during builds and remain outside Git.

Executable matching rules, compiler tooling, matching schemas and regression corpora live in the private Manabi Grammar implementation repository. They are not included in this repository or its SQLite/releases. `ruleID` and `ruleVersion` remain public identifiers for associating a private match with its explanation page; neither contains detection logic.

## Authoring content

```sh
mise exec python -- python scripts/create_stub_entry.py \
  --headword が --target-lang ja --reader-lang en \
  --rule-id grammar.ja.ga.subject
```

Required YAML fields are `ruleID`, `ruleVersion`, and `examples` (which may be empty). Headword, target language and variant are inferred from filenames and checked if explicitly supplied. Variant 1 uses `<headword>.yaml` plus `<headword>.<reader>.md`; other variants use `.v2`, `.v3`, etc. Content/schema validation rejects unknown matching fields. The content stub creates no matcher scaffold.

Markdown starts with exactly one `# <headword>` title. H2 sections are `Meaning`, `Guides`, `Q&A`, and `Related`; duplicates fail. `Meaning` retains original Markdown including H3–H6, fenced code and blank lines. Resource sections use one-line `- [Name](https://...) - description` links, with optional `⭐ ` after the dash; Related requires `### <headword>` groups. Duplicate groups fail, and empty groups are preserved. Resource/example source URLs must use HTTP(S). Hosts rendering Meaning must sanitize generated HTML with an allowlist; validation does not make Markdown executable HTML safe. `alternativeForms` and translated `exampleSentences` remain optional content metadata; `levelLabel` is explicit supported metadata. Do not infer JLPT levels or fabricate source URLs. The build serializes validated YAML plus reader Markdown into the SQLite `grammar` table's JSON payload.

Lint and build use the same strict loader (`scripts/content.py`). It rejects duplicate YAML keys, non-string mapping keys, aliases/merges, unknown fields and malformed example entries. Only `true`/`false` spellings resolve implicitly as booleans; unquoted language key `no` remains a string. Other PyYAML safe-loader scalar semantics remain in effect: this is not a full YAML 1.2 parser. Use canonical camelCase keys; legacy snake_case aliases are rejected. Translation/reader language keys use 2–3 lowercase letters. Numeric identity/version fields fit the shared 32-bit WASM contract.

`grammar-yaml.schema.json` owns shared definitions. `scripts/schema_contract.py --write` derives a **self-contained** row schema from it; lint/tests reject a stale generated schema. No external schema resolution is needed by release consumers.

## Canonical external citations

`references/registry.json` is the only maintained source registry and binding collection. It contains metadata, foreign entry/page IDs, pinned release/revision IDs, hashes, selectors, source attribution and original labels; it contains **no fetched explanations, snippets or wiki markup**. Its strict `reference-registry.schema.json` rejects unknown fields, duplicate identities, unresolved keys and invalid metadata. Bindings explicitly carry stable `ruleID`, reviewed `ruleVersion`, reader language and source IDs. Changed matching semantics increment the rule version and require citation review; citation/prose edits alone do not change matcher versions.

The build projects those bindings into each SQLite row's `referenceBindings`, which typed native Swift and WASM consumers retain. The registry ships with the DB release. External source bodies remain in separately generated, ignored summary/detail snapshots; the web resolver fetches verified pinned sources and renders them inline on existing grammar pages. Other hosts can resolve the same foreign keys or consume those portable artifacts. Alias/title discovery never selects a rule sense or creates a grammar match.

The current adapters support Japanese entries with English explanation text:
Takoboto/JGram uses CC-BY-SA-2.0, and English Wiktionary uses CC-BY-SA-4.0.
The registry rejects contradictory language/license metadata; Wiktionary
selectors must start in the Japanese section. Takoboto titles and aliases are
checked against the pinned release, so metadata changes cannot silently disappear
during projection. Adding another source language requires an adapter update.
Reader-language bindings can differ from the source explanation language.

Releases include the DB, three self-contained schemas, `reference-registry.json`, the self-contained client ZIP, and SHA-256 `checksums.txt`. ZIP packaging excludes earlier archives. Consumers must install one coherent release and support the versioned content schema; matching definitions are not distributed by this repository.

Database generation rejects duplicate rule IDs and payload identities that disagree with the grammar directory/filename. It commits and checks a staged DELETE-journal database before atomically replacing the current snapshot. Failed builds preserve the prior usable database; replaced and failed snapshots are preserved in Trash. `mise run build-db` includes publication/identity and authoring/citation regressions; run them alone with `mise exec python -- python -m unittest discover -s scripts -p 'test_*.py'`.

Dataset license: Creative Commons Attribution-ShareAlike 4.0. See [Terms of Use](TERMS_OF_USE.md).


## Build boundary

`mise run build-db` validates only public content, builds the official SQLite WASM client, and tests the public SQLite snapshot. It requires no private checkout or credentials. Downstream private builds join content and private rules by stable identities, verify versions, and write their enriched artifacts into a separate private output directory. Never upload those enriched artifacts as public content releases.
