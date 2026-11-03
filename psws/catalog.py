# Usage:
#   python catalog.py
#
# Returns HAPI catalog information from catalog.csv in JSON format to stdout
#
# Equivalent API response to:
#   hapi/catalog

import os
import csv
import json

from pathlib import Path

DEBUG = True

# Directory containing this script
SCRIPT_DIR = Path(__file__).resolve().parent

#DATA_DIR_DEFAULT = SCRIPT_DIR.parent / "data"
DATA_DIR_DEFAULT = "/Users/rweigel/sshfs/psws"

def data_dir():
  PSWS_DATA_DIR = os.getenv("PSWS_DATA_DIR")
  if PSWS_DATA_DIR is not None:
    return Path(PSWS_DATA_DIR)
  return Path(DATA_DIR_DEFAULT)

def read_catalog_csv():
  catalog = []
  with (SCRIPT_DIR / 'catalog.csv').open('r') as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
      if row[0].startswith('#'):
        continue
      catalog.append({"id": row[0].strip()})
  return catalog

def _log(msg):
  if DEBUG:
    print(msg)

if __name__ == "__main__":
  catalog = read_catalog_csv()
  print(json.dumps(catalog, indent=2))

  from util import listdirs
  regex = "S[0-9]{6}"
  #regex = "^[A-Z][0-9]{6}"
  station_dirs = listdirs(data_dir(), regex=regex)
  _log(f"{len(station_dirs)} station directories (regex = {regex}) found in {data_dir()}")
  catalog = {}
  for station_dir in station_dirs:

    _log(f"{station_dir}")

    mag_dir = data_dir() / station_dir / "magData"
    if mag_dir.exists() and mag_dir.is_dir():
      _log(f"  Found magData/ (magnetometer) with {len(list(mag_dir.iterdir()))} files")

    dop_dir = data_dir() / station_dir / "csvData"
    if dop_dir.exists() and dop_dir.is_dir():
      _log(f"  Found csvData/ (doppler) with {len(list(dop_dir.iterdir()))} files")

    obs_dirs = listdirs(data_dir() / station_dir, regex="^OBS.*")
    if len(obs_dirs) > 0:
      _log(f"  Found {len(obs_dirs)} OBS*/ (drf) directories")

    g2drf_dirs = listdirs(data_dir() / station_dir, regex="^G2DRF.*")
    if len(g2drf_dirs) > 0:
      _log(f"  Found {len(g2drf_dirs)} G2DRF*/ (drf) directories")
