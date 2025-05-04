#!/usr/bin/env python3
# train_transaction_fraud_model.py

import argparse
import json
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split

class FraudDataset(Dataset):
    def __init__(self, countries, amounts, labels):
        self.countries = torch.tensor(countries, dtype=torch.long)
        self.amounts = torch.tensor(amounts, dtype=torch.float)
        self.labels = torch.tensor(labels, dtype=torch.float)
    def __len__(self):
        return len(self.labels)
    def __getitem__(self, idx):
        return self.countries[idx], self.amounts[idx], self.labels[idx]

class FraudModel(nn.Module):
    def __init__(self, num_countries, amount_mean, amount_std, embedding_dim=4):
        super(FraudModel, self).__init__()
        # register mean and std for normalization as buffers
        self.register_buffer('amount_mean', torch.tensor(amount_mean, dtype=torch.float))
        self.register_buffer('amount_std',  torch.tensor(amount_std,  dtype=torch.float))
        self.country_emb = nn.Embedding(num_countries, embedding_dim)
        self.fc1 = nn.Linear(embedding_dim + 1, 16)
        self.fc2 = nn.Linear(16, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, country, amount):
        # amount: raw units
        x_country = self.country_emb(country)           # (batch, embedding_dim)
        x_amount_raw = amount.unsqueeze(1)              # (batch,1)
        # log1p and normalize
        x_amount_log = torch.log1p(x_amount_raw)
        x_amount = (x_amount_log - self.amount_mean) / self.amount_std
        x = torch.cat([x_country, x_amount], dim=1)     # (batch, embedding_dim+1)
        x = torch.relu(self.fc1(x))                    # (batch,16)
        x = self.sigmoid(self.fc2(x))                  # (batch,1)
        return x


def main():
    parser = argparse.ArgumentParser(description="Train transaction fraud model")
    parser.add_argument('--data', type=str, default='fraud_data.csv', help='Path to CSV dataset')
    parser.add_argument('--epochs', type=int, default=10, help='Number of training epochs')
    parser.add_argument('--batch_size', type=int, default=64, help='Batch size for training')
    parser.add_argument('--lr', type=float, default=1e-3, help='Learning rate')
    parser.add_argument('--output', type=str, default='fraud_model.onnx', help='Output ONNX model file')
    parser.add_argument('--stats_out', type=str, default='stats.json', help='Output JSON for mean/std')
    args = parser.parse_args()

    # Load and encode
    df = pd.read_csv(args.data)
    countries = df['shipping_country'].unique().tolist()
    country_to_idx = {c: i for i, c in enumerate(countries)}
    df['country_idx'] = df['shipping_country'].map(country_to_idx)

    # Compute normalization stats on log1p(amount_units)
    amount_log = np.log1p(df['amount_units'].astype(float))
    mean = float(amount_log.mean())
    std  = float(amount_log.std())
    # Save stats for serving clients if needed
    with open(args.stats_out, 'w') as f:
        json.dump({'mean': mean, 'std': std}, f)

    # Prepare raw amount_units as feature
    X_country = df['country_idx'].values
    X_amount  = df['amount_units'].astype(float).values
    y = df['label_suspicious'].values

    # Split train/validation
    Xc_train, Xc_val, Xa_train, Xa_val, y_train, y_val = train_test_split(
        X_country, X_amount, y, test_size=0.2, random_state=42
    )

    train_dataset = FraudDataset(Xc_train, Xa_train, y_train)
    val_dataset = FraudDataset(Xc_val, Xa_val, y_val)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size)

    # Initialize model with stats baked in
    model = FraudModel(num_countries=len(countries), amount_mean=mean, amount_std=std)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)

    # Training loop
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        for country, amount, label in train_loader:
            optimizer.zero_grad()
            preds = model(country, amount).squeeze(1)
            loss = criterion(preds, label)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * country.size(0)
        avg_loss = total_loss / len(train_loader.dataset)

        # Validation accuracy
        model.eval()
        correct = 0
        with torch.no_grad():
            for country, amount, label in val_loader:
                preds = model(country, amount).squeeze(1)
                predicted = (preds > 0.5).float()
                correct += (predicted == label).sum().item()
        accuracy = correct / len(val_loader.dataset)
        print(f"Epoch {epoch}/{args.epochs} - Loss: {avg_loss:.4f}, Val Accuracy: {accuracy:.4f}")

    # ONNX export
    dummy_country = torch.tensor([0], dtype=torch.long)
    dummy_amount  = torch.tensor([0.0], dtype=torch.float)  # raw units
    torch.onnx.export(
        model,
        (dummy_country, dummy_amount),
        args.output,
        input_names=['country', 'amount'],
        output_names=['fraud_probability'],
        dynamic_axes={
            'country': {0: 'batch'},
            'amount':  {0: 'batch'}
        },
        opset_version=11
    )
    print(f"Model exported to {args.output}")

if __name__ == '__main__':
    main()
