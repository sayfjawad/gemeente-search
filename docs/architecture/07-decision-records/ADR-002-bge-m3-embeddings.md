# ADR-002: BGE-M3 als embeddingmodel

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Gemeentelijke content is Nederlandstalig, maar bevat veel afkortingen,
samenstellingen en juridisch/bestuurlijke terminologie die semantisch doorzocht
moeten worden op "vraag"-niveau (niet op trefwoord). Het embeddingmodel moet
Nederlandse tekst goed in de vectorruimte kunnen plaatsen, en genoeg context
aankunnen voor chunks tot ~1400 tekens.

## 2. Besluit

BGE-M3 (`BAAI/bge-m3`), draaiend op de GPU in fp16, met L2-genormaliseerde
output (zodat cosine similarity een simpel dot product is). Zelfde model als al
gebruikt in `wilders-search` / `lift-normen-search` / `abo-ali-search` op dit
account — het model was al gevalideerd en lokaal gecached (`/data/huggingface`,
gezet via `HF_HOME` in `embedder.py`), dus geen nieuwe download- of
validatiecyclus nodig.

## 3. Consequenties

### 3.1. Voordelen

* Bewezen op Nederlandse content in de zusterprojecten.
* Al gecached op de GPU-node — geen nieuwe afhankelijkheid of download.
* 1024-dimensionale output is compact genoeg om de hele indexmatrix per
  gemeente in het GPU-geheugen te houden.

### 3.2. Nadelen

* Groter/trager dan een puur-Engels model zou zijn voor een Engelstalige
  usecase — hier geen bezwaar, de content is Nederlandstalig.
* Vereist een GPU voor acceptabele encode-snelheid (op CPU merkbaar trager).

## 4. Alternatieven

1. **OpenAI/Cohere embeddings-API**: geen lokale GPU-afhankelijkheid, maar
   stuurt de volledige (deels nog niet-herbouwde) gemeente-content naar een
   externe partij bij elke her-indexering. Verworpen.
2. **`nomic-embed-text` / een lokaal Ollama-embeddingmodel**: primair
   Engelstalig getraind; minder sterk op Nederlandse juridische tekst. Niet
   getest tegen BGE-M3 op deze data, en BGE-M3 was al beschikbaar. Verworpen.

## 5. Referenties

* [`embedder.py`](../../../embedder.py)
* [`build_index.py`](../../../build_index.py)
