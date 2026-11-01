# Feature Wish: Plaintext Config Secrets verschlüsseln

**Status:** Open  
**Datum:** 2025-10-31

## Problem

`web.tavily_api_key` ist aktuell als Klartext im `config` table der SQLite-Datenbank gespeichert. Im Gegensatz zu anderen API Keys (z.B. Ollama, Image Generation) wird er nicht mit dem AES-Verschlüsselungsschema (`encrypted:gAAAAA...`) verschlüsselt.

## Ziel

Alle API Keys und sensiblen Tokens in `config` (Tavily, Brave, Exa, Firecrawl, Chat Completions etc.) konsistent über das bestehende AES-Verschlüsselungsverfahren schützen.

## To-Do

- [ ] Encryption/Decryption für alle Plaintext-Secrets implementieren
- [ ] Migration der bestehenden Plaintext-Werte (z.B. `web.tavily_api_key`)
- [ ] Config-Lease prüfen: gibt es noch weitere unverschlüsselte Secrets?
