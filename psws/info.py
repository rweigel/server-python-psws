"""
Returns HAPI info JSON stdout

Equivalent API response to:
  hapi/info?dataset=<id>

Command-line usage:

  Print HAPI info for dataset to stdout
    python info.py --dataset S000028/mag
    python info.py --dataset S000028/mag --debug
  See also
    python info.py --help
"""

def info(dataset):
  import util
  from catalog import catalog
  if not isinstance(dataset, str) or not dataset.strip():
    raise util.Error("A dataset is required: use --dataset <id> or -d <id>.")
  entries = catalog(dataset=dataset)
  if not entries:
    raise util.Error(f"Dataset {dataset} not found in catalog.")
  entry = entries[0]
  if not isinstance(entry, dict) or not isinstance(entry.get("info"), dict):
    raise util.Error(f"Invalid info metadata for dataset {dataset}.")
  return entry["info"]

if __name__ == "__main__":
  import json

  import util

  try:
    args = util.cli()
    result = info(args["dataset"])
    output = json.dumps(result, indent=2)
  except (util.Error, OSError, ValueError) as error:
    raise SystemExit(str(error)) from None
  print(output)
