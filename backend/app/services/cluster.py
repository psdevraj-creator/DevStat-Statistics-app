from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score
import app.state as _state


def cluster_analysis(columns: list[str], method: str = 'kmeans',
                     n_clusters: int = 3) -> dict[str, Any]:
    """Perform k-means or hierarchical clustering on selected columns.

    Parameters
    ----------
    columns : list[str]
        Numeric column names to cluster on.
    method : str
        'kmeans' or 'hierarchical'.
    n_clusters : int
        Number of clusters (>= 2).

    Returns
    -------
    dict with cluster labels, centroids, silhouette score, interpretation.
    """
    data = _state.current_data
    if data is None or data.empty:
        return {'error': 'No data loaded'}

    valid_cols = [c for c in columns if c in data.columns]
    if len(valid_cols) < 2:
        return {'error': 'At least 2 numeric columns required'}

    X = data[valid_cols].dropna()
    if len(X) < n_clusters:
        return {'error': f'Not enough rows ({len(X)}) for {n_clusters} clusters'}

    if method == 'hierarchical':
        model = AgglomerativeClustering(n_clusters=n_clusters)
        labels = model.fit_predict(X)
    else:
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
        labels = model.fit_predict(X)

    sil = silhouette_score(X, labels) if len(set(labels)) > 1 else 0.0

    cluster_counts = pd.Series(labels).value_counts().sort_index()
    clusters = [
        {'cluster': int(i), 'n': int(cluster_counts.get(i, 0))}
        for i in range(n_clusters)
    ]

    centroids_list = []
    if method == 'kmeans' and hasattr(model, 'cluster_centers_'):
        for i, center in enumerate(model.cluster_centers_):
            centroids_list.append({
                'cluster': int(i),
                **{col: round(float(center[j]), 4) for j, col in enumerate(valid_cols)}
            })

    qual = _interpret_silhouette(sil)
    return {
        'method': method,
        'n_clusters': n_clusters,
        'n_rows': int(len(X)),
        'n_columns': len(valid_cols),
        'columns': valid_cols,
        'silhouette_score': round(float(sil), 4),
        'silhouette_quality': qual,
        'cluster_sizes': clusters,
        'centroids': centroids_list,
        'labels': [int(l) for l in labels],
        'interpretation': (
            f"Cluster analysis ({method}) with {n_clusters} clusters on {len(valid_cols)} variables "
            f"({len(X)} observations). Silhouette score = {sil:.3f} ({qual}). "
            f"{'Cluster structure appears well-separated.' if sil > 0.5 else 'Clusters show moderate overlap.' if sil > 0.25 else 'Cluster structure is weak — try different k or method.'}"
        ),
    }


def _interpret_silhouette(sil: float) -> str:
    if sil >= 0.7:
        return 'Strong'
    elif sil >= 0.5:
        return 'Moderate'
    elif sil >= 0.25:
        return 'Weak'
    return 'Poor'
