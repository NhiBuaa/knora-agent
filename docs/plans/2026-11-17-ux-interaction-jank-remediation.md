# Kế Hoạch Triển Khai Khắc Phục Hiện Tượng Giật / Đơ Và Tối Ưu Tương Tác UX (Giai Đoạn 1)

> **Dành cho kỹ sư triển khai:** BẮT BUỘC tuân thủ các nguyên tắc từ `test-driven-development` (TDD: Red-Green-Refactor), `emil-design-eng` (phản hồi tức thì, exit transition, custom easing), `animation-performance` (chỉ animate transform/opacity, chạy ngoài main-thread, 60 FPS), và `verification-before-completion` (chạy kiểm chứng có bằng chứng cụ thể trước khi kết luận).

**Mục tiêu:** Khắc phục triệt để các điểm nghẽn tương tác nghiêm trọng nhất đã phát hiện trong báo cáo kiểm toán UX/Performance: thêm Optimistic UI & sửa lỗi logic mảng cho Upload & Archive tài liệu, tối ưu Divider drag chống bão tính toán kiểu dáng, loại bỏ Forced Reflow ô Composer, memoize Markdown AST khi chọn Citation, và bổ sung Exit transitions mượt mà cho Dialog/Drawer.

**Kiến trúc:**
- **Documents Optimistic UI:** Chèn dòng giữ chỗ lạc quan (optimistic row) ngay khi bấm Upload; chèn trực tiếp tài liệu từ phản hồi của `POST /documents` vào mảng state (thay vì chỉ `map` trên mảng cũ khiến tài liệu mới bị nuốt mất), loại bỏ request `GET /documents` kép thừa thãi; cập nhật lạc quan trạng thái `archived` và bỏ ép chuyển trang `router.push` khi restore.
- **Divider Drag Throttling (rAF + Decoupled State):** Tách biệt sự kiện `pointermove` khỏi React re-render và I/O `localStorage.setItem`. Cập nhật CSS variables trực tiếp trên DOM qua `requestAnimationFrame`, chỉ commit React state và ghi bộ nhớ khi nhả chuột (`pointerup`).
- **Composer Layout Stability:** Sử dụng CSS `field-sizing: content` hiện đại kết hợp cơ chế đo chiều cao không ép hạ `height = 0px`, loại bỏ Forced Synchronous Reflow trên từng ký tự.
- **Citation Markdown Memoization:** Memoize plugin rehype và pipeline chuyển đổi Markdown AST, cô lập trạng thái `selectedIndex` để không phân tích lại cú pháp toàn bộ tài liệu khi chuyển đổi trích dẫn.
- **Dialog & Drawer Exit Transitions:** Bổ sung chu trình đóng (exit state machine) cho `Dialog` (140ms ease-out với `cubic-bezier(0.23, 1, 0.32, 1)`, trượt nhẹ `translateY(6px)` hoặc `translateX(-12px)`, giảm độ mờ về 0), hỗ trợ đầy đủ `prefers-reduced-motion`.

**Tech Stack:** Next.js 15, React 18, TypeScript, Vitest, Testing Library, Tailwind CSS / Vanilla CSS Variables, Chrome DevTools MCP.

**Tài liệu tham chiếu:** [Báo cáo kiểm tra toàn diện UX, Độ trễ & Hiệu năng chuyển động](file:///C:/Users/NhiBuaa/.gemini/antigravity/brain/5ea9c021-b31f-4b5e-b6c9-673fee695925/knora-ux-performance-audit-report.md)

---

## Ràng Buộc Chung (Global Constraints)
- Mọi thay đổi tuân thủ nghiêm ngặt chuẩn định dạng mã nguồn: `npm --prefix frontend run format:check` và `python -m ruff format --check .`.
- Không chỉnh sửa tệp tự sinh `frontend/generated/knora-openapi.ts`.
- Mọi hiệu ứng chuyển động phải nằm trong ngân sách khung hình (< 16.7ms trên 60Hz, < 8.3ms trên 120Hz), tuyệt đối không dùng `transition: all`.
- Mọi animation phải hỗ trợ `@media (prefers-reduced-motion: reduce)`.
- Mọi logic xử lý state mới phải có kiểm thử tự động (Vitest) được viết và chạy thất bại (RED) trước khi viết mã triển khai (GREEN).

---

## Chi Tiết Các Tác Vụ Triển Khai

### Nhiệm Vụ 1: Optimistic UI & Sửa Lỗi Logic Cập Nhật State Trong Luồng Upload Tài Liệu

**Tệp tin:**
- Sửa đổi: `frontend/components/documents/DocumentList.tsx`
- Sửa đổi: `frontend/components/documents/UploadDocumentDialog.tsx`
- Sửa đổi: `frontend/components/documents/documents.css`
- Kiểm thử mới: `frontend/tests/documents-optimistic-upload.test.tsx`

**Giao diện & Chức năng:**
- Nhận diện trạng thái uploading: một đối tượng `DocumentResponse` tạm thời với `ingestion_status: "uploading"` và cờ `is_optimistic?: boolean`.
- Khi người dùng bấm nút Upload trong `UploadDocumentDialog`:
  - `onUpload` kích hoạt `upload()`: đóng ngay hộp thoại (`setUploadOpen(false)`), chèn dòng tài liệu lạc quan vào đầu danh sách `documents` với tên file, kích thước/định dạng và badge "Uploading...".
  - Gửi `POST /documents`.
  - Khi phản hồi trả về kết quả `result` (`IngestionResponse` hoặc `PdfSubmissionResponse`):
    - Tìm và cập nhật hoặc thay thế dòng lạc quan bằng bản ghi tài liệu chính thức với `document_id`, `status`, `ingestion_job_id`.
    - **Sửa lỗi logic:** Nếu `previous` không có `result.document_id`, ta chèn bản ghi mới vào mảng `previous` thay vì chỉ chạy `map` trả về mảng cũ.
    - **Bỏ request GET kép:** Không gọi `await load(controller)` sau khi `POST` thành công.
    - Kích hoạt polling tiến trình nền nếu có `ingestion_job_id`.
  - Nếu upload thất bại: xóa dòng lạc quan và hiển thị banner lỗi rõ ràng để người dùng có thể thử lại.

- [ ] **Bước 1.1: Viết test thất bại (RED) cho Optimistic Upload**
  Tạo `frontend/tests/documents-optimistic-upload.test.tsx`:
  - Kiểm tra rằng khi bấm nút Upload một tệp mới, dòng tài liệu lạc quan lập tức xuất hiện trên bảng (ngay trước khi request POST giải quyết).
  - Kiểm tra rằng khi request `POST` thành công, tài liệu mới được chèn vào danh sách mà không cần gọi thêm request `GET /documents`.
  - Chạy: `npx vitest run tests/documents-optimistic-upload.test.tsx` -> Xác nhận FAIL.

- [ ] **Bước 1.2: Triển khai cập nhật lạc quan và sửa logic mảng trong `DocumentList.tsx`**
  - Cập nhật hàm `upload()`:
    - Sinh `tempId = "optimistic-" + crypto.randomUUID()`.
    - Đặt `setDocuments(prev => [optimisticDoc, ...prev])`.
    - Đóng dialog `setUploadOpen(false)`.
    - Khi có `result`: thay thế `tempId` bằng `result.document_id` và các trường từ `result`.
    - Loại bỏ lệnh `await load(controller)` ở cuối nhánh thành công.
  - Cập nhật hàm render dòng tài liệu để hiển thị huy hiệu "Uploading..." kèm spinner nhẹ khi `ingestion_status === "uploading"`.

- [ ] **Bước 1.3: Chạy lại test và xác nhận đạt (GREEN)**
  Chạy: `npx vitest run tests/documents-optimistic-upload.test.tsx` -> Xác nhận PASS.
  Chạy lại: `npx vitest run tests/documents-management.test.tsx` -> Xác nhận không hồi quy.

---

### Nhiệm Vụ 2: Optimistic UI Cho Luồng Archive / Restore & Bỏ Chuyển Trang Cưỡng Ép

**Tệp tin:**
- Sửa đổi: `frontend/components/documents/DocumentList.tsx:679-763`
- Kiểm thử: `frontend/tests/documents-optimistic-archive.test.tsx`

**Giao diện & Chức năng:**
- Trong `archive(document)`:
  - Khi người dùng chọn "Archive document":
    - Ngay lập tức cập nhật lạc quan trong state: đổi `archived: true` cho tài liệu đó. Dòng tài liệu sẽ mờ đi hoặc ẩn đi (nếu checkbox "Show archived" tắt).
    - Gửi request `POST .../archive`.
    - Khi thành công: giữ nguyên state, **bỏ lệnh `await load(controller)`**.
    - Nếu thất bại (hoặc 409): hoàn tác lại trạng thái cũ (`archived: false`) và báo lỗi.
  - Khi người dùng chọn "Restore document" (từ menu 3 chấm hoặc nút Restore):
    - Ngay lập tức cập nhật lạc quan `archived: false`.
    - Gửi request `POST .../unarchive`.
    - Khi thành công: **LOẠI BỎ hoàn toàn `router.push(routes.document(...))`**! Người dùng ở lại danh sách, dòng tài liệu chuyển trạng thái hoạt động ngay tại chỗ. Bỏ lệnh `await load(controller)`.
    - Nếu thất bại: hoàn tác lại `archived: true` và báo lỗi.

- [ ] **Bước 2.1: Viết test thất bại (RED) cho Archive/Restore Optimistic**
  Tạo `frontend/tests/documents-optimistic-archive.test.tsx`:
  - Kiểm tra trạng thái `archived` thay đổi ngay tức thì khi bấm Archive mà không chờ mạng.
  - Kiểm tra khi bấm Restore từ menu, router KHÔNG bị gọi `router.push` sang trang chi tiết, tài liệu được phục hồi trực tiếp trong danh sách.
  - Chạy: `npx vitest run tests/documents-optimistic-archive.test.tsx` -> Xác nhận FAIL.

- [ ] **Bước 2.2: Triển khai cập nhật lạc quan trong `archive` và `restoreArchivedDocument`**
  - Chỉnh sửa `DocumentList.tsx`:
    - Thêm cập nhật lạc quan trước khi gọi `browserRequest`.
    - Xóa `router.push(...)` ở dòng 704.
    - Xóa `await load(controller)` thừa sau khi thao tác thành công.
    - Thêm cơ chế rollback khi request gặp lỗi.

- [ ] **Bước 2.3: Chạy lại test và xác nhận đạt (GREEN)**
  Chạy: `npx vitest run tests/documents-optimistic-archive.test.tsx` -> Xác nhận PASS.

---

### Nhiệm Vụ 3: Khắc Phục Bão Tính Toán Kiểu Dáng Khi Kéo Dải Phân Cách (Divider)

**Tệp tin:**
- Sửa đổi: `frontend/components/conversations/ConversationPanels.tsx:101-105, 150-250`
- Sửa đổi: `frontend/components/conversations/conversations.css`
- Kiểm thử: `frontend/tests/conversation-panels-divider.test.tsx`

**Giao diện & Chức năng:**
- Phân tách luồng kéo chuột:
  - Khi `onPointerDown`:
    - Lưu vị trí bắt đầu `drag.current = { panel, x, width, pointer }`.
    - Đặt thuộc tính `data-resizing="true"` lên container để tắt mọi transition trong lúc kéo.
  - Khi `onPointerMove`:
    - Tính toán độ dịch chuyển `deltaX`.
    - Sử dụng `requestAnimationFrame` để ghi trực tiếp biến CSS `--rail-width` hoặc `--inspector-width` lên `root.current.style.setProperty(...)`.
    - **TUYỆT ĐỐI KHÔNG** gọi `setStored` (không kích hoạt React re-render).
    - **TUYỆT ĐỐI KHÔNG** gọi `writePanelPreferences` (không ghi `localStorage` đồng bộ trên mỗi pixel).
  - Khi `onPointerUp` / `onPointerCancel`:
    - Xóa thuộc tính `data-resizing`.
    - Đọc kích thước cuối cùng vừa kéo, gọi `update({ railWidth: finalWidth })` hoặc `{ inspectorWidth: finalWidth }` một lần duy nhất để lưu React state và `localStorage`.

- [ ] **Bước 3.1: Viết test xác minh hành vi phân tách State & rAF của Divider**
  Tạo `frontend/tests/conversation-panels-divider.test.tsx`:
  - Mô phỏng chuỗi sự kiện `pointerdown` -> nhiều `pointermove` -> `pointerup`.
  - Xác nhận rằng trong lúc `pointermove`, `writePanelPreferences` không bị gọi liên tục ở mỗi nhịp di chuột, mà chỉ được gọi 1 lần khi `pointerup`.
  - Chạy: `npx vitest run tests/conversation-panels-divider.test.tsx` -> Xác nhận FAIL.

- [ ] **Bước 3.2: Triển khai rAF và tách React re-render trong `ConversationPanels.tsx`**
  - Sử dụng `useRef` lưu `pendingWidth` và `rafId`.
  - Cập nhật trực tiếp style inline của `root.current` trong frame `requestAnimationFrame`.
  - Xử lý debounce/commit tại `onPointerUp`.

- [ ] **Bước 3.3: Chạy lại test và xác nhận đạt (GREEN)**
  Chạy: `npx vitest run tests/conversation-panels-divider.test.tsx` -> Xác nhận PASS.
  Chạy lại: `npx vitest run tests/conversation-panels.test.tsx` -> PASS.

---

### Nhiệm Vụ 4: Khắc Phục Forced Synchronous Reflow Trên Ô Soạn Thảo (Composer)

**Tệp tin:**
- Sửa đổi: `frontend/components/conversations/ConversationComposer.tsx:148-154`
- Sửa đổi: `frontend/components/conversations/conversations.css`
- Kiểm thử: `frontend/tests/conversation-composer-height.test.tsx`

**Giao diện & Chức năng:**
- Loại bỏ chuỗi thao tác độc hại `input.current.style.height = "0px"` rồi đọc ngay `scrollHeight`.
- Thêm thuộc tính CSS hiện đại `field-sizing: content` cho textarea của ô soạn thảo với `min-height: 44px; max-height: 160px; resize: none;`.
- Đối với các trình duyệt chưa hỗ trợ `field-sizing`:
  - Trong `useEffect([draft])`, chỉ đo `scrollHeight` khi nội dung thay đổi số dòng hoặc bọc cập nhật trong `requestAnimationFrame`, không ép hạ chiều cao về `0px` gây sập bố cục rồi tính lại đồng bộ.

- [ ] **Bước 4.1: Viết test cho hành vi tự co giãn của Composer không gây reflow 0px**
  Tạo `frontend/tests/conversation-composer-height.test.tsx`.
  - Kiểm tra textarea tự động điều chỉnh chiều cao theo nội dung trong khoảng 44px đến 160px.
  - Kiểm tra `style.height` không bị gán về `0px` trước khi tính toán.
  - Chạy test -> Xác nhận FAIL hoặc xác nhận hành vi.

- [ ] **Bước 4.2: Triển khai tối ưu chiều cao trong `ConversationComposer.tsx` và `conversations.css`**
  - Cập nhật CSS với `field-sizing: content;`.
  - Viết lại hàm tự co giãn an toàn không hạ chiều cao sập DOM.

- [ ] **Bước 4.3: Chạy lại test và xác nhận đạt (GREEN)**
  Chạy: `npx vitest run tests/conversation-composer-height.test.tsx` -> Xác nhận PASS.
  Chạy lại: `npx vitest run tests/conversation-view.test.tsx` -> PASS.

---

### Nhiệm Vụ 5: Memoize Cây Markdown AST Khi Bấm Citation (AnswerContent)

**Tệp tin:**
- Sửa đổi: `frontend/components/conversations/AnswerContent.tsx:38-124`
- Kiểm thử: `frontend/tests/answer-citation-memo.test.tsx`

**Giao diện & Chức năng:**
- Tách việc tạo plugin `citationNodes` ra ngoài thân component hoặc memoize bằng `useMemo` với các dependency cố định (`markdown`, `citations.length`).
- Cô lập việc highlight `CitationChip` được chọn (`selectedIndex === index`) khỏi pipeline phân tích Markdown.
- Ghi nhớ (memoize) kết quả render của phần thân Markdown, bảo đảm khi `selectedIndex` thay đổi (người dùng bấm qua lại giữa các trích dẫn `[1]`, `[2]`), AST không bị `unified` phân tích lại từ đầu trên luồng chính.

- [ ] **Bước 5.1: Viết test xác nhận Markdown AST không bị parse lại khi đổi selected citation**
  Tạo `frontend/tests/answer-citation-memo.test.tsx`.
  - Kiểm tra khi render `AnswerContent` và thay đổi `selectedIndex`, các node văn bản không bị re-mount hoặc plugin rehype không bị khởi tạo lại.
  - Chạy test -> Xác nhận FAIL.

- [ ] **Bước 5.2: Triển khai memoization trong `AnswerContent.tsx`**
  - Tách hoặc memoize plugin `rehypePlugins`.
  - Dùng `React.memo` cho phần Markdown body hoặc tách `CitationChip` context / component để việc chuyển đổi selection chỉ kích hoạt re-render cục bộ tại các thẻ chip trích dẫn.

- [ ] **Bước 5.3: Chạy lại test và xác nhận đạt (GREEN)**
  Chạy: `npx vitest run tests/answer-citation-memo.test.tsx` -> Xác nhận PASS.
  Chạy lại: `npx vitest run tests/answer-rendering.test.tsx` -> PASS.

---

### Nhiệm Vụ 6: Bổ Sung Exit Transitions Cho Dialog & Drawer Theo Chuẩn /emil-design-eng

**Tệp tin:**
- Sửa đổi: `frontend/components/ui/Dialog.tsx`
- Sửa đổi: `frontend/styles/controls.css`
- Sửa đổi: `frontend/components/conversations/conversations.css`
- Kiểm thử: `frontend/tests/dialog-exit-transition.test.tsx`

**Giao diện & Chức năng:**
- Thêm máy trạng thái mở/đóng (`mounted`, `isClosing`) vào `Dialog`:
  - Khi `open` chuyển từ `true` sang `false`:
    - Không unmount ngay lập tức!
    - Đặt `isClosing = true`, gán thuộc tính `data-closing="true"` lên `<dialog>` và `kn-dialog__content`.
    - Chạy animation đóng:
      - Dialog thông thường: `kn-dialog-exit` (140ms, `cubic-bezier(0.23, 1, 0.32, 1)`, translateY(6px), opacity 0).
      - Drawer di động: `kn-rail-drawer-exit` (140ms, `cubic-bezier(0.23, 1, 0.32, 1)`, translateX(-12px), opacity 0).
      - Evidence sheet di động: `kn-evidence-sheet-exit` (140ms, translateY(12px), opacity 0).
    - Sau khi hoàn thành thời lượng animation (140ms) hoặc nhận sự kiện `animationend`: hoàn tất đóng, gọi `dialog.close()` và unmount.
  - Hỗ trợ đầy đủ `@media (prefers-reduced-motion: reduce)`: chuyển thời lượng về 0ms để unmount ngay, không gây chóng mặt cho người dùng nhạy cảm với chuyển động.

- [ ] **Bước 6.1: Viết test xác nhận Dialog duy trì trong DOM trong suốt quá trình chạy exit animation**
  Tạo `frontend/tests/dialog-exit-transition.test.tsx`:
  - Render Dialog với `open = true`.
  - Đổi prop `open = false`.
  - Kiểm tra Dialog vẫn còn trong DOM với thuộc tính `data-closing="true"`.
  - Chờ hết thời gian transition -> Kiểm tra Dialog đã unmount hoàn toàn.
  - Chạy test -> Xác nhận FAIL.

- [ ] **Bước 6.2: Triển khai Exit state machine trong `Dialog.tsx` và thêm CSS keyframes**
  - Chỉnh sửa `Dialog.tsx` với state `isRendered` và `isExiting`.
  - Thêm `@keyframes kn-dialog-exit`, `@keyframes kn-rail-drawer-exit`, `@keyframes kn-evidence-sheet-exit` trong `controls.css` và `conversations.css`.
  - Khai báo biến thời lượng `--duration-dialog-exit: 140ms` và easing `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`.

- [ ] **Bước 6.3: Chạy lại test và xác nhận đạt (GREEN)**
  Chạy: `npx vitest run tests/dialog-exit-transition.test.tsx` -> Xác nhận PASS.
  Chạy lại: `npx vitest run tests/dialog-menu.test.tsx` -> PASS.

---

### Nhiệm Vụ 7: Kiểm Thử Tích Hợp Toàn Bộ, Kiểm Tra Định Dạng & Đo Đạc Bằng Chứng Trước / Sau

**Tệp tin:**
- Toàn bộ các file đã chỉnh sửa.
- Báo cáo kiểm chứng: `docs/plans/2026-11-17-ux-interaction-jank-verification-report.md`.

**Các bước thực hiện:**
- [ ] **Bước 7.1: Chạy toàn bộ test suite frontend**
  - Chạy: `npx vitest run` trên thư mục `frontend/`.
  - Đảm bảo tất cả 68+ test suites đều PASS.
- [ ] **Bước 7.2: Kiểm tra định dạng và OpenAPI**
  - Chạy: `npm --prefix frontend run format:check`
  - Chạy: `python -m ruff format --check .` và `python -m ruff check .`
  - Chạy: `python scripts/export_openapi.py --check`
- [ ] **Bước 7.3: Đo đạc và thu thập bằng chứng Chrome DevTools thực tế**
  - Mở ứng dụng trên trình duyệt qua Chrome DevTools.
  - Đo thời gian phản hồi Upload & Archive (Performance Timestamps).
  - Đo FPS khi kéo dải phân cách (Performance trace: xác nhận 60 FPS, 0 Long Tasks).
  - Đo INP khi gõ trên Composer (Interaction to Next Paint < 16ms).
  - Ghi nhận chỉ số định lượng vào bảng Trước / Sau và lập báo cáo hoàn tất.
