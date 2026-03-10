"""
兼容层：将所有导入重定向到 utils/ 包。
旧代码中 import actutils 或 from actutils import xxx 仍然可用。
新代码请直接使用 from utils import xxx。
"""

from utils import (
    IOUtils, data_io, DEFAULT_STATE, STATE_FILE, CHAR_FILE,
    MatchUtils, match_mgr,
    TimeoutUtils, timeout_mgr,
    ResourceUtils, resource_mgr,
    MissionUtils, mission_mgr,
    ActUtils, act_mgr,
)


