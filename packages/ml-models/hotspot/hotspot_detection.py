"""
Hotspot Detection (Phase 8 of the plan)

Runs DBSCAN on lat/long to find geographic clusters of crime, and KDE to
produce a smoothed density grid for heatmap rendering.
"""

import json
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.neighbors import KernelDensity


def load_coords(records_path="records.json"):
    with open(records_path) as f:
        records = json.load(f)
    coords = np.array([[r["latitude"], r["longitude"]] for r in records])
    return records, coords


def run_dbscan(coords, eps=0.005, min_samples=12):
    """
    eps is in degrees (~0.005 deg ~ 550m at this latitude). Tune eps/
    min_samples against your real data until you get 3-5 clusters
    rather than one blob or dozens of fragments.
    """
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(coords)
    return db.labels_  # -1 = noise, 0..n = cluster id


def summarize_clusters(records, coords, labels):
    clusters = {}
    for rec, coord, label in zip(records, coords, labels):
        if label == -1:
            continue  # noise point, not part of a cluster
        clusters.setdefault(label, {"points": [], "fir_numbers": []})
        clusters[label]["points"].append(coord)
        clusters[label]["fir_numbers"].append(rec["fir_number"])

    summary = []
    for cluster_id, data in clusters.items():
        pts = np.array(data["points"])
        summary.append({
            "cluster_id": int(cluster_id),
            "case_count": len(data["fir_numbers"]),
            "center_lat": float(pts[:, 0].mean()),
            "center_lon": float(pts[:, 1].mean()),
            "fir_numbers": data["fir_numbers"],
        })
    return sorted(summary, key=lambda c: -c["case_count"])


def get_hotspots(records_path="records.json", eps=0.005, min_samples=12):
    """This is what /analytics/hotspots would call."""
    records, coords = load_coords(records_path)
    labels = run_dbscan(coords, eps=eps, min_samples=min_samples)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int(np.sum(labels == -1))
    return {
        "n_clusters": n_clusters,
        "n_noise_points": n_noise,
        "clusters": summarize_clusters(records, coords, labels),
    }


def get_density_grid(records_path="records.json", grid_size=50, bandwidth=0.01):
    records, coords = load_coords(records_path)

    kde = KernelDensity(bandwidth=bandwidth, kernel="gaussian")
    kde.fit(coords)

    lat_min, lat_max = coords[:, 0].min(), coords[:, 0].max()
    lon_min, lon_max = coords[:, 1].min(), coords[:, 1].max()

    lat_grid = np.linspace(lat_min, lat_max, grid_size)
    lon_grid = np.linspace(lon_min, lon_max, grid_size)
    lat_mesh, lon_mesh = np.meshgrid(lat_grid, lon_grid)
    grid_points = np.column_stack([lat_mesh.ravel(), lon_mesh.ravel()])

    log_density = kde.score_samples(grid_points)
    density = np.exp(log_density)
    density = (density - density.min()) / (density.max() - density.min())

    return [
        {"lat": float(lat), "lon": float(lon), "intensity": float(d)}
        for lat, lon, d in zip(grid_points[:, 0], grid_points[:, 1], density)
    ]


if __name__ == "__main__":
    result = get_hotspots()
    print(f"Found {result['n_clusters']} clusters, {result['n_noise_points']} noise points")
    for c in result["clusters"]:
        print(f"  Cluster {c['cluster_id']}: {c['case_count']} cases "
              f"@ ({c['center_lat']:.4f}, {c['center_lon']:.4f})")