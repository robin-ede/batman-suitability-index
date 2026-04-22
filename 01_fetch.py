import time
import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape, Point, LineString
from shapely.ops import polygonize, unary_union
from dotenv import load_dotenv
import os

from config import (
    DATA_DIR,
    SOCRATA_CRIME_V3_URL,
    CRIME_START_YEAR,
    CRIME_END_YEAR,
    CENSUS_API_BASE,
    CENSUS_POP_VAR,
    TIGER_TRACT_URL,
    IL_FIPS,
    COOK_COUNTY_FIPS,
    OVERPASS_API_URL,
    CHICAGO_OSM_AREA_ID,
)

load_dotenv()


def fetch_crimes():
    out_path = DATA_DIR / "crimes_raw.parquet"
    if out_path.exists():
        print(f"[CRIME] Cached: {out_path}")
        return

    key_id = os.getenv("SOCRATA_KEY_ID", "")
    key_secret = os.getenv("SOCRATA_KEY_SECRET", "")
    app_token = os.getenv("SOCRATA_APP_TOKEN", "")

    where_clause = (
        f"date between '{CRIME_START_YEAR}-01-01T00:00:00' "
        f"and '{CRIME_END_YEAR}-12-31T23:59:59'"
    )

    query = {
        "query": f"SELECT id, date, primary_type, latitude, longitude WHERE {where_clause}",
    }

    headers = {"Content-Type": "application/json"}
    if app_token:
        headers["X-App-Token"] = app_token
    auth = None
    if key_id and key_secret:
        auth = (key_id, key_secret)
        print("[CRIME] Using Socrata v3 API with authenticated credentials")
    else:
        print(
            "[CRIME] Warning: No Socrata credentials found, attempting unauthenticated request"
        )

    print(
        f"[CRIME] Fetching crimes from {CRIME_START_YEAR} to {CRIME_END_YEAR} (v3, no limit)..."
    )
    resp = requests.post(
        SOCRATA_CRIME_V3_URL,
        json=query,
        headers=headers,
        auth=auth,
    )
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict) and "result" in data:
        records = (
            data["result"]["records"] if "records" in data["result"] else data["result"]
        )
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict) and "rows" in data:
        records = data["rows"]
    else:
        records = data

    df = pd.DataFrame(records)
    df = df.dropna(subset=["latitude", "longitude"])
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])
    df.to_parquet(out_path, index=False)
    print(f"[CRIME] Saved {len(df):,} records to {out_path}")


def fetch_census():
    tracts_path = DATA_DIR / "census_tracts.gpkg"
    if tracts_path.exists():
        print(f"[CENSUS] Cached: {tracts_path}")
        return

    zip_path = DATA_DIR / "tl_2025_17_tract.zip"
    if not zip_path.exists():
        print("[CENSUS] Downloading TIGER tract shapefile for Illinois...")
        resp = requests.get(TIGER_TRACT_URL, stream=True)
        resp.raise_for_status()
        zip_path.write_bytes(resp.content)
        print(f"[CENSUS] Saved to {zip_path}")

    print("[CENSUS] Loading shapefile and filtering to Cook County...")
    gdf = gpd.read_file(f"zip://{zip_path}")
    gdf = gdf[gdf["COUNTYFP"] == COOK_COUNTY_FIPS].copy()

    print("[CENSUS] Fetching population data from Census API...")
    api_key = os.getenv("CENSUS_API_KEY", "")
    url = f"{CENSUS_API_BASE}?get={CENSUS_POP_VAR},NAME&for=tract:*&in=state:{IL_FIPS}&in=county:{COOK_COUNTY_FIPS}"
    if api_key:
        url += f"&key={api_key}"

    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    pop_df = pd.DataFrame(data[1:], columns=data[0])
    pop_df[CENSUS_POP_VAR] = pd.to_numeric(pop_df[CENSUS_POP_VAR], errors="coerce")
    pop_df["GEOID"] = pop_df["state"] + pop_df["county"] + pop_df["tract"]

    gdf = gdf.merge(pop_df[["GEOID", CENSUS_POP_VAR]], on="GEOID", how="left")
    gdf["pop_density_km2"] = gdf[CENSUS_POP_VAR] / (gdf["ALAND"] / 1e6)

    gdf.to_file(tracts_path, driver="GPKG")
    print(f"[CENSUS] Saved {len(gdf)} tracts to {tracts_path}")


def fetch_osm():
    boundary_path = DATA_DIR / "chicago_boundary.gpkg"
    police_path = DATA_DIR / "police_stations.gpkg"
    industrial_path = DATA_DIR / "industrial_zones.gpkg"

    need_boundary = not boundary_path.exists()
    need_police = not police_path.exists()
    need_industrial = not industrial_path.exists()

    if not need_boundary and not need_police and not need_industrial:
        print("[OSM] All OSM data cached.")
        return

    queries = {}

    if need_boundary:
        queries["boundary"] = f"""
        [out:json][timeout:120];
        relation({CHICAGO_OSM_AREA_ID - 3600000000});
        out geom;
        """

    if need_police or need_industrial:
        union_parts = []
        if need_police:
            union_parts.append('nwr(area.chicago)["amenity"="police"];')
        if need_industrial:
            union_parts.append('nwr(area.chicago)["landuse"="industrial"];')

        queries["infrastructure"] = f"""
        [out:json][timeout:180];
        area({CHICAGO_OSM_AREA_ID})->.chicago;
        (
          {"".join(union_parts)}
        );
        out geom;
        """

    results = {}
    for name, query in queries.items():
        print(f"[OSM] Querying Overpass API ({name})...")
        for attempt in range(3):
            try:
                resp = requests.post(
                    OVERPASS_API_URL,
                    data={"data": query},
                    headers={"User-Agent": "BSI-Pipeline/1.0"},
                    timeout=300,
                )
                resp.raise_for_status()
                results[name] = resp.json()
                break
            except (
                requests.exceptions.RequestException,
                requests.exceptions.Timeout,
            ) as e:
                print(f"  Attempt {attempt + 1}/3 failed: {e}")
                if attempt < 2:
                    time.sleep(10)
                else:
                    raise

    if need_boundary and "boundary" in results:
        elements = results["boundary"]["elements"]
        if elements:
            lines = []
            for el in elements:
                if el["type"] == "relation" and "members" in el:
                    for member in el["members"]:
                        role = member.get("role", "outer")
                        if role != "outer":
                            continue
                        if member.get("type") == "way" and "geometry" in member:
                            coords = [(pt["lon"], pt["lat"]) for pt in member["geometry"]]
                            if len(coords) >= 2:
                                lines.append(LineString(coords))

            if lines:
                # polygonize assembles the individual ways into valid closed rings
                polys = list(polygonize(unary_union(lines)))
                if not polys:
                    # fallback: merge all coords into one ring
                    all_coords = []
                    for ln in lines:
                        all_coords.extend(list(ln.coords))
                    polys = [shape({"type": "Polygon", "coordinates": [all_coords]})]

                boundary_gdf = gpd.GeoDataFrame(
                    {"name": ["Chicago"] * len(polys)},
                    geometry=polys,
                    crs="EPSG:4326",
                )
                boundary_gdf = boundary_gdf.dissolve(by="name").reset_index()
                boundary_gdf.to_file(boundary_path, driver="GPKG")
                print(f"[OSM] Saved Chicago boundary to {boundary_path}")

    if "infrastructure" in results:
        elements = results["infrastructure"]["elements"]
        police_rows = []
        industrial_rows = []

        for el in elements:
            tags = el.get("tags", {})
            geom = None

            if el["type"] == "node" and "lat" in el and "lon" in el:
                geom = Point(el["lon"], el["lat"])
            elif el["type"] == "way" and "geometry" in el:
                coords = [(pt["lon"], pt["lat"]) for pt in el["geometry"]]
                if len(coords) >= 4 and coords[0] == coords[-1]:
                    geom = {"type": "Polygon", "coordinates": [coords]}
                    geom = shape(geom)
                elif len(coords) >= 2:
                    geom = {"type": "LineString", "coordinates": coords}
                    geom = shape(geom)

            if geom is None:
                if "center" in el:
                    geom = Point(el["center"]["lon"], el["center"]["lat"])
                else:
                    continue

            if tags.get("amenity") == "police":
                pt = geom if geom.geom_type == "Point" else geom.centroid
                police_rows.append({"name": tags.get("name", "Police"), "geometry": pt})
            elif tags.get("landuse") == "industrial" and geom.geom_type in ("Polygon", "MultiPolygon"):
                industrial_rows.append({"name": tags.get("name", "Industrial"), "geometry": geom})

        if need_police and police_rows:
            police_gdf = gpd.GeoDataFrame(police_rows, crs="EPSG:4326")
            police_gdf.to_file(police_path, driver="GPKG")
            print(f"[OSM] Saved {len(police_gdf)} police stations to {police_path}")

        if need_industrial and industrial_rows:
            ind_gdf = gpd.GeoDataFrame(industrial_rows, crs="EPSG:4326")
            ind_gdf = ind_gdf.dissolve().reset_index(drop=True)
            ind_gdf["name"] = "Industrial Zones"
            ind_gdf.to_file(industrial_path, driver="GPKG")
            print(f"[OSM] Saved industrial zones to {industrial_path}")


def main():
    fetch_crimes()
    fetch_census()
    fetch_osm()
    print("\n=== All data fetched successfully ===")


if __name__ == "__main__":
    main()
