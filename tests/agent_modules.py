"""Load agent modules without starting the agent or reading user configuration."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
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
    # Isolated action tests must not switch Maa's global library to AgentServer
    # mode or register callbacks when importing the module under test.
    agent_server = ModuleType("maa.agent.agent_server")
    agent_server.AgentServer = SimpleNamespace(
        custom_action=lambda name: lambda action: action,
    )
    overrides = {"utils": utils, "maa.agent.agent_server": agent_server}
    previous_modules = {name: sys.modules.get(name) for name in overrides}
    sys.modules.update(overrides)
    try:
        spec.loader.exec_module(module)
    finally:
        for name, previous_module in previous_modules.items():
            if previous_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module
    return module
