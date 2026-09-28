"""Load agent modules without starting the agent or reading user configuration."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


def load_agent_module(relative_path, **dependencies):
    utils = SimpleNamespace(
        logger=Mock(), timeout_mgr=Mock(check_timeout=Mock(return_value=False)),
        data_io=Mock(read_data=Mock(return_value={})),
        proj_path=SimpleNamespace(UI_FILE="unused"),
        match_mgr=Mock(fuzzy_match=Mock(return_value=False)),
        info_share=SimpleNamespace(current_lang=""),
    )
    vars(utils).update(dependencies)
    spec = importlib.util.spec_from_file_location(
        "regression_" + Path(relative_path).stem, ROOT / relative_path
    )
    module = importlib.util.module_from_spec(spec)
    previous_utils = sys.modules.get("utils")
    sys.modules["utils"] = utils
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_utils is None:
            del sys.modules["utils"]
        else:
            sys.modules["utils"] = previous_utils
    return module
