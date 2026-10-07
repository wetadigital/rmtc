# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.ops.infer import Inferer
from rmtc.ops.artifacts import Dataset
from rmtc.ops.process import Process
from rmtc.system.objects import IN
from rmtc.system import Device, RMTCException


class DatasetInferer(Inferer):
    """
    Simple dataset to dataset inference
    """

    def __init__(
        self,
        device=Device.GPU,
    ):
        """Initialize DatasetInferer with model, paths, and file handlers."""
        super(DatasetInferer, self).__init__(
            device=device,
        )

    def run(
        self,
        inference,
        asset_manager,
    ):
        """
        Execute inference on the provided datasets
        """

        # validate
        if inference is None:
            raise RMTCException("Invalid inference on infer")
        inputs = inference.inputs
        outputs = inference.outputs
        if inputs is None:
            raise RMTCException("Invalid input dataset on infer")
        if outputs is None:
            raise RMTCException("Invalid output dataset on infer")

        # move to device ahead of read
        for dataset in inputs:
            dataset.move(self.device)

        # read the datasets
        asset_manager.read(inputs)
        model = self.get_model_instance(inference, asset_manager)

        # iterate through the dataset in batches
        batch = []
        for row in Dataset.generate_rows(inputs):
            batch.append(row)

        # load inputs and process
        for row in batch:
            asset_manager.read(row)

        # run
        results = model(batch)

        # reset
        for row in batch:
            asset_manager.reset(row)

        # add to the outputs
        for row in results:
            for dataset in outputs:
                row = dataset.fill_row(row)

        # setup metric either from weights, or model
        metric = 1.0
        if inference.weights is not None:
            metric = inference.weights.metric
        else:
            metric = inference.model.metric

        return (inputs, outputs, metric)


class BatchedInferer(Inferer):
    """
    Simple dataset to dataset inference
    """

    def __init__(
        self,
        batch_size=1,
        flush_outputs=True,
        device=Device.GPU,
        pre_process=None,
        post_process=None,
    ):
        """Initialize DatasetInferer with model, paths, and file handlers."""
        super(BatchedInferer, self).__init__(
            device=device,
        )
        self.add_property(
            "pre_process",
            [Process],
            pre_process,
            direction=IN,
        )
        self.add_property(
            "post_process",
            [Process],
            post_process,
            direction=IN,
        )
        self.add_property("batch_size", int, batch_size)

        self.add_property("flush_outputs", bool, flush_outputs)

    def run(
        self,
        inference,
        asset_manager,
    ):
        """
        Execute inference on the provided datasets
        """

        # validate
        if inference is None:
            raise RMTCException("Invalid inference on infer")
        inputs = inference.inputs
        outputs = inference.outputs
        if inputs is None:
            raise RMTCException("Invalid input dataset on infer")
        if outputs is None:
            raise RMTCException("Invalid output dataset on infer")

        # move to device ahead of read
        # TODO : race condition if dataset is being used in multiple places?
        for dataset in inputs:
            dataset.move(self.device)

        # read the datasets - this doesn't load any asset tensors, just builds up the datasets
        # e.g. loads the CSV file list of other assets etc. puts the dataset into a state where
        # we can iterate
        asset_manager.read(inputs)
        for dataset in inputs:
            if not dataset.is_valid():
                raise RMTCException(f"Invalid input {dataset}")
        # for dataset in outputs:
        #     if not dataset.is_valid():
        #         raise RMTCException(f"Invalid output {dataset}")
        model = self.get_model_instance(inference, asset_manager)

        # iterate through the dataset in batches
        batch = []
        for row in Dataset.generate_rows(inputs):

            # accumulate
            batch.append(row)

            # run when accumulated batch size
            if len(batch) >= self.batch_size:
                self._run_batch(batch, model, outputs, asset_manager)
                batch = []

        # run remainder batches
        if batch:
            self._run_batch(batch, model, outputs, asset_manager)

        if self.flush_outputs:
            asset_manager.write(outputs)
            asset_manager.reset(outputs)

        # setup metric either from weights, or model
        metric = 1.0
        if inference.weights is not None:
            metric = inference.weights.metric
        else:
            metric = inference.model.metric

        return (inputs, outputs, metric)

    def _run_batch(self, batch, model, outputs, asset_manager):
        # load inputs and process
        for row in batch:
            asset_manager.read(row)
            if self.pre_process:
                for asset, process in zip(row, self.pre_process):
                    asset.process(process)

        # run
        results = model(batch)

        # reset
        for row in batch:
            asset_manager.reset(row)

        # add to the outputs
        for row in results:
            if self.post_process:
                for asset, process in zip(row, self.post_process):
                    asset.process(process)
            for dataset in outputs:
                row = dataset.fill_row(row)


class ParametricInferer(Inferer):
    """
    This inferer takes a dataset which is passed into the model as parameters
    """

    pass


class RecurrentInferer(Inferer):
    """
    This inferer uses the last inference result as a secondary input to the model
    """

    pass
