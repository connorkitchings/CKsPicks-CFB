# TensorFlow/Keras for the CFB Model: A Project-Specific Guide

> **Note:** This project currently uses a `scikit-learn` based ensemble model. This guide serves as a reference for a *potential future implementation* of a TensorFlow/Keras model, adapting deep learning concepts to our existing data pipeline.

## 1. TensorFlow/Keras Philosophy in Our Project

TensorFlow, with its high-level Keras API, provides a fast and straightforward way to build deep learning models. Its graph-based execution is highly optimized for production environments.

## 2. The `tf.data` Pipeline: Adapting Our Data

Our data is loaded into `pandas` DataFrames. To build an efficient input pipeline for TensorFlow, we would use the `tf.data` API.

**Project-Specific Data Loading:**
```python
import tensorflow as tf
import pandas as pd
from cfb_model.analysis.loader import load_scored_season_data

# 1. Load our pre-calculated features
df = load_scored_season_data(year=2024, report_dir='./reports')

# 2. Select features and target
feature_columns = ['home_adj_off_epa_pp', 'away_adj_def_sr', 'diff_momentum_3', ...] # Example
target_column = 'spread_target'

# 3. Create a tf.data.Dataset
features_df = df[feature_columns]
target_series = df[target_column]

dataset = tf.data.Dataset.from_tensor_slices((
    dict(features_df), 
    target_series.values
))

# 4. Batch and shuffle the dataset
batched_dataset = dataset.shuffle(buffer_size=len(df)).batch(64)
```

## 3. Building a Model with Keras

A Keras `Sequential` model is the most direct way to build a deep learning model for our tabular data.

### A Potential Keras Model for Our Features

This model would serve as an alternative to our current `scikit-learn` ensembles.

```python
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# To get the number of features:
# from cfb_model.models.features import build_feature_list
# num_features = len(build_feature_list(df))

def create_cfb_model(input_shape):
    model = keras.Sequential([
        layers.Input(shape=(input_shape,)),
        layers.Dense(128, activation='relu'),
        layers.Dropout(0.4),
        layers.Dense(64, activation='relu'),
        layers.Dropout(0.4),
        layers.Dense(1) # Final layer for regression, no activation
    ])
    
    return model

# model = create_cfb_model(num_features)
```

## 4. The Training Workflow

With Keras, compiling and training the model is a high-level, streamlined process.

```python
# 1. Compile the model
model.compile(
    optimizer='adam',
    loss='mean_absolute_error', # Corresponds to MAE
    metrics=['mean_squared_error']
)

# 2. Train the model
# Note: For robust validation, we would manually split data by season
# instead of using a random validation_split.
history = model.fit(
    train_dataset, # Assumes a batched tf.data.Dataset
    epochs=50,
    # validation_data=validation_dataset
)
```

## 5. Model Persistence

Keras provides a simple, standardized format for saving and loading entire models.

```python
# Save the entire model
model_path = 'models/tensorflow/2024/spread_tf_v1'
model.save(model_path)

# Load the model
loaded_model = tf.keras.models.load_model(model_path)

# Make predictions
# predictions = loaded_model.predict(new_data)
```

## 6. TensorFlow vs. Our Current `scikit-learn` Stack

| Aspect | TensorFlow/Keras | `scikit-learn` (Current) |
| :--- | :--- | :--- |
| **API Style** | High-level, declarative (Keras) | Consistent Estimator API (`fit`, `predict`) |
| **Best For** | Deep learning, production deployment | Classical ML, tabular data, interpretability |
| **Data Pipeline** | `tf.data` for performance | `pandas` DataFrames |
| **Deployment** | Excellent (TensorFlow Serving, TFLite) | `joblib` for simple persistence |
| **Our Use Case** | Future research, complex non-linear models | **Current production model**, robust and effective |