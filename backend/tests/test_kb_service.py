from chatbi.services.kb_chunking import (
    ChunkProfile,
    chunk_document,
    chunk_text,
    infer_chunk_profile,
    looks_like_faq,
    sliding_window_chunk,
)
from chatbi.services.kb_chunking import FileKind
from chatbi.services.kb_parsers import is_supported_upload, parse_paste


def test_chunk_text_splits_long_paragraph():
    para = "甲" * 800
    chunks = chunk_text(para, chunk_size=300, overlap=50)
    assert len(chunks) >= 2
    assert all(len(c) <= 300 for c in chunks)


def test_chunk_text_preserves_short_paragraphs():
    text = "第一段内容。\n\n第二段内容。"
    chunks = chunk_text(text)
    assert len(chunks) == 2


def test_infer_markdown_profile():
    md = "## 第一章\n内容\n\n## 第二章\n更多"
    profile = infer_chunk_profile(md, file_kind=FileKind.MARKDOWN, suffix=".md")
    assert profile == ChunkProfile.MARKDOWN


def test_infer_faq_profile():
    faq = "问：差旅上限？\n答：每天 500。\n\n问：如何报销？\n答：走 OA。"
    assert looks_like_faq(faq)
    profile = infer_chunk_profile(faq, file_kind=FileKind.TXT, suffix=".txt")
    assert profile == ChunkProfile.FAQ


def test_chunk_markdown_by_heading():
    md = "## A\n" + ("x" * 100) + "\n\n## B\n" + ("y" * 100)
    chunks = chunk_document(md, ChunkProfile.MARKDOWN)
    assert len(chunks) >= 2


def test_supported_suffixes():
    assert is_supported_upload("a.pdf")
    assert is_supported_upload("b.xlsx")
    assert not is_supported_upload("legacy.doc")


def test_parse_paste():
    parsed = parse_paste("hello\n\nworld", filename="note.txt")
    assert parsed.text == "hello\n\nworld"
    assert parsed.file_kind == FileKind.TXT


def test_sliding_window_overlap():
    text = "甲" * 2000
    chunks = sliding_window_chunk(text, chunk_size=500, overlap=100)
    assert len(chunks) >= 4
    # 步长 400，第二块起点应与第一块 [400:500] 重叠
    assert chunks[1][:100] == chunks[0][400:500]


def test_long_general_uses_sliding():
    text = ("段落内容。" * 80) + "\n\n" + ("更多说明。" * 80)
    chunks = chunk_document(text, ChunkProfile.GENERAL, chunk_size=400, overlap=80)
    assert len(chunks) >= 2
