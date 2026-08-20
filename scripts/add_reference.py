"""Add a curated reference document to the corpus.

The municipality's vergunning pages defer to the national Omgevingsloket /
Besluit bouwwerken leefomgeving (Bbl) for the actual "vergunningsvrij bouwen"
criteria (e.g. whether a serre/aanbouw/bijgebouw needs a permit). That content
is not on ijsselstein.nl and is fragmented across interactive tools, so we add
one concise, accurately-sourced summary as a reference doc. This is what lets
"smart" bouw questions (e.g. "mag ik een serre van 6x4m in mijn 8x6m tuin
plaatsen?") be answered with the concrete rules.

Written as a normal doc record so ingest.py / build_index.py treat it like any
other page (chunked + embedded). Re-run any time to (re)generate the file.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import muni

REFERENCE_TEXTS = [
    {
        "url": "https://www.omgevingsloket.nl/",
        "title": "Vergunningsvrij bouwen: bijbehorende bouwwerken (aanbouw, serre, bijgebouw)",
        "text": (
            "Onder de Omgevingswet staat wanneer u een omgevingsvergunning nodig heeft "
            "voor het bouwen van een bijbehorend bouwwerk bij een woning. Een bijbehorend "
            "bouwwerk is een aanbouw, uitbouw, bijgebouw, serre, garage, schuur, carport of "
            "overkapping die functioneel ondergeschikt is aan het hoofdgebouw (de woning).\n\n"

            "Wanneer is een bijbehorend bouwwerk vergunningsvrij?\n"
            "Een bijbehorend bouwwerk mag in beginsel zonder omgevingsvergunning worden "
            "gebouwd als het in het achtererfgebied staat en aan de regels voldoet. Het "
            "achtererfgebied is het erf achter de lijn die op 1 meter achter de voorgevel "
            "van het hoofdgebouw ligt en evenwijdig daaraan loopt. Op het voorerf (naar de "
            "openbare weg gekeerd) is een bijbehorend bouwwerk niet vergunningsvrij; "
            "uitzonderingen zijn onder meer een erker of een verbindend bouwwerk tussen de "
            "woning en een legaal bijbehorend bouwwerk.\n\n"

            "Belangrijkste regels voor een vergunningsvrij bijbehorend bouwwerk in het "
            "achtererf:\n"
            "- De oppervlakte van het achtererfgebied mag voor maximaal 50% worden bebouwd "
            "met bijbehorende bouwwerken. (Sommige omgevingsplannen laten meer toe.)\n"
            "- De goothoogte is maximaal 3 meter en de bouwhoogte (nok) maximaal 5 meter.\n"
            "- Het bouwwerk staat minimaal 1 meter achter het verlengde van de voorgevel "
            "en minimaal 1 meter uit een zijerfgrens die aan de openbare weg grenst.\n"
            "- Het bouwwerk staat op de grond en is functioneel ondergeschikt aan de "
            "woning; verblijfsruimten alleen op de eerste bouwlaag.\n"
            "- Het bouwwerk voldoet aan de bouwtechnische eisen van het Besluit bouwwerken "
            "leefomgeving (Bbl), inclusief brandveiligheid.\n\n"

            "Wanneer heeft u WEL een omgevingsvergunning nodig?\n"
            "- Als het bouwwerk in het voorerfgebied staat (met uitzondering van een erker "
            "of verbindend bouwwerk).\n"
            "- Als het perceel of gebouw een rijks- of gemeentelijk monument is, of in een "
            "beschermd stads- of dorpsgezicht ligt.\n"
            "- Als de 50%-regel, de hoogteregels of andere maatvoering wordt overschreden.\n"
            "- Als het omgevingsplan van de gemeente het niet toestaat.\n\n"

            "Rekenvoorbeeld serre: een tuin van 8 x 6 meter is 48 m2. Een serre van 6 x 4 "
            "meter is 24 m2. Dat is precies 50% van de tuin. Als de serre als aanbouw aan de "
            "woning in het achtererf staat, niet hoger is dan 5 meter (goothoogte 3 meter) en "
            "aan de overige voorwaarden voldoet, is dit in de regel vergunningsvrij. Stond de "
            "serre (deels) in het voorerf, of wordt de 50%-grens of de hoogte overschreden, "
            "dan is wel een omgevingsvergunning nodig.\n\n"

            "Ook vergunningsvrij is niet regelvrij: u moet altijd voldoen aan de "
            "bouwtechnische eisen en lokale regels. Doe voor uw eigen adres de "
            "vergunningcheck op omgevingsloket.nl om zeker te weten of u een vergunning nodig "
            "heeft of iets moet melden; bij twijfel neemt u contact op met de gemeente "
            "IJsselstein."
        ),
    },
]


def main():
    parser = argparse.ArgumentParser()
    muni.add_muni_arg(parser)
    args = parser.parse_args()
    name = muni.get(args.municipality)["name"]
    out = muni.data_dir(args.municipality) / "crawl" / "reference_docs.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in REFERENCE_TEXTS:
            text = r["text"].strip().replace("gemeente IJsselstein", f"gemeente {name}")
            doc = {
                "id": hashlib.sha1(r["url"].encode()).hexdigest(),
                "url": r["url"],
                "title": r["title"],
                "text": text,
                "doc_type": "html",
                "published_at": None,
                "fetched_at": now,
                "source_path": None,
                "pages": None,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "site": "reference",
            }
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"wrote {len(REFERENCE_TEXTS)} reference doc(s) -> {out}")


if __name__ == "__main__":
    main()
