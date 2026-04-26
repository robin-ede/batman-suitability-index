#!/usr/bin/env python3
"""Generate individual full-page figures from saved BSI results for a cleaner report layout."""

from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

DATA_DIR = Path("data/")
IMG_DIR = Path("output/")
CRS_WGS84 = "EPSG:4326"


def load():
    hex_gdf = gpd.read_file(DATA_DIR / "bsi_results.gpkg").to_crs(CRS_WGS84)
    police_gdf = gpd.read_file(DATA_DIR / "police_stations.gpkg").to_crs(CRS_WGS84)
    ind_gdf = gpd.read_file(DATA_DIR / "industrial_zones.gpkg").to_crs(CRS_WGS84)
    return hex_gdf, police_gdf, ind_gdf


def fig1_crime(hex_gdf):
    bounds = hex_gdf.total_bounds
    buf_x = (bounds[2] - bounds[0]) * 0.05
    buf_y = (bounds[3] - bounds[1]) * 0.05

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.set_xlim(bounds[0] - buf_x, bounds[2] + buf_x)
    ax.set_ylim(bounds[1] - buf_y, bounds[3] + buf_y)

    hex_gdf.plot(column="gi_z", cmap="RdYlBu_r", legend=True, ax=ax, edgecolor="none")
    ax.set_title(
        "Crime Hotspots \u2014 Getis-Ord Gi* Z-Score", fontsize=14, fontweight="bold"
    )
    ax.set_axis_off()
    plt.tight_layout()
    fig.savefig(IMG_DIR / "fig1_crime_hotspots.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[FIG] Saved fig1_crime_hotspots.png")


def fig2_population(hex_gdf):
    bounds = hex_gdf.total_bounds
    buf_x = (bounds[2] - bounds[0]) * 0.05
    buf_y = (bounds[3] - bounds[1]) * 0.05

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.set_xlim(bounds[0] - buf_x, bounds[2] + buf_x)
    ax.set_ylim(bounds[1] - buf_y, bounds[3] + buf_y)

    hex_gdf.plot(
        column="pop_density_km2", cmap="YlOrRd", legend=True, ax=ax, edgecolor="none"
    )
    ax.set_title("Population Density (per km\u00b2)", fontsize=14, fontweight="bold")
    ax.set_axis_off()
    plt.tight_layout()
    fig.savefig(IMG_DIR / "fig2_pop_density.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[FIG] Saved fig2_pop_density.png")


def fig3_police(hex_gdf, police_gdf):
    bounds = hex_gdf.total_bounds
    buf_x = (bounds[2] - bounds[0]) * 0.05
    buf_y = (bounds[3] - bounds[1]) * 0.05

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.set_xlim(bounds[0] - buf_x, bounds[2] + buf_x)
    ax.set_ylim(bounds[1] - buf_y, bounds[3] + buf_y)

    hex_gdf.plot(
        column="police_score", cmap="RdYlGn", legend=True, ax=ax, edgecolor="none"
    )
    police_gdf.plot(ax=ax, color="blue", markersize=30, label="Police Stations")
    handles = [
        Line2D(
            [],
            [],
            marker="o",
            color="w",
            markerfacecolor="blue",
            markersize=8,
            label="Police Stations",
        )
    ]
    ax.legend(handles=handles, loc="lower right")
    ax.set_title("Police Proximity Score (Sweet Spot)", fontsize=14, fontweight="bold")
    ax.set_axis_off()
    plt.tight_layout()
    fig.savefig(IMG_DIR / "fig3_police_proximity.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[FIG] Saved fig3_police_proximity.png")


def fig4_bsi(hex_gdf, ind_gdf):
    top5 = hex_gdf.nlargest(5, "bsi")
    centroids = top5.geometry.centroid

    # Limit axes to the buffered extent of the actual data to avoid excess whitespace
    bounds = hex_gdf.total_bounds  # [minx, miny, maxx, maxy]
    buf_x = (bounds[2] - bounds[0]) * 0.05
    buf_y = (bounds[3] - bounds[1]) * 0.05

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.set_xlim(bounds[0] - buf_x, bounds[2] + buf_x)
    ax.set_ylim(bounds[1] - buf_y, bounds[3] + buf_y)

    hex_gdf.plot(column="bsi", cmap="viridis", legend=True, ax=ax, edgecolor="none")

    if not ind_gdf.empty:
        ind_gdf.plot(ax=ax, color="gray", alpha=0.25, label="Industrial Zones")

    xs = np.array(centroids.x)
    ys = np.array(centroids.y)

    ax.scatter(xs, ys, c="red", s=120, zorder=5, edgecolors="white", linewidths=1.5)

    # Radial placement: push each label outward from the cluster centroid so
    # arrows point away from the center and never cross each other.
    cx, cy = xs.mean(), ys.mean()
    raw_angles = np.arctan2(ys - cy, xs - cx)
    # Sort by angle and redistribute evenly so labels don't bunch up.
    order = np.argsort(raw_angles)
    start = raw_angles[order[0]]
    even_angles = start + np.linspace(0, 2 * np.pi, 5, endpoint=False)
    label_angles = np.empty(5)
    for rank, idx in enumerate(order):
        label_angles[idx] = even_angles[rank]

    offset_dist = 70
    for i, (_, row) in enumerate(top5.iterrows()):
        c = row.geometry.centroid
        off = (np.cos(label_angles[i]) * offset_dist,
               np.sin(label_angles[i]) * offset_dist)
        txt = ax.annotate(
            f"#{i + 1}\nBSI {row['bsi']:.3f}",
            (c.x, c.y),
            fontsize=9,
            fontweight="bold",
            color="white",
            ha="center",
            va="center",
            xytext=off,
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.75),
            zorder=6,
            arrowprops=dict(arrowstyle="-", color="white", lw=1.2),
        )
        txt.set_path_effects([pe.withStroke(linewidth=2, foreground="black")])

    handles = [
        Line2D(
            [],
            [],
            marker="s",
            color="w",
            markerfacecolor="gray",
            markersize=8,
            label="Industrial Zones",
        ),
        Line2D(
            [],
            [],
            marker="o",
            color="w",
            markerfacecolor="red",
            markersize=8,
            label="Top 5 Batcave",
        ),
    ]
    ax.legend(handles=handles, loc="lower right")
    ax.set_title(
        "Batman Suitability Index (BSI) \u2014 Top 5 Locations",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_axis_off()
    plt.tight_layout()
    fig.savefig(IMG_DIR / "fig4_bsi_final.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[FIG] Saved fig4_bsi_final.png")


if __name__ == "__main__":
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    hex_gdf, police_gdf, ind_gdf = load()
    fig1_crime(hex_gdf)
    fig2_population(hex_gdf)
    fig3_police(hex_gdf, police_gdf)
    fig4_bsi(hex_gdf, ind_gdf)
    print("\nAll individual figures generated.")
