# Minecraft-dashboard en whitelist

Deze map bevat [Minecraft_Whitelist.json](Minecraft_Whitelist.json), een n8n-workflow voor een Minecraft-dashboard, een AI-beheerchat en registratie via uitnodigingslinks. In [minecraft-mcp](minecraft-mcp/) staat een MCP-server die consolecommando's via RCON uitvoert.

Daarnaast bevat [Minecraft_Whitelist_Portal](Minecraft_Whitelist_Portal/README.md) een aparte workflow waarmee studenten via Authentik hun Minecraft Java-account kunnen registreren en laten whitelisten.

Zie de [algemene README](../README.md) voor de centrale n8n-installatie.

## Werking

### Minecraft-dashboard en whitelist

- Het dashboard toont serverstatus en online spelers via de Pterodactyl Client API. De statusaanvraag stuurt `minecraft:list`, wacht en leest `logs/latest.log`.
- De AI-chat gebruikt een taalmodel, geheugen, een commandoreferentie en tools voor consolecommando's en logs. Zowel de Pterodactyl-commandotool als de RCON MCP-tool is aangesloten.
- Het whitelistbeheer maakt uitnodigingslinks met een geldigheidsduur, toegangsduur en maximaal aantal registraties. Links kunnen worden ingetrokken of verborgen.
- Een speler vult via de uitnodigingslink zijn Minecraft-gebruikersnaam en echte naam in. De workflow slaat de registratie op, stuurt `whitelist add` en activeert de registratie.
- Een geplande tak zoekt dagelijks om 03:00 verlopen actieve registraties en stuurt `whitelist remove`. Het tijdstip volgt de ingestelde n8n-/workflowtijdzone.

### Minecraft Whitelist Portal

De aparte portal gebruikt Authentik voor de aanmelding van studenten met hun schoolaccount.

- De student meldt zich aan via Authentik.
- Het R-nummer wordt via een vertrouwde HTTP-header aan n8n doorgegeven.
- De student geeft zijn Minecraft Java-gebruikersnaam op.
- De registratie wordt opgeslagen in PostgreSQL en gekoppeld aan het R-nummer.
- De Minecraft-server wordt via de Pterodactyl Client API bijgewerkt.
- Als een student zijn Minecraft-gebruikersnaam wijzigt, wordt de oude gebruikersnaam eerst van de whitelist verwijderd.
- Op 1 februari en 1 september om 03:00 worden de geregistreerde spelers van de whitelist verwijderd en worden de registraties uit PostgreSQL gewist.

De volledige workflow, installatie-instructies en configuratie staan in [Minecraft_Whitelist_Portal/README.md](Minecraft_Whitelist_Portal/README.md).

De workflowexport staat in [Minecraft_Whitelist_Portal/workflow.json](Minecraft_Whitelist_Portal/workflow.json).

## Benodigdheden

- Een werkende n8n-installatie met de gebruikte AI-, MCP-, PostgreSQL- en HTTP-nodes.
- Een OpenAI-compatibele modelprovider met ondersteuning voor toolaanroepen.
- PostgreSQL met het schema `minecraft_whitelist` en passende rechten voor de n8n-databasecredential.
- Een Minecraft-server in Pterodactyl, met een Client API-key die resources kan lezen, commando's kan versturen en `logs/latest.log` kan lezen.
- Voor de MCP-tool: Docker Compose en een bereikbare Minecraft RCON-aansluiting.
- Voor de Minecraft Whitelist Portal: een PostgreSQL-database met de tabel `minecraft_registrations`, een Pterodactyl Client API-credential en een werkende Authentik-integratie via een reverse proxy.

## Workflow importeren en configureren

### Dashboard en whitelist

1. Importeer `Minecraft_Whitelist.json` in n8n en controleer de nodes voordat je de workflow activeert.
2. Koppel bij **OpenAI Chat Model1** je eigen API-credential en een beschikbaar model. De export gebruikt `qwen3.8-27b`.
3. Koppel alle PostgreSQL-nodes aan je eigen databasecredential.
4. Koppel de Pterodactyl HTTP-nodes en HTTP-tools aan een **Header Auth**-credential: headernaam `Authorization`, waarde `Bearer <PTERODACTYL_CLIENT_API_KEY>`.
5. Koppel bij **Webhook**, **Admin GET** en **Admin POST** een eigen **Basic Auth**-credential.
6. Vervang overal `PTERODACTYL_HOST` door het adres van je panel en serveridentifier `5ed5eed2` door die van jouw server. Controleer alle URL's onder `/api/client/servers/`.
7. Vervang `N8N_HOST` in de gegenereerde uitnodigingslink door het adres dat spelers kunnen bereiken. Pas ook protocol en poort aan als jouw n8n via een reverse proxy bereikbaar is.

Credential-ID's uit de export zijn verwijzingen naar de oorspronkelijke installatie; de geheimen moet je zelf instellen.

### Minecraft Whitelist Portal

1. Importeer `Minecraft_Whitelist_Portal/workflow.json` als een aparte workflow in n8n.
2. Controleer de PostgreSQL-nodes en koppel ze aan je eigen PostgreSQL-credential.
3. Koppel de Pterodactyl HTTP-nodes aan je eigen **Header Auth**-credential.
4. Vervang `PTERODACTYL_HOST` in de drie HTTP Request-nodes door het adres van je Pterodactyl-panel.
5. Controleer de serveridentifier in de API-URL en pas deze aan naar jouw Minecraft-server.
6. Configureer de Authentik reverse proxy zodat de juiste studentidentiteit via een vertrouwde header wordt doorgegeven.
7. Verwijder de tijdelijke R-nummerfallback `r0982191` uit de Code-nodes voordat je de workflow in productie gebruikt. Laat de workflow stoppen wanneer de Authentik-identiteit ontbreekt.
8. Controleer de tijdzone van de workflow. Voor de semesterreset moet deze `Europe/Brussels` zijn.
9. Activeer de workflow en test zowel de registratie als de semesterreset in een testomgeving.

**Beveiliging Authentik:** de reverse proxy moet inkomende headers met studentidentiteit verwijderen en zelf de vertrouwde identiteit instellen. Anders kunnen gebruikers mogelijk zelf een R-nummer doorgeven. Zorg er ook voor dat de n8n-webhook niet rechtstreeks toegankelijk is buiten de beveiligde proxy om.

## Database voorbereiden

Het basisschema staat in [minecraft-whitelist-schema.sql](../minecraft-whitelist-schema.sql). Dat bestand gebruikt de bestaande databasegebruiker `n8n_gebruiker` als schema-eigenaar. Controleer die rol en de doeldatabase voordat je het uitvoert.

**Het meegeleverde SQL-schema sluit nog niet volledig aan op deze workflow-export.** Alleen het basisschema uitvoeren is onvoldoende:

- De workflow verwacht op `invites` ook `access_days`, `max_uses`, `use_count` en `deleted_at`.
- Op `registrations` verwacht de workflow ook `access_expires_at`, terwijl het basisschema alleen `expires_at` bevat.
- Het basisschema maakt `registrations.invite_id` uniek. Dat botst met uitnodigingen die meerdere registraties toestaan.
- De queries gebruiken `gen_random_bytes` en `digest`; zorg dat `pgcrypto` beschikbaar is in de database en via het zoekpad kan worden gevonden.

Breng schema en workflow eerst met elkaar in overeenstemming in een testdatabase. De losse node **Execute a SQL query** voegt alleen `access_days` toe en voert geen volledige migratie uit. Het SQL-bestand is ook niet volledig herhaalbaar: het toevoegen van de foreign-keyconstraint aan het einde kan bij een tweede uitvoering mislukken.

### Database voor de Minecraft Whitelist Portal

De portal gebruikt een afzonderlijke tabel `minecraft_registrations`:

```sql
CREATE TABLE IF NOT EXISTS minecraft_registrations (
    id SERIAL PRIMARY KEY,
    r_number VARCHAR(50) NOT NULL UNIQUE,
    minecraft_username VARCHAR(16) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

De registratie wordt gekoppeld aan het R-nummer. Per R-nummer kan er één actieve registratie bestaan. Bij een nieuwe registratie wordt de bestaande Minecraft-gebruikersnaam vervangen.

De semesterreset verwijdert eerst de actieve gebruikers van de Minecraft-whitelist en voert daarna `DELETE FROM minecraft_registrations;` uit. Er wordt dus geen registratiehistoriek bijgehouden.

## Minecraft MCP-server starten

Voer de volgende stappen uit op de Docker-host, vanuit `Minecraft_dashboard/minecraft-mcp`.

Maak daar een eigen `.env` met:

```dotenv
RCON_HOST=<BEREIKBARE_MINECRAFT_HOST>
RCON_PORT=48786
RCON_PASSWORD=<RCON_WACHTWOORD>
MCP_TOKEN=<WILLEKEURIG_TOKEN_VAN_MINSTENS_32_TEKENS>
```

`RCON_PORT` moet overeenkomen met de RCON-poort van jouw Minecraft-server. Schakel RCON in de serverconfiguratie in en zorg dat de container die host en poort kan bereiken. Een token kun je bijvoorbeeld genereren met `openssl rand -hex 32`.

Start en controleer de container:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f minecraft-mcp
```

De Compose-configuratie maakt het netwerk `minecraft-tools` en publiceert geen hostpoort. Verbind n8n met dit netwerk. Vanuit de hoofdmap van de repository kun je de draaiende n8n-container koppelen met:

```bash
docker network connect minecraft-tools "$(docker compose ps -q n8n)"
```

Deze opdracht is voor Bash op de Docker-host. Leg het extra netwerk ook vast in je n8n Compose-configuratie als de koppeling behouden moet blijven bij het opnieuw aanmaken van de container; behoud daarbij het bestaande netwerk voor PostgreSQL en de andere centrale services.

Configureer vervolgens de node **MCP Client**:

- Endpoint: `http://minecraft-mcp:8000/sse`.
- Transport: SSE.
- Authenticatie: Header Auth met `Authorization: Bearer <MCP_TOKEN>`.
- Geselecteerde tool: `minecraft_command`.

De MCP-server staat alle consolecommando's toe. `sent: true` betekent dat een RCON-antwoord is ontvangen; controleer de inhoud van `server_response` om te bepalen of het commando is gelukt. Bij een onzekere uitvoeringsstatus mag je een commando niet automatisch opnieuw versturen.

## Pagina's en endpoints

Na activeren/publiceren zijn de productie-endpoints van het dashboard bereikbaar onder `http://<N8N_HOST>:5678`:

- `GET /webhook/dashboard`: dashboard, met Basic Auth.
- `GET /webhook/mc-status`: serverstatus en spelerslijst.
- `POST /webhook/mc-chat`: chatbericht, bijvoorbeeld JSON `{"message":"Wie is online?"}`.
- `GET /webhook/wl-admin`: whitelistbeheer, met Basic Auth.
- `POST /webhook/wl-admin`: uitnodiging aanmaken, intrekken of verbergen, met Basic Auth.
- `GET /webhook/wl-join?token=<TOKEN>`: registratiepagina voor een uitnodiging.
- `POST /webhook/wl-register`: registratieformulier verwerken.

De Minecraft Whitelist Portal gebruikt een eigen endpoint:

- `GET /webhook/minecraft-portal`: toont het registratieformulier.
- `POST /webhook/minecraft-portal`: verwerkt de Minecraft-gebruikersnaam en registreert de student.

**Let op:** `mc-status` en `mc-chat` hebben in de export geen webhookauthenticatie. De Basic Auth op de dashboardpagina beschermt deze afzonderlijke endpoints niet. Beveilig vooral het chatendpoint voordat je de workflow buiten een vertrouwde omgeving bereikbaar maakt: het kan consolecommando's laten uitvoeren. De registratie-endpoints controleren de uitnodigingstoken in de workflow.

## Testen

1. Controleer eerst het aangepaste databaseschema en de PostgreSQL-credentials in een testomgeving.
2. Test de Pterodactyl-node **Resources** en het lezen van `latest.log`.
3. Test via MCP een leescommando zoals `list` en controleer de serverrespons.
4. Activeer/publiceer de workflow en open het dashboard en whitelistbeheer. De ingebouwde formulieren gebruiken productiepaths onder `/webhook/`.
5. Maak een uitnodiging voor één registratie en registreer een testspeler. Controleer de database én `whitelist list` op de server.
6. Controleer dat een verbruikte, ingetrokken of verlopen link geen registratie meer toestaat.
7. Test de vervaltak met een testregistratie en controleer de whitelist op de server.
8. Test de Minecraft Whitelist Portal met een geldig Authentik-account en een bestaande Minecraft Java-gebruikersnaam.
9. Controleer of een nieuwe registratie voor hetzelfde R-nummer de vorige Minecraft-gebruikersnaam van de whitelist verwijdert.
10. Test de semesterreset in een testomgeving en controleer dat de whitelist en de tabel `minecraft_registrations` worden leeggemaakt.

## Aandachtspunten in de huidige export

- Na **Minecraft whitelist verwijderen** volgt geen database-update naar `expired` of een andere eindstatus. Een verlopen registratie blijft daardoor `active` en kan de volgende dag opnieuw worden opgehaald.
- Een geslaagde Pterodactyl HTTP-aanvraag bevestigt dat het commando is verstuurd; de whitelisttak controleert het daadwerkelijke consoleantwoord niet voordat een registratie wordt geactiveerd.
- **Simple Memory2** gebruikt een vaste sessiesleutel `dashboard`; chatgesprekken delen daardoor hetzelfde geheugen.
- De losse testnode **Test Year Back** wijzigt een vaste spelersregistratie. **Delete al users** wist registraties en uitnodigingen met `TRUNCATE ... CASCADE`. Voer deze nodes niet uit op een database met echte registraties.
- Een lege spelerslijst kan ook ontstaan doordat het verwachte Engelstalige `players online`-logformaat ontbreekt of het antwoord nog niet in het log staat.
- De Minecraft Whitelist Portal gebruikt een tijdelijke testfallback voor het R-nummer. Verwijder deze voordat de workflow in productie gaat.
- De semesterreset verwijdert alle registraties. Controleer daarom de cronplanning en de tijdzone voordat je de workflow activeert.

Deze README beschrijft de meegeleverde bestanden; de genoemde schema- en workflowaanpassingen zijn niet automatisch uitgevoerd.