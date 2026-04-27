# extract-data-files

Biblioteca para extração inicial de conteúdo de documentos antes de enviar para uma API de IA.

Por enquanto: **suporte apenas a PDF** (usando `pdferli`).

## API (para micro-serviço)

```python
from extract_data_files.api import extract_text_plain, extract_text_structured, extract_kv

text = extract_text_plain("files/pdf/boleto.pdf")
structured = extract_text_structured("files/pdf/boleto.pdf")  # JSON-serializável
kv = extract_kv("files/pdf/boleto.pdf")
```

