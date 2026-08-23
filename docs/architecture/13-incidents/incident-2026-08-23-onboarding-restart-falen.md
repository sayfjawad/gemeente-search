# Incident 2026-08-23: onboarding-pipeline kan de live service niet herstarten

- **Datum & duur**: ontdekt 2026-08-23, ~2u19m na de start van de
  `onboard-all-gemeentes.service`-run van die dag; gefixt dezelfde dag.
- **Impact**: elke gemeente die de crawl/ingest/index-stappen succesvol
  doorloopt maar bij de laatste stap (`restart_service_and_verify()`) faalt,
  wordt in `onboarding_queue.json` als `failed` gemarkeerd — terwijl de
  index zelf wél correct is opgebouwd. `'s-Hertogenbosch` was de eerste
  hierdoor geraakte gemeente in deze run; zonder ingrijpen zou dit
  vermoedelijk élke volgende gemeente in de resterende ~335 hebben getroffen
  (de fout is structureel, niet gemeente-specifiek).
- **Oorzaak**: `onboard-all-gemeentes.service` draait als **systeem**-level
  systemd-unit (`User=sayf`, maar niet als een ingelogde sessie), terwijl
  `gemeente-search.service` een **user**-level (`systemctl --user`) unit is.
  De system-unit mist `$XDG_RUNTIME_DIR`/`$DBUS_SESSION_BUS_ADDRESS`, dus
  `systemctl --user restart gemeente-search.service` binnen het
  onboarding-script faalde met `Failed to connect to bus`. Een eerdere,
  interactief-gestarte testrun van dezelfde service had deze env wél
  (geërfd van de inlogsessie) en slaagde daardoor toevallig wel — vandaar
  dat dit niet meteen bij de allereerste gemeente (Schiermonnikoog) aan het
  licht kwam.
- **Oplossing / mitigatie**: `Environment=XDG_RUNTIME_DIR=/run/user/1000`
  toegevoegd aan `onboard-all-gemeentes.service`'s unit-bestand. Werkt
  omdat `loginctl enable-linger sayf` al aanstond, waardoor de user-systemd-
  instantie en diens D-Bus-socket persistent bestaan, los van een actieve
  inlogsessie. Geen scriptwijziging nodig. Geverifieerd door het exacte
  restart-commando met dezelfde environment handmatig te reproduceren
  (slaagt, `exit=0`). `'s-Hertogenbosch`'s queue-entry teruggezet naar
  `pending` zodat de pipeline die opnieuw oppakt.
- **Vervolgacties**: geen — dit is een structurele fix, geen workaround.
  Elke toekomstige system-level unit op deze machine die een `--user`-unit
  van `sayf` moet aansturen loopt tegen hetzelfde gat aan als
  `Environment=XDG_RUNTIME_DIR=/run/user/1000` ontbreekt.
