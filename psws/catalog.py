# Usage:
# Print HAPI catalog information to stdout
#   python catalog.py
#
# Debugging - specify a single station and enable debug output:
#   python catalog.py --station N000008 --debug
#
# Details on options
#   python catalog.py --help
#
# Equivalent API response to:
#   hapi/catalog

DEBUG = False         # Override with --debug CLI option
STATION_DIR = "/home" # Override with --station-dir CLI option
STATION_DIR_REGEX = "^[A-Z][0-9]{6}" # Override with --station-dir-regex CLI option

# For debugging, stop processing once one of each type of data is found.
# Not a CLI option.
PARTIAL = True


def catalog(dataset=None):

  import utilrsw

  catalog = _cache_read("catalog")
  if _cli()["use_cache"] and catalog is not None:
    return catalog

  catalog_full = _cache_read("catalog.full")
  if _cli()["use_cache"] and catalog_full is not None:
    pass
  else:
    catalog_full = _catalog_full()
    _cache_write("catalog.full", catalog_full)

  if _cli()["debug"]:
    _log("\nCatalog full:")
    utilrsw.print_dict(catalog_full, style="json")
    _log("\n")

  catalog = []
  for station_dir in catalog_full:
    geoLocation = None
    for data_type in catalog_full[station_dir]:
      if data_type == "dop":
        for data_subtype in catalog_full[station_dir][data_type]:
          dsid = f"{station_dir}/{data_type}/{data_subtype}"
          entry = {
            "id": dsid,
            "info": _info(dsid, catalog_full[station_dir][data_type][data_subtype])
          }
          geoLocation = entry.get("info", {}).get("geoLocation")
          catalog.append(entry)
      else:
        dsid = f"{station_dir}/{data_type}"
        entry = {
          "id": dsid,
          "info": _info(dsid, catalog_full[station_dir][data_type])
        }
        if geoLocation is not None:
          # Use geoLocation from last dop entry
          entry["info"]["geoLocation"] = geoLocation
        catalog.append(entry)

  _cache_write("catalog", catalog)

  return catalog


def _info(dataset, entry):
  import utilrsw
  if dataset.split("/")[1] == "dop":
    template = utilrsw.read(_script_dir() / "template" / "info.dop.json")
  else:
    template = utilrsw.read(_script_dir() / "template" / "info.mag.json")

  template['startDate'] = entry['startDate']
  template['stopDate'] = entry['stopDate']

  if parsed := entry.get('parsed'):
    template['geoLocation'] = [
      parsed['Lon'],
      parsed['Lat'],
      parsed['Elv']
    ]

  return template


def _cache_read(fname):
  import utilrsw
  cache_file = _cli()["cache_dir"] / f"{fname}.pkl"
  if not cache_file.exists():
    return None
  _log(f"Reading {cache_file}")
  return utilrsw.read(cache_file)


def _cache_write(fname, data):
  import utilrsw
  file_base = _cli()["cache_dir"] / f"{fname}"
  if fname == "catalog":
    file_base = _cli()["catalog_dir"] / f"{fname}"

  if len(data) == 0:
    _log(f"No data to write for {file_base}.{{json,pkl}}")
    return

  _log(f"Writing {file_base}.{{json,pkl}}")

  for ext in ["json", "pkl"]:
    utilrsw.write(file_base.with_suffix(f".{ext}"), data, atomic=True)


def _log(msg):
  if _cli()["debug"]:
    print(msg)


def _script_dir():
  # Directory containing this script
  import pathlib
  return pathlib.Path(__file__).resolve().parent


def _data_dir():
  import os
  import sys
  import pathlib

  import util

  if _cli()["station_dir"] != STATION_DIR:
    # If the station_dir CLI option is set and differs from STATION_DIR, use it.
    data_dir = pathlib.Path(_cli()["station_dir"])
    if not data_dir.exists():
      sys.exit(f"Station directory {_cli()['station_dir']} does not exist.")
    if util.listdirs(data_dir) == []:
      sys.exit(f"Station directory {_cli()['station_dir']} is empty.")
    return data_dir

  data_dir = os.getenv("PSWS_DATA_DIR")
  if data_dir is not None:
    if not pathlib.Path(data_dir).exists():
      sys.exit(f"PSWS_DATA_DIR is set to {data_dir} but the directory does not exist.")
    return pathlib.Path(data_dir)

  data_dir_alts = [
    pathlib.Path("~/sshfs/psws").expanduser(),
    _script_dir().parent / "data"
  ]

  for data_dir_alt in data_dir_alts:
    if data_dir_alt.exists() and data_dir_alt.is_dir():
      return data_dir_alt


def _catalog_full():
  """Generate a dict with metadata extracted from directories and files.

  We assume metadata does not change such that it makes sense to concatenate
  all data; we do not check for consistency across files. (For example, we don't
  check if location changes significantly or metadata changes such that a
  single HAPI dataset would be inaccurate.)

  Writes:
    catalog.full.json: Full (non-HAPI) catalog in JSON format.

  Returns:
    dict: (non-HAPI) catalog with structure
            {
              "STATION_DIR": {
                "mag": {
                  "files": [],
                  "startDate": "YYYY-MM-DD",
                  "stopDate": "YYYY-MM-DD"
                },
                "dop": {
                  "WWV5": {
                    "startDate": "YYYY-MM-DD",
                    "stopDate": "YYYY-MM-DD",
                    "files": []
                  },
                  "WWV10": {
                    "startDate": "YYYY-MM-DD",
                    "stopDate": "YYYY-MM-DD",
                    "files": []
                  },
                  ...
                }
              }
            }
  """
  from util import listdirs, listfiles

  station_dirs = listdirs(_data_dir(), regex=STATION_DIR_REGEX)

  msg = (
    f"{len(station_dirs)} directories matching regex "
    f"{STATION_DIR_REGEX} found in {_data_dir()}"
  )
  _log(msg)

  catalog = {}
  found = {"mag": False, "dop": False, "drf": False}

  for station_dir in station_dirs:
    # If all found true, break
    if all(found.values()) and PARTIAL:
      break

    _log(f"{station_dir}")

    for dir_name in ["csvData", "magData"]:
      data_type = "dop" if dir_name == "csvData" else "mag"
      if PARTIAL and found[data_type]:
        continue
      # STATION_DIR/csvData contains all doppler files
      # STATION_DIR/magData contains all magnetometer files
      dir_path = _data_dir() / station_dir / dir_name
      if dir_path.exists() and dir_path.is_dir():
        files = listfiles(dir_path)
        n_files = len(files)
        if n_files > 0:
          if dir_name == "magData":
            catalog.setdefault(station_dir, {})["mag"] = _mag_entry(files)
            found["mag"] = True
          elif dir_name == "csvData":
            catalog.setdefault(station_dir, {})["dop"] = _dop_entry(files, dir_path)
            found["dop"] = True

    for dir_prefix in ['OBS', 'G2DRF']:
      if PARTIAL and found["drf"]:
        break
      # STATION_DIR/OBS* and STATION_DIR/G2DRF* are directories containing drf data.
      # Warning: drf.py only looks for OBS and stops if found, so G2DRF* is ignored.
      # This is not done here.
      obs_dirs = listdirs(_data_dir() / station_dir, regex=f"^{dir_prefix}.*")
      if len(obs_dirs) > 0:
        s = "y" if len(obs_dirs) == 1 else "ies"
        _log(f"  Found {len(obs_dirs)} {dir_prefix}*/ (drf) director{s}")
        catalog.setdefault(station_dir, {})[dir_prefix] = {"dirs": obs_dirs}
        found["drf"] = True

  return catalog


def _mag_entry(files):
  """Given list of magnetometer files, returns catalog entry.

  Args:
    files (list of str): List of magnetometer file names.

  Returns:
    dict: Entry containing 'files', 'startDate', and 'stopDate'.
  """
  entry = {
            "startDate": files[0][3:13],
            "stopDate": files[-1][3:13],
            "files": files
          }
  _log(f"  Found magData/ (magnetometer) with {len(files)} files")
  _log(f"    Start date: {entry['startDate']}")
  _log(f"    Stop date:  {entry['stopDate']}")
  return entry


def _dop_metadata(file_name, file_dir):
  """Reads the header of a doppler CSV file and extracts metadata.

  Args:
    file_name (str or Path): Name of the doppler CSV file.
    file_dir (str or Path): Directory containing the doppler CSV file.

  Returns:
    tuple: A tuple containing the raw header as a string and the parsed
           metadata from the first line as a dict.

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
  file_name = file_dir / file_name
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


def _dop_entry(files, files_dir):
  """Given list of doppler files, returns catalog entry.

  Args:
    files (list of str): List of doppler file names.
    files_dir (str or Path): Directory path containing the files.

  Returns:
    dict: Entry containing 'files', 'startDate', 'stopDate', 'header', and 'parsed'.
  """
  entry = {}
  unique_suffixes = {file_name.split("_")[-1].replace(".csv", "") for file_name in files}

  for file in files:
    suffix = file.split("_")[-1].replace(".csv", "")
    entry.setdefault(suffix, {"files": []})
    entry[suffix]["files"].append(file)

  for suffix in unique_suffixes:
    files = entry[suffix]["files"]
    entry[suffix]["startDate"] = files[0][0:10]
    entry[suffix]["stopDate"] = files[-1][0:10]
    header, parsed = _dop_metadata(files[0], files_dir)
    entry[suffix]["header"] = header
    entry[suffix]["parsed"] = parsed
    _log(f"  Found csvData/ (doppler) with {len(files)} files ending with _{suffix}.csv")
    _log(f"    Start date: {entry[suffix]['startDate']}")
    _log(f"    Stop date:  {entry[suffix]['stopDate']}")

  # Put `files` at end of dict
  for suffix in unique_suffixes:
    entry[suffix]["files"] = entry[suffix].pop("files")

  return entry


def _cli():
  import os
  import re
  import argparse
  from pathlib import Path

  parser = argparse.ArgumentParser(
      description='Read Digital RF data from PSWS station directories.'
  )
  parser.add_argument(
      '--station-dir',
      default=STATION_DIR,
      required=False,
      dest='station_dir',
      help='Directory containing station subdirectories (e.g., S0000183, N000020).'
  )
  parser.add_argument(
      '--station-dir-regex',
      default=STATION_DIR_REGEX,
      required=False,
      dest='station_dir_regex',
      help='Regex pattern that must match the entire station subdirectory name. Use .* to match any directory name.'
  )
  parser.add_argument(
      '--station', default=None,
      help='Only process this station subdirectory.'
  )
  parser.add_argument(
      '--debug', action='store_true', dest='debug',
      help='Enable debug mode.'
  )
  parser.add_argument(
      '--use-cache', action='store_true', dest='use_cache',
      help='Use any cached sample metadata and data if available.'
  )

  base_dir = _script_dir()
  cache_dir = base_dir / "data" / "cache"
  log_dir = base_dir / "data" / "log"
  catalog_dir = base_dir / "data" / "hapi"

  parser.add_argument(
      '--cache-dir', type=Path, default=cache_dir, dest='cache_dir',
      help=f'Directory to use for caching sample data. Default is {cache_dir}.'
  )
  parser.add_argument(
      '--log-dir', type=Path, default=log_dir, dest='log_dir',
      help=f'Directory to use for log files. Default is {log_dir}.'
  )
  parser.add_argument(
      '--catalog-dir', type=Path, default=catalog_dir, dest='catalog_dir',
      help=f'Directory to write hapi catalog. Default is {catalog_dir}.'
  )

  for dir in [cache_dir, log_dir, catalog_dir]:
    if not os.path.exists(dir):
      os.makedirs(dir, exist_ok=True)

  args = parser.parse_args()

  try:
    re.compile(args.station_dir_regex)
  except re.error as error:
    raise SystemExit(f"Invalid --station-dir-regex: {error}")

  return vars(args)


if __name__ == "__main__":
  cat = catalog()
  _log(f"\nHAPI catalog ({len(cat)} datasets):")
  import json
  print(json.dumps(cat, indent=2))
