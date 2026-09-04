# services/positions — vincoli operativi
- Read-only: NIENTE metodi diversi da GET (imposto dal gate_solo_lettura).
- Rifiuta i parametri sconosciuti (gate_parametri_noti): l'inatteso si respinge, non si ignora.
- Lo stato del feed è una macchina a stati (Feed): non introdurre flag booleani paralleli.
- Ogni nuovo controllo trasversale va aggiunto a CATENA, non sparso negli endpoint.
- NIENTE accesso al DB: la cache è in-memory. Il protobuf non esce da qui: ogni risposta è JSON.
- L'URL del feed arriva dalla config (GTFS_RT_URL), mai hardcoded. Deve essere in allowlist.
