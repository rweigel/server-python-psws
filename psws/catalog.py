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

def read_doppler_metadata(file_name):
  """
  Example CSV header (S000479/csvData/2026-10-11T000000Z_N0001020_G2R1_DN31xd_FRQ_WWV5.csv)
    #,2026-10-11T00:00:00Z,N0001020,DN31xd,41.147997,-112.049739,1334.9,Clinton Utah,G2R1,WWV5
    ######################################################
    # MetaData for Grape Gen 2 Station
    #
    # Station Node Number      N0001020
    # Callsign                 KF7ZN
    # Grid Square              DN31xd
    # Lat, Lon, Elv            41.147997,-112.049739,1334.9
    # GPS Fix,PDOP             3,1.63
    # GPS Acquisition on       2024-08-16 15:19:37.961159
    # City State               Clinton Utah
    # Radio                    Grape 2
    # RFGain                   2.5
    # RadioID1                 G2R1
    # Antenna                  Wire Antenna
    # Frequency Standard       LB GPSDO
    # System Info              RasPi4B/8GB, RasPi OS Bullseye 6.1.21
    # RFDeckSN, LogicCtrlrSN   120,1020
    # G2console Version        12.17               
    # Data Controller Version  0.7.26
    # Picorun Version          0.5.19
    # magdata Version          None
    # PSWSsetup Version        2.28
    # A/D Sample RAte          8000
    #
    # Beacon 1 Now Decoded     WWV5
    #
    ######################################################
  """
  header = []
  with open(file_name, 'r') as f:
    for line in f:
      if not line.startswith('#'):
        break
      header.append(line.strip())

  parsed = header[0].lstrip('#').strip() if header else None
  parsed = parsed.split(',') if parsed else None
  if parsed and len(parsed) >= 10:
    parsed = {
      "Grid Square": parsed[3],
      "Lat": float(parsed[4]),
      "Lon": float(parsed[5]),
      "Elv": float(parsed[6]),
      "City State": parsed[7],
      "RadioID1": parsed[8],
      "Beacon 1 Now Decoded": parsed[9],
    }
  header = "\n".join(header)

  return header, parsed

def _log(msg):
  if DEBUG:
    print(msg)

if __name__ == "__main__":
  catalog = read_catalog_csv()
  print(json.dumps(catalog, indent=2))

  from util import listdirs, listfiles
  regex = "^[A-Z][0-9]{6}"
  station_dirs = listdirs(data_dir(), regex=regex)
  _log(f"{len(station_dirs)} station directories (regex = {regex}) found in {data_dir()}")

  catalog = {}
  for station_dir in station_dirs:

    _log(f"{station_dir}")

    for dir_name in ["csvData", "magData"]:
      dir_path = data_dir() / station_dir / dir_name
      if dir_path.exists() and dir_path.is_dir():
        files = listfiles(dir_path)
        n_files = len(files)
        # Here we assume metadata does not change such that it makes
        # sense to concatenate all data; we do not check for consistency across files.
        # (For example, we don't check if location changes significantly or metadata changes
        # such that a single HAPI dataset would be inaccurate.)
        if n_files > 0:
          if dir_name == "magData":
            catalog.setdefault(station_dir, {})["mag"] = {"files": files}
            catalog[station_dir]["mag"]["startDate"] = files[0][3:13]
            catalog[station_dir]["mag"]["stopDate"] = files[-1][3:13]
            # Example file name: OBS2026-10-31T00:00.zip
            _log(f"  Found magData/ (magnetometer) with {n_files} files")
            _log(f"    Start date: {catalog[station_dir]['mag']['startDate']}")
            _log(f"    Stop date: {catalog[station_dir]['mag']['stopDate']}")
          elif dir_name == "csvData":
            # Example file name: 2026-10-14T000000Z_N0001029_G2R1_EM00wv_FRQ_WWV5.csv

            # Split files depending on ending, e.g., _WWV5.csv, WWV10.csv, etc.
            # Put under ["dop"]["WWV5"], ["dop"]["WWV10"], etc. depending on the file suffix
            # Get unique file suffixes
            unique_suffixes = set(f.split("_")[-1].replace(".csv", "") for f in files)
            for suffix in unique_suffixes:
              catalog.setdefault(station_dir, {}).setdefault("dop", {}).setdefault(suffix, {"files": []})

            for f in files:
              suffix = f.split("_")[-1].replace(".csv", "")
              catalog[station_dir]["dop"][suffix]["files"].append(f)

            for suffix in unique_suffixes:
              files = catalog[station_dir]["dop"][suffix]["files"]
              n_files = len(files)
              _log(f"  Found csvData/ (doppler) with {n_files} files ending with _{suffix}.csv")
              # Example file name: 2026-10-14T000000Z_N0001029_G2R1_EM00wv_FRQ_WWV5.csv
              catalog[station_dir]["dop"][suffix]["startDate"] = files[0][0:10]
              catalog[station_dir]["dop"][suffix]["stopDate"] = files[-1][0:10]
              header, parsed = read_doppler_metadata(dir_path / files[0])
              catalog[station_dir]["dop"][suffix]["header"] = header
              catalog[station_dir]["dop"][suffix]["parsed"] = parsed
              _log(f"    Start date: {catalog[station_dir]['dop'][suffix]['startDate']}")
              _log(f"    Stop date:  {catalog[station_dir]['dop'][suffix]['stopDate']}")


    for dir_prefix in ['OBS', 'G2DRF']:
      obs_dirs = listdirs(data_dir() / station_dir, regex=f"^{dir_prefix}.*")
      if len(obs_dirs) > 0:
        s = "y" if len(obs_dirs) == 1 else "ies"
        _log(f"  Found {len(obs_dirs)} {dir_prefix}*/ (drf) director{s}")
        catalog.setdefault(station_dir, {})[dir_prefix] = {"dirs": obs_dirs}

  import utilrsw
  utilrsw.write("catalog.full.json", catalog)