"""
知识库文档切块。策略由 parse 推断的 ChunkProfile 决定，经 chunk_document 分发。

策略一览：
  general  — ≤chunk_size：整段或按空行多段；≥800 字或无段落：全文滑动；否则短段整块、长段滑动
  markdown — 按 # 标题分节，每节同 general；无标题 → general
  faq      — 按「问：/Q：」分块，小块合并至 ≤chunk_size，超大块滑动
  csv      — 首行表头，25 行/块，重叠 3 行（不用字符 chunk_size）
  excel    — 按「## 工作表:」分 sheet；≤35 行整块，否则 30 行/块、重叠 3 行

滑动窗口：步长 = chunk_size - overlap；截断优先对齐换行/句号。KB_CHUNK_SIZE/OVERLAP 可覆盖默认值。
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Callable, List

# 通用文本（字符）
_DEFAULT_CHUNK_SIZE = 600
_DEFAULT_OVERLAP = 120
# 表格（行）
_CSV_ROWS_PER_CHUNK = 25
_CSV_ROW_OVERLAP = 3
_EXCEL_ROWS_PER_CHUNK = 30
_EXCEL_ROW_OVERLAP = 3
# general：全文滑动阈值
_FULL_DOC_SLIDING_THRESHOLD = 800

_SOFT_BREAK_PATTERN = re.compile(r"[\n。！？!?；;]")
_FAQ_LINE = re.compile(
    r"^(?:Q[:：]|问[:：]|【问】|问题\s*[:：]|\d+[、.．]\s*.+？\s*$)",
    re.MULTILINE,
)
_HEADING = re.compile(r"^#{1,4}\s+.+$", re.MULTILINE)
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


class ChunkProfile(str, Enum):
    """切块策略。"""

    GENERAL = "general"
    MARKDOWN = "markdown"
    FAQ = "faq"
    CSV = "csv"
    EXCEL = "excel"


class FileKind(str, Enum):
    """文件类型（推断策略用）。"""

    TXT = "txt"
    MARKDOWN = "markdown"
    CSV = "csv"
    PDF = "pdf"
    EXCEL = "excel"
    WORD = "word"


_KIND_TO_PROFILE: dict[FileKind, ChunkProfile] = {
    FileKind.CSV: ChunkProfile.CSV,
    FileKind.EXCEL: ChunkProfile.EXCEL,
}


def looks_like_faq(text: str) -> bool:
    """≥2 处 FAQ 问句标记。"""
    return len(_FAQ_LINE.findall(text)) >= 2


def looks_like_markdown(text: str, *, suffix: str = "") -> bool:
    """.md 后缀或 ≥2 行 # 标题。"""
    return suffix.lower() in (".md", ".markdown") or len(_HEADING.findall(text)) >= 2


def infer_chunk_profile(
    text: str,
    *,
    file_kind: FileKind | str,
    suffix: str = "",
) -> ChunkProfile:
    """自动选策略：csv/excel 固定 → markdown → faq → general。"""
    kind = file_kind if isinstance(file_kind, FileKind) else FileKind(str(file_kind))
    fixed = _KIND_TO_PROFILE.get(kind)
    if fixed is not None:
        return fixed
    suf = suffix.lower()
    if kind == FileKind.MARKDOWN or looks_like_markdown(text, suffix=suf):
        return ChunkProfile.MARKDOWN
    return ChunkProfile.FAQ if looks_like_faq(text) else ChunkProfile.GENERAL


def chunk_document(
    text: str,
    profile: ChunkProfile | str,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_OVERLAP,
) -> List[str]:
    """统一入口：规范化后按 profile 分发 _CHUNK_HANDLERS。"""
    profile_enum = ChunkProfile(profile) if isinstance(profile, str) else profile
    normalized = (text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return []
    overlap = _normalize_overlap(overlap, chunk_size)
    handler = _CHUNK_HANDLERS[profile_enum]
    return handler(normalized, chunk_size=chunk_size, overlap=overlap)


def chunk_text(
    text: str,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_OVERLAP,
) -> List[str]:
    """兼容入口，等同 general。"""
    return _chunk_general(text, chunk_size=chunk_size, overlap=overlap)

"""滑动窗口切块"""
def sliding_window_chunk(
    text: str,
    *,
    chunk_size: int,
    overlap: int,
) -> List[str]:
    """字符滑动+重叠：≤chunk_size 一块；否则软边界截断，步长 chunk_size-overlap。"""
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    overlap = _normalize_overlap(overlap, chunk_size)
    step = max(1, chunk_size - overlap)
    chunks: List[str] = []
    start = 0
    n = len(normalized)

    while start < n:
        hard_end = min(start + chunk_size, n)
        end = _find_soft_break_end(normalized, hard_end) if hard_end < n else hard_end
        end = max(end, min(start + 1, n))
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start += step
    return chunks

"""规范化重叠值"""
def _normalize_overlap(overlap: int, chunk_size: int) -> int:
    return 0 if chunk_size < 2 else min(max(0, overlap), chunk_size - 1)


def _find_soft_break_end(text: str, hard_end: int, *, search_back: int = 150) -> int:
    """hard_end 前 search_back 字符内取最靠后的软边界。"""
    if hard_end >= len(text):
        return len(text)
    start_search = max(0, hard_end - search_back)
    window = text[start_search:hard_end]
    best = -1
    for match in _SOFT_BREAK_PATTERN.finditer(window):
        best = match.end()
    return start_search + best if best > 0 else hard_end


"""按段落拆分"""
def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]

"""按段落单位切块"""
def _chunk_sections(
    sections: List[str], *, chunk_size: int, overlap: int
) -> List[str]:
    """多 section：≤chunk_size 整块，否则段内 sliding_window。"""
    chunks: List[str] = []
    for section in sections:
        if len(section) <= chunk_size:
            chunks.append(section)
            continue
        chunks.extend(sliding_window_chunk(section, chunk_size=chunk_size, overlap=overlap))
    return chunks


def _chunk_general(text: str, *, chunk_size: int, overlap: int) -> List[str]:
    """general：短全文单/多段；≥800 或无段落则全文滑动；否则按段落 _chunk_sections。"""
    paragraphs = _split_paragraphs(text)
    if len(text) <= chunk_size:
        return paragraphs if len(paragraphs) > 1 else [text]
    if len(text) >= _FULL_DOC_SLIDING_THRESHOLD or not paragraphs:
        return sliding_window_chunk(text, chunk_size=chunk_size, overlap=overlap)
    return _chunk_sections(paragraphs, chunk_size=chunk_size, overlap=overlap)


def _chunk_markdown(text: str, *, chunk_size: int, overlap: int) -> List[str]:
    """markdown：按 #~#### 分节 → _chunk_sections；无标题 → general。"""
    parts = re.split(r"(?=^#{1,4}\s)", text, flags=re.MULTILINE)
    sections = [p.strip() for p in parts if p.strip()]
    if len(sections) <= 1 and not _HEADING.search(text):
        return _chunk_general(text, chunk_size=chunk_size, overlap=overlap)
    return _chunk_sections(sections, chunk_size=chunk_size, overlap=overlap)


def _chunk_faq(text: str, *, chunk_size: int, overlap: int) -> List[str]:
    """faq：按问句拆块，buf 合并至 ≤chunk_size；单块超长则滑动。"""
    blocks = re.split(
        r"(?=^(?:Q[:：]|问[:：]|【问】|问题\s*[:：]))",
        text,
        flags=re.MULTILINE,
    )
    chunks = [b.strip() for b in blocks if b.strip()]
    if len(chunks) <= 1:
        chunks = _split_paragraphs(text)

    merged: List[str] = []
    buf = ""
    for block in chunks:
        if len(block) > chunk_size:
            if buf:
                merged.append(buf.strip())
                buf = ""
            merged.extend(
                sliding_window_chunk(block, chunk_size=chunk_size, overlap=overlap)
            )
            continue
        candidate = f"{buf}\n\n{block}".strip() if buf else block
        if len(candidate) <= chunk_size:
            buf = candidate
            continue
        if buf:
            merged.append(buf)
        buf = block
    if buf:
        merged.append(buf.strip())
    return merged


def _chunk_row_table(
    lines: List[str],
    *,
    rows_per_chunk: int,
    row_overlap: int,
    header: str | None = None,
) -> List[str]:
    """表格行：每块=表头+rows_per_chunk 行，stride=rows_per_chunk-row_overlap。"""
    if not lines:
        return []
    table_header = header if header is not None else lines[0]
    data_lines = lines[1:] if header is None and len(lines) > 1 else lines
    if header is not None:
        data_lines = lines
    if not data_lines:
        return [table_header]

    overlap = min(max(0, row_overlap), rows_per_chunk - 1)
    stride = max(1, rows_per_chunk - overlap)
    return [
        "\n".join([table_header, *data_lines[i : i + rows_per_chunk]]).strip()
        for i in range(0, len(data_lines), stride)
    ]


def _chunk_csv_text(text: str, *, chunk_size: int, overlap: int) -> List[str]:
    """csv：25 行/块，3 行重叠，首行表头。"""
    del chunk_size, overlap
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return _chunk_row_table(
        lines, rows_per_chunk=_CSV_ROWS_PER_CHUNK, row_overlap=_CSV_ROW_OVERLAP
    )


def _chunk_excel_text(text: str, *, chunk_size: int, overlap: int) -> List[str]:
    """excel：按工作表分；小 sheet 整块，大 sheet 30 行/块、3 行重叠。"""
    del chunk_size, overlap
    sheet_parts = re.split(r"(?=^##\s*工作表[:：])", text, flags=re.MULTILINE)
    sections = [s.strip() for s in sheet_parts if s.strip()]
    if not sections:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        return _chunk_row_table(
            lines,
            rows_per_chunk=_EXCEL_ROWS_PER_CHUNK,
            row_overlap=_EXCEL_ROW_OVERLAP,
        )

    chunks: List[str] = []
    for section in sections:
        lines = section.splitlines()
        if len(lines) <= _EXCEL_ROWS_PER_CHUNK + 5:
            chunks.append(section)
            continue
        chunks.extend(
            _chunk_row_table(
                lines[1:],
                rows_per_chunk=_EXCEL_ROWS_PER_CHUNK,
                row_overlap=_EXCEL_ROW_OVERLAP,
                header=lines[0],
            )
        )
    return chunks


_CHUNK_HANDLERS: dict[ChunkProfile, Callable[..., List[str]]] = {
    ChunkProfile.GENERAL: _chunk_general,
    ChunkProfile.MARKDOWN: _chunk_markdown,
    ChunkProfile.FAQ: _chunk_faq,
    ChunkProfile.CSV: _chunk_csv_text,
    ChunkProfile.EXCEL: _chunk_excel_text,
}
