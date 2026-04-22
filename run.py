import argparse
import subprocess
import sys

from config import OUTPUT_DIR


STAGES = {
    "fetch": ("01_fetch.py", "Fetch raw data from APIs"),
    "process": ("02_process.py", "Build H3 grid & assign attributes"),
    "analyze": ("03_analyze.py", "Gi* hotspot detection & BSI scoring"),
    "visualize": ("04_visualize.py", "Folium dashboard & static maps"),
}

STAGE_ORDER = ["fetch", "process", "analyze", "visualize"]


def run_stage(stage_name):
    script, desc = STAGES[stage_name]
    print(f"\n{'=' * 60}")
    print(f"  STAGE: {stage_name.upper()} — {desc}")
    print(f"{'=' * 60}\n")
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(
            f"\n[ABORT] Stage '{stage_name}' failed with exit code {result.returncode}"
        )
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Batman Suitability Index — Pipeline Runner"
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        choices=STAGE_ORDER,
        default=[],
        help="Stages to skip (e.g., --skip fetch to reuse cached data)",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        choices=STAGE_ORDER,
        default=None,
        help="Run only these stages (e.g., --only analyze visualize)",
    )
    args = parser.parse_args()

    if args.only is not None:
        stages_to_run = [s for s in STAGE_ORDER if s in args.only]
    else:
        stages_to_run = [s for s in STAGE_ORDER if s not in args.skip]

    print("\n=== Batman Suitability Index (BSI) Pipeline ===")
    print(f"Stages to run: {', '.join(stages_to_run) or '(none)'}\n")

    for stage in stages_to_run:
        run_stage(stage)

    print(f"\n{'=' * 60}")
    print("  PIPELINE COMPLETE")
    print(f"  Dashboard: {OUTPUT_DIR / 'bsi_dashboard.html'}")
    print(f"  Static maps: {OUTPUT_DIR / 'bsi_static_maps.png'}")
    print(f"  Top 5 map: {OUTPUT_DIR / 'bsi_top5_map.png'}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
