"""
validate_qaria_pandera.py — Esempio standalone di validazione Pandera
sul dataset qualità aria del Comune di Milano:
https://dati.comune.milano.it/dataset/ds2969-rilevazione-qualita-aria-2026
Scarica un file e chiamalo: qaria_datoariagiornostazione.csv
Richiede: pip install pandera pandas requests
"""

import pandas as pd
import pandera.pandas as pa
from pandera import Column, Check, DataFrameSchema

INQUINANTI = ["C6H6", "CO_8h", "NO2", "O3", "PM10", "PM25", "SO2"]

# --- Schema dichiarativo ---
schema_qaria = DataFrameSchema(
    columns={
        "stazione_id": Column(
            str,
            checks=Check.str_matches(r"^\d+$"),
            nullable=False,
        ),
        "data": Column(
            str,
            checks=Check.str_matches(r"^\d{4}-\d{2}-\d{2}$"),
            nullable=False,
        ),
        "inquinante": Column(
            str,
            checks=Check.isin(INQUINANTI),
            nullable=False,
        ),
        "valore": Column(
            str,
            checks=Check.str_matches(r"^$|^\d+(\.\d+)?$"),
            nullable=False,
        ),
    },
    strict=True,
    ordered=True,
)


def valida(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Ritorna (df_valide, df_quarantena).
    
    lazy=True: Pandera accumula TUTTI gli errori invece di
    sollevare al primo. Senza, otterresti solo il primo problema
    e non avresti modo di costruire la quarantena.
    """
    try:
        df_ok = schema_qaria.validate(df, lazy=True)
        return df_ok, df.iloc[0:0]  # nessuna quarantena
    except pa.errors.SchemaErrors as exc:
        # exc.failure_cases è un DataFrame con un record per check fallito.
        # Estraiamo gli indici univoci delle righe sporche.
        indici_sporchi = (
            exc.failure_cases["index"]
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
        df_quarantena = df.loc[indici_sporchi].copy()
        df_valide = df.drop(index=indici_sporchi)
        return df_valide, df_quarantena


if __name__ == "__main__":
    # NB: dtype=str + keep_default_na=False per non perdere
    # informazione su quale valore è davvero vuoto nel CSV originale.
    df = pd.read_csv(
        "qaria_datoariagiornostazione.csv",
        sep=";",
        dtype=str,
        keep_default_na=False,
    )

    valide, quarantena = valida(df)

    print(f"Totale righe lette: {len(df)}")
    print(f"  → valide:        {len(valide)}")
    print(f"  → quarantenate:  {len(quarantena)}")
    print(f"  → quarantena %:  {100*len(quarantena)/len(df):.1f}%")

    if len(quarantena) > 0:
        print("\nPrime 10 righe quarantenate:")
        print(quarantena.head(10).to_string(index=False))
