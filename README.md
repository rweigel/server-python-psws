# Install

```
conda deactivate
conda env remove -y -n psws-python-3.11
conda create -y -n psws-python-3.11 python=3.11
conda activate psws-python-3.11
```

```
git clone https://github.com/hapi-server/server-python-psws
python -m pip install -e .
```

# Run

```
cd server-python-general-psws
hapiserver --config config.json
```

For additional command-line options, see

```
hapiserver --help
```

# Test

```
pip install requests pandas
cd server-python-psws
python test.py --config config.json
```

# Development

Assumes magnetometer data in directories as under `data/` - each subdir corresponds to data from a station with ID in `catalog.csv`.

The responses to HAPI endpoints are implemented as Python scripts that return the response to `stdout`.

Return response to `/hapi/catalog` request

```
python bin/catalog.py
```

Return response to `/hapi/info` request

```
python bin/info.py S000028
```

Return response to `/hapi/data` request

```
python bin/data.py W2NAF 2025-10-20 2025-10-21
```
