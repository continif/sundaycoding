#!/usr/bin/env python3
"""
Traffic Anomaly Detection using a Keras Autoencoder (v2).

This script uses the pre-processed dataset with numeric/categorical features.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import sys
import os

# Force TensorFlow to use CPU only to avoid potential CUDA initialization errors.
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

# --- TensorFlow and Keras Imports ---
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Embedding, Dense, Concatenate, Flatten, Dropout
from tensorflow.keras.utils import Sequence

# --- Scikit-learn and other Imports ---
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences

# --- Configuration with Hardcoded Absolute Paths ---
DATASET_PATH = "/home/francesco/code/astarte/data/malicious_dataset.unique.csv"
MODEL_SAVE_PATH = Path("/home/francesco/code/astarte/astarte/core/ml/saved_autoencoder")

# --- Training Parameters ---
# Using a sample for feasible interactive training.
SAMPLE_SIZE = 500000 
VALIDATION_SPLIT = 0.2
EPOCHS = 15
BATCH_SIZE = 512

# --- Feature Engineering Parameters ---
URL_MAX_LEN = 100
URL_VOCAB_SIZE = 20000

# --- Data Generator Class ---
class DataGenerator(Sequence):
    """Generates data for Keras, handling batch-wise target creation."""
    def __init__(self, data_inputs, embedding_model, batch_size, indices, shuffle=True):
        self.data_inputs = data_inputs
        self.indices = indices
        self.embedding_model = embedding_model
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.on_epoch_end()

    def __len__(self):
        """Denotes the number of batches per epoch."""
        return int(np.ceil(len(self.indices) / self.batch_size))

    def __getitem__(self, index):
        """Generate one batch of data."""
        # Get indices for the current batch
        batch_indices = self.indices[index * self.batch_size:(index + 1) * self.batch_size]
        
        # Get input data for the batch
        batch_inputs = {key: val[batch_indices] for key, val in self.data_inputs.items()}
        
        # Generate target data for the batch on-the-fly
        batch_targets = self.embedding_model.predict(batch_inputs, verbose=0)
        
        return batch_inputs, batch_targets

    def on_epoch_end(self):
        """Updates indices after each epoch."""
        if self.shuffle:
            np.random.shuffle(self.indices)


class TrafficAutoencoder:
    """
    Manages the creation, training, and saving of the traffic autoencoder model.
    """
    def __init__(self):
        self.url_tokenizer = Tokenizer(num_words=URL_VOCAB_SIZE, oov_token="<unk>")
        self.model = None
        self.metadata = {}

    def _load_and_preprocess_data(self):
        """Loads and preprocesses the data for the autoencoder."""
        print(f"Loading dataset and sampling {SAMPLE_SIZE} records...")
        
        # Define the columns to use
        use_cols = ['ip_version', 'asn', 'user_agent_id', 'url']
        df = pd.read_csv(DATASET_PATH, usecols=use_cols, nrows=SAMPLE_SIZE)
        df.dropna(subset=['url'], inplace=True)

        print("Fitting URL tokenizer...")
        df['url'] = df['url'].astype(str)
        self.url_tokenizer.fit_on_texts(df['url'])

        print("Transforming data into sequences and preparing inputs...")
        url_seq = self.url_tokenizer.texts_to_sequences(df['url'])
        url_padded = pad_sequences(url_seq, maxlen=URL_MAX_LEN, padding='post', truncating='post')

        # Prepare inputs, calculating vocab sizes for embeddings
        inputs = {'url': url_padded}
        for col in ['ip_version', 'asn', 'user_agent_id']:
            self.metadata[f'{col}_vocab_size'] = int(df[col].max()) + 1
            inputs[col] = df[col].values
        
        self.metadata['url_vocab_size'] = URL_VOCAB_SIZE
        self.metadata['url_max_len'] = URL_MAX_LEN

        return inputs

    def build_model(self):
        """Builds the Keras autoencoder model."""
        print("Building the autoencoder model...")
        
        # --- Input and Embedding Layers ---
        input_url = Input(shape=(URL_MAX_LEN,), name='url')
        emb_url = Embedding(input_dim=self.metadata['url_vocab_size'], output_dim=32)(input_url)
        flat_url = Flatten()(emb_url)

        input_ip_version = Input(shape=(1,), name='ip_version')
        emb_ver = Embedding(input_dim=self.metadata['ip_version_vocab_size'], output_dim=2)(input_ip_version)
        flat_ver = Flatten()(emb_ver)

        input_asn = Input(shape=(1,), name='asn')
        emb_asn = Embedding(input_dim=self.metadata['asn_vocab_size'], output_dim=50)(input_asn)
        flat_asn = Flatten()(emb_asn)

        input_ua = Input(shape=(1,), name='user_agent_id')
        emb_ua = Embedding(input_dim=self.metadata['user_agent_id_vocab_size'], output_dim=50)(input_ua)
        flat_ua = Flatten()(emb_ua)

        # --- ENCODER ---
        concatenated = Concatenate(name='concatenate')([flat_url, flat_ver, flat_asn, flat_ua])
        
        encoder = Dense(512, activation='relu')(concatenated)
        encoder = Dropout(0.2)(encoder)
        encoder = Dense(256, activation='relu')(encoder)
        bottleneck = Dense(128, activation='relu', name='bottleneck')(encoder)

        # --- DECODER ---
        decoder = Dense(256, activation='relu')(bottleneck)
        decoder = Dense(512, activation='relu')(decoder)
        decoder = Dropout(0.2)(decoder)
        reconstructed = Dense(concatenated.shape[1], activation='linear', name='reconstruction')(decoder)

        all_inputs = [input_url, input_ip_version, input_asn, input_ua]
        self.model = Model(inputs=all_inputs, outputs=reconstructed)
        self.model.compile(optimizer='adam', loss='mean_squared_error')
        self.model.summary()

    def train(self, data):
        """Trains the autoencoder model."""
        print("\n--- Starting Model Training ---")
        
        # Create a helper model to generate the target data (the concatenated embeddings)
        embedding_model = Model(inputs=self.model.inputs, outputs=self.model.get_layer('concatenate').output)

        # Split indices for training and validation
        num_samples = data['url'].shape[0]
        indices = np.arange(num_samples)
        train_indices, val_indices = train_test_split(indices, test_size=VALIDATION_SPLIT, random_state=42)
        
        # Create data generators
        train_generator = DataGenerator(data, embedding_model, BATCH_SIZE, train_indices)
        val_generator = DataGenerator(data, embedding_model, BATCH_SIZE, val_indices, shuffle=False)

        self.model.fit(
            train_generator,
            validation_data=val_generator,
            epochs=EPOCHS,
            shuffle=False, # Shuffling is handled by the generator
            callbacks=[
                tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=3, mode='min', restore_best_weights=True)
            ]
        )
        print("--- Model Training Complete ---")

    def save(self, data):
        """Calculates threshold and saves all necessary artifacts."""
        print("\nCalculating reconstruction error threshold...")

        embedding_model = Model(inputs=self.model.inputs, outputs=self.model.get_layer('concatenate').output)

        num_samples = data['url'].shape[0]
        mse_list = []

        print("Processing data in batches to calculate reconstruction error...")
        num_batches = int(np.ceil(num_samples / BATCH_SIZE))

        for i in range(num_batches):
            start_idx = i * BATCH_SIZE
            end_idx = min((i + 1) * BATCH_SIZE, num_samples)
            
            print(f"  - Processing batch {i+1}/{num_batches}...")

            batch_inputs = {key: val[start_idx:end_idx] for key, val in data.items()}
            
            target_data = embedding_model.predict(batch_inputs, verbose=0)
            reconstructions = self.model.predict(batch_inputs, verbose=0)
            
            batch_mse = np.mean(np.power(target_data - reconstructions, 2), axis=1)
            mse_list.append(batch_mse)

        mse = np.concatenate(mse_list)
        
        # Use the 98th percentile as the anomaly threshold for higher confidence
        threshold = np.quantile(mse, 0.98)
        self.metadata['anomaly_threshold'] = threshold
        print(f"Reconstruction error threshold (98th percentile): {threshold}")

        print(f"Saving model and artifacts to {MODEL_SAVE_PATH}...")
        MODEL_SAVE_PATH.mkdir(parents=True, exist_ok=True)

        self.model.save(MODEL_SAVE_PATH / "traffic_autoencoder.keras")

        with open(MODEL_SAVE_PATH / "url_tokenizer.json", 'w', encoding='utf-8') as f:
            f.write(self.url_tokenizer.to_json())
            
        with open(MODEL_SAVE_PATH / "metadata.json", 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=4)
        
        print("--- All artifacts saved successfully! ---")

def main():
    autoencoder = TrafficAutoencoder()
    processed_data = autoencoder._load_and_preprocess_data()
    autoencoder.build_model()
    autoencoder.train(processed_data)
    autoencoder.save(processed_data)

if __name__ == "__main__":
    main()
