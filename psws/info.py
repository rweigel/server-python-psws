"""
Returns HAPI info JSON stdout

Equivalent API response to:
  hapi/info?dataset=<id>

Command-line usage:

  Print HAPI info for dataset to stdout
    python info.py --dataset S000028/mag
  See also
    python info.py --help
"""

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
