# Install

```
git clone https://github.com/hapi-server/server-python-psws
cd server-python-psws
python -m pip install -e .
```

# Run

If executing on `pswsnetwork.eng.ua.edu`

* Edit the `PSWS_DATA_DIR` variable in `config.json` to be `/home`.

Otherwise,

* edit and execute `etc/sshmnt.sh` to mount the PSWS data directory `pswsnetwork.eng.ua.edu:/home` using a SSH filesystem; modify the `PSWS_DATA_DIR` variable in `config.json` to point to the mounted directory.

* download and extract a sample of the data at `pswsnetwork.eng.ua.edu:/home` and modify the `PSWS_DATA_DIR` variable in `config.json` to point to it.

  ```bash
  mkdir -p data/;
  cd data/
  curl -O http://mag.gmu.edu/git-data/server-python-psws/data.tgz
  tar zxvf data.tgz
  ```

Create or update catalog. This will take a long time (hours?) on `pswsnetwork.eng.ua.edu:/home`. For the sample data, it takes ~5 seconds.

```
python psws/catalog.py --debug
```

Without `--station-dir` or `PSWS_DATA_DIR`, the scripts use `/home`.
If `/home` is unavailable or has no matching station subdirectories, they use
the repository's `data/` directory and log the fallback to stderr only with
`--debug`.
Explicit CLI or environment paths never fall back;
`PSWS_DATA_DIR` takes precedence over `--station-dir`.

Start server

```
hapiserver --config config.json
```

For additional `hapiserver` command-line options, see

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
