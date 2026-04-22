import geopandas as gpd
import pandas as pd
import h3
import numpy as np
from shapely.geometry import Polygon, mapping

from config import (
    DATA_DIR,
    CRS_WGS84,
    CRS_METRIC,
    H3_RESOLUTION,
    CENSUS_POP_VAR,
    POLICE_PROXIMITY_SWEET_SPOT_MIN_M,
    POLICE_PROXIMITY_SWEET_SPOT_MAX_M,
)


def load_data():
    print("[PROCESS] Loading raw data...")
    crimes_df = pd.read_parquet(DATA_DIR / "crimes_raw.parquet")
    tracts_gdf = gpd.read_file(DATA_DIR / "census_tracts.gpkg")
    police_gdf = gpd.read_file(DATA_DIR / "police_stations.gpkg")
    industrial_gdf = gpd.read_file(DATA_DIR / "industrial_zones.gpkg")
    boundary_gdf = gpd.read_file(DATA_DIR / "chicago_boundary.gpkg")
    return crimes_df, tracts_gdf, police_gdf, industrial_gdf, boundary_gdf


def reproject(gdf, target_crs=CRS_METRIC):
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_WGS84)
    if gdf.crs != target_crs:
        gdf = gdf.to_crs(target_crs)
    return gdf


def build_hex_grid(boundary_gdf):
    print(f"[PROCESS] Building H3 grid at resolution {H3_RESOLUTION}...")
    boundary_wgs84 = boundary_gdf.to_crs(CRS_WGS84)
    chicago_geom = boundary_wgs84.geometry.iloc[0]
    geojson_geom = mapping(chicago_geom)

    if geojson_geom["type"] == "Polygon":
        cells = h3.geo_to_cells(geojson_geom, res=H3_RESOLUTION)
    else:
        cells = set()
        if geojson_geom["type"] == "MultiPolygon":
            for poly in geojson_geom["coordinates"]:
                single = {"type": "Polygon", "coordinates": poly}
                cells.update(h3.geo_to_cells(single, res=H3_RESOLUTION))

    hex_records = []
    for cell_id in cells:
        coords = [(lng, lat) for lat, lng in h3.cell_to_boundary(cell_id)]
        hex_records.append({"h3_id": cell_id, "geometry": Polygon(coords + [coords[0]])})

    hex_gdf = gpd.GeoDataFrame(hex_records, crs=CRS_WGS84)
    hex_gdf = hex_gdf.to_crs(CRS_METRIC)
    print(f"[PROCESS] Created {len(hex_gdf)} hexagonal cells")
    return hex_gdf


def assign_crime_counts(hex_gdf, crimes_df):
    print("[PROCESS] Assigning crime counts to hexes...")
    geometry = gpd.points_from_xy(crimes_df["longitude"], crimes_df["latitude"])
    crimes_gdf = gpd.GeoDataFrame(crimes_df, geometry=geometry, crs=CRS_WGS84)

    hex_wgs84 = hex_gdf.to_crs(CRS_WGS84)
    crimes_in_hex = gpd.sjoin(
        crimes_gdf, hex_wgs84[["h3_id", "geometry"]], how="left", predicate="within"
    )
    crime_counts = crimes_in_hex.groupby("h3_id").size().reset_index(name="crime_count")

    hex_gdf = hex_gdf.merge(crime_counts, on="h3_id", how="left")
    hex_gdf["crime_count"] = hex_gdf["crime_count"].fillna(0).astype(int)

    print(f"[PROCESS] Total crimes assigned: {hex_gdf['crime_count'].sum():,}")
    return hex_gdf


def assign_population_density(hex_gdf, tracts_gdf):
    print(
        "[PROCESS] Assigning population density to hexes via area-weighted interpolation..."
    )
    tracts_m = reproject(tracts_gdf)
    hex_m = hex_gdf.copy()

    tracts_m["tract_area"] = tracts_m.geometry.area
    tracts_m = tracts_m[
        [CENSUS_POP_VAR, "pop_density_km2", "tract_area", "geometry"]
    ].copy()
    tracts_m = tracts_m.rename(columns={CENSUS_POP_VAR: "tract_pop"})

    intersections = gpd.overlay(hex_m, tracts_m, how="intersection")
    intersections["intersect_area"] = intersections.geometry.area

    intersections["weight"] = (
        intersections["intersect_area"] / intersections["tract_area"]
    )
    intersections["pop_contribution"] = (
        intersections["tract_pop"] * intersections["weight"]
    )

    hex_pop = intersections.groupby("h3_id")["pop_contribution"].sum().reset_index()
    hex_pop = hex_pop.rename(columns={"pop_contribution": "tract_pop"})

    hex_gdf = hex_gdf.merge(hex_pop, on="h3_id", how="left")
    hex_gdf["tract_pop"] = hex_gdf["tract_pop"].fillna(0)

    hex_gdf["hex_area_km2"] = hex_gdf.geometry.area / 1e6
    hex_gdf["pop_density_km2"] = hex_gdf["tract_pop"] / hex_gdf["hex_area_km2"]
    hex_gdf["pop_density_km2"] = (
        hex_gdf["pop_density_km2"].replace([np.inf, -np.inf], 0).fillna(0)
    )

    print(
        f"[PROCESS] Population density assigned (mean: {hex_gdf['pop_density_km2'].mean():.0f} /km²)"
    )
    return hex_gdf


def assign_police_proximity(hex_gdf, police_gdf):
    print("[PROCESS] Computing police station proximity (sweet spot scoring)...")
    hex_centroids = hex_gdf.geometry.centroid
    police_pts = police_gdf.geometry.union_all()

    distances = hex_centroids.distance(police_pts)
    hex_gdf["police_dist_m"] = distances

    min_d = POLICE_PROXIMITY_SWEET_SPOT_MIN_M
    max_d = POLICE_PROXIMITY_SWEET_SPOT_MAX_M

    score = np.zeros(len(distances))
    in_sweet = (distances >= min_d) & (distances <= max_d)
    score[in_sweet] = 1.0

    too_close = distances < min_d
    score[too_close] = distances[too_close] / min_d

    too_far = distances > max_d
    max_dist = distances.max()
    far_range = max_dist - max_d if max_dist > max_d else 1.0
    score[too_far] = 1.0 - ((distances[too_far] - max_d) / far_range) * 0.5

    hex_gdf["police_score"] = np.clip(score, 0, 1)

    print(f"[PROCESS] Police proximity scored (sweet spot: {min_d}-{max_d}m)")
    return hex_gdf


def assign_industrial(hex_gdf, industrial_gdf):
    print("[PROCESS] Assigning industrial zone intersection...")
    industrial_m = reproject(industrial_gdf)

    hits = gpd.sjoin(hex_gdf[["geometry"]], industrial_m[["geometry"]], how="inner", predicate="intersects")
    hex_gdf["industrial"] = hex_gdf.index.isin(hits.index).astype(int)

    n_industrial = hex_gdf["industrial"].sum()
    print(f"[PROCESS] {n_industrial} hexes overlap industrial zones")
    return hex_gdf


def main():
    crimes_df, tracts_gdf, police_gdf, industrial_gdf, boundary_gdf = load_data()

    tracts_gdf = reproject(tracts_gdf)
    police_gdf = reproject(police_gdf)
    industrial_gdf = reproject(industrial_gdf)
    boundary_gdf = reproject(boundary_gdf)

    hex_gdf = build_hex_grid(boundary_gdf)
    hex_gdf = assign_crime_counts(hex_gdf, crimes_df)
    hex_gdf = assign_population_density(hex_gdf, tracts_gdf)
    hex_gdf = assign_police_proximity(hex_gdf, police_gdf)
    hex_gdf = assign_industrial(hex_gdf, industrial_gdf)

    out_path = DATA_DIR / "hex_grid.gpkg"
    hex_gdf.to_file(out_path, driver="GPKG")
    print(f"\n[PROCESS] Saved hex grid to {out_path}")


if __name__ == "__main__":
    main()
