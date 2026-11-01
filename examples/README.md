# Examples (TEMPLATE DATA – not measured)

`base.csv` / `after.csv` only show the CSV format and exercise the pipeline.
The values are illustrative, NOT real measurements. Never report results computed
from them as real savings. Replace them with meter/sensor data.

```bash
python controller/v91_cli.py impact energy-saving-test \
  --baseline examples/base.csv --after examples/after.csv --unit kWh \
  --co2-factor 0.380 --co2-source "<cite your source, e.g. UBA Strommix, year>" \
  --ledger demo_ledger.jsonl
python controller/v91_cli.py report --ledger demo_ledger.jsonl
```

`--co2-source` is mandatory with `--co2-factor`. The factor is user-supplied and not verified here.
