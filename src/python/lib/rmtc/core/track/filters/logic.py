# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Tracking storage interface - contains all the core
entity types that we expect to store and their properties.
"""

from rmtc.system import Operator
from rmtc.track.entities import Filter


class Truth(Filter):
    """Either passes or fails according to a given bool value"""

    def __init__(
        self,
        truth=None,
    ):
        super(Truth, self).__init__()
        self.add_property(
            "truth",
            bool,
            truth,
        )

    def __call__(self, entities):
        return self.truth


class LogicFilter(Filter):
    """Passes if the logical operation on the given set of filters is true"""

    def __init__(
        self,
        filters=None,
        operator=None,
    ):
        super(LogicFilter, self).__init__()
        self.add_property(
            "filters",
            [Filter],
            filters,
        )
        self.add_property(
            "operator",
            Operator,
            operator,
        )

    def __call__(self, entities):

        if self.operator == Operator.AND:
            for f in self.filters:
                if not f(entities):
                    return False
        elif self.operator == Operator.NAND:
            counter = 0
            for f in self.filters:
                if not f(entities):
                    counter += 1
                return counter == len(self.filters)
        elif self.operator == Operator.OR:
            for f in self.filters:
                if f(entities):
                    return True
        elif self.operator == Operator.NOR:
            for f in self.filters:
                if f(entities):
                    return False
        elif self.operator == Operator.XOR:
            counter = 0
            for f in self.filters:
                if f(entities):
                    counter += 1
            return counter == 1
        elif self.operator == Operator.XNOR:
            last = None
            for f in self.filters:
                if last is not None:
                    if last != f(entities):
                        return False
                else:
                    last = f(entities)
            return True

        return False
