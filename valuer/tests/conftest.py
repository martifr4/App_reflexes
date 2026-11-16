import datetime as dt
import json
from pathlib import Path

import pytest

from valuer.edgar.ingest import load_documents
from valuer.market.prices import from_csv
from valuer.params import load_params
from valuer.store.store import FactStore

FIX = Path(__file__).parent / "fixtures"
PARAMS_DIR = Path(__file__).parent.parent / "params" / "v001"
AS_OF = dt.date(2026, 11, 16)


@pytest.fixture
def home(tmp_path):
    store = FactStore(tmp_path)
    load_documents(store, "LECO", json.loads((FIX / "LECO_submissions.json").read_text()),
                   json.loads((FIX / "LECO_companyfacts.json").read_text()))
    store.add_prices("LECO", "csv", from_csv(FIX / "LECO_prices.csv"))
    return tmp_path


@pytest.fixture
def store(home):
    return FactStore(home)


@pytest.fixture
def params():
    return load_params(PARAMS_DIR, sic=3540, ticker="LECO")
