**Nu koppel je Proxmox-MCP aan je nieuwe AI Agent in n8n.** Dit gaat ervan uit dat de container uit de vorige stap draait.

**1. Maak de workflow**

Open n8n en maak een workflow **Proxmox Manager**:

- Voeg **Chat Trigger** en **AI Agent** toe en verbind ze.
- Koppel je **OpenAI Chat Model** aan de agent met je bestaande credential en model `qwen3.8-27b`.
- Gebruik de Chat Trigger als promptbron.

**2. Voeg de MCP-tool toe**

Klik onder de AI Agent op **Tool → + → MCP Client Tool**.

| Instelling | Waarde |
|---|---|
| Transport | **Streamable HTTP** |
| Endpoint | `http://proxmox-mcp:8000/mcp` |
| Authentication | Header Auth |
| Tools to Include | Selected |

Maak bij Header Auth een credential:

| Veld | Waarde |
|---|---|
| Name | `Authorization` |
| Value | `Bearer JOUW_MCP_API_KEY` |

Vervang `JOUW_MCP_API_KEY` door de waarde van **`MCP_API_KEY` uit `.env`**. Behoud één spatie na `Bearer`. Gebruik hier niet je Proxmox-token-secret.

**3. Selecteer eerst alleen deze tools**

```text
get_nodes
get_vms
get_containers
get_storage
```

**4. Test in de chat**

> Toon de nodes, VM’s en containers die je kunt zien. Wijzig niets.

Controleer in de uitvoering of de agent de tools daadwerkelijk aanroept. Als het laden van de tools of de test mislukt, stuur dan de exacte foutmelding zonder geheimen.