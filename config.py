from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

CRS_WGS84 = "EPSG:4326"
CRS_METRIC = "EPSG:26971"

H3_RESOLUTION = 8

CRIME_START_YEAR = 2022
CRIME_END_YEAR = 2026

IL_FIPS = "17"
COOK_COUNTY_FIPS = "031"

CHICAGO_OSM_RELATION_ID = 122604
CHICAGO_OSM_AREA_ID = 3600000000 + CHICAGO_OSM_RELATION_ID

SOCRATA_CRIME_V3_URL = (
    "https://data.cityofchicago.org/api/v3/views/ijzp-q8t2/query.json"
)

CENSUS_API_BASE = "https://api.census.gov/data/2024/acs/acs5"
CENSUS_POP_VAR = "B01003_001E"
TIGER_TRACT_URL = (
    "https://www2.census.gov/geo/tiger/TIGER2025/TRACT/tl_2025_17_tract.zip"
)

OVERPASS_API_URL = "https://overpass.private.coffee/api/interpreter"

POLICE_PROXIMITY_SWEET_SPOT_MIN_M = 500
POLICE_PROXIMITY_SWEET_SPOT_MAX_M = 2000

BSI_WEIGHTS = {
    "crime_hotspot": 0.35,
    "pop_density": 0.30,
    "police_proximity": 0.20,
    "industrial": 0.15,
}

GI_PERMUTATIONS = 999
GI_SIGNIFICANCE = 0.05
