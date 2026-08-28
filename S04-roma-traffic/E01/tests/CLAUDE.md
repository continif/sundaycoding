# tests/ — come si scrive un test qui
- Marca ogni test: @pytest.mark.unit | integration | contract | e2e.
- Isola con una fixture autouse che azzera lo stato. Niente dipendenze d'ordine.
- Determinismo: golden file in fixtures/, tempo congelato, niente rete reale.
- NON lanciare pytest a mano: usa scripts/run_tests.sh.
