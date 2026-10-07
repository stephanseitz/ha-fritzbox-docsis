<p align="center">
  <img src="docs/images/banner.svg" alt="FRITZ!Box Cable DOCSIS für Home Assistant" width="100%">
</p>

<p align="center">
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square" alt="HACS Custom"></a>
  <a href="https://github.com/stephanseitz/ha-fritzbox-docsis/releases"><img src="https://img.shields.io/github/v/release/stephanseitz/ha-fritzbox-docsis?style=flat-square" alt="Release"></a>
  <a href="https://github.com/stephanseitz/ha-fritzbox-docsis/actions/workflows/validate.yml"><img src="https://img.shields.io/github/actions/workflow/status/stephanseitz/ha-fritzbox-docsis/validate.yml?branch=main&label=hassfest%20%26%20HACS&style=flat-square" alt="Validierung"></a>
  <a href="https://github.com/stephanseitz/ha-fritzbox-docsis/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/stephanseitz/ha-fritzbox-docsis/tests.yml?branch=main&label=tests&style=flat-square" alt="Tests"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2025.2%2B-18BCF2?style=flat-square&logo=homeassistant&logoColor=white" alt="Home Assistant 2025.2+">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/stephanseitz/ha-fritzbox-docsis?style=flat-square" alt="Lizenz: MIT"></a>
</p>

<p align="center">
  <a href="README.md">English</a> · <b>Deutsch</b>
</p>

# FRITZ!Box Kabel (DOCSIS) für Home Assistant

Holt die Seite **Kabel-Informationen** einer FRITZ!Box Cable (*Internet › Kabel-Informationen*)
und die Kabel-Ereignisse aus dem **Ereignisprotokoll** nach Home Assistant: Pegel, MSE/MER,
korrigierbare und nicht korrigierbare Fehler je Kanal, **Fehlerraten pro Stunde** und ein
Ereignis bei jedem Synchronisationsverlust.

Gebaut für die Frage, die jeder Kabelkunde irgendwann der Hotline stellt: *„Warum bricht
meine Verbindung ständig ab, und wie kann ich das belegen?“* Nach ein paar Wochen Verlauf
siehst du, welcher Kanal gestört ist, wann das passiert, ob es mit etwas im Haus
zusammenhängt und wann genau jede Neusynchronisierung war.

## Inhalt

- [Funktionen](#funktionen)
- [Voraussetzungen](#voraussetzungen)
- [Installation](#installation)
- [Einrichtung](#einrichtung)
- [Entitäten](#entitäten)
- [Ereignisse und Automationen](#ereignisse-und-automationen)
- [Dashboard](#dashboard)
- [Werte richtig lesen](#werte-richtig-lesen)
- [Funktionsweise](#funktionsweise)
- [Fehlersuche](#fehlersuche)
- [Entwicklung](#entwicklung)
- [Hintergrund und Danksagung](#hintergrund-und-danksagung)

## Funktionen

- 📶 **Jeder Kanal mit eigenen Entitäten**: DOCSIS-3.0-Downstream (Pegel, MSE, Fehler),
  DOCSIS-3.1-OFDM-Blöcke (Pegel, MER, Fehler), Upstream-Kanäle und OFDMA-Modulation.
- 📈 **Fehlerraten pro Stunde** je Kanal und gesamt. Die Rohzähler starten bei jeder
  Neusynchronisierung bei 0, die Raten nicht. So bleiben Trends lesbar.
- 🔎 Sensor **Auffälligster Kanal**: zeigt direkt auf die gestörte Frequenz, mit den
  Top 5 als Attribut.
- 🔌 **Sync-Verluste aus dem Ereignisprotokoll** mit dem **ursprünglichen Zeitpunkt**,
  auch wenn Home Assistant die Box während des Ausfalls nicht erreicht hat.
- ⚡ **Ereignisse** `fritzbox_docsis_sync_lost` / `fritzbox_docsis_sync_restored` und eine
  Event-Entität für Logbuch und Automationen.
- 📊 **Langzeitstatistik** ohne Zusatzaufwand (Zähler als `total_increasing`, Pegel als
  `measurement`), bereit für Statistik-Diagramme über Monate.
- 🧭 **Stabile Entity-IDs**: Kanäle heißen nach ihrer **Frequenz**, nicht nach der
  Kanal-ID, denn die Kanal-IDs können sich nach jeder Neusynchronisierung ändern.
- 🌍 Oberfläche auf Deutsch und Englisch, Entitätsnamen folgen der Sprache von Home Assistant.
- 🔒 Nur lokale Abfrage, nur lesend, keine Cloud. Diagnose-Download ohne Zugangsdaten.

## Voraussetzungen

| | |
|---|---|
| **FRITZ!Box** | Ein Kabelmodell, z. B. FRITZ!Box 6591 Cable, 6660 Cable oder 6690 Cable. Andere Kabelmodelle mit derselben Oberfläche sollten ebenfalls funktionieren. |
| **FRITZ!OS** | 7.2x oder neuer. Anmeldung per PBKDF2 (ab FRITZ!OS 7.24), MD5 als Rückfall. |
| **Home Assistant** | 2025.2 oder neuer. |
| **Netzwerk** | Home Assistant muss die Oberfläche der FRITZ!Box erreichen, lokal oder über MyFRITZ!. |

## Installation

### HACS (empfohlen)

[![Repository in HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stephanseitz&repository=ha-fritzbox-docsis&category=integration)

Oder von Hand:

1. HACS › ⋮ › **Benutzerdefinierte Repositories**
2. Repository: `https://github.com/stephanseitz/ha-fritzbox-docsis`, Typ **Integration**
3. Nach **FRITZ!Box Cable (DOCSIS)** suchen, herunterladen und **Home Assistant neu starten**.

### Manuell

1. `fritzbox_docsis.zip` aus dem [neuesten Release](https://github.com/stephanseitz/ha-fritzbox-docsis/releases/latest) herunterladen.
2. Nach `/config/custom_components/fritzbox_docsis/` entpacken, sodass
   `/config/custom_components/fritzbox_docsis/manifest.json` existiert.
3. Home Assistant neu starten.

## Einrichtung

### 1. FRITZ!Box-Benutzer anlegen

In der FRITZ!Box: **System › FRITZ!Box-Benutzer › Benutzer hinzufügen**

- Name z. B. `homeassistant`, mit einem langen, eigenen Kennwort
- Recht **„FRITZ!Box Einstellungen“** aktivieren. Ohne dieses Recht liefert die Box keine Kabel-Informationen.
- Nur bei Zugriff über MyFRITZ!: zusätzlich **„Zugang auch aus dem Internet erlaubt“**
- Alle anderen Rechte (Sprachnachrichten, Smart Home, NAS …) aus

### 2. Lokal oder über MyFRITZ!?

**Lokal ist besser**: schneller, und Home Assistant erreicht die Box auch während eines
Kabel-Ausfalls. Nimm die Adresse, mit der du die FRITZ!Box im Browser öffnest, z. B.
`http://192.168.178.1`. Steht die FRITZ!Box vor einem weiteren Router, ist es meist eine
Adresse im WAN-Netz dieses Routers.

**MyFRITZ!** funktioniert auch, z. B. `https://xxxxxxxx.myfritz.net:44xxx`:

- **„SSL-Zertifikat prüfen“** eingeschaltet lassen, das MyFRITZ!-Zertifikat ist gültig.
- Während eines Kabel-Ausfalls ist die Box über MyFRITZ! nicht erreichbar. Die Entitäten
  sind dann kurz *nicht verfügbar*. Der Sync-Verlust wird trotzdem erfasst: Sobald die Box
  wieder erreichbar ist, liest die Integration das Protokoll und meldet das Ereignis mit
  dem **ursprünglichen Zeitpunkt**.

### 3. Optional: Zugang vorab testen

`tools/fritz_docsis_check.py` braucht nur Python 3.10+ und keine Zusatzpakete:

```bash
python tools/fritz_docsis_check.py --url http://192.168.178.1 --user homeassistant
```

Das Skript fragt das Kennwort ab, zeigt alle Kanäle als Tabelle und die letzten
Kabel-Ereignisse und speichert die Rohdaten in `fritz_docsis_raw.json` (ohne Zugangsdaten).
Passt etwas nicht, ist diese Datei die beste Grundlage für ein Issue.

### 4. Integration hinzufügen

[![Einrichtung in Home Assistant starten](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=fritzbox_docsis)

Oder **Einstellungen › Geräte & Dienste › Integration hinzufügen › FRITZ!Box Cable (DOCSIS)**.

- **Adresse**: z. B. `http://192.168.178.1` oder die MyFRITZ!-Adresse mit Port. Ein aus dem
  Browser kopierter Pfad wie `/#/cable/channels` wird automatisch entfernt.
- **Benutzername / Kennwort** aus Schritt 1.

**Optionen** (*Konfigurieren*):

| Option | Standard | |
|---|---|---|
| Abfrageintervall | 300 s | 60–3600 s. Jede Abfrage sind zwei Anfragen an die Box. |
| Ereignisprotokoll auswerten | an | Nötig für Sync-Verluste und die Verbindungssensoren. |

Ändert sich das Kennwort, fragt Home Assistant von selbst nach den neuen Zugangsdaten.

## Entitäten

Die Entity-IDs folgen der Sprache von Home Assistant. Die Beispiele unten gelten für
**Deutsch**; auf Englisch heißen sie z. B. `sensor.fritz_box_cable_ds_578_mhz_correctable_errors_per_hour`.

### Gerät

| Entität | Beispiel-ID | Hinweis |
|---|---|---|
| Kabelverbindung | `binary_sensor.fritz_box_kabel_kabelverbindung` | Aus dem Ereignisprotokoll. Attribut `recent_events`. |
| Kabel-Synchronisation | `event.fritz_box_kabel_kabel_synchronisation` | Ereignistypen `sync_lost`, `sync_start`, `sync_ok` |
| Letzter Sync-Verlust | `sensor.fritz_box_kabel_letzter_sync_verlust` | Zeitpunkt aus dem Protokoll |
| Synchron seit | `sensor.fritz_box_kabel_synchron_seit` | Zeitpunkt |
| Sync-Rate Empfangen / Senden | `sensor.fritz_box_kabel_sync_rate_empfangen` | Mbit/s, aus dem letzten Protokolleintrag „Kabel-Internet ist verfügbar“ |
| Sync-Verluste 24 h / 7 Tage | `sensor.fritz_box_kabel_sync_verluste_24_h` | |
| Korrigierbare / nicht korrigierbare Fehler gesamt | `sensor.fritz_box_kabel_korrigierbare_fehler_gesamt` | Zähler, startet bei Neusynchronisierung bei 0 |
| Korrigierbare / nicht korrigierbare Fehler pro Stunde | `sensor.fritz_box_kabel_korrigierbare_fehler_pro_stunde` | Rate über alle Downstream-Kanäle |
| Auffälligster Kanal | `sensor.fritz_box_kabel_auffalligster_kanal` | Kanal mit der höchsten Rate korrigierbarer Fehler. Attribut `top_channels`. |
| DS Pegel min / max | `sensor.fritz_box_kabel_ds_pegel_min` | dBmV |
| DS MSE schlechtester Kanal | `sensor.fritz_box_kabel_ds_mse_schlechtester_kanal` | dB, DOCSIS 3.0 |
| DS MER schlechtester OFDM-Block | `sensor.fritz_box_kabel_ds_mer_schlechtester_ofdm_block` | dB, DOCSIS 3.1 |
| US Pegel max | `sensor.fritz_box_kabel_us_pegel_max` | dBmV |
| US OFDMA Modulation | `sensor.fritz_box_kabel_us_ofdma_modulation` | z. B. `256QAM` |
| DS / US Kanäle | `sensor.fritz_box_kabel_ds_kanale` | Diagnose |

### Je Kanal

Werden für jede Frequenz, die die Box meldet, automatisch angelegt. Neue Frequenzen
erscheinen ohne Neustart als neue Entitäten.

| Kanaltyp | Entitäten |
|---|---|
| **Downstream DOCSIS 3.0** (`ds_578_mhz_…`) | Pegel, MSE, korrigierbare Fehler, nicht korrigierbare Fehler, korrigierbare Fehler pro Stunde, nicht korrigierbare Fehler pro Stunde *(standardmäßig deaktiviert)* |
| **Downstream OFDM** (`ds_ofdm_751_861_mhz_…`) | Pegel, MER, nicht korrigierbare Fehler, nicht korrigierbare Fehler pro Stunde |
| **Upstream** (`us_37_2_mhz_…`, `us_ofdma_48_65_mhz_…`) | Pegel |

Attribute: `docsis`, `channel_id`, `frequency_mhz`, `frequency_end_mhz` (OFDM),
`modulation`, `active_subcarriers` (OFDMA). In der Oberfläche erscheinen sie übersetzt.

> [!NOTE]
> Die FRITZ!Box setzt alle Fehlerzähler bei jeder Neusynchronisierung und jedem Neustart
> auf 0. Die Zähler haben `state_class: total_increasing`, Home Assistant verarbeitet das
> Zurücksetzen in der Langzeitstatistik deshalb korrekt. Die Raten sind nach einem
> Zurücksetzen für ein Intervall *unbekannt*. Die Einheit der Fehler ist `errors` bzw.
> `errors/h`, unabhängig von der Sprache, damit die Statistik stabil bleibt.

## Ereignisse und Automationen

Bei jedem neuen Kabel-Ereignis im Protokoll feuert die Integration auf dem Event-Bus:

| Ereignis | Wann |
|---|---|
| `fritzbox_docsis_sync_lost` | „Kabel-Internet antwortet nicht (Keine Synchronisierung)“ |
| `fritzbox_docsis_sync_restored` | „Kabel-Internet ist verfügbar“ |

Ereignisdaten:

```yaml
kind: sync_lost                     # sync_lost | sync_ok
timestamp: "2026-10-01T23:52:28+02:00"  # Zeitpunkt aus dem FRITZ!Box-Protokoll
message: "Kabel-Internet antwortet nicht (Keine Synchronisierung)."
source: log                         # log, oder counters bei abgeschaltetem Protokoll
```

Ereignisse werden über Neustarts von Home Assistant hinweg nur einmal gemeldet. Ältere
Einträge werden beim ersten Einrichten nicht nachträglich gemeldet.

Minimale Benachrichtigung:

```yaml
triggers:
  - trigger: event
    event_type: fritzbox_docsis_sync_lost
actions:
  - action: notify.notify
    data:
      title: "Kabel-Internet: Sync-Verlust"
      message: "{{ trigger.event.data.timestamp }}: {{ trigger.event.data.message }}"
```

Mehr in [`examples/de/automations.yaml`](examples/de/automations.yaml): Sync-Verlust,
Verbindung wieder da, Paketverluste und abgesenkte Upstream-Modulation.

## Dashboard

[`examples/de/dashboard.yaml`](examples/de/dashboard.yaml) ist ein fertiges
Abschnitts-Dashboard nur aus Standardkarten: Verbindungsstatus, Logbuch der
Sync-Ereignisse, Fehlerraten mit Verlaufsgrafik, Tachos mit Richtwert-Farbbereichen für
Pegel und MSE sowie Statistiken über 30 Tage. Englische Entity-IDs:
[`examples/en/dashboard.yaml`](examples/en/dashboard.yaml).

**Tipp** für die Suche nach Störquellen: die Fehlerrate des auffälligsten Kanals in einem
Verlaufsdiagramm neben große Verbraucher im Haus legen (Wärmepumpe, Wallbox,
PV-Wechselrichter) oder auf die Uhrzeiten achten, zu denen die Fehler anfangen.

## Werte richtig lesen

Grobe Richtwerte für SC-QAM-Kabelkanäle. Netzbetreiber haben eigene Grenzwerte, und ein
einzelner Wert knapp außerhalb ist kein Grund zur Sorge; entscheidend ist der Verlauf.

| Wert | Gut | Beobachten | Schlecht |
|---|---|---|---|
| **DS-Pegel** | −2 … +12 dBmV | −6 … −2 oder +12 … +18 | unter −6 / über +18 |
| **DS-MSE** (256QAM) | besser als −33 dB (z. B. −37) | −33 … −31 dB | schlechter als −31 dB |
| **US-Pegel** | 35 … 49 dBmV | 49 … 51 | über 51 dBmV (Modem am Limit) |
| **Korrigierbare Fehler** | einige pro Stunde | auf einem Kanal stetig steigend | hohe Rate auf einem Kanal: Einstrahlung |
| **Nicht korrigierbare Fehler** | 0 | gelegentlich | dauerhaft: Paketverlust |

Typische Muster:

- **Ein Downstream-Kanal mit deutlich mehr korrigierbaren Fehlern als seine Nachbarn**
  deutet auf schmalbandige Einstrahlung auf dieser Frequenz hin, z. B. ein Rundfunk- oder
  Mobilfunksignal, das über schlecht geschirmte Kabel eindringt. Zuerst Kabel, Stecker und
  Dose prüfen.
- **Wiederholte Sync-Verluste** bei Upstream-Pegel am oberen Ende deuten auf ein Problem im
  Rückweg hin. Den Netzbetreiber die Leitung prüfen lassen und ihm den Verlauf zeigen.
- **Sinkende OFDMA-Modulation** (z. B. von 256QAM auf 64QAM) heißt: Der Betreiber sieht
  einen schlechteren Rückweg und stuft herunter.

## Funktionsweise

- Anmeldung über `login_sid.lua?version=2` (PBKDF2, MD5 als Rückfall), die Sitzung bleibt
  bestehen. Läuft sie ab, meldet sich die Integration unbemerkt neu an.
- Liest von `data.lua` die Seite `docInfo` (das JSON hinter *Kabel-Informationen*) und die
  Seite `log`.
- Fehlerraten sind die Differenz der Zähler geteilt durch die vergangene Zeit; ein
  kleiner gewordener Zähler markiert eine Neusynchronisierung und ergibt für dieses
  Intervall *unbekannt*.
- Kabel-Ereignisse werden an den Protokolltexten erkannt (deutsche und englische
  FRITZ!OS-Texte). Das neueste gesehene Ereignis wird gespeichert, damit nichts doppelt
  gemeldet wird.
- Ohne Ereignisprotokoll wird ein Zurücksetzen der Zähler als Sync-Verlust mit
  `source: counters` gemeldet.

> [!IMPORTANT]
> `data.lua` ist die Schnittstelle der FRITZ!Box-Oberfläche und von AVM **nicht offiziell
> dokumentiert**. Der Parser ist bewusst tolerant gegenüber geänderten Feldnamen, nach
> größeren FRITZ!OS-Updates kann trotzdem eine Anpassung nötig sein. Fehlen nach einem
> Update Werte, bitte ein Issue mit den Diagnosedaten anlegen.

## Fehlersuche

| Problem | Was prüfen |
|---|---|
| *FRITZ!Box nicht erreichbar* | Adresse und Port; erreicht Home Assistant dieses Netz (Firewall-/VLAN-Regeln)? |
| *Anmeldung fehlgeschlagen oder fehlende Rechte* | Kennwort; Benutzer hat „FRITZ!Box Einstellungen“ (und für MyFRITZ! „Zugang aus dem Internet“). |
| *Anmeldung vorübergehend gesperrt* | Die Box sperrt nach Fehlversuchen. Kurz warten. |
| *Keine Kabel-Informationen gefunden* | Kein Kabelmodell, oder dem Benutzer fehlt „FRITZ!Box Einstellungen“. |
| Sync-Sensoren *nicht verfügbar* | Protokollauswertung in den Optionen abgeschaltet oder Protokollseite nicht lesbar. |

**Diagnose:** *Einstellungen › Geräte & Dienste › FRITZ!Box Cable (DOCSIS) › ⋮ › Diagnose
herunterladen* enthält alle Rohdaten ohne Zugangsdaten.

**Debug-Protokoll:**

```yaml
logger:
  logs:
    custom_components.fritzbox_docsis: debug
```

## Entwicklung

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest              # läuft gegen eine simulierte FRITZ!Box
ruff check . && ruff format --check .
```

Die Tests starten eine kleine simulierte FRITZ!Box (`tests/mock_fritzbox.py`) mit
realistischen Kanaldaten und prüfen Anmeldung (PBKDF2 und MD5), abgelaufene Sitzungen, den
Einrichtungsdialog, das Anlegen der Entitäten auf Deutsch und Englisch, Raten,
Zählerrücksetzungen, Sync-Ereignisse samt Entdoppelung und dass jede in `examples/`
verwendete Entität existiert. Siehe [CONTRIBUTING.md](CONTRIBUTING.md).

## Hintergrund und Danksagung

Diese Integration ist eine eigenständige Umsetzung. Sie baut auf öffentlich verfügbarem
Wissen auf:

- **Anmeldung:** Der Challenge-Response-Login über `login_sid.lua` (PBKDF2, MD5 als
  Rückfall) folgt AVMs offizieller
  [Technical Note „Session-ID“](https://fritz.com/fileadmin/user_upload/Global/Service/Schnittstellen/AVM_Technical_Note_-_Session_ID_deutsch_2021-05-03.pdf).
- **Kabeldaten:** `data.lua` mit den Seiten `docInfo` und `log` ist von AVM nicht
  dokumentiert. Der Aufbau ist dank der Community bekannt, zum Beispiel durch den
  [ioBroker-Forenthread zum Auslesen der Pegelwerte](https://forum.iobroker.net/topic/38443/pegelwerte-fritzbox-6490-cable-auslesen)
  und andere Open-Source-Projekte, die dieselbe Schnittstelle nutzen:
  - [pdreker/fritz_exporter](https://github.com/pdreker/fritz_exporter) – Prometheus-Exporter
  - [itsDNNS/docsight](https://github.com/itsDNNS/docsight) – DOCSIS-Monitoring mit Weboberfläche
  - [mulbc/fritzdocsis](https://github.com/mulbc/fritzdocsis) – DOCSIS-Exporter in Go

Danke an alle, die ihre Erkenntnisse geteilt haben.

## Hinweis

Dies ist ein Community-Projekt ohne Verbindung zu AVM GmbH. FRITZ! und FRITZ!Box sind
Marken der AVM GmbH.

## Lizenz

[MIT](LICENSE)
