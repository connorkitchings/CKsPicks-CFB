# PyTorch for the CFB Model: A Project-Specific Guide

> **Note:** This project currently uses a `scikit-learn` based ensemble model, which has proven effective and interpretable. This guide serves as a reference for a *potential future implementation* of a PyTorch model, adapting deep learning concepts to our existing data pipeline and feature set.

## 1. PyTorch Philosophy in Our Project

PyTorch's "define-by-run" nature would allow for rapid experimentation with complex model architectures, should we choose to explore deep learning. We could use standard Python control flow to build dynamic models, which might be useful for handling situational features.

## 2. The Tensor: Adapting Our Data

Our data is stored as partitioned CSVs and loaded into `pandas` DataFrames. To use PyTorch, we would convert our feature sets into `torch.Tensor` objects.

**Project-Specific Data Loading:**
```python
import torch
import pandas as pd
from cfb_model.analysis.loader import load_scored_season_data

# 1. Load our pre-calculated features using existing loaders
# This would load data from the `processed/team_week_adj` directory
df = load_scored_season_data(year=2024, report_dir='./reports')

# 2. Select feature columns (e.g., from feature_catalog.md)
feature_columns = ['home_adj_off_epa_pp', 'away_adj_def_sr', 'diff_momentum_3', ...] # Example
target_column = 'spread_target' # or 'total_target'

# 3. Convert to Tensors
features_tensor = torch.tensor(df[feature_columns].values, dtype=torch.float32)
labels_tensor = torch.tensor(df[target_column].values, dtype=torch.float32).view(-1, 1)
```

## 3. Autograd: The Core of Training

PyTorch's automatic differentiation engine, `autograd`, would track operations on our feature tensors to compute gradients, which is standard for any deep learning model. The key takeaway for our workflow is the need to manage gradients explicitly during training:

```python
# Inside the training loop
optimizer.zero_grad()  # Reset gradients before computing loss
loss.backward()        # Compute gradients for the current batch
optimizer.step()       # Update model weights
```

## 4. Building a Model with `torch.nn`

While our current models are `Ridge`, `RandomForestRegressor`, etc., a PyTorch equivalent would be a custom class inheriting from `nn.Module`.

### A Potential PyTorch Model for Our Features

This model would take our pre-calculated features as input.

```python
import torch.nn as nn

class CFBRegressionModel(nn.Module):
    def __init__(self, input_size, hidden_sizes=[128, 64]):
        super().__init__()
        
        # Define layers
        self.fc1 = nn.Linear(input_size, hidden_sizes[0])
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.4)
        self.fc2 = nn.Linear(hidden_sizes[0], hidden_sizes[1])
        
        # Output layer: 1 neuron for regression (predicting the margin or total)
        self.output = nn.Linear(hidden_sizes[1], 1)
    
    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.relu(self.fc2(x))
        # No activation on the final layer for regression
        return self.output(x)

# To instantiate, we would get the number of features from our feature list
# from cfb_model.models.features import build_feature_list
# num_features = len(build_feature_list(df))
# model = CFBRegressionModel(input_size=num_features)
```

## 5. Data Loading: `Dataset` and `DataLoader`

To feed our partitioned data into a PyTorch model efficiently, we would create a custom `Dataset`.

```python
from torch.utils.data import Dataset, DataLoader

class CFBDataset(Dataset):
    """Custom dataset for loading our pre-aggregated football data."""
    
    def __init__(self, dataframe, feature_cols, target_col):
        self.X = torch.tensor(dataframe[feature_cols].values, dtype=torch.float32)
        self.y = torch.tensor(dataframe[target_col].values, dtype=torch.float32).view(-1, 1)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

# In practice:
# train_df = load_data_for_years([2019, 2021, 2022])
# train_dataset = CFBDataset(train_df, feature_list, 'spread_target')
# train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
```

## 6. The Training Loop

The training loop structure would be standard, but it would incorporate our specific components:

-   **Device Management**: Move model and data to GPU if available.
-   **Loss Function**: `nn.MSELoss()` or `nn.L1Loss()` (MAE) are good choices for our regression task.
-   **Optimizer**: `optim.Adam` is a robust default.
-   **Train/Eval Mode**: Use `model.train()` and `model.eval()` to correctly handle layers like `Dropout`.

## 7. Model Persistence

Saving a trained PyTorch model would follow our existing structure.

```python
# Save model weights
model_path = 'models/pytorch/2024/spread_pytorch_v1.pth'
torch.save(model.state_dict(), model_path)

# Load model weights
# num_features = len(build_feature_list(df))
# model = CFBRegressionModel(input_size=num_features)
# model.load_state_dict(torch.load(model_path))
# model.eval() # Set to evaluation mode
```

## 8. PyTorch vs. Our Current `scikit-learn` Stack

| Aspect | PyTorch | `scikit-learn` (Current) |
| :--- | :--- | :--- |
| **Graph** | Dynamic | N/A (algorithms are self-contained) |
| **Debugging** | Native Python debugger | Standard Python debugging |
| **API Style** | Pythonic, object-oriented | Consistent Estimator API (`fit`, `predict`) |
| **Best For** | Deep learning, custom architectures | Classical ML, tabular data, interpretability |
| **Our Use Case** | Future research, complex non-linear models | **Current production model**, robust and effective for tabular features |