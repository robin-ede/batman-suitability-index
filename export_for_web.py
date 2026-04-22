#!/usr/bin/env python3
"""
export_for_web.py
-----------------
Reads existing pipeline outputs and generates web-friendly data files
for the BSI Interactive Story Map (Local HTML).

No ETL logic here — just format conversion to avoid CORS when opening
file:// URLs in a browser.
"""

import json
from pathlib import Path
import numpy as np
import geopandas as gpd


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
WEB_DIR = BASE_DIR / "web"
JS_DIR = WEB_DIR / "js" / "data"


def round_coords(coord, ndigits=5):
    """Recursively round all floating numbers in a nested list (GeoJSON coords)."""
    if isinstance(coord, list):
        return [round_coords(c, ndigits) for c in coord]
    return round(float(coord), ndigits) if coord is not None else coord


def simplify_geojson(gdf, keep_cols):
    """Drop heavy columns, round coordinates, and return GeoJSON dict."""
    gdf = gdf[keep_cols + [gdf.geometry.name]].copy()
    d = json.loads(gdf.to_json())
    # round coords (massively reduces file size)
    for feat in d.get("features", []):
        geom = feat.get("geometry", {})
        if geom:
            geom["coordinates"] = round_coords(geom.get("coordinates", []))
    return d


def write_js(name, obj):
    out = JS_DIR / f"{name}.js"
    content = f"const {name.upper()} = {json.dumps(obj)};\n"
    out.write_text(content)
    print(f"[EXPORT] {out} ({len(content):,} bytes)")


def main():
    JS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Hex grid (BSI results, reprojected to WGS84)
    # ------------------------------------------------------------------
    print("[EXPORT] Loading BSI results...")
    hex_gdf = gpd.read_file(DATA_DIR / "bsi_results.gpkg").to_crs("EPSG:4326")

    hex_keep = [
        "h3_id",
        "crime_count",
        "pop_density_km2",
        "police_dist_m",
        "police_score",
        "industrial",
        "gi_z",
        "hotspot",
        "norm_crime",
        "norm_pop",
        "norm_police",
        "norm_industrial",
        "bsi",
    ]
    hex_geojson = simplify_geojson(hex_gdf, hex_keep)
    write_js("hex_data", hex_geojson)

    # ------------------------------------------------------------------
    # 2. Police stations
    # ------------------------------------------------------------------
    print("[EXPORT] Loading police stations...")
    police_gdf = gpd.read_file(DATA_DIR / "police_stations.gpkg").to_crs("EPSG:4326")
    police_geojson = simplify_geojson(police_gdf, ["name"])
    write_js("police_stations", police_geojson)

    # ------------------------------------------------------------------
    # 3. Industrial zones
    # ------------------------------------------------------------------
    print("[EXPORT] Loading industrial zones...")
    ind_gdf = gpd.read_file(DATA_DIR / "industrial_zones.gpkg").to_crs("EPSG:4326")
    ind_geojson = simplify_geojson(ind_gdf, ["name"])
    write_js("industrial_zones", ind_geojson)

    # ------------------------------------------------------------------
    # 4. Chicago boundary
    # ------------------------------------------------------------------
    boundary_gdf = gpd.read_file(DATA_DIR / "chicago_boundary.gpkg").to_crs("EPSG:4326")
    boundary_geojson = simplify_geojson(boundary_gdf, ["name"])
    write_js("chicago_boundary", boundary_geojson)

    # ------------------------------------------------------------------
    # 5. Top 5 candidates (structured + centroid coordinates)
    # ------------------------------------------------------------------
    top5 = hex_gdf.nlargest(5, "bsi").copy()
    top5_list = []
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        centroid = row.geometry.centroid
        top5_list.append(
            {
                "rank": i,
                "h3_id": row["h3_id"],
                "lat": round(float(centroid.y), 5),
                "lng": round(float(centroid.x), 5),
                "bsi": round(float(row["bsi"]), 4),
                "crime_score": round(float(row["norm_crime"]), 4),
                "pop_score": round(float(row["norm_pop"]), 4),
                "police_score": round(float(row["police_score"]), 4),
                "industrial_score": round(float(row["industrial"]), 4),
                "hotspot": row["hotspot"],
                "crime_count": int(row["crime_count"]),
                "pop_density_km2": round(float(row["pop_density_km2"]), 2),
                "police_dist_m": round(float(row["police_dist_m"]), 1),
            }
        )
    write_js("top5", top5_list)

    # ------------------------------------------------------------------
    # 6. Summary stats for hero section
    # ------------------------------------------------------------------
    stats = {
        "total_crimes": int(hex_gdf["crime_count"].sum()),
        "total_hexes": int(len(hex_gdf)),
        "hot_spots": int((hex_gdf["hotspot"] == "Hot Spot").sum()),
        "cold_spots": int((hex_gdf["hotspot"] == "Cold Spot").sum()),
        "avg_pop_density": round(float(hex_gdf["pop_density_km2"].mean()), 1),
        "avg_bsi": round(float(hex_gdf["bsi"].mean()), 4),
        "max_bsi": round(float(hex_gdf["bsi"].max()), 4),
        "police_stations": int(len(police_gdf)),
        "bsi_formula": {
            "crime_hotspot": 0.35,
            "pop_density": 0.30,
            "police_proximity": 0.20,
            "industrial": 0.15,
        },
        "weight_labels": {
            "crime_hotspot": "Crime Hotspot (Gi*)",
            "pop_density": "Population Density",
            "police_proximity": "Police Proximity",
            "industrial": "Industrial Zone",
        },
        "weight_colors": {
            "crime_hotspot": "#ef4444",
            "pop_density": "#f59e0b",
            "police_proximity": "#3b82f6",
            "industrial": "#10b981",
        },
    }
    write_js("stats", stats)

    print("\n[EXPORT] All web data files written to web/js/data/")


if __name__ == "__main__":
    main()
