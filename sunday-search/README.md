# sunday-search — S05 "Un pitone in biblioteca"

Il codice della quinta stagione di [Sunday Coding](https://sundaycoding.substack.com):
gli algoritmi di base in Python, fino a un piccolo motore di ricerca su
*Attraverso lo specchio* di Lewis Carroll.

Python 3.12 o successivo.

```
pip install -r requirements.txt
```

## Il libro (da scaricare a parte)

Il testo non è in questo archivio: è un'edizione di Liber Liber con licenza
CC BY-NC-SA 4.0, e la fonte resta loro.

1. Scaricate lo zip HTML da
   <https://liberliber.it/autori/autori-c/lewis-carroll-alias-charles-lutwidge-dodgson/attraverso-lo-specchio/>
   e scompattatelo, per esempio in `attrav_h/`.
2. Generate il corpus:

```
python corpus/estrai_specchio.py attrav_h/ corpus/specchio.jsonl
```

Lewis Carroll, *Attraverso lo specchio*, dall'edizione *Nel Paese dello specchio*,
Istituto Editoriale Italiano, Milano 1914; edizione elettronica Liber Liber,
CC BY-NC-SA 4.0.

## e01 — Ordinamento

Free, *Salutame a sort!*

```
python e01/free_esempi.py
python e01/free_bench_sorted.py
python e01/free_bench_timsort_bisect.py
```

Paid, *S05E01 — Rettangoli in fila*

```
python -m pytest e01/test_ordinamenti.py
python e01/bench_paid.py
python e01/catalogo.py corpus/specchio.jsonl
python e01/tenniel.py attrav_h/
```

- `rettangoli.py`: i quattro modi di rendere ordinabile un rettangolo per area.
- `ordinamenti.py`: insertion, selection, merge, quick e heap sort con i contatori.

## e02 — Alberi

Free, *Le scatole cinesi di Joe Celko*

```
python e02/esempio_piccolo.py
python e02/albero_disco.py /usr/share --db alberi/
python e02/albero_disco.py --db alberi/ --print > /dev/null
python e02/albero_disco.py --db alberi/ --print --da doc --latenza 0.5 > /dev/null
python e02/albero_disco.py --db alberi/ --aggiungi doc/0-leggimi.txt
```

Paid, *S05E02 — Lo schedario*

```
python e02/schedario.py corpus/specchio.jsonl schedario.duckdb
python -m pytest e02/test_schedario.py
python e02/personaggi.py corpus/specchio.jsonl
```

## e03 — Il tokenizzatore

Free, *Come si fa a pezzi un testo*

Serve il dizionario italiano di OpenOffice/LibreOffice (progetto dict-it,
GPL 3, non incluso qui): scaricate l'estensione `.oxt` da
<https://extensions.openoffice.org/project/dict-it>, che è uno zip, e
scompattatela per esempio in `dizionario/`. Poi si genera il vocabolario,
**una volta sola**: i due Parquet in `vocabolario/` servono a tutta la
stagione (e non vanno nel repo, sono GPL anche loro).

```
unzip dict-it.oxt -d dizionario/
python e03/genera_vocabolario.py dizionario/dictionaries vocabolario/   # a pezzi da 100.000 righe
python e03/vocabolario.py vocabolario/ corpus/specchio.jsonl
python e03/tokenizzatore.py corpus/specchio.jsonl vocabolario/
python e03/bpe.py corpus/specchio.jsonl 500
python e03/mistral.py corpus/specchio.jsonl
```

- `genera_vocabolario.py`: dal dizionario e dal thesaurus a `forme.parquet`
  (forma, lemma, origine; 3,2 milioni di righe, 6,3 MB) e `sinonimi.parquet`.
- `vocabolario.py`: confronta il libro col vocabolario con una JOIN in
  DuckDB e stampa il residuo da leggere a mano.
- `tokenizzatore.py`: la strada classica (regex, stopword, Snowball) contro
  quella col vocabolario, con le parole che si confondono.
- `bpe.py`: Byte Pair Encoding in miniatura, addestrato sul libro.
- `mistral.py`: come tagliano l'italiano i tokenizzatori di Mistral (v1 e
  Tekken), con i file inclusi in `mistral-common`.

Paid, *S05E03 — L'indice analitico* (serve il vocabolario generato qui sopra)

```
python e03/indice.py corpus/specchio.jsonl vocabolario/ indice/ "Regina Rossa" "gridare"
python e03/bench_stringhe.py corpus/specchio.jsonl vocabolario/
python e03/bench_indice.py vocabolario/ indice/
python e03/specchio.py corpus/specchio.jsonl vocabolario/
python -m pytest e03/
```

- `stringhe.py`: forza bruta, KMP, Horspool, Rabin-Karp e Aho-Corasick, con `test_stringhe.py`.
- `indice.py`: l'indice invertito con le posizioni in `indice/indice.parquet`, e `cerca()`,
  `cerca_frase()`, `cerca_sql()`, le varianti dal dizionario; i test in `test_indice.py`.
- `specchio.py`: il paragrafo stampato al contrario, i palindromi, le parole bifronti.

I numeri citati negli articoli sono stati misurati con Python 3.13 su una
macchina virtuale a due core: sulla vostra cambiano i millisecondi, non i rapporti.
