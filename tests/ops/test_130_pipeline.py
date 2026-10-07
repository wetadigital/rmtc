# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import unittest
from unittest.mock import Mock

from rmtc.ops.artifacts import Artifact
from rmtc.ops.pipeline import Builder, ReaderWriter, Pipeline, AssetManager
from rmtc.system import RMTCException


class FakeArtifact(Artifact):
    """Minimal concrete Artifact for exercising ReaderWriter without real IO"""

    def __init__(self, uri=None, io=None, dependencies=None, ephemeral=False, valid=False):
        self.uri = uri
        self._io = io
        self._dependencies = dependencies if dependencies is not None else set()
        self._ephemeral = ephemeral
        self._valid = valid
        self.init_calls = 0
        self.reset_calls = 0

    def get_uri(self):
        return self.uri

    def get_io(self):
        return self._io

    def get_dependencies(self):
        return self._dependencies

    def set_uri(self, uri, io):
        self.uri = uri
        self._io = io

    def get_device(self):
        return None

    def init(self):
        self.init_calls += 1
        return True

    def reset(self):
        self.reset_calls += 1
        self._valid = False
        return True

    def is_valid(self):
        return self._valid

    def move(self, device):
        pass

    def is_ephemeral(self):
        return self._ephemeral


class ConcreteReaderWriter(ReaderWriter):
    """Minimal concrete ReaderWriter to exercise the shared base logic"""

    def __init__(self, *args, exists_return=False, supported_return=True, **kwargs):
        super(ConcreteReaderWriter, self).__init__(*args, **kwargs)
        self.exists_return = exists_return
        self.supported_return = supported_return

    def is_uri_supported(self, uri):
        return self.supported_return

    def create_uri(self, artifact, root):
        return None

    def delete_uri(self, uri):
        return None

    def exists(self, uris):
        return self.exists_return


class TestBuilder(unittest.TestCase):

    def test_builder_is_abstract(self):
        with self.assertRaises(TypeError):
            Builder()


class TestReaderWriter(unittest.TestCase):

    def setUp(self):
        self.log = Mock()
        self.env = Mock()
        self.publisher = Mock()

    def _make(self, **overrides):
        kwargs = dict(env=self.env, log=self.log, publisher=self.publisher)
        kwargs.update(overrides)
        return ConcreteReaderWriter(**kwargs)

    def test_is_abstract_without_full_interface(self):
        with self.assertRaises(TypeError):
            ReaderWriter(env=self.env, log=self.log, publisher=self.publisher)

    def test_requires_publisher(self):
        with self.assertRaises(RMTCException):
            self._make(publisher=None)

    def test_requires_env(self):
        with self.assertRaises(RMTCException):
            self._make(env=None)

    def test_is_immutable_reflects_flag(self):
        self.assertTrue(self._make(immutable=True).is_immutable())
        self.assertFalse(self._make(immutable=False).is_immutable())

    def test_log_and_env_properties(self):
        rw = self._make()
        self.assertIs(rw.log, self.log)
        self.assertIs(rw.env, self.env)

    def test_init_requires_list(self):
        rw = self._make()
        with self.assertRaises(RMTCException):
            rw.init(FakeArtifact())

    def test_init_missing_io_raises(self):
        rw = self._make()
        artifact = FakeArtifact(io=None)
        with self.assertRaises(RMTCException):
            rw.init([artifact])

    def test_init_skips_ephemeral_artifact(self):
        """Ephemeral means no IO by definition - a skip, not a missing-IO error"""
        rw = self._make()
        artifact = FakeArtifact(io=None, ephemeral=True)
        rw.init([artifact])
        self.assertEqual(artifact.init_calls, 0)

    def test_init_io_failure_raises(self):
        rw = self._make()
        io = Mock()
        io.init.return_value = False
        artifact = FakeArtifact(io=io)
        with self.assertRaises(RMTCException):
            rw.init([artifact])

    def test_init_invalid_after_success_raises(self):
        rw = self._make()
        io = Mock()
        io.init.return_value = True
        artifact = FakeArtifact(io=io, valid=False)
        with self.assertRaises(RMTCException):
            rw.init([artifact])

    def test_init_success(self):
        rw = self._make()
        io = Mock()
        io.init.return_value = True
        artifact = FakeArtifact(io=io, valid=True)
        rw.init([artifact])
        io.init.assert_called_once_with(artifact, rw)

    def test_read_requires_list(self):
        rw = self._make()
        with self.assertRaises(RMTCException):
            rw.read(FakeArtifact())

    def test_read_rejects_non_artifact(self):
        rw = self._make()
        with self.assertRaises(RMTCException):
            rw.read([object()])

    def test_read_skips_already_valid_artifact(self):
        rw = self._make()
        io = Mock()
        artifact = FakeArtifact(io=io, valid=True)
        rw.read([artifact])
        io.read.assert_not_called()

    def test_read_missing_io_raises(self):
        rw = self._make()
        artifact = FakeArtifact(io=None, valid=False)
        with self.assertRaises(RMTCException):
            rw.read([artifact])

    def test_read_success_resolves_and_loads(self):
        resolved_uri = Mock()
        self.publisher.resolve.return_value = [resolved_uri]
        rw = self._make()
        io = Mock()

        def fake_read(uri, artifact, manager):
            artifact._valid = True

        io.read.side_effect = fake_read
        artifact = FakeArtifact(uri=Mock(), io=io, dependencies={"pkg"}, valid=False)

        rw.read([artifact])

        self.env.add_packages.assert_called_once_with({"pkg"})
        self.publisher.resolve.assert_called_once_with([artifact.uri])
        io.read.assert_called_once_with(resolved_uri, artifact, rw)
        self.assertEqual(artifact.init_calls, 1)
        self.assertTrue(artifact.is_valid())

    def test_read_raises_if_still_invalid_after_read(self):
        self.publisher.resolve.return_value = [Mock()]
        rw = self._make()
        io = Mock()
        artifact = FakeArtifact(uri=Mock(), io=io, valid=False)
        with self.assertRaises(RMTCException):
            rw.read([artifact])

    def test_write_requires_list(self):
        rw = self._make()
        with self.assertRaises(RMTCException):
            rw.write(FakeArtifact())

    def test_write_skips_ephemeral_artifact(self):
        rw = self._make()
        rw.init = Mock()
        io = Mock()
        artifact = FakeArtifact(io=io, valid=True, ephemeral=True)
        rw.write([artifact])
        io.write.assert_not_called()

    def test_write_skips_invalid_artifact(self):
        rw = self._make()
        rw.init = Mock()
        io = Mock()
        artifact = FakeArtifact(io=io, valid=False)
        rw.write([artifact])
        io.write.assert_not_called()

    def test_write_missing_io_raises(self):
        rw = self._make()
        rw.init = Mock()
        artifact = FakeArtifact(io=None, valid=True)
        with self.assertRaises(RMTCException):
            rw.write([artifact])

    def test_write_raises_on_immutable_overwrite(self):
        resolved_uri = Mock()
        self.publisher.resolve.return_value = [resolved_uri]
        rw = self._make(immutable=True, exists_return=True)
        rw.init = Mock()
        io = Mock()
        artifact = FakeArtifact(uri=Mock(), io=io, valid=True)
        with self.assertRaises(RMTCException):
            rw.write([artifact])
        io.write.assert_not_called()

    def test_write_warns_and_overwrites_when_mutable(self):
        resolved_uri = Mock()
        self.publisher.resolve.return_value = [resolved_uri]
        rw = self._make(immutable=False, exists_return=True)
        rw.init = Mock()
        io = Mock()
        artifact = FakeArtifact(uri=Mock(), io=io, valid=True)
        rw.write([artifact])
        self.log.warning.assert_called_once()
        io.write.assert_called_once_with(resolved_uri, artifact, rw)

    def test_write_success_when_not_existing(self):
        resolved_uri = Mock()
        self.publisher.resolve.return_value = [resolved_uri]
        rw = self._make(exists_return=False)
        rw.init = Mock()
        io = Mock()
        artifact = FakeArtifact(uri=Mock(), io=io, valid=True)
        rw.write([artifact])
        io.write.assert_called_once_with(resolved_uri, artifact, rw)

    def test_write_unresolved_uri_raises(self):
        """A URI the publisher cannot resolve must fail closed, not land"""
        self.publisher.resolve.return_value = [None]
        rw = self._make()
        rw.init = Mock()
        io = Mock()
        artifact = FakeArtifact(uri=Mock(), io=io, valid=True)
        with self.assertRaises(RMTCException):
            rw.write([artifact])
        io.write.assert_not_called()

    def test_write_unsupported_uri_raises(self):
        """Enforcement runs on the write path, not only at accept time"""
        self.publisher.resolve.return_value = [Mock()]
        rw = self._make(supported_return=False)
        rw.init = Mock()
        io = Mock()
        artifact = FakeArtifact(uri=Mock(), io=io, valid=True)
        with self.assertRaises(RMTCException):
            rw.write([artifact])
        io.write.assert_not_called()

    def test_write_prepares_the_resolved_uri(self):
        """prepare is the only sanctioned side effect before the write"""
        resolved_uri = Mock()
        self.publisher.resolve.return_value = [resolved_uri]
        rw = self._make(exists_return=False)
        rw.init = Mock()
        rw.prepare = Mock()
        io = Mock()
        artifact = FakeArtifact(uri=Mock(), io=io, valid=True)
        rw.write([artifact])
        rw.prepare.assert_called_once_with(resolved_uri)

    def test_reset_requires_list(self):
        rw = self._make()
        with self.assertRaises(RMTCException):
            rw.reset(FakeArtifact())

    def test_reset_clears_artifacts_and_removes_env_packages(self):
        rw = self._make()
        artifact = FakeArtifact(valid=True, dependencies={"pkg"})
        rw.reset([artifact])
        self.assertEqual(artifact.reset_calls, 1)
        self.assertFalse(artifact.is_valid())
        self.env.remove_packages.assert_called_once_with({"pkg"})


class TestPipeline(unittest.TestCase):

    def test_call_runs_supported_builder_and_tracks_ancestors(self):
        artifact = Mock()
        result = Mock()
        builder = Mock()
        builder.is_supported.return_value = True
        builder.return_value = [result]
        pipeline = Pipeline(name="test", builders=[builder])
        asset_manager = Mock()

        built = pipeline(asset_manager, [artifact])

        builder.assert_called_once_with(asset_manager, artifact)
        result.add_ancestors.assert_called_once_with([artifact])
        self.assertEqual(built, [result])

    def test_call_skips_unsupported_builder(self):
        artifact = Mock()
        builder = Mock()
        builder.is_supported.return_value = False
        pipeline = Pipeline(name="test", builders=[builder])

        built = pipeline(Mock(), [artifact])

        builder.assert_not_called()
        self.assertEqual(built, [])

    def test_call_dedupes_shared_results(self):
        artifact = Mock()
        shared_result = Mock()
        builder_a = Mock()
        builder_a.is_supported.return_value = True
        builder_a.return_value = [shared_result]
        builder_b = Mock()
        builder_b.is_supported.return_value = True
        builder_b.return_value = [shared_result]
        pipeline = Pipeline(name="test", builders=[builder_a, builder_b])

        built = pipeline(Mock(), [artifact])

        self.assertEqual(built, [shared_result])

    def test_name_and_description_properties(self):
        pipeline = Pipeline(name="Nuke", builders=[], description="desc")
        self.assertEqual(pipeline.name, "Nuke")
        self.assertEqual(pipeline.description, "desc")

    def test_description_defaults_to_empty_string(self):
        pipeline = Pipeline(name="Nuke", builders=[])
        self.assertEqual(pipeline.description, "")


class TestAssetManager(unittest.TestCase):

    def setUp(self):
        self.readerwriter = Mock()
        self.publisher = Mock()
        self.log = Mock()

    def _make(self, **overrides):
        kwargs = dict(readerwriter=self.readerwriter, publisher=self.publisher, log=self.log)
        kwargs.update(overrides)
        return AssetManager(**kwargs)

    def test_requires_readerwriter(self):
        with self.assertRaises(RMTCException):
            self._make(readerwriter=None)

    def test_requires_publisher(self):
        with self.assertRaises(RMTCException):
            self._make(publisher=None)

    def test_log_property(self):
        manager = self._make()
        self.assertIs(manager.log, self.log)

    def test_is_supported_delegates_to_readerwriter_uri_check(self):
        manager = self._make()
        artifact = Mock()
        self.readerwriter.is_uri_supported.return_value = True
        self.assertTrue(manager.is_supported(artifact))
        self.readerwriter.is_uri_supported.assert_called_once_with(artifact.uri)

    def test_create_uri_delegates_to_readerwriter(self):
        """URI derivation is the readerwriter's, never the publisher's"""
        manager = self._make()
        artifact = Mock()
        root = Mock()
        manager.create_uri(artifact, root)
        self.readerwriter.create_uri.assert_called_once_with(artifact, root)

    def test_readerwriter_domain_delegation(self):
        manager = self._make()
        artifacts = [Mock()]
        uris = [Mock()]

        manager.init(artifacts)
        self.readerwriter.init.assert_called_once_with(artifacts)

        manager.read(artifacts)
        self.readerwriter.read.assert_called_once_with(artifacts)

        manager.write(artifacts)
        self.readerwriter.write.assert_called_once_with(artifacts)

        manager.reset(artifacts)
        self.readerwriter.reset.assert_called_once_with(artifacts)

        manager.exists(uris)
        self.readerwriter.exists.assert_called_once_with(uris)

    def test_publisher_domain_delegation(self):
        manager = self._make()
        uris = [Mock()]
        entities = [Mock()]

        manager.resolve(uris)
        self.publisher.resolve.assert_called_once_with(uris)

        manager.resolve_inverse(uris)
        self.publisher.resolve_inverse.assert_called_once_with(uris)

        manager.publish(entities, force=True)
        self.publisher.publish.assert_called_once_with(entities, force=True)

        manager.unpublish(entities)
        self.publisher.unpublish.assert_called_once_with(entities)

        manager.is_published(entities)
        self.publisher.is_published.assert_called_once_with(entities)

        manager.is_immutable()
        self.publisher.is_immutable.assert_called_once_with()

        manager.relocate(entities[0], "uri")
        self.publisher.relocate.assert_called_once_with(entities[0], "uri")

    def test_reserve_delegates_to_publisher(self):
        manager = self._make()
        path = Mock()
        self.publisher.reserve.return_value = (Mock(), Mock())
        result = manager.reserve(path)
        self.publisher.reserve.assert_called_once_with(path)
        self.assertEqual(result, self.publisher.reserve.return_value)

    def test_reserve_raises_if_publisher_does_not_support_it(self):
        manager = self._make(publisher=Mock(spec=[]))
        with self.assertRaises(RMTCException):
            manager.reserve(Mock())


if __name__ == "__main__":
    unittest.main()
