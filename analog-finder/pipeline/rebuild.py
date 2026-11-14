"""Rebuild the whole data pack from public sources: download everything, then run pipeline steps 01 to 09 in order.
Usage (from anywhere): python analog-finder/pipeline/rebuild.py
Needs the packages in requirements.txt, about 8 GB of free disk and a few hours (mostly downloads).
Safe to re-run: downloads and the slow steps are skipped when their output already exists.
The finished pack is written to analog-finder/web/data, and FINDINGS.md is regenerated.
"""
import glob, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))          # analog-finder/pipeline
APP = os.path.dirname(HERE)                                # analog-finder
RAW = os.path.join(APP, "raw")
WEB = os.path.join(APP, "web")


def run(script, *args, cwd=HERE, output=None):
    if output and os.path.exists(os.path.join(RAW, output)):
        print(f"\n=== {script}: skipped, raw/{output} already exists"); return
    print(f"\n=== {script} {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, script, *args], cwd=cwd, check=True)


def official():
    """LRO Diviner, JAXA Earth API layers and GLiM, fetched into analog-finder/data/official, then copied to raw/official."""
    run("fetch_official.py", cwd=APP)
    dst = os.path.join(RAW, "official"); os.makedirs(dst, exist_ok=True)
    for f in glob.glob(os.path.join(APP, "data", "official", "*.npz")) + glob.glob(os.path.join(APP, "data", "official", "*.zip")):
        shutil.copy2(f, dst)


def main():
    os.makedirs(RAW, exist_ok=True)
    run("get_data.py", RAW)
    run("01_fetch_earth_tiles.py", os.path.join(RAW, "terrarium7"))
    run("02_fetch_power.py", os.path.join(RAW, "power"))
    run("03_build_earth_dem.py", os.path.join(RAW, "terrarium7"), os.path.join(RAW, "earth_1min.npy"), output="earth_1min.npy")
    run("04_fetch_worldcover.py", os.path.join(RAW, "worldcover_025.npz"), output="worldcover_025.npz")
    run("05_earth_traits.py", RAW, os.path.join(RAW, "earth_traits.npz"))
    official()
    run("05b_official_earth.py", RAW)
    run("06_mars_moon_grids.py", RAW, os.path.join(RAW, "grids"), os.path.join(WEB, "assets"))
    run("06b_lro_layers.py", RAW, os.path.join(WEB, "assets"))
    run("07_build_pack.py", RAW, WEB)
    run("07c_hires_images.py", RAW, WEB)
    run("08_findings.py", RAW, WEB, os.path.join(APP, "FINDINGS.md"))
    run("09_stage2.py", RAW, WEB)
    print("\nRebuild finished. Start the app with start.bat (Windows) or start.sh (Mac/Linux).")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"\nA pipeline step failed ({os.path.basename(e.cmd[1])}). Fix the error above and run rebuild again; finished steps are kept.")
