# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from rmtc.core.track.publishing.publishers.filesystem import DiskPublisher
from rmtc.track.publishing import Publisher
from rmtc.system import RMTCException, URI, FileURI


class TestPublisher(unittest.TestCase):

    def test_publisher_is_abstract(self):
        with self.assertRaises(TypeError):
            Publisher()

    def test_get_metadata_default_returns_none_per_uri(self):
        """
        get_metadata is a concrete hook, not abstract - a Publisher with no
        metadata concept (e.g. DiskPublisher) needs no override to satisfy
        the interface, and callers get None rather than a missing method.
        """
        publisher = DiskPublisher(log=Mock())
        self.assertEqual(publisher.get_metadata(["a", "b", "c"]), [None, None, None])

    def test_get_metadata_default_handles_empty_list(self):
        publisher = DiskPublisher(log=Mock())
        self.assertEqual(publisher.get_metadata([]), [])


class TestDiskPublisher(unittest.TestCase):

    def setUp(self):
        self.log = Mock()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    def _entity(self, uri):
        return SimpleNamespace(uri=uri)

    def test_is_immutable_reflects_flag(self):
        self.assertTrue(DiskPublisher(log=self.log, immutable=True).is_immutable())
        self.assertFalse(DiskPublisher(log=self.log, immutable=False).is_immutable())

    def test_is_supported_rejects_missing_uri(self):
        publisher = DiskPublisher(log=self.log)
        self.assertFalse(publisher.is_supported([self._entity(None)]))

    def test_is_supported_rejects_invalid_uri(self):
        publisher = DiskPublisher(log=self.log)
        self.assertFalse(publisher.is_supported([self._entity(URI())]))

    def test_is_supported_rejects_non_file_scheme(self):
        publisher = DiskPublisher(log=self.log)
        uri = URI(scheme="https", host="example.com", path="/x")
        self.assertFalse(publisher.is_supported([self._entity(uri)]))

    def test_is_supported_rejects_non_localhost(self):
        publisher = DiskPublisher(log=self.log)
        uri = URI(scheme="file", host="remotehost", path="/x")
        self.assertFalse(publisher.is_supported([self._entity(uri)]))

    def test_is_supported_accepts_valid_file_uri(self):
        publisher = DiskPublisher(log=self.log)
        uri = FileURI(path=self.tmp_path / "asset.bin")
        self.assertTrue(publisher.is_supported([self._entity(uri)]))

    def test_is_supported_enforces_root(self):
        root = self.tmp_path / "root"
        publisher = DiskPublisher(log=self.log, root=root)
        inside = FileURI(path=root / "asset.bin")
        outside = FileURI(path=self.tmp_path / "elsewhere" / "asset.bin")
        self.assertTrue(publisher.is_supported([self._entity(inside)]))
        self.assertFalse(publisher.is_supported([self._entity(outside)]))

    def test_is_published_raises_on_none_entity(self):
        publisher = DiskPublisher(log=self.log)
        with self.assertRaises(RMTCException):
            publisher.is_published([None])

    def test_is_published_false_when_missing_uri(self):
        publisher = DiskPublisher(log=self.log)
        self.assertFalse(publisher.is_published([self._entity(None)]))

    def test_is_published_false_when_file_missing(self):
        publisher = DiskPublisher(log=self.log)
        uri = FileURI(path=self.tmp_path / "missing.bin")
        self.assertFalse(publisher.is_published([self._entity(uri)]))

    def test_is_published_true_when_file_exists(self):
        publisher = DiskPublisher(log=self.log)
        path = self.tmp_path / "present.bin"
        path.write_text("data")
        uri = FileURI(path=path)
        self.assertTrue(publisher.is_published([self._entity(uri)]))

    def test_publish_raises_on_none_entity(self):
        publisher = DiskPublisher(log=self.log)
        with self.assertRaises(RMTCException):
            publisher.publish([None])

    def test_publish_filters_out_unsupported_entities(self):
        publisher = DiskPublisher(log=self.log)
        supported = self._entity(FileURI(path=self.tmp_path / "ok.bin"))
        unsupported = self._entity(None)
        results = publisher.publish([supported, unsupported])
        self.assertEqual(results, [supported])
        self.log.warning.assert_called_once()

    def test_publish_accepts_kwargs(self):
        publisher = DiskPublisher(log=self.log)
        results = publisher.publish([], force=True)
        self.assertEqual(results, [])

    def test_resolve_passes_through_local_file_uris(self):
        publisher = DiskPublisher(log=self.log)
        uri = FileURI(path=self.tmp_path / "asset.bin")
        self.assertEqual(publisher.resolve([uri]), [uri])

    def test_resolve_returns_none_for_unsupported_uri(self):
        publisher = DiskPublisher(log=self.log)
        uri = URI(scheme="https", host="example.com", path="/x")
        self.assertEqual(publisher.resolve([uri]), [None])

    def test_resolve_raises_on_none_uri(self):
        publisher = DiskPublisher(log=self.log)
        with self.assertRaises(RMTCException):
            publisher.resolve([None])

    def test_resolve_inverse_matches_resolve(self):
        publisher = DiskPublisher(log=self.log)
        uri = FileURI(path=self.tmp_path / "asset.bin")
        self.assertEqual(publisher.resolve_inverse([uri]), publisher.resolve([uri]))

    def test_unpublish_not_implemented(self):
        publisher = DiskPublisher(log=self.log)
        with self.assertRaises(NotImplementedError):
            publisher.unpublish([])

    def test_relocate_raises_when_immutable(self):
        publisher = DiskPublisher(log=self.log, immutable=True)
        with self.assertRaises(RMTCException):
            publisher.relocate(self._entity(None), FileURI(path=self.tmp_path / "x.bin"))

    def test_relocate_raises_on_invalid_uri(self):
        publisher = DiskPublisher(log=self.log, immutable=False)
        with self.assertRaises(RMTCException):
            publisher.relocate(self._entity(None), URI())

    def test_relocate_moves_file_and_updates_entity(self):
        publisher = DiskPublisher(log=self.log, immutable=False)
        old_path = self.tmp_path / "old.bin"
        old_path.write_text("data")
        new_path = self.tmp_path / "new.bin"
        entity = self._entity(FileURI(path=old_path))

        publisher.relocate(entity, FileURI(path=new_path))

        self.assertFalse(old_path.exists())
        self.assertTrue(new_path.exists())
        self.assertEqual(entity.uri.path, new_path)

    def test_relocate_warns_on_overwrite(self):
        publisher = DiskPublisher(log=self.log, immutable=False)
        old_path = self.tmp_path / "old.bin"
        old_path.write_text("data")
        new_path = self.tmp_path / "new.bin"
        new_path.write_text("existing")
        entity = self._entity(FileURI(path=old_path))

        publisher.relocate(entity, FileURI(path=new_path))

        self.log.warning.assert_called_once()



if __name__ == "__main__":
    unittest.main()
