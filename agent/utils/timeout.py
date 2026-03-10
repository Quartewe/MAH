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
            print(f"Start monitoring task: {task_name}, timeout: {timeout}s")
            #
            return False
            
        elapsed = now - cls._monitoring_tasks[task_name]
        if elapsed > timeout:
            # debug
            print(f"Task {task_name}'s Agent Error! Elapsed: {elapsed:.2f}s")
            #
            return True
            
        return False

    @classmethod
    def stop_monitoring(cls, task_name: str):
        """取消任务计时"""
        if task_name in cls._monitoring_tasks:
            del cls._monitoring_tasks[task_name]
            # debug
            print(f"Stopped monitoring task: {task_name}")
            #


timeout_mgr = TimeoutUtils
