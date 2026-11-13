# Proxmox Agent + Dashboard

Deze map bevat [workflow.json](workflow.json): een n8n-workflow met een Proxmox-chatagent en een webdashboard voor VM-gegevens. Zie de [algemene README](../README.md) voor de centrale n8n-installatie.

## Werking

De workflow heeft twee ingangen:

- **Chat:** Chat Trigger → AI Agent, met een taalmodel, Simple Memory en geselecteerde Proxmox MCP-tools.
- **Dashboard:** Dashboard openen → MCP - VM gegevens → Dashboard HTML → Dashboard tonen.

Beide MCP-nodes gebruiken `http://proxmox-mcp:8000/mcp`. De dashboardtak roept `get_vm_dashboard` aan met `{"include_guest_ips": false}`. De HTML-node verwacht gegevens met `schema_version: 1`, `sampled_at` en een lijst `vms`; een server zonder deze tool of dit uitvoerschema is niet voldoende.

## Benodigdheden

- Een werkende n8n-installatie met de AI-, MCP Client Tool- en MCP Client-nodes uit de export.
- Een OpenAI-compatibele modelprovider met ondersteuning voor toolaanroepen.
- Een bereikbare Proxmox MCP-server met de geselecteerde tools, waaronder `get_vm_dashboard`.
- Een Proxmox API-token met de benodigde leesrechten.
- Een MCP API-key voor n8n en een Basic Auth-account voor het dashboard.

## MCP-server voorbereiden

De MCP-server en zijn Compose-configuratie staan niet in deze map. De [workshop](../workshop-proxmox-agent/) bevat instructies voor de aparte installatie van ProxmoxMCP-Plus:

1. [Docker-netwerk en projectmap](../workshop-proxmox-agent/Stap1.md).
2. [Broncode downloaden](../workshop-proxmox-agent/Stap2.md).
3. [Omgevingsvariabelen en tokens](../workshop-proxmox-agent/Stap3.md).
4. [Proxmox-CA-certificaat](../workshop-proxmox-agent/Stap4.md).
5. [Container starten](../workshop-proxmox-agent/Stap5.md).
6. [MCP koppelen aan n8n](../workshop-proxmox-agent/Stap6.md).

De workshop verwijst naar een eigen `compose.yaml` in `~/Projects/proxmox-agent`; dat bestand wordt hier niet meegeleverd. Controleer ook of jouw serverversie `get_vm_dashboard` met het verwachte schema aanbiedt.

Verbind n8n en `proxmox-mcp` met hetzelfde Docker-netwerk, bijvoorbeeld `proxmox-tools`. De centrale `compose.yml` configureert dit extra netwerk nog niet. Een handmatige `docker network connect` moet na het opnieuw aanmaken van de n8n-container opnieuw worden uitgevoerd, tenzij je het netwerk in Compose vastlegt.

## Workflow configureren

1. Importeer `workflow.json` in n8n.
2. Koppel bij **OpenAI Chat Model** je eigen modelcredential. De export selecteert `qwen3.8-27b`; pas dit aan jouw provider aan.
3. Stel bij **MCP Client** en **MCP - VM gegevens** hetzelfde bereikbare endpoint in. Gebruik Streamable HTTP voor `/mcp`.
4. Koppel aan beide MCP-nodes een **Header Auth**-credential met headernaam `Authorization` en waarde `Bearer <MCP_API_KEY>`.
5. Gebruik hiervoor de API-key van de MCP-server, niet het Proxmox API-token. Het Proxmox-token wordt op de MCP-server ingesteld.
6. Koppel bij **Dashboard openen** een eigen **Basic Auth**-credential.
7. Controleer of de geselecteerde tools geladen worden en `get_vm_dashboard` beschikbaar is.

De export bevat credentialverwijzingen, maar geen werkende secrets voor een nieuwe installatie.

## Dashboard openen

Na het activeren of publiceren van de workflow is de productie-URL:

```text
http://<N8N_HOST>:5678/webhook/proxmox-dashboard
```

Meld je aan met de Basic Auth-gegevens van **Dashboard openen**. Voor een handmatige test gebruik je de test-URL van de webhooknode terwijl n8n op een testaanvraag wacht.

## Testen

1. Vraag in de n8n-chat: `Toon de nodes en VM's die je kunt zien. Wijzig niets.`
2. Controleer of de MCP-tool daadwerkelijk wordt aangeroepen.
3. Test **MCP - VM gegevens** en controleer het uitvoerschema.
4. Open het dashboard en vergelijk de weergegeven VM's met Proxmox.
5. Controleer dat de dashboard-URL om Basic Auth vraagt.

## Problemen oplossen

- **Host niet gevonden of verbinding geweigerd:** controleer het gedeelde Docker-netwerk, de servicenaam en poort 8000.
- **401/403:** controleer de MCP-header; controleer bij Proxmox-fouten ook het API-token en de rechten op de MCP-server.
- **Certificaatfout:** controleer de Proxmox-hostnaam en het vertrouwde CA-certificaat volgens workshopstap 4.
- **Tool ontbreekt of dashboard toont een fout:** controleer de serverversie en het schema van `get_vm_dashboard`.
- **Webhook niet geregistreerd:** activeer/publiceer de workflow of gebruik de test-URL tijdens het luisteren.
