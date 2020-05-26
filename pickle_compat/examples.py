"""Examples for tests."""
from collections import namedtuple

Foo = namedtuple("Foo", "a, b")


class OldClass:
    a = "UNSET"
    b = "UNSET"

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return "OldClass(%r, %r)" % (self.a, self.b)


class NewClass(object):
    a = "UNSET"
    b = "UNSET"

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return "NewClass(%r, %r)" % (self.a, self.b)


class DictSubclass(dict):
    pass
