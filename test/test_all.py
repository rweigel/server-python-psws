# Usage:
#   python test_all.py
#
# Using Pytest:
#   Short test (first magnetometer and Doppler datasets):
#     python -m pytest test/test_all.py::test_short -v --log-cli-level=INFO
#   Full test:
#     python -m pytest test/test_all.py::test_all -v --log-cli-level=INFO

import logging

logging.basicConfig(level=logging.INFO, format='%(name)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def _print_title(url):
  line = len(url)*"-"
  logger.info(line)
  logger.info(f"Testing {url}")
  logger.info(line)


def test_short():
  test_all(short=True)


def test_all(short=False):

  import pathlib

  import hapiserver

  wait = {"retries": 10, "delay": 0.5}

  # Set config.json path to be one dir up from this test script
  config = pathlib.Path(__file__).parent.parent / "config.json"

  configs = hapiserver.cli(config=config)

  _run(configs, 'mag', wait, short=short)
  _run(configs, 'dop', wait, short=short)


def _run(configs, data_type, wait, short=False):
  import requests
  import utilrsw.uvicorn
  import hapiclient

  port = configs['server']['--port']
  url_base = f"http://0.0.0.0:{port}/hapi"

  wait['url'] = url_base

  utilrsw.uvicorn.start('hapiserver.app', configs, wait)

  url = url_base
  _print_title(url)
  response = requests.get(url)
  assert response.status_code == 200
  assert 'text/html' in response.headers['Content-Type']
  assert 'HAPI' in response.text

  url = f"{url_base}/catalog"
  response = requests.get(url)
  assert response.status_code == 200
  assert 'application/json' in response.headers['Content-Type']
  assert 'catalog' in response.json()
  assert len(response.json()['catalog']) > 0

  # Find all datasets with id having "mag"
  catalog = response.json()['catalog']

  catalog = [d for d in catalog if f'/{data_type}' in d['id']]
  if not catalog:
    logger.warning(f"No {data_type} datasets found in the catalog.")

  for dataset in catalog:
    logger.info(f"Dataset: {dataset['id']}")

    # Fetch info dataset
    url = f"{url_base}/info?dataset={dataset['id']}"
    response = requests.get(url)
    assert response.status_code == 200
    assert 'application/json' in response.headers['Content-Type']
    assert 'parameters' in response.json()
    assert len(response.json()['parameters']) > 0

    info = response.json()
    assert 'startDate' in info
    assert 'stopDate' in info
    start = info['startDate']

    # Add 1 hour
    from datetime import datetime, timedelta
    start_dt = datetime.fromisoformat(start)
    stop = (start_dt + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')

    if False:
      url = f"{url_base}/data?dataset={dataset['id']}&start={start}&stop={stop}"
      response = requests.get(url)
      assert response.status_code == 200
      assert 'text/csv' in response.headers['Content-Type']
    else:
      # Verify that HAPI client can read the CSV content
      data, _ = hapiclient.hapi(url_base, dataset['id'], '', start, stop)

    if short:
      break

if __name__ == "__main__":
  #test_all()
  test_short()
  #_run(configs, 'mag', wait)
  #_run(configs, 'dop', wait)
