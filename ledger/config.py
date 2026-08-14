"""Where the ledger files live.

One JSON file, `ledger.json`, found by walking up from the working directory.
JSON and not TOML on purpose: tomllib is 3.11 and this has to run on 3.9 with
no dependency.
"""

import json
import os

CONFIG_NAME = "ledger.json"
DEFAULTS = {"dir": "ledger"}


def find_config(start=None):
    here = os.path.abspath(start or os.getcwd())
    while True:
        candidate = os.path.join(here, CONFIG_NAME)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def load(start=None):
    conf = dict(DEFAULTS)
    path = find_config(start)
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            raise ValueError("%s is not readable JSON: %s" % (path, exc))
        if not isinstance(data, dict):
            raise ValueError("%s must contain a JSON object" % path)
        conf.update(data)
        conf["_path"] = path
        conf["_root"] = os.path.dirname(path)
    else:
        conf["_path"] = None
        conf["_root"] = os.path.abspath(start or os.getcwd())
    return conf


def resolve_dir(cli_dir=None, start=None):
    """--dir beats LEDGER_DIR beats ledger.json beats the default `ledger/`."""
    if cli_dir:
        return os.path.abspath(cli_dir)
    env = os.environ.get("LEDGER_DIR")
    if env:
        return os.path.abspath(env)
    conf = load(start)
    return os.path.abspath(os.path.join(conf["_root"], conf.get("dir") or "ledger"))
