# Vietnamese regression labels v2

Independent source review read all 12 physical PDF pages and reproduced the M2 derivation:
22 Chunks; all 28 positive v1 gold checksums existed on their expected pages. Original v1
questions, labels and checksum remain unchanged. Both versions are now development-exposed
regression sets, not independent held-out benchmarks after prompt/context tuning.

| Case | Change before the next run | Source |
| --- | --- | --- |
| 01 | Explicitly ask about the suggested chapter count and the small-report alternative; retain both original facts. | Page 1 |
| 13 | Explicitly ask what accompanies the mandatory architecture diagram; retain original facts. | Page 5 |
| 16 | Require GET, POST, PUT, DELETE. The original question asks HTTP methods; URL is a separate concept and optional supported information. | Page 6 |
| 18 | Anchor the question to High Availability Design and avoiding disruption. Preserve the redundancy fact; do not replace it with performance/scaling facts. | Page 6 |
| 25 | Add caption font approximately 1–2pt smaller than body text. Original36 must not be rescored with this added requirement. | Page 10 |

## Semantic review rubric

Review each actual public response against its public citation excerpts and pinned source locators.
Hidden retrieved evidence is diagnostic only and must not be supplied to semantic citation scoring.
Decision, structural
validation, retrieval gold hit, semantic completeness and citation support are separate checks.
A checksum/page hit alone cannot prove that every stated claim is supported by its alias.
Unsupported additions fail semantic review even when required words/numbers appear.

- Counts and rules retain source qualifications: seven suggested chapters may be combined for
  small reports; three TOC levels is recommended and may be exceeded when necessary.
- Self-drawn illustrations in case 10 are a recommendation, not a mandatory rule.
- Case 14 allows ERD or another suitable diagram. Case 15 allows wireframes or mockups.
- Printing is ordinarily one-sided without unnecessary colour. The source's thesis/image
  exceptions do not imply that every thesis must be printed in colour.
- Explicitly prohibited AI-created report content is an ANSWER stating the prohibition.
- Cases 29–36 require REFUSAL, with no answer or citations. Related headings, edition dates,
  page counts and examples do not supply an absent deadline, grade, class code, URL, report
  length, team size, plagiarism rate or defense duration.

Record the dataset/case/decision/answer-and-citation response SHA-256 with each manual semantic
review. Keep full responses and diagnostic evidence in
the local private review artifact, outside Git. Report original36 and revised36 separately;
questions changed in v2 require new observations.
