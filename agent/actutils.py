"""
兼容层：将所有导入重定向到 utils/ 包。
旧代码中 import actutils 或 from actutils import xxx 仍然可用。
新代码请直接使用 from utils import xxx。
"""

from utils import (
    IOUtils, data_io,
    MatchUtils, match_mgr,
    TimeoutUtils, timeout_mgr,
    ActUtils, act_mgr,
    proj_path,
)

CONFIG_FILE = proj_path.CONFIG_FILE
CHAR_FILE = proj_path.CHAR_FILE

