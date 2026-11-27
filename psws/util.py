from functools import cache
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent / "data"
# Base directory for output data storage. One dir up from the current file.
out_dir = Path(__file__).resolve().parent.parent / "data-out"

STATION_DIR = "/home"
STATION_DIR_FALLBACK = base_dir / "home"
STATION_DIR_REGEX = "^[A-Z][0-9]{6}"

CACHE_DIR = out_dir / "cache"
LOG_DIR = out_dir / "log"
CATALOG_DIR = CACHE_DIR / "hapi"

class Error(ValueError):
  """A non-fatal error."""


def log(msg, *, debug=None):
  import sys
  # Debug keyword needed when log() is called from cli().
  if debug is None:
    debug = cli()["debug"]
  if debug:
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
  from textwrap import dedent

  parser = argparse.ArgumentParser(
    description='Read Digital RF data from PSWS station directories.'
  )
  if endpoint == "info":
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.epilog = dedent("""\
      Examples:
        Print HAPI info for a dataset to stdout:
          python psws/info.py --dataset S000028/mag

        Enable debug output:
          python psws/info.py --dataset S000028/mag --debug
    """)

  parser.add_argument(
    '-d', '--dataset',
    default=None,
    required=False,
    help='Dataset ID, e.g., S000028/mag.'
  )

  if endpoint == "data":
    parser.add_argument(
      '--parameters', nargs='?', const=None, default=None,
      help='Comma-separated parameter names.')
    parser.add_argument(
      '--start', default=None,
      help='Start time in UTC, e.g., 2025-10-20T00:00:00Z.')
    parser.add_argument(
      '--stop', default=None,
      help='Exclusive stop time in UTC, e.g., 2025-10-21T00:00:00Z.')

  parser.add_argument(
      '--station-dir',
      default=None,
      type=Path,
      required=False,
      dest='station_dir',
      help=(f'Directory containing station subdirectories '
            f'(e.g., S0000183, N000020). Default is {STATION_DIR}. '
            f'If the default is unavailable or has no matching station '
            f'subdirectories, use {STATION_DIR_FALLBACK} relative to this '
            'script. Explicit CLI or environment paths never fall back. ')
      )

  if endpoint != "data":
    parser.add_argument(
        '--station-dir-regex',
        default=STATION_DIR_REGEX,
        required=False,
        dest='station_dir_regex',
        help=('Regex pattern that must match the entire station subdirectory '
              'name. Use .* to match any directory name.')
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


  parser.add_argument(
      '--cache-dir', type=Path, default=CACHE_DIR, dest='cache_dir',
      help=f'Directory to use for caching data and metadata. Default: {CACHE_DIR}. '
  )
  parser.add_argument(
      '--log-dir', type=Path, default=LOG_DIR, dest='log_dir',
      help=f'Directory to use for log files. Default: {LOG_DIR}.'
  )
  if endpoint != "data":
    parser.add_argument(
        '--catalog-dir', type=Path, default=CATALOG_DIR, dest='catalog_dir',
        help=f'Directory to write hapi catalog. Default: {CATALOG_DIR}.'
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

  if args["station_dir"] is None:
    args["station_dir"] = Path(STATION_DIR)
    fallback_reason = None
    if not args["station_dir"].is_dir():
      fallback_reason = "is unavailable"
    else:
      station_pattern = re.compile(
        args.get("station_dir_regex", STATION_DIR_REGEX)
      )
      try:
        with os.scandir(args["station_dir"]) as entries:
          has_stations = any(
            station_pattern.fullmatch(entry.name) and entry.is_dir()
            for entry in entries
          )
      except OSError as error:
        raise Error(
          f"Failed to inspect station directory {STATION_DIR}: {error}"
        ) from error
      if not has_stations:
        fallback_reason = "has no matching station subdirectories"
    if fallback_reason is not None:
      args["station_dir"] = (base_dir / STATION_DIR_FALLBACK).resolve()
      log(
        f"Default station directory {STATION_DIR} {fallback_reason}; "
        f"using fallback {args['station_dir']}.",
        debug=args["debug"],
      )

  return args


def validate_station_dir(station_dir):
  """Validate source storage only when a fresh scan needs it."""
  if not station_dir.exists():
    raise Error(f"Station directory {station_dir} does not exist.")
  if not station_dir.is_dir():
    raise Error(f"Station path {station_dir} is not a directory.")
