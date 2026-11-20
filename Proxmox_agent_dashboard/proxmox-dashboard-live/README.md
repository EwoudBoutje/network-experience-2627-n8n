# Automatisch bijwerkend Proxmox-dashboard in n8n

Dit pakket is gemaakt op basis van jouw bestand Proxmox Agent + Dashboard.json. De bestaande chat-agent, zijn model, geheugen en MCP-credentialverwijzingen zijn behouden. Het dashboard heeft nu een pagina-endpoint en een apart JSON-data-endpoint. De pagina laadt één keer; daarna haalt de browser 30 seconden na iedere afgeronde aanvraag een nieuwe meting op. Zoeken, statusfilter en geopende VM-details blijven staan.

## 1. Workflow importeren

Pak de ZIP uit op je laptop. Importeer Proxmox-Agent-Dashboard-live.json via het workflowmenu → Import from File. Dit is een volledige vervangende workflow, inclusief je agent. De import staat uitgeschakeld zodat er niet meteen een conflict met je bestaande webhook ontstaat.

Kopieer niet nogmaals deze volledige workflow in je bestaande canvas; dan krijg je dubbele chat- en webhooknodes.

Je bestaande Basic Auth-, MCP- en modelcredentials zijn als verwijzing behouden. Als je in dezelfde n8n-instantie importeert, horen die geselecteerd te blijven. Controleer dit in Dashboard openen, MCP - VM gegevens, MCP Client en OpenAI Chat Model.

## 2. Eén nieuwe JWT-credential maken

Maak een nieuwe JWT Auth-credential, bijvoorbeeld Dashboard sessie:

- Key Type: Passphrase
- Algorithm: HS256
- Secret: een uniek willekeurig geheim, bijvoorbeeld de uitvoer van dit commando op Debian:

```bash
openssl rand -hex 32
```

Gebruik dit geheim alleen voor het dashboard, niet voor je MCP of Proxmox-account. Deel de waarde niet in de chat en plak hem niet in de dashboardcode.

Selecteer EXACT DEZELFDE nieuwe credential in deze drie nodes:

1. Dashboard sessie maken (JWT)
2. Dashboard data ophalen (Webhook, Authentication: JWT Auth)
3. Dashboard sessie vernieuwen (JWT)

De sign-nodes zijn al ingesteld met een geldigheidsduur van 900 seconden. Iedere geslaagde data-aanvraag levert een nieuw token op, zodat een open dashboard kan blijven doorwerken. Na meer dan 15 minuten zonder succesvolle tokenvernieuwing kan de pagina opnieuw geopend moeten worden. De ondertekeningssleutel blijft in de n8n-credential; de browser krijgt alleen een tijdelijk token voor dit data-endpoint.

## 3. Data-URL invullen

Open Dashboard data ophalen en kopieer de Production URL. Het pad is proxmox-dashboard-data.

Open Dashboard HTML en wijzig alleen de eerste instelling:

```javascript
const DATA_URL = 'https://JOUW-N8N-ADRES/webhook/proxmox-dashboard-data';
```

Gebruik het n8n-adres dat jouw browser op je laptop kan bereiken. Bij LAN-gebruik kan dat bijvoorbeeld http://IP_VAN_DEBIAN:5678/webhook/proxmox-dashboard-data zijn. Gebruik HTTPS als je n8n via HTTPS opent. localhost werkt alleen wanneer je n8n daadwerkelijk via een lokale tunnel bereikt.

Gebruik hier de Production URL, geen Test URL, Docker-servicenaam of URL van de Proxmox API.

## 4. Controleren en publiceren

De takken horen zo te lopen:

Pagina: Dashboard openen → Dashboard sessie maken → Dashboard HTML → Dashboard tonen.

Data: Dashboard data ophalen → MCP - VM gegevens → Dashboard sessie vernieuwen → Dashboard JSON → Dashboard data tonen.

De AI-agenttak blijft zoals in je oorspronkelijke bestand. De browser hoeft het taalmodel niet aan te roepen voor de metingen.

Sla de nieuwe workflow op. De oude workflow gebruikt hetzelfde /webhook/proxmox-dashboard-pad. Deactiveer/ontpubliceer daarom de oude workflow vlak voordat je deze nieuwe publiceert/activeert. Gebruik geen twee actieve workflows met hetzelfde webhookpad of dezelfde overgenomen chat-trigger.

Publiceer/activeer daarna de nieuwe workflow en open de Production URL van Dashboard openen. Je bestaande dashboardadres en Basic Auth-login blijven hetzelfde, tenzij je ze zelf hebt aangepast.

Test deze opstelling met de Production URL. Twee aparte test-webhooks tegelijk laten luisteren is voor deze opstelling niet handig.

## 5. Test automatische updates

1. Open het dashboard en log in zoals eerder.
2. Wacht op de eerste VM-meting.
3. Vul een zoekfilter in en open de details van een VM.
4. Wacht minstens 30 seconden plus de tijd die de MCP-aanvraag nodig heeft.
5. Het meetmoment bovenaan moet veranderen; waarden die gewijzigd zijn worden vervangen. Filter en details blijven staan.

CPU of RAM hoeven niet iedere meting te verschillen. Gebruik het meetmoment als controle dat er nieuwe data binnenkomt.

In n8n Executions zie je één aanvraag om de pagina te openen, en vervolgens ongeveer twee data-uitvoeringen per minuut per open browserpagina, als de aanvragen snel afgerond worden. Langzame MCP-aanvragen verschuiven de volgende aanvraag: er worden binnen één pagina geen aanvragen tegelijk gestart. Browsers kunnen timers vertragen wanneer een tab niet zichtbaar is of het apparaat slaapt.

## 6. Fouten en toegang

- Bij een mislukte data-aanvraag blijven de laatste waarden zichtbaar met een waarschuwing. Na 30 seconden probeert de pagina opnieuw.
- Bij een verlopen of geweigerde sessie stopt de pagina met aanvragen. Open de dashboard-URL opnieuw voor een nieuwe sessie.
- Wordt de oude pagina nog weergegeven? Controleer of de oude workflow uitstaat en de nieuwe is gepubliceerd; heropen daarna de dashboard-URL.
- Zie je een fout over DATA_URL? Vul de echte Production URL bovenaan Dashboard HTML in.
- 401/403 op het data-endpoint: controleer dat de drie JWT-nodes exact dezelfde dedicated JWT-credential gebruiken met HS256, en dat beide sign-nodes de bestaande exp-expressie behouden.
- Fetch-/CORS-fout: controleer DATA_URL, het schema (http/https), de browserconsole en je eventuele reverseproxy. Die moet OPTIONS en Authorization doorlaten en geen extra Basic Auth-login eisen op het data-endpoint.
- Bij een test via curl zonder JWT hoort het data-endpoint geen VM-gegevens terug te geven.
- 502: bekijk de uitvoer van MCP - VM gegevens; ook Docker-netwerk proxmox-tools en de verbinding naar Proxmox moeten blijven werken.

De data-webhook heeft Allowed Origins (CORS) op *. Dit is nodig voor de sandboxed n8n-pagina; de browser gebruikt credentials: omit en stuurt expliciet het tijdelijke Bearer-token mee. CORS vervangt authenticatie niet: JWT Auth moet ingeschakeld blijven.

Het volledige proxmox-token, de MCP-credential en het Basic Auth-wachtwoord staan niet in de gegenereerde browserpagina. Gebruik HTTPS voor toegang over een onbetrouwbaar netwerk. Een actieve browsersessie mag het tijdelijke token gebruiken om de zichtbare VM-gegevens opnieuw op te halen; geef de JWT-credential daarom geen andere functie.

De metingen worden niet historisch opgeslagen door de dashboardcode. n8n kan wel uitvoeringsgegevens bewaren volgens je bestaande workflowinstellingen. Overweeg succesvolle data-uitvoeringen niet te bewaren als je veel pagina's openhoudt.

## Verificatie

JavaScript-syntax, MCP-parsing, data-updates met gesimuleerde responses, behoud van filters/details, foutafhandeling, verlopen sessies, veilige HTML-inbedding, voorkomen van overlappende polls, nodeverbindingen en behoud van je bestaande agentconfiguratie zijn lokaal gecontroleerd. Een echte browsertest werd door de uitvoeringsomgeving geblokkeerd. De JWT-credentials, CORS en de volledige live uitvoering moeten daarom na import in jouw n8n worden gecontroleerd.
