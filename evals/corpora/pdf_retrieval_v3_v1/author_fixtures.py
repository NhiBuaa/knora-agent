"""Offline authoring recipe. Run with bundled reportlab/Pillow, never backend dependencies.

Gold below is authored from these fixture literals and visually checked paper facts,
not from parser output. Academic originals are downloaded separately, never rewritten.
"""

import hashlib
import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
EVALS = HERE.parents[1]
FONT = Path("C:/Windows/Fonts/arial.ttf")
BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
CC = "https://creativecommons.org/licenses/by/4.0/"
PROJECT = "https://github.com/NhiBuaa/knora-agent"
EXPOSURE = "agent-authored; no model calls; owner review pending"
anchors = []
sources = []
cases = []

# Stable anchor key, source-visible text. Prefix identifies its authored document.
TEXT = {
    "r1": "Mã A-17 tra cứu hồ sơ QD-42.",
    "r2": "Mã B-08 tra cứu hồ sơ TB-19.",
    "r3": "Mã C-31 tra cứu hồ sơ SC-07.",
    "r4": "Mã D-12 tra cứu hồ sơ COL-58.",
    "r5": "Mã E-24 tra cứu hồ sơ QD-63.",
    "r6": "Mã F-09 tra cứu hồ sơ TB-27.",
    "g1": "Phiếu hỗ trợ chuẩn phải được xác nhận trong 24 giờ.",
    "g2": "Phiếu hỗ trợ khẩn phải được xác nhận trong 2 giờ.",
    "g3": "Giờ xác nhận không phải thời gian giải quyết hoàn tất.",
    "g4": "Hạn xác nhận được tính theo giờ liên tục, kể cả cuối tuần.",
    "g5": "Không thu phí xác nhận phiếu hỗ trợ.",
    "g6": "Không thu phí xác nhận phiếu hỗ trợ.",
    "h11": "QD-42: mức bồi hoàn tối đa là 350.000 đồng.",
    "h12": "1. Phạm vi: áp dụng cho đơn hàng nội địa.",
    "h13": "1.1. Đơn chuẩn: được đổi trong 48 giờ sau khi nhận.",
    "h14": "1.2. Đơn vùng xa: được đổi trong 72 giờ sau khi nhận.",
    "h15": "1.2.1. Ngoại lệ: không nhận đổi hàng đã mở niêm phong.",
    "h16": "2. Hoàn tiền: xử lý trong 5 ngày làm việc.",
    "h21": "QD-63: thời hạn lưu bản sao là 90 ngày.",
    "h22": "1. Quyền truy cập: người đọc chỉ được xem tài liệu.",
    "h23": "1.1. Biên tập viên: được sửa bản nháp, không được công bố.",
    "h24": "1.2. Chủ sở hữu: được công bố bản đã duyệt.",
    "h25": "2. Lưu trữ: bản nháp thường được giữ 30 ngày.",
    "h26": "2.1. Hồ sơ tranh chấp được giữ 90 ngày, thay cho 30 ngày.",
    "h31": "1. Cảnh báo P1: phải báo trực trong 15 phút.",
    "h32": "1.1. Cảnh báo P2: phải báo trực trong 60 phút.",
    "h33": "1.1.1. Không hạ P1 xuống P2 chỉ vì ngoài giờ.",
    "h34": "2. Người trực phải xác nhận đã nhận cảnh báo.",
    "h35": "2.1. Khi chưa có xác nhận, gọi lại sau 5 phút.",
    "h36": "2.2. Không gửi nội dung khách hàng qua kênh công khai.",
    "c11": "COL-58: tổng hạn mức là 42 lượt.",
    "c12": "Hạn mức đầu kỳ cấp 14 lượt.",
    "c13": "Hạn mức chuyển kỳ tối đa 28 lượt.",
    "c14": "Không cộng dồn lượt đã hết hạn.",
    "c15": "Lượt chuyển kỳ được dùng trước lượt đầu kỳ.",
    "c16": "Hạn mức được kiểm tra lúc 09:00 mỗi thứ Hai.",
    "c21": "Evidence nghĩa là bằng chứng nguồn, không phải câu trả lời.",
    "c22": "Citation nghĩa là trích dẫn chỉ đến bằng chứng nguồn.",
    "c23": "Refusal nghĩa là từ chối trả lời khi thiếu bằng chứng.",
    "c24": "Answer means a response supported by source evidence.",
    "c25": "A citation does not replace the required answer facts.",
    "c26": "A refusal must not invent a missing source fact.",
    "t11": "TB-19",
    "t12": "12",
    "t13": "18",
    "t14": "30",
    "t15": "TB-20",
    "t16": "7",
    "t17": "9",
    "t18": "16",
    "t21": "TB-27",
    "t22": "45",
    "t23": "15",
    "t24": "60",
    "t25": "TB-28",
    "t26": "20",
    "t27": "10",
    "t28": "30",
    "t31": "KT-09",
    "t32": "2,5",
    "t33": "4,0",
    "t34": "6,5",
    "t35": "KT-10",
    "t36": "1,5",
    "t37": "2,0",
    "t38": "3,5",
    "s11": "SC-07: phí lưu kho là 27.000 đồng mỗi ngày.",
    "s12": "Kho ảnh mở từ 08:30 đến 17:30.",
    "s13": "Kho ảnh không nhận hàng vào Chủ nhật.",
    "s14": "Người nhận phải xuất trình mã nhận hàng.",
    "s21": "MX-11: hồ sơ đã kiểm có 23 trang.",
    "s22": "Trong hồ sơ có 5 trang phụ lục ảnh.",
    "s23": "Bản số hóa không thay thế bản gốc có chữ ký.",
    "s24": "Ngày kiểm tra hồ sơ là 14/10/2026.",
    "s31": "RX-03: thiết bị đo có sai số tối đa 0,2 độ C.",
    "s32": "Kiểm chuẩn thiết bị mỗi 6 tháng.",
    "s33": "Không dùng thiết bị khi tem kiểm chuẩn đã hết hạn.",
    "s34": "Nhiệt độ bảo quản từ 15 đến 25 độ C.",
}


def anchor(key, source, page, text, region):
    anchors.append(dict(id=key, source_id=source, page=page, text=text, region=region))


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def source_record(source_id, category, pages, title, url=None, attribution=None):
    path = HERE / f"{source_id}.pdf"
    sources.append(
        dict(
            id=source_id,
            path=f"corpora/pdf_retrieval_v3_v1/{path.name}",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            page_count=pages,
            category=category,
            kind="real" if category == "academic" else "synthetic",
            license="CC-BY-4.0",
            source_url=url or PROJECT,
            license_url="https://aclanthology.org/faq/copyright/" if url else CC,
            title=title,
            attribution=attribution or "Knora evaluation fixture; agent-authored, 2026",
            acquired_at="2026-10-14",
            exposure=EXPOSURE,
        )
    )


def line(c, text, x, y, width=500, size=11, bold=False):
    font = "FixtureBold" if bold else "Fixture"
    c.setFont(font, size)
    words = text.split()
    current = ""
    lines = []
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and pdfmetrics.stringWidth(candidate, font, size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    lines.append(current)
    for number, item in enumerate(lines):
        c.drawString(x, y - number * (size + 6), item)
    return y - len(lines) * (size + 6)


def page_header(c, title, page):
    c.setFillColorRGB(0.1, 0.18, 0.3)
    line(c, title, 45, 792, size=18, bold=True)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    line(c, "SYNTHETIC FIXTURE - agent-authored - owner review pending", 45, 760, size=9)
    c.setLineWidth(0.7)
    c.line(45, 744, 550, 744)
    line(c, f"PDF page {page} | CC BY 4.0 | Knora evaluation fixture", 45, 35, size=8)


def prose(source_id, title, category, key_pages, columns=False):
    c = canvas.Canvas(str(HERE / f"{source_id}.pdf"), pagesize=(595, 842), invariant=1)
    c.setTitle(title)
    for page, keys in enumerate(key_pages, 1):
        page_header(c, title, page)
        if columns:
            c.line(297, 150, 297, 720)
        half = (len(keys) + 1) // 2
        for column, selected in enumerate((keys[:half], keys[half:]) if columns else (keys,)):
            y = 706
            x = 45 + column * 270
            for key in selected:
                heading = category == "hierarchy"
                indent = 16 * min(TEXT[key].split(" ")[0].count(".") - 1, 2) if heading else 0
                indent = max(indent, 0)
                start = y
                y = line(
                    c,
                    TEXT[key],
                    x + indent,
                    y,
                    width=228 - indent if columns else 490 - indent,
                    size=12 if heading else 11,
                    bold=heading,
                )
                anchor(
                    key,
                    source_id,
                    page,
                    TEXT[key],
                    f"{'left' if column == 0 else 'right'} column; x={x + indent}, y={start} "
                    f"PDF points from bottom; heading path {TEXT[key].split(':')[0]}"
                    if heading
                    else f"{'left' if column == 0 else 'right'} text block; "
                    f"x={x}, y={start} PDF points from bottom",
                )
                y -= 35
        c.showPage()
    c.save()
    source_record(source_id, category, len(key_pages), title)


def table(source_id, title, prefix, unit, headers):
    c = canvas.Canvas(str(HERE / f"{source_id}.pdf"), pagesize=(595, 842), invariant=1)
    page_header(c, title, 1)
    line(c, f"Đơn vị: {unit}. Không làm tròn số thập phân.", 45, 701)
    x = [45, 165, 285, 405, 550]
    c.setFillColorRGB(0.9, 0.94, 0.98)
    c.rect(45, 560, 505, 100, fill=1, stroke=0)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.rect(45, 440, 505, 220)
    # First/last headers span two rows, middle header spans two columns.
    c.line(x[1], 440, x[1], 660)
    c.line(x[3], 440, x[3], 660)
    c.line(x[2], 440, x[2], 610)
    c.line(x[1], 610, x[3], 610)
    for edge in (560, 500):
        c.line(45, edge, 550, edge)
    line(c, "Mã hồ sơ", 62, 602, width=100, bold=True)
    line(c, headers[0], 192, 638, width=195, bold=True)
    line(c, headers[1], 177, 584, width=100, bold=True)
    line(c, headers[2], 299, 584, width=100, bold=True)
    line(c, "Tổng", 454, 602, bold=True)
    for row in range(2):
        for col in range(4):
            key = f"{prefix}{row * 4 + col + 1}"
            c.setFont("Fixture", 13)
            c.drawString(x[col] + 15, 527 - row * 60, TEXT[key])
            anchor(
                key,
                source_id,
                1,
                TEXT[key],
                f"merged-header table; row {row + 1}; "
                f"column {['Mã hồ sơ', headers[1], headers[2], 'Tổng'][col]}; unit {unit}; "
                f"x={x[col] + 15}, y={527 - row * 60} PDF points from bottom",
            )
    line(c, "Tổng là tổng hai cột thành phần trong cùng một hàng.", 45, 406)
    c.showPage()
    c.save()
    source_record(source_id, "hard_table", 1, title)


def scan(source_id, title, keys, mixed=False, rotated=False):
    image = Image.new("RGB", (1500, 1700), "#f4f1e8")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), 32)
    bold = ImageFont.truetype(str(BOLD), 42)
    draw.text((70, 90), "BẢN ẢNH - SYNTHETIC FIXTURE", font=bold, fill="#202020")
    draw.rectangle((55, 190, 1445, 1350), outline="#555555", width=3)
    y = 270
    for key in keys:
        words = TEXT[key].split()
        text = ""
        lines = []
        for word in words:
            candidate = f"{text} {word}".strip()
            if text and draw.textlength(candidate, font=font) > 1300:
                lines.append(text)
                text = word
            else:
                text = candidate
        lines.append(text)
        start = y
        for text in lines:
            draw.text((95, y), text, font=font, fill="#171717")
            y += 55
        anchor(
            key,
            source_id,
            1,
            TEXT[key],
            f"raster-only evidence block; image x=95,y={start} pixels from top; "
            "embedded image occupies PDF x=45..550,y=110..700",
        )
        y += 100
    draw.text((95, 1450), "Owner review pending | CC BY 4.0", font=font, fill="#777777")
    if rotated:
        image = image.convert("L").rotate(0.6, resample=Image.Resampling.BICUBIC, fillcolor=245)
    data = BytesIO()
    image.save(data, format="PNG")
    c = canvas.Canvas(str(HERE / f"{source_id}.pdf"), pagesize=(595, 842), invariant=1)
    if mixed:
        page_header(c, title, 1)
    c.drawImage(ImageReader(data), 45, 110, width=505, height=590)
    c.showPage()
    c.save()
    source_record(source_id, "scan_mixed", 1, title)


def case(category, question, reference, facts, groups, language="vi", parent=None, scope=None):
    cases.append(
        dict(
            id=f"pdf-v3-{len(cases) + 1:03}",
            category=category,
            language=language,
            question=question,
            expected_behavior="REFUSAL" if scope else "ANSWER",
            reference_answer=reference,
            required_facts=facts,
            evidence_groups=[[key] if isinstance(key, str) else key for key in groups],
            parent_case_id=parent,
            no_answer_scope=scope,
            exposure=EXPOSURE,
        )
    )


def author_gold():
    case(
        "simple",
        "Phiếu hỗ trợ chuẩn phải được xác nhận trong bao lâu?",
        "Trong 24 giờ.",
        ["24 giờ"],
        ["g1"],
    )
    case(
        "simple",
        "Đơn chuẩn nội địa được đổi trong bao lâu và phạm vi nào?",
        "Trong 48 giờ sau khi nhận; áp dụng đơn nội địa.",
        ["48 giờ sau khi nhận", "đơn hàng nội địa"],
        ["h12", "h13"],
    )
    case("simple", "Ai được công bố bản đã duyệt?", "Chủ sở hữu.", ["chủ sở hữu"], ["h24"])
    case(
        "simple",
        "Cảnh báo P1 phải báo trực trong bao nhiêu phút?",
        "15 phút.",
        ["15 phút"],
        ["h31"],
    )
    case("simple", "Hạn mức đầu kỳ được cấp bao nhiêu lượt?", "14 lượt.", ["14 lượt"], ["c12"])
    case("simple", "Kho ảnh mở cửa lúc nào?", "Từ 08:30 đến 17:30.", ["08:30", "17:30"], ["s12"])
    case(
        "simple",
        "Hồ sơ MX-11 có bao nhiêu trang và được kiểm ngày nào?",
        "23 trang; ngày 14/10/2026.",
        ["23 trang", "14/10/2026"],
        ["s21", "s24"],
    )
    case("simple", "RX-03 có sai số tối đa bao nhiêu?", "0,2 độ C.", ["0,2 độ C"], ["s31"])
    case(
        "comparison",
        "So sánh hạn xác nhận phiếu chuẩn và khẩn; có phải hạn giải quyết hoàn tất không?",
        "Chuẩn 24 giờ; khẩn 2 giờ. Đây không phải hạn giải quyết hoàn tất.",
        ["chuẩn 24 giờ", "khẩn 2 giờ", "không phải thời gian giải quyết hoàn tất"],
        ["g1", "g2", "g3"],
    )
    case(
        "comparison",
        "Đơn chuẩn và vùng xa khác hạn đổi thế nào; đơn vùng xa đã mở niêm phong có ngoại lệ gì?",
        "Chuẩn 48 giờ sau khi nhận; vùng xa 72 giờ sau khi nhận; "
        "không nhận đổi hàng vùng xa đã mở niêm phong.",
        [
            "chuẩn 48 giờ sau khi nhận",
            "vùng xa 72 giờ sau khi nhận",
            "không nhận đổi hàng vùng xa đã mở niêm phong",
        ],
        ["h13", "h14", "h15"],
    )
    case(
        "comparison",
        "Biên tập viên và người đọc khác quyền gì?",
        "Người đọc chỉ xem; biên tập viên sửa bản nháp nhưng không công bố.",
        ["người đọc chỉ xem", "biên tập viên sửa bản nháp", "không được công bố"],
        ["h22", "h23"],
    )
    case(
        "comparison",
        "Bản nháp thường và hồ sơ tranh chấp được giữ bao lâu?",
        "Bản nháp thường 30 ngày; hồ sơ tranh chấp 90 ngày thay cho 30 ngày.",
        ["30 ngày", "90 ngày thay cho 30 ngày"],
        ["h25", "h26"],
    )
    case(
        "comparison",
        "So sánh hạn báo trực P1 và P2; ngoài giờ có được hạ P1 không?",
        "P1 15 phút; P2 60 phút; không hạ P1 chỉ vì ngoài giờ.",
        ["P1 15 phút", "P2 60 phút", "không hạ P1 chỉ vì ngoài giờ"],
        ["h31", "h32", "h33"],
    )
    case(
        "comparison",
        "Compare evidence and citation in the bilingual glossary.",
        "Evidence is source evidence, not the answer; a citation points to source evidence.",
        ["evidence is source evidence, not an answer", "citation points to source evidence"],
        ["c21", "c22"],
        "en",
    )
    case(
        "comparison",
        "Refusal khác Answer thế nào, có được bịa fact thiếu không?",
        "Refusal là từ chối khi thiếu bằng chứng; Answer có bằng chứng nguồn. "
        "Refusal không được bịa fact thiếu.",
        [
            "từ chối khi thiếu bằng chứng",
            "answer supported by source evidence",
            "must not invent a missing fact",
        ],
        ["c23", "c24", "c26"],
        "mixed",
    )
    case(
        "comparison",
        "PhoBERT và ViT5 được mô tả với loại mô hình nào và ViT5 benchmark mấy tác vụ?",
        "PhoBERT là mô hình ngôn ngữ đơn ngữ cho tiếng Việt; "
        "ViT5 là encoder-decoder cho tiếng Việt, benchmark hai tác vụ.",
        [
            "PhoBERT monolingual Vietnamese",
            "ViT5 encoder-decoder Vietnamese",
            "two downstream tasks",
        ],
        ["pb1", "v51", "v52"],
        "mixed",
    )
    case(
        "comparison",
        "PhoNLP nêu ba tác vụ nào; ViT5 nêu hai tác vụ nào?",
        "PhoNLP: POS tagging, NER, dependency parsing. ViT5: abstractive text summarization, NER.",
        ["PhoNLP POS tagging, NER, dependency parsing", "ViT5 abstractive summarization and NER"],
        ["pn1", "v52", "v53"],
        "mixed",
    )
    case(
        "comparison",
        "Compare the TB-19 and TB-20 totals, preserving each row identifier, "
        "and state the difference in orders.",
        "TB-19 totals 30 orders; TB-20 totals 16 orders; TB-19 is larger by 14 orders.",
        ["TB-19 30 orders", "TB-20 16 orders", "difference 14 orders"],
        ["t11", "t14", "t15", "t18"],
        "en",
    )
    case(
        "table_hierarchy",
        "Bảng TB-19 chia số đơn đã xử lý và còn chờ thế nào, tổng bao nhiêu?",
        "TB-19: đã xử lý 12, còn chờ 18, tổng 30 đơn.",
        ["TB-19", "đã xử lý 12", "còn chờ 18", "tổng 30 đơn"],
        ["t11", "t12", "t13", "t14"],
    )
    case(
        "table_hierarchy",
        "Hàng TB-20 có bao nhiêu đơn đã xử lý và còn chờ?",
        "TB-20: đã xử lý 7; còn chờ 9.",
        ["TB-20", "đã xử lý 7", "còn chờ 9"],
        ["t15", "t16", "t17"],
    )
    case(
        "table_hierarchy",
        "TB-27 có phút trực tuyến, phút tại chỗ và tổng thế nào?",
        "TB-27: trực tuyến 45 phút, tại chỗ 15 phút, tổng 60 phút.",
        ["TB-27", "trực tuyến 45 phút", "tại chỗ 15 phút", "tổng 60 phút"],
        ["t21", "t22", "t23", "t24"],
    )
    case(
        "table_hierarchy",
        "TB-28 có phút trực tuyến, phút tại chỗ và tổng thế nào?",
        "TB-28: trực tuyến 20 phút, tại chỗ 10 phút, tổng 30 phút.",
        ["TB-28", "trực tuyến 20 phút", "tại chỗ 10 phút", "tổng 30 phút"],
        ["t25", "t26", "t27", "t28"],
    )
    case(
        "table_hierarchy",
        "Đọc hàng KT-09 theo đúng đơn vị: sáng, chiều và tổng?",
        "KT-09: sáng 2,5 kg; chiều 4,0 kg; tổng 6,5 kg.",
        ["KT-09", "sáng 2,5 kg", "chiều 4,0 kg", "tổng 6,5 kg"],
        ["t31", "t32", "t33", "t34"],
    )
    case(
        "table_hierarchy",
        "Đọc hàng KT-10 theo đúng đơn vị: sáng, chiều và tổng?",
        "KT-10: sáng 1,5 kg; chiều 2,0 kg; tổng 3,5 kg.",
        ["KT-10", "sáng 1,5 kg", "chiều 2,0 kg", "tổng 3,5 kg"],
        ["t35", "t36", "t37", "t38"],
    )
    case(
        "table_hierarchy",
        "Theo mục 2 và 2.1 cảnh báo, người trực cần làm gì và khi nào gọi lại?",
        "Phải xác nhận nhận cảnh báo; chưa có xác nhận thì gọi lại sau 5 phút.",
        ["xác nhận đã nhận cảnh báo", "gọi lại sau 5 phút khi chưa xác nhận"],
        ["h34", "h35"],
    )
    case(
        "table_hierarchy",
        "Quy tắc 2.2 có cho gửi nội dung khách hàng ra kênh công khai không?",
        "Không được gửi nội dung khách hàng qua kênh công khai.",
        ["không gửi nội dung khách hàng qua kênh công khai"],
        ["h36"],
    )
    case(
        "table_hierarchy",
        "Theo hai cột hạn mức, lượt nào dùng trước và lượt hết hạn xử lý thế nào?",
        "Dùng lượt chuyển kỳ trước lượt đầu kỳ; không cộng dồn lượt đã hết hạn.",
        ["chuyển kỳ dùng trước đầu kỳ", "không cộng dồn lượt hết hạn"],
        ["c14", "c15"],
    )
    case(
        "table_hierarchy",
        "Trong bản ảnh MX-11, bao nhiêu trang phụ lục ảnh và bản số hóa có thay bản gốc không?",
        "5 trang phụ lục ảnh; bản số hóa không thay bản gốc có chữ ký.",
        ["5 trang phụ lục ảnh", "không thay bản gốc có chữ ký"],
        ["s22", "s23"],
    )
    follow = [
        (
            "Vậy hạn đó có tính cuối tuần và mất phí không?",
            "Tính giờ liên tục kể cả cuối tuần; không thu phí xác nhận.",
            ["tính giờ liên tục, kể cả cuối tuần", "không thu phí xác nhận"],
            ["g4", ["g5", "g6"]],
        ),
        (
            "Còn hoàn tiền cho loại đơn vừa hỏi mất bao lâu?",
            "5 ngày làm việc.",
            ["5 ngày làm việc"],
            ["h16"],
        ),
        (
            "Người đó có quyền công bố bản chưa duyệt được nêu không?",
            "Chỉ quyền công bố bản đã duyệt được nêu; "
            "không thể suy ra quyền công bố bản chưa duyệt.",
            [
                "quyền được nêu chỉ là công bố bản đã duyệt",
                "không thể suy ra quyền công bố bản chưa duyệt",
            ],
            ["h24"],
        ),
        (
            "Ngoài giờ thì có được đổi nó thành P2 không?",
            "Không hạ P1 xuống P2 chỉ vì ngoài giờ.",
            ["không hạ P1 xuống P2 chỉ vì ngoài giờ"],
            ["h33"],
        ),
        (
            "Còn phần chuyển kỳ tối đa bao nhiêu lượt và kiểm lúc nào?",
            "28 lượt; kiểm lúc 09:00 mỗi thứ Hai.",
            ["28 lượt", "09:00 mỗi thứ Hai"],
            ["c13", "c16"],
        ),
        (
            "Chủ nhật nơi đó có nhận hàng không và cần xuất trình gì?",
            "Không nhận hàng Chủ nhật; người nhận xuất trình mã nhận hàng.",
            ["không nhận hàng Chủ nhật", "mã nhận hàng"],
            ["s13", "s14"],
        ),
        (
            "Trong số trang vừa hỏi có bao nhiêu trang ảnh?",
            "5 trang phụ lục ảnh.",
            ["5 trang phụ lục ảnh"],
            ["s22"],
        ),
        (
            "Thiết bị đó kiểm chuẩn bao lâu một lần và khi tem kiểm chuẩn hết hạn "
            "có dùng được không?",
            "Mỗi 6 tháng; không dùng khi tem kiểm chuẩn hết hạn.",
            ["6 tháng", "không dùng khi tem hết hạn"],
            ["s32", "s33"],
        ),
    ]
    for number, (question, answer, facts, groups) in enumerate(follow, 1):
        case("follow_up", question, answer, facts, groups, parent=f"pdf-v3-{number:03}")
    case("typo_identifier", "phieu ho tro khan xac nhan may gio?", "2 giờ.", ["2 giờ"], ["g2"])
    case(
        "typo_identifier",
        "qd-42 boi hoan toi da bao nhieu dong?",
        "350.000 đồng.",
        ["350.000 đồng"],
        ["h11"],
    )
    case("typo_identifier", "QD-63 luu ban sao may ngay?", "90 ngày.", ["90 ngày"], ["h21"])
    case(
        "typo_identifier",
        "COL-58 tong han muc la 24 hay 42 luot?",
        "42 lượt, không phải 24.",
        ["42 lượt", "không phải 24"],
        ["c11"],
    )
    case(
        "typo_identifier",
        "SC-07 phi luu kho 1 ngay bao nhieu?",
        "27.000 đồng mỗi ngày.",
        ["27.000 đồng mỗi ngày"],
        ["s11"],
    )
    case(
        "typo_identifier",
        "RX-03 nhiet do bao quan tu may den may do C?",
        "15 đến 25 độ C.",
        ["15 đến 25 độ C"],
        ["s34"],
    )
    case(
        "typo_identifier",
        "Does a citaton replace the required answer facts?",
        "No, a citation does not replace the required answer facts.",
        ["citation does not replace required answer facts"],
        ["c25"],
        "en",
    )
    case(
        "typo_identifier",
        "Phobert co bao nhieu version, ten gi?",
        "Hai phiên bản: PhoBERT-base và PhoBERT-large.",
        ["hai phiên bản", "PhoBERT-base", "PhoBERT-large"],
        ["pb2"],
        "mixed",
    )
    case(
        "typo_identifier",
        "PhoNLP toolkit dung licnese gi theo abstract (khong hoi license PDF)?",
        "Apache License 2.0 cho toolkit.",
        ["toolkit Apache License 2.0"],
        ["pn2"],
        "mixed",
    )
    case(
        "typo_identifier",
        "vit5 pretrained tren subset ngon ngu nao cua CC100?",
        "Tập con đơn ngữ tiếng Việt của CC100.",
        ["Vietnamese monolingual subset of CC100"],
        ["v54"],
        "mixed",
    )
    hops = [
        ("A-17", "r1", "h11", "350.000 đồng", "mức bồi hoàn tối đa", "QD-42"),
        ("B-08", "r2", "t14", "30 đơn", "tổng số đơn", "TB-19"),
        ("C-31", "r3", "s11", "27.000 đồng mỗi ngày", "phí lưu kho", "SC-07"),
        ("D-12", "r4", "c11", "42 lượt", "tổng hạn mức", "COL-58"),
        ("E-24", "r5", "h21", "90 ngày", "thời hạn lưu bản sao", "QD-63"),
        ("F-09", "r6", "t24", "60 phút", "tổng thời lượng hỗ trợ", "TB-27"),
    ]
    for code, lookup, value, answer, field, target in hops:
        # The user gives only route code, never its second-document identifier.
        case(
            "multi_hop",
            f"Tra mã {code} trong sổ điều hướng rồi cho biết {field} của hồ sơ được trỏ tới.",
            f"{code} trỏ tới {target}; {field} là {answer}.",
            [f"{code} trỏ tới {target}", f"{field}: {answer}"],
            [lookup, *(["t11"] if value == "t14" else ["t21"] if value == "t24" else []), value],
        )
    absent = [
        (
            "Phiếu hỗ trợ chuẩn phải giải quyết hoàn tất trong bao lâu?",
            "Chỉ có hạn xác nhận; g3 phủ định việc đồng nhất với hạn giải quyết hoàn tất. "
            "Không có SLA hoàn tất.",
        ),
        (
            "Mã Z-99 trỏ tới hồ sơ nào?",
            "Sổ điều hướng chỉ có A-17/B-08/C-31/D-12/E-24/F-09; không có Z-99.",
        ),
        (
            "QD-42 quy định mức bồi hoàn cho đơn quốc tế bao nhiêu?",
            "QD-42 chỉ nêu phạm vi nội địa; không có mức cho đơn quốc tế.",
        ),
        (
            "PhoNLP báo cáo chi phí huấn luyện bằng USD bao nhiêu?",
            "Toàn bộ 7 trang PhoNLP không nêu chi phí huấn luyện USD; "
            "không suy đoán từ thiết bị hoặc thời gian.",
        ),
        (
            "ViT5 có chỉ số F1 trên bộ dữ liệu hư cấu KnoraMed-2099 bao nhiêu?",
            "KnoraMed-2099 không xuất hiện trong bất kỳ PDF nào; "
            "không dùng các bộ benchmark khác thay thế.",
        ),
        (
            "Kho ảnh SC-07 có số điện thoại liên hệ nào?",
            "Bản ảnh SC-07 có phí/giờ/ngày/mã nhận, không có số điện thoại; "
            "toàn corpus không bổ sung số này.",
        ),
        (
            "TB-19 có số liệu quý IV năm 2027 không?",
            "Bảng chỉ có hai hàng TB-19/TB-20 theo trạng thái; không có thời gian quý IV/2027.",
        ),
        (
            "What is the 2026 production accuracy of PhoBERT at Knora?",
            "The corpus contains a 2020 research paper, not a Knora production measurement "
            "in 2026; no such accuracy appears in the 16 PDFs.",
        ),
    ]
    for question, scope in absent:
        case(
            "no_answer",
            question,
            "Không đủ bằng chứng trong corpus để trả lời."
            if not question.startswith("What")
            else "The corpus does not provide enough evidence to answer.",
            [],
            [],
            "en" if question.startswith("What") else "vi",
            scope=scope,
        )


def academic():
    # Transcriptions of visible PDF regions inspected at page 1, not extracted gold.
    records = [
        (
            "academic-phobert",
            "PhoBERT: Pre-trained language models for Vietnamese",
            6,
            "2020.findings-emnlp.92",
            "Dat Quoc Nguyen and Anh Tuan Nguyen, Findings of EMNLP 2020, pp. 1037-1042",
            [
                (
                    "pb1",
                    "public large-scale monolingual language mod-\nels pre-trained for Vietnamese.",
                    "page 1; Abstract, left column, opening sentence",
                ),
                (
                    "pb2",
                    "We present PhoBERT with two versions—\nPhoBERTbase and PhoBERTlarge",
                    "page 1; Abstract opening; base/large are typographic subscripts "
                    "attached to PhoBERT; transcribed without adding a hyphen",
                ),
            ],
        ),
        (
            "academic-phonlp",
            "PhoNLP: A joint multi-task learning model for Vietnamese part-of-speech tagging, "
            "named entity recognition and dependency parsing",
            7,
            "2021.naacl-demos.1",
            "Linh The Nguyen and Dat Quoc Nguyen, NAACL-HLT 2021 Demonstrations, pp. 1-7",
            [
                (
                    "pn1",
                    "model—named PhoNLP—for joint Viet-\n"
                    "namese part-of-speech (POS) tagging, named\n"
                    "entity recognition (NER) and dependency\nparsing.",
                    "page 1; Abstract opening, left column; "
                    "joint Vietnamese POS tagging, NER and dependency parsing sentence",
                ),
                (
                    "pn2",
                    "Apache License 2.0.",
                    "page 1; Abstract, left column, toolkit release license sentence",
                ),
            ],
        ),
        (
            "academic-vit5",
            "ViT5: Pretrained Text-to-Text Transformer for Vietnamese Language Generation",
            7,
            "2022.naacl-srw.18",
            "Long Phan, Hieu Tran, Hieu Nguyen and Trieu H. Trinh, "
            "NAACL 2022 Student Research Workshop, pp. 136-142",
            [
                (
                    "v51",
                    "based encoder-decoder model for the Viet-\nnamese language.",
                    "page 1; Abstract opening, left column; "
                    "based continues hyphenated Transformer- from preceding line",
                ),
                (
                    "v52",
                    "two downstream text generation tasks",
                    "page 1; Abstract, left column, benchmark sentence",
                ),
                (
                    "v53",
                    "stractive Text Summarization and Named En-\ntity Recognition.",
                    "page 1; Abstract, left column, benchmark sentence; "
                    "stractive continues hyphenated Ab- from preceding line",
                ),
                (
                    "v54",
                    "the Viet-\nnamese monolingual subset of CC100",
                    "page 1; Introduction, right column near bottom",
                ),
            ],
        ),
    ]
    for source_id, title, pages, paper_id, attribution, evidence in records:
        source_record(
            source_id,
            "academic",
            pages,
            title,
            f"https://aclanthology.org/{paper_id}.pdf",
            attribution,
        )
        for key, text, region in evidence:
            anchor(key, source_id, 1, text, region)


def write_reviews(manifest):
    by_anchor = {row["id"]: row for row in anchors}
    by_source = {row["id"]: row for row in sources}
    for batch in range(5):
        lines = [
            f"# Source gold review batch {batch + 1}/5",
            "",
            EXPOSURE,
            "",
            f"Status: batch {batch + 1} approved by NhiBuaa on 2026-10-14. "
            "Full dataset is not frozen; binding and baseline B are not approved."
            if batch < 3
            else "Status: pending NhiBuaa review. Candidate content is not approved gold.",
            "",
            f"Corpus SHA-256: `{manifest['corpus_sha256']}`",
            f"Dataset SHA-256: `{manifest['dataset_sha256']}`",
            "",
            "Evidence groups: outer AND; anchors within each bracket are OR alternatives. "
            "Locators use 1-based PDF pages, not printed journal page numbers.",
            "",
        ]
        if batch == 0:
            lines.extend(
                [
                    "Approval scope: cases 001-012; case 010 includes after-receipt "
                    "timing for both 48 and 72 hours, with the opened-seal exception "
                    "limited to remote orders. Other cases are unchanged.",
                    "",
                    "Agent reconfirmed clean-02.pdf page 1 from a fresh rendering: "
                    "g1 states standard confirmation within 24 hours; g2 states "
                    "urgent confirmation within 2 hours; g3 explicitly excludes "
                    "completed resolution time. Source hash matches the manifest.",
                    "",
                ]
            )
        if batch == 1:
            lines.extend(
                [
                    "Approval scope: cases 013-024; case 018 explicitly asks for "
                    "the difference in orders. Reference, required facts and evidence "
                    "anchors are unchanged. Other cases are unchanged.",
                    "",
                    "Case 018: the difference of 14 orders is calculated from "
                    "30 minus 16 in table-01.pdf, not printed directly in the PDF.",
                    "",
                ]
            )
        if batch == 2:
            lines.extend(
                [
                    "Approval scope: cases 025-036; case 029 required facts include "
                    "continuous hours including weekends; case 031 required facts "
                    "include that permission to publish unapproved versions cannot "
                    "be inferred; case 036 explicitly asks about an expired "
                    "calibration label. Other cases are unchanged.",
                    "",
                    "Case 031 remains ANSWER: the source states permission for "
                    "approved versions only, without establishing either permission "
                    "or an absolute prohibition for unapproved versions. Evidence "
                    "anchors and follow-up parent links are unchanged.",
                    "",
                ]
            )
        for row in cases[batch * 12 : (batch + 1) * 12]:
            lines.extend(
                [
                    f"## {row['id']} - {row['category']} - {row['language']}",
                    "",
                    row["question"],
                    "",
                    f"Reference: {row['reference_answer']}",
                    "",
                    "Required facts: " + "; ".join(row["required_facts"])
                    if row["required_facts"]
                    else "Required facts: none (REFUSAL).",
                    f"AND/OR groups: `{json.dumps(row['evidence_groups'])}`",
                    f"Parent: {row['parent_case_id'] or 'none'}",
                    "",
                ]
            )
            if row["no_answer_scope"]:
                lines.extend(
                    [
                        f"Corpus-bounded absence: {row['no_answer_scope']}",
                        "",
                        "Check against all 16 source PDFs listed in the manifest; "
                        "no positive evidence anchor is claimed.",
                        "",
                    ]
                )
            for group in row["evidence_groups"]:
                for key in group:
                    a = by_anchor[key]
                    s = by_source[a["source_id"]]
                    lines.extend(
                        [
                            f"- Anchor `{key}`: [{s['id']}](./{s['id']}.pdf), "
                            f"PDF page {a['page']}, {a['region']}",
                            f"  - Verbatim visible evidence: {a['text'].replace(chr(10), ' / ')}",
                            f"  - Source SHA-256: `{s['sha256']}`; "
                            f"license: [{s['license']}]({s['license_url']}); "
                            f"[source]({s['source_url']})",
                            "",
                        ]
                    )
            lines.extend(
                [
                    "Owner decision: approved by NhiBuaa on 2026-10-14 for this batch only."
                    if batch < 3
                    else "Owner decision: pending. Fact completeness, visible locator, "
                    "AND/OR alternatives and no-answer scope require owner review.",
                    "",
                ]
            )
        (HERE / f"review-batch-{batch + 1:02}.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    pdfmetrics.registerFont(TTFont("Fixture", str(FONT)))
    pdfmetrics.registerFont(TTFont("FixtureBold", str(BOLD)))
    prose(
        "clean-01",
        "Sổ điều hướng hồ sơ",
        "clean",
        [[f"r{i}" for i in range(1, 4)], [f"r{i}" for i in range(4, 7)]],
    )
    prose("clean-02", "Hướng dẫn phiếu hỗ trợ", "clean", [[f"g{i}" for i in range(1, 7)]])
    prose("hierarchy-01", "Quy định đổi và hoàn", "hierarchy", [[f"h1{i}" for i in range(1, 7)]])
    prose("hierarchy-02", "Quyền và lưu trữ", "hierarchy", [[f"h2{i}" for i in range(1, 7)]])
    prose(
        "hierarchy-03",
        "Cảnh báo vận hành",
        "hierarchy",
        [[f"h3{i}" for i in range(1, 4)], [f"h3{i}" for i in range(4, 7)]],
    )
    prose(
        "columns-01",
        "Hạn mức sử dụng",
        "multi_column",
        [[f"c1{i}" for i in range(1, 7)]],
        columns=True,
    )
    prose(
        "columns-02",
        "Bilingual evidence glossary",
        "multi_column",
        [[f"c2{i}" for i in range(1, 7)]],
        columns=True,
    )
    table("table-01", "Bảng đơn hàng", "t1", "đơn", ["Trạng thái đơn", "Đã xử lý", "Còn chờ"])
    table(
        "table-02", "Bảng thời lượng hỗ trợ", "t2", "phút", ["Kênh hỗ trợ", "Trực tuyến", "Tại chỗ"]
    )
    table("table-03", "Bảng khối lượng kiểm", "t3", "kg", ["Ca kiểm", "Sáng", "Chiều"])
    scan("scan-01", "Kho ảnh SC-07", [f"s1{i}" for i in range(1, 5)])
    scan("scan-02", "Biên bản kiểm MX-11", [f"s2{i}" for i in range(1, 5)], mixed=True)
    scan("scan-03", "Phiếu thiết bị RX-03", [f"s3{i}" for i in range(1, 5)], rotated=True)
    academic()
    author_gold()
    assert len(sources) == 16 and len(cases) == 60
    assert {a["id"] for a in anchors} == {a for c in cases for g in c["evidence_groups"] for a in g}
    raw = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in cases).encode()
    manifest = dict(
        schema_version=1,
        version="pdf-retrieval-v3-v1-candidate",
        status="pending",
        owner="NhiBuaa",
        exposure=EXPOSURE,
        corpus_digest_scheme="canonical-sources-and-anchors-json-sha256-v1",
        corpus_sha256=digest(dict(sources=sources, anchors=anchors)),
        dataset_sha256=hashlib.sha256(raw).hexdigest(),
        sources=sources,
        anchors=anchors,
    )
    (EVALS / "datasets/pdf_retrieval_v3_v1.jsonl").write_bytes(raw)
    (EVALS / "datasets/pdf_retrieval_v3_v1.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_reviews(manifest)
    print(
        f"Authored {len(sources)} sources, {len(anchors)} anchors, {len(cases)} cases; "
        "owner review pending."
    )


if __name__ == "__main__":
    main()
