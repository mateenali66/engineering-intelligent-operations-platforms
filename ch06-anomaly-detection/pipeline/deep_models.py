"""Listing 6-3: reconstruction models, their failure mode, and a density contrast.

Three ideas live here. A plain autoencoder and a transformer autoencoder score
by reconstruction error. That error is a treacherous anomaly score: on tabular
telemetry, anomalies often sit on the data manifold at higher magnitude, the
encoder collapses to a near-constant output, and reconstruction error goes DOWN
on anomalies, which inverts the score. The variance-aware override and the
inversion check below catch that. DAGMM scores by GMM energy instead, which does
not invert. Set batch_first=True on the transformer (the default is
sequence-first, a silent-bug source). Score under torch.no_grad.
"""

from __future__ import annotations

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch import nn

torch.manual_seed(42)


class AutoEncoder(nn.Module):
    """A small MLP autoencoder. Reconstruction error is the anomaly score."""

    def __init__(self, n_features, latent=8):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(n_features, 32), nn.ReLU(), nn.Linear(32, latent)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent, 32), nn.ReLU(), nn.Linear(32, n_features)
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


class TransformerAE(nn.Module):
    """A transformer-encoder autoencoder over the feature vector as a sequence."""

    def __init__(self, n_features, d_model=64, nhead=4, layers=2):
        super().__init__()
        self.embed = nn.Linear(1, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=128,
            dropout=0.1, batch_first=True,  # batch_first avoids a silent bug
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=layers)
        self.head = nn.Linear(d_model, 1)

    def forward(self, x):
        # (batch, features) -> (batch, features, 1) treats each feature as a token
        tokens = self.embed(x.unsqueeze(-1))
        return self.head(self.encoder(tokens)).squeeze(-1)


def train_autoencoder(model, X_train, epochs=20, lr=1e-3):
    """Train on normal-only rows to minimize reconstruction error."""
    x = torch.tensor(X_train, dtype=torch.float32)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        loss = loss_fn(model(x), x)
        loss.backward()
        opt.step()
    return model


def reconstruction_score(model, X, train_errors):
    """Higher means more anomalous, with a guard against collapse."""
    model.eval()
    x = torch.tensor(X, dtype=torch.float32)
    with torch.no_grad():
        recon = model(x)
        errors = ((recon - x) ** 2).mean(dim=1).numpy()
    if recon.var().item() < 1e-6:  # constant output: the collapse signature
        return np.ones(len(X), dtype="float32")
    mu, sigma = train_errors.mean(), train_errors.std() + 1e-8
    return ((errors - mu) / sigma).astype("float32")


def auc_guarding_inversion(y_true, scores):
    """Return AUC and a flag. An AUC below 0.5 means the scores are inverted."""
    auc = roc_auc_score(y_true, scores)
    return {"auc": round(float(auc), 3), "inverted": bool(auc < 0.5)}


# --- Density-based scoring (DAGMM), which does not invert ---------------------

class DAGMM(nn.Module):
    """Compact DAGMM: a compression autoencoder feeding a GMM estimation net.

    The anomaly score is GMM sample energy in the joint space of the latent code
    and the reconstruction features. Density scoring sidesteps the reconstruction
    inversion that sinks the autoencoders above. This is a compact teaching
    version: the encoder trains by reconstruction and the GMM is fit post-hoc, so
    on the small synthetic slice it separates only modestly. The full joint
    energy training that produces the leaderboard numbers is in the Paper 5
    Zenodo deposit (10.5281/zenodo.19462083).
    """

    def __init__(self, n_features, latent=4, n_components=4):
        super().__init__()
        self.enc = nn.Sequential(
            nn.Linear(n_features, 16), nn.Tanh(), nn.Linear(16, latent)
        )
        self.dec = nn.Sequential(
            nn.Linear(latent, 16), nn.Tanh(), nn.Linear(16, n_features)
        )
        self.estim = nn.Sequential(
            nn.Linear(latent + 2, 10), nn.Tanh(), nn.Dropout(0.3),
            nn.Linear(10, n_components), nn.Softmax(dim=1),
        )

    def _joint(self, x):
        z_c = self.enc(x)
        x_hat = self.dec(z_c)
        rel = ((x - x_hat).norm(dim=1) / (x.norm(dim=1) + 1e-8)).unsqueeze(1)
        cos = torch.cosine_similarity(x, x_hat, dim=1).unsqueeze(1)
        return torch.cat([z_c, rel, cos], dim=1), x_hat

    def forward(self, x):
        z, x_hat = self._joint(x)
        return z, x_hat, self.estim(z)


def train_dagmm(model, X_train, epochs=30, lr=1e-3):
    x = torch.tensor(X_train, dtype=torch.float32)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        z, x_hat, _ = model(x)
        loss = ((x - x_hat) ** 2).mean()  # reconstruction drives the encoder
        loss.backward()
        opt.step()
    return model


def dagmm_energy_score(model, X_train, X):
    """Higher energy means lower likelihood under the fitted GMM: more anomalous."""
    model.eval()
    with torch.no_grad():
        z_tr, _, gamma_tr = model(torch.tensor(X_train, dtype=torch.float32))
        phi = gamma_tr.mean(dim=0)
        mu = (gamma_tr.t() @ z_tr) / gamma_tr.sum(dim=0).unsqueeze(1)

        z, _, _ = model(torch.tensor(X, dtype=torch.float32))
        energies = []
        for k in range(mu.shape[0]):
            diff = z - mu[k]
            cov = (diff.t() @ diff) / len(z) + 1e-3 * torch.eye(z.shape[1])
            maha = (diff @ torch.linalg.inv(cov) * diff).sum(dim=1)
            energies.append(phi[k] * torch.exp(-0.5 * maha)
                            / torch.sqrt(torch.linalg.det(cov) + 1e-8))
        likelihood = torch.stack(energies, dim=1).sum(dim=1)
    return (-torch.log(likelihood + 1e-8)).numpy().astype("float32")


class DeepSVDD(nn.Module):
    """Deep SVDD: an encoder that maps normal data near a fixed center.

    The anomaly score is the distance from that center, so it never inverts.
    Like DAGMM, this is a compact teaching version; the full joint training is in
    the Paper 5 Zenodo deposit (10.5281/zenodo.19462083).
    """

    def __init__(self, n_features, latent=8):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, 32, bias=False), nn.ReLU(),
            nn.Linear(32, latent, bias=False),
        )

    def forward(self, x):
        return self.net(x)


def train_deep_svdd(model, X_train, epochs=30, lr=1e-3):
    """Pull normal points toward a fixed center set from the initial encoding."""
    x = torch.tensor(X_train, dtype=torch.float32)
    with torch.no_grad():
        center = model(x).mean(dim=0)  # fixed hypersphere center
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        loss = ((model(x) - center) ** 2).sum(dim=1).mean()
        loss.backward()
        opt.step()
    return model, center


def deep_svdd_score(model, center, X):
    """Distance from the center: higher is more anomalous, no inversion."""
    model.eval()
    with torch.no_grad():
        dist = ((model(torch.tensor(X, dtype=torch.float32)) - center) ** 2).sum(dim=1)
    return dist.numpy().astype("float32")
