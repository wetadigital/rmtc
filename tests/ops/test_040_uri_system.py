# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import tempfile
from pathlib import Path

import numpy as np

from rmtc.system import Datetime, FileURI, Logger, RMTCException, Version
from rmtc.track.entities import Resource, Solution
from rmtc.ops.pipeline import ReaderWriter
from rmtc.ops.assets import Values

from rmtc.core.track.publishing.publishers.filesystem import DiskPublisher

from rmtc.core.ops.pipeline.readerwriters.filesystem import DiskReaderWriter
from rmtc.core.ops.io.filesystem.folders import FolderIO
from rmtc.core.ops.io.filesystem.json import TensorJSONFile

from abstract_rmtc_test import AbstractRMTCTest


class _Env:
    """Environment stub - the write path never consults packages"""

    def add_packages(self, packages):
        pass

    def remove_packages(self, packages):
        pass


def make_readerwriter(immutable=True, root=None, identity_mode="instantiated_at"):
    log = Logger()
    return DiskReaderWriter(
        log=log,
        env=_Env(),
        publisher=DiskPublisher(log=log, immutable=immutable),
        immutable=immutable,
        root=root,
        identity_mode=identity_mode,
    )


def make_values(name="weights"):
    """A concrete, valid, non-ephemeral leaf artifact"""
    return Values(
        name=name,
        io=TensorJSONFile(),
        tensors=(np.zeros(3, dtype="float32"),),
    )


class TestTimestampSegment(AbstractRMTCTest):
    """instantiated_at path segments - filesystem safety and ordering"""

    def test_segment_has_no_hostile_characters(self):
        """':' and '+' must never reach a path component"""
        segment = ReaderWriter.timestamp_segment(Datetime())
        self.assertNotIn(":", segment)
        self.assertNotIn("+", segment)
        self.assertNotIn("/", segment)

    def test_segment_is_deterministic(self):
        """The same stamp must always produce the same segment"""
        stamp = Datetime("2026-01-02T03:04:05.123456+00:00")
        self.assertEqual(
            ReaderWriter.timestamp_segment(stamp),
            ReaderWriter.timestamp_segment(stamp),
        )

    def test_segment_sort_is_chronological(self):
        """Lexicographic order of segments must equal creation order"""
        stamps = [
            Datetime("2026-01-02T03:04:04.999999+00:00"),
            Datetime("2026-01-02T03:04:05+00:00"),  # zero-microsecond edge
            Datetime("2026-01-02T03:04:05.000001+00:00"),
            Datetime("2026-01-02T03:04:06+00:00"),
        ]
        segments = [ReaderWriter.timestamp_segment(stamp) for stamp in stamps]
        self.assertEqual(segments, sorted(segments))

    def test_distinct_stamps_are_distinct_segments(self):
        first = Datetime("2026-01-02T03:04:05.000001+00:00")
        second = Datetime("2026-01-02T03:04:05.000002+00:00")
        self.assertNotEqual(
            ReaderWriter.timestamp_segment(first),
            ReaderWriter.timestamp_segment(second),
        )


class TestCategoryFolder(AbstractRMTCTest):
    """Category to folder naming"""

    def test_singular_category_is_pluralized(self):
        solution = Solution(name="Folder Test")
        run = solution.create_run(name="Run Folder")
        self.assertEqual(ReaderWriter.category_folder(run), "runs")

    def test_plural_category_is_untouched(self):
        """Weights must not become weightss"""
        weights = make_values()
        folder = ReaderWriter.category_folder(weights)
        self.assertFalse(folder.endswith("ss"))

    def test_folder_is_lowercase(self):
        entity = Resource(name="Case Test")
        folder = ReaderWriter.category_folder(entity)
        self.assertEqual(folder, folder.lower())


class TestCreateUri(AbstractRMTCTest):
    """Identity-derived URI construction - pure, deterministic, contained"""

    def setUp(self):
        super(TestCreateUri, self).setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = FileURI(path=Path(self._tmp.name))
        self.readerwriter = make_readerwriter()

    def test_layout_without_io(self):
        """No IO means no filename - the URI is a directory"""
        entity = Resource(name="Dir Target")
        uri = self.readerwriter.create_uri(entity, self.root)
        relative = uri.path.relative_to(self.root.path)
        self.assertEqual(len(relative.parts), 2)
        self.assertEqual(relative.parts[0], "resources")
        self.assertEqual(
            relative.parts[1],
            ReaderWriter.timestamp_segment(entity.instantiated_at),
        )

    def test_layout_with_io_appends_filename(self):
        """The IO owns the filename stem; identity is spliced into the
        filename itself rather than given its own directory level - a leaf
        artifact's category folder holds many files side by side instead of
        one file per identity-named subfolder"""
        leaf = make_values(name="weights")
        uri = self.readerwriter.create_uri(leaf, self.root)
        relative = uri.path.relative_to(self.root.path)
        self.assertEqual(len(relative.parts), 2)
        self.assertEqual(
            relative.parts[-1],
            f"weights-{ReaderWriter.timestamp_segment(leaf.instantiated_at)}.json",
        )

    def test_construction_is_pure(self):
        """create_uri must not touch the filesystem"""
        leaf = make_values()
        self.readerwriter.create_uri(leaf, self.root)
        self.assertEqual(list(Path(self._tmp.name).iterdir()), [])

    def test_construction_is_deterministic(self):
        """Identity is immutable, so the derived path must never move"""
        leaf = make_values()
        first = self.readerwriter.create_uri(leaf, self.root)
        second = self.readerwriter.create_uri(leaf, self.root)
        self.assertEqual(str(first.path), str(second.path))

    def test_same_name_distinct_identity_distinct_paths(self):
        """Two artifacts named alike must never share a location"""
        first = make_values(name="checkpoint")
        second = make_values(name="checkpoint")
        first_uri = self.readerwriter.create_uri(first, self.root)
        second_uri = self.readerwriter.create_uri(second, self.root)
        self.assertNotEqual(str(first_uri.path), str(second_uri.path))

    def test_invalid_root_raises(self):
        leaf = make_values()
        with self.assertRaises(RMTCException):
            self.readerwriter.create_uri(leaf, None)

    def test_absolute_name_cannot_escape(self):
        """A pathlib join with an absolute name replaces the whole path"""
        leaf = make_values(name="/etc/evil")
        with self.assertRaises(RMTCException):
            self.readerwriter.create_uri(leaf, self.root)

    def test_parent_traversal_cannot_escape(self):
        """is_relative_to is lexical - '..' needs its own refusal"""
        leaf = make_values(name="../../evil")
        with self.assertRaises(RMTCException):
            self.readerwriter.create_uri(leaf, self.root)

    def test_created_uri_survives_duplicate(self):
        """A mutated URI loses its string cache and duplicates empty -
        derived URIs must be freshly constructed so the chain can reuse them"""
        leaf = make_values(name="weights")
        uri = self.readerwriter.create_uri(leaf, self.root)
        copy = uri.duplicate()
        self.assertEqual(str(copy.path), str(uri.path))
        self.assertTrue(copy.is_valid())


class TestEagerConstruction(AbstractRMTCTest):
    """Creation-site URI chains - solution to run to artifact"""

    def setUp(self):
        super(TestEagerConstruction, self).setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.readerwriter = make_readerwriter()
        self.solution = Solution(
            name="Chain Solution",
            uri=FileURI(path=Path(self._tmp.name)),
        )

    def test_run_uri_derives_beneath_solution(self):
        run = self.solution.create_run(name="Chain Run")
        run.uri = self.readerwriter.create_uri(run, self.solution.uri)
        relative = run.uri.path.relative_to(self.solution.uri.path)
        self.assertEqual(relative.parts[0], "runs")
        self.assertEqual(
            relative.parts[1],
            ReaderWriter.timestamp_segment(run.instantiated_at),
        )

    def test_artifact_uri_derives_beneath_run(self):
        run = self.solution.create_run(name="Chain Run")
        run.uri = self.readerwriter.create_uri(run, self.solution.uri)
        leaf = make_values(name="weights")
        leaf.uri = self.readerwriter.create_uri(leaf, run.uri)
        self.assertTrue(leaf.uri.path.is_relative_to(run.uri.path))
        self.assertEqual(
            leaf.uri.path.name,
            f"weights-{ReaderWriter.timestamp_segment(leaf.instantiated_at)}.json",
        )

    def test_no_folders_exist_before_write(self):
        """Construction allocates nothing - no empty-run litter on a crash"""
        run = self.solution.create_run(name="Unwritten Run")
        run.uri = self.readerwriter.create_uri(run, self.solution.uri)
        leaf = make_values()
        leaf.uri = self.readerwriter.create_uri(leaf, run.uri)
        self.assertEqual(list(Path(self._tmp.name).iterdir()), [])

    def test_two_runs_never_share_a_directory(self):
        first = self.solution.create_run(name="Twin Run")
        second = self.solution.create_run(name="Twin Run")
        first.uri = self.readerwriter.create_uri(first, self.solution.uri)
        second.uri = self.readerwriter.create_uri(second, self.solution.uri)
        self.assertNotEqual(str(first.uri.path), str(second.uri.path))


class TestWritePath(AbstractRMTCTest):
    """ReaderWriter.write - enforcement, side effects and guards"""

    def setUp(self):
        super(TestWritePath, self).setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = FileURI(path=Path(self._tmp.name))

    def test_write_lands_the_file_and_creates_parents(self):
        """No pre-allocation - the write makes its own directories"""
        readerwriter = make_readerwriter()
        leaf = make_values()
        leaf.uri = readerwriter.create_uri(leaf, self.root)
        readerwriter.write([leaf])
        self.assertTrue(leaf.uri.path.exists())

    def test_write_without_uri_is_refused(self):
        """A location is never guessed - fail closed"""
        readerwriter = make_readerwriter()
        leaf = make_values()
        with self.assertRaises(RMTCException):
            readerwriter.write([leaf])

    def test_write_outside_configured_root_is_refused(self):
        """The write-anywhere hole must stay closed"""
        inside = tempfile.TemporaryDirectory()
        self.addCleanup(inside.cleanup)
        readerwriter = make_readerwriter(root=Path(inside.name))
        leaf = make_values()
        leaf.uri = FileURI(path=Path(self._tmp.name) / "outside.json")
        with self.assertRaises(RMTCException):
            readerwriter.write([leaf])

    def test_immutable_write_refuses_existing_target(self):
        readerwriter = make_readerwriter(immutable=True)
        leaf = make_values()
        leaf.uri = FileURI(path=Path(self._tmp.name) / "occupied.json")
        leaf.uri.path.write_text("occupied")
        with self.assertRaises(RMTCException):
            readerwriter.write([leaf])
        self.assertEqual(leaf.uri.path.read_text(), "occupied")

    def test_mutable_write_overwrites_existing_target(self):
        readerwriter = make_readerwriter(immutable=False)
        leaf = make_values()
        leaf.uri = FileURI(path=Path(self._tmp.name) / "occupied.json")
        leaf.uri.path.write_text("occupied")
        readerwriter.write([leaf])
        self.assertNotEqual(leaf.uri.path.read_text(), "occupied")

    def test_ephemeral_artifacts_are_skipped(self):
        """No IO means ephemeral - nothing may land on disk"""
        readerwriter = make_readerwriter()
        leaf = Values(name="ghost", tensors=(np.zeros(3, dtype="float32"),))
        readerwriter.write([leaf])
        self.assertEqual(list(Path(self._tmp.name).iterdir()), [])

    def test_user_override_is_written_verbatim(self):
        """URI set means put it exactly there - no derivation"""
        readerwriter = make_readerwriter()
        target = Path(self._tmp.name) / "chosen" / "spot.json"
        leaf = make_values()
        leaf.uri = FileURI(path=target)
        readerwriter.write([leaf])
        self.assertTrue(target.exists())

    def test_prepare_creates_parent_directories(self):
        readerwriter = make_readerwriter()
        uri = FileURI(path=Path(self._tmp.name) / "a" / "b" / "c.json")
        readerwriter.prepare(uri)
        self.assertTrue(uri.path.parent.is_dir())
        self.assertFalse(uri.path.exists())


class TestExclusiveCreate(AbstractRMTCTest):
    """The 'x' mode collision claim in file-owning IOs"""

    def setUp(self):
        super(TestExclusiveCreate, self).setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_immutable_io_write_refuses_existing_file(self):
        """The claim is atomic at the OS - no check-then-write window"""
        readerwriter = make_readerwriter(immutable=True)
        leaf = make_values()
        target = Path(self._tmp.name) / "claimed.json"
        target.write_text("claimed")
        uri = FileURI(path=target)
        with self.assertRaises(FileExistsError):
            leaf.io.write(uri, leaf, readerwriter)
        self.assertEqual(target.read_text(), "claimed")

    def test_mutable_io_write_overwrites(self):
        readerwriter = make_readerwriter(immutable=False)
        leaf = make_values()
        target = Path(self._tmp.name) / "replaceable.json"
        target.write_text("replaceable")
        uri = FileURI(path=target)
        leaf.io.write(uri, leaf, readerwriter)
        self.assertNotEqual(target.read_text(), "replaceable")


class TestFolderIO(AbstractRMTCTest):
    """Dataset member placement - user-placed folder, position-named members"""

    def setUp(self):
        super(TestFolderIO, self).setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.readerwriter = make_readerwriter()

    def _make_dataset(self):
        from rmtc.ops.artifacts import Dataset

        io = FolderIO(asset_io=TensorJSONFile())
        dataset = Dataset(
            name="Member Test",
            io=io,
            uri=FileURI(path=Path(self._tmp.name) / "dataset"),
        )
        dataset.columns = ["a"]
        return dataset, io

    def test_init_places_unplaced_members(self):
        """Members land beneath the dataset folder with position names"""
        dataset, io = self._make_dataset()
        member = Values(tensors=(np.zeros(3, dtype="float32"),))
        dataset.fill_row([member])
        io.init(dataset, self.readerwriter)
        self.assertEqual(member.name, "0000_a")
        self.assertTrue(member.uri.path.is_relative_to(dataset.uri.path))
        self.assertEqual(member.uri.path.name, "0000_a.json")

    def test_init_leaves_placed_members_alone(self):
        """A member with a concrete URI keeps its name and location"""
        dataset, io = self._make_dataset()
        placed = Values(
            name="already_here",
            tensors=(np.zeros(3, dtype="float32"),),
            uri=FileURI(path=Path(self._tmp.name) / "elsewhere.json"),
        )
        dataset.fill_row([placed])
        io.init(dataset, self.readerwriter)
        self.assertEqual(placed.name, "already_here")
        self.assertEqual(
            str(placed.uri.path), str(Path(self._tmp.name) / "elsewhere.json")
        )

    def test_init_assigns_dataset_io_to_members(self):
        dataset, io = self._make_dataset()
        member = Values(tensors=(np.zeros(3, dtype="float32"),))
        dataset.fill_row([member])
        io.init(dataset, self.readerwriter)
        self.assertIsNotNone(member.io)

    def test_init_is_pure(self):
        """Placement is bookkeeping - the folder appears only at write"""
        dataset, io = self._make_dataset()
        member = Values(tensors=(np.zeros(3, dtype="float32"),))
        dataset.fill_row([member])
        io.init(dataset, self.readerwriter)
        self.assertFalse(dataset.uri.path.exists())


class TestIONames(AbstractRMTCTest):
    """create_name - filename only, format owned by the IO"""

    def test_tensor_json_name(self):
        """The Path concatenation defect - must not raise"""
        leaf = make_values(name="sample")
        self.assertEqual(TensorJSONFile().create_name(leaf), "sample.json")

    def test_folder_io_has_no_name(self):
        """Directory-target IOs must yield None so no filename is appended"""
        io = FolderIO(asset_io=TensorJSONFile())
        self.assertIsNone(io.create_name(make_values()))


class TestDeleteUri(AbstractRMTCTest):
    """delete_uri - immutability and the scalar/list defect"""

    def setUp(self):
        super(TestDeleteUri, self).setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_immutable_delete_is_refused(self):
        readerwriter = make_readerwriter(immutable=True)
        with self.assertRaises(RMTCException):
            readerwriter.delete_uri(FileURI(path=Path(self._tmp.name) / "x.json"))

    def test_mutable_delete_of_existing_reaches_the_stub(self):
        """Must raise NotImplementedError, not TypeError from iterating a URI"""
        readerwriter = make_readerwriter(immutable=False)
        target = Path(self._tmp.name) / "doomed.json"
        target.write_text("doomed")
        with self.assertRaises(NotImplementedError):
            readerwriter.delete_uri(FileURI(path=target))

    def test_mutable_delete_of_missing_is_a_noop(self):
        readerwriter = make_readerwriter(immutable=False)
        readerwriter.delete_uri(FileURI(path=Path(self._tmp.name) / "absent.json"))


class TestIdentityMode(AbstractRMTCTest):
    """identity_mode selects instantiated_at vs version as the path-identity
    source - instantiated_at remains the default, version is opt-in per
    DiskReaderWriter instance"""

    def setUp(self):
        super(TestIdentityMode, self).setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = FileURI(path=Path(self._tmp.name))

    def test_default_identity_mode_is_instantiated_at(self):
        readerwriter = make_readerwriter()
        leaf = make_values(name="weights")
        uri = readerwriter.create_uri(leaf, self.root)
        self.assertEqual(
            uri.path.name,
            f"weights-{ReaderWriter.timestamp_segment(leaf.instantiated_at)}.json",
        )

    def test_version_identity_mode_uses_version_in_filename(self):
        readerwriter = make_readerwriter(identity_mode="version")
        leaf = make_values(name="weights")
        leaf.version = Version("3.2.1")
        uri = readerwriter.create_uri(leaf, self.root)
        self.assertEqual(uri.path.name, "weights-3.2.1.json")

    def test_version_identity_mode_container_uses_version_as_directory(self):
        """No-IO/container entities (e.g. Run) keep identity as a bare
        directory segment in both modes - only leaf/filename-bearing
        artifacts get identity spliced into the filename"""
        readerwriter = make_readerwriter(identity_mode="version")
        solution = Solution(name="Version Mode Solution", uri=self.root)
        run = solution.create_run(name="Version Mode Run")
        run.version = Version("4.0.0")
        uri = readerwriter.create_uri(run, self.root)
        relative = uri.path.relative_to(self.root.path)
        self.assertEqual(relative.parts, ("runs", "4.0.0"))

    def test_version_identity_mode_with_unset_version_raises(self):
        """version is a plain, freely-settable property (never readonly),
        so a caller can assign an explicitly invalid Version() (major=0) -
        create_uri() must refuse to build a path segment from it rather
        than silently emitting 'weights-0.0.0.pt'"""
        readerwriter = make_readerwriter(identity_mode="version")
        leaf = make_values(name="weights")
        leaf.version = Version()  # major=0, invalid
        with self.assertRaises(RMTCException):
            readerwriter.create_uri(leaf, self.root)

    def test_invalid_identity_mode_rejected_at_construction(self):
        with self.assertRaises(RMTCException):
            make_readerwriter(identity_mode="not_a_real_mode")

    def test_construction_is_pure_in_version_mode_too(self):
        """create_uri must never touch the filesystem, regardless of mode"""
        readerwriter = make_readerwriter(identity_mode="version")
        leaf = make_values(name="weights")
        leaf.version = Version("1.0.0")
        readerwriter.create_uri(leaf, self.root)
        self.assertEqual(list(Path(self._tmp.name).iterdir()), [])

    def test_set_identity_mode_overrides_configured_default(self):
        """A user can flip identity_mode on their own instance after
        construction, overriding whatever the global config set it to."""
        readerwriter = make_readerwriter()
        leaf = make_values(name="weights")
        leaf.version = Version("2.0.0")

        readerwriter.set_identity_mode("version")
        uri = readerwriter.create_uri(leaf, self.root)

        self.assertEqual(uri.path.name, "weights-2.0.0.json")

    def test_set_identity_mode_can_restore_default(self):
        readerwriter = make_readerwriter(identity_mode="version")
        leaf = make_values(name="weights")

        readerwriter.set_identity_mode("instantiated_at")
        uri = readerwriter.create_uri(leaf, self.root)

        self.assertEqual(
            uri.path.name,
            f"weights-{ReaderWriter.timestamp_segment(leaf.instantiated_at)}.json",
        )

    def test_identity_mode_property_reflects_current_value(self):
        readerwriter = make_readerwriter()
        self.assertEqual(readerwriter.identity_mode, "instantiated_at")
        readerwriter.set_identity_mode("version")
        self.assertEqual(readerwriter.identity_mode, "version")

    def test_set_identity_mode_rejects_invalid_mode(self):
        readerwriter = make_readerwriter()
        with self.assertRaises(RMTCException):
            readerwriter.set_identity_mode("not_a_real_mode")
        # rejected override must not clobber the previously valid mode
        self.assertEqual(readerwriter.identity_mode, "instantiated_at")


class TestReserve(AbstractRMTCTest):
    """DiskPublisher.reserve() - explicit, caller-invoked version allocation

    Never called implicitly from create_uri() or anywhere else - a caller
    using identity_mode=version who wants an auto-bumped version calls this
    themselves before setting entity.version and writing.
    """

    def setUp(self):
        super(TestReserve, self).setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.publisher = DiskPublisher(log=Logger(), immutable=False)

    def test_file_case_bumps_major_on_each_call(self):
        path = Path(self._tmp.name) / "weights.pt"
        uri1, version1 = self.publisher.reserve(path)
        self.assertEqual(version1, Version("1.0.0"))
        self.assertEqual(uri1.path, Path(self._tmp.name) / "weights-1.0.0.pt")

        uri2, version2 = self.publisher.reserve(path)
        self.assertEqual(version2, Version("2.0.0"))
        self.assertEqual(uri2.path, Path(self._tmp.name) / "weights-2.0.0.pt")

    def test_file_case_creates_parent_directories(self):
        path = Path(self._tmp.name) / "nested" / "dir" / "weights.pt"
        uri, _ = self.publisher.reserve(path)
        self.assertTrue(uri.path.parent.is_dir())

    def test_folder_case_scans_existing_and_bumps_max(self):
        folder = Path(self._tmp.name) / "runs"
        folder.mkdir()
        (folder / "1.0.0").mkdir()
        (folder / "3.0.0").mkdir()
        uri, version = self.publisher.reserve(folder)
        self.assertEqual(version, Version("4.0.0"))
        self.assertEqual(uri.path, folder / "4.0.0")
        self.assertTrue(uri.path.is_dir())

    def test_folder_case_with_no_existing_versions_starts_at_one(self):
        folder = Path(self._tmp.name) / "runs"
        uri, version = self.publisher.reserve(folder)
        self.assertEqual(version, Version("1.0.0"))
        self.assertTrue(uri.path.is_dir())

    def test_folder_case_ignores_unparseable_siblings(self):
        folder = Path(self._tmp.name) / "runs"
        folder.mkdir()
        (folder / "not_a_version").mkdir()
        (folder / "2.0.0").mkdir()
        uri, version = self.publisher.reserve(folder)
        self.assertEqual(version, Version("3.0.0"))

    def test_reserve_never_touches_the_filesystem_before_being_called(self):
        """Sanity check that reserve() is opt-in - create_uri() elsewhere in
        this suite must never have already materialized this path"""
        path = Path(self._tmp.name) / "untouched.pt"
        self.assertFalse(path.parent.exists() and any(path.parent.iterdir()))
        self.publisher.reserve(path)
        self.assertTrue(path.parent.exists())

    def test_reserve_is_not_called_by_create_uri(self):
        """create_uri in version mode must raise on an unset version rather
        than silently calling reserve() to fill one in - see
        TestIdentityMode.test_version_identity_mode_with_unset_version_raises"""
        readerwriter = make_readerwriter(identity_mode="version")
        root = FileURI(path=Path(self._tmp.name))
        leaf = make_values(name="weights")
        leaf.version = Version()  # invalid
        with self.assertRaises(RMTCException):
            readerwriter.create_uri(leaf, root)
        self.assertEqual(list(Path(self._tmp.name).iterdir()), [])
