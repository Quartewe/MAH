"""
项目路径管理模块 - 一次配置，全项目使用
基于模块位置自动计算绝对路径，不依赖工作目录
"""

from pathlib import Path

# 项目根目录：agent/utils/proj_path.py -> agent/utils -> agent -> 项目根
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _pick_existing_path(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
AUTO_COMBAT_DIR = DATA_DIR / "auto_combat"
DEBUG_DIR = PROJECT_ROOT / "debug"
ON_ERROR_DIR = str(PROJECT_ROOT / "debug" / "on_error")

# 兼容两种布局：
# 1) 源码目录: assets/resource, assets/interface.json
# 2) 打包目录: resource, interface.json
RESOURCE_DIR = _pick_existing_path(
    PROJECT_ROOT / "resource",
    PROJECT_ROOT / "assets" / "resource",
)
INDEX_DIR = _pick_existing_path(
    PROJECT_ROOT / "resource" / "index",
    PROJECT_ROOT / "assets" / "index",
)
INTERFACE_PATH = _pick_existing_path(
    PROJECT_ROOT / "interface.json",
    PROJECT_ROOT / "assets" / "interface.json",
)
MAA_CONFIG_PATH = _pick_existing_path(
    PROJECT_ROOT / "config" / "maa_option.json",
    PROJECT_ROOT / "assets" / "config" / "maa_option.json",
    PROJECT_ROOT / "resource" / "config" / "maa_pi_config.json",
)

# 数据文件
STATE_FILE = str(DATA_DIR / "state.json")
CHAR_FILE = str(INDEX_DIR / "characters.json")
CHAR_LOWSTAR_FILE = str(INDEX_DIR / "characters_lowstar.json")
AR_FILE = str(INDEX_DIR / "ar.json")
UI_FILE = str(INDEX_DIR / "ui.json")

# 资源目录
IMAGE_DIR = RESOURCE_DIR / "image"
MODEL_DIR = RESOURCE_DIR / "model"

# 管道配置
PIPELINE_DIR = RESOURCE_DIR / "pipeline"

# 接口配置
INTERFACE_FILE = str(INTERFACE_PATH)
MAA_CONFIG_FILE = str(MAA_CONFIG_PATH)


# 便利函数
def get_data_dir() -> str:
    """获取数据目录绝对路径"""
    return str(DATA_DIR)


def get_auto_combat_dir() -> str:
    """获取自动战斗配置目录绝对路径"""
    return str(AUTO_COMBAT_DIR)


def get_debug_dir() -> str:
    """获取调试目录绝对路径"""
    return str(DEBUG_DIR)


def get_resource_dir() -> str:
    """获取资源目录绝对路径"""
    return str(RESOURCE_DIR)
