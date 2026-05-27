from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


class TaskScheduler:
    """任务调度器封装。

    统一管理 APScheduler 生命周期，并提供任务注册方法。
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()

    @property
    def running(self) -> bool:
        return bool(self._scheduler.running)

    @property
    def job_count(self) -> int:
        """当前调度器任务数量。"""
        return len(self._scheduler.get_jobs())

    def GetJobIds(self) -> list[str]:
        """返回当前调度器中的任务 ID 列表。"""
        return [str(job.id) for job in self._scheduler.get_jobs()]

    async def Start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    async def Shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def AddOrReplaceCronJob(self, job_id: str, cron_expr: str, callback, args: list | None = None) -> None:
        """注册或替换 cron 任务。"""
        trigger = CronTrigger.from_crontab(cron_expr)
        self._scheduler.add_job(
            callback,
            trigger=trigger,
            args=args or [],
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    def AddOrReplaceIntervalJob(self, job_id: str, seconds: int, callback, args: list | None = None) -> None:
        """注册或替换 interval 任务。"""
        trigger = IntervalTrigger(seconds=max(5, seconds))
        self._scheduler.add_job(
            callback,
            trigger=trigger,
            args=args or [],
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    def RemoveJob(self, job_id: str) -> None:
        if self._scheduler.get_job(job_id) is not None:
            self._scheduler.remove_job(job_id)
