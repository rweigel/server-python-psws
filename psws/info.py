# Usage:
#   python info.py --dataset <id>
# where <id> is the station ID, e.g., S000028 found in first column of catalog.csv
#
# Examples:
#   python info.py --dataset S000028/mag
#   python info.py -d N000001/dop/WWV5

# Returns HAPI info JSON stdout
#
# Equivalent API response to:
#   hapi/info?dataset=<id>


def info(dataset):
  from catalog import catalog
  info = catalog(dataset=dataset)
  return info[0]

if __name__ == "__main__":
  import json

  import util

  args = util.cli()
  if args["dataset"] is None:
    raise SystemExit("A dataset is required: use --dataset <id> or -d <id>.")

  print(json.dumps(info(args["dataset"]), indent=2))
