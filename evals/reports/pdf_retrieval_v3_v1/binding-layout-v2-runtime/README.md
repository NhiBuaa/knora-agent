# Review binding gold → chunks: actual runtime pypdf layout-v2

**Trạng thái: chờ owner duyệt actual proposal/IDs. Chưa collect/scoring/B 60 câu.**

- Run: `s1-runtime-binding-20261015-01`; Workspace: `ee8acee6-6fea-4aaf-b472-d5ae1609516f`.
- Actual proposal SHA: `3796d4228f8bd5d6677b162125c34d551e644fe5488133c31df8b0f306488a9d`.
- Actual derivation SHA: `fd5711d2ce76e40dae231cc441feddce61aa36451ae073e4a55f3bbfda3f46f2`.
- Offline proposal SHA: `2fa44a4d7acefbf60bf4f5fef457b7a28b97de46d76120b51c0a4453fbc44075`.
- Corpus SHA: `c8c0a978e3494242c19d1d342d00d8c8e239aaed8715c6213e5415085ac0fcc0`.
- Gold SHA: `2299db0f8a24f3633883c21a407e68ec3b07e0765c4511bfe55522f0768604ae`.

## Đối chiếu đã kiểm tra

[Persistence evidence](persistence-evidence.json): 47 vectors thực, tất cả 1024d và profile `embedding-cloudflare-qwen3-06b-v1`/Cloudflare Qwen3; 16 attempts cho 16 jobs. Database có 0 Question Trace, 0 Conversation và 0 Turn. Container riêng đã trả về stopped; volume, database và original objects được giữ nguyên.

Free/quota được kiểm trước startup lúc 05:10:46 UTC ngày 15/10/2026: **Workers Free / Current plan, 95.88/10,000 neurons**; account khớp credential config và đã thông báo cửa sổ qua #158. Sau lượt chạy, dashboard reload hiển thị **96.62/10,000** khoảng 05:15–05:16 UTC. Đây là số đo account chia sẻ, có thể cập nhật trễ; không coi chênh lệch 0.74 là chi phí cuối cùng của riêng run. Không upgrade, paid gateway hoặc paid fallback. Không có invoice riêng để quy đổi chi phí thực; ngân sách trả phí vẫn 0 USD.

Launcher local đã được kiểm bằng MockTransport, capability denial và production Windows PDF extraction trước live; reviewer độc lập xác nhận cùng SHA. SHA256 của file Windows CRLF đã chạy: `10a902b2624020ecaf86bf6a1297df8480102757923f65b84b4499b44041b0fb`. [Bản lưu source](ingestion-launcher.py.txt) chỉ chuẩn hóa CRLF→LF để lưu Git, SHA256 `0c5809cb10c89db6ca98419c9b8b570b2c3a4032f0c82ba536b04f6ce3b3b123`; không đổi dòng code nào. Code production tại commit `71bf691c67d20baa271a553799cd4673a0b78dc3`; original composition, HTTP authorization, worker, parser, persistence và reader được tái sử dụng. Không chạy lại full tests vì không sửa production code; kiểm chứng thực tế ở lượt ingestion này và các asserts đối chiếu riêng.

16 PDF/60 câu frozen giữ nguyên. 16 upload qua production HTTP routes bằng FastAPI TestClient trong process; không mở listener8153. Mỗi job production worker xử lý đúng một attempt. 14 succeeded /2 failed `PDF_TEXT_INSUFFICIENT` (scan-01, scan-03); giữ mọi nguồn và anchor. Provider thực Cloudflare Qwen3 0.6B1024d:14 HTTP attempts/47 document strings, query/generation/judge0, không retry. Free preflight và provenance trong [run-evidence.json](run-evidence.json); ngân sách trả phí0USD.

47/47 chunk có rawSHA, parser/normalizer/chunker, page/range, checksum và nội dung giống offline snapshot. 86/86 anchor có cùng trạng thái và các occurrence; 61 mappings được đối chiếu theo nguồn/trang/offset/checksum, giữ25 missing. Chỉ workspace/version/chunk-set/chunk identity đổi thành UUID persisted thực; vì vậy actual proposal/derivation SHA khác offline. Không fuzzy matching hoặc thay gold/parser. Đây chưa phải kết quả retrieval quality.

[chunks.json](chunks.json) chứa toàn bộ nội dung/provenance; [proposals.json](proposals.json) là output nguyên bản của proposer hiện có. [review-candidate.json](review-candidate.json) chứa choices **pending**, không phải approved record. Không mang số index offline sang runtime nếu chưa đối chiếu occurrence.

## Từng binding và bằng chứng vị trí

Exact evidence text cùng source/physical page nằm trong review-candidate; kiểm tra range nửa mở trong chunk nội dung tương ứng. Ba lựa chọn nhiều occurrence g5/g6/t17 được giữ bằng source/page/offset đã duyệt.

| Anchor | Source | Page | Runtime index | Range | Actual chunk IDs |
| --- | --- | ---: | ---: | --- | --- |
| r1 | clean-01 | 1 | 0 | [78,106) | `0d6c4295-e1b1-4b08-9a2a-4250fe61c3d0` |
| r2 | clean-01 | 1 | 0 | [107,135) | `0d6c4295-e1b1-4b08-9a2a-4250fe61c3d0` |
| r3 | clean-01 | 1 | 0 | [136,164) | `0d6c4295-e1b1-4b08-9a2a-4250fe61c3d0` |
| r4 | clean-01 | 2 | 0 | [78,107) | `3caed1b0-823a-4d67-9cce-46d5fa71fd93` |
| r5 | clean-01 | 2 | 0 | [108,136) | `3caed1b0-823a-4d67-9cce-46d5fa71fd93` |
| r6 | clean-01 | 2 | 0 | [137,165) | `3caed1b0-823a-4d67-9cce-46d5fa71fd93` |
| g1 | clean-02 | 1 | 0 | [81,132) | `b75a9997-9248-4268-adea-7e6dc100e0b5` |
| g2 | clean-02 | 1 | 0 | [133,182) | `b75a9997-9248-4268-adea-7e6dc100e0b5` |
| g3 | clean-02 | 1 | 0 | [183,237) | `b75a9997-9248-4268-adea-7e6dc100e0b5` |
| g4 | clean-02 | 1 | 0 | [238,296) | `b75a9997-9248-4268-adea-7e6dc100e0b5` |
| g5 | clean-02 | 1 | 0 | [297,333) | `b75a9997-9248-4268-adea-7e6dc100e0b5` |
| g6 | clean-02 | 1 | 1 | [334,370) | `b75a9997-9248-4268-adea-7e6dc100e0b5` |
| h11 | hierarchy-01 | 1 | 0 | [79,122) | `2b8031ca-a049-43d7-a96e-70cac81c7710` |
| h12 | hierarchy-01 | 1 | 0 | [123,164) | `2b8031ca-a049-43d7-a96e-70cac81c7710` |
| h13 | hierarchy-01 | 1 | 0 | [165,216) | `2b8031ca-a049-43d7-a96e-70cac81c7710` |
| h14 | hierarchy-01 | 1 | 0 | [217,270) | `2b8031ca-a049-43d7-a96e-70cac81c7710` |
| h15 | hierarchy-01 | 1 | 0 | [271,325) | `2b8031ca-a049-43d7-a96e-70cac81c7710` |
| h16 | hierarchy-01 | 1 | 0 | [326,368) | `2b8031ca-a049-43d7-a96e-70cac81c7710` |
| h21 | hierarchy-02 | 1 | 0 | [75,114) | `2c54d222-7131-4fa7-b4fb-ff4afae66385` |
| h22 | hierarchy-02 | 1 | 0 | [115,166) | `2c54d222-7131-4fa7-b4fb-ff4afae66385` |
| h23 | hierarchy-02 | 1 | 0 | [167,225) | `2c54d222-7131-4fa7-b4fb-ff4afae66385` |
| h24 | hierarchy-02 | 1 | 0 | [226,269) | `2c54d222-7131-4fa7-b4fb-ff4afae66385` |
| h25 | hierarchy-02 | 1 | 0 | [270,315) | `2c54d222-7131-4fa7-b4fb-ff4afae66385` |
| h26 | hierarchy-02 | 1 | 0 | [316,373) | `2c54d222-7131-4fa7-b4fb-ff4afae66385` |
| h31 | hierarchy-03 | 1 | 0 | [76,120) | `fc30cda0-54ff-4726-a4ee-90c84256ced4` |
| h32 | hierarchy-03 | 1 | 0 | [121,167) | `fc30cda0-54ff-4726-a4ee-90c84256ced4` |
| h33 | hierarchy-03 | 1 | 0 | [168,213) | `fc30cda0-54ff-4726-a4ee-90c84256ced4` |
| h34 | hierarchy-03 | 2 | 0 | [76,121) | `2f76e65f-99ff-473f-b508-47de0d74ca7c` |
| h35 | hierarchy-03 | 2 | 0 | [122,168) | `2f76e65f-99ff-473f-b508-47de0d74ca7c` |
| h36 | hierarchy-03 | 2 | 0 | [169,223) | `2f76e65f-99ff-473f-b508-47de0d74ca7c` |
| c11 | columns-01 | 1 | 0 | [74,106) | `a1a278bc-62ed-4b40-9eca-25a003312c5d` |
| c12 | columns-01 | 1 | 0 | [139,166) | `a1a278bc-62ed-4b40-9eca-25a003312c5d` |
| c13 | columns-01 | 1 | 0 | [211,244) | `a1a278bc-62ed-4b40-9eca-25a003312c5d` |
| c14 | columns-01 | 1 | 0 | [107,138) | `a1a278bc-62ed-4b40-9eca-25a003312c5d` |
| c15 | columns-01 | 1 | 0 | [167,210) | `a1a278bc-62ed-4b40-9eca-25a003312c5d` |
| c16 | columns-01 | 1 | 0 | [245,289) | `a1a278bc-62ed-4b40-9eca-25a003312c5d` |
| c21 | columns-02 | 1 | — | missing | — |
| c22 | columns-02 | 1 | — | missing | — |
| c23 | columns-02 | 1 | — | missing | — |
| c24 | columns-02 | 1 | — | missing | — |
| c25 | columns-02 | 1 | — | missing | — |
| c26 | columns-02 | 1 | — | missing | — |
| t11 | table-01 | 1 | 0 | [160,165) | `1694b5b2-cc87-4b8e-8c32-ab028485b615` |
| t12 | table-01 | 1 | 0 | [166,168) | `1694b5b2-cc87-4b8e-8c32-ab028485b615` |
| t13 | table-01 | 1 | 0 | [169,171) | `1694b5b2-cc87-4b8e-8c32-ab028485b615` |
| t14 | table-01 | 1 | 0 | [172,174) | `1694b5b2-cc87-4b8e-8c32-ab028485b615` |
| t15 | table-01 | 1 | 0 | [175,180) | `1694b5b2-cc87-4b8e-8c32-ab028485b615` |
| t16 | table-01 | 1 | 0 | [181,182) | `1694b5b2-cc87-4b8e-8c32-ab028485b615` |
| t17 | table-01 | 1 | 1 | [183,184) | `1694b5b2-cc87-4b8e-8c32-ab028485b615` |
| t18 | table-01 | 1 | 0 | [185,187) | `1694b5b2-cc87-4b8e-8c32-ab028485b615` |
| t21 | table-02 | 1 | 0 | [169,174) | `5f08dfa9-e5c4-4205-a14e-9e0c84bef84c` |
| t22 | table-02 | 1 | 0 | [175,177) | `5f08dfa9-e5c4-4205-a14e-9e0c84bef84c` |
| t23 | table-02 | 1 | 0 | [178,180) | `5f08dfa9-e5c4-4205-a14e-9e0c84bef84c` |
| t24 | table-02 | 1 | 0 | [181,183) | `5f08dfa9-e5c4-4205-a14e-9e0c84bef84c` |
| t25 | table-02 | 1 | 0 | [184,189) | `5f08dfa9-e5c4-4205-a14e-9e0c84bef84c` |
| t26 | table-02 | 1 | 0 | [190,192) | `5f08dfa9-e5c4-4205-a14e-9e0c84bef84c` |
| t27 | table-02 | 1 | 0 | [193,195) | `5f08dfa9-e5c4-4205-a14e-9e0c84bef84c` |
| t28 | table-02 | 1 | 0 | [196,198) | `5f08dfa9-e5c4-4205-a14e-9e0c84bef84c` |
| t31 | table-03 | 1 | 0 | [153,158) | `a747ce32-dc6e-4bdd-8b28-2b57f79ccc8a` |
| t32 | table-03 | 1 | 0 | [159,162) | `a747ce32-dc6e-4bdd-8b28-2b57f79ccc8a` |
| t33 | table-03 | 1 | 0 | [163,166) | `a747ce32-dc6e-4bdd-8b28-2b57f79ccc8a` |
| t34 | table-03 | 1 | 0 | [167,170) | `a747ce32-dc6e-4bdd-8b28-2b57f79ccc8a` |
| t35 | table-03 | 1 | 0 | [171,176) | `a747ce32-dc6e-4bdd-8b28-2b57f79ccc8a` |
| t36 | table-03 | 1 | 0 | [177,180) | `a747ce32-dc6e-4bdd-8b28-2b57f79ccc8a` |
| t37 | table-03 | 1 | 0 | [181,184) | `a747ce32-dc6e-4bdd-8b28-2b57f79ccc8a` |
| t38 | table-03 | 1 | 0 | [185,188) | `a747ce32-dc6e-4bdd-8b28-2b57f79ccc8a` |
| s11 | scan-01 | 1 | — | missing | — |
| s12 | scan-01 | 1 | — | missing | — |
| s13 | scan-01 | 1 | — | missing | — |
| s14 | scan-01 | 1 | — | missing | — |
| s21 | scan-02 | 1 | — | missing | — |
| s22 | scan-02 | 1 | — | missing | — |
| s23 | scan-02 | 1 | — | missing | — |
| s24 | scan-02 | 1 | — | missing | — |
| s31 | scan-03 | 1 | — | missing | — |
| s32 | scan-03 | 1 | — | missing | — |
| s33 | scan-03 | 1 | — | missing | — |
| s34 | scan-03 | 1 | — | missing | — |
| pb1 | academic-phobert | 1 | — | missing | — |
| pb2 | academic-phobert | 1 | — | missing | — |
| pn1 | academic-phonlp | 1 | — | missing | — |
| pn2 | academic-phonlp | 1 | 0 | [1246,1265) | `66a3b490-0f34-4ff6-be7a-36eae9b14667` |
| v51 | academic-vit5 | 1 | — | missing | — |
| v52 | academic-vit5 | 1 | — | missing | — |
| v53 | academic-vit5 | 1 | — | missing | — |
| v54 | academic-vit5 | 1 | — | missing | — |

## Quyết định cần owner duyệt

Duyệt actual proposal SHA ở trên với 58 unique mappings, g5/g6/t17 tại các vị trí đã đối chiếu trong bảng/candidate, và giữ25 missing? Sau quyết định mới ghi approved binding record theo cơ chế hiện có. Chưa cấp quyền chạy Baseline B/query/generation/scoring từ approval này. PR#189 tiếp tục Draft, chưa merge/deploy/Done.
