import collections
import itertools
import numbers
import random
import string
import sys

import numpy as np

from pandas.core.dtypes.base import ExtensionDtype
from pandas.core.arrays import ExtensionArray


class JSONDtype(ExtensionDtype):
    type = collections.Mapping
    name = 'json'

    @classmethod
    def construct_from_string(cls, string):
        if string == cls.name:
            return cls()
        else:
            raise TypeError("Cannot construct a '{}' from "
                            "'{}'".format(cls, string))


class JSONArray(ExtensionArray):
    dtype = JSONDtype()

    def __init__(self, values):
        for val in values:
            if not isinstance(val, self.dtype.type):
                raise TypeError
        self.data = values

        # Some aliases for common attribute names to ensure pandas supports
        # these
        self._items = self._data = self.data
        # those aliases are currently not working due to assumptions
        # in internal code (GH-20735)
        # self._values = self.values = self.data

    @classmethod
    def _from_sequence(cls, scalars):
        return cls(scalars)

    @classmethod
    def _from_factorized(cls, values, original):
        return cls([collections.UserDict(x) for x in values if x != ()])

    def __getitem__(self, item):
        if isinstance(item, numbers.Integral):
            return self.data[item]
        elif isinstance(item, np.ndarray) and item.dtype == 'bool':
            return self._from_sequence([x for x, m in zip(self, item) if m])
        elif isinstance(item, collections.Iterable):
            # fancy indexing
            return type(self)([self.data[i] for i in item])
        else:
            # slice
            return type(self)(self.data[item])

    def __setitem__(self, key, value):
        if isinstance(key, numbers.Integral):
            self.data[key] = value
        else:
            if not isinstance(value, (type(self),
                                      collections.Sequence)):
                # broadcast value
                value = itertools.cycle([value])

            if isinstance(key, np.ndarray) and key.dtype == 'bool':
                # masking
                for i, (k, v) in enumerate(zip(key, value)):
                    if k:
                        assert isinstance(v, self.dtype.type)
                        self.data[i] = v
            else:
                for k, v in zip(key, value):
                    assert isinstance(v, self.dtype.type)
                    self.data[k] = v

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return 'JSONArary({!r})'.format(self.data)

    @property
    def nbytes(self):
        return sys.getsizeof(self.data)

    def isna(self):
        return np.array([x == self._na_value for x in self.data])

    def take(self, indexer, allow_fill=True, fill_value=None):
        try:
            output = [self.data[loc] if loc != -1 else self._na_value
                      for loc in indexer]
        except IndexError:
            raise IndexError("Index is out of bounds or cannot do a "
                             "non-empty take from an empty array.")
        return self._from_sequence(output)

    def copy(self, deep=False):
        return type(self)(self.data[:])

    def unique(self):
        # Parent method doesn't work since np.array will try to infer
        # a 2-dim object.
        return type(self)([
            dict(x) for x in list(set(tuple(d.items()) for d in self.data))
        ])

    @property
    def _na_value(self):
        return {}

    @classmethod
    def _concat_same_type(cls, to_concat):
        data = list(itertools.chain.from_iterable([x.data for x in to_concat]))
        return cls(data)

    def _values_for_factorize(self):
        frozen = self._values_for_argsort()
        return frozen, ()

    def _values_for_argsort(self):
        # Disable NumPy's shape inference by including an empty tuple...
        # If all the elemnts of self are the same size P, NumPy will
        # cast them to an (N, P) array, instead of an (N,) array of tuples.
        frozen = [()] + list(tuple(x.items()) for x in self)
        return np.array(frozen, dtype=object)[1:]


def make_data():
    # TODO: Use a regular dict. See _NDFrameIndexer._setitem_with_indexer
    return [collections.UserDict([
        (random.choice(string.ascii_letters), random.randint(0, 100))
        for _ in range(random.randint(0, 10))]) for _ in range(100)]
