# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.ops.train import Run
from rmtc.ops.infer import Inference
from rmtc.track.entities import Model


from abstract_rmtc_test import AbstractRMTCTest


class TestTaskMetricInvariant(AbstractRMTCTest):
    """
    Metric lifecycle on Run and Inference: unmeasured metrics are 1.0 by default,
    Run.finish() propagates a measures metric down to the model as a best-so-far update
    so that a model's metric only improves.
    """

    def test_run_initializes_pessimal(self):
        """A fresh Run's metric reads 1.0 — an unmeasured loss is worst-case."""
        run = Run()
        self.assertEqual(run.metric, 1.0)

    def test_run_init_resets_pessimal(self):
        """Re-running init() restores the pessimal metric."""
        run = Run()
        run.metric = 0.05
        run.init()
        self.assertEqual(run.metric, 1.0)

    def test_inference_initializes_pessimal(self):
        """A fresh Inference's metric reads 1.0."""
        inference = Inference()
        self.assertEqual(inference.metric, 1.0)

    def test_finish_pushes_metric_to_model(self):
        """finish() after result assignment propagates the run metric to the model."""
        model = Model()
        run = Run(model=model)
        run.metric = 0.05
        run.finish()
        self.assertEqual(model.metric, 0.05)

    def test_finish_keeps_best_model_metric(self):
        """A worse later run must not overwrite a model's best metric."""
        model = Model()
        first = Run(model=model)
        first.metric = 0.05
        first.finish()

        second = Run(model=model)
        second.metric = 0.2
        second.finish()

        self.assertEqual(model.metric, 0.05)

    def test_finish_unmeasured_run_leaves_model_untouched(self):
        """
        finish() on a run that never measured must not touch the model.
        This should fail if init() ever regresses to metric=0.0, causing the
        best-so-far guard to give the model a perfect score.
        """
        model = Model()
        run = Run(model=model)
        run.finish()
        self.assertEqual(model.metric, 1.0)

    def test_finish_without_model_does_not_raise(self):
        """A run with no model finishes cleanly"""
        run = Run()
        run.metric = 0.05
        run.finish()
        self.assertEqual(run.status.name, "FINISHED")
