from __future__ import annotations

import re

BR_PATTERNS: dict[str, re.Pattern[str]] = {
    "cnpj": re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
    "cpf": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "data_br": re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),
    "competencia_mm_aaaa": re.compile(r"\b\d{2}/\d{4}\b"),
    "competencia_mes_aaaa": re.compile(
        r"\b(?:Janeiro|Fevereiro|Março|Abril|Maio|Junho|"
        r"Julho|Agosto|Setembro|Outubro|Novembro|Dezembro)/\d{4}\b",
        re.IGNORECASE,
    ),
    # Valor BRL com ou sem prefixo R$. O prefixo é opcional, mas se vier deve
    # estar imediatamente antes do número — não capturamos espaço solto.
    "valor_brl": re.compile(r"(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}"),
    "cep": re.compile(r"\b\d{5}-\d{3}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    # Exige separador entre DDD e número (parênteses, espaço, ponto ou hífen)
    # para não casar com sequências longas de dígitos (p.ex. linha digitável).
    "telefone_br": re.compile(r"(?:\(\d{2}\)\s?|\b\d{2}[.\s-])(?:9\s?)?\d{4}[-.\s]?\d{4}\b"),
    # Linha digitável de boleto bancário (FEBRABAN, 47 dígitos).
    "linha_digitavel_boleto": re.compile(
        r"\b\d{5}\.?\d{5}\s+\d{5}\.?\d{6}\s+\d{5}\.?\d{6}\s+\d\s+\d{14}\b"
    ),
    # Linha digitável de arrecadação (DARF, concessionárias): 4 blocos
    # ~11 dígitos + 1 dígito verificador, separados por espaço ou hífen.
    "linha_digitavel_arrecadacao": re.compile(r"(?:\d{10,11}[\s-]+\d[\s-]+){3}\d{9,11}[\s-]+\d"),
    "codigo_barras_44": re.compile(r"(?<!\d)\d{44}(?!\d)"),
}


# Padrões adicionais opcionais — alta abrangência, baixa precisão.
# Use junto com BR_PATTERNS quando precisar caçar dígitos crus, sabendo que
# fragmentos de linha digitável podem aparecer como falsos positivos.
BR_PATTERNS_RAW: dict[str, re.Pattern[str]] = {
    "cnpj_unformatted": re.compile(r"(?<!\d)\d{14}(?!\d)"),
    "cpf_unformatted": re.compile(r"(?<!\d)\d{11}(?!\d)"),
    "pis_pasep": re.compile(r"\b\d{3}\.\d{5}\.\d{2}-\d\b"),
}


def extract_patterns(
    text: str,
    *,
    patterns: dict[str, re.Pattern[str]] | None = None,
    unique: bool = True,
    normalize_whitespace: bool = True,
) -> dict[str, list[str]]:
    """
    Aplica um catálogo de regex sobre o texto e devolve todos os matches por padrão.

    `unique=True` remove duplicatas preservando a ordem.
    `normalize_whitespace=True` colapsa quebras de linha em espaço antes de aplicar
    os regex (necessário para padrões que cruzam linhas, como linha digitável).
    """
    if patterns is None:
        patterns = BR_PATTERNS
    if normalize_whitespace:
        text = re.sub(r"\s+", " ", text)

    out: dict[str, list[str]] = {}
    for name, pattern in patterns.items():
        matches = pattern.findall(text)
        if unique:
            seen: set[str] = set()
            matches = [m for m in matches if not (m in seen or seen.add(m))]
        out[name] = matches
    return out
