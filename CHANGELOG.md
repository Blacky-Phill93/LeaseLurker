# Changelog

Alle wesentlichen Änderungen dieses Projekts werden in dieser Datei dokumentiert.
Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/)
und die Versionierung an [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

## [0.1.6] - 2026-09-24

### Sicherheit

- Debian-Laufzeitpakete werden während des Container-Builds auf die aktuellen
  Security-Revisionsstände aktualisiert.

## [0.1.5] - 2026-09-24

### Behoben

- Aktive Kea-Leases ohne Hardwareadresse bleiben anhand von Hostname und
  IP-Adresse sichtbar, ohne einen HTTP-503-Fehler auszulösen.
- Fehlerhafte einzelne Lease-Einträge werden übersprungen und als Anzahl
  protokolliert, anstatt den gesamten Snapshot zu verwerfen.
- Fehler beim Aktualisieren eines Snapshots werden mit ihrer tatsächlichen
  Ursache protokolliert und sind dadurch diagnostizierbar.

## [0.1.4] - 2026-09-08

### Behoben

- Nicht aktive Kea-Leases werden vor der MAC-Adressvalidierung übersprungen,
  sodass beispielsweise ein abgelaufener Lease ohne Hardwareadresse nicht mehr
  den gesamten Snapshot mit HTTP 503 verhindert.

## [0.1.3] - 2026-09-08

### Behoben

- Das produktive Docker-Compose-Deployment verwendet unter Linux das
  Host-Netzwerk und erreicht dadurch einen ausschließlich an
  `127.0.0.1:8000` gebundenen Kea Control Agent.
- Der Kea-Entwicklungsmock setzt das Host-Netzwerk wieder zurück und bleibt in
  einem isolierten Docker-Bridge-Netz erreichbar.

## [0.1.2] - 2026-09-08

### Behoben

- Docker Compose reicht die Basic-Auth-Zugangsdaten für den Kea Control Agent an
  den LeaseLurker-Container weiter.
- Der lokale Kea-Mock prüft nun ebenfalls HTTP Basic Authentication.
- Kea 2.4 kann Subnetze ohne den nicht verfügbaren `subnet_cmds`-Hook über den
  eingebauten `config-get`-Fallback liefern.

## [0.1.1] - 2026-09-07

### Hinzugefügt

- Veröffentlichung eines signierten Multi-Arch-Container-Images über GHCR.
- SBOM und Build-Provenance für veröffentlichte Container-Images.

### Geändert

- Compose verwendet standardmäßig das öffentliche GHCR-Image; lokale Builds
  erfolgen über eine separate Override-Datei.

## [0.1.0] - 2026-09-07

### Hinzugefügt

- Read-only-Weboberfläche für aktive Kea-DHCPv4-Leases.
- Teiltreffersuche nach Hostname und normalisierter MAC-Adresse.
- Nach freigegebenen Subnetzen gruppierte und paginierte Listenansicht.
- Modularer DHCP-Provider und interne Gerätenamen-Resolver-Schnittstelle.
- Offline-Herstellerauflösung mit IEEE MA-L-, MA-M- und MA-S-Daten.
- 30-Sekunden-Snapshot mit begrenztem Stale-Fallback und manuellem Refresh.
- Deutsche und englische Oberfläche.
- Non-Root-Container, Compose-Konfiguration und lokaler Kea-Entwicklungsmock.
- GitHub-CI für Formatierung, Linting, Typprüfung, Tests, Security und Image-Build.

[Unreleased]: https://github.com/Phill93/LeaseLurker/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/Phill93/LeaseLurker/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/Phill93/LeaseLurker/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Phill93/LeaseLurker/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Phill93/LeaseLurker/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Phill93/LeaseLurker/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Phill93/LeaseLurker/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Phill93/LeaseLurker/releases/tag/v0.1.0
