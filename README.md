# Network Experience 2627: n8n Automation Hub

Dit project bouwt een beheerd automatiseringsplatform met **n8n**, **PostgreSQL**, **SearXNG** en de **n8n AI Sandbox** op een Debian VM in Proxmox.

Het doel is een professionele basisinstallatie waarmee workflows veilig ontwikkeld, getest, beheerd en later gedocumenteerd kunnen worden. Deze README beschrijft de installatie vanaf nul.

## Bestanden in deze repository

Deze repository bevat de benodigde configuratiebestanden om de stack te starten:

| Bestand | Doel | In Git |
|---|---|---|
| `compose.yml` | Docker Compose stack voor n8n, PostgreSQL, SearXNG en de AI Sandbox | Ja |
| `searxng-settings.yml` | Configuratie voor SearXNG | Ja |
| `.env.example` | Voorbeeld van alle benodigde environmentvariabelen | Ja |
| `.env` | Lokale configuratie met echte gegenereerde secrets | Nee |
| `.gitignore` | Voorkomt dat secrets en runtimebestanden in Git terechtkomen | Ja |

> De lokale `.env` is bewust niet bedoeld voor GitHub. Bewaar de waarden ook in de afgesproken vault, vooral `N8N_ENCRYPTION_KEY`.

## Vereisten

Voor je begint heb je nodig:

- Een werkende Proxmox host
- Een Debian 13
- Toegang tot de VM via Proxmox console of SSH
- Minimaal deze VM-specificaties:

| Onderdeel | Minimum |
|---|---:|
| CPU | 2 vCPU's |
| RAM | 4 GB |
| Opslag | 32 GB |
| OS | Debian 13 |

> Gebruik een **VM** en geen LXC-container. De AI Sandbox gebruikt Docker-in-Docker en heeft daarvoor een echte VM nodig.

## Stap 1: Debian VM aanmaken in Proxmox

Maak in Proxmox een nieuwe VM aan met de Debian 13 ISO.

Installeer de nodige updates.
```bash
sudo apt update
sudo apt upgrade -y
```

## Stap 2: Docker en Docker Compose installeren

Installeer eerst de benodigde pakketten:

```bash
sudo apt-get install ca-certificates curl gnupg -y
```

Maak de map voor APT-sleutels aan:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
```

Voeg de officiele Docker GPG-sleutel toe:

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

## Stap 3: Projectmap aanmaken

Maak op de VM een aparte map voor de n8n-stack:

```bash
mkdir ~/n8n
cd ~/n8n
```

Alle volgende bestanden worden in deze map geplaatst.

## Stap 4: Environmentbestand maken

Maak een `.env` bestand:

```bash
nano .env
```

Plaats onderstaande inhoud in het bestand en vervang alle voorbeeldwaarden door eigen sterke secrets.

```env
# n8n en sandbox versies
N8N_VERSION=latest
N8N_SANDBOX_VERSION=1.3.1
N8N_RUNNERS_AUTH_TOKEN=kies_een_random_wachtwoord_voor_runners

# Sandbox secrets
SANDBOX_API_KEYS=kies_een_api_sleutel
SANDBOX_API_RUNNER_REGISTRATION_TOKEN=kies_een_registratie_token
SANDBOX_API_RUNNER_API_KEY=kies_een_runner_sleutel
N8N_SANDBOX_SERVICE_API_KEY=kies_een_api_sleutel

# SearXNG
SEARXNG_SECRET=kies_een_searxng_secret
N8N_INSTANCE_AI_SEARXNG_URL=http://searxng:8080

# PostgreSQL
POSTGRES_USER=n8n_gebruiker
POSTGRES_PASSWORD=kies_een_heel_sterk_wachtwoord
POSTGRES_DB=n8n_database

# n8n beveiliging
N8N_ENCRYPTION_KEY=jouw_super_geheime_encryptiesleutel_van_minimaal_32_tekens
GENERIC_TIMEZONE=Europe/Brussels
```

Belangrijk:

- `N8N_ENCRYPTION_KEY` moet veilig bewaard worden in de afgesproken vault.
- `N8N_SANDBOX_SERVICE_API_KEY` moet dezelfde waarde hebben als `SANDBOX_API_KEYS`.
- Commit nooit echte secrets naar GitHub.

Sla op met `CTRL+O`, bevestig met `Enter` en sluit af met `CTRL+X`.

## Stap 5: SearXNG configureren

Maak het configuratiebestand voor SearXNG:

```bash
nano searxng-settings.yml
```

Plaats deze inhoud:

```yaml
use_default_settings: true
search:
  formats:
    - html
    - json
```

Sla het bestand op en sluit `nano`.

## Stap 6: Docker Compose stack maken

Maak het Compose-bestand:

```bash
nano compose.yml
```

Plaats onderstaande configuratie:

```yaml
volumes:
  n8n-data:
  sandbox-tls:
  db-storage:

services:
  sandbox-certs:
    image: ghcr.io/n8n-io/n8n-sandbox-service-api:${N8N_SANDBOX_VERSION}
    user: '0:0'
    entrypoint: ['sh', '-c']
    command:
      - >
        bootstrap-mtls.sh --out-dir /tls --api-san sandbox-api --control-san-prefix sandbox-runner --world-readable &&
        chown -R sandbox-api:sandbox-api /tls/api && chmod -R a+rX /tls
    volumes:
      - sandbox-tls:/tls

  sandbox-api:
    image: ghcr.io/n8n-io/n8n-sandbox-service-api:${N8N_SANDBOX_VERSION}
    depends_on:
      sandbox-certs:
        condition: service_completed_successfully
    env_file: .env
    environment:
      SANDBOX_API_GRPC_TLS_CERT_FILE: /tls/api/grpc-server.crt
      SANDBOX_API_GRPC_TLS_KEY_FILE: /tls/api/grpc-server.key
      SANDBOX_API_GRPC_TLS_CLIENT_CA_FILE: /tls/api/ca.crt
      SANDBOX_API_RUNNER_CONTROL_GRPC_TLS_CA_FILE: /tls/api/ca.crt
      SANDBOX_API_RUNNER_CONTROL_GRPC_TLS_CERT_FILE: /tls/api/control-grpc-api-client.crt
      SANDBOX_API_RUNNER_CONTROL_GRPC_TLS_KEY_FILE: /tls/api/control-grpc-api-client.key
      SANDBOX_API_RUNNER_CONTROL_GRPC_TLS_SERVER_NAME: sandbox-runner-1
    volumes:
      - sandbox-tls:/tls:ro
    healthcheck:
      test: ['CMD', 'wget', '-qO-', 'http://localhost:8080/healthz']
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 10s

  sandbox-runner-1:
    image: ghcr.io/n8n-io/n8n-sandbox-service-runner-dind:${N8N_SANDBOX_VERSION}
    privileged: true
    depends_on:
      sandbox-api:
        condition: service_healthy
    env_file: .env
    environment:
      SANDBOX_RUNNER_API_GRPC_ADDR: sandbox-api:9090
      SANDBOX_RUNNER_HTTP_BASE_URL: https://sandbox-runner-1:8080
      SANDBOX_RUNNER_CONTROL_GRPC_LISTEN_ADDR: ':9091'
      SANDBOX_RUNNER_CONTROL_GRPC_ADVERTISE_ADDR: sandbox-runner-1:9091
      SANDBOX_RUNNER_ID: runner-1
      SANDBOX_RUNNER_DOCKER_SANDBOX_IMAGE: ghcr.io/n8n-io/n8n-sandbox-service-sandbox:${N8N_SANDBOX_VERSION}
      SANDBOX_RUNNER_REGISTRATION_GRPC_CA_FILE: /tls/runner/ca.crt
      SANDBOX_RUNNER_REGISTRATION_GRPC_CERT_FILE: /tls/runner/grpc-client.crt
      SANDBOX_RUNNER_REGISTRATION_GRPC_KEY_FILE: /tls/runner/grpc-client.key
      SANDBOX_RUNNER_REGISTRATION_GRPC_SERVER_NAME: sandbox-api
      SANDBOX_RUNNER_CONTROL_GRPC_TLS_CERT_FILE: /tls/runner/control-grpc-server.crt
      SANDBOX_RUNNER_CONTROL_GRPC_TLS_KEY_FILE: /tls/runner/control-grpc-server.key
      SANDBOX_RUNNER_CONTROL_GRPC_TLS_CLIENT_CA_FILE: /tls/runner/ca.crt
    volumes:
      - sandbox-tls:/tls:ro

  searxng:
    image: ghcr.io/searxng/searxng:latest
    environment:
      SEARXNG_SECRET: ${SEARXNG_SECRET}
    volumes:
      - ./searxng-settings.yml:/etc/searxng/settings.yml:ro

  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - db-storage:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h localhost -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

  n8n:
    image: docker.io/n8nio/n8n:${N8N_VERSION}
    depends_on:
      sandbox-api:
        condition: service_healthy
      postgres:
        condition: service_healthy
    ports:
      - '5678:5678'
    env_file: .env
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: '5432'
      DB_POSTGRESDB_DATABASE: ${POSTGRES_DB}
      DB_POSTGRESDB_USER: ${POSTGRES_USER}
      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
    volumes:
      - n8n-data:/home/node/.n8n

  runners:
    image: ghcr.io/n8n-io/runners:${N8N_VERSION}
    depends_on:
      - n8n
    environment:
      N8N_RUNNERS_AUTH_TOKEN: ${N8N_RUNNERS_AUTH_TOKEN}
      N8N_RUNNERS_TASK_BROKER_URI: http://n8n:5679
      N8N_RUNNERS_AUTO_SHUTDOWN_TIMEOUT: '15'
```

Sla het bestand op en sluit `nano`.

## Stap 7: Stack starten

Start alle containers:

```bash
sudo docker compose up -d
```

De eerste start kan enkele minuten duren omdat Docker alle images moet downloaden.

Controleer daarna de status:

```bash
sudo docker compose ps
```

De belangrijkste containers moeten actief zijn. Controleer vooral of `postgres` en `sandbox-api` de status `healthy` krijgen.

Bekijk logs wanneer iets niet start:

```bash
sudo docker compose logs -f
```

## Stap 8: n8n openen

Zoek het IP-adres van de Debian VM:

```bash
ip a
```

Open daarna op je eigen computer:

```text
http://<JOUW_VM_IP>:5678
```

Als het n8n-instelscherm verschijnt, is de installatie gelukt.

Maak daarna:

1. Een **Owner account** voor beheer.
2. Een apart **Member account** voor dagelijks gebruik via **Settings > Users**.

## Beheerafspraken

Voor een projectklare installatie horen deze afspraken bij de setup:

- Gebruik het Owner account alleen voor beheer.
- Gebruik een Member account voor normale workflowontwikkeling.
- Bewaar credentials alleen in n8n of in de afgesproken vault.
- Bewaar de `N8N_ENCRYPTION_KEY` apart en veilig.
- Exporteer workflows zonder credentials.
- Commit geen `.env` bestand met echte waarden naar GitHub.
- Documenteer wijzigingen aan workflows in Git.

## Handige beheercommando's

Containers bekijken:

```bash
sudo docker compose ps
```

Logs volgen:

```bash
sudo docker compose logs -f
```

Stack stoppen:

```bash
sudo docker compose down
```

Stack opnieuw starten:

```bash
sudo docker compose up -d
```

Images updaten:

```bash
sudo docker compose pull
sudo docker compose up -d
```

## Back-up aandachtspunten

Voor herstelbaarheid moeten minstens deze onderdelen veilig bewaard worden:

- PostgreSQL databaseback-up
- n8n workflowexports zonder credentials
- `N8N_ENCRYPTION_KEY`
- Documentatie van gebruikte credentials zonder geheime waarden
- Runbook voor restore en credentialrotatie

## Acceptatiecheck

De installatie is klaar wanneer:

- n8n bereikbaar is via `http://<JOUW_VM_IP>:5678`
- PostgreSQL `healthy` is
- `sandbox-api` `healthy` is
- er een Owner account bestaat
- er een apart Member account bestaat
- de encryptiesleutel veilig in de vault staat
- echte secrets niet in GitHub staan
