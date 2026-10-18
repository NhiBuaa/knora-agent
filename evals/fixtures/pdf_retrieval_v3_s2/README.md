# Finite S2 lexical populations

`frozen47-lexical-population-v1.json` is an opt-in population pin for the unchanged frozen
47 chunks. It represents14 source hashes,7083 native tokens and mean length7083/47.
Two dataset sources have no frozen chunks; the manifest does not invent content for them.
Documents are ordered by source SHA; chunks retain physical page/offset order.

The new profile is `bm25-word-frozen47-population-v1`. Its statistics digest is
`b9a03c93106424e3c7cfbdc6c96bc8b94f7635c0c618d27ed410a51fac385451` and profile digest is
`f54643e1d15632ebdf46739fbe3b4523aee77fe892628587498058c4bbb0b849`.
Statistics use canonical JSON of source hashes, ordered checksum/count pairs and tokenizer
identity. Random runtime chunk IDs are excluded. Historical profiles and evidence are unchanged.

Counts were joined by historical chunk ID/checksum/content to retained native parity evidence:

- Native artifact `frozen-parity-ec80d5cda5fa445d8ed848807d9d3f89.json`, byte SHA256
  `556f3733fdc3fa815c88f2b89f91bb632e6b17bbf1330ab25c0606dc23d2e303`.
- Read-only correspondence `retained-population-counts-b527b99898794cfbb3e89a12722d2c43.json`,
  byte SHA256 `dcb8efe51096fe82e8226918d239d6288e9b7eca153b81b00620f68844fff2c2`.
- Both retained under `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/runtime-20261017`.
  Their input byte hashes were rechecked before creating this pin.

The test checks every frozen source/content position, population statistics and evidence pin.
This establishes offline correspondence only. The new profile still requires native/runtime
verification in the bounded S2 batch. No all60 retrieval, quality or serving acceptance is claimed.

## Upload fixture

`refund-policy.pdf` is a new synthetic single-page source with one chunk:
"Refund requests are accepted within 30 days." Source SHA256:
`4ab63c9a21e8e2cb43e041df7ea02909df9726a521cd6acdea22f3483ed9c6ec`.

`upload-native-counter-v1.json` records separate measurement by the retained upstream native
counter WASM pinned above, after actual production layout extraction. Its byte SHA256 is
`890dacd4662d65167237a700056964d9c81533ec6bfa8ae2f136eee55cac9017`.
The chunk contains7 native tokens. `native_server_verified=false` deliberately records that
Qdrant vector parity and application serving remain unverified for this new fixture.

`upload-lexical-population-v1.json` has byte/LF SHA256
`e29bd9a22e6cabbf5e2ffd8580f006801470886859801469b3fe68ae422869a0` and profile
`bm25-word-upload-fixture-population-v1`, digest
`8e9d975fe58da2741572d7190c0de1f363e1cf8166c6a87e1353548bcce84b24`.
Its separate configuration ID is `retrieval-bm25-upload-fixture-top8-v1`.
Git preserves these new JSON evidence files as LF and the PDF as binary.

The finite deployment loader compares the full immutable retrieval semantics and a fixed
manifest SHA, after CRLF-to-LF normalization; a changed manifest cannot authorize itself.
Frozen47's byte hash at creation was `8e3f437eae9eba63de373d20214a520d44b644e9bc4051481cd87512b00a328f`
under Windows CRLF; its pinned LF hash is
`5d9ddeec5aca02d0ceabaaebe7ae867ba895fc1e8cf67e13859fbd0923b7fe60`.
Arbitrary PDFs remain outside finite S2 support. No Qdrant/app startup, provider call or
fresh-upload E2E is established by generating these fixtures.
