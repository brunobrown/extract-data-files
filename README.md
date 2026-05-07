# extract-data-files

Biblioteca para extração inicial de conteúdo de documentos.

Requer Python 3.13+.

## Estratégias de extração

A biblioteca oferece três estratégias complementares — escolha conforme o documento:

| Estratégia | Quando usar | Função |
|---|---|---|
| Heurística por fonte | PDF tem rótulos como texto (negrito = chave) | `extract_kv` |
| Template posicional (bbox) | Layout gráfico fixo onde rótulos não vêm como texto (DARF, GPS, boleto) | `extract_kv_by_template` |
| Catálogo de regex | Qualquer documento — extrai padrões conhecidos sem depender do layout | `extract_patterns_from_file` |

Para texto bruto: `extract_text_plain` (string) ou `extract_text_structured` (JSON-serializável por página).

## API

```python
from extract_data_files import (
    extract_text_plain,
    extract_text_structured,
    extract_kv,
    extract_kv_by_template,
    extract_patterns_from_file,
    inspect_layout,
)
```

### 1. Texto bruto

```python
text = extract_text_plain("files/pdf/doc.pdf")             # str
pages = extract_text_structured("files/pdf/doc.pdf")       # [{page, lines}]
```

### 2. Heurística por fonte (`extract_kv`)

Detecta linhas em negrito como chaves e usa as linhas seguintes como valor. Funciona quando o PDF tem rótulos **textuais** (ex.: relatórios gerados por sistemas).

```python
kv = extract_kv("files/pdf/relatorio.pdf")
# {'Razão Social': '<nome do contribuinte>', 'CNPJ': '<cnpj>', ...}
```

Quando o documento é um **template gráfico** (boleto, DARF, etc.), os rótulos são desenhados como imagem ou path vetorial e essa estratégia retorna `{}`. Use a estratégia 3 para esses casos.

### 3. Template posicional (`extract_kv_by_template`)

Para documentos com layout fixo, defina um `dict[str, bbox]` onde cada bbox é `(x0, y0, x1, y1[, page])` em coordenadas do PDF (origem inferior-esquerda).

```python
from extract_data_files import extract_kv_by_template

DARF = {
    "cnpj_contribuinte": (130, 725, 145, 730),
    "razao_social": (150, 725, 320, 730),
    "periodo_apuracao": (88, 698, 100, 705),
    "data_vencimento": (480, 685, 495, 695),
    "valor_total": (495, 650, 510, 660),
    "linha_digitavel": (35, 188, 230, 198),
}

result = extract_kv_by_template("files/pdf/darf.pdf", DARF)
# {'cnpj_contribuinte': '<cnpj>', 'razao_social': '<nome>', ...}
```

Para autorar um template novo, use `inspect_layout` para descobrir as coordenadas reais:

```python
for line in inspect_layout("files/pdf/novo_doc.pdf"):
    print(line)  # {'page': 0, 'x0': 132.75, 'y0': 727.137, 'fontname': '...', 'text': '...'}
```

Um template pronto para DARF Sicalc está em `extract_data_files.api.DARF_SICALC_TEMPLATE`.

### 4. Catálogo de regex (`extract_patterns_from_file`)

Extrai padrões brasileiros (CNPJ, CPF, datas, valor BRL, linha digitável, CEP, e-mail, telefone, código de barras) de qualquer documento. Não sabe **qual** valor é qual campo, mas funciona em qualquer layout — útil como triagem ou fallback.

```python
from extract_data_files import extract_patterns_from_file

matches = extract_patterns_from_file("files/pdf/qualquer.pdf")
# {
#   'cnpj': ['<cnpj>'],
#   'data_br': ['<dd/mm/aaaa>'],
#   'valor_brl': ['<valor>'],
#   'linha_digitavel_arrecadacao': ['<linha digitável>'],
#   ...
# }
```

Para um catálogo customizado, passe `patterns=...`:

```python
import re
from extract_data_files import extract_patterns_from_file, BR_PATTERNS

custom = {**BR_PATTERNS, "matricula": re.compile(r"\bMAT\.\s*\d{6}\b")}
matches = extract_patterns_from_file("files/pdf/holerite.pdf", patterns=custom)
```

Padrões disponíveis em `BR_PATTERNS`: `cnpj`, `cpf`, `data_br`, `competencia_mm_aaaa`, `competencia_mes_aaaa`, `valor_brl`, `cep`, `email`, `telefone_br`, `linha_digitavel_boleto`, `linha_digitavel_arrecadacao`, `codigo_barras_44`. Em `BR_PATTERNS_RAW` há variantes de alta abrangência (ex.: `cnpj_unformatted`, `cpf_unformatted`, `pis_pasep`) — úteis quando os dados vêm sem formatação, ao custo de mais falsos positivos.

## Fluxo recomendado em produção

1. **Template** quando o documento é recorrente e o layout é estável.
2. **Catálogo de regex** como fallback ou complemento (resolve "que valores existem").
3. Para tudo o mais, encaminhe `extract_text_plain` para uma LLM com schema estruturado.

## Desenvolvimento

```bash
uv tool run ruff format
uv tool run ruff check
uv tool run ty check
```