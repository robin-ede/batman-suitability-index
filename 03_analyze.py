import geopandas as gpd
import numpy as np
from libpysal.weights import Queen, fill_diagonal
from esda.getisord import G_Local

from config import (
    DATA_DIR,
    CRS_METRIC,
    BSI_WEIGHTS,
    GI_PERMUTATIONS,
    GI_SIGNIFICANCE,
)


def compute_gi_star(hex_gdf):
    print("[ANALYZE] Computing Getis-Ord Gi* on crime counts...")
    w = Queen.from_dataframe(hex_gdf, use_index=False)
    w.transform = "r"
    fill_diagonal(w, 1.0)

    g_star = G_Local(
        hex_gdf["crime_count"].values,
        w,
        star=None,
        permutations=GI_PERMUTATIONS,
    )

    hex_gdf["gi_z"] = g_star.Zs
    hex_gdf["gi_p_sim"] = g_star.p_sim

    hex_gdf["hotspot"] = "Not Significant"
    sig = hex_gdf["gi_p_sim"] < GI_SIGNIFICANCE
    hex_gdf.loc[sig & (hex_gdf["gi_z"] > 0), "hotspot"] = "Hot Spot"
    hex_gdf.loc[sig & (hex_gdf["gi_z"] < 0), "hotspot"] = "Cold Spot"

    n_hot = (hex_gdf["hotspot"] == "Hot Spot").sum()
    n_cold = (hex_gdf["hotspot"] == "Cold Spot").sum()
    print(f"[ANALYZE] Hot spots: {n_hot}, Cold spots: {n_cold}")
    return hex_gdf


def normalize(values):
    vmin = values.min()
    vmax = values.max()
    if vmax == vmin:
        return np.zeros_like(values, dtype=float)
    return (values - vmin) / (vmax - vmin)


def compute_bsi(hex_gdf):
    print("[ANALYZE] Computing BSI scores...")

    crime_score = normalize(hex_gdf["gi_z"].values)
    pop_score = normalize(hex_gdf["pop_density_km2"].values)
    police_score = hex_gdf["police_score"].values
    industrial_score = hex_gdf["industrial"].values.astype(float)

    hex_gdf["norm_crime"] = crime_score
    hex_gdf["norm_pop"] = pop_score
    hex_gdf["norm_police"] = police_score
    hex_gdf["norm_industrial"] = industrial_score

    hex_gdf["bsi"] = (
        BSI_WEIGHTS["crime_hotspot"] * crime_score
        + BSI_WEIGHTS["pop_density"] * pop_score
        + BSI_WEIGHTS["police_proximity"] * police_score
        + BSI_WEIGHTS["industrial"] * industrial_score
    )

    top5 = hex_gdf.nlargest(5, "bsi")
    print("[ANALYZE] Top 5 Batcave candidates:")
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        print(
            f"  {i}. H3={row['h3_id']} | BSI={row['bsi']:.4f} | "
            f"Hotspot={row['hotspot']} | PopDens={row['pop_density_km2']:.0f}/km² | "
            f"PoliceDist={row['police_dist_m']:.0f}m | Industrial={row['industrial']}"
        )

    return hex_gdf


def main():
    hex_gdf = gpd.read_file(DATA_DIR / "hex_grid.gpkg")

    hex_gdf = compute_gi_star(hex_gdf)
    hex_gdf = compute_bsi(hex_gdf)

    out_path = DATA_DIR / "bsi_results.gpkg"
    hex_gdf.to_file(out_path, driver="GPKG")
    print(f"\n[ANALYZE] Saved BSI results to {out_path}")


if __name__ == "__main__":
    main()
