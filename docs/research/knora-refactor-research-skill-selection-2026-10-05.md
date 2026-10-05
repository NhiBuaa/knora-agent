# Chọn skill cho nghiên cứu kiến trúc Knora

Ngày: 2026-10-05. Phạm vi: chọn skill hỗ trợ 14 research track; chưa thực hiện các track, cài skill hoặc refactor.

## Kết luận

**Nên bổ sung một bộ 4 skill nếu muốn dùng đầy đủ quy trình khảo sát kiến trúc của Matt Pocock:** `codebase-design`, `improve-codebase-architecture`, `grilling`, `domain-modeling`.
Sau đó cân nhắc `wayfinder` và `prototype` khi nghiên cứu kéo dài nhiều phiên và cần bản đồ quyết định. Không cần một skill riêng cho mỗi công nghệ.

Đây là khuyến nghị cho công việc kiến trúc hiện tại, khác với ưu tiên chung `retro`/`writing-for-agents` trong [báo cáo trước](matt-pocock-skill-gap-analysis-2026-10-05.md).

## Cơ sở đối chiếu

- Nguồn canonical: `C:/Users/NhiBuaa/.codex/skills`; bộ hiện có gồm 16 skill ở cấp thư mục gốc. Skill hệ thống và plugin có trong catalog là nguồn bổ sung, không được xem là các skill bên ngoài đã được phê duyệt cho Knora.
- Đối chiếu nội dung thực tế của `research`, `brainstorming`, `writing-plans`, `systematic-debugging`, `requesting-code-review`; không dựa vào tên skill hoặc workflow cũ đã bị bỏ khỏi hướng dẫn repo.
- Upstream được chốt tại commit [`24fe0ef7737efae15c87225755e9f6f5965e4888`](https://github.com/mattpocock/skills/tree/24fe0ef7737efae15c87225755e9f6f5965e4888). Các liên kết dưới đây dùng cùng commit để tránh thay đổi nội dung trong lúc đối chiếu.
- Trước khi thực hiện nghiên cứu kiến trúc, chọn rõ branch và SHA cần khảo sát. Checkout hiện tại `codex/test` khác `main` (78 commit riêng phía checkout, 2 phía `main` tại thời điểm kiểm tra); không mặc định kết quả trên checkout đại diện cho GitHub `main`.

## Bộ nên bổ sung

| Skill | Phần bổ sung so với bộ hiện có | Dùng trong công việc này |
|---|---|---|
| [`codebase-design`](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/codebase-design/SKILL.md) | Khung phân tích độ sâu module, interface, seam, adapter và locality | Đánh giá interface có che giấu complexity thật không; vị trí test và provider/storage seams |
| [`improve-codebase-architecture`](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/improve-codebase-architecture/SKILL.md) | Khảo sát code/điểm hay thay đổi, tìm architectural friction và trình bày ứng viên bằng HTML | Track 1; tổng hợp ứng viên refactor từ kết quả các track khác |
| [`grilling`](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/grilling/SKILL.md) | Phỏng vấn theo cây quyết định, hỏi các câu đủ prerequisite theo từng vòng | Chốt trade-off sau khi có bằng chứng; là dependency của quy trình upstream |
| [`domain-modeling`](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/domain-modeling/SKILL.md) | Thử domain bằng edge case, kiểm tra ngôn ngữ với code và ghi quyết định ngay khi được chốt | Workspace authority, retrieval/evidence ownership, agent/tool authority và lifecycle |

`brainstorming` đã hỗ trợ thiết kế và chốt yêu cầu. Vì vậy `grilling` và `domain-modeling` có phần chồng lấp; lý do đưa chúng vào bộ này là dependency cụ thể của workflow upstream, cộng với cách ghi và kiểm tra quyết định sâu hơn. Không chạy đồng thời hai quy trình phỏng vấn cho cùng một quyết định.

**Hai skill kiến trúc đầu tiên không đủ cho toàn bộ workflow nguyên bản.** `improve-codebase-architecture` tiếp tục từ khảo sát → HTML → người dùng chọn ứng viên → `grilling` → `domain-modeling`. Nếu chỉ muốn khảo sát đọc-only với hai skill, cần một bản điều chỉnh được người dùng cho phép, giới hạn rõ điểm dừng; không coi việc bỏ dependency là đã chạy đầy đủ workflow. [Nguồn quy trình](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/improve-codebase-architecture/SKILL.md).

## Tùy chọn cho chương trình nhiều phiên

| Skill | Khi đáng thêm | Giới hạn |
|---|---|---|
| [`wayfinder`](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/wayfinder/SKILL.md) | 14 track có nhiều quyết định phụ thuộc nhau, vượt quá một phiên | Tạo map/child issues, gắn label, claim, dependency, comment và đóng issue; cần cấu hình tracker và quyền tương ứng |
| [`prototype`](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/prototype/SKILL.md) | Cần nhìn/chạy thử state machine, HITL hoặc UI để chốt một câu hỏi thiết kế | Hai nhánh chính là demo logic HTML và UI variants; không phải quy trình benchmark retrieval/ML |

Dependency theo nội dung thực tế:

```text
improve-codebase-architecture
  → codebase-design
  → grilling             (sau khi người dùng chọn ứng viên)
  → domain-modeling      (khi chốt/chỉnh domain hoặc ADR)

wayfinder
  → grilling + domain-modeling  (định nghĩa destination và decision tickets)
  → research                   (research tickets; đã có)
  → prototype                  (prototype tickets)
  → skill trong Notes          (tùy map, phải kiểm tra riêng)
```

Với bộ 4 đã chọn, **thêm `wayfinder` + `prototype` thành bộ 6** nếu muốn hỗ trợ đầy đủ các loại ticket thông thường. Một map chỉ có research/grilling không cần gọi prototype. Tracker chưa cấu hình thì upstream hướng tới `setup-matt-pocock-skills`; Knora đã có [tracker guide](../agents/issue-tracker.md), nhưng guide chưa có mục “Wayfinding operations”, nên phải bổ sung routing cho map/child issues, labels, claim và frontier trước khi dùng. Không tự cài setup hoặc thay tracker của repo. [Nguồn](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/wayfinder/SKILL.md).

## Ánh xạ cả 14 track

| Track | Skill hỗ trợ chính | Bằng chứng đầu ra cần có |
|---|---|---|
| 1 — Kiến trúc hiện tại | `improve-codebase-architecture`, `codebase-design`, `research` | Boundary/ownership map, code path và SHA, friction có bằng chứng, baseline test |
| 2 — Reference OSS | `research`, `codebase-design` | So sánh bằng source/docs chính thức; điều kiện phù hợp và khác biệt với Knora |
| 3, 4, 5 — RAG, vector, reranking | `research`; thiết kế seam bằng `codebase-design` | Baseline/candidate cùng corpus và query set, metric chất lượng/latency/cost, quyết định thử adapter hay migration |
| 6 — GraphRAG | `research`, `domain-modeling` | Câu hỏi quan hệ thực tế, chi phí extraction/resolution và bằng chứng vượt baseline |
| 7, 8, 9 — Framework, agent/tool, MCP | `research`, `codebase-design`, `domain-modeling`; `prototype` nếu cần | Native/framework trade-off, authority map, state/HITL và hợp đồng capability |
| 10 — Evaluation | `research`, `verification-before-completion`; TDD khi triển khai | Dataset tách development/held-out, regression gate, retrieval/answer/citation/tool metrics |
| 11 — Security/privacy | `research`, domain/authority review; `systematic-debugging` khi tái hiện lỗi | Threat model, attack cases, isolation/leakage/tool escalation evidence |
| 12 — Reliability | `research`, `systematic-debugging` khi có failure/bottleneck | Failure matrix, retry/consistency invariants, recovery/fault-injection evidence |
| 13 — Observability/performance/cost | `research`, `systematic-debugging` | Trace coverage, load profile, p50/p95/p99, cost và SLO có điều kiện đo |
| 14 — Deployment/SDLC/career | `research`, `verification-before-completion`, review hiện có | Release/rollback evidence, CI/security checks và demo/README phản ánh kết quả thực tế |

`wayfinder` điều phối các quyết định giữa các nhóm trên; `writing-plans` chỉ đến sau khi lựa chọn đã được chốt. Skill quy trình không bảo đảm chuyên môn RAG, security, ML hay production: các track vẫn cần tài liệu/source/spec chính thức và thí nghiệm có thể lặp lại.

## Chưa cần thêm

- **`to-spec`/`to-tickets`:** hữu ích khi chuyển quyết định thành issue, nhưng chưa cần để nghiên cứu. Bộ hiện có đã viết design/plan; upstream mới thêm hành vi publish tracker và label, cần ủy quyền riêng. [to-spec](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/to-spec/SKILL.md), [to-tickets](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/to-tickets/SKILL.md).
- **`code-review`:** thêm review tách Standards/Spec, nhưng `requesting-code-review` đã có reviewer theo requirements và SHA. Cân nhắc sau khi bắt đầu thay đổi; chưa phải khoảng thiếu cấp thiết của research. [Nguồn](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/code-review/SKILL.md).
- **`retro`/`writing-for-agents`:** cải thiện môi trường và tài liệu sau phiên; hữu ích nhưng không giải quyết trực tiếp lựa chọn retrieval/storage/agent architecture. [retro](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/retro/SKILL.md), [writing-for-agents](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/productivity/writing-for-agents/SKILL.md).
- Chưa cần cài thêm TDD/debugging, hoặc săn một bộ skill chuyên từng framework, khi các công nghệ đó vẫn đang được đánh giá.

## Điều chỉnh trước khi sử dụng

1. **Domain routing:** upstream dùng `GLOSSARY.md`/`GLOSSARY-MAP.md`; Knora dùng [CONTEXT.md](../../CONTEXT.md) và [domain guide](../agents/domain.md). Giữ canonical source của Knora, ghi mapping rõ; không tạo glossary thứ hai hoặc tự đổi tên tài liệu.
2. **Architecture authority:** vocabulary deep-module là công cụ phân tích. [Architecture Standard](../standards/architecture.md), [M1 seams](../design/milestone-1-module-seams.md), [M2 seams](../design/milestone-2-module-seams.md) và ADR hiện có vẫn là ràng buộc. Đặc biệt không gộp module bằng cách phá Workspace isolation, citation provenance hay ownership giữa Knora/KittaChat.
3. **Git và tracker:** wayfinder/prototype có thao tác issue và nhánh; mọi worktree phải theo [AGENTS.md](../../AGENTS.md). Cài skill không đồng nghĩa cho phép publish issue, migration, commit, merge hay deploy. Đây chỉ là đề xuất cài đặt.
4. **Refactor và nâng capability:** chia thành hai scope. Refactor giữ behavior/contract/invariants với regression evidence; query rewrite, reranker, GraphRAG, agent workflow hay backend migration cần spec và quality gate riêng. Không gọi tất cả các thay đổi đó là refactor.
5. **Test và benchmark:** [DEEPENING.md](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/codebase-design/DEEPENING.md) đề xuất thay unit tests bằng tests ở interface; chỉ bỏ tests cũ sau khi có coverage tương đương, vẫn giữ integration/security/quality gates. Prototype upstream bỏ test để khám phá thiết kế; benchmark và production code cần phương pháp kiểm chứng riêng.

## Thứ tự đề xuất

**Cài và kiểm tra bộ 4 → chốt SHA khảo sát → Track 1 + baseline evaluation → nghiên cứu các lựa chọn → quyết định có cần wayfinder/prototype → chốt design → writing-plans → triển khai từng scope và kiểm chứng.**

Chưa cài, kích hoạt hoặc chạy candidate skill nào trong lần nghiên cứu này.
