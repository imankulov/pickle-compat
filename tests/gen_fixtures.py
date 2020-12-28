#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate fixtures and save then to "fixtures" directory, under "py2" and "py3"
subdirectories.
"""


def get_int():
    return 1


def get_long():
    from past.types import long

    return long("1")


def get_unicode():
    return u"привет"


def get_bytes():
    return b"foo"


def get_past_unicode():
    from past.types import unicode

    return unicode(u"привет")


def get_old_object():
    from pickle_compat.examples import OldClass

    return OldClass(u"foo", u"bar")


def get_new_object():
    from pickle_compat.examples import NewClass

    return NewClass(u"foo", u"bar")


def get_datetime_object():
    from datetime import datetime

    return datetime.utcnow()


def get_dict_instance():
    return {u"foo": 1}


def get_namedtuple():
    from pickle_compat.examples import Foo

    return Foo(u"a", u"b")


def get_dict_subclass():
    from pickle_compat.examples import DictSubclass

    return DictSubclass({u"foo": 1})


test_functions = {k[4:]: v for k, v in locals().items() if k.startswith("get_")}

# Highest version of the protocol, understood by Python2.
PICKLE_PY2_COMPAT_PROTO = 2


def run():
    import os
    import pickle
    import sys

    root = os.path.dirname(__file__)
    directory = os.path.join(root, "fixtures", "py{}".format(sys.version_info.major))
    for name, function in test_functions.items():
        filename = "{}/{}.pickle".format(directory, name)
        with open(filename, "wb") as fd:
            pickle.dump(function(), fd, PICKLE_PY2_COMPAT_PROTO)


run()
