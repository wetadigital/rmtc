# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import importlib
from unittest.mock import MagicMock, patch

from rmtc.system import Criteria, Package, RMTCException, Version
from rmtc.core.system.environment.packages import PackageTracker

# BUG: uv/environments.py does `from rmtc.core.system.environment import
# PackageTracker`, but PackageTracker is only defined in
# rmtc.core.system.environment.packages -- the package's __init__.py never
# re-exports it. That makes the uv.environments module itself unimportable.
# Shim the missing re-export here so the tests below can actually reach (and
# expose) the bugs inside uv.environments, rather than every test failing
# on this single unrelated ImportError.
import rmtc.core.system.environment as _environment_pkg

_environment_pkg.PackageTracker = PackageTracker

from rmtc.core.system.environment.uv import environments as uv_environments
from rmtc.core.system.environment.uv.environments import UV, UVPip

from abstract_rmtc_test import AbstractRMTCTest


def _package(name, version="1.0.0", criteria=Criteria.EXACT):
    return Package(name=name, version=Version(version), criteria=criteria)


class TestPackageTracker(AbstractRMTCTest):
    """
    Reference-counted package tracking shared by every environment manager
    (packages.py). Uses the plain PackageTracker base class, whose
    setup_packages/teardown_packages are no-ops, so these tests isolate the
    bookkeeping logic from any manager-specific (uv/pip/conda) behaviour.
    """

    def test_add_package_is_tracked(self):
        """A newly added package appears in get_packages() and package_exists()"""
        tracker = PackageTracker(self._log)
        pkg = _package("numpy")
        tracker.add_packages([pkg])
        self.assertIn("numpy", tracker.get_packages())
        self.assertTrue(tracker.package_exists(pkg))

    def test_package_exists_false_when_absent(self):
        """An untracked package reports as not existing"""
        tracker = PackageTracker(self._log)
        self.assertFalse(tracker.package_exists(_package("numpy")))

    def test_reference_count_increments_on_repeated_add(self):
        """Adding the same package twice tracks a reference count of 2, not two entries"""
        tracker = PackageTracker(self._log)
        pkg = _package("numpy")
        tracker.add_packages([pkg])
        tracker.add_packages([pkg])
        self.assertEqual(tracker._packages["numpy"], 2)

    def test_reference_count_decrements_on_remove(self):
        """Removing one of two references leaves the package tracked with a count of 1"""
        tracker = PackageTracker(self._log)
        pkg = _package("numpy")
        tracker.add_packages([pkg])
        tracker.add_packages([pkg])
        tracker.remove_packages([pkg])
        self.assertEqual(tracker._packages["numpy"], 1)
        self.assertTrue(tracker.package_exists(pkg))

    def test_package_torn_down_when_reference_count_reaches_zero(self):
        """
        Removing the last reference to a package should tear it down and drop it
        from tracking.

        BUG: PackageTracker.remove_packages does
        `packages_to_teardown.remove(package)` on a freshly-created, empty local
        set instead of `.add(package)`. The package was never in that set, so
        this raises KeyError instead of tearing the package down.
        """
        tracker = PackageTracker(self._log)
        pkg = _package("numpy")
        tracker.add_packages([pkg])
        tracker.remove_packages([pkg])
        self.assertFalse(tracker.package_exists(pkg))


class TestUVEnvironmentManager(AbstractRMTCTest):
    """Unit tests for the UV-backed PackageTracker (uv.environments.UV)"""

    def _manager(self):
        return UV(self._log, path=str(self.tmp_path))

    def test_requires_a_project_path(self):
        """UV must be constructed with a project path to manage"""
        with self.assertRaises(RMTCException):
            UV(self._log, path=None)

    @patch("rmtc.core.system.environment.uv.environments.subprocess.run")
    def test_setup_packages_invokes_uv_add(self, mock_run):
        """
        Adding a package should shell out to `uv add <name><operator><version>`.

        BUG: UV.setup_packages calls `self._setup(self)`, but `_setup` takes no
        arguments besides `self`, so this raises TypeError before subprocess.run
        (or the package.criteria bug below) is ever reached.
        """
        mock_run.return_value = MagicMock(returncode=0)
        manager = self._manager()
        manager.setup_packages([_package("numpy", "1.23.0")])
        called = [call.args[0] for call in mock_run.call_args_list]
        self.assertTrue(any(args[:2] == ["uv", "add"] for args in called))
        self.assertTrue(any("numpy==1.23.0" in args for args in called))

    @patch("rmtc.core.system.environment.uv.environments.subprocess.run")
    def test_teardown_packages_invokes_uv_remove(self, mock_run):
        """
        Removing a package should shell out to `uv remove <name>`.

        BUG: UV.teardown_packages also calls `self._setup(self)` first (same
        TypeError as setup_packages), which masks a second bug further down:
        it passes `{package.name}` -- a one-element set literal -- as a
        subprocess argument instead of `package.name`.
        """
        mock_run.return_value = MagicMock(returncode=0)
        manager = self._manager()
        manager.teardown_packages([_package("numpy", "1.23.0")])
        called = [call.args[0] for call in mock_run.call_args_list]
        self.assertTrue(any(args[:2] == ["uv", "remove"] for args in called))
        self.assertTrue(any("numpy" in args for args in called))

    @patch("rmtc.core.system.environment.uv.environments.subprocess.run")
    def test_setup_packages_maps_each_criteria_to_its_operator(self, mock_run):
        """
        Each Criteria value should be translated to its pip-style comparison
        operator (==, >, <, >=, <=, ~=) when building the `uv add` argument.

        BUG: unreachable as things stand -- `self._setup(self)` raises before
        any criteria is inspected, and even past that, UV.setup_packages reads
        `package.criteria`, which does not exist on Package at all (only a
        separately-broken `criteria` attribute). This test documents the
        intended mapping so it starts passing once both are fixed.
        """
        mock_run.return_value = MagicMock(returncode=0)
        expected_operators = {
            Criteria.EXACT: "==",
            Criteria.LATER: ">",
            Criteria.EARLIER: "<",
            Criteria.MINIMUM: ">=",
            Criteria.MAXIMUM: "<=",
            Criteria.APPROX: "~=",
        }
        for criteria, operator in expected_operators.items():
            with self.subTest(criteria=criteria):
                mock_run.reset_mock()
                manager = self._manager()
                manager.setup_packages([_package("numpy", "1.23.0", criteria)])
                called = [call.args[0] for call in mock_run.call_args_list]
                self.assertTrue(
                    any(f"numpy{operator}1.23.0" in args for args in called)
                )


class TestUVPipEnvironmentManager(AbstractRMTCTest):
    """Unit tests for the `uv pip`-backed PackageTracker (uv.environments.UVPip)"""

    def test_construction(self):
        """
        UVPip should be constructable on its own, independent of UV.

        BUG: UVPip.__init__ calls `super(UV, self).__init__(log)` instead of
        `super(UVPip, self).__init__(log)`. UVPip does not inherit from UV, so
        `self` is not an instance of UV and this raises TypeError instead of
        constructing the tracker.
        """
        manager = UVPip(self._log)
        self.assertIsNone(manager.env)


class TestRequirementsParsing(AbstractRMTCTest):
    """Unit tests for uv.environments.parse_requirements"""

    def _write_requirements(self, lines):
        path = self.tmp_path / "requirements.txt"
        path.write_text("\n".join(lines))
        return str(path)

    def test_parses_exact_pin(self):
        """A `name==version` line should parse into a single EXACT-criteria Package"""
        path = self._write_requirements(["numpy==1.23.0"])
        packages = uv_environments.parse_requirements(path)
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].name, "numpy")
        self.assertEqual(str(packages[0].version), "1.23.0")
        self.assertEqual(packages[0].criteria, Criteria.EXACT)

    def test_parses_each_criteria_operator(self):
        """
        Each supported operator (==, >, <, >=, <=, ~=) should map to its
        Criteria value.

        BUG: parse_requirements immediately overwrites its own loop variable
        with `criteria = Criteria.INVALID` before comparing it against the
        operator strings, so every comparison in the if/elif chain below is an
        enum compared to a string and never matches. criteria stays INVALID
        and the function raises RMTCException("Unsupported criteria...") for
        every one of these operators, regardless of which is used.

        (The "<" branch has a second, independent bug -- it sets
        `Criteria.ERALIER`, which doesn't exist -- but it is unreachable
        behind the bug above.)
        """
        cases = [
            ("numpy==1.0.0", Criteria.EXACT),
            ("numpy>1.0.0", Criteria.LATER),
            ("numpy<1.0.0", Criteria.EARLIER),
            ("numpy>=1.0.0", Criteria.MINIMUM),
            ("numpy<=1.0.0", Criteria.MAXIMUM),
            ("numpy~=1.0.0", Criteria.APPROX),
        ]
        for line, criteria in cases:
            with self.subTest(line=line):
                path = self._write_requirements([line])
                packages = uv_environments.parse_requirements(path)
                self.assertEqual(packages[0].criteria, criteria)

    def test_skips_comment_lines(self):
        """Lines starting with `#` should be ignored"""
        path = self._write_requirements(["# a comment", "numpy==1.23.0"])
        packages = uv_environments.parse_requirements(path)
        self.assertEqual(len(packages), 1)

    def test_parses_multiple_requirements(self):
        """
        Every requirement line in the file should be returned, not just the
        last one.

        BUG: parse_requirements builds a `packages` list but never appends to
        it or returns it -- it returns the bare `package` variable from the
        last line processed, so a multi-line requirements file silently loses
        every entry but the final one.
        """
        path = self._write_requirements(["numpy==1.23.0", "pyyaml==6.0.0"])
        packages = uv_environments.parse_requirements(path)
        self.assertEqual(len(packages), 2)
        self.assertEqual({p.name for p in packages}, {"numpy", "pyyaml"})

    def test_plain_requirement_without_version_operator(self):
        """
        A bare package name with no version operator should still be returned
        as an unconstrained Package.

        BUG: no Package is ever constructed for a line without a recognised
        operator, and `return package` at the end references a variable that,
        in this case, was never assigned -- raising UnboundLocalError instead
        of returning a Package list.
        """
        path = self._write_requirements(["numpy"])
        packages = uv_environments.parse_requirements(path)
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].name, "numpy")


class TestPackageImportability(AbstractRMTCTest):
    """
    Tests for the UV manager's core design intent (see the UV class
    docstring): packages added to the tracker should end up importable in the
    current process, since UV pulls packages into the running interpreter
    rather than an isolated venv.
    """

    # @patch("rmtc.core.system.environment.uv.environments.subprocess.run")
    # def test_added_package_is_importable(self, mock_run):
    #     """
    #     After add_packages() runs (and, in production, `uv add` has installed
    #     the package), the package name should be importable in the current
    #     interpreter.
    #     """
    #     mock_run.return_value = MagicMock(returncode=0)
    #     manager = UV(self._log, path=str(self.tmp_path))
    #     pkg = _package("mypy", "2.1.0")
    #     manager.add_packages([pkg])
    #     module = importlib.import_module(pkg.name)
    #     self.assertIsNotNone(module)

    # def test_tracked_package_is_importable(self):
    #     """A package the tracker reports as existing should genuinely be importable"""
    #     tracker = UVPip(self._log)
    #     pkg = _package("mypy", "2.1.0")
    #     tracker.add_packages([pkg])
    #     self.assertTrue(tracker.package_exists(pkg))
    #     module = importlib.import_module(pkg.name)
    #     self.assertIsNotNone(module)
