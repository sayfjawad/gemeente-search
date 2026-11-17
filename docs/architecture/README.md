# Architectuurdocumentatie — gemeente-search

Welkom bij de architectuurdocumentatie van **gemeente-search** — de
multi-gemeente RAG-zoekmachine over Nederlandse gemeentewebsites. Deze
documentatie is de single source of truth voor het ontwerp, de principes en de
technische keuzes van het systeem.

De structuur volgt dezelfde **genummerde opzet als `odp-architecture`**, maar
geschaald naar één FastAPI-service: zelfde discipline (context vastleggen,
beslissingen onderbouwen via ADR's, "wat" én "waarom"), geen 13 losse
platforms maar één applicatie met bouwblokken.

## 🗺️ Repositorystructuur & navigatie

| Sectie | Beschrijving |
| :--- | :--- |
| **[00-Overview](00-overview/)** | Business-context, [visie & doelen](00-overview/vision-and-goals.md), [scope](00-overview/scope-and-boundaries.md), [glossary](00-overview/glossary.md). |
| **[01-Principes](01-architecture-principles/)** | [Drivers](01-architecture-principles/architectural-drivers.md), [constraints](01-architecture-principles/constraints.md), [designprincipes](01-architecture-principles/design-principles.md), [invloeden](01-architecture-principles/influences.md). |
| **[02-Systeemcontext](02-system-context/)** | [Contextdiagram](02-system-context/context-diagram.md), [externe systemen](02-system-context/external-systems.md), [datastromen](02-system-context/data-flow-overview.md). |
| **[03-Platforms](03-platforms/)** | [De applicatie](03-platforms/gemeente-search-platform.md), [de LLM-dienst](03-platforms/llm-node.md), [embeddings & retrieval](03-platforms/embedding-and-retrieval.md). |
| **[04-Shared Resources](04-shared-resources/)** | [Gedeelde infrastructuur](04-shared-resources/shared-infrastructure.md): GPU-server, LLM-dienst, NAS, venv, HF-cache, edge-VPS. |
| **[05-Cross-Cutting Concerns](05-cross-cutting-concerns/)** | [RAG & contextvenster](05-cross-cutting-concerns/rag-and-context-window.md), [bronvermelding](05-cross-cutting-concerns/source-citation.md), [kosten & schaling](05-cross-cutting-concerns/costs-and-scaling.md), security, observability. |
| **[06-Concepts](06-cross-cutting-concepts/)** | [Domeinmodel](06-cross-cutting-concepts/domain-model.md), [retrieval](06-cross-cutting-concepts/retrieval-and-ranking.md), [LLM-concepten](06-cross-cutting-concepts/llm-concepts.md). |
| **[07-ADR's](07-decision-records/)** | Architecture Decision Records voor elke belangrijke keuze. |
| **[08-Development](08-development/)** | [Lokaal ontwikkelen](08-development/local-development.md), [codeerconventies](08-development/coding-guidelines.md), [bijdragen](08-development/contributing.md). |
| **[09-Operations](09-operations/)** | [Deployment](09-operations/deployment.md), [onboarding-runbook](09-operations/onboarding-runbook.md), [monitoring](09-operations/monitoring.md). |
| **[10-Runtime & Data Flows](10-runtime-and-data-flows/)** | [Datapijplijn](10-runtime-and-data-flows/data-pipeline.md), [query-flow](10-runtime-and-data-flows/query-flow.md). |
| **[11-Roadmap](11-roadmap/)** | [Verbeteringen](11-roadmap/roadmap.md) en [schaling naar heel Nederland](11-roadmap/netherlands-scaling.md). |
| **[12-Diagrams](12-diagrams/)** | PlantUML-bronbestanden voor alle diagrammen. |
| **[13-Incidents](13-incidents/)** | Incidentenrapporten. |

## 🛠️ Hoe bij te werken

Documentation-as-code: wijzigingen via een feature-branch + PR.

1. **Nummering behouden** — volg de bestaande genummerde secties en
   bestandsnamen.
2. **ADR verplicht** bij een significante architectuurkeuze — gebruik
   [het sjabloon](07-decision-records/adr-template.md).
3. **Diagrammen in PlantUML** — bronbestanden in `12-diagrams/`, geëxporteerde
   afbeeldingen embedden in de markdown.
4. **Relatieve links** — controleer dat links tussen documenten kloppen.

## 📚 Kernverwijzingen

- [Visie & doelen](00-overview/vision-and-goals.md)
- [Contextdiagram](02-system-context/context-diagram.md)
- [De LLM-dienst (Qwen3.8-27B) en de modelhistorie](03-platforms/llm-node.md)
- [Deployment](09-operations/deployment.md)
- [RAG-technieken & contextvenster](05-cross-cutting-concerns/rag-and-context-window.md)
- [Bronvermelding & visuele aanpak](05-cross-cutting-concerns/source-citation.md)
- [Schaling naar heel Nederland](11-roadmap/netherlands-scaling.md)
- [ADR-index](07-decision-records/)
