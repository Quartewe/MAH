import time


class TimeoutUtils:
    _monitoring_tasks = {}
    DEFAULT_TIMEOUT = 300

    @classmethod
    def check_timeout(cls, task_name: str, timeout: int = DEFAULT_TIMEOUT) -> bool:

        now = time.time()
        
        if task_name not in cls._monitoring_tasks:
            cls._monitoring_tasks[task_name] = now
            # debug
            print(f"[MONITOR] 开始监控任务: {task_name}, 超时时间: {timeout}秒")
            #
            return False
            
        elapsed = now - cls._monitoring_tasks[task_name]
        if elapsed > timeout:
            # debug
            print(f"[ERROR] 任务 {task_name} Agent 错误! 已耗时: {elapsed:.2f}秒")
            #
            return True
            
        return False

    @classmethod
    def stop_monitoring(cls, task_name: str):
        """取消任务计时"""
        if task_name in cls._monitoring_tasks:
            del cls._monitoring_tasks[task_name]
            # debug
            print(f"[MONITOR] 已停止监控任务: {task_name}")
            #


timeout_mgr = TimeoutUtils
