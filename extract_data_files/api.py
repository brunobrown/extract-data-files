from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from pprint import pprint

from extract_data_files.patterns import BR_PATTERNS, extract_patterns
from extract_data_files.pdf import (
    PdfStructuredText,
    TemplateSpec,
    extract_pdf_kv,
    extract_pdf_kv_by_template,
    extract_pdf_text_structured,
    inspect_pdf_layout,
)


def _suffix(path: str | Path) -> str:
    return Path(path).suffix.lower()


def extract_text_structured(
    path: str | Path,
    *,
    normalize_content: bool = False,
) -> list[dict]:
    """
    Entry-point para o micro-serviço.

    Retorna uma estrutura JSON-serializável com texto organizado (ex.: por página).
    Por enquanto suporta apenas PDF; outros tipos serão adicionados depois.
    """
    if _suffix(path) == ".pdf":
        pages = extract_pdf_text_structured(path, normalize_content=normalize_content)
        return [asdict(p) for p in pages]
    raise NotImplementedError(f"Unsupported file type: {_suffix(path) or '(no extension)'}")


def extract_kv(
    path: str | Path,
    *,
    normalize_content: bool = False,
) -> dict[str, str]:
    """
    Entry-point para extrair dicionário chave/valor.
    Por enquanto suporta apenas PDF; outros tipos serão adicionados depois.
    """
    if _suffix(path) == ".pdf":
        return extract_pdf_kv(path, normalize_content=normalize_content)
    raise NotImplementedError(f"Unsupported file type: {_suffix(path) or '(no extension)'}")


def extract_kv_by_template(
    path: str | Path,
    template: dict[str, TemplateSpec],
    *,
    normalize_content: bool = False,
    join: str = " ",
) -> dict[str, str]:
    """
    Extrai dicionário usando template posicional (bbox por campo).

    Para PDFs cujo layout é gráfico (boleto, DARF, GPS, DANFE…) e os rótulos
    não vêm como texto. O template mapeia o nome do campo a (x0, y0, x1, y1)
    em coordenadas do PDF (origem inferior-esquerda); opcionalmente acrescente
    a página como 5º elemento.
    """
    if _suffix(path) == ".pdf":
        return extract_pdf_kv_by_template(
            path, template, normalize_content=normalize_content, join=join
        )
    raise NotImplementedError(f"Unsupported file type: {_suffix(path) or '(no extension)'}")


def inspect_layout(
    path: str | Path,
    *,
    normalize_content: bool = False,
) -> list[dict]:
    """
    Devolve linhas com posição (page, x0, y0, fontname, text). Útil para
    descobrir os bbox que vão alimentar `extract_kv_by_template`.
    """
    if _suffix(path) == ".pdf":
        return inspect_pdf_layout(path, normalize_content=normalize_content)
    raise NotImplementedError(f"Unsupported file type: {_suffix(path) or '(no extension)'}")


def extract_text_plain(
    path: str | Path,
    *,
    normalize_content: bool = False,
    page_separator: str = "\n\n--- PAGE {page} ---\n\n",
) -> str:
    """
    Retorna uma string única pronta para enviar para um modelo de IA.
    """
    if _suffix(path) != ".pdf":
        raise NotImplementedError(f"Unsupported file type: {_suffix(path) or '(no extension)'}")

    pages: list[PdfStructuredText] = extract_pdf_text_structured(
        path, normalize_content=normalize_content
    )
    chunks: list[str] = []
    for p in pages:
        if page_separator:
            chunks.append(page_separator.format(page=p.page))
        chunks.append("\n".join(p.lines))
    return "".join(chunks).strip()


def extract_patterns_from_file(
    path: str | Path,
    *,
    normalize_content: bool = False,
    patterns: dict[str, re.Pattern[str]] | None = None,
    unique: bool = True,
) -> dict[str, list[str]]:
    """
    Extrai padrões (CNPJ, CPF, datas, valores BRL, linha digitável…) do texto
    do arquivo. Funciona em qualquer documento — o regex não depende do layout.

    Use junto com `extract_kv_by_template` para resolver ambiguidades em
    layouts conhecidos, ou sozinho como triagem inicial.
    """
    text = extract_text_plain(path, normalize_content=normalize_content, page_separator=" ")
    return extract_patterns(text, patterns=patterns or BR_PATTERNS, unique=unique)


DARF_SICALC_TEMPLATE: dict[str, TemplateSpec] = {
    # Topo do DARF
    "cnpj_contribuinte": (130, 725, 145, 730),
    "razao_social_contribuinte": (150, 725, 320, 730),
    "periodo_apuracao": (88, 698, 100, 705),
    "data_documento": (215, 695, 230, 702),
    "numero_referencia": (325, 695, 340, 705),
    "data_vencimento": (480, 685, 495, 695),
    "receita_descricao": (35, 678, 50, 685),
    "razao_social_beneficiario": (44, 668, 60, 675),
    "codigo_receita": (35, 650, 50, 658),
    "valor_total": (495, 650, 510, 660),
    # Linha digitável (4 fragmentos em y≈192)
    "linha_digitavel": (35, 188, 230, 198),
}


if __name__ == "__main__":
    pdf_path = "/data/projects/python/extract-data-files/files/pdf/boleto_fake.pdf"

    print("--- extract_kv (heurística por fonte) ---")
    layout_result = inspect_layout(pdf_path)
    pprint(layout_result)

    print("\n--- extract_kv_by_template (template DARF Sicalc) ---")
    for k, v in extract_kv_by_template(pdf_path, DARF_SICALC_TEMPLATE).items():
        print(f"{k}: {v!r}")

    print("\n--- extract_patterns_from_file (catálogo BR) ---")
    for k, v in extract_patterns_from_file(pdf_path).items():
        if v:
            print(f"{k}: {v}")
