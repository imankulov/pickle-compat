# coding: utf-8
import io
import os
import pickle

import pytest

from pickle_compat import patch, unpatch


@pytest.fixture(autouse=True)
def _patch():
    patch()
    yield
    unpatch()


@pytest.fixture(params=["py2", "py3"])
@pytest.mark.parametrize("python_version",)
def get_fixture(request):
    python_version = request.param

    def getter(name):
        """Read two fixture from the file by its name, and return bytes."""
        root = os.path.join(os.path.dirname(__file__), "fixtures")
        filename = os.path.join(root, python_version, "{}.pickle".format(name))
        with io.open(filename, "rb") as fd:
            return fd.read()

        return filename

    return getter


def test_dumps_with_protocol():
    assert pickle.dumps("foo", 1)


def test_int(get_fixture):
    assert pickle.loads(get_fixture("int")) == 1


def test_long(get_fixture):
    assert pickle.loads(get_fixture("long")) == 1


def test_unicode(get_fixture):
    assert pickle.loads(get_fixture("unicode")) == u"привет"


def test_bytes(get_fixture):
    assert pickle.loads(get_fixture("bytes")) == b"foo"


def test_past_unicode(get_fixture):
    assert pickle.loads(get_fixture("past_unicode")) == u"привет"


def test_old_object(get_fixture):
    assert pickle.loads(get_fixture("old_object")).a == u"foo"


def test_new_object(get_fixture):
    assert pickle.loads(get_fixture("new_object")).a == u"foo"


def test_datetime_object(get_fixture):
    assert pickle.loads(get_fixture("datetime_object")).year == 2020


def test_dict_instance(get_fixture):
    assert pickle.loads(get_fixture("dict_instance")) == {u"foo": 1}


def test_namedtuple(get_fixture):
    assert pickle.loads(get_fixture("namedtuple")).a == u"a"


def test_dict_subclass(get_fixture):
    assert pickle.loads(get_fixture("dict_subclass")) == {u"foo": 1}
