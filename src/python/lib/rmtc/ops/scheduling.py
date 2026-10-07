# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project
"""
Scheduler for infer & train
"""
import enum
from abc import ABC, abstractmethod
import rmtc.system.objects
from rmtc.system.objects import IN


class Status(enum.IntEnum):
    """Enumeration for execution states."""

    INVALID = 0
    READY = 1
    RUNNING = 2
    PAUSED = 3
    STOPPED = 4
    FINISHED = 5
    FAILED = 6

    def __str__(self):
        return self.name.upper()


class Task(ABC):
    """
    This is used to unify training & inference tasks
    """

    @abstractmethod
    def get_status(self):
        pass

    @abstractmethod
    def get_duration(self):
        pass

    @abstractmethod
    def init(self):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def resume(self):
        pass

    @abstractmethod
    def pause(self):
        pass

    @abstractmethod
    def finish(self):
        pass

    @abstractmethod
    def is_complete(self):
        pass

    @abstractmethod
    def is_inflight(self):
        pass


class Scheduler(rmtc.system.objects.Object, ABC):
    """
    Abstract base class for training and inference job scheduling.

    The Scheduler class manages the execution lifecycle of jobs
    including initialization, starting, pausing, resuming, and stopping.
    It coordinates between jobs, trackers, runs, and execution environments.
    """

    def __init__(
        self,
        tracker=None,
        task=None,
        job=None,
        asset_manager=None,
        env=None,
        env_manager=None,
    ):
        """Initialize the Scheduler with job components."""
        super(Scheduler, self).__init__()
        self.add_property("job", Job, job)
        self.add_property("tracker", Tracker, tracker, member=False)
        self.add_property("task", Task, task, member=False)
        self.add_property("env", [rmtc.system.Package], env, direction=IN)
        self._asset_manager = asset_manager
        self._env_manager = env_manager
        self._active_time = rmtc.system.Datetime()

    @property
    def asset_manager(self):
        return self._asset_manager

    @property
    def env_manager(self):
        return self._env_manager

    @asset_manager.setter
    def asset_manager(self, value):
        self._asset_manager = value

    @env_manager.setter
    def env_manager(self, value):
        self._env_manager = value

    def create_job(self, object_type, **kwargs):
        """Construct a new job."""
        job = object_type(**kwargs)
        job.scheduler = self
        self.job = job
        return job

    def __call__(self):
        self.start()

    @abstractmethod
    def init(self):
        """Initialize the scheduler for job execution."""
        pass

    @abstractmethod
    def start(self):
        """Start the scheduled job execution."""
        pass

    @abstractmethod
    def resume(self):
        """Resume a paused job execution."""
        pass

    @abstractmethod
    def pause(self):
        """Pause the current job execution."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the current job execution."""
        pass

    @abstractmethod
    def join(self):
        """Wait for job completion."""
        pass


class Tracker(rmtc.system.objects.Object, ABC):
    """
    Abstract base class for training progress tracking.

    The Tracker class provides a standardized interface for logging and
    monitoring training progress including metrics, images, checkpoints,
    and hyperparameters. It manages the lifecycle of training runs and
    provides persistence through URI-based storage.

    This is different from the provenance tracking - but to provide
    feedback during the training process.
    """

    def __init__(self, uri=None):
        """Initialize the Tracker with optional URI."""
        super(Tracker, self).__init__()
        self.add_property("uri", rmtc.system.URI, value=uri)

    @abstractmethod
    def start(self, artifact):
        """Start tracking for the specified artifact."""
        pass

    @abstractmethod
    def finish(self):
        """Finish the current tracking session."""
        pass

    @abstractmethod
    def log_debug(self, message, step=None):
        """Log a message."""
        pass

    @abstractmethod
    def log_info(self, message, step=None):
        """Log a message."""
        pass

    @abstractmethod
    def log_warning(self, message, step=None):
        """Log a message."""
        pass

    @abstractmethod
    def log_error(self, message, step=None):
        """Log a message."""
        pass

    @abstractmethod
    def log_image(self, name, image, step=None):
        """Log an image at the specified training step."""
        pass


class LogTracker(Tracker):

    def __init__(self, log):
        self._log = log

    def start(self, artifact):
        self._log.info("Starting tracking")

    def finish(self):
        self._log.info("Finished tracking")

    def log_debug(self, message, step=None):
        if step is not None:
            message = f"Step {step}: {message}"
        self._log.debug(message)

    def log_info(self, message, step=None):
        if step is not None:
            message = f"Step {step}: {message}"
        self._log.info(message)

    def log_warning(self, message, step=None):
        if step is not None:
            message = f"Step {step}: {message}"
        self._log.warning(message)

    def log_error(self, message, step=None):
        if step is not None:
            message = f"Step {step}: {message}"
        self._log.error(message)

    def log_image(self, name, image, step=None):
        pass


class Job(rmtc.system.objects.Object, ABC):
    """
    Abstract base class for distributed jobs
    """

    def __init__(
        self,
        tracker=None,
        task=None,
        job_id=None,
    ):
        """Initialize the Job with tracking and scheduling components."""
        super(Job, self).__init__()

        # references
        self.add_property("tracker", Tracker, tracker, member=False)
        self.add_property("task", Task, task, member=False)

        # members
        self.add_property("job_id", str, job_id)

    @abstractmethod
    def start(self):
        """Start the job execution."""
        pass

    @abstractmethod
    def resume(self):
        """Resume a paused job execution."""
        pass

    @abstractmethod
    def pause(self):
        """Pause the current job execution."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the current job execution."""
        pass

    @abstractmethod
    def add_executor(self, executor):
        """Add an executor to this job."""
        pass

    @abstractmethod
    def get_executors(self):
        """Get all executors associated with this job."""
        pass


class Executor(rmtc.system.objects.Object, ABC):
    # TODO : Is this required?

    def __init__(
        self,
        job=None,
        env=None,
        env_manager=None,
        asset_manager=None,
    ):
        """Initialize the Executor with job reference."""
        super(Executor, self).__init__()
        self.add_property("job", Job, job)
        self.add_property("env", [rmtc.system.Package], env, direction=IN)
        self._env_manager = env_manager
        self._asset_manager = asset_manager

    @property
    def asset_manager(self):
        return self._asset_manager

    @property
    def env_manager(self):
        return self._env_manager

    @env_manager.setter
    def env_manager(self, value):
        self._env_manager = value

    @abstractmethod
    def __call__(self, tracker, task):
        pass
