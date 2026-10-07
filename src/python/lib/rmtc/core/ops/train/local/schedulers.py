# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.core.ops.scheduling.local.schedulers import (
    FunctionExecutor,
    LocalJob,
    LocalScheduler,
    SimpleAsyncMixin,
)
from rmtc.system.objects import Immutable
from rmtc.system import RMTCException


class LocalTrainScheduler(LocalScheduler):
    """
    Local training scheduler for single-machine execution without distribution.

    The Local scheduler provides a simple execution strategy for training jobs
    that run on a single machine without any distributed computing capabilities.
    It executes training tasks sequentially using local resources and provides
    basic job lifecycle management.
    """

    def __init__(
        self,
        tracker=None,
        run=None,
        env=None,
        env_manager=None,
        asset_manager=None,
        rmtc_system=None,
    ):
        """Initialize Local scheduler with tracker, run, and environment."""
        super(LocalTrainScheduler, self).__init__(
            tracker=tracker,
            task=run,
            env=env,
            env_manager=env_manager,
            asset_manager=asset_manager,
            rmtc_system=rmtc_system,
        )

    @property
    def run(self):
        return self.task

    def start(self):
        """Start the local training execution."""

        # check
        if self.run is None:
            raise RMTCException("No task")
        if self.run.trainer is None:
            raise RMTCException(f"No trainer set for task {self.run}")
        if self.run.dataset is None:
            raise RMTCException(f"No dataset set for task {self.run}")
        if self.asset_manager is None:
            raise RMTCException(f"No asset manager set for task {self.run}")

        # Create a local job
        self.job = LocalJob(
            task=self.run,
            job_id="local",
            tracker=self.tracker,
        )

        # Add an executor for the trainer function
        executor = FunctionExecutor(
            env=self.env,
            env_manager=self.env_manager,
        )
        executor.set_function(
            self.run.trainer,
            tracker=self.tracker,
            run=self.run,
            asset_manager=self.asset_manager,
        )
        self.job.add_executor(executor)

        # Start
        with Immutable(self.run):
            self.run.start()
            self.tracker.start(run=self.run)
            self.job.start()

        model, weights, metric, checkpoints = self.job.results[0]

        # finish
        self.tracker.finish()
        self.run.model = model
        self.run.metric = metric
        self.run.result_weights = weights
        self.run.result_checkpoints = checkpoints
        self.run.finish()

    def get_artifact(self):
        """Return managed artifact (run)"""
        return self.run


class SimpleTrainAsync(SimpleAsyncMixin, LocalTrainScheduler):
    """Local training scheduler that runs in another process."""

    pass
