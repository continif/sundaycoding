# TESTS — positions

Piramide: molti unit, qualche contract, pochi integration. Nessun test tocca la rete.

## Unit
- `test_feed.py` — proto2: timestamp assente → None (non 1970); linea assente → None; senza position → scartato.
- `test_gates.py` — `ip_client` ignora XFF se il peer non è fidato; risale la catena da destra; PROXY_FIDATI vuoto → sempre il peer; token spazzatura → None. TokenBucket si esaurisce. Ordine della catena: sicurezza prima.
- `test_stato.py` — alert solo sul fronte; transizione illegale = ValueError; breaker apre alla soglia; un bug nel refresh NON viene ingoiato.

## Contract
- `test_api.py` — /vehicles 200; singolo 404; POST 405; `?admin=1` 400; `?linea=$$$` 422; IP fuori rete 403; feed giù senza cache 503 + Retry-After.

## Integration
- Coperto dai test di `aggiorna_stato` con feed mockato: guasto con cache → STALE; senza cache → 503.

## Lancio
```bash
./scripts/run_tests.sh            # python3 -m pytest -q
```
