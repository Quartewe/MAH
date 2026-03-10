from datetime import datetime, timedelta
import time

from .data_io import IOUtils, DEFAULT_STATE


class ResourceUtils:
    AP_RECOVERY_INTERVAL = 480  # 8分钟 480秒
    CN_RESET_HOUR = 3  # CN凌晨3点刷新

    @classmethod
    def get_estimated_resources(cls) -> dict:
        state = IOUtils.read_data()
        res = state.get("resources", DEFAULT_STATE["resources"])
        now_ts = time.time()

        estimated = {}

        # 体力
        print("[DEBUG] now calculating AP data...")
        ap = res.get("AP", {"value": 0, "upper_limit": 0, "last_updated": 0})
        if ap["last_updated"] == 0 or cls.AP_RECOVERY_INTERVAL <= 0:
            estimated["AP"] = ap["value"]
        else:
            passed_time = now_ts - ap["last_updated"]
            recovered = int(passed_time // cls.AP_RECOVERY_INTERVAL)
            estimated["AP"] = min(ap["value"] + recovered, ap.get("upper_limit", 0))
        # debug
        print("[DEBUG] AP data calculated")
        #

        # DP
        print("[DEBUG] now calculating DP data...")
        dp = res.get("DP", {"value": 0, "upper_limit": 3, "last_updated": 0})
        if dp["last_updated"] == 0:
            estimated["DP"] = dp["value"]
        else:
            last_dt = datetime.fromtimestamp(dp["last_updated"]) - timedelta(
                hours=cls.CN_RESET_HOUR
            )
            now_dt = datetime.fromtimestamp(now_ts) - timedelta(hours=cls.CN_RESET_HOUR)
            days_passed = (now_dt.date() - last_dt.date()).days

            estimated["DP"] = min(
                dp["value"] + max(0, days_passed), dp.get("upper_limit", 3)
            )
        # debug
        print("[DEBUG] DP data calculated")
        #

        # 石头虹碎
        estimated["Stone"] = res.get("Stone", 0)
        estimated["RF"] = res.get("RF", 0)
        # debug
        print("[DEBUG] Stone and RF data already recorded")
        #
        return estimated


resource_mgr = ResourceUtils
