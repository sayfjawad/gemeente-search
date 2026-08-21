# ADR-010: Bestaande deploy-topologie hergebruikt (systemd + Tailscale + nginx)

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Dit account draait al meerdere GPU-backed zoekapplicaties (`wilders-search`,
`lift-normen-search`, `slimme-archief-zoeker`) met een bewezen topologie:
systemd-`--user`-unit op de GPU-node, nginx-reverse-proxy met TLS op een
edge-VPS, en Tailscale als privaat netwerk ertussen. Voor `gemeente-search`
was er geen reden om hiervan af te wijken — de enige afwijking is dat het
taalmodel niet lokaal (Ollama) draait maar op de gx10-node (zie ADR-004).

## 2. Besluit

De bestaande topologie wordt hergebruikt:
- systemd-`--user`-unit op de GPU-node (Z8), poort **8905**;
- de runtime-venv wordt gedeeld met `lift-normen-search`
  (`/data/git/lift-normen-search/.venv`), een bewezen ML-stack;
- nginx + certbot op de edge-VPS, TLS-terminatie, `proxy_pass` naar de
  GPU-node over Tailscale (`gemeente.multicode.nl`);
- het taalmodel (GPT-OSS-120B) draait op de gx10-node via llama.cpp
  (`100.64.x.x:8083`), eveneens over Tailscale.

## 3. Consequenties

### 3.1. Voordelen

* Geen nieuwe infrastructuur, geen nieuwe operationele procedures — consistent
  met de rest van het account.
* De gedeelde venv betekent geen duplicatie van de (grote) ML-stack.

### 3.2. Nadelen

* Koppeling aan de gedeelde venv: een wijziging daarin (bijv. voor
  `lift-normen-search`) kan `gemeente-search` raken en omgekeerd.
* Gedeelde GPU-node: meer diensten concurreren om VRAM/geheugen.

## 4. Alternatieven

1. **Containeriseren (Docker/K8s)**: herbouwbaar, maar overkill voor één
   single-user service op een bestaande node en breekt met de bestaande
   systemd-conventie van het account. Verworpen.
2. **Eigen venv per app**: isoleert dependencies, maar dupliceert een
   torch/transformers-installatie van meerdere GB. Verworpen.

## 5. Referenties

* [`deploy/gemeente-search.service`](../../../deploy/gemeente-search.service)
* [deployment.md](../09-operations/deployment.md)
