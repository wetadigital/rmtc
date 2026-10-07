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


class LocalInferScheduler(LocalScheduler):
    """
    Local inferencing scheduler for single-machine execution without distribution.

    The Local scheduler provides a simple execution strategy for inferencing jobs
    that run on a single machine without any distributed computing capabilities.
    It executes inferencing tasks sequentially using local resources and provides
    basic job lifecycle management.
    """

    def __init__(
        self,
        tracker=None,
        env_manager=None,
        inference=None,
        asset_manager=None,
        rmtc_system=None,
    ):
        super(LocalInferScheduler, self).__init__(
            task=inference,
            tracker=tracker,
            asset_manager=asset_manager,
            env_manager=env_manager,
            rmtc_system=rmtc_system,
        )

    @property
    def inference(self):
        return self.task

    def start(self):
        """Start the local inferencing execution."""

        # check
        if self.inference is None:
            raise RMTCException("No task")
        if self.inference.inferer is None:
            raise RMTCException(f"No inferer set for task {self.inference}")
        if self.inference.model is None:
            raise RMTCException(f"No model set for task {self.inference}")
        if self.inference.inputs is None:
            raise RMTCException(f"No inputs set for task {self.inference}")
        if self.asset_manager is None:
            raise RMTCException(f"No asset manager set for task {self.inference}")

        # Create a local job
        self.job = LocalJob(
            task=self.inference,
            job_id="local",
        )

        # Add an executor for the inferencer function
        executor = FunctionExecutor(
            env=self.env,
            env_manager=self.env_manager,
        )
        executor.set_function(
            self.inference.inferer,
            inference=self.inference,
            asset_manager=self.asset_manager,
        )
        self.job.add_executor(executor)

        # start
        with Immutable(self.inference):
            self.inference.start()
            self.job.start()

        # store result
        _, outputs, metric = self.job.results[0]
        self.inference.outputs = outputs
        self.inference.metric = metric
        self.inference.finish()

    def get_artifact(self):
        return self.inference


class SimpleInferAsync(SimpleAsyncMixin, LocalInferScheduler):
    """Local training scheduler that runs in another process."""

    pass
