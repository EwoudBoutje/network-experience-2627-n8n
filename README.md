# Network Experience 2627: n8n Automation Hub

Dit project bouwt een beheerd automatiseringsplatform met **n8n**, **PostgreSQL**, **SearXNG** en de **n8n AI Sandbox** op een Debian VM in Proxmox. Alles draait als Docker Compose stack.

Het doel is een professionele basisinstallatie waarmee workflows veilig ontwikkeld, getest, beheerd en gedocumenteerd kunnen worden. De volledige projectopdracht (Must/Should/Could, acceptatietests, mijlpalen) staat in [`opdracht.md`](opdracht.md).

## Inhoud

- [Inhoud van de repository](#inhoud-van-de-repository)
- [Architectuur](#architectuur)
- [Vereisten](#vereisten)
- [Installatie](#installatie)
- [Workflows](#workflows)
- [Beheer](#beheer)
- [Back-up en restore](#back-up-en-restore)
- [Troubleshooting](#troubleshooting)
- [Acceptatiecheck](#acceptatiecheck)

## Inhoud van de repository

| Bestand / map                       | Doel                                                                 | In Git |
|-------------------------------------|----------------------------------------------------------------------|--------|
| `README.md`                         | Deze handleiding                                                     | Ja     |
| `opdracht.md`                       | Projectopdracht en acceptatiecriteria                                | Ja     |
| `compose.yml`                       | Docker Compose stack: n8n, runners, PostgreSQL, SearXNG, AI Sandbox  | Ja     |
| `searxng-settings.yml`              | Configuratie voor SearXNG (HTML- en JSON-output)                     | Ja     |
| `.env.example`                      | Voorbeeld van alle benodigde environmentvariabelen                   | Ja     |
| `.env`                              | Lokale configuratie met echte, gegenereerde secrets                  | **Nee** |
| `.gitignore`                        | Voorkomt dat secrets en runtimebestanden in Git terechtkomen         | Ja     |
| `step1_n8n_installation`            | TODO: korte omschrijving toevoegen                                   | Ja     |
| `step2_instructions_mcp_client.md`  | TODO: korte omschrijving toevoegen (n8n als MCP-client?)             | Ja     |
| `workshop-proxmox-agent/`           | TODO: korte omschrijving toevoegen                                   | Ja     |

> De lokale `.env` is bewust niet bedoeld voor GitHub. Bewaar de waarden ook in de afgesproken vault, vooral `N8N_ENCRYPTION_KEY`.

## Architectuur

| Service           | Rol                                                                     | Poort (host) |
|-------------------|-------------------------------------------------------------------------|--------------|
| `n8n`             | Workflow engine en beheerinterface                                      | `5678`       |
| `runners`         | n8n task runners voor Code nodes                                        | -            |
| `postgres`        | Database van n8n (PostgreSQL 16)                                        | -            |
| `searxng`         | Zoekmachine voor de AI-functies van n8n                                 | -            |
| `sandbox-certs`   | Eenmalige container die de mTLS-certificaten voor de sandbox aanmaakt   | -            |
| `sandbox-api`     | API van de n8n AI Sandbox                                               | -            |
| `sandbox-runner-1`| Voert sandboxcode uit via Docker-in-Docker (`privileged`)               | -            |

Alleen n8n is bereikbaar van buiten de Docker-omgeving. Alle andere services praten onderling via het interne Docker-netwerk.

## Vereisten

- Een werkende Proxmox host
- Toegang tot de VM via de Proxmox console of SSH
- Een **Debian 13 VM** met minimaal:

| Onderdeel | Minimum   |
|-----------|----------:|
| CPU       | 2 vCPU's  |
| RAM       | 4 GB      |
| Opslag    | 32 GB     |
| OS        | Debian 13 |

> Gebruik een **VM** en geen LXC-container. De AI Sandbox gebruikt Docker-in-Docker en heeft daarvoor een echte VM nodig.

## Installatie

Alle commando's voer je uit op de Debian VM.

### Stap 1: Debian VM aanmaken en updaten

Maak in Proxmox een nieuwe VM aan met de Debian 13 ISO en installeer Debian. Werk daarna het systeem bij en installeer `git`:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install git openssl -y
```

### Stap 2: Docker en Docker Compose installeren

Installeer de benodigde pakketten:

```bash
sudo apt-get install ca-certificates curl gnupg -y
```

Maak de map voor APT-sleutels aan:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
```

Voeg de officiële Docker GPG-sleutel toe:

```bash
curl -fsSL https://download.docker.com/linux/debian/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

Voeg de Docker repository toe:

```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Installeer Docker en de Compose plugin:

```bash
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
```

Controleer de installatie:

```bash
sudo docker version
sudo docker compose version
```

### Stap 3: Repository clonen

Clone deze repository. De bestanden `compose.yml` en `searxng-settings.yml` komen hiermee al op de juiste plaats, je hoeft ze dus **niet** zelf aan te maken.

```bash
git clone https://github.com/EwoudBoutje/network-experience-2627-n8n.git
cd network-experience-2627-n8n
```

Alle volgende commando's voer je uit in deze map.

### Stap 4: Environmentbestand maken

Kopieer het voorbeeldbestand:

```bash
cp .env.example .env
nano .env
```

Vervang **alle** voorbeeldwaarden door eigen sterke secrets. Een veilige willekeurige waarde genereer je zo:

```bash
openssl rand -hex 32
```

| Variabele | Betekenis |
|-----------|-----------|
| `N8N_VERSION` | Versie van de n8n- en runners-image. Pin een vaste versie in plaats van `latest`, zodat de installatie reproduceerbaar blijft. |
| `N8N_SANDBOX_VERSION` | Versie van de AI Sandbox images |
| `N8N_RUNNERS_AUTH_TOKEN` | Gedeeld token tussen `n8n` en `runners` |
| `SANDBOX_API_KEYS` | API-sleutel(s) waarmee `sandbox-api` aanvragen accepteert |
| `N8N_SANDBOX_SERVICE_API_KEY` | API-sleutel die n8n gebruikt. **Moet dezelfde waarde hebben als `SANDBOX_API_KEYS`.** |
| `SANDBOX_API_RUNNER_REGISTRATION_TOKEN` | Token waarmee de runner zich registreert bij de sandbox API |
| `SANDBOX_API_RUNNER_API_KEY` | API-sleutel van de sandbox runner |
| `SEARXNG_SECRET` | Secret van SearXNG |
| `N8N_INSTANCE_AI_SEARXNG_URL` | Interne URL van SearXNG (standaard `http://searxng:8080`, niet aanpassen) |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Databasegebruiker, wachtwoord en databasenaam |
| `N8N_ENCRYPTION_KEY` | Sleutel waarmee n8n credentials versleutelt (minimaal 32 tekens) |
| `GENERIC_TIMEZONE` | Tijdzone voor schedules, standaard `Europe/Brussels` |

Belangrijk:

- `N8N_ENCRYPTION_KEY` moet veilig bewaard worden in de afgesproken vault. Zonder deze sleutel zijn opgeslagen credentials na een restore onbruikbaar.
- Commit nooit echte secrets naar GitHub. `.env` staat in `.gitignore`.

Sla op met `CTRL+O`, bevestig met `Enter` en sluit af met `CTRL+X`.

### Stap 5: Stack starten

```bash
sudo docker compose up -d
```

De eerste start kan enkele minuten duren omdat Docker alle images moet downloaden. Controleer daarna de status:

```bash
sudo docker compose ps
```

Controleer vooral of `postgres` en `sandbox-api` de status `healthy` krijgen. De container `sandbox-certs` hoort na afloop de status `exited (0)` te hebben: dat is correct, het is een eenmalige taak.

Bekijk logs wanneer iets niet start:

```bash
sudo docker compose logs -f
```

### Stap 6: n8n openen

Zoek het IP-adres van de VM:

```bash
ip a
```

Open daarna op je eigen computer:

```text
http://<JOUW_VM_IP>:5678
```

Als het n8n-instelscherm verschijnt, is de installatie gelukt. Zie [Troubleshooting](#troubleshooting) als je een foutmelding over een *secure cookie* krijgt.

> Deze HTTP-verbinding is bedoeld voor de testomgeving. De opdracht vraagt voor productie een niet-publieke beheerinterface en TLS via de afgesproken publicatieroute (reverse proxy). Open poort `5678` dus niet naar buiten.

### Stap 7: Accounts aanmaken

Maak in n8n:

1. Een **Owner account** voor beheer.
2. Een apart **Member account** voor dagelijks gebruik via **Settings > Users**.

## Workflows

> TODO: vul deze tabel aan met de drie gekozen workflows (zie `opdracht.md`: één geplande, één event/webhook, één goedkeuringsflow) en de bestanden in deze repository.

| Workflow | Trigger | Integraties | Bestand |
|----------|---------|-------------|---------|
| TODO     | TODO    | TODO        | TODO    |

Workflows worden **zonder credentials** geëxporteerd en in Git bewaard.

## Beheer

### Beheerafspraken

- Gebruik het Owner account alleen voor beheer.
- Gebruik een Member account voor normale workflowontwikkeling.
- Bewaar credentials alleen in n8n of in de afgesproken vault.
- Bewaar de `N8N_ENCRYPTION_KEY` apart en veilig.
- Exporteer workflows zonder credentials.
- Commit geen `.env` bestand met echte waarden naar GitHub.
- Documenteer wijzigingen aan workflows in Git.

### Handige commando's

Voer deze uit in de projectmap.

| Actie | Commando |
|-------|----------|
| Containers bekijken | `sudo docker compose ps` |
| Logs volgen (alles) | `sudo docker compose logs -f` |
| Logs van één service | `sudo docker compose logs -f n8n` |
| Stack stoppen | `sudo docker compose down` |
| Stack (opnieuw) starten | `sudo docker compose up -d` |
| Images updaten | `sudo docker compose pull && sudo docker compose up -d` |

> Gebruik **niet** `docker compose down -v`: de optie `-v` verwijdert ook de volumes met de database en n8n-data.

## Back-up en restore

Voor herstelbaarheid moeten minstens deze onderdelen veilig bewaard worden:

- PostgreSQL databaseback-up
- n8n workflowexports zonder credentials
- `N8N_ENCRYPTION_KEY`
- Documentatie van gebruikte credentials zonder geheime waarden
- Runbook voor restore en credentialrotatie

**Database back-up maken:**

```bash
sudo docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup_$(date +%F).sql
```

**Database terugzetten** (in een aparte testinstantie of op een lege database):

```bash
cat backup_<DATUM>.sql | sudo docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

Een restore werkt alleen als dezelfde `N8N_ENCRYPTION_KEY` gebruikt wordt als bij de back-up.

## Troubleshooting

| Probleem | Oplossing |
|----------|-----------|
| n8n toont een melding over een *secure cookie* bij `http://<JOUW_VM_IP>:5678` | n8n verwacht HTTPS, behalve op `localhost`. Gebruik een SSH-tunnel (`ssh -L 5678:localhost:5678 <gebruiker>@<JOUW_VM_IP>`) en open `http://localhost:5678`, of publiceer n8n via een reverse proxy met TLS. |
| `sandbox-api` wordt niet `healthy` | Bekijk `sudo docker compose logs sandbox-certs sandbox-api`. Controleer of de waarden in `.env` ingevuld zijn en `N8N_SANDBOX_VERSION` bestaat. |
| `sandbox-runner-1` start niet | Controleer dat je een VM gebruikt en geen LXC-container (Docker-in-Docker). |
| n8n start niet na een wijziging in `.env` | Gebruik `sudo docker compose up -d` opnieuw: Compose maakt de container opnieuw aan met de nieuwe waarden. |
| Credentials werken niet meer na een restore | De `N8N_ENCRYPTION_KEY` is niet dezelfde als bij de back-up. |

## Acceptatiecheck

De installatie is klaar wanneer:

- [ ] n8n bereikbaar is via `http://<JOUW_VM_IP>:5678` (of via de afgesproken TLS-route)
- [ ] `postgres` de status `healthy` heeft
- [ ] `sandbox-api` de status `healthy` heeft
- [ ] er een Owner account bestaat
- [ ] er een apart Member account bestaat
- [ ] de encryptiesleutel veilig in de vault staat
- [ ] echte secrets niet in GitHub staan
- [ ] een database back-up gemaakt en getest is
