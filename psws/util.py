
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

