<p align="center">
  <img src="docs/leaselurker-icon.png" alt="LeaseLurker-Icon: Der Lurker" width="140" height="140">
</p>

# LeaseLurker

LeaseLurker ist ein ausschließlich lesendes Webinterface für aktive IPv4-Leases
eines Kea-DHCP-Servers. Enduser können anhand eines Hostname-, IP- oder
MAC-Adressfragments die aktuelle IP-Adresse ihres Rechners ermitteln. Die
Listenansicht stellt freigegebene Subnetze als Tabs dar und unterstützt ein
automatisches sowie manuell umschaltbares helles und dunkles Farbschema.

> **Hinweis zum Projektstatus:** LeaseLurker ist ein Arbeitsprojekt, das im
> Rahmen der beruflichen Tätigkeit am Karlsruher Institut für Technologie (KIT)
> entwickelt wurde.

## Voraussetzungen

- Python 3.14 für lokale Entwicklung
- Poetry 2.4 oder neuer
- Kea Control Agent mit aktiviertem Hook `lease_cmds`
- Docker mit Compose für den vorgesehenen Produktivbetrieb

Kea muss `lease4-get-all` über den Dienst `dhcp4` bereitstellen. Für Subnetze
verwendet LeaseLurker bevorzugt `subnet4-list` aus dem optionalen Hook
`subnet_cmds`. Fehlt dieser beispielsweise bei Kea 2.4 unter Ubuntu 24.04, wird
automatisch das eingebaute read-only Kommando `config-get` verwendet.
LeaseLurker besitzt bewusst keine schreibenden Kea-Kommandos.

## Lokale Installation

```bash
poetry install
cp config.example.yaml config.yaml
LEASELURKER_CONFIG=./config.yaml poetry run lease-lurker
```

Danach ist die Anwendung unter <http://localhost:8080> erreichbar.

### Entwicklung ohne Kea

Für lokale UI- und Integrationstests steht ein kleiner Kea-Control-Agent-Mock mit
Beispielsubnetzen und -leases bereit:

```bash
cp config.example.yaml config.yaml
docker compose -f compose.yaml -f compose.build.yaml -f compose.mock.yaml up --build
```

LeaseLurker verwendet dabei automatisch `http://mock-kea:8000/`. Subnetz 1 ist
sichtbar und enthält zwei aktive Beispielleases; Subnetz 2 bleibt entsprechend der
Beispielkonfiguration verborgen. Der Mock implementiert ausschließlich
`list-commands`, `status-get`, `config-get` und `lease4-get-all` und ist nicht für
Produktivbetrieb vorgesehen. Die Compose-Entwicklungskonfiguration aktiviert für
Mock und Anwendung passende Basic-Auth-Testzugangsdaten.

## Konfiguration

Die YAML-Datei legt Cache, Sprache und sichtbare Subnetze fest. Nicht aufgeführte
und mit `visible: false` konfigurierte Subnetze bleiben verborgen. Anzeigenamen
können den von Kea gelieferten Namen überschreiben.

Deploymentwerte werden bevorzugt per Umgebung gesetzt:

| Variable | Bedeutung |
|---|---|
| `LEASELURKER_CONFIG` | Pfad zur YAML-Datei |
| `LEASELURKER_KEA_URL` | URL des Kea Control Agent |
| `LEASELURKER_KEA_USERNAME` | Optionaler Basic-Auth-Benutzer |
| `LEASELURKER_KEA_PASSWORD` | Optionales Basic-Auth-Passwort |
| `LEASELURKER_LOG_LEVEL` | Python-Log-Level, standardmäßig `INFO` |

Zugangsdaten gehören nicht in die YAML-Beispieldatei oder das Image. Benutzername
und Passwort müssen immer gemeinsam gesetzt werden. Bei Docker Compose können sie
über die von Git ignorierte Datei `.env` bereitgestellt werden:

```dotenv
LEASELURKER_KEA_USERNAME=lease-lurker
LEASELURKER_KEA_PASSWORD=replace-with-a-long-random-password
```

Compose reicht beide Werte an den Container weiter. Der Kea Control Agent muss
denselben Benutzer per HTTP Basic Authentication kennen. Das Passwort darf nicht
in `compose.yaml`, `config.yaml` oder ein Container-Image eingetragen werden.

Der `config-get`-Fallback verarbeitet aus der Antwort ausschließlich Subnetz-ID,
Präfix und Shared-Network-Name. Die vollständige Kea-Konfiguration wird weder
gespeichert noch protokolliert oder an das Webinterface weitergegeben.

## Qualität und Tests

```bash
poetry run ruff format .
poetry run ruff check .
poetry run mypy src
poetry run pytest
poetry run pip-audit
```

## Offline-Herstellerdaten

Die Anwendung führt zur Laufzeit keine Herstellerabfragen im Internet aus. Die
gebündelte Datenbank wird aus den öffentlichen IEEE-Registern MA-L, MA-M und MA-S
erzeugt:

```bash
poetry run python scripts/update_ieee_vendors.py
```

Änderungen der erzeugten Datei werden geprüft und zusammen mit dem Projekt
versioniert. Quelle: [IEEE Registration Authority](https://standards.ieee.org/products-programs/regauth/).

## Container

```bash
cp config.example.yaml config.yaml
docker compose pull
docker compose up -d
```

Kea läuft als Dienst auf dem Docker-Host. Compose bildet dafür
unter Linux das Host-Netzwerk in den Container ein. Dadurch erreicht LeaseLurker
den ausschließlich an `127.0.0.1:8000` gebundenen Kea Control Agent, ohne diesen
auf einer externen Schnittstelle freigeben zu müssen. Eine `ports:`-Freigabe ist
im Host-Netzwerk nicht erforderlich; LeaseLurker ist direkt auf Port 8080 des
Hosts erreichbar. Der Container läuft ohne Root-Rechte, ohne Linux-Capabilities
und mit schreibgeschütztem Dateisystem.

Das produktive `compose.yaml` ist damit für Docker Engine unter Linux ausgelegt.
Der Mock-Override setzt das Host-Netzwerk zurück und verwendet für die lokalen
Container wieder ein isoliertes Bridge-Netzwerk.

Das öffentliche Multi-Arch-Image für AMD64 und ARM64 liegt unter
`ghcr.io/phill93/leaselurker`. Stabile Releases erhalten vollständige SemVer-,
Minor-, Major- und `latest`-Tags. Für einen lokalen Image-Build:

```bash
docker compose -f compose.yaml -f compose.build.yaml up --build
```

Veröffentlichte Images enthalten SBOM und Build-Provenance und werden über
GitHub OIDC keyless signiert. Eine Signatur kann mit Cosign geprüft werden:

```bash
cosign verify ghcr.io/phill93/leaselurker:latest \
  --certificate-identity-regexp '^https://github.com/Phill93/LeaseLurker/.github/workflows/release-image.yml@refs/tags/v' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'
```

## Release

Die Paketversion wird ausschließlich in `pyproject.toml` gepflegt und von der
Anwendung aus den installierten Metadaten gelesen. Für einen Release:

1. Änderungen unter `Unreleased` in `CHANGELOG.md` einer datierten Version
   zuordnen.
2. `poetry check --lock`, Ruff, mypy, pytest, `pip-audit` und den Container-Build
   erfolgreich ausführen.
3. Wheel und sdist mit `poetry build` erzeugen und aus dem Wheel testen.
4. Den geprüften Commit mit einem signierten Tag `v<Version>` markieren und ein
   GitHub-Release veröffentlichen. Der Release-Workflow scannt AMD64 und ARM64
   separat und veröffentlicht das Image nur nach erfolgreichen Prüfungen.

## Architektur und Betrieb

Die Adapterentscheidung ist in
[`docs/adr/0001-read-only-adapter-architecture.md`](docs/adr/0001-read-only-adapter-architecture.md)
dokumentiert. `/health/live` prüft den Prozess; `/health/ready` berücksichtigt Kea
und den letzten brauchbaren Snapshot. Der In-Memory-Cache ist pro Prozess, daher
startet das ausgelieferte Image genau einen Uvicorn-Prozess.

## Copyright, Urheber und Lizenz

- **Copyright-Inhaber:** Karlsruher Institut für Technologie (KIT)
- **Urheber:** Daniel Bacher
- **Lizenz:** MIT License, siehe [LICENSE](LICENSE)
- **App-Icon:** Mit dem Bild-Modell Gemini 3.1 Flash Image (Google) generiert; Entwurf (Prompt, Zuschnitt) durch Daniel Bacher. Das Icon ist über die MIT-Lizenz des Projekts freigegeben.

Copyright © 2026 Karlsruher Institut für Technologie (KIT). LeaseLurker darf
unter den Bedingungen der MIT-Lizenz verwendet, verändert und weitergegeben
werden. Pflege und Issues erfolgen über das Projekt-Repository.
