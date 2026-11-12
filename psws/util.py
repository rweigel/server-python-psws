from functools import cache

STATION_DIR = "/home"
STATION_DIR_REGEX = "^[A-Z][0-9]{6}"

class Error(ValueError):
  """A non-fatal error."""


def log(msg):
  import sys
  if cli()["debug"]:
    print(msg, file=sys.stderr)


def listfiles(dir_path):
  from pathlib import Path
  try:
    return sorted(path.name for path in Path(dir_path).iterdir() if path.is_file())
  except Exception as error:
    raise Error(f"Failed to list files in {dir_path}: {error}") from error


def listdirs(dir_base, regex=None, sort=True):
  import os
  import re

  # Keep only directories
  def is_dir(d):
    return os.path.isdir(os.path.join(dir_base, d))

  try:
    dir_list = os.listdir(dir_base)
  except Exception as error:  # noqa: BLE001
    log(f"Failed to list directories in {dir_base}: {error}; skipping directory.")
    return []

  if sort:
    dir_list = sorted(dir_list)

  dir_pattern = re.compile(regex) if regex is not None else None
  return [
    dir for dir in dir_list
    if (dir_pattern is None or dir_pattern.fullmatch(dir))
    and is_dir(dir)
  ]

@cache
def cli(*, endpoint=None):
  import argparse
  import os
  import re
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

  if endpoint == "data":
    parser.add_argument(
      '--parameters', nargs='?', const=None, default=None, help='Comma-separated parameter names.')
    parser.add_argument(
      '--start', default=None, help='Start time in UTC, e.g., 2025-10-20T00:00:00Z.')
    parser.add_argument(
      '--stop', default=None, help='Exclusive stop time in UTC, e.g., 2025-10-21T00:00:00Z.')

  parser.add_argument(
      '--station-dir',
      default=STATION_DIR,
      type=Path,
      required=False,
      dest='station_dir',
      help=f'Directory containing station subdirectories (e.g., S0000183, N000020). Default is {STATION_DIR}.'
  )

  if endpoint != "data":
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

  base_dir = Path(__file__).resolve().parent
  cache_dir = base_dir / "data" / "cache"
  log_dir = base_dir / "data" / "log"
  catalog_dir = base_dir / "data" / "hapi"

  parser.add_argument(
      '--cache-dir', type=Path, default=cache_dir, dest='cache_dir',
      help=f'Directory to use for caching sample data. Default is {cache_dir}. PSWS_CACHE_DIR overrides this option.'
  )
  parser.add_argument(
      '--log-dir', type=Path, default=log_dir, dest='log_dir',
      help=f'Directory to use for log files. Default is {log_dir}.'
  )
  if endpoint != "data":
    parser.add_argument(
        '--catalog-dir', type=Path, default=catalog_dir, dest='catalog_dir',
        help=f'Directory to write hapi catalog. Default is {catalog_dir}.'
    )

  args, _ = parser.parse_known_args()
  if endpoint == "data" and (args.parameters is None or not args.parameters.strip()):
    args.parameters = None

  if endpoint != "data":
    try:
      re.compile(args.station_dir_regex)
    except re.error as error:
      raise Error(f"Invalid --station-dir-regex: {error}") from error

  args = vars(args)
  for environment_name, option_name in (
    ("PSWS_CACHE_DIR", "cache_dir"),
    ("PSWS_DATA_DIR", "station_dir"),
  ):
    if environment_name in os.environ:
      args[option_name] = Path(os.environ[environment_name])
  return args


def validate_station_dir(station_dir):
  """Validate source storage only when a fresh scan needs it."""
  if not station_dir.exists():
    raise Error(f"Station directory {station_dir} does not exist.")
  if not station_dir.is_dir():
    raise Error(f"Station path {station_dir} is not a directory.")
