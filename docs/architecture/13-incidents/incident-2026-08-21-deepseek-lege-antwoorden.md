# Incident 2026-08-21: lege antwoorden ondanks correcte bronnen (DeepSeek)

- **Datum & duur**: ontdekt 2026-08-21 tijdens het testen van de
  gemeente-onboarding-pipeline; vermoedelijk actief sinds de DeepSeek-
  omschakeling diezelfde dag (zie [ADR-013](../07-decision-records/ADR-013-deepseek-tijdelijke-failover.md)),
  tot de fix later dezelfde dag.
- **Impact**: een onbekende fractie van live `/api/ask`-vragen op *alle* op
  dat moment al aangesloten gemeentes (IJsselstein, Nieuwegein,
  Vijfheerenlanden, Utrecht, Houten, Barendrecht) kon een leeg antwoord
  krijgen terwijl de bronnen wél correct gevonden en geciteerd waren —
  gebruikers zagen vermoedelijk "geen antwoord" zonder duidelijke reden.
  Gereproduceerd op Schiermonnikoog's openingstijden-vraag tijdens het
  testen van de onboarding-pipeline.
- **Oorzaak**: `call_llm()` stuurde `chat_template_kwargs: {enable_thinking:
  false}` mee, een llama.cpp/Qwen-specifieke conventie. DeepSeek's API
  negeert dit veld en kan bij een dubbelzinnige of tegenstrijdige
  brondataset het volledige `max_tokens`-budget (1800) opmaken aan
  `reasoning_content`, met `finish_reason: "length"` en lege `content` als
  gevolg.
- **Oplossing / mitigatie**: `call_llm()` retried nu automatisch één keer
  met `max_tokens=6000` zodra de eerste poging leeg terugkomt met
  `finish_reason=="length"`. Geverifieerd op de exacte vraag die het
  probleem reproduceerde.
- **Vervolgacties**: zie [ADR-014](../07-decision-records/ADR-014-verhuizing-naar-c4130.md)
  §6 — met GPT-OSS-120B (via `reasoning_effort` i.p.v. `enable_thinking`) is
  de kans op deze situatie kleiner, maar de retry-bescherming blijft
  bewust staan als generiek vangnet tegen elk reasoning-model dat zijn
  budget aan denken kan opmaken.
