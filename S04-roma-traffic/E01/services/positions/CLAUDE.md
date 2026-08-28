# services/positions — vincoli operativi
- NIENTE accesso al DB. Se serve persistenza è un errore di design: fermati.
- Nessuna dipendenza da altri servizi: parla solo col feed e con la sua cache.
