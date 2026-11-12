# Usage:
#   python data.py --dataset <id> --start <start> --stop <stop>
#   python data.py --dataset <id> --start <start> --stop <stop> --parameters <parameters>
#
# <id> is the station ID, e.g., S000028 found in first column of catalog.csv
# <start> and <stop> are 20-character HAPI ISO date strings, e.g.,
# 2023-03-22T00:00:00Z
#
# The output of this script is HAPI CSV and equivalent to the response from:
#   hapi/data?dataset=<id>&start=<start>&stop=<stop>
#   hapi/data?dataset=<id>&start=<start>&stop=<stop>&parameters=<parameters>
#
# Examples:
#
#  python data.py --dataset S000003/mag --start 2026-08-19T00:00:00.000000Z --stop 2026-08-20T00:00:00.000000Z
#  python data.py --dataset S000003/mag --parameters Field_Vector --start 2026-08-19T00:00:00.000000Z --stop 2026-08-20T00:00:00.000000Z
#
#  python data.py -d N000001/doppler --start 2019-05-24T00:00:00Z --stop 2019-05-25T23:59:59Z --parameters Freq

import util

def error(emsg):
  raise util.Error(emsg)

def files_needed(id, start, stop, data_dir):
  import os

  sub_dir_map = {
    'mag': 'magData',
    'dop': 'csvData',
    'drf': '',
  }

  # id = S000028/mag => S000028/magData
  # id = S000028/dop/? => S000028/csvData
  # id = S000028/drf => S000028

  data_type = id.split('/')[1]
  util.log(f"Dataset ID: {id}, data type: {data_type}")
  if data_type not in sub_dir_map:
    msg = f"Unknown dataset ID suffix for id '{id}'. "
    msg += "Expected to end with 'mag', 'dop', or 'drf'."
    error(msg)

  dir_base = id.split('/')[0]
  dir_sub = sub_dir_map[data_type]
  dataset_dir = os.path.join(data_dir, dir_base, dir_sub)
  if not os.path.exists(dataset_dir):
    error(f"Dataset directory does not exist: {dataset_dir}")

  # Keep only day precision for file matching
  start = start[0:10]
  stop = stop[0:10]

  util.log(f"Looking for file with data in range [{start}, {stop}]")

  if data_type == 'mag':
    files = files_needed_mag(dataset_dir, start, stop)
  if data_type == 'dop':
    freq = id.split('/')[-1]
    files = files_needed_doppler(dataset_dir, freq, start, stop)

  if len(files) == 0:
    util.log(f"No files found with data in range [{start}, {stop}]")
  else:
    s = "s" if len(files) > 1 else ""
    util.log(f"Found {len(files)} file{s} with data in range [{start}, {stop}]:")
    files_join = "  \n:   ".join(files)
    util.log(files_join)

  return files


def files_needed_doppler(dataset_dir, freq, start, stop):
  import os

  files_csv = [f for f in os.listdir(dataset_dir) if f.endswith(".csv")]

  files_needed = []
  for file in sorted(files_csv):
    file_date = file[0:10]
    if not file.endswith(f"{freq}.csv"):
      continue
    util.log(f"File: {file}, date: {file_date}")
    if start <= file_date <= stop:
      files_needed.append(os.path.join(dataset_dir, file))

  return files_needed


def files_needed_mag(dataset_dir, start, stop):
  import os
  files_zip = [f for f in os.listdir(dataset_dir) if f.endswith(".zip")]
  files_zip.sort()

  if not files_zip:
    util.log(f"No .zip files found in dataset directory: {dataset_dir}")
    return []

  util.log(f"Found {len(files_zip)} files that end with .zip in {dataset_dir}")

  files_needed = []

  for file in files_zip:
    file_date = file[3:13]
    util.log(f"  {file}, date: {file_date}")
    if start <= file_date <= stop:
      files_needed.append(os.path.join(dataset_dir, file))

  return files_needed


def print_data(id, filename, start, stop, parameters, data_dir):

  data_type = id.split('/')[1]
  if data_type == 'mag':
    print_data_mag(filename, start, stop, parameters)

  if data_type == 'dop':
    print_data_doppler(filename, start, stop, parameters)


def print_data_doppler(filepath, start, stop, parameters):

  import pandas as pd

  # Read CSV file with pandas, skipping comment lines that start with #
  df = pd.read_csv(filepath, comment='#', skipinitialspace=True)

  # Convert UTC column to datetime and set as index
  if 'UTC' in df.columns:
    df['UTC'] = pd.to_datetime(df['UTC'], utc=True)
    df.set_index('UTC', inplace=True)

  df = df[(df.index >= start) & (df.index < stop)]

  if parameters is not None:
    # Filter out columns that are not in the parameters list
    df = df[parameters]

  # Print HAPI CSV
  print(df.to_csv(index=True, header=False, date_format='%Y-%m-%dT%H:%M:%SZ'), end='')


def print_data_mag(filepath, start, stop, parameters):

  def extract_data(file):
    """Read files in a zip file into a string"""
    import zipfile

    data = ""
    with zipfile.ZipFile(file, 'r') as z:
      for filename in sorted(z.namelist()):
        with z.open(filename) as f:
          data += f.read().decode('utf-8')
    return data

  import json
  import datetime

  if parameters is None:
    parameters = ['Field_Vector', 'rxryrz', 'rt', 'lt', 'Tm']

  # TODO: This will be much faster if CSV files were read using Pandas, which
  # loops over lines in c code.
  data = extract_data(filepath)

  for line in data.splitlines():

    util.log(f"Processing line: {line}")

    if line.startswith('{'):
      # Row format:
      # {'ts': '21 Oct 2025 04:01:59', 'rt': 32.5, 'lt': 41.69,
      #  'x': -45676.67, 'y': -13284.67, 'z': 16150.67,
      #  'rx': -68515, 'ry': -19927, 'rz': 24226, 'Tm': 50236.2845}
      entry = json.loads(line)
      ts = entry['ts']
      try:
        dt = datetime.datetime.strptime(ts, '%d %b %Y %H:%M:%S')
        entry['ts'] = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
      except Exception as e:
        error(f"Failed to parse ts '{ts}': {e}")

    elif line.startswith('"'):
      # Row format:
      # TODO: Verify that these columns are correct.
      entry = line.split(', ')
      try:
        ts = entry[0].strip('"')
        dt = datetime.datetime.strptime(ts, '%d %b %Y %H:%M:%S')
      except Exception as e:
        error(f"Failed to parse ts '{ts}': {e}")

      entry = {
        'ts': dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'x': float(entry[1]) if len(entry) > 1 else 'NaN',
        'y': float(entry[2]) if len(entry) > 2 else 'NaN',
        'z': float(entry[3]) if len(entry) > 3 else 'NaN',
        'rx': float(entry[4]) if len(entry) > 4 else 'NaN',
        'ry': float(entry[5]) if len(entry) > 5 else 'NaN',
        'rz': float(entry[6]) if len(entry) > 6 else 'NaN',
        'rt': float(entry[7]) if len(entry) > 7 else 'NaN',
        'lt': float(entry[8]) if len(entry) > 8 else 'NaN',
        'Tm': float(entry[9]) if len(entry) > 9 else 'NaN'
      }
    else:
      # TODO: Read other format
      error(f"Unsupported data format in file {filepath}: {line}")

    if entry['ts'][0:20] < start:
      continue
    if entry['ts'][0:20] >= stop:
      break

    row = entry['ts']

    if 'Field_Vector' in parameters:
      if 'x' in entry and 'y' in entry and 'z' in entry:
        row += f",{entry['x']},{entry['y']},{entry['z']}"
      else:
        row += ",NaN,NaN,NaN"
    if 'rxryrz' in parameters:
      if 'rx' in entry and 'ry' in entry and 'rz' in entry:
        row += f",{entry['rx']},{entry['ry']},{entry['rz']}"
      else:
        row += ",NaN,NaN,NaN"
    if 'rt' in parameters:
      if 'rt' in entry:
        row += f",{entry['rt']}"
      else:
        row += ",NaN"
    if 'lt' in parameters:
      if 'lt' in entry:
        row += f",{entry['lt']}"
      else:
        row += ",NaN"
    if 'Tm' in parameters:
      if 'Tm' in entry:
        row += f",{entry['Tm']}"
      else:
        row += ",NaN"

    print(row)


if __name__ == "__main__":
  try:
    args = util.cli(endpoint="data")
    for option in ("dataset", "start", "stop"):
      if not args[option]:
        raise util.Error(f"A --{option} argument is required.")

    dataset = args["dataset"]
    start = args["start"]
    stop = args["stop"]

    parameters = None
    if args["parameters"] is not None:
      parameters = [parameter.strip() for parameter in args["parameters"].split(",")]

    data_dir = args["station_dir"].expanduser().resolve()
    util.validate_station_dir(data_dir)
    util.log(f"dataset: {dataset}, start: {start}, stop: {stop}")

    files = files_needed(dataset, start, stop, data_dir)
    for file_name in files:
      print_data(dataset, file_name, start, stop, parameters, data_dir)

  except (util.Error, OSError, ValueError) as error:
    raise SystemExit(str(error)) from None
