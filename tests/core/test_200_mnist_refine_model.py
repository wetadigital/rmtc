# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import glob
import json
import os
from pathlib import Path

import cv2
import numpy as np
import torch.nn as nn
import torchvision
import torchvision.datasets
import torchvision.transforms

import rmtc.ops.artifacts as artifacts
import rmtc.ops.assets as assets
import rmtc.ops.process as process
import rmtc.core.ops.process.tensor.structure as structure_processors
import rmtc.core.ops.process.image.channels as channel_processors
import rmtc.core.ops.artifacts.torch.models as torch_models
import rmtc.core.ops.io.oiio.image as image_io
import rmtc.core.ops.io.torch.models as model_io
import rmtc.core.ops.infer.simple.inferers as inferers
import rmtc.core.track.entities.licenses.community as community_licenses
import rmtc.core.ops.train.local.schedulers as local_train_schedulers
import rmtc.core.ops.infer.local.schedulers as local_infer_schedulers
import rmtc.core.ops.train.torch.trainers as torch_trainers
import rmtc.core.ops.io.filesystem.json as structured_io
import rmtc.core.ops.io.filesystem.folders as folder_io

from rmtc.core.ops.infer.simple.inferers import DatasetInferer
from rmtc.system import URI, Device, FileURI
from rmtc.system import DataType
from rmtc.ops.scheduling import Status
from rmtc.track.entities import Party, Jurisdiction
from rmtc.core.ops.process.torch.packagers.tensor import BatchedTorchTensor
from abstract_rmtc_test import AbstractRMTCTest

def export_mnist_exrs(output_dir, train=True, data_dir="./data", max_count=None):
    """Save the MNIST dataset as EXR images and a corresponding json labels.

    Args:
        output_dir (str): Output directory path
        train (bool): If true, exports the training data, otherwise exports the test data
        data_dir (str): Directory containing downloaded MNIST data

    Returns:
        str: json filepath
    """
    # Load the MNIST dataset
    transform = torchvision.transforms.ToTensor()
    if not os.path.exists(data_dir):
        dataset = torchvision.datasets.MNIST(
            root=data_dir,
            train=train,
            download=True,
            transform=transform,
        )

    exr_output_dir = os.path.join(output_dir, "exr")
    if not os.path.exists(exr_output_dir):
        os.makedirs(exr_output_dir, exist_ok=True)

    export_data = []

    # Iterate through the dataset and save each image as EXR
    for i, (image_tensor, label) in enumerate(dataset):

        # early out
        if max_count is not None and i > max_count:
            break

        # Export PyTorch MNIST dataset as normalized floating point 3 channel 28x28 EXRs
        image_tensor = image_tensor.cpu()
        np_image = image_tensor.squeeze().numpy()
        np_image = np_image.astype(np.float32)
        np_image = np.squeeze(np_image)
        np_image = np.stack([np_image, np_image, np_image], axis=-1)

        # Export EXR - if not already
        output_path = os.path.join(
            exr_output_dir, "mnist_{:05d}_{}.exr".format(i, label)
        )
        if not os.path.exists(output_path):
            success = cv2.imwrite(output_path, np_image)
            if not success:
                raise RuntimeError(f"Could not create output file for {output_path}")

        rmtc_exr_uri = "file://localhost{}".format(os.path.abspath(output_path))

        # Convert label to integer logit tensor
        label_logits = [0.0] * 10
        label_logits[label] = 1.0
        export_data.append([rmtc_exr_uri, label_logits])

    # Save JSON file
    json_data = {}
    for exr_uri, label in export_data:
        json_data[exr_uri] = label
    json_file_path = os.path.join(output_dir, "mnist_exr_dataset.json")
    with open(json_file_path, "w") as json_file:
        json.dump(json_data, json_file, indent=4)

    return os.path.abspath(json_file_path)


def export_mnist_data(data_dir="./data", output_dir=""):
    """Export MNIST dataset.

    Args:
        data_dir (str): Directory containing downloaded MNIST data
        output_dir (str): Directory to export data to

    Returns:
        Tuple of str, str: JSON filepaths for the train, test data
    """
    train_path = os.path.join(output_dir, "mnist_exr/train")
    test_path = os.path.join(output_dir, "mnist_exr/test")

    # Export the 60,000 training images and labels
    train_json = export_mnist_exrs(
        train_path,
        train=True,
        data_dir=data_dir,
        max_count = 10,
    )

    # Export the 10,000 testing images and labels
    test_json = export_mnist_exrs(
        test_path,
        train=False,
        data_dir=data_dir,
    )

    return train_json, test_json


def get_inferred_mnist_data(directory_path):
    """Generator that yields labels and predictions from inferred JSON files.

    Args:
        directory_path (str): Directory containing inferred JSON files

    Yields:
        list<Tuples(int, int)>: List of (label, prediction)
    """
    # Recursively get json files
    json_pattern = os.path.join(directory_path, "**", "*.json")
    json_files = glob.glob(json_pattern, recursive=True)

    for file_path in json_files:
        # The last digit in the file name is the label
        label = int(file_path.rsplit("_")[-1].split(".")[0])
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logits = [0] * len(data.items())
            for key, value in data.items():
                logits[int(key)] = float(value)
            max_value = max(logits)
            max_index = int(logits.index(max_value))
            yield label, max_index


class SimpleClassifierModel(nn.Module):
    """Simple pytorch model for MNIST image classification"""

    def __init__(self):
        super(SimpleClassifierModel, self).__init__()
        # Input layer (flattened 28x28 4-channel images)
        self.fc1 = nn.Linear(28 * 28 * 4, 128)
        self.relu = nn.ReLU()
        # Output layer (Logits for digits 0-9)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        # Flatten the image
        x = x.view(-1, 28 * 28 * 4)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x

    def set_training(self, train=True):
        pass


class TestRefineModel(AbstractRMTCTest):
    """Test model refinement using MNIST dataset"""

    def test_refine_model(self):
        # HACK: cannot test this as there is no access externally to download the MNIST dataset
        return

        """Test refining a model"""
        self.temp_dir = self.tmp_path
        directory_uri = f"file://localhost{self.temp_dir}"

        rmtc_sys = self.get_system()
        config = rmtc_sys.config

        # If specified in the config, use existing mnist data
        if "rmtc_testing" in config and "data_path" in config["rmtc_testing"]:
            mnist_data_dir = config["rmtc_testing"]["data_path"]
        else:
            mnist_data_dir = str(self.temp_dir / "data")

        # add mnist data path
        mnist_data_dir += "/mnist"

        rmtc_sys = self.get_system()

        # Create Creative Commons license
        cc_license = rmtc_sys.create_license(
            community_licenses.OSS,
            name="Creative Commons Attribution-Share Alike 3.0",
            uri=URI("https://creativecommons.org/licenses/by-sa/3.0/"),
            parties=[rmtc_sys.get_create(Party, name="Creative Commons")],
        )

        # Export a basic MNIST model torch package
        mnist_model = SimpleClassifierModel()
        model_dir = self.temp_dir / "mnist_model"
        os.makedirs(model_dir, exist_ok=True)
        this_module_name = (
            f"integration.{os.path.splitext(os.path.basename(__file__))[0]}"
        )
        model_path = model_io.TorchPackage.package_model(
            model=mnist_model,
            package_name="MNIST",
            output_path=Path(model_dir),
            externs=[this_module_name],
        )

        # Wrap model
        model = rmtc_sys.create_model(
            torch_models.TorchModel,
            name="MNIST Model",
            uri=FileURI(model_path),
            input_types=[assets.Image],
            input_packager = process.ProcessPackager(
                processors = [],
                packager = BatchedTorchTensor(data_type=DataType.FLOAT32),
            ),
            output_types=[assets.Values],          
            output_packager = BatchedTorchTensor(data_type=DataType.FLOAT32),
            io=model_io.TorchPackage(
                model_name="MNIST",
                package_name="MNIST.pkl",
            ),
        )
        self.assertEqual(len(model.input_types), 1)
        self.assertEqual(len(model.output_types), 1)        

        # Solution
        solution = rmtc_sys.create_solution(
            name="Number Categorization",
            uri=URI(f"{directory_uri}/solution/test"),
            input_types=[assets.Image],
            output_types=[assets.Values],
            description="MNIST Solution",
        )

        # MNIST Dataset
        train_json, test_json = export_mnist_data(
            data_dir=mnist_data_dir, output_dir=str(self.temp_dir)
        )
        dataset = rmtc_sys.create_dataset(artifacts.Dataset,
            name="MNIST Training Dataset",
            licenses=[cc_license],
            uri=FileURI(train_json),
            io=structured_io.AssetValuesJSONFile(
                asset_type=assets.Image, 
                asset_io=image_io.EXR()
            ),
        )

        rmtc_sys.push()

        # Run the training
        run = rmtc_sys.train(
            solution=solution,
            scheduler=local_train_schedulers.LocalTrainScheduler(rmtc_system=rmtc_sys),
            trainer=torch_trainers.TorchRegression(
                lr=0.001,
                batch_size=5,
                epochs=1,
                optimizer="adam",
                device=Device.GPU,
            ),
            model=model,
            dataset=dataset,
        )
        self.assertTrue(run is not None)
        self.assertEqual(run.status, Status.FINISHED)
        self.assertTrue(run.model is not None)
        self.assertTrue(run.result_weights is not None)               
        rmtc_sys.push()

        # Basic DB validation
        mnist_dataset = rmtc_sys.get_datasets("MNIST")[0]
        self.assertEqual(mnist_dataset.name, "MNIST Training Dataset")
        rmtc_model = rmtc_sys.get_models("MNIST Model")[0]
        self.assertEqual(rmtc_model.name, "MNIST Model")

        # Generate inferences
        session = rmtc>-sys.create_sesssion()
        solution = rmtc_sys.get_solutions("Number Categorization")[0]
        run = rmtc_sys.get_best_run(solution=solution)
        self.assertTrue(run is not None)
        rmtc_sys.track.open().sync([run, run.model, run.result_weights])
        inference = rmtc_sys.infer(
            solution=solution,
            session=session,
            scheduler=local_infer_schedulers.LocalInferScheduler(rmtc_system=rmtc_sys),
            inferer=inferers.DatasetInferer(asset_manager=rmtc_sys.ops.asset_manager),
            model=run.model,
            weights=run.result_weights,
            inputs=[artifacts.Dataset(
                uri=URI(f"{directory_uri}/mnist_exr/test/exr"),
                io=folder_io.FolderIO(
                    asset_type=assets.Image,
                    asset_io=image_io.EXR(),
                )
            )],
            outputs=[artifacts.Dataset(
                uri=URI(f"{directory_uri}/results"),
                io=folder_io.FolderIO(
                    asset_type=assets.Values,
                    asset_io=structured_io.ValuesJSONFile(),
                )
            )],
        )
        rmtc_sys.push()

        # Confirm we generated some inferences
        mnist_inferences = rmtc_sys.get_inferences(model=run.model)
        self.assertNotEqual(len(mnist_inferences), 0)

        # TODO : work out how to do this without filenames
        # # Validate predictions
        # num_results = 0
        # results_file = str(self.temp_dir / "results")
        # correct = 0
        # for label, prediction in get_inferred_mnist_data(results_file):
        #     num_results += 1
        #     if label == prediction:
        #         correct += 1
        # self.assertTrue(num_results > 0)
        # success_rate = correct / num_results * 100
        # self.assertTrue(success_rate > 50.0)
