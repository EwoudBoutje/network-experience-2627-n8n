# Trello-agent

Deze map bevat [workflow.json](workflow.json): een n8n-chatagent die Trello kan gebruiken en bestanden uit GitHub-repositories kan lezen. De algemene installatie van n8n staat in de [README van de repository](../README.md).

## Werking

De Chat Trigger stuurt een bericht naar de AI Agent. Die gebruikt een taalmodel, Simple Memory en twee aangesloten tools:

- **Trello MCP** voor de Trello-integratie.
- **GitHub MCP** voor het lezen van repositorybestanden via de geselecteerde tool `get_file_contents`.

Beide MCP Registry-nodes zijn aangesloten op de agent. De GitHub-node gebruikt OAuth2 en biedt in deze export alleen `get_file_contents` aan de agent aan.

## Benodigdheden

- Een werkende n8n-installatie met de node-types uit de export, waaronder `@n8n/mcp-registry.trello` en `@n8n/mcp-registry.gitHub`.
- Toegang tot een taalmodel via een OpenAI-compatibele API.
- Een Trello-account met toegang tot de gewenste borden.
- Een GitHub-account dat via OAuth2 gekoppeld kan worden en leestoegang heeft tot de gewenste repositories.

## Configuratie

1. Importeer `workflow.json` in n8n.
2. Koppel bij **OpenAI Chat Model** je eigen API-credential. De export gebruikt `qwen3.8-27b`; selecteer een model dat jouw provider aanbiedt en dat toolaanroepen ondersteunt. Stel indien nodig de base URL in de credential in.
3. Koppel bij **Trello MCP** je eigen Trello OAuth2-credential en voltooi de accountkoppeling.
4. Koppel bij **GitHub MCP** je eigen **GitHub OAuth2**-credential en voltooi de accountkoppeling. Controleer of het gekoppelde account toegang heeft tot de gewenste repositories.
5. Controleer bij **GitHub MCP** dat **Tools to Include** op **Selected** staat en `get_file_contents` is geselecteerd.
6. Controleer of beide MCP-tools hun tools kunnen laden en op de AI Agent zijn aangesloten.

De credentialnamen en -ID's in de export verwijzen naar de oorspronkelijke installatie. De bijbehorende geheimen worden niet meegeleverd. Voor deze workflow bevat de map geen aparte MCP-server of Docker-stack.

## Testen en gebruiken

Open de chat van de workflow in n8n en test bijvoorbeeld:

- `Toon mijn Trello-borden. Wijzig niets.`
- `Welke lijsten staan op het bord <bordnaam>?`
- `Lees README.md uit <eigenaar>/<repository> en vat de inhoud samen. Wijzig niets.`

Het ophalen van issues of andere GitHub-acties valt buiten de geselecteerde toolset van deze export.

Controleer in de uitvoering of de agent daadwerkelijk de juiste tool aanroept. Test een schrijfactie op Trello alleen op een testbord, bijvoorbeeld door expliciet een testkaart te laten aanmaken.

De export staat op `active: false`. Activeer of publiceer de workflow pas nadat de credentials en tests werken als je de chat buiten de editor wilt gebruiken.

## Problemen oplossen

- **Onbekende node:** zorg dat jouw n8n-installatie de MCP Registry-nodes voor Trello en GitHub ondersteunt.
- **Trello geeft geen borden terug:** controleer de accountkoppeling en bordrechten.
- **GitHub geeft een authenticatie- of rechtenfout:** controleer de OAuth2-accountkoppeling en toegang tot de repository.
- **GitHub kan een bestand niet vinden:** controleer de eigenaar, repositorynaam, het bestandspad en eventueel de opgegeven branch of ref.
- **De agent gebruikt geen tools:** controleer de toolverbindingen en ondersteuning voor toolaanroepen bij het gekozen model.
