# S2 native BM25 tokenizer compatibility — offline spike

Date: 2026-10-16 (Asia/Saigon). This records source investigation and an offline
experiment, **not native server compatibility or S2 acceptance**.

## Owner decision and sources

The owner approved a new native `word` profile and an offline spike bounded to two
hours in [the decision record](https://github.com/NhiBuaa/knora-agent/issues/153#issuecomment-6199338839).
No new application dependency, model/provider call or service was used.

Pinned primary sources at Qdrant `v1.19.2`:

- [Multilingual tokenizer](https://github.com/qdrant/qdrant/blob/v1.19.2/lib/segment/src/index/field_index/full_text_index/tokenizers/multilingual.rs):
  calls charabia with `lossy: true`, then skips tokens with no alphabetic character.
  `ascii_folding: false` applies later and cannot disable that normalization.
- [Cargo.lock](https://github.com/qdrant/qdrant/blob/v1.19.2/Cargo.lock) pins charabia `0.10.0`.
  Its [lossy normalizers](https://github.com/meilisearch/charabia/blob/v0.10.0/charabia/src/normalizer/mod.rs)
  include removal of Latin nonspacing marks after compatibility decomposition.
- [Native word tokenizer](https://github.com/qdrant/qdrant/blob/v1.19.2/lib/segment/src/index/field_index/full_text_index/tokenizers/mod.rs)
  splits on Rust `!char::is_alphanumeric`, then calls `TokensProcessor`.
  It retains numeric tokens and accents with the approved disabled options. It is
  Unicode-aware but provides no specialized CJK segmentation or Vietnamese word segmentation.
- [TokensProcessor](https://github.com/qdrant/qdrant/blob/v1.19.2/lib/segment/src/index/field_index/full_text_index/tokenizers/tokens_processor.rs)
  applies lowercase, optional folding/stemming/stopwords and length checks.
- [Native inference](https://github.com/qdrant/qdrant/blob/v1.19.2/src/common/inference/bm25_inference.rs)
  gathers tokenizer outputs and passes them to BM25. The inspected
  [OpenAPI](https://github.com/qdrant/qdrant/blob/v1.19.2/docs/redoc/master/openapi.json)
  has no tokenizer-count endpoint. Edge Python BM25 bindings expose sparse vectors,
  not a token-count method. This is an observation about inspected interfaces, not
  proof that no future API can provide counts.
- [Build Dockerfile](https://github.com/qdrant/qdrant/blob/v1.19.2/Dockerfile) selects Rust `1.98.1`.

## Experiment

The host had no Rust compiler. Official Rust `1.98.1` compiler and WASI standard
library archives were downloaded to a temporary directory and verified against
upstream SHA-256 files; nothing was installed globally. The first checksum check
failed because PowerShell returned the checksum body as bytes; decoding it as ASCII
showed the archive hashes matched. No unchecked archive was executed.

The harness extracts the unchanged `WordTokenizer` implementation and includes the
entire upstream `TokensProcessor`. It compiles to WASI and runs with Node's built-in
WASI runtime. Dependencies for disabled stemming/folding panic if reached; the
stopword filter is explicitly an empty-set stub. Thus this tests those upstream
implementations under the fixed options, **not the whole server/config deserializer**.
No Python/whitespace tokenizer is substituted.

Both fixture and chunk inputs receive NFKC/lowercase first. Exact fixture tokens:

| Input | Expected and observed tokens |
| --- | --- |
| `HẠN MỨC 42` | `hạn`, `mức`, `42` |
| `ＰＤＦ bản_001` | `pdf`, `bản`, `001` |
| `Hạn mức` | `hạn`, `mức` |
| `...` | empty |
| `PhoBERT-base 0.65` | `phobert`, `base`, `0`, `65` |

All five fixtures passed. The **same 47 frozen runtime chunks** produced **7,083
upstream tokens**, proposed `avg_len = 7083 / 47 = 150.70212765957447`. No corpus/gold,
chunk content, parser, binding or missing anchor was changed. This population is the
controlled 47-chunk baseline only, not a general multi-tenant profile.

## Provenance and remaining gate

- Read-only runtime `chunks.json` byte SHA: `146109370459186ef0d46e49e0165e1184ec719fe8a61a6b9cd55156e0b256f9`.
- Upstream processor SHA: `67fea17c6dc966c5e01c177eeea4b85adc6679c2d376f17856f6a6e2d6e4d952`.
- Unchanged word implementation extract SHA: `5ec3707deed40ba5e08e5fcaa86e8b9c28b2731ed79b9ad04526fc80220518a7`.
- Counter WASM SHA: `36f2b5cb8879b5b62a06c477c5de818b1b84795261b4785400714d2854d16269`.
- Verified compiler archive SHA: `cb5370843a9d15ce6e6cf6461b4c997722220d268d0d813c2b2b86f3ed59ac24`.
- Verified WASI std archive SHA: `b5e91be9ed75c632a4c576d3c4c725ab143cd48c27c345133b97ccdf217b23e7`.

Raw result, 47 per-chunk counts, harness, WASM and source extracts are retained outside
Git at `C:/Users/NhiBuaa/.codex/artifacts/issue153/s2/word-tokenizer-spike-20261016`.
They are experiment artifacts, not a second canonical corpus or runtime dependency.

Before using a profile, verify pinned server/configuration and native vectors/parity
in the authorized isolated runtime. Freeze population/options/source/compiler digests
with that compatibility evidence. The offline value does not bypass this gate; no
profile was activated and no native runtime PASS is claimed here.
