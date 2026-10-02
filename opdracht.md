# Project 2 — n8n Automation Hub

## Opdracht

Bouw een beheerd automatiseringsplatform met n8n dat saaie en foutgevoelige opleidingsprocessen veiliger en sneller maakt. De groep levert niet alleen losse demo-workflows op, maar een platform met intake, credentialsbeheer, foutafhandeling, versiebeheer, monitoring, documentatie en eigenaarschap.

## Eerst het proces, dan de workflow

Interview minstens drie stakeholders en verzamel vijf automatiseringskandidaten. Beoordeel per kandidaat frequentie, tijdswinst, foutkans, gevoeligheid van data, benodigde API's en impact bij falen. Selecteer daarna drie workflows met verschillende triggers en integraties.

## Must

- Een afgeschermde n8n-installatie met ondersteunde database, TLS via de afgesproken publicatieroute en een niet-publieke beheerinterface.
- Gescheiden beheer- en uitvoeringsaccounts; credentials uitsluitend in n8n of de afgesproken vault.
- Minstens drie bruikbare workflows:
  1. een geplande controle, bijvoorbeeld service-health, certificaatverval of back-upstatus;
  2. een event- of webhookflow, bijvoorbeeld intake van een supportmelding;
  3. een goedkeuringsflow met menselijke beslissing vóór een impactvolle actie.
- Minstens drie verschillende integraties, waarvan één API met correcte authenticatie en één notificatiekanaal of veilige testsink.
- Validatie van input, idempotentie waar relevant, time-outs, retries met limiet en foutpad.
- Centrale error workflow die eigenaar, correlatie-ID en bruikbare context meldt zonder secrets te lekken.
- Export/versiebeheer van workflowdefinities zonder credentials.
- Back-up en restore van database, encryptiesleutelprocedure en workflowexports.
- Monitoring van beschikbaarheid, executiefouten, wachtrij/doorlooptijd, disk en database.
- Runbooks voor workflow toevoegen, credential roteren, fout analyseren, workflow uitschakelen en restore.

## Voorbeelden van waardevolle workflows

- dagelijkse healthcheck met deduplicatie en automatische incidentregistratie;
- aanvraag van een Minecraft-whitelist met goedkeuring, uitvoering en auditlog;
- wekelijkse controle op verlopen accounts of ontbrekende projecteigenaars;
- certificaatverval opvolgen en tijdig escaleren;
- wijzigingen uit GitHub-issues vertalen naar een changelog of statusupdate;
- LAN-party-inschrijvingen valideren zonder echte persoonsgegevens in de testfase;
- status van back-ups verzamelen en alleen afwijkingen melden.

De groep kiest samen met de opdrachtgever. Een workflow die echte accounts verwijdert, firewallregels wijzigt of massacommunicatie verstuurt, blijft read-only of gebruikt een sandbox tenzij expliciet goedgekeurd.

## Should

- Een ontwikkel- en productieaanpak met promotiechecklist.
- Herbruikbare subworkflows voor logging, notificatie en foutafhandeling.
- Statusdashboard met aantallen geslaagd/mislukt en gemiddelde doorlooptijd.
- Dataretentie en automatische opschoning van executiedata.
- Contracttests met mock API of testsink zodat externe systemen niet worden gespamd.

## Could

- Queue mode met workers, alleen wanneer metingen aantonen dat dit zinvol is binnen het budget.
- SSO als de gedeelde identiteitsdienst dit ondersteunt.
- Automatische deployment van gevalideerde workflowexports.
- Een eenvoudige aanvraagcatalogus voor nieuwe automatiseringen.

## Niet in scope

- productiecredentials in Git of screenshots;
- willekeurige community nodes zonder herkomst- en securitycontrole;
- onbeperkte retries of notificatielussen;
- workflows die zonder menselijke controle destructieve productieacties uitvoeren;
- echte bulkmail tijdens ontwikkeling;
- het kopiëren van persoonsgegevens naar debuglogs.

## Acceptatietests

| Test | Geslaagd wanneer |
|---|---|
| Happy path | alle drie workflows leveren het afgesproken resultaat en een traceerbare execution |
| Ongeldige input | data wordt veilig geweigerd en leidt niet tot gedeeltelijke uitvoering |
| Dubbel event | herhaling veroorzaakt geen dubbele tickets, accounts of berichten waar idempotentie nodig is |
| API-storing | time-out, beperkte retry en error workflow werken zonder storm |
| Goedkeuring | impactvolle stap kan niet zonder bevoegde menselijke beslissing worden uitgevoerd |
| Credentialrotatie | een testcredential wordt vervangen zonder workflowcode of Git-secret te wijzigen |
| Restore | database/configuratie en workflows worden in een aparte testinstantie hersteld |
| Privacy | logs en exports bevatten geen credential of onnodige persoonsgegevens |

## Mijlpalen

- Week 2: procesinventaris en scoringsmatrix.
- Week 4: platformontwerp, dataclassificatie en één technische spike.
- Week 6: drie end-to-end workflows in testmodus.
- Week 8: error handling, monitoring, back-up en credentialprocedure.
- Week 10: stakeholdertest met gemeten tijdswinst en fouten.
- Week 12: productieklare selectie, workflowcatalogus en overdracht.

## Verplichte bewijsstukken

Procesanalyse voor en na, dataflowdiagram, workflowcatalogus, geschoonde exports, credentialmatrix zonder waarden, foutscenario's, meetresultaten, herstelbewijs en beheerrunbooks.