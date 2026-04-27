from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from extract_data_files.pdf import PdfStructuredText, extract_pdf_kv, extract_pdf_text_structured


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

    pages: list[PdfStructuredText] = extract_pdf_text_structured(path, normalize_content=normalize_content)
    chunks: list[str] = []
    for p in pages:
        if page_separator:
            chunks.append(page_separator.format(page=p.page))
        chunks.append("\n".join(p.lines))
    return "".join(chunks).strip()


if __name__ == "__main__":
    test = extract_text_structured(path='/data/projects/python/extract-data-files/files/pdf/boleto.pdf')
    print(test)