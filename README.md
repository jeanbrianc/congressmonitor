# Congress Monitor

A command-line tool for monitoring periodic transaction reports (PTRs) filed by members of the U.S. Congress and Senate. The tool downloads the latest available disclosure datasets, filters to legislators you care about, and drops a CSV or text report on your Desktop (or any folder you specify). It is designed to be scheduled from cron or another job runner so you can keep tabs on recent trades automatically.

## Features

- Pulls the latest aggregated disclosure feeds for both the House and the Senate.
- Filters trades to a configurable watch list of legislators (defaults to Nancy Pelosi, David Rouzer, Debbie Wasserman Schultz, and Ron Wyden).
- Limits the report to disclosures filed within a configurable time window (24 hours by default).
- Exports to CSV (default) or a human-readable text format.
- Friendly CLI that can be invoked manually or from cron.

## Installation

```bash
pip install --upgrade pip
pip install .
```

The project requires Python 3.9 or newer. The install command creates a console entry point named `congressmonitor`.

If you prefer not to install globally, you can run the tool from the repository:

```bash
python -m congressmonitor --help
```

## Usage

```
usage: congressmonitor [-h] [--members [MEMBERS ...]] [--lookback-hours LOOKBACK_HOURS]
                       [--since SINCE] [--until UNTIL] [--output-dir OUTPUT_DIR]
                       [--output-format {csv,txt}] [--filename-prefix FILENAME_PREFIX]
                       [--skip-house] [--skip-senate] [--max-records MAX_RECORDS]
                       [--verbose] [--quiet]
```

### Examples

Generate a CSV for the default watch list covering the last 24 hours and save it to your Desktop:

```bash
congressmonitor --output-dir ~/Desktop
```

Report on trades from the past 48 hours for a custom set of legislators:

```bash
congressmonitor --members "Nancy Pelosi" "Ron Wyden" --lookback-hours 48 --output-dir ~/Desktop
```

Specify the reporting window explicitly and write a text summary instead of CSV:

```bash
congressmonitor --members all --since 2024-05-01 --until 2024-05-08T12:00:00 \
  --output-format txt --output-dir ~/Desktop/reports
```

Use the tool in a cron job that runs every morning at 8am (adjust the schedule as needed):

```
0 8 * * * /usr/bin/env python3 -m congressmonitor --output-dir ~/Desktop --lookback-hours 24 >> ~/congressmonitor.log 2>&1
```

### Command-line options

- `--members / -m`: Space-separated list of legislators to monitor. Use `all` to disable filtering. If omitted, the default watch list is used.
- `--lookback-hours`: Number of hours prior to `now` to include when `--since` is not provided (default `24`).
- `--since`: Explicit start of the reporting window (ISO 8601, e.g., `2024-05-01T00:00:00`).
- `--until`: Explicit end of the reporting window (ISO 8601, defaults to current time).
- `--output-dir`: Target directory for the generated report (defaults to `~/Desktop`).
- `--output-format`: Choose `csv` or `txt` output (default `csv`).
- `--filename-prefix`: Prefix for the output file name (default `congress_trades`).
- `--skip-house` / `--skip-senate`: Ignore one chamber's filings if you only care about the other.
- `--max-records`: Optional cap on the number of rows written.
- `--verbose` / `--quiet`: Adjust logging verbosity.

The generated CSV columns are: chamber, legislator, reported_date, transaction_date, ticker, asset_description, transaction_type, amount, owner, link, source.

## Data sources

The monitor pulls JSON datasets that mirror the official disclosure portals:

- House trades are sourced from `https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json`.
- Senate trades are sourced from `https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/transaction_report_for_<year>.json`.

If a request fails (e.g., due to networking issues), the tool logs a warning and continues with whichever chambers are reachable.

## Development

Run the unit tests with `unittest`:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

Feel free to extend the watch list or reporting logic by editing `src/congressmonitor/monitor.py` and `src/congressmonitor/cli.py`.
