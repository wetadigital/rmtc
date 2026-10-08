# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import multiprocessing

from rmtc.ops.scheduling import Job, Scheduler, Executor


class LocalScheduler(Scheduler):
    """
    Local scheduler for single-machine execution without distribution.

    The Local scheduler provides a simple execution strategy for training and
    inference jobs that run on a single machine without any distributed computing
    capabilities. It executes tasks sequentially using local resources and
    provides basic job lifecycle management.
    """

    def __init__(
        self,
        tracker=None,
        task=None,
        env=None,
        env_manager=None,
        asset_manager=None,
        rmtc_system=None,
    ):
        """Initialize Local scheduler with tracker, task, and environment."""
        super(LocalScheduler, self).__init__(
            tracker=tracker,
            task=task,
            asset_manager=asset_manager,
            env=env,
            env_manager=env_manager,
        )
        self._system = rmtc_system

    def start(self):
        """Start the local execution. In this example, we assume self.task is callable."""

        # Start the job
        self.job.start()

        return self.job.results

    def init(self):
        """Initialize scheduler resources (no-op for local execution)."""
        raise NotImplementedError()

    def resume(self):
        """Resume paused job (no-op for local execution)."""
        self.job.resume()

    def pause(self):
        """Pause running job (no-op for local execution)."""
        self.job.pause()

    def stop(self):
        """Stop running job (no-op for local execution)."""
        self.job.stop()

    def join(self):
        """Wait for completion (no-op for local execution)."""
        raise NotImplementedError()


class SimpleAsyncMixin:
    """Scheduler mixin to run start() in another process."""

    def start(self):
        process = multiprocessing.Process(target=self._start)
        process.start()

    def _start(self):
        if self._system is not None:
            self._system.push()
        super(SimpleAsyncMixin, self).start()
        if self._system is not None:
            self._system.push()


class SimpleAsync(SimpleAsyncMixin, LocalScheduler):
    """Local scheduler that runs in another process."""

    pass


class LocalJob(Job):
    """
    Local job implementation for sequential task execution.

    The LocalJob class provides a concrete implementation of the Job interface
    for local execution environments. It manages a collection of executors
    and runs them sequentially on the local machine, collecting results
    for downstream processing.
    """

    def __init__(
        self,
        tracker=None,
        task=None,
        job_id=None,
    ):
        super(LocalJob, self).__init__(
            tracker=tracker,
            task=task,
            job_id=job_id,
        )
        self._executors = []
        self._results = []

    @property
    def results(self):
        """Get the list of results from completed executors."""
        return self._results

    def start(self):
        """Execute all registered executors sequentially and collect results."""
        # Execute tasks sequentially
        for executor in self._executors:
            result = executor()
            self._results.append(result)

    def add_executor(self, executor):
        """Add an executor to the job's execution queue.

        Args:
            executor (Executor): Executor to add to the job.
        """
        executor.job = self
        self._executors.append(executor)

    def get_executors(self):
        """Get the list of registered executors."""
        return self._executors

    def resume(self):
        """Resume paused job execution (no-op for local jobs)."""
        raise NotImplementedError()

    def pause(self):
        """Pause job execution (no-op for local jobs)."""
        raise NotImplementedError()

    def stop(self):
        """Stop job execution (no-op for local jobs)."""
        raise NotImplementedError()


class FunctionExecutor(Executor):
    """
    Executor for deferred function calls with argument binding.

    The FunctionExecutor class provides a simple mechanism for deferring
    function execution until explicitly called. It stores a function
    reference along with its arguments and keyword arguments, enabling
    flexible task scheduling and execution patterns.

    This executor is particularly useful for wrapping inferencing functions
    or other callable objects that need to be executed as part of a
    job's execution pipeline.
    """

    def __init__(
        self,
        job=None,
        env=None,
        env_manager=None,
    ):
        """Initialize FunctionExecutor with no function set."""
        super(FunctionExecutor, self).__init__(
            job=job,
            env=env,
            env_manager=env_manager,
        )
        self._func = None
        self._args = []
        self._kwargs = {}

    def __call__(self, tracker, task):
        """Execute the stored function with bound arguments."""
        if self._func is None:
            raise RuntimeError("Executor has no executable")
        self.env_manager.setup(self.env)
        result = self._func(*self._args, **self._kwargs)
        self.env_manager.teardown(self.env)
        return result

    def set_function(self, func, *args, **kwargs):
        """Set the function and arguments to execute."""
        self._func = func
        self._args = args
        self._kwargs = kwargs.copy()
