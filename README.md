# Install

```
git clone https://github.com/hapi-server/server-python-psws
cd server-python-psws
python -m pip install -e .
```

# Run

Edit the `PSWS_DATA_DIR` variable in `config.json` to point to the root directory of data. See `etc/sshmnt.sh` for mounting the PSWS data directory using a SSH filesystem.

Create or update catalog. This will take a few minutes.

```
python psws/catalog.py
```

```
hapiserver --config config.json
```

For additional command-line options, see

```
hapiserver --help
```

# Test

## Without Pytest

```
cd server-python-psws
python -m pip install -e ".[test]"
python test/test_server.py
```

## With Pytest

Test the first magnetometer and Doppler datasets:

```
pytest
# or
python -m pytest -v --log-cli-level=INFO
```

Test all magnetometer and Doppler datasets:

```
python -m pytest -m full -v --log-cli-level=INFO
```

# Development

See the comments in `psws/catalog.py`, `psws/info.py`, and `psws/data.py` for examples of testing responses on command line.
