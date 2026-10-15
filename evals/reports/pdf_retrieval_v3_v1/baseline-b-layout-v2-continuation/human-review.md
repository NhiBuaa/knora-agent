# Baseline B human response review

All 60 frozen gold cases remain in order. Semantic review is pending; this packet does not judge answers.
Failed rows remain failed, including saved public payloads, and not-run cases remain not run.

## pdf-v3-001 — observed

- **category**: "simple"
- **language**: "vi"
- **question**: "Phiếu hỗ trợ chuẩn phải được xác nhận trong bao lâu?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Trong 24 giờ."
- **required_facts**: ["24 giờ"]
- **evidence_groups**: [["g1"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-001:1"
- **trace_id**: "1540271b-3946-4565-bbe6-aec3a901eb73"
- **conversation_id**: "d2adebf7-d1c6-4dca-b18a-c0255a7294de"
- **turn_id**: "4dd3c00a-072a-4985-b69d-843feeaf0eae"
- **response_sha256**: "771c285f4bc78ddbfcba89c5d4e181673e322c5a91ba0a9417773d59d0513c9f"
- **failure_code**: null
- **observation_failure_code**: "CITATION_STRUCTURAL_ERROR"
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [true], "selected_group_coverage": [true], "all_candidate_groups_covered": true, "all_selected_groups_covered": true, "candidate_chunk_ids": ["b75a9997-9248-4268-adea-7e6dc100e0b5"], "selected_chunk_ids": ["b75a9997-9248-4268-adea-7e6dc100e0b5"]}
- **semantic_review**: "pending"
- **actual_decision**: "ANSWER"
- **actual_answer**: "Phiếu hỗ trợ chuẩn phải được xác nhận trong 24 giờ. [[E1]]"
- **actual_refusal_reason**: null
- **actual_citations**: [{"content_checksum": "a59e008f514818311fe90970e1b6fbb0398df49bda3beb7fca3a2a3be9d1e68c", "document_id": "73242722-0442-4f57-91c9-aff70d77cd32", "document_version_id": "28008827-fc3a-43dc-9d5b-713b86da62e9", "end_line": 9, "end_offset": 420, "evidence_id": "E1", "excerpt": "Hướng dẫn phiếu hỗ trợ\nSYNTHETIC FIXTURE - agent-authored - owner review pending\nPhiếu hỗ trợ chuẩn phải được xác nhận trong 24 giờ.\nPhiếu hỗ trợ khẩn phải được xác nhận trong 2 giờ.\nGiờ xác nhận không phải thời gian giải quyết hoàn tất.\nHạn xác nhận được tính theo giờ liên tục, kể cả cuối tuần.\nKhông thu phí xác nhận phiếu hỗ trợ.\nKhông thu phí xác nhận phiếu hỗ trợ.\nPDF page 1 | CC BY 4.0 | Knora evaluation …", "heading_path": [], "page_end": 1, "page_start": 1, "source_key": "clean-02", "source_name": "clean-02.pdf", "start_line": 1, "start_offset": 0}]

## pdf-v3-002 — observed

- **category**: "simple"
- **language**: "vi"
- **question**: "Đơn chuẩn nội địa được đổi trong bao lâu và phạm vi nào?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Trong 48 giờ sau khi nhận; áp dụng đơn nội địa."
- **required_facts**: ["48 giờ sau khi nhận", "đơn hàng nội địa"]
- **evidence_groups**: [["h12"], ["h13"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-002:1"
- **trace_id**: "9375291d-cbd0-4150-8eab-c1a8108f85c2"
- **conversation_id**: "6e48ad27-ace6-4ac6-9580-6a0be4f8284c"
- **turn_id**: "766f4c64-f9e3-43e3-ba85-f08f796cbf68"
- **response_sha256**: "e792fca80fddd8079c3fd7f656ed48a55d35f7e38fdb92fdc401318085d124b8"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false], "selected_group_coverage": [false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-003 — observed

- **category**: "simple"
- **language**: "vi"
- **question**: "Ai được công bố bản đã duyệt?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Chủ sở hữu."
- **required_facts**: ["chủ sở hữu"]
- **evidence_groups**: [["h24"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-003:1"
- **trace_id**: "918a317e-5f34-41af-8af2-337db92f1808"
- **conversation_id**: "62dac7c5-d585-4fe7-86ba-cee97a5bc232"
- **turn_id**: "b3e66d33-e2d4-4d25-95ec-7fff26ac3eed"
- **response_sha256**: "af24e488f8159c01cea7599514b4a7d8a74c40c9d514808d0f7789ff59b46d77"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false], "selected_group_coverage": [false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-004 — observed

- **category**: "simple"
- **language**: "vi"
- **question**: "Cảnh báo P1 phải báo trực trong bao nhiêu phút?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "15 phút."
- **required_facts**: ["15 phút"]
- **evidence_groups**: [["h31"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-004:1"
- **trace_id**: "5df05b2e-f785-4c07-bc02-5db87535112d"
- **conversation_id**: "fd1b6ef7-34e9-4087-8699-8e8d4999ecc1"
- **turn_id**: "32cf5f39-fb43-459f-b7fa-59b15c26fb85"
- **response_sha256**: "078d1c595cf6c13672b92831e5cd3d0f76ecc962b9e6ca265dcef7661ceaa46b"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [true], "selected_group_coverage": [true], "all_candidate_groups_covered": true, "all_selected_groups_covered": true, "candidate_chunk_ids": ["fc30cda0-54ff-4726-a4ee-90c84256ced4"], "selected_chunk_ids": ["fc30cda0-54ff-4726-a4ee-90c84256ced4"]}
- **semantic_review**: "pending"
- **actual_decision**: "ANSWER"
- **actual_answer**: "Cảnh báo P1 phải báo trực trong 15 phút. [[E1]]"
- **actual_refusal_reason**: null
- **actual_citations**: [{"content_checksum": "aa38434ec8a2b8c0a30ec53b566ea207c9a97ec311c0eb65f10d0d07feecc505", "document_id": "4427c055-4fe6-485b-b557-85ad631d6e35", "document_version_id": "c0b35b48-be5f-4b26-b16b-3e02a1d92cf6", "end_line": 6, "end_offset": 263, "evidence_id": "E1", "excerpt": "Cảnh báo vận hành\nSYNTHETIC FIXTURE - agent-authored - owner review pending\n1. Cảnh báo P1: phải báo trực trong 15 phút.\n1.1. Cảnh báo P2: phải báo trực trong 60 phút.\n1.1.1. Không hạ P1 xuống P2 chỉ vì ngoài giờ.\nPDF page 1 | CC BY 4.0 | Knora evaluation …", "heading_path": [], "page_end": 1, "page_start": 1, "source_key": "hierarchy-03", "source_name": "hierarchy-03.pdf", "start_line": 1, "start_offset": 0}]

## pdf-v3-005 — observed

- **category**: "simple"
- **language**: "vi"
- **question**: "Hạn mức đầu kỳ được cấp bao nhiêu lượt?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "14 lượt."
- **required_facts**: ["14 lượt"]
- **evidence_groups**: [["c12"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-005:1"
- **trace_id**: "d2676672-1eb9-4daf-a56d-de9016a86019"
- **conversation_id**: "ae471951-cddc-4b83-a841-2c2b6ffd42ad"
- **turn_id**: "9b93d32d-3ce0-4ee2-aacd-bc2de39a8e1a"
- **response_sha256**: "338780f5f55c94fe2c487ce6a3e5981b95adef51e77edfb6335d04bbd9b5463c"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [true], "selected_group_coverage": [true], "all_candidate_groups_covered": true, "all_selected_groups_covered": true, "candidate_chunk_ids": ["a1a278bc-62ed-4b40-9eca-25a003312c5d"], "selected_chunk_ids": ["a1a278bc-62ed-4b40-9eca-25a003312c5d"]}
- **semantic_review**: "pending"
- **actual_decision**: "ANSWER"
- **actual_answer**: "Hạn mức đầu kỳ được cấp **14 lượt**.\n\n**Cấu trúc**\n- Hạn mức đầu kỳ: 14 lượt.\n- Lượt chuyển kỳ được dùng trước lượt đầu kỳ.\n- Hạn mức chuyển kỳ tối đa: 28 lượt.\n- Kiểm tra hạn mức lúc 09:00 mỗi thứ Hai.\n\n[[E1]]"
- **actual_refusal_reason**: null
- **actual_citations**: [{"content_checksum": "7e8aeb61760f58c7c8b94f4c0f6c1c6474171178af5aa015775b7482232c457c", "document_id": "486e6e2d-0857-4e09-839d-de9c208054fa", "document_version_id": "3ca50a31-2cf7-48a9-893f-584eccc324db", "end_line": 6, "end_offset": 339, "evidence_id": "E1", "excerpt": "Hạn mức sử dụng\nSYNTHETIC FIXTURE - agent-authored - owner review pending\nCOL-58: tổng hạn mức là 42 lượt. Không cộng dồn lượt đã hết hạn.\nHạn mức đầu kỳ cấp 14 lượt. Lượt chuyển kỳ được dùng trước lượt đầu kỳ.\nHạn mức chuyển kỳ tối đa 28 lượt. Hạn mức được kiểm tra lúc 09:00 mỗi thứ Hai.\nPDF page 1 | CC BY 4.0 | Knora evaluation …", "heading_path": [], "page_end": 1, "page_start": 1, "source_key": "columns-01", "source_name": "columns-01.pdf", "start_line": 1, "start_offset": 0}]

## pdf-v3-006 — extraction_or_mapping_missing

- **category**: "simple"
- **language**: "vi"
- **question**: "Kho ảnh mở cửa lúc nào?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Từ 08:30 đến 17:30."
- **required_facts**: ["08:30", "17:30"]
- **evidence_groups**: [["s12"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-006:1"
- **trace_id**: "075a9fba-a9a6-4b2a-b202-c15d7716e1d7"
- **conversation_id**: "84f1eca8-11f3-42ef-b46b-6411d3c03d37"
- **turn_id**: "2124f15e-bea8-4efb-9cde-d0734baa8bbc"
- **response_sha256**: "7bc0a693b822b9ce9dd66cfab393a023481b427b5e530a79ca8fc3c710ff5b6a"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-007 — extraction_or_mapping_missing

- **category**: "simple"
- **language**: "vi"
- **question**: "Hồ sơ MX-11 có bao nhiêu trang và được kiểm ngày nào?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "23 trang; ngày 14/10/2026."
- **required_facts**: ["23 trang", "14/10/2026"]
- **evidence_groups**: [["s21"], ["s24"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-007:1"
- **trace_id**: "ffdc0e1e-6843-4b21-a4d6-36fb99454a90"
- **conversation_id**: "ac7f663f-e058-461c-a998-2e6631686ee3"
- **turn_id**: "9e73090c-cabb-48f6-a188-4c32c29731e5"
- **response_sha256**: "0ae49223ae63c70be076c1acbc7633988a1f04ba3bb1cf30ef10c1184563c5ad"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-008 — extraction_or_mapping_missing

- **category**: "simple"
- **language**: "vi"
- **question**: "RX-03 có sai số tối đa bao nhiêu?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "0,2 độ C."
- **required_facts**: ["0,2 độ C"]
- **evidence_groups**: [["s31"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-008:1"
- **trace_id**: "01659831-2785-4bc1-ad94-841c58eb0cb4"
- **conversation_id**: "f7dd00c9-4870-440f-b0ef-c37e9bd2b5c8"
- **turn_id**: "3916ccc1-de92-413a-9630-ab1fa5e51459"
- **response_sha256**: "a76cb984989de5e9bb9028fdfa3a71e2e38421e79abbe561694d03fea4a8ff13"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-009 — observed

- **category**: "comparison"
- **language**: "vi"
- **question**: "So sánh hạn xác nhận phiếu chuẩn và khẩn; có phải hạn giải quyết hoàn tất không?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Chuẩn 24 giờ; khẩn 2 giờ. Đây không phải hạn giải quyết hoàn tất."
- **required_facts**: ["chuẩn 24 giờ", "khẩn 2 giờ", "không phải thời gian giải quyết hoàn tất"]
- **evidence_groups**: [["g1"], ["g2"], ["g3"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-009:1"
- **trace_id**: "b170a8ab-1b3e-46af-9d1c-cba686220d37"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "ebdd61eb52f962dc65224116bb76461b6c2893d57ac6b6ff374ab464d36490b8"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false], "selected_group_coverage": [false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-010 — observed

- **category**: "comparison"
- **language**: "vi"
- **question**: "Đơn chuẩn và vùng xa khác hạn đổi thế nào; đơn vùng xa đã mở niêm phong có ngoại lệ gì?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Chuẩn 48 giờ sau khi nhận; vùng xa 72 giờ sau khi nhận; không nhận đổi hàng vùng xa đã mở niêm phong."
- **required_facts**: ["chuẩn 48 giờ sau khi nhận", "vùng xa 72 giờ sau khi nhận", "không nhận đổi hàng vùng xa đã mở niêm phong"]
- **evidence_groups**: [["h13"], ["h14"], ["h15"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-010:1"
- **trace_id**: "2fe087e1-11b6-46b6-a635-274f2d56df7a"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "a56840dd1ea202b7f00765941f3fc4875031e5656ff220814c36b7c776ef50c4"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false], "selected_group_coverage": [false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-011 — observed

- **category**: "comparison"
- **language**: "vi"
- **question**: "Biên tập viên và người đọc khác quyền gì?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Người đọc chỉ xem; biên tập viên sửa bản nháp nhưng không công bố."
- **required_facts**: ["người đọc chỉ xem", "biên tập viên sửa bản nháp", "không được công bố"]
- **evidence_groups**: [["h22"], ["h23"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-011:1"
- **trace_id**: "2f5478af-bf70-4020-a57e-8e0f196c9dfd"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "1f03e7669325dbcc6e1d29eb4cf97afc462f41ef33c264aa514cc1ab8822c959"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false], "selected_group_coverage": [false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-012 — observed

- **category**: "comparison"
- **language**: "vi"
- **question**: "Bản nháp thường và hồ sơ tranh chấp được giữ bao lâu?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Bản nháp thường 30 ngày; hồ sơ tranh chấp 90 ngày thay cho 30 ngày."
- **required_facts**: ["30 ngày", "90 ngày thay cho 30 ngày"]
- **evidence_groups**: [["h25"], ["h26"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-012:1"
- **trace_id**: "dd080f90-d359-4133-9224-58994aaec0fc"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "eb85f7e7370fe350879aa8f43f03863d7ec16ec63734ce877fde75b8a0a28194"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [true, true], "selected_group_coverage": [true, true], "all_candidate_groups_covered": true, "all_selected_groups_covered": true, "candidate_chunk_ids": ["2c54d222-7131-4fa7-b4fb-ff4afae66385"], "selected_chunk_ids": ["2c54d222-7131-4fa7-b4fb-ff4afae66385"]}
- **semantic_review**: "pending"
- **actual_decision**: "ANSWER"
- **actual_answer**: "Bản nháp thường được giữ 30 ngày; hồ sơ tranh chấp được giữ 90 ngày. [[E1]]"
- **actual_refusal_reason**: null
- **actual_citations**: [{"content_checksum": "fa850438f7607eb9ea5750954f0927d8d4a87052ef313130312f66fcfdf3d2bc", "document_id": "733f1080-0a27-4781-940d-3cbdb060117c", "document_version_id": "3172814d-ea76-4213-af46-947fe702a103", "end_line": 9, "end_offset": 423, "evidence_id": "E1", "excerpt": "Quyền và lưu trữ\nSYNTHETIC FIXTURE - agent-authored - owner review pending\nQD-63: thời hạn lưu bản sao là 90 ngày.\n1. Quyền truy cập: người đọc chỉ được xem tài liệu.\n1.1. Biên tập viên: được sửa bản nháp, không được công bố.\n1.2. Chủ sở hữu: được công bố bản đã duyệt.\n2. Lưu trữ: bản nháp thường được giữ 30 ngày.\n2.1. Hồ sơ tranh chấp được giữ 90 ngày, thay cho 30 ngày.\nPDF page 1 | CC BY 4.0 | Knora evaluation …", "heading_path": [], "page_end": 1, "page_start": 1, "source_key": "hierarchy-02", "source_name": "hierarchy-02.pdf", "start_line": 1, "start_offset": 0}]

## pdf-v3-013 — observed

- **category**: "comparison"
- **language**: "vi"
- **question**: "So sánh hạn báo trực P1 và P2; ngoài giờ có được hạ P1 không?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "P1 15 phút; P2 60 phút; không hạ P1 chỉ vì ngoài giờ."
- **required_facts**: ["P1 15 phút", "P2 60 phút", "không hạ P1 chỉ vì ngoài giờ"]
- **evidence_groups**: [["h31"], ["h32"], ["h33"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-013:1"
- **trace_id**: "091f3adf-b5db-4870-a83a-c4c068671cbf"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "847adde4fd847a7223087b15013ddcf53ef4886030f24a7b6b3f4f3f0d8f1f9b"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false], "selected_group_coverage": [false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-014 — extraction_or_mapping_missing

- **category**: "comparison"
- **language**: "en"
- **question**: "Compare evidence and citation in the bilingual glossary."
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Evidence is source evidence, not the answer; a citation points to source evidence."
- **required_facts**: ["evidence is source evidence, not an answer", "citation points to source evidence"]
- **evidence_groups**: [["c21"], ["c22"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-014:1"
- **trace_id**: "9caa9ab8-ab7a-42d9-b64e-f20ebb1d4411"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "d44ff845714d2ff3629463fc2e07027ebded648f8beee670702688d8df146b56"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "ANSWER"
- **actual_answer**: "Trong từ điển song ngữ, evidence (bằng chứng) là nguồn cung cấp thông tin thực sự; nó là dữ liệu gốc mà câu trả lời dựa vào. Trong khi đó, citation (trích dẫn) chỉ là cách tham chiếu đến evidence đó, giúp người đọc xác định nguồn nhưng không thay thế nội dung evidence. [[E1]]"
- **actual_refusal_reason**: null
- **actual_citations**: [{"content_checksum": "5fc40236ce546ce78c37b9d06f832813cd541cca9cb08da05f7ee5af8923e5d9", "document_id": "bbcdad36-5752-409c-806f-42a7f9fef85d", "document_version_id": "d0f48886-f87c-4467-b69e-530a03ada95a", "end_line": 9, "end_offset": 462, "evidence_id": "E1", "excerpt": "Bilingual evidence glossary\nSYNTHETIC FIXTURE - agent-authored - owner review pending\nEvidence nghĩa là bằng chứng nguồn, không Answer means a response supported by\nphải câu trả lời. source evidence.\nCitation nghĩa là trích dẫn chỉ đến bằng chứng A citation does not replace the required\nnguồn. answer facts.\nRefusal nghĩa là từ chối trả lời khi thiếu bằng A refusal must not invent a missing source\nchứng. fact.\nPDF page 1 | CC BY 4.0 | Knora evaluation …", "heading_path": [], "page_end": 1, "page_start": 1, "source_key": "columns-02", "source_name": "columns-02.pdf", "start_line": 1, "start_offset": 0}]

## pdf-v3-015 — extraction_or_mapping_missing

- **category**: "comparison"
- **language**: "mixed"
- **question**: "Refusal khác Answer thế nào, có được bịa fact thiếu không?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Refusal là từ chối khi thiếu bằng chứng; Answer có bằng chứng nguồn. Refusal không được bịa fact thiếu."
- **required_facts**: ["từ chối khi thiếu bằng chứng", "answer supported by source evidence", "must not invent a missing fact"]
- **evidence_groups**: [["c23"], ["c24"], ["c26"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-015:1"
- **trace_id**: "4344b014-1633-4a61-8ddb-7e22517898e0"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "f402dded82ff5a838ceb56e6584b0fbdc92c17811b50d8d87db29c658846f3fa"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-016 — extraction_or_mapping_missing

- **category**: "comparison"
- **language**: "mixed"
- **question**: "PhoBERT và ViT5 được mô tả với loại mô hình nào và ViT5 benchmark mấy tác vụ?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "PhoBERT là mô hình ngôn ngữ đơn ngữ cho tiếng Việt; ViT5 là encoder-decoder cho tiếng Việt, benchmark hai tác vụ."
- **required_facts**: ["PhoBERT monolingual Vietnamese", "ViT5 encoder-decoder Vietnamese", "two downstream tasks"]
- **evidence_groups**: [["pb1"], ["v51"], ["v52"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-016:1"
- **trace_id**: "9da9ff4e-22f5-44ef-8340-2a02610bf0ec"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "8e1298a6da66e90193a341b6a4a437303dba2b7b33f0890333f8e91b65012528"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-017 — extraction_or_mapping_missing

- **category**: "comparison"
- **language**: "mixed"
- **question**: "PhoNLP nêu ba tác vụ nào; ViT5 nêu hai tác vụ nào?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "PhoNLP: POS tagging, NER, dependency parsing. ViT5: abstractive text summarization, NER."
- **required_facts**: ["PhoNLP POS tagging, NER, dependency parsing", "ViT5 abstractive summarization and NER"]
- **evidence_groups**: [["pn1"], ["v52"], ["v53"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-017:1"
- **trace_id**: "f6c70884-4ece-425d-9347-85ab9ebfffb2"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "eacc0ecbc6ceb3e65276dd0b126a9b36eb28cb3655e99433cef1699c16e4416b"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-018 — observed

- **category**: "comparison"
- **language**: "en"
- **question**: "Compare the TB-19 and TB-20 totals, preserving each row identifier, and state the difference in orders."
- **expected_behavior**: "ANSWER"
- **reference_answer**: "TB-19 totals 30 orders; TB-20 totals 16 orders; TB-19 is larger by 14 orders."
- **required_facts**: ["TB-19 30 orders", "TB-20 16 orders", "difference 14 orders"]
- **evidence_groups**: [["t11"], ["t14"], ["t15"], ["t18"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-018:1"
- **trace_id**: "bb6e155c-20ca-40c7-986c-47bb049c5c48"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "11379b0d538e6869ad444b50ac42c072ed5f4a83c76c610331e3fb84c0eda5b1"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false, false], "selected_group_coverage": [false, false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-019 — observed

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "Bảng TB-19 chia số đơn đã xử lý và còn chờ thế nào, tổng bao nhiêu?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "TB-19: đã xử lý 12, còn chờ 18, tổng 30 đơn."
- **required_facts**: ["TB-19", "đã xử lý 12", "còn chờ 18", "tổng 30 đơn"]
- **evidence_groups**: [["t11"], ["t12"], ["t13"], ["t14"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-019:1"
- **trace_id**: "70e1be4e-5ccc-4c0d-8c58-03edb7644eb7"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "e32258723c48751e74126dd366d731d8bb39af9f0d2ad66db470650ff3e55063"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false, false], "selected_group_coverage": [false, false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-020 — observed

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "Hàng TB-20 có bao nhiêu đơn đã xử lý và còn chờ?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "TB-20: đã xử lý 7; còn chờ 9."
- **required_facts**: ["TB-20", "đã xử lý 7", "còn chờ 9"]
- **evidence_groups**: [["t15"], ["t16"], ["t17"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-020:1"
- **trace_id**: "00d24fb6-0006-4f5a-9ea3-d6e2bcb5a71d"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "27ed071d2d9d8659d3c159a196a800ac9712838fcc439bb086359927eaaa2793"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false], "selected_group_coverage": [false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-021 — observed

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "TB-27 có phút trực tuyến, phút tại chỗ và tổng thế nào?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "TB-27: trực tuyến 45 phút, tại chỗ 15 phút, tổng 60 phút."
- **required_facts**: ["TB-27", "trực tuyến 45 phút", "tại chỗ 15 phút", "tổng 60 phút"]
- **evidence_groups**: [["t21"], ["t22"], ["t23"], ["t24"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-021:1"
- **trace_id**: "69763478-9c10-4e4b-8513-964b0b92c522"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "884596ae5a6d5b22e78687a5e4867b109cdb756bfe405bd75af2ff09e4f76c76"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false, false], "selected_group_coverage": [false, false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-022 — observed

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "TB-28 có phút trực tuyến, phút tại chỗ và tổng thế nào?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "TB-28: trực tuyến 20 phút, tại chỗ 10 phút, tổng 30 phút."
- **required_facts**: ["TB-28", "trực tuyến 20 phút", "tại chỗ 10 phút", "tổng 30 phút"]
- **evidence_groups**: [["t25"], ["t26"], ["t27"], ["t28"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-022:1"
- **trace_id**: "4cdd8ce2-22f5-4cb4-bd59-88df7f557e04"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "85f341c5e7a3a6168dce528fe7fb671354eabda52557014cc595e84863e2d344"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false, false], "selected_group_coverage": [false, false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-023 — observed

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "Đọc hàng KT-09 theo đúng đơn vị: sáng, chiều và tổng?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "KT-09: sáng 2,5 kg; chiều 4,0 kg; tổng 6,5 kg."
- **required_facts**: ["KT-09", "sáng 2,5 kg", "chiều 4,0 kg", "tổng 6,5 kg"]
- **evidence_groups**: [["t31"], ["t32"], ["t33"], ["t34"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-023:1"
- **trace_id**: "399d99e3-8ad4-4fac-b7c2-c7d500ef2154"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "0945a8cac661817611e4cf49b5aae629260bba78edc1d66cd7bfc79b998169e8"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false, false], "selected_group_coverage": [false, false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-024 — observed

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "Đọc hàng KT-10 theo đúng đơn vị: sáng, chiều và tổng?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "KT-10: sáng 1,5 kg; chiều 2,0 kg; tổng 3,5 kg."
- **required_facts**: ["KT-10", "sáng 1,5 kg", "chiều 2,0 kg", "tổng 3,5 kg"]
- **evidence_groups**: [["t35"], ["t36"], ["t37"], ["t38"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-024:1"
- **trace_id**: "2a9d4f73-eeee-4b7b-a26f-95a97e1cd56c"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "dec8c29b141fa3ad3315b2824e68a5929da87279e201e3265d9c60ca1e69a0f9"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false, false], "selected_group_coverage": [false, false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-025 — observed

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "Theo mục 2 và 2.1 cảnh báo, người trực cần làm gì và khi nào gọi lại?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Phải xác nhận nhận cảnh báo; chưa có xác nhận thì gọi lại sau 5 phút."
- **required_facts**: ["xác nhận đã nhận cảnh báo", "gọi lại sau 5 phút khi chưa xác nhận"]
- **evidence_groups**: [["h34"], ["h35"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-025:1"
- **trace_id**: "5e79f2c9-fec4-4d8f-b593-7e6a6f8e7024"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "fafe3cb499935244883d7d71739c386aea88d376ae3090722eba41794a3877f3"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false], "selected_group_coverage": [false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-026 — observed

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "Quy tắc 2.2 có cho gửi nội dung khách hàng ra kênh công khai không?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Không được gửi nội dung khách hàng qua kênh công khai."
- **required_facts**: ["không gửi nội dung khách hàng qua kênh công khai"]
- **evidence_groups**: [["h36"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-026:1"
- **trace_id**: "a3a88148-9fdf-41b8-9867-dd647663cee1"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "e5fad7440bd96b97618458fd386114052254d422d27ab6a37481d41ed1e88fa5"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false], "selected_group_coverage": [false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-027 — observed

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "Theo hai cột hạn mức, lượt nào dùng trước và lượt hết hạn xử lý thế nào?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Dùng lượt chuyển kỳ trước lượt đầu kỳ; không cộng dồn lượt đã hết hạn."
- **required_facts**: ["chuyển kỳ dùng trước đầu kỳ", "không cộng dồn lượt hết hạn"]
- **evidence_groups**: [["c14"], ["c15"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-027:1"
- **trace_id**: "e2f6c10f-91e4-4ead-8081-e27a232e5262"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "6d2f922492328db32ecfec904135c5f1034791d12b26221135474c4047fa9a41"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false], "selected_group_coverage": [false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-028 — extraction_or_mapping_missing

- **category**: "table_hierarchy"
- **language**: "vi"
- **question**: "Trong bản ảnh MX-11, bao nhiêu trang phụ lục ảnh và bản số hóa có thay bản gốc không?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "5 trang phụ lục ảnh; bản số hóa không thay bản gốc có chữ ký."
- **required_facts**: ["5 trang phụ lục ảnh", "không thay bản gốc có chữ ký"]
- **evidence_groups**: [["s22"], ["s23"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-028:1"
- **trace_id**: "489137e7-36b3-4a27-b4a4-f006e4040633"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "f26a57ea36ca0ffd9c0e4aa5d525e631f3440ecfd7269afb8f3a0eec08d09359"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-029 — observed

- **category**: "follow_up"
- **language**: "vi"
- **question**: "Vậy hạn đó có tính cuối tuần và mất phí không?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Tính giờ liên tục kể cả cuối tuần; không thu phí xác nhận."
- **required_facts**: ["tính giờ liên tục, kể cả cuối tuần", "không thu phí xác nhận"]
- **evidence_groups**: [["g4"], ["g5", "g6"]]
- **parent_case_id**: "pdf-v3-001"
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-029:1"
- **trace_id**: "297a3174-e958-4234-a47d-fd7c40a08483"
- **conversation_id**: "d2adebf7-d1c6-4dca-b18a-c0255a7294de"
- **turn_id**: "6873a097-74ca-4cac-ac14-a7df905461fe"
- **response_sha256**: "3164b4cb9a1af1ff1be4498f13c9e1d12039c0fadb67037c8e9f53826d046009"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [true, true], "selected_group_coverage": [true, true], "all_candidate_groups_covered": true, "all_selected_groups_covered": true, "candidate_chunk_ids": ["b75a9997-9248-4268-adea-7e6dc100e0b5"], "selected_chunk_ids": ["b75a9997-9248-4268-adea-7e6dc100e0b5"]}
- **semantic_review**: "pending"
- **actual_decision**: "ANSWER"
- **actual_answer**: "Đúng vậy, thời hạn tính liên tục và bao gồm cuối tuần, và không tính phí xác nhận. [[E1]]"
- **actual_refusal_reason**: null
- **actual_citations**: [{"content_checksum": "a59e008f514818311fe90970e1b6fbb0398df49bda3beb7fca3a2a3be9d1e68c", "document_id": "73242722-0442-4f57-91c9-aff70d77cd32", "document_version_id": "28008827-fc3a-43dc-9d5b-713b86da62e9", "end_line": 9, "end_offset": 420, "evidence_id": "E1", "excerpt": "Hướng dẫn phiếu hỗ trợ\nSYNTHETIC FIXTURE - agent-authored - owner review pending\nPhiếu hỗ trợ chuẩn phải được xác nhận trong 24 giờ.\nPhiếu hỗ trợ khẩn phải được xác nhận trong 2 giờ.\nGiờ xác nhận không phải thời gian giải quyết hoàn tất.\nHạn xác nhận được tính theo giờ liên tục, kể cả cuối tuần.\nKhông thu phí xác nhận phiếu hỗ trợ.\nKhông thu phí xác nhận phiếu hỗ trợ.\nPDF page 1 | CC BY 4.0 | Knora evaluation …", "heading_path": [], "page_end": 1, "page_start": 1, "source_key": "clean-02", "source_name": "clean-02.pdf", "start_line": 1, "start_offset": 0}]

## pdf-v3-030 — observed

- **category**: "follow_up"
- **language**: "vi"
- **question**: "Còn hoàn tiền cho loại đơn vừa hỏi mất bao lâu?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "5 ngày làm việc."
- **required_facts**: ["5 ngày làm việc"]
- **evidence_groups**: [["h16"]]
- **parent_case_id**: "pdf-v3-002"
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-030:1"
- **trace_id**: "55361c19-9b29-4a67-80f7-2f98b3c7d175"
- **conversation_id**: "6e48ad27-ace6-4ac6-9580-6a0be4f8284c"
- **turn_id**: "35e20aa8-cfd1-4469-ab03-a58c4af028d9"
- **response_sha256**: "ceb8d849c12853dd8822d0c10d49cdc5d95c0b54ae47c13b22c019caffbf1322"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false], "selected_group_coverage": [false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-031 — observed

- **category**: "follow_up"
- **language**: "vi"
- **question**: "Người đó có quyền công bố bản chưa duyệt được nêu không?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Chỉ quyền công bố bản đã duyệt được nêu; không thể suy ra quyền công bố bản chưa duyệt."
- **required_facts**: ["quyền được nêu chỉ là công bố bản đã duyệt", "không thể suy ra quyền công bố bản chưa duyệt"]
- **evidence_groups**: [["h24"]]
- **parent_case_id**: "pdf-v3-003"
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-031:1"
- **trace_id**: "992b4634-6459-4ecc-9c81-180ea00bc5b6"
- **conversation_id**: "62dac7c5-d585-4fe7-86ba-cee97a5bc232"
- **turn_id**: "254c2687-1967-4dcf-9271-569440c1b5cf"
- **response_sha256**: "c755f77534fbb954027e3843f827887a29977f99f39534a91f8d60378f18c458"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false], "selected_group_coverage": [false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-032 — observed

- **category**: "follow_up"
- **language**: "vi"
- **question**: "Ngoài giờ thì có được đổi nó thành P2 không?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Không hạ P1 xuống P2 chỉ vì ngoài giờ."
- **required_facts**: ["không hạ P1 xuống P2 chỉ vì ngoài giờ"]
- **evidence_groups**: [["h33"]]
- **parent_case_id**: "pdf-v3-004"
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-032:1"
- **trace_id**: "bbbee126-66dc-4c98-a19c-f1eff95ea06d"
- **conversation_id**: "fd1b6ef7-34e9-4087-8699-8e8d4999ecc1"
- **turn_id**: "12a4fed9-d3dd-4abb-ac80-041c18d1664f"
- **response_sha256**: "7dad8fc85facf6f87042adf28d7932ab6b6d420016cb24f8f00a12041f395d13"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [true], "selected_group_coverage": [true], "all_candidate_groups_covered": true, "all_selected_groups_covered": true, "candidate_chunk_ids": ["fc30cda0-54ff-4726-a4ee-90c84256ced4"], "selected_chunk_ids": ["fc30cda0-54ff-4726-a4ee-90c84256ced4"]}
- **semantic_review**: "pending"
- **actual_decision**: "ANSWER"
- **actual_answer**: "Không, ngoài giờ không được đổi cảnh báo P1 thành P2. [[E1]]"
- **actual_refusal_reason**: null
- **actual_citations**: [{"content_checksum": "aa38434ec8a2b8c0a30ec53b566ea207c9a97ec311c0eb65f10d0d07feecc505", "document_id": "4427c055-4fe6-485b-b557-85ad631d6e35", "document_version_id": "c0b35b48-be5f-4b26-b16b-3e02a1d92cf6", "end_line": 6, "end_offset": 263, "evidence_id": "E1", "excerpt": "Cảnh báo vận hành\nSYNTHETIC FIXTURE - agent-authored - owner review pending\n1. Cảnh báo P1: phải báo trực trong 15 phút.\n1.1. Cảnh báo P2: phải báo trực trong 60 phút.\n1.1.1. Không hạ P1 xuống P2 chỉ vì ngoài giờ.\nPDF page 1 | CC BY 4.0 | Knora evaluation …", "heading_path": [], "page_end": 1, "page_start": 1, "source_key": "hierarchy-03", "source_name": "hierarchy-03.pdf", "start_line": 1, "start_offset": 0}]

## pdf-v3-033 — observed

- **category**: "follow_up"
- **language**: "vi"
- **question**: "Còn phần chuyển kỳ tối đa bao nhiêu lượt và kiểm lúc nào?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "28 lượt; kiểm lúc 09:00 mỗi thứ Hai."
- **required_facts**: ["28 lượt", "09:00 mỗi thứ Hai"]
- **evidence_groups**: [["c13"], ["c16"]]
- **parent_case_id**: "pdf-v3-005"
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-033:1"
- **trace_id**: "0d932713-e191-4e65-a7d8-9439cdf4ccee"
- **conversation_id**: "ae471951-cddc-4b83-a841-2c2b6ffd42ad"
- **turn_id**: "597eae9e-b920-443b-8165-f5cafdbd13b7"
- **response_sha256**: "e311fe483e1646acd83edd7f61464fafa93a4fbd9606755fa4457f867551f7b0"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [true, true], "selected_group_coverage": [true, true], "all_candidate_groups_covered": true, "all_selected_groups_covered": true, "candidate_chunk_ids": ["a1a278bc-62ed-4b40-9eca-25a003312c5d"], "selected_chunk_ids": ["a1a278bc-62ed-4b40-9eca-25a003312c5d"]}
- **semantic_review**: "pending"
- **actual_decision**: "ANSWER"
- **actual_answer**: "## Thông tin chuyển kỳ\n\n- Phần chuyển kỳ tối đa là **28 lượt**. \n- Kiểm tra hạn mức lúc **09:00 mỗi thứ Hai**. [[E1]]"
- **actual_refusal_reason**: null
- **actual_citations**: [{"content_checksum": "7e8aeb61760f58c7c8b94f4c0f6c1c6474171178af5aa015775b7482232c457c", "document_id": "486e6e2d-0857-4e09-839d-de9c208054fa", "document_version_id": "3ca50a31-2cf7-48a9-893f-584eccc324db", "end_line": 6, "end_offset": 339, "evidence_id": "E1", "excerpt": "Hạn mức sử dụng\nSYNTHETIC FIXTURE - agent-authored - owner review pending\nCOL-58: tổng hạn mức là 42 lượt. Không cộng dồn lượt đã hết hạn.\nHạn mức đầu kỳ cấp 14 lượt. Lượt chuyển kỳ được dùng trước lượt đầu kỳ.\nHạn mức chuyển kỳ tối đa 28 lượt. Hạn mức được kiểm tra lúc 09:00 mỗi thứ Hai.\nPDF page 1 | CC BY 4.0 | Knora evaluation …", "heading_path": [], "page_end": 1, "page_start": 1, "source_key": "columns-01", "source_name": "columns-01.pdf", "start_line": 1, "start_offset": 0}]

## pdf-v3-034 — extraction_or_mapping_missing

- **category**: "follow_up"
- **language**: "vi"
- **question**: "Chủ nhật nơi đó có nhận hàng không và cần xuất trình gì?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Không nhận hàng Chủ nhật; người nhận xuất trình mã nhận hàng."
- **required_facts**: ["không nhận hàng Chủ nhật", "mã nhận hàng"]
- **evidence_groups**: [["s13"], ["s14"]]
- **parent_case_id**: "pdf-v3-006"
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-034:1"
- **trace_id**: "fedbeb4e-8ae2-4ef4-b897-9af081a7d8e0"
- **conversation_id**: "84f1eca8-11f3-42ef-b46b-6411d3c03d37"
- **turn_id**: "48346ab7-b453-4bf3-848d-eb10c62025c4"
- **response_sha256**: "e31825c3357154e32924c4b1f8e89fd3f859cb05fc0cc3a5cdf7e39d5ff13feb"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-035 — extraction_or_mapping_missing

- **category**: "follow_up"
- **language**: "vi"
- **question**: "Trong số trang vừa hỏi có bao nhiêu trang ảnh?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "5 trang phụ lục ảnh."
- **required_facts**: ["5 trang phụ lục ảnh"]
- **evidence_groups**: [["s22"]]
- **parent_case_id**: "pdf-v3-007"
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-035:1"
- **trace_id**: "c6942cd2-9050-41f6-b4e7-4d2348934c2f"
- **conversation_id**: "ac7f663f-e058-461c-a998-2e6631686ee3"
- **turn_id**: "734a32db-18f7-438a-a913-c2dd359f70fe"
- **response_sha256**: "c4b1bbe41c5eb12d87f38ba606a8684a99d64459ee21b981645d42835bb4350e"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-036 — extraction_or_mapping_missing

- **category**: "follow_up"
- **language**: "vi"
- **question**: "Thiết bị đó kiểm chuẩn bao lâu một lần và khi tem kiểm chuẩn hết hạn có dùng được không?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Mỗi 6 tháng; không dùng khi tem kiểm chuẩn hết hạn."
- **required_facts**: ["6 tháng", "không dùng khi tem hết hạn"]
- **evidence_groups**: [["s32"], ["s33"]]
- **parent_case_id**: "pdf-v3-008"
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-036:1"
- **trace_id**: "a6a7862f-3c32-431d-87b8-e00634506a17"
- **conversation_id**: "f7dd00c9-4870-440f-b0ef-c37e9bd2b5c8"
- **turn_id**: "db1b01de-702c-47e6-bd67-63bff93c051d"
- **response_sha256**: "695560ec3bd613ac2631ffb798447631c2738bc316ffad6c44c56ffb8049a0c9"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-037 — observed

- **category**: "typo_identifier"
- **language**: "vi"
- **question**: "phieu ho tro khan xac nhan may gio?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "2 giờ."
- **required_facts**: ["2 giờ"]
- **evidence_groups**: [["g2"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-037:1"
- **trace_id**: "10a3f197-236a-4eb2-bec5-48815a577319"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "8229c7d442da2e534c2640f24c524da0f6ee0b78f7de9b01180a813d05b0b812"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false], "selected_group_coverage": [false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-038 — observed

- **category**: "typo_identifier"
- **language**: "vi"
- **question**: "qd-42 boi hoan toi da bao nhieu dong?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "350.000 đồng."
- **required_facts**: ["350.000 đồng"]
- **evidence_groups**: [["h11"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-038:1"
- **trace_id**: "57dba5c6-61db-408e-97db-92333a37e9c4"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "f38aa43efe97da215660b32fe809ce337bbed76e3d0d4736e5bfe1a1f6274920"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false], "selected_group_coverage": [false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-039 — observed

- **category**: "typo_identifier"
- **language**: "vi"
- **question**: "QD-63 luu ban sao may ngay?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "90 ngày."
- **required_facts**: ["90 ngày"]
- **evidence_groups**: [["h21"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-039:1"
- **trace_id**: "32329bce-a310-4c25-9893-44d5cc60ec55"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "f125a6e475423783d5739014c84b64ad6433882c567eb2f6e249a881b82d1953"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false], "selected_group_coverage": [false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-040 — observed

- **category**: "typo_identifier"
- **language**: "vi"
- **question**: "COL-58 tong han muc la 24 hay 42 luot?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "42 lượt, không phải 24."
- **required_facts**: ["42 lượt"]
- **evidence_groups**: [["c11"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-040:1"
- **trace_id**: "871b9372-d9bf-48fa-acbd-4be80b894f0b"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "40754ba84a7e688ae9719756cc5c377d69de6a91c6d462c2e7865126a41ecaa6"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false], "selected_group_coverage": [false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-041 — extraction_or_mapping_missing

- **category**: "typo_identifier"
- **language**: "vi"
- **question**: "SC-07 phi luu kho 1 ngay bao nhieu?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "27.000 đồng mỗi ngày."
- **required_facts**: ["27.000 đồng mỗi ngày"]
- **evidence_groups**: [["s11"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-041:1"
- **trace_id**: "d750ef80-7900-4d00-a853-e63bba883235"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "f95534e117e8e105e5d001d4fa0647b938621a18508e7896f1ec2914de8404fc"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-042 — extraction_or_mapping_missing

- **category**: "typo_identifier"
- **language**: "vi"
- **question**: "RX-03 nhiet do bao quan tu may den may do C?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "15 đến 25 độ C."
- **required_facts**: ["15 đến 25 độ C"]
- **evidence_groups**: [["s34"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-042:1"
- **trace_id**: "e554aa4d-57e8-4bb6-a908-87f91b3f1696"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "b9906c09d921ca3f469e5ec60b651c3be4eb76d70d37cb134d0141cd79979cd7"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-043 — extraction_or_mapping_missing

- **category**: "typo_identifier"
- **language**: "en"
- **question**: "Does a citaton replace the required answer facts?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "No, a citation does not replace the required answer facts."
- **required_facts**: ["citation does not replace required answer facts"]
- **evidence_groups**: [["c25"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-043:1"
- **trace_id**: "99382943-39c3-4c4d-bb82-adca9d2b85a0"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "719401ccae5000c69de72eb1a353c387c3c2725b5897badce05164e325ac3efa"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-044 — extraction_or_mapping_missing

- **category**: "typo_identifier"
- **language**: "mixed"
- **question**: "Phobert co bao nhieu version, ten gi?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Hai phiên bản: PhoBERT-base và PhoBERT-large."
- **required_facts**: ["hai phiên bản", "phiên bản base của PhoBERT", "phiên bản large của PhoBERT"]
- **evidence_groups**: [["pb2"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-044:1"
- **trace_id**: "b29eab48-16e1-436a-bdd5-847f7a9bca18"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "43ccf62535dd38628b543ccb51ec05bba0a4ac9a127d6a2a81f5aa01d03b7215"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-045 — observed

- **category**: "typo_identifier"
- **language**: "mixed"
- **question**: "PhoNLP toolkit dung licnese gi theo abstract (khong hoi license PDF)?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Apache License 2.0 cho toolkit."
- **required_facts**: ["toolkit Apache License 2.0"]
- **evidence_groups**: [["pn2"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-045:1"
- **trace_id**: "d8e8bf10-9d8d-4d72-8f8b-7afd8c9a20b1"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "6862937cbf799c967ff46c4578f5754f42af3f869c75fe55e83de7d4922b1d70"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [true], "selected_group_coverage": [true], "all_candidate_groups_covered": true, "all_selected_groups_covered": true, "candidate_chunk_ids": ["75de1620-c8ce-434a-b031-ea46d8570c27", "ab31322c-7555-498c-aa8b-7b2181201f91", "66a3b490-0f34-4ff6-be7a-36eae9b14667"], "selected_chunk_ids": ["75de1620-c8ce-434a-b031-ea46d8570c27", "ab31322c-7555-498c-aa8b-7b2181201f91", "66a3b490-0f34-4ff6-be7a-36eae9b14667"]}
- **semantic_review**: "pending"
- **actual_decision**: "ANSWER"
- **actual_answer**: "Theo tóm tắt, PhoNLP được phát hành dưới giấy phép Apache License 2.0. [[E3]]"
- **actual_refusal_reason**: null
- **actual_citations**: [{"content_checksum": "efe56896ff326cc0d9af0b0365d69e1476729b33201f6a9f5ad34dc1d4b84a62", "document_id": "2746c059-25b6-4ba0-83f2-7bd30776576c", "document_version_id": "d12ebe0c-e77c-4d58-b3a7-694b3518e5e7", "end_line": 35, "end_offset": 2521, "evidence_id": "E3", "excerpt": "PhoNLP:Ajointmulti-tasklearningmodelforVietnamesepart-of-speech\ntagging,namedentityrecognitionanddependencyparsing\nLinhTheNguyen and DatQuocNguyen\nVinAIResearch,Hanoi,Vietnam\n{v.linhnt140, v.datnq9}@vinai.io\nAbstract (Nguyen et al.,2017;Le-Hong and Bui,2018).\nWe present the first multi-task learning Thus, there is a need to develop NLP toolkits for\nmodel—named PhoNLP—for joint Viet- linguisticannotationsw.r.t. VietnamesePOStag-\nnamese part-of-speech (POS) tagging, named …", "heading_path": [], "page_end": 1, "page_start": 1, "source_key": "academic-phonlp", "source_name": "academic-phonlp.pdf", "start_line": 1, "start_offset": 0}]

## pdf-v3-046 — extraction_or_mapping_missing

- **category**: "typo_identifier"
- **language**: "mixed"
- **question**: "vit5 pretrained tren subset ngon ngu nao cua CC100?"
- **expected_behavior**: "ANSWER"
- **reference_answer**: "Tập con đơn ngữ tiếng Việt của CC100."
- **required_facts**: ["Vietnamese monolingual subset of CC100"]
- **evidence_groups**: [["v54"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-046:1"
- **trace_id**: "d4b30339-22b7-427e-a49e-f80a04f8f6e6"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "6a8d098d88a16697aa8a39c920afa19b77e4d5beb540da0eede6dc949df642c9"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-047 — observed

- **category**: "multi_hop"
- **language**: "vi"
- **question**: "Tra mã A-17 trong sổ điều hướng rồi cho biết mức bồi hoàn tối đa của hồ sơ được trỏ tới."
- **expected_behavior**: "ANSWER"
- **reference_answer**: "A-17 trỏ tới QD-42; mức bồi hoàn tối đa là 350.000 đồng."
- **required_facts**: ["A-17 trỏ tới QD-42", "mức bồi hoàn tối đa: 350.000 đồng"]
- **evidence_groups**: [["r1"], ["h11"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-047:1"
- **trace_id**: "218b87c0-caba-4ae7-b64b-bad791aca665"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "f443409c2a63a94e7c5d85f62955078eef8f80ee6ba23d1a7884f3f9a3b8ae3e"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false], "selected_group_coverage": [false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-048 — observed

- **category**: "multi_hop"
- **language**: "vi"
- **question**: "Tra mã B-08 trong sổ điều hướng rồi cho biết tổng số đơn của hồ sơ được trỏ tới."
- **expected_behavior**: "ANSWER"
- **reference_answer**: "B-08 trỏ tới TB-19; tổng số đơn là 30 đơn."
- **required_facts**: ["B-08 trỏ tới TB-19", "tổng số đơn: 30 đơn"]
- **evidence_groups**: [["r2"], ["t11"], ["t14"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-048:1"
- **trace_id**: "cf2109a6-0c21-4750-a6d4-3e7eb3e8700c"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "ba4f894869efa1841b78ea2a106b56a25634d235ce50ae6237fe7dd8dd10217f"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false], "selected_group_coverage": [false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-049 — extraction_or_mapping_missing

- **category**: "multi_hop"
- **language**: "vi"
- **question**: "Tra mã C-31 trong sổ điều hướng rồi cho biết phí lưu kho của hồ sơ được trỏ tới."
- **expected_behavior**: "ANSWER"
- **reference_answer**: "C-31 trỏ tới SC-07; phí lưu kho là 27.000 đồng mỗi ngày."
- **required_facts**: ["C-31 trỏ tới SC-07", "phí lưu kho: 27.000 đồng mỗi ngày"]
- **evidence_groups**: [["r3"], ["s11"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-049:1"
- **trace_id**: "0b4bc6a5-16c2-457c-b859-e8b2335e2dc9"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "8bdf7004c7d864cc2cdcebde6bf0ee0bb35c73dfb30fe57731c16f99b461fd16"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "extraction_or_mapping_missing"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-050 — observed

- **category**: "multi_hop"
- **language**: "vi"
- **question**: "Tra mã D-12 trong sổ điều hướng rồi cho biết tổng hạn mức của hồ sơ được trỏ tới."
- **expected_behavior**: "ANSWER"
- **reference_answer**: "D-12 trỏ tới COL-58; tổng hạn mức là 42 lượt."
- **required_facts**: ["D-12 trỏ tới COL-58", "tổng hạn mức: 42 lượt"]
- **evidence_groups**: [["r4"], ["c11"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-050:1"
- **trace_id**: "ed7446db-e0a5-4c90-a072-8aa319e8473c"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "6be54967a41eaaffb66755f6c9489c1725ecda3eb4ef2cdc4fcf1a6fa0cd6f1b"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false], "selected_group_coverage": [false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-051 — observed

- **category**: "multi_hop"
- **language**: "vi"
- **question**: "Tra mã E-24 trong sổ điều hướng rồi cho biết thời hạn lưu bản sao của hồ sơ được trỏ tới."
- **expected_behavior**: "ANSWER"
- **reference_answer**: "E-24 trỏ tới QD-63; thời hạn lưu bản sao là 90 ngày."
- **required_facts**: ["E-24 trỏ tới QD-63", "thời hạn lưu bản sao: 90 ngày"]
- **evidence_groups**: [["r5"], ["h21"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-051:1"
- **trace_id**: "744a4644-7292-480d-8ae4-5e4e0e6b8fc5"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "20ecf36a3129ec27b0ce44c6b8055d65f51d2fcd5179c629947c0fbbc8705797"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false], "selected_group_coverage": [false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-052 — observed

- **category**: "multi_hop"
- **language**: "vi"
- **question**: "Tra mã F-09 trong sổ điều hướng rồi cho biết tổng thời lượng hỗ trợ của hồ sơ được trỏ tới."
- **expected_behavior**: "ANSWER"
- **reference_answer**: "F-09 trỏ tới TB-27; tổng thời lượng hỗ trợ là 60 phút."
- **required_facts**: ["F-09 trỏ tới TB-27", "tổng thời lượng hỗ trợ: 60 phút"]
- **evidence_groups**: [["r6"], ["t21"], ["t24"]]
- **parent_case_id**: null
- **no_answer_scope**: null
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-052:1"
- **trace_id**: "b60cf293-c8d1-4c46-9e57-5a5015ff475e"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "af320c1170f46a8d129c34c0c1fda53cde60e98689429aebe04449cafdb51b19"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "evaluable", "candidate_pool": "saved post-threshold candidates with final decisions", "candidate_group_coverage": [false, false, false], "selected_group_coverage": [false, false, false], "all_candidate_groups_covered": false, "all_selected_groups_covered": false, "candidate_chunk_ids": [], "selected_chunk_ids": []}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-053 — observed

- **category**: "no_answer"
- **language**: "vi"
- **question**: "Phiếu hỗ trợ chuẩn phải giải quyết hoàn tất trong bao lâu?"
- **expected_behavior**: "REFUSAL"
- **reference_answer**: "Không đủ bằng chứng trong corpus để trả lời."
- **required_facts**: []
- **evidence_groups**: []
- **parent_case_id**: null
- **no_answer_scope**: "Chỉ có hạn xác nhận; g3 phủ định việc đồng nhất với hạn giải quyết hoàn tất. Không có SLA hoàn tất."
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-053:1"
- **trace_id**: "f483e759-cf3a-465b-bd4a-43e2b9ce4018"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "1feb3f48c39e1f77c92fb9821d1b00f157edfe0b87abcd65c17f660891bfa9a9"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "not_evaluable"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-054 — observed

- **category**: "no_answer"
- **language**: "vi"
- **question**: "Mã Z-99 trỏ tới hồ sơ nào?"
- **expected_behavior**: "REFUSAL"
- **reference_answer**: "Không đủ bằng chứng trong corpus để trả lời."
- **required_facts**: []
- **evidence_groups**: []
- **parent_case_id**: null
- **no_answer_scope**: "Sổ điều hướng chỉ có A-17/B-08/C-31/D-12/E-24/F-09; không có Z-99."
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-054:1"
- **trace_id**: "fad1a316-c757-42dc-bdbb-18ec1e04a42c"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "98dcc0ba0f136c1c7e61051adb9c200827f6022fc0c3f0beb6dc582d1095ddb9"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "not_evaluable"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-055 — observed

- **category**: "no_answer"
- **language**: "vi"
- **question**: "QD-42 quy định mức bồi hoàn cho đơn quốc tế bao nhiêu?"
- **expected_behavior**: "REFUSAL"
- **reference_answer**: "Không đủ bằng chứng trong corpus để trả lời."
- **required_facts**: []
- **evidence_groups**: []
- **parent_case_id**: null
- **no_answer_scope**: "QD-42 chỉ nêu phạm vi nội địa; không có mức cho đơn quốc tế."
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-055:1"
- **trace_id**: "65f404f7-32fd-4af5-91a6-7d14fd969162"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "a744ba91c024d305f5aa7d5560060d9e99f7fdff7813b3492dcf807d7ccd8a48"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "not_evaluable"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-056 — observed

- **category**: "no_answer"
- **language**: "vi"
- **question**: "PhoNLP báo cáo chi phí huấn luyện bằng USD bao nhiêu?"
- **expected_behavior**: "REFUSAL"
- **reference_answer**: "Không đủ bằng chứng trong corpus để trả lời."
- **required_facts**: []
- **evidence_groups**: []
- **parent_case_id**: null
- **no_answer_scope**: "Toàn bộ 7 trang PhoNLP không nêu chi phí huấn luyện USD; không suy đoán từ thiết bị hoặc thời gian."
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-056:1"
- **trace_id**: "b47f0913-dee4-45d1-a17d-b27c257c93e0"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "a5deb9c7c7a795534c465a6d48c8a6e90de0c0be34bee3fa918ca299d0b82b25"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "not_evaluable"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-057 — observed

- **category**: "no_answer"
- **language**: "vi"
- **question**: "ViT5 có chỉ số F1 trên bộ dữ liệu hư cấu KnoraMed-2099 bao nhiêu?"
- **expected_behavior**: "REFUSAL"
- **reference_answer**: "Không đủ bằng chứng trong corpus để trả lời."
- **required_facts**: []
- **evidence_groups**: []
- **parent_case_id**: null
- **no_answer_scope**: "KnoraMed-2099 không xuất hiện trong bất kỳ PDF nào; không dùng các bộ benchmark khác thay thế."
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-057:1"
- **trace_id**: "1226214b-9966-403e-81ce-64e78dfb1e7c"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "167fd01619b41c7b83ef1d6395eebe8f7021878c545120b6770640a584d05a6b"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "not_evaluable"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-058 — observed

- **category**: "no_answer"
- **language**: "vi"
- **question**: "Kho ảnh SC-07 có số điện thoại liên hệ nào?"
- **expected_behavior**: "REFUSAL"
- **reference_answer**: "Không đủ bằng chứng trong corpus để trả lời."
- **required_facts**: []
- **evidence_groups**: []
- **parent_case_id**: null
- **no_answer_scope**: "Bản ảnh SC-07 có phí/giờ/ngày/mã nhận, không có số điện thoại; toàn corpus không bổ sung số này."
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-058:1"
- **trace_id**: "1c7f0cc2-d798-42e7-87ed-224810d044f4"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "7dc0377224ece2cae5005420208d36a65574c8b23f3d6d6d438119f1c00f5f6d"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "not_evaluable"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-059 — observed

- **category**: "no_answer"
- **language**: "vi"
- **question**: "TB-19 có số liệu quý IV năm 2027 không?"
- **expected_behavior**: "REFUSAL"
- **reference_answer**: "Không đủ bằng chứng trong corpus để trả lời."
- **required_facts**: []
- **evidence_groups**: []
- **parent_case_id**: null
- **no_answer_scope**: "Bảng chỉ có hai hàng TB-19/TB-20 theo trạng thái; không có thời gian quý IV/2027."
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-059:1"
- **trace_id**: "31c5b0be-57f2-4db1-96ba-5d7b82a06a30"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "617674b602944e7f87301723aa9614b280f0f79bcd3dff8ee6bf62b6d6ac7058"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "not_evaluable"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

## pdf-v3-060 — observed

- **category**: "no_answer"
- **language**: "en"
- **question**: "What is the 2026 production accuracy of PhoBERT at Knora?"
- **expected_behavior**: "REFUSAL"
- **reference_answer**: "The corpus does not provide enough evidence to answer."
- **required_facts**: []
- **evidence_groups**: []
- **parent_case_id**: null
- **no_answer_scope**: "The corpus contains a 2020 research paper, not a Knora production measurement in 2026; no such accuracy appears in the 16 PDFs."
- **run_id**: "s1-runtime-binding-20261015-01"
- **attempt_id**: "s1-runtime-binding-20261015-01:pdf-v3-060:1"
- **trace_id**: "fbf654c9-e4fb-4b18-911f-a1a26fa64492"
- **conversation_id**: null
- **turn_id**: null
- **response_sha256**: "4e99439ecc571a8fb106ffbe3163d9672f7648267764b1dea0a228d30caa6496"
- **failure_code**: null
- **observation_failure_code**: null
- **coverage**: {"status": "not_evaluable"}
- **semantic_review**: "pending"
- **actual_decision**: "REFUSAL"
- **actual_answer**: null
- **actual_refusal_reason**: "INSUFFICIENT_EVIDENCE"
- **actual_citations**: []

