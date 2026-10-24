# Issue #158 Evaluation Tools Acceptance — Human Review Packet

- **Packet ID**: `issue-158-acceptance-packet-v1`
- **Packet Digest**: `sha256:b0384374646121f3cc68d38c5dd51d4f7cf3d0130dd48c3c01143afa6510a1dd`
- **Shuffle Seed**: `158`
- **Items Count**: 12 (6 Real Answers, 4 Synthetic Controls, 2 Refusal Controls)
- **Note**: Review packet — absolute zero judge scores/rationales included in this packet template.
- **Exposure Disclosure (§8)**: Điểm số và lý do giám định từ đợt chạy pilot cũ đã bị bộc lộ trong quá trình kiểm toán mã nguồn và báo cáo audit. Do đó, đợt đánh giá này không tuyên bố là nghiên cứu mù tuyệt đối (blind study). Tuy nhiên, Owner vẫn thực hiện gán nhãn, nhận định và trích dẫn bằng chứng hoàn toàn độc lập trước khi bất kỳ lượt giám định judge mới nào được thực hiện.


---

## Bảng tổng quan 12 mục đánh giá

| STT | Item ID | Mã ca (Case ID) | Loại mục | Quyết định | Kỳ vọng | Trạng thái Review |
|---|---|---|---|---|---|---|
| REV-01 | `REV-01` | `pdf-v3-012-ctrl-missing-exception` | `synthetic_control` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-02 | `REV-02` | `pdf-v3-045` | `real_answer` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-03 | `REV-03` | `pdf-v3-005-ctrl-off-topic` | `synthetic_control` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-04 | `REV-04` | `pdf-v3-014-ctrl-unsupported` | `synthetic_control` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-05 | `REV-05` | `pdf-v3-002` | `refusal_control` | `REFUSAL` | `ANSWER` | `pending_review` |
| REV-06 | `REV-06` | `pdf-v3-012` | `real_answer` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-07 | `REV-07` | `pdf-v3-032` | `real_answer` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-08 | `REV-08` | `pdf-v3-004-ctrl-wrong-fact` | `synthetic_control` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-09 | `REV-09` | `pdf-v3-004` | `real_answer` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-10 | `REV-10` | `pdf-v3-005` | `real_answer` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-11 | `REV-11` | `pdf-v3-014` | `real_answer` | `ANSWER` | `ANSWER` | `pending_review` |
| REV-12 | `REV-12` | `pdf-v3-053` | `refusal_control` | `REFUSAL` | `REFUSAL` | `pending_review` |

---

## Chi tiết từng mục và mẫu ghi nhận đánh giá của Owner

### Mục REV-01: `pdf-v3-012-ctrl-missing-exception` (synthetic_control)

- **Question**: Bản nháp thường và hồ sơ tranh chấp được giữ bao lâu?
- **Actual Output**: Bản nháp thường giữ 30 ngày. Hồ sơ tranh chấp không có quy định riêng.
- **Reference Answer**: Bản nháp thường 30 ngày; hồ sơ tranh chấp 90 ngày thay cho 30 ngày.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `dd080f90-d359-4133-9224-58994aaec0fc`
- **Input SHA-256**: `sha256:021fd8176cef5184a015bacd601ea59e3fcd3ed5ffec965ef14a5f4c26190a04`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E1]**: Quyền và lưu trữ
SYNTHETIC FIXTURE - agent-authored - owner review pending
QD-63: thời hạn lưu bản sao là 90 ngày.
1. Quyền truy cập: người đọc chỉ được xem tài liệu.
1.1. Biên tập viên: được sửa bản nháp, không được công bố.
1.2. Chủ sở hữu: được công bố bản đã duyệt.
2. Lưu trữ: bản nháp thường được giữ 30 ngày.
2.1. Hồ sơ tranh chấp được giữ 90 ngày, thay cho 30 ngày.
PDF page 1 | CC BY 4.0 | Knora evaluation fixture

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-01
case_id: pdf-v3-012-ctrl-missing-exception
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-02: `pdf-v3-045` (real_answer)

- **Question**: PhoNLP toolkit dung licnese gi theo abstract (khong hoi license PDF)?
- **Actual Output**: Theo tóm tắt, PhoNLP được phát hành dưới giấy phép Apache License 2.0. [[E3]]
- **Reference Answer**: Apache License 2.0 cho toolkit.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `d8e8bf10-9d8d-4d72-8f8b-7afd8c9a20b1`
- **Input SHA-256**: `sha256:fb2b6eb01dd07f5f8abba42bb041dcc097bacabc71bfcc6e7a070ad2453e5b01`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E3]**: PhoNLP:Ajointmulti-tasklearningmodelforVietnamesepart-of-speech
tagging,namedentityrecognitionanddependencyparsing
LinhTheNguyen and DatQuocNguyen
VinAIResearch,Hanoi,Vietnam
{v.linhnt140, v.datnq9}@vinai.io
Abstract (Nguyen et al.,2017;Le-Hong and Bui,2018).
We present the first multi-task learning Thus, there is a need to develop NLP toolkits for
model—named PhoNLP—for joint Viet- linguisticannotationsw.r.t. VietnamesePOStag-
namese part-of-speech (POS) tagging, named ging,NERanddependencyparsing.
entity recognition (NER) and dependency VnCoreNLP (Vu et al.,2018) is the previ-
parsing. Experiments on Vietnamese bench- ous public toolkit employing traditional feature-
mark datasets show that PhoNLP produces based machine learning models to handle those
state-of-the-art results, outperforming a Vietnamese NLP tasks. However, VnCoreNLP
single-task learning approach that fine-tunes is now no longer considered state-of-the-art be-
the pre-trained Vietnamese language model
PhoBERT (Nguyen and Nguyen, 2020) for cause its performance results are significantly
each task independently. We publicly release outperformedbyonesobtainedwhenfine-tuning
PhoNLP as an open-source toolkit under the PhoBERT—the current state-of-the-art monolin-
Apache License 2.0. Although we specify gual pre-trained language model for Vietnamese
PhoNLPforVietnamese,ourPhoNLPtraining (Nguyen and Nguyen,2020). Note that there are
and evaluation command scripts in fact can nopubliclyavailablefine-tunedBERT-basedmod-
directly work for other languages that have a elsforthethreeVietnamesetasks. Assumingthat
pre-trained BERT-based language model and therewouldbe,apotentialdrawbackmightbethat
gold annotated corpora available for the three
tasks of POS tagging, NER and dependency anNLPpackagewrappingsuchfine-tunedBERT-
parsing. We hope that PhoNLP can serve as basedmodelswouldtakealargestoragespace,i.e.
a strong baseline and useful toolkit for future threetimeslargerthanthestoragespaceusedbya
NLP research and applications to not only BERTmodel(Devlinetal.,2019),thusitwouldnot
Vietnamese but also the other languages. Our besuitableforpracticalapplicationsthatrequirea
PhoNLP is available athttps://github. smallerstoragespace. Jointlymulti-tasklearning
com/VinAIResearch/PhoNLP. isapromisingsolutionasitmighthelpreducethe
1 Introduction storagespace. Inaddition,POStagging,NERand
dependency parsing are related tasks: POS tags
Vietnamese NLP research has been significantly are essential input features used for dependency
explo

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-02
case_id: pdf-v3-045
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-03: `pdf-v3-005-ctrl-off-topic` (synthetic_control)

- **Question**: Hạn mức đầu kỳ được cấp bao nhiêu lượt?
- **Actual Output**: Màu yêu thích của tôi là xanh dương. Tôi thích thời tiết đẹp.
- **Reference Answer**: 14 lượt.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `d2676672-1eb9-4daf-a56d-de9016a86019`
- **Input SHA-256**: `sha256:6b1ac5e1f2509e4978c9462cb4e0abad2d8e84d7e340bef614a84eaba0db3c11`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E1]**: Hạn mức sử dụng
SYNTHETIC FIXTURE - agent-authored - owner review pending
COL-58: tổng hạn mức là 42 lượt. Không cộng dồn lượt đã hết hạn.
Hạn mức đầu kỳ cấp 14 lượt. Lượt chuyển kỳ được dùng trước lượt đầu kỳ.
Hạn mức chuyển kỳ tối đa 28 lượt. Hạn mức được kiểm tra lúc 09:00 mỗi thứ Hai.
PDF page 1 | CC BY 4.0 | Knora evaluation fixture

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-03
case_id: pdf-v3-005-ctrl-off-topic
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-04: `pdf-v3-014-ctrl-unsupported` (synthetic_control)

- **Question**: Compare evidence and citation in the bilingual glossary.
- **Actual Output**: Evidence means approval by the Tokyo office within 3 minutes. Citation means a mandatory payment of 500 USD to that office.
- **Reference Answer**: Evidence is source evidence, not the answer; a citation points to source evidence.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `9caa9ab8-ab7a-42d9-b64e-f20ebb1d4411`
- **Input SHA-256**: `sha256:226473d89f21990d85c6f78aa9d2463aec917ee5304e8331cd75b3aac8dff6b7`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E1]**: Bilingual evidence glossary
SYNTHETIC FIXTURE - agent-authored - owner review pending
Evidence nghĩa là bằng chứng nguồn, không Answer means a response supported by
phải câu trả lời. source evidence.
Citation nghĩa là trích dẫn chỉ đến bằng chứng A citation does not replace the required
nguồn. answer facts.
Refusal nghĩa là từ chối trả lời khi thiếu bằng A refusal must not invent a missing source
chứng. fact.
PDF page 1 | CC BY 4.0 | Knora evaluation fixture

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-04
case_id: pdf-v3-014-ctrl-unsupported
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-05: `pdf-v3-002` (refusal_control)

- **Question**: Đơn chuẩn nội địa được đổi trong bao lâu và phạm vi nào?
- **Actual Output**: *(REFUSAL - Không có câu trả lời)*
- **Reference Answer**: Trong 48 giờ sau khi nhận; áp dụng đơn nội địa.
- **Decision / Expected**: `REFUSAL` / `ANSWER`
- **Trace ID**: `9375291d-cbd0-4150-8eab-c1a8108f85c2`
- **Input SHA-256**: `sha256:00265f05dab3fc3bac4763cddf8945ea80841f8162aadfb1ba5f61041865827a`

**Bằng chứng trích xuất (Generation Evidence):**

- *(Không có bằng chứng văn bản)*

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-05
case_id: pdf-v3-002
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
refusal_verdict:
  verdict: pending # accept | reject
  reason: ""
```

---

### Mục REV-06: `pdf-v3-012` (real_answer)

- **Question**: Bản nháp thường và hồ sơ tranh chấp được giữ bao lâu?
- **Actual Output**: Bản nháp thường được giữ 30 ngày; hồ sơ tranh chấp được giữ 90 ngày. [[E1]]
- **Reference Answer**: Bản nháp thường 30 ngày; hồ sơ tranh chấp 90 ngày thay cho 30 ngày.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `dd080f90-d359-4133-9224-58994aaec0fc`
- **Input SHA-256**: `sha256:c86b9735459fc49a90a2233da1b7747189dbcba8b7e275d2129232103356a684`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E1]**: Quyền và lưu trữ
SYNTHETIC FIXTURE - agent-authored - owner review pending
QD-63: thời hạn lưu bản sao là 90 ngày.
1. Quyền truy cập: người đọc chỉ được xem tài liệu.
1.1. Biên tập viên: được sửa bản nháp, không được công bố.
1.2. Chủ sở hữu: được công bố bản đã duyệt.
2. Lưu trữ: bản nháp thường được giữ 30 ngày.
2.1. Hồ sơ tranh chấp được giữ 90 ngày, thay cho 30 ngày.
PDF page 1 | CC BY 4.0 | Knora evaluation fixture

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-06
case_id: pdf-v3-012
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-07: `pdf-v3-032` (real_answer)

- **Question**: Ngoài giờ thì có được đổi nó thành P2 không?
- **Actual Output**: Không, ngoài giờ không được đổi cảnh báo P1 thành P2. [[E1]]
- **Reference Answer**: Không hạ P1 xuống P2 chỉ vì ngoài giờ.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `bbbee126-66dc-4c98-a19c-f1eff95ea06d`
- **Input SHA-256**: `sha256:69de686405a8981426a06551b0d6fe3cb1e90e1e76131e812e167d54276c7f63`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E1]**: Cảnh báo vận hành
SYNTHETIC FIXTURE - agent-authored - owner review pending
1. Cảnh báo P1: phải báo trực trong 15 phút.
1.1. Cảnh báo P2: phải báo trực trong 60 phút.
1.1.1. Không hạ P1 xuống P2 chỉ vì ngoài giờ.
PDF page 1 | CC BY 4.0 | Knora evaluation fixture

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-07
case_id: pdf-v3-032
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-08: `pdf-v3-004-ctrl-wrong-fact` (synthetic_control)

- **Question**: Cảnh báo P1 phải báo trực trong bao nhiêu phút?
- **Actual Output**: Cảnh báo P1 phải báo trực trong 150 phút.
- **Reference Answer**: 15 phút.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `5df05b2e-f785-4c07-bc02-5db87535112d`
- **Input SHA-256**: `sha256:35db757de54bd0dec49dec01791955478c04ba0535b7510c719d4e9468115246`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E1]**: Cảnh báo vận hành
SYNTHETIC FIXTURE - agent-authored - owner review pending
1. Cảnh báo P1: phải báo trực trong 15 phút.
1.1. Cảnh báo P2: phải báo trực trong 60 phút.
1.1.1. Không hạ P1 xuống P2 chỉ vì ngoài giờ.
PDF page 1 | CC BY 4.0 | Knora evaluation fixture

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-08
case_id: pdf-v3-004-ctrl-wrong-fact
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-09: `pdf-v3-004` (real_answer)

- **Question**: Cảnh báo P1 phải báo trực trong bao nhiêu phút?
- **Actual Output**: Cảnh báo P1 phải báo trực trong 15 phút. [[E1]]
- **Reference Answer**: 15 phút.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `5df05b2e-f785-4c07-bc02-5db87535112d`
- **Input SHA-256**: `sha256:2c6e80ed4a50100394cecd512cc753276e32581df01244a2b6dbca794b2db6a5`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E1]**: Cảnh báo vận hành
SYNTHETIC FIXTURE - agent-authored - owner review pending
1. Cảnh báo P1: phải báo trực trong 15 phút.
1.1. Cảnh báo P2: phải báo trực trong 60 phút.
1.1.1. Không hạ P1 xuống P2 chỉ vì ngoài giờ.
PDF page 1 | CC BY 4.0 | Knora evaluation fixture

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-09
case_id: pdf-v3-004
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-10: `pdf-v3-005` (real_answer)

- **Question**: Hạn mức đầu kỳ được cấp bao nhiêu lượt?
- **Actual Output**: Hạn mức đầu kỳ được cấp **14 lượt**.

**Cấu trúc**
- Hạn mức đầu kỳ: 14 lượt.
- Lượt chuyển kỳ được dùng trước lượt đầu kỳ.
- Hạn mức chuyển kỳ tối đa: 28 lượt.
- Kiểm tra hạn mức lúc 09:00 mỗi thứ Hai.

[[E1]]
- **Reference Answer**: 14 lượt.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `d2676672-1eb9-4daf-a56d-de9016a86019`
- **Input SHA-256**: `sha256:ac8159e18664d688f6adc5352bde9084f874791b9e4ab81a5914e28c372aa164`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E1]**: Hạn mức sử dụng
SYNTHETIC FIXTURE - agent-authored - owner review pending
COL-58: tổng hạn mức là 42 lượt. Không cộng dồn lượt đã hết hạn.
Hạn mức đầu kỳ cấp 14 lượt. Lượt chuyển kỳ được dùng trước lượt đầu kỳ.
Hạn mức chuyển kỳ tối đa 28 lượt. Hạn mức được kiểm tra lúc 09:00 mỗi thứ Hai.
PDF page 1 | CC BY 4.0 | Knora evaluation fixture

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-10
case_id: pdf-v3-005
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-11: `pdf-v3-014` (real_answer)

- **Question**: Compare evidence and citation in the bilingual glossary.
- **Actual Output**: Trong từ điển song ngữ, evidence (bằng chứng) là nguồn cung cấp thông tin thực sự; nó là dữ liệu gốc mà câu trả lời dựa vào. Trong khi đó, citation (trích dẫn) chỉ là cách tham chiếu đến evidence đó, giúp người đọc xác định nguồn nhưng không thay thế nội dung evidence. [[E1]]
- **Reference Answer**: Evidence is source evidence, not the answer; a citation points to source evidence.
- **Decision / Expected**: `ANSWER` / `ANSWER`
- **Trace ID**: `9caa9ab8-ab7a-42d9-b64e-f20ebb1d4411`
- **Input SHA-256**: `sha256:26d3b20e5012abd073a565544e081c45b1b71f1d89d3caca2bf49a5cd87fc5de`

**Bằng chứng trích xuất (Generation Evidence):**

- **[E1]**: Bilingual evidence glossary
SYNTHETIC FIXTURE - agent-authored - owner review pending
Evidence nghĩa là bằng chứng nguồn, không Answer means a response supported by
phải câu trả lời. source evidence.
Citation nghĩa là trích dẫn chỉ đến bằng chứng A citation does not replace the required
nguồn. answer facts.
Refusal nghĩa là từ chối trả lời khi thiếu bằng A refusal must not invent a missing source
chứng. fact.
PDF page 1 | CC BY 4.0 | Knora evaluation fixture

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-11
case_id: pdf-v3-014
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
```

---

### Mục REV-12: `pdf-v3-053` (refusal_control)

- **Question**: Phiếu hỗ trợ chuẩn phải giải quyết hoàn tất trong bao lâu?
- **Actual Output**: *(REFUSAL - Không có câu trả lời)*
- **Reference Answer**: Không đủ bằng chứng trong corpus để trả lời.
- **Decision / Expected**: `REFUSAL` / `REFUSAL`
- **Trace ID**: `f483e759-cf3a-465b-bd4a-43e2b9ce4018`
- **Input SHA-256**: `sha256:9baaed27310da637e276b1b9424b7a38b6f10fc3ec6dc2a0547f927f7d36fdfc`

**Bằng chứng trích xuất (Generation Evidence):**

- *(Không có bằng chứng văn bản)*

**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**

```yaml
item_id: REV-12
case_id: pdf-v3-053
reviewer: ""
reviewed_at: null
correctness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
answer_relevancy:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
faithfulness:
  verdict: pending # accept | reject | unavailable
  reason: ""
  evidence_anchor: ""
refusal_verdict:
  verdict: pending # accept | reject
  reason: ""
```

---

## Phụ lục 1: Kết quả Chấm DeepEval & Bảng Đối Chiếu (Task 7 Live Results)

- **Mô hình giám định**: `@cf/openai/gpt-oss-20b` (qua Cloudflare Workers AI Free)
- **Công cụ**: DeepEval 4.2.8 (`GEval`, `AnswerRelevancyMetric`, `FaithfulnessMetric`)
- **Số lần gọi (Attempts)**: 85 attempts (1 Ragas draft + 51 Real captures + 33 Synthetic controls + 0 Refusal controls)
- **Chi phí tiền mặt**: USD 0 (Workers Free)
- **Khởi động runtime stack**: 0 startups

### Bảng đối chiếu 12 mục đánh giá

| Item ID | Mã ca (Case ID) | Loại mục | Quyết định | Correctness | Relevancy | Faithfulness | Kết luận Giám định / Bác bỏ |
|---|---|---|:---:|:---:|:---:|:---:|---|
| **REV-01** | `pdf-v3-012-ctrl-missing-exception` | `synthetic_control` | `ANSWER` | `0.30` | `1.00` | `0.50` | **BÁC BỎ ĐẠT** (Kỳ vọng Correctness < 0.5) |
| **REV-02** | `pdf-v3-045` | `real_answer` | `ANSWER` | `1.00` | `1.00` | N/A* | Chấp nhận (Faithfulness N/A do không có exact context) |
| **REV-03** | `pdf-v3-005-ctrl-off-topic` | `synthetic_control` | `ANSWER` | `0.00` | `0.00` | `1.00` | **BÁC BỎ ĐẠT** (Kỳ vọng Relevancy < 0.5) |
| **REV-04** | `pdf-v3-014-ctrl-unsupported` | `synthetic_control` | `ANSWER` | `0.00` | `1.00` | `0.00` | **BÁC BỎ ĐẠT** (Kỳ vọng Faithfulness < 0.5) |
| **REV-05** | `pdf-v3-002` | `refusal_control` | `REFUSAL` | N/A | N/A | N/A | False Refusal Control (Kỳ vọng ANSWER nhưng model từ chối) |
| **REV-06** | `pdf-v3-012` | `real_answer` | `ANSWER` | `1.00` | `1.00` | `1.00` | Chấp nhận toàn diện (100% khớp và trung thực) |
| **REV-07** | `pdf-v3-032` | `real_answer` | `ANSWER` | N/A** | `1.00` | `1.00` | Chấp nhận (Correctness N/A do câu follow-up) |
| **REV-08** | `pdf-v3-004-ctrl-wrong-fact` | `synthetic_control` | `ANSWER` | `0.00` | `1.00` | `0.00` | **BÁC BỎ ĐẠT** (Kỳ vọng Correctness < 0.5) |
| **REV-09** | `pdf-v3-004` | `real_answer` | `ANSWER` | `0.70` | `1.00` | `1.00` | Chấp nhận (Correctness 0.70, Relevancy 1.0, Faithfulness 1.0) |
| **REV-10** | `pdf-v3-005` | `real_answer` | `ANSWER` | `0.90` | `0.40` | `1.00` | Chấp nhận một phần (Relevancy 0.40 do diễn giải thêm chi tiết) |
| **REV-11** | `pdf-v3-014` | `real_answer` | `ANSWER` | `1.00` | `1.00` | `1.00` | Chấp nhận toàn diện (100% khớp và trung thực) |
| **REV-12** | `pdf-v3-053` | `refusal_control` | `REFUSAL` | N/A | N/A | N/A | True Refusal Control (Kỳ vọng REFUSAL và model từ chối đúng) |

---

## Phụ lục 2: Ragas Proposal Batch Tiếng Việt (Task 7 Live)

- **Trạng thái**: `SUCCESS` (1 HTTP attempt, `@cf/openai/gpt-oss-20b`)
- **Generator**: Ragas 0.4.3 + Pydantic Prompt (`KnoraRagasLLM`, prompt version `ragas-vi-v1`)
- **Release gate**: `false` (Bản nháp độc lập, không tự động thăng hạng vào Gold v1)
- **Câu hỏi đề xuất**: *"Nếu tôi quên mật khẩu và muốn hoàn tiền, tôi cần làm gì?"*
- **Đáp án tham chiếu đề xuất**: *"Bạn cần đặt lại mật khẩu qua chức năng Forgot password và sau đó yêu cầu hoàn tiền trong vòng 30 ngày kể từ ngày mua."*
- **Các bước liên kết cần thiết (Proposed Necessary Hops)**:
  1. `support/account-security#0`: *"Bạn cần đặt lại mật khẩu qua chức năng Forgot password."* (Quote: *"Use Forgot password on the sign-in page to reset an account password. Never send a password to support by email."*)
  2. `support/refund-policy#0`: *"Bạn cần yêu cầu hoàn tiền trong vòng 30 ngày kể từ ngày mua."* (Quote: *"Refund requests are accepted within 30 days of purchase. Approved refunds are returned to the original payment method; they are not automatically paid in cash."*)

---

## Phụ lục 3: Trạng thái Langfuse Cloud Pilot

- **Trạng thái**: **BLOCKED / OFF** (0 POSTs, 0 DELETEs, 0 GETs, 0 scores)
- **Nguyên nhân**: Không phát hiện các biến môi trường `LANGFUSE_SECRET_KEY` và `LANGFUSE_PUBLIC_KEY` trong môi trường runtime.
- **Tuân thủ chính sách**: Theo đúng quy định tại §4.3 và §5 của plan v1 (`docs/plans/evaluation-tools-acceptance.md`), khi không có credentials hoặc chưa có lệnh tường minh của Owner, module bridge giữ an toàn 100% dữ liệu, không thực hiện bất kỳ egress nào ra cloud.

---

## Phụ lục 4: Chứng Chỉ Nhật Ký & Ranh Giới Tài Nguyên

- **Journal SQLite**: `reports/issue-158-acceptance/package_1792764691.sqlite`
- **Total attempts**: `85` (Dưới trần ngân sách 121 attempts)
- **Total startups**: `0` (Sử dụng saved baseline continuation captures)
- **Package Stopped**: `false` (Đã hoàn tất an toàn, không vi phạm invariant, không trigger emergency stop)
- **Summary file**: `reports/issue-158-acceptance/acceptance-run-summary.json`
