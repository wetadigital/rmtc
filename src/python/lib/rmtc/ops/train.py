# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Training classes, derivations from the tracking entities that
are trainable.
"""

from abc import abstractmethod, ABC

import rmtc.system

from rmtc.track import entities
from rmtc.track.store import Entity
from rmtc.system.objects import OUT
from rmtc.system import Datetime, RMTCException
from rmtc.ops.scheduling import Status, Task


class Solution(entities.Solution):
    """
    Training solution extending the base Solution class.

    A simple extension of the base Solution class for training-specific
    functionality. Currently provides no additional behavior beyond
    the base implementation.
    """

    pass


class Run(entities.Run, Task):
    """
    Training run extending the base Run class.

    A simple extension of the base Run class for training-specific
    functionality. Currently provides no additional behavior beyond
    the base implementation.
    """

    def __init__(
        self,
        uri=None,
        name=None,
        solution=None,
        context=None,
        trainer=None,
        model=None,
        dataset=None,
        checkpoint=None,
        result_weights=None,
        result_checkpoints=None,
        metric=1.0,
    ):
        """Initialize the Run with training components and configuration."""
        super(Run, self).__init__(
            name=name,
            context=context,
            model=model,
            dataset=dataset,
            checkpoint=checkpoint,
            result_weights=result_weights,
            result_checkpoints=result_checkpoints,
            solution=solution,
            metric=metric,
            uri=uri,
        )

        # members
        self.add_property("duration", float, 0.0, volatile=True)
        self.add_property("started", Datetime, volatile=True)
        self.add_property(
            "trainer",
            Trainer,
            trainer,
            direction=OUT,
        )
        self.add_property("status", Status, Status.READY, volatile=True)
        self._start_time = Datetime()
        self.init()

    def get_status(self):
        return self.status

    def init(self):
        """Initialize run state to default values."""
        self.status = Status.READY
        self.metric = 1.0
        self.epochs = 0
        self.duration = 0.0
        self.result_weights = None
        self.result_checkpoints = []

    def start(self):
        """Start the training run if in READY state."""
        if self.status == Status.READY:
            self.started = Datetime()
            self.status = Status.RUNNING
            self._start_time = Datetime.now()

    def stop(self):
        """Stop a running or paused training run and update duration."""
        if self.status in (Status.RUNNING, Status.PAUSED):
            self.status = Status.STOPPED
            self.duration += (Datetime.now().timestamp() * 1000) - (
                self._start_time.timestamp() * 1000.0
            )

    def resume(self):
        """Resume a paused training run."""
        if self.status == Status.PAUSED:
            self.status = Status.RUNNING
            self._start_time = Datetime.now()

    def pause(self):
        """Pause a running training run and update duration."""
        if self.status == Status.RUNNING:
            self.status = Status.PAUSED
            self.duration += (Datetime.now().timestamp() * 1000) - (
                self._start_time.timestamp() * 1000.0
            )

    def finish(self):
        """
        Complete the training run with results.

        Finalizes a running training run by setting the final status,
        updating duration, recording results, and adding the result
        model to the parent solution.
        """
        if self.status not in (Status.FAILED, Status.INVALID):
            self.status = Status.FINISHED
            self.duration += (Datetime.now().timestamp() * 1000) - (
                self._start_time.timestamp() * 1000.0
            )
            if self.model is not None and self.metric < self.model.metric:
                self.model.metric = self.metric

    def is_complete(self):
        return self.status not in (
            Status.INVALID,
            Status.READY,
            Status.RUNNING,
            Status.PAUSED,
        )

    def is_inflight(self):
        return self.status in (Status.RUNNING, Status.PAUSED)

    def get_duration(self):
        return self.duration


class Trainer(Entity, ABC):
    """
    Abstract base class for model training implementations.

    The Trainer class extends the base Trainer with training-specific
    functionality including hyperparameter management and checkpoint
    scheduling. It provides the core interface for training operations.
    """

    def __init__(
        self,
        name=None,
        epochs=1,
        batch_size=1,
        checkpoint_interval=0,
        device=None,
    ):
        """Initialize the Trainer with training parameters."""
        super(Trainer, self).__init__(
            name=name,
        )
        self.add_property("epochs", int, epochs)
        self.add_property("batch_size", int, batch_size)
        self.add_property("checkpoint_interval", int, checkpoint_interval)
        self.add_property("device", rmtc.system.Device, device)
        self._model_instance = None
        self._model_checkpoint = None

    def create_weights(
        self,
        run,
        model,
        epoch,
        metric,
        io,
        asset_manager,
    ):
        if self._model_instance is None:
            raise RMTCException("No model instance")

        # create weights
        weights = self._model_instance.create_weights()
        weights.name = "weights"
        weights.parent = run
        weights.model = model
        weights.epoch = epoch
        weights.metric = metric
        weights.io = io

        # create URI - identity-derived beneath the run
        weights.uri = asset_manager.create_uri(weights, run.uri)

        return weights

    def create_checkpoint(
        self,
        run,
        model,
        epoch,
        metric,
        io,
        asset_manager,
    ):
        if self._model_instance is None:
            raise RMTCException("No model instance")

        # create checkpoint
        checkpoint = self._model_instance.create_checkpoint()
        checkpoint.name = "checkpoint"
        checkpoint.parent = run
        checkpoint.model = model
        checkpoint.epoch = epoch
        checkpoint.metric = metric
        checkpoint.io = io

        # create URI - identity-derived beneath the run
        checkpoint.uri = asset_manager.create_uri(checkpoint, run.uri)

        return checkpoint

    def reset(self):
        self._model_instance = None
        self._model_checkpoint = None

    def get_model_instance(self, run, asset_manager):
        if self._model_instance is None:
            self._model_instance = run.model.duplicate(descendent=True)
            asset_manager.read([self._model_instance])
            if run.checkpoint is not None:
                self._model_checkpoint = run.checkpoint.duplicate()
                asset_manager.read([self._model_checkpoint])
                self._model_instance.load_checkpoint(self._model_checkpoint)
        if self._model_instance is None or not self._model_instance.is_valid():
            raise rmtc.system.RMTCException(f"Invalid model {self._model_instance}")
        self._model_instance.move(self.device)
        return self._model_instance

    @property
    def hyperparameters(self):
        """Get all trainer properties as hyperparameters dictionary."""
        params = {}
        for prop in self.properties:
            params[prop.name] = prop.value
        return params

    def __call__(
        self,
        tracker,
        run,
        asset_manager,
    ):
        return self.run(tracker, run, asset_manager)

    @abstractmethod
    def run(
        self,
        tracker,
        run,
        asset_manager,
    ):
        pass

    def do_checkpoint(self, epoch):
        """
        Determine if a checkpoint should be created at the given epoch.
        This references the trainer checkpoint interval. An interval of 0 always
        creates a checkpoint
        """
        if epoch == self.epochs:
            return True
        return epoch % self.checkpoint_interval == 0

    @classmethod
    def category(cls):
        """Get the string name of the entity type."""
        return "Trainer"
