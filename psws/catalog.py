# Usage:
# Print HAPI catalog information to stdout
#   python catalog.py
# Details on options
#   python catalog.py --help
#
# Debugging
#   Specify a single station and enable debug output:
#     python catalog.py --station N000008 --debug
#   Change default root directory from /home
#   python catalog.py --station-dir ~/sshfs/psws --debug
#
#
# Equivalent API response to:
#   hapi/catalog

import util

def catalog(dataset=None):
  options = util.cli()

  regex = options["station_dir_regex"] != util.STATION_DIR_REGEX
  restricted = options["station"] is not None or regex

  catalog_full = None
  if options["use_cache"]:
    catalog = _cache_read("catalog")
    if catalog is not None:
      return _catalog_filter(catalog, dataset=dataset, options=options)

    catalog_full = _cache_read("catalog.full")

  if catalog_full is None:
    catalog_full = _catalog_full()
    if not restricted:
      _cache_write("catalog.full", catalog_full)

  catalog_full = _catalog_filter(catalog_full, dataset=dataset, options=options)

  if util.cli()["debug"]:
    import json
    util.log("\nCatalog full:")
    util.log(json.dumps(catalog_full, indent=2))
    util.log("\n")

  catalog = []
  for station_dir in catalog_full:

    geoLocation = None
    if dataset is not None:
      for doppler_entry in catalog_full[station_dir].get("dop", {}).values():
        parsed = doppler_entry.get("parsed")
        if isinstance(parsed, dict) and all(key in parsed for key in ("Lon", "Lat", "Elv")):
          geoLocation = [parsed["Lon"], parsed["Lat"], parsed["Elv"]]

    for data_type in catalog_full[station_dir]:
      if data_type not in ("dop", "mag"):
        continue
      if data_type == "dop":
        for data_subtype in catalog_full[station_dir][data_type]:
          dsid = f"{station_dir}/{data_type}/{data_subtype}"
          if dataset is not None and dsid != dataset:
            continue
          entry = {
            "id": dsid,
            "info": _info(dsid, catalog_full[station_dir][data_type][data_subtype])
          }
          geoLocation = entry.get("info", {}).get("geoLocation")
          catalog.append(entry)
      else:
        dsid = f"{station_dir}/{data_type}"
        if dataset is not None and dsid != dataset:
          continue
        entry = {
          "id": dsid,
          "info": _info(dsid, catalog_full[station_dir][data_type])
        }
        if geoLocation is not None:
          # Use geoLocation from last dop entry
          entry["info"]["geoLocation"] = geoLocation
        catalog.append(entry)

  if dataset is not None:
    matches = _catalog_filter(catalog, dataset=dataset, options=options)
    if not matches:
      util.log(f"Dataset {dataset} not found in catalog.")
    return matches

  if not restricted:
    _cache_write("catalog", catalog)

  return catalog


def _catalog_filter(catalog, dataset=None, options=None):
  """Filter public entries or full station metadata by CLI selection."""
  import re

  if options is None:
    options = util.cli()
  station_pattern = re.compile(options["station_dir_regex"])

  def station_selected(station):
    return station_pattern.fullmatch(station) is not None and (
      options["station"] is None or station == options["station"]
    ) and (dataset is None or station == dataset.split("/")[0])

  if isinstance(catalog, dict):
    return {station: entry for station, entry in catalog.items() if station_selected(station)}
  return [
    entry for entry in catalog
    if station_selected(entry["id"].split("/")[0])
    and (dataset is None or entry["id"] == dataset)
  ]


def _info(dataset, entry):
  import pathlib

  import utilrsw

  script_dir = pathlib.Path(__file__).resolve().parent
  data_type = dataset.split("/")[1]
  if data_type not in ("dop", "mag"):
    raise util.Error(f"Info metadata is not implemented for dataset {dataset}.")
  template_path = script_dir / "template" / f"info.{data_type}.json"
  try:
    template = utilrsw.read(template_path)
    template['startDate'] = entry['startDate']
    template['stopDate'] = entry['stopDate']
    if parsed := entry.get('parsed'):
      if not isinstance(parsed, dict):
        raise ValueError("parsed metadata must be a dictionary")
      template['geoLocation'] = [parsed['Lon'], parsed['Lat'], parsed['Elv']]
    if columns := entry.get('columns'):
      if not isinstance(columns, str):
        raise ValueError("columns metadata must be a string")
      columns = columns.split(",")[1:]
      if len(columns) != len(template['parameters']) - 1:
        raise ValueError("columns metadata does not match template parameters")
      for i, col in enumerate(columns, start=1):
        template['parameters'][i]['name'] = col.strip()

  except (OSError, ValueError, KeyError, TypeError) as error:
    msg = f"Failed to build info for {dataset} using {template_path}: {error}"
    raise util.Error(msg) from error

  return template


def _cache_read(fname):
  import pickle

  import utilrsw

  options = util.cli()
  directory = options["catalog_dir"] if fname == "catalog" else options["cache_dir"]
  cache_file = directory / f"{fname}.pkl"
  if not cache_file.exists():
    return None

  util.log(f"Reading {cache_file}")
  try:
    data = utilrsw.read(cache_file)
  except (OSError, ValueError, EOFError, pickle.UnpicklingError, ImportError, AttributeError) as error:
    msg = f"Failed to read cache {cache_file}: {error}. Retry without --use-cache."
    raise util.Error(msg) from error
  if fname == "catalog":
    valid = isinstance(data, list) and all(
      isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("info"), dict)
      for entry in data
    )
  else:
    valid = isinstance(data, dict) and all(isinstance(entry, dict) for entry in data.values())
  if not valid:
    raise util.Error(f"Invalid cache structure in {cache_file}. Retry without --use-cache.")
  return data


def _cache_write(fname, data):
  import sys
  from contextlib import redirect_stdout

  import utilrsw
  file_base = util.cli()["cache_dir"] / f"{fname}"
  if fname == "catalog":
    file_base = util.cli()["catalog_dir"] / f"{fname}"

  util.log(f"Writing {file_base}.{{json,pkl}}")

  for ext in ["json", "pkl"]:
    file_path = file_base.parent / f"{file_base.name}.{ext}"
    try:
      file_path.parent.mkdir(parents=True, exist_ok=True)
      with redirect_stdout(sys.stderr):
        utilrsw.write(file_path, data, atomic=True)
    except (OSError, ValueError, TypeError) as error:
      raise util.Error(f"Failed to write cache {file_path}: {error}") from error


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

  options = util.cli()
  util.validate_station_dir(options['station_dir'])
  station_dirs = listdirs(options['station_dir'], regex=options['station_dir_regex'])
  if options["station"] is not None:
    station_dirs = [station for station in station_dirs if station == options["station"]]
  if not station_dirs:
    msg = (
      f"No matching station directories found in {options['station_dir']} "
      f"with regex {options['station_dir_regex']}. "
      f"If running from command line, set --station-dir. If running from "
      f"and using the HAPI server, check PSWS_DATA_DIR in config.json."
    )
    raise util.Error(msg)

  msg = (
    f"{len(station_dirs)} directories matching regex "
    f"{options['station_dir_regex']} found in {options['station_dir']}"
  )
  util.log(msg)

  catalog = {}

  for station_dir in station_dirs:
    util.log(f"{station_dir}")

    for dir_name in ["csvData", "magData"]:
      # STATION_DIR/csvData contains all doppler files
      # STATION_DIR/magData contains all magnetometer files
      dir_path = util.cli()['station_dir'] / station_dir / dir_name
      if dir_path.exists() and dir_path.is_dir():
        files = listfiles(dir_path)
        n_files = len(files)
        if n_files > 0:
          if dir_name == "magData":
            entry = _mag_entry(files)
            if entry is not None:
              catalog.setdefault(station_dir, {})["mag"] = entry
          elif dir_name == "csvData":
            entry = _dop_entry(files, dir_path)
            if entry:
              catalog.setdefault(station_dir, {})["dop"] = entry

    for dir_prefix in ['OBS', 'G2DRF']:
      # STATION_DIR/OBS* and STATION_DIR/G2DRF* are directories containing drf data.
      # Warning: drf.py only looks for OBS and stops if found, so G2DRF* is ignored.
      # This is not done here.
      obs_dirs = listdirs(util.cli()['station_dir'] / station_dir, regex=f"^{dir_prefix}.*")
      if len(obs_dirs) > 0:
        s = "y" if len(obs_dirs) == 1 else "ies"
        util.log(f"  Found {len(obs_dirs)} {dir_prefix}*/ (drf) director{s}")
        catalog.setdefault(station_dir, {})[dir_prefix] = {"dirs": obs_dirs}

  return catalog


def _file_date_range(files, offset=0):
  """Determine start and stop dates from file names."""
  from datetime import date, timedelta

  valid_files = []
  dates = []
  for file_name in files:
    try:
      file_date = date.fromisoformat(file_name[offset:offset + 10])
      file_date = file_date + timedelta(days=1)
    except (ValueError, OverflowError) as error:
      util.log(f"    Skipping file {file_name}: cannot parse date in filename: {error}")
      continue
    valid_files.append(file_name)
    dates.append(file_date)

  files[:] = valid_files
  if not dates:
    return None

  start = min(dates)
  stop = max(dates) + timedelta(days=1)

  return f"{start.isoformat()}T00:00:00Z", f"{stop.isoformat()}T00:00:00Z"


def _mag_entry(files):
  """Given list of magnetometer files, returns catalog entry.

  Args:
    files (list of str): List of magnetometer file names.

  Returns:
    dict: Entry containing 'files', 'startDate', and 'stopDate'.
  """
  if not files:
    raise util.Error("Cannot build magnetometer metadata from an empty file list.")
  files = sorted(files)
  util.log(f"  Found magData/ (magnetometer) with {len(files)} files")
  bounds = _file_date_range(files, offset=3)
  if bounds is None:
    return None
  start_date, stop_date = bounds
  entry = {
            "startDate": start_date,
            "stopDate": stop_date,
            "files": files
          }
  util.log(f"    Start date: {entry['startDate']}")
  util.log(f"    Stop date:  {entry['stopDate']}")
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
  columns = []
  file_name = file_dir / file_name
  with open(file_name, 'r') as f:
    for line in f:
      if not line.startswith('#'):
        # Last line before the actual data, contains column headers
        columns = line.strip()
        break
      header.append(line.strip())

  parsed = header[0].lstrip('#').strip() if header else None
  if parsed:
    import csv
    parsed = next(csv.reader([parsed]))
  else:
    parsed = None
  if parsed and len(parsed) < 10:
    raise util.Error(f"Invalid doppler header in {file_name}: expected at least 10 fields.")
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

  return header, parsed, columns


def _dop_entry(files, files_dir):
  """Given list of doppler files, returns catalog entry.

  Args:
    files (list of str): List of doppler file names.
    files_dir (str or Path): Directory path containing the files.

  Returns:
    dict: Entry containing 'files', 'startDate', 'stopDate', 'header', and 'parsed'.
  """
  if not files:
    raise util.Error("Cannot build doppler metadata from an empty file list.")
  files = sorted(files)
  entry = {}
  unique_suffixes = {file_name.split("_")[-1].replace(".csv", "") for file_name in files}

  for file in files:
    suffix = file.split("_")[-1].replace(".csv", "")
    entry.setdefault(suffix, {"files": []})
    entry[suffix]["files"].append(file)

  for suffix in unique_suffixes:
    files = entry[suffix]["files"]
    bounds = _file_date_range(files)
    if bounds is None:
      del entry[suffix]
      continue
    start_date, stop_date = bounds
    entry[suffix]["startDate"] = start_date
    entry[suffix]["stopDate"] = stop_date
    try:
      header, parsed, columns = _dop_metadata(files[0], files_dir)
    except (OSError, ValueError, TypeError) as error:
      raise util.Error(f"Failed to read doppler metadata from {files_dir / files[0]}: {error}") from error

    entry[suffix]["header"] = header
    entry[suffix]["columns"] = columns
    entry[suffix]["parsed"] = parsed

    util.log(f"  Found csvData/ (doppler) with {len(files)} files ending with _{suffix}.csv")
    util.log(f"    Start date: {entry[suffix]['startDate']}")
    util.log(f"    Stop date:  {entry[suffix]['stopDate']}")

  # Put `files` at end of dict
  for suffix_entry in entry.values():
    suffix_entry["files"] = suffix_entry.pop("files")

  return entry


if __name__ == "__main__":
  import json

  try:
    cat = catalog(dataset=util.cli()["dataset"])
    util.log(f"\nHAPI catalog ({len(cat)} datasets):")
    output = json.dumps(cat, indent=2)
  except (util.Error, OSError, ValueError) as error:
    raise SystemExit(str(error)) from None

  print(output)
