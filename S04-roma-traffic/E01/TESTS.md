# TESTS — cosa lanciare e quando

Regola zero: NON scrivere test al volo. Usa il dispatcher canonico.

- Dopo ogni modifica a un servizio:  `scripts/run_tests.sh <servizio> quick`
- Prima di chiudere una fase:        `scripts/run_tests.sh all ci`
- Un piano singolo:                  `scripts/run_tests.sh <servizio> contract`

`quick` = unit + contract, ordine fisso, feedback in secondi.
`ci`    = tutto, ordine casuale e in parallelo, per stanare i test che si incrociano.

Golden file in tests/fixtures/ (feed reali congelati). NON rigenerarli senza annotarlo in STATUS.md.
