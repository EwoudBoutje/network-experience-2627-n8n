# Trello-agent

Deze map bevat [workflow.json](workflow.json): een n8n-chatagent die Trello kan gebruiken en GitHub-informatie kan opvragen. De algemene installatie van n8n staat in de [README van de repository](../README.md).

## Werking

De Chat Trigger stuurt een bericht naar de AI Agent. Die gebruikt een taalmodel, Simple Memory en twee aangesloten tools:

- **Trello MCP** voor de Trello-integratie.
- **GithubMCP** voor GitHub via `https://api.githubcopilot.com/mcp/readonly`.

De aparte node **GitHub MCP** staat ook in de export, maar is niet aangesloten op de agent. De aangesloten GitHub-verbinding gebruikt het readonly-endpoint.

## Benodigdheden

- Een werkende n8n-installatie met de node-types uit de export, waaronder `@n8n/mcp-registry.trello`.
- Toegang tot een taalmodel via een OpenAI-compatibele API.
- Een Trello-account met toegang tot de gewenste borden.
- Een GitHub-token met leestoegang tot de gewenste repositories en toegang tot het ingestelde MCP-endpoint.

## Configuratie

1. Importeer `workflow.json` in n8n.
2. Koppel bij **OpenAI Chat Model** je eigen API-credential. De export gebruikt `qwen3.8-27b`; selecteer een model dat jouw provider aanbiedt en dat toolaanroepen ondersteunt. Stel indien nodig de base URL in de credential in.
3. Koppel bij **Trello MCP** je eigen Trello OAuth2-credential en voltooi de accountkoppeling.
4. Koppel bij **GithubMCP** een **Bearer Auth**-credential met je GitHub-token.
5. Controleer of beide MCP-tools hun tools kunnen laden en op de AI Agent zijn aangesloten.

De credentialnamen en -ID's in de export verwijzen naar de oorspronkelijke installatie. De bijbehorende geheimen worden niet meegeleverd. Voor deze workflow bevat de map geen aparte MCP-server of Docker-stack.

## Testen en gebruiken

Open de chat van de workflow in n8n en test bijvoorbeeld:

- `Toon mijn Trello-borden. Wijzig niets.`
- `Welke lijsten staan op het bord <bordnaam>?`
- `Vat de open issues van <eigenaar>/<repository> samen. Wijzig niets.`

Controleer in de uitvoering of de agent daadwerkelijk de juiste tool aanroept. Test een schrijfactie op Trello alleen op een testbord, bijvoorbeeld door expliciet een testkaart te laten aanmaken.

De export staat op `active: false`. Activeer of publiceer de workflow pas nadat de credentials en tests werken als je de chat buiten de editor wilt gebruiken.

## Problemen oplossen

- **Onbekende node:** zorg dat jouw n8n-installatie de MCP Registry-node voor Trello ondersteunt.
- **Trello geeft geen borden terug:** controleer de accountkoppeling en bordrechten.
- **GitHub geeft een authenticatie- of rechtenfout:** controleer het token, repositorytoegang en toegang tot het MCP-endpoint.
- **De agent gebruikt geen tools:** controleer de toolverbindingen en ondersteuning voor toolaanroepen bij het gekozen model.
