import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import HashingVectorizer
from scipy.sparse import hstack, vstack
import joblib
import os
import argparse
from tqdm import tqdm  # Libreria per la barra di avanzamento

# --- Configuration ---
DATA_FILE = 'data/malicious_dataset.csv'
SAMPLE_DATA_FILE = 'data/malicious_dataset.sample.csv'
MODEL_OUTPUT_DIR = 'models'
MODEL_PATH = os.path.join(MODEL_OUTPUT_DIR, 'isolation_forest_model.pkl')
VECTORIZER_PATH = os.path.join(MODEL_OUTPUT_DIR, 'hashing_vectorizer.pkl')

CHUNK_SIZE = 50000
N_FEATURES_URL = 2**18
N_JOBS = -1

def load_and_preprocess_data(file_path, chunksize, url_vectorizer=None):
    """Carica e processa i dati mostrando una barra di avanzamento."""
    print(f"Lettura dati da '{file_path}'...")

    # Calcolo approssimativo del numero di chunk per la barra di progresso
    file_size = os.path.getsize(file_path)
    estimated_chunks = max(1, file_size // (chunksize * 200)) # Stima grossolana

    # Se non viene fornito un vectorizer, ne creiamo uno nuovo
    if url_vectorizer is None:
        url_vectorizer = HashingVectorizer(n_features=N_FEATURES_URL, ngram_range=(1, 3))

    numeric_features_list = []
    url_features_list = []
    original_data_list = []

    # Iteratore con tqdm per vedere il progresso del caricamento
    reader = pd.read_csv(file_path, chunksize=chunksize, on_bad_lines='skip')

    for chunk in tqdm(reader, desc="📦 Caricamento e Vettorizzazione", unit="chunk"):
        original_data_list.append(chunk[['ip', 'user_agent_id', 'url']].copy())

        chunk.fillna({
            'ip_numeric': 0,
            'asn': 0,
            'user_agent_id': 0,
            'url': ''
        }, inplace=True)

        numeric_features = chunk[['ip_numeric', 'asn', 'user_agent_id']].values
        numeric_features_list.append(numeric_features)

        url_features = url_vectorizer.transform(chunk['url'])
        url_features_list.append(url_features)

    print("Concatenazione caratteristiche in corso...")
    X_numeric = np.vstack(numeric_features_list).astype(np.float64)
    X_url = vstack(url_features_list)
    X_features = hstack([X_numeric, X_url]).tocsr()
    original_df = pd.concat(original_data_list, ignore_index=True)

    return X_features, original_df, url_vectorizer

def train_model(X):
    print("Training Isolation Forest in corso (Uso CPU al massimo)...")
    model = IsolationForest(
        n_estimators=100,
        contamination='auto',
        random_state=42,
        n_jobs=N_JOBS
    )
    model.fit(X)
    print("✅ Training completato.")
    return model

def analyze_results(model, X_features, original_df):
    """Analizza i risultati usando batch per evitare freeze del sistema."""
    print("Inizio analisi anomalie...")

    num_rows = X_features.shape[0]
    batch_size = 20000  # Processiamo 20k righe alla volta
    predictions = []
    anomaly_scores = []

    # Barra di avanzamento per la fase critica di predizione
    for i in tqdm(range(0, num_rows, batch_size), desc="🔍 Scansione Traffico", unit="batch"):
        end_idx = min(i + batch_size, num_rows)
        batch = X_features[i:end_idx]

        predictions.extend(model.predict(batch))
        anomaly_scores.extend(model.decision_function(batch))

    original_df['anomaly_score'] = anomaly_scores
    original_df['prediction'] = predictions

    # Classificazione
    score_threshold_malicious = -0.01
    score_threshold_suspicious = 0.0

    def classify(score):
        if score < score_threshold_malicious:
            return 'malicious'
        elif score < score_threshold_suspicious:
            return 'suspicious'
        else:
            return 'good'

    original_df['classification'] = original_df['anomaly_score'].apply(classify)

    print("\n--- Distribuzione Classificazioni ---")
    print(original_df['classification'].value_counts())

    print("\n--- Top 20 Richieste Più Anomale ---")
    anomalous_requests = original_df[original_df['classification'] != 'good'].sort_values(
        by='anomaly_score'
    ).head(20)
    print(anomalous_requests)

if __name__ == "__main__":
    # Parsing degli argomenti da riga di comando
    parser = argparse.ArgumentParser(description='Malicious Traffic Detector - Training e Testing')
    parser.add_argument('--test', type=str, help='File di test da analizzare usando il modello salvato')
    args = parser.parse_args()

    os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)

    if args.test:
        # MODALITÀ TEST: Carica modello salvato e analizza il file di test
        print(f"🧪 MODALITÀ TEST: Analisi del file '{args.test}'")

        # Verifica che il modello e il vectorizer esistano
        if not os.path.exists(MODEL_PATH):
            print(f"❌ Errore: Modello non trovato in '{MODEL_PATH}'")
            print("   Esegui prima il training senza il parametro --test")
            exit(1)

        if not os.path.exists(VECTORIZER_PATH):
            print(f"❌ Errore: Vectorizer non trovato in '{VECTORIZER_PATH}'")
            print("   Esegui prima il training senza il parametro --test")
            exit(1)

        # Carica il modello e il vectorizer salvati
        print("Caricamento modello e vectorizer...")
        trained_model = joblib.load(MODEL_PATH)
        url_vectorizer = joblib.load(VECTORIZER_PATH)
        print("✅ Modello e vectorizer caricati con successo")

        # Carica e preprocessa i dati di test usando il vectorizer salvato
        X_features, original_df, _ = load_and_preprocess_data(args.test, chunksize=CHUNK_SIZE, url_vectorizer=url_vectorizer)

        # Analizza i risultati
        analyze_results(trained_model, X_features, original_df)

        print(f"\n✅ Analisi completata per '{args.test}'.")
    else:
        # MODALITÀ TRAINING: Training normale del modello
        print("🏋️ MODALITÀ TRAINING: Addestramento del modello")

        data_source = DATA_FILE if os.path.exists(DATA_FILE) else SAMPLE_DATA_FILE

        # 1. Caricamento
        X_features, original_df, url_vectorizer = load_and_preprocess_data(data_source, chunksize=CHUNK_SIZE)

        # 2. Training
        trained_model = train_model(X_features)

        # 3. Salvataggio (Veloce)
        print(f"Salvataggio artefatti...")
        joblib.dump(trained_model, MODEL_PATH)
        joblib.dump(url_vectorizer, VECTORIZER_PATH)

        # 4. Analisi con barra di progresso
        analyze_results(trained_model, X_features, original_df)

        print(f"\n✅ Tutto completato. Modello salvato in '{MODEL_OUTPUT_DIR}'.")
