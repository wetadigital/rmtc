# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import subprocess
import sys
import importlib

from rmtc.system import Criteria, Version, Package, RMTCException
from rmtc.core.system.environment import PackageTracker


def parse_requirements(path):
    """
    Load the requirements package list from the path
    and return them
    """
    packages = []
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line.startswith("#"):
                continue
            criteria = None
            version = None
            name = line.strip()
            for op in [
                "==",
                ">=",
                "<=",
                "~=",
                ">",
                "<",  # order is important: '>=' matches with '>'
            ]:
                if op not in line:
                    continue
                if op == "==":
                    criteria = Criteria.EXACT
                elif op == ">":
                    criteria = Criteria.LATER
                elif op == "<":
                    criteria = Criteria.EARLIER
                elif op == "<=":
                    criteria = Criteria.MAXIMUM
                elif op == ">=":
                    criteria = Criteria.MINIMUM
                elif op == "~=":
                    criteria = Criteria.APPROX
                parts = line.split(op)
                if len(parts) != 2:
                    raise RMTCException(f"Unsupported requirement {parts} in {path}")
                name = parts[0].strip()
                version = Version(parts[1].strip())
                break
            package = Package(
                name=name,
                version=version,
                criteria=criteria,
            )
            packages.append(package)
    return packages


class UV(PackageTracker):
    """
    UV is not a great fit for the current design which assume
    pulling in packages into the current process for importing

    We need to move to venv and subprocess based environments for
    inference & training
    """

    def __init__(
        self,
        log,
        path,
    ):
        super(UV, self).__init__(log)
        self._env = path
        if path is None:
            raise RMTCException("UV requires a project path to manage")

    @property
    def env(self):
        return self._env

    def _setup(self):
        subprocess.run(
            ["uv", "init", self._env, "--bare"],
            capture_output=True,
            text=True,
            check=True,
        )

    def setup_packages(self, packages):
        self._setup()

        for package in packages:

            op = None
            if package.criteria == Criteria.EXACT:
                op = "=="
            elif package.criteria == Criteria.LATER:
                op = ">"
            elif package.criteria == Criteria.EARLIER:
                op = "<"
            elif package.criteria == Criteria.MINIMUM:
                op = ">="
            elif package.criteria == Criteria.MAXIMUM:
                op = "<="
            elif package.criteria == Criteria.APPROX:
                op = "~="

            subprocess.run(
                [
                    "uv",
                    "add",
                    f"{package.name}{op}{package.version}",
                    "--python",
                    sys.executable,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        importlib.invalidate_caches()

    def teardown_packages(self, packages):
        self._setup()

        for package in packages:
            subprocess.run(
                [
                    "uv",
                    "remove",
                    package.name,
                    "--python",
                    sys.executable,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        importlib.invalidate_caches()

    def setup(self, env):

        # env is the requirements.txt location
        if self._env is not None:
            return False

        packages = parse_requirements(env)
        self.add_packages(packages)
        self._env = env

        return True

    def teardown(self, env):

        # env is the requirements.txt location
        if self._env != env:
            return None

        packages = parse_requirements(env)
        self.remove_packages(packages)
        self._env = env

        return True


class UVPip(PackageTracker):

    def __init__(
        self,
        log,
    ):
        super(UVPip, self).__init__(log)
        self._env = None

    @property
    def env(self):
        return self._env

    def setup_packages(self, packages):
        for package in packages:

            op = None
            if package.criteria == Criteria.EXACT:
                op = "=="
            elif package.criteria == Criteria.LATER:
                op = ">"
            elif package.criteria == Criteria.EARLIER:
                op = "<"
            elif package.criteria == Criteria.MINIMUM:
                op = ">="
            elif package.criteria == Criteria.MAXIMUM:
                op = "<="
            elif package.criteria == Criteria.APPROX:
                op = "~="

            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    f"{package.name}{op}{package.version}",
                    "--python",
                    sys.executable,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        importlib.invalidate_caches()

    def teardown_packages(self, packages):
        for package in packages:
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "uninstall",
                    {package.name},
                    "--python",
                    sys.executable,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        importlib.invalidate_caches()

    def setup(self, env):

        # env is the requirements.txt location
        if self._env is not None:
            return False

        packages = parse_requirements(env)
        self.add_packages(packages)
        self._env = env

        return True

    def teardown(self, env):

        # env is the requirements.txt location
        if self._env != env:
            return None

        packages = parse_requirements(env)
        self.remove_packages(packages)
        self._env = env

        return True
