
def listfiles(dir_path):
  import os
  return [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]

def listdirs(dir_base, regex=None, sort=True):
  import os
  import re

  # Keep only directories
  def is_dir(d):
    return os.path.isdir(os.path.join(dir_base, d))

  try:
    dir_list = os.listdir(dir_base)
  except Exception as e: # noqa: BLE001
    #logger.error(dir_base, f"Failed to list directory {dir_base}: {e}")
    return []

  if sort:
    dir_list = sorted(dir_list)

  dir_pattern = re.compile(regex) if regex is not None else None
  return [
    dir for dir in dir_list
    if (dir_pattern is None or dir_pattern.fullmatch(dir))
    and is_dir(dir)
  ]

def cli():
  import os
  import re
  import argparse
  from pathlib import Path

  parser = argparse.ArgumentParser(
      description='Read Digital RF data from PSWS station directories.'
  )
  parser.add_argument(
    '-d', '--dataset',
    default=None,
    required=False,
    help='Dataset ID, e.g., S000028/mag.'
  )
  parser.add_argument(
      '--station-dir',
      default='/home',
      required=False,
      dest='station_dir',
      help='Directory containing station subdirectories (e.g., S0000183, N000020).'
  )
  parser.add_argument(
      '--station-dir-regex',
      default='^[A-Z][0-9]{6}',
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

  base_dir = Path(__file__).resolve().parent
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

  args, _ = parser.parse_known_args()

  try:
    re.compile(args.station_dir_regex)
  except re.error as error:
    raise SystemExit(f"Invalid --station-dir-regex: {error}")

  return vars(args)
