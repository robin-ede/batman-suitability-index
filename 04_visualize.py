import warnings
warnings.filterwarnings("ignore", message=".*Geometry is in a geographic CRS.*")

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
import folium
from folium import LayerControl
import numpy as np

from config import DATA_DIR, OUTPUT_DIR, CRS_WGS84


def build_folium_dashboard(hex_gdf, police_gdf, industrial_gdf):
    print("[VIZ] Building Folium interactive dashboard...")

    hex_wgs84 = hex_gdf.to_crs(CRS_WGS84)
    police_wgs84 = police_gdf.to_crs(CRS_WGS84)
    ind_wgs84 = industrial_gdf.to_crs(CRS_WGS84)

    center_lat = hex_wgs84.geometry.centroid.y.mean()
    center_lon = hex_wgs84.geometry.centroid.x.mean()
    m = folium.Map(
        location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB dark_matter"
    )

    crime_layer = folium.FeatureGroup(name="Crime Hotspots (Gi* Z-Score)", show=True)
    bsi_layer = folium.FeatureGroup(name="BSI Suitability Score", show=False)

    hotspot_cmap = plt.cm.RdYlBu_r
    vmax_gi = max(abs(hex_wgs84["gi_z"].min()), abs(hex_wgs84["gi_z"].max()))
    if vmax_gi == 0:
        vmax_gi = 1.0

    for _, row in hex_wgs84.iterrows():
        geo = row.geometry.__geo_interface__
        gi_val = row["gi_z"]
        norm_val = (gi_val + vmax_gi) / (2 * vmax_gi)
        color = mcolors.to_hex(hotspot_cmap(norm_val))
        folium.GeoJson(
            geo,
            style_function=lambda x, c=color: {
                "fillColor": c,
                "color": "black",
                "weight": 0.3,
                "fillOpacity": 0.7,
            },
        ).add_to(crime_layer)

    bsi_cmap = plt.cm.viridis
    bsi_max = hex_wgs84["bsi"].max() if hex_wgs84["bsi"].max() > 0 else 1.0

    for _, row in hex_wgs84.iterrows():
        geo = row.geometry.__geo_interface__
        norm_bsi = row["bsi"] / bsi_max
        color = mcolors.to_hex(bsi_cmap(norm_bsi))
        folium.GeoJson(
            geo,
            style_function=lambda x, c=color: {
                "fillColor": c,
                "color": "black",
                "weight": 0.3,
                "fillOpacity": 0.7,
            },
        ).add_to(bsi_layer)

    crime_layer.add_to(m)
    bsi_layer.add_to(m)

    for _, row in police_wgs84.iterrows():
        lat = row.geometry.y
        lon = row.geometry.x
        name = row.get("name", "Police Station")
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>{name}</b>",
            icon=folium.Icon(color="blue", icon="star", prefix="fa"),
        ).add_to(m)

    ind_geo = ind_wgs84.geometry.iloc[0].__geo_interface__
    folium.GeoJson(
        ind_geo,
        style_function=lambda x: {
            "fillColor": "gray",
            "color": "gray",
            "weight": 1,
            "fillOpacity": 0.3,
        },
        name="Industrial Zones",
    ).add_to(m)

    top5 = hex_wgs84.nlargest(5, "bsi")
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        centroid = row.geometry.centroid
        folium.Marker(
            location=[centroid.y, centroid.x],
            popup=f"<b>Batcave #{i}</b><br>BSI: {row['bsi']:.4f}<br>Hotspot: {row['hotspot']}<br>Pop Density: {row['pop_density_km2']:.0f}/km²",
            icon=folium.Icon(color="darkpurple", icon="info-sign"),
        ).add_to(m)

    LayerControl().add_to(m)

    out_path = OUTPUT_DIR / "bsi_dashboard.html"
    m.save(str(out_path))
    print(f"[VIZ] Saved Folium dashboard to {out_path}")


def build_static_maps(hex_gdf, police_gdf, industrial_gdf):
    print("[VIZ] Generating static maps...")
    hex_wgs84 = hex_gdf.to_crs(CRS_WGS84)
    police_wgs84 = police_gdf.to_crs(CRS_WGS84)
    ind_wgs84 = industrial_gdf.to_crs(CRS_WGS84)
    top5 = hex_wgs84.nlargest(5, "bsi")
    top5_centroids = top5.geometry.centroid

    fig, axes = plt.subplots(2, 2, figsize=(20, 20))
    fig.suptitle("Batman Suitability Index (BSI) — Chicago", fontsize=18, fontweight="bold")

    ax1 = axes[0, 0]
    hex_wgs84.plot(column="gi_z", cmap="RdYlBu_r", legend=True, ax=ax1, edgecolor="none")
    ax1.set_title("Crime Hotspots (Gi* Z-Score)")
    ax1.set_axis_off()

    ax2 = axes[0, 1]
    hex_wgs84.plot(column="pop_density_km2", cmap="YlOrRd", legend=True, ax=ax2, edgecolor="none")
    ax2.set_title("Population Density (per km²)")
    ax2.set_axis_off()

    ax3 = axes[1, 0]
    hex_wgs84.plot(column="police_score", cmap="RdYlGn", legend=True, ax=ax3, edgecolor="none")
    police_wgs84.plot(ax=ax3, color="blue", markersize=20, label="Police Stations")
    ax3.set_title("Police Proximity Score (Sweet Spot)")
    ax3.legend(handles=[Line2D([], [], marker="o", color="w", markerfacecolor="blue", markersize=8, label="Police Stations")])
    ax3.set_axis_off()

    ax4 = axes[1, 1]
    hex_wgs84.plot(column="bsi", cmap="viridis", legend=True, ax=ax4, edgecolor="none")
    ind_wgs84.plot(ax=ax4, color="gray", alpha=0.3, label="Industrial Zones")
    ax4.scatter(top5_centroids.x, top5_centroids.y, c="red", s=100, zorder=5, label="Top 5 Batcave")
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        c = row.geometry.centroid
        ax4.annotate(f"#{i}", (c.x, c.y), fontsize=10, fontweight="bold", color="white", ha="center", va="bottom")
    ax4.set_title("Final BSI Score — Top 5 Locations")
    ax4.legend(handles=[
        Line2D([], [], marker="s", color="w", markerfacecolor="gray", markersize=10, label="Industrial Zones"),
        Line2D([], [], marker="o", color="w", markerfacecolor="red", markersize=8, label="Top 5 Batcave"),
    ])
    ax4.set_axis_off()

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out_path = OUTPUT_DIR / "bsi_static_maps.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[VIZ] Saved static maps to {out_path}")

    fig2, ax = plt.subplots(1, 1, figsize=(12, 12))
    hex_wgs84.plot(column="bsi", cmap="viridis", legend=True, ax=ax, edgecolor="none")
    ind_wgs84.plot(ax=ax, color="gray", alpha=0.3)
    ax.scatter(top5_centroids.x, top5_centroids.y, c="red", s=150, zorder=5, edgecolors="white", linewidths=1.5)
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        c = row.geometry.centroid
        ax.annotate(
            f"Batcave #{i}\nBSI: {row['bsi']:.3f}", (c.x, c.y),
            fontsize=9, fontweight="bold", color="white", ha="center", va="bottom",
            xytext=(0, 10), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.7),
        )
    ax.set_title("Batman Suitability Index — Top 5 Batcave Locations", fontsize=16, fontweight="bold")
    ax.set_axis_off()
    out_path2 = OUTPUT_DIR / "bsi_top5_map.png"
    fig2.savefig(out_path2, dpi=300, bbox_inches="tight")
    plt.close(fig2)
    print(f"[VIZ] Saved top-5 map to {out_path2}")


def main():
    hex_gdf = gpd.read_file(DATA_DIR / "bsi_results.gpkg")
    police_gdf = gpd.read_file(DATA_DIR / "police_stations.gpkg")
    industrial_gdf = gpd.read_file(DATA_DIR / "industrial_zones.gpkg")

    build_folium_dashboard(hex_gdf, police_gdf, industrial_gdf)
    build_static_maps(hex_gdf, police_gdf, industrial_gdf)
    print("\n[VIZ] Visualization complete!")


if __name__ == "__main__":
    main()
