# About

This is an in-development HAPI server for PSWS data.

# Install

```
git clone https://github.com/hapi-server/server-python-psws
cd server-python-psws
python -m pip install -e .
```

# Set-up data

## Using sample data

Download and extract a sample of the data taken from `pswsnetwork.eng.ua.edu:/home` and modify the `PSWS_DATA_DIR` variable in `config.json` to point to it.

```bash
cd server-python-psws/
mkdir -p data/
cd data/
curl -O http://mag.gmu.edu/git-data/server-python-psws/data.tgz
tar zxvf data.tgz
```

## On `pswsnetwork.eng.ua.edu`

Edit the `PSWS_DATA_DIR` variable in `config.json` to be `/home`.

# Prepare `catalog`

Create or update catalog. This will take a long time (hours?) on `pswsnetwork.eng.ua.edu:/home`. For the sample data, it takes ~5 seconds.

```bash
python psws/catalog.py --debug
```

# Run

Start server

```bash
hapiserver --config config.json
```

For additional `hapiserver` command-line options, see

```bash
hapiserver --help
```

# Test

## Without Pytest

```bash
cd server-python-psws
python -m pip install -e ".[test]"
python test/test_server.py
```

## With Pytest

Test the first magnetometer and Doppler datasets:

```bash
pytest
# or
python -m pytest -v --log-cli-level=INFO
```

Test all magnetometer and Doppler datasets:

```bash
python -m pytest -m full -v --log-cli-level=INFO
```

# Development

See

```bash
python psws/catalog.py -h
python psws/info.py -h
python psws/data.py -h
```

for examples of testing responses on command line.
