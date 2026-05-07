from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd
from pdferli import get_pdfdf


@dataclass(frozen=True)
class PdfStructuredText:
    page: int
    lines: list[str]


@dataclass(frozen=True)
class TemplateField:
    """Bounding box em coordenadas do PDF (origem inferior-esquerda)."""

    x0: float
    y0: float
    x1: float
    y1: float
    page: int = 0


type TemplateSpec = (
    TemplateField | tuple[float, float, float, float] | tuple[float, float, float, float, int]
)


def _coerce_path(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    return str(p)


def _unique_lines(df: pd.DataFrame) -> pd.DataFrame:
    required = {"aa_text_line", "aa_x0", "aa_y0", "aa_fontname", "bb_hierachy_page"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"pdferli dataframe missing columns: {sorted(missing)}")

    lines = df.dropna(subset=["aa_text_line"]).copy()
    lines["aa_text_line"] = lines["aa_text_line"].astype(str)

    def _page(v) -> int:
        if isinstance(v, tuple):
            return int(v[0]) if len(v) >= 1 else 0
        if pd.isna(v):
            return 0
        return int(v)

    lines["__page"] = lines["bb_hierachy_page"].map(_page)
    lines["__y"] = pd.to_numeric(lines["aa_y0"], errors="coerce")
    lines["__x"] = pd.to_numeric(lines["aa_x0"], errors="coerce")

    # De-duplicate repeated line text generated per-character by pdfminer.
    # Rounding stabilizes tiny coordinate differences across chars.
    lines["__y_key"] = lines["__y"].round(1)
    lines["__x_key"] = lines["__x"].round(1)

    lines = lines.sort_values(
        by=["__page", "__y", "__x"],
        ascending=[True, False, True],
        kind="mergesort",
    )
    lines = lines.drop_duplicates(subset=["__page", "__y_key", "aa_text_line"], keep="first")

    return lines[["__page", "__x", "__y", "aa_fontname", "aa_text_line"]].rename(
        columns={
            "__page": "page",
            "__x": "x0",
            "__y": "y0",
            "aa_fontname": "fontname",
            "aa_text_line": "text",
        }
    )


def extract_pdf_text_structured(
    path: str | Path,
    *,
    normalize_content: bool = False,
) -> list[PdfStructuredText]:
    """
    Extracts structured text from a PDF as pages + ordered lines.
    """
    df = get_pdfdf(_coerce_path(path), normalize_content=normalize_content)
    lines = _unique_lines(df)

    out: list[PdfStructuredText] = []
    for page, group in lines.groupby("page", sort=True):
        out.append(PdfStructuredText(page=int(cast(int, page)), lines=group["text"].tolist()))
    return out


def extract_pdf_kv(
    path: str | Path,
    *,
    normalize_content: bool = False,
    is_key_font: Callable[[str], bool] | None = None,
) -> dict[str, str]:
    """
    Extracts a dictionary (key -> value) from a PDF by detecting key lines (bold by default)
    and assigning subsequent lines as its value until the next key.
    """
    if is_key_font is None:

        def is_key_font(font: str) -> bool:
            return "bold" in str(font).lower()

    def _looks_like_value(text: str) -> bool:
        t = text.strip()
        if not t:
            return True
        # Avoid treating amounts / numeric codes as keys even if they are bold.
        return bool(re.search(r"\d", t) and re.fullmatch(r"[0-9\s\.,:/\-–—R$\(\)]+", t))

    df = get_pdfdf(_coerce_path(path), normalize_content=normalize_content)
    lines = _unique_lines(df)
    if lines.empty:
        return {}

    lines = lines.copy()
    lines["x0round"] = lines["x0"].round(2)

    result: dict[str, str] = {}

    for _, x_group in lines.groupby("x0round", sort=False):
        x_group = x_group.sort_values(
            by=["page", "y0", "x0"], ascending=[True, False, True], kind="mergesort"
        )

        current_key: str | None = None
        current_value: list[str] = []

        for _, row in x_group.iterrows():
            text = str(row["text"]).strip()
            if not text:
                continue

            font = row["fontname"]
            if is_key_font(font) and not _looks_like_value(text):
                if current_key is not None and current_value:
                    result.setdefault(current_key, "\n".join(current_value).strip())
                current_key = text
                current_value = []
                continue

            if current_key is not None:
                current_value.append(text)

        if current_key is not None and current_value:
            result.setdefault(current_key, "\n".join(current_value).strip())

    # Drop empty values and normalize duplicate keys a bit
    result = {k.strip(): v.strip() for k, v in result.items() if k and v}
    return result


def _coerce_bbox(spec: TemplateSpec) -> TemplateField:
    if isinstance(spec, TemplateField):
        return spec
    match spec:
        case (x0, y0, x1, y1):
            return TemplateField(x0=x0, y0=y0, x1=x1, y1=y1)
        case (x0, y0, x1, y1, page):
            return TemplateField(x0=x0, y0=y0, x1=x1, y1=y1, page=int(page))
        case _:
            raise TypeError(f"Unsupported template spec: {spec!r}")


def extract_pdf_kv_by_template(
    path: str | Path,
    template: dict[str, TemplateSpec],
    *,
    normalize_content: bool = False,
    join: str = " ",
) -> dict[str, str]:
    """
    Extrai pares chave/valor a partir de um template posicional.

    Use quando o PDF é um template gráfico (boleto, DARF, GPS, DANFE…) onde os
    rótulos não vêm como texto extraível. Cada entrada do template mapeia o
    nome do campo a um bounding box (x0, y0, x1, y1[, page]) em coordenadas do
    PDF (origem inferior-esquerda).
    """
    df = get_pdfdf(_coerce_path(path), normalize_content=normalize_content)
    lines = _unique_lines(df)
    if lines.empty:
        return {field: "" for field in template}

    result: dict[str, str] = {}
    for field, spec in template.items():
        bbox = _coerce_bbox(spec)
        mask = (
            (lines["page"] == bbox.page)
            & (lines["x0"] >= bbox.x0)
            & (lines["x0"] <= bbox.x1)
            & (lines["y0"] >= bbox.y0)
            & (lines["y0"] <= bbox.y1)
        )
        matched = lines.loc[mask].sort_values(
            by=["y0", "x0"], ascending=[False, True], kind="mergesort"
        )
        result[field] = join.join(matched["text"].astype(str).tolist()).strip()
    return result


def inspect_pdf_layout(
    path: str | Path,
    *,
    normalize_content: bool = False,
) -> list[dict]:
    """
    Devolve linhas com posição (page, x0, y0, fontname, text) — útil para
    autorar templates de extract_pdf_kv_by_template.
    """
    df = get_pdfdf(_coerce_path(path), normalize_content=normalize_content)
    lines = _unique_lines(df)
    return lines.to_dict(orient="records")


def list_pdfs(root: str | Path = "files/pdf") -> list[Path]:
    base = Path(root)
    if not base.exists():
        return []
    return sorted([p for p in base.rglob("*.pdf") if p.is_file()])


def extract_many_pdfs_text_structured(
    paths: Iterable[str | Path],
    *,
    normalize_content: bool = False,
) -> dict[str, list[PdfStructuredText]]:
    return {
        str(Path(p)): extract_pdf_text_structured(p, normalize_content=normalize_content)
        for p in paths
    }


def extract_many_pdfs_kv(
    paths: Iterable[str | Path],
    *,
    normalize_content: bool = False,
) -> dict[str, dict[str, str]]:
    return {str(Path(p)): extract_pdf_kv(p, normalize_content=normalize_content) for p in paths}
