import sys

DEFAULT_PROTOCOL = 2
DEFAULT_ENCODING = "latin1"

if sys.version_info.major == 3:
    # Helper functions and classes to make pickle backward-compatible with python2
    # pickles, covering as many cases as we know.
    import pickle
    from functools import partial

    # Backward-compatible load and loads, that use "latin1" as a default encoding.
    compat_load = partial(pickle._load, encoding=DEFAULT_ENCODING)  # type: ignore
    compat_loads = partial(pickle._loads, encoding=DEFAULT_ENCODING)  # type: ignore

    # Backward-compatible dump and dumps, that use the second version of the protocol.
    def compat_dump(obj, file, protocol=None, fix_imports=True, **kwargs):
        return pickle._dump(
            obj, file, protocol=DEFAULT_PROTOCOL, fix_imports=fix_imports, **kwargs
        )

    def compat_dumps(obj, protocol=None, fix_imports=True, **kwargs):
        return pickle._dumps(
            obj, protocol=DEFAULT_PROTOCOL, fix_imports=fix_imports, **kwargs
        )

    # Backward-compatible versions of functions and classes
    compat = {
        "Unpickler": pickle.Unpickler,
        "load": compat_load,
        "loads": compat_loads,
        "dump": compat_dump,
        "dumps": compat_dumps,
    }

else:
    import pickle

    import new

    # Vanilla implementation of the objects that we overwrite.
    VanillaUnpickler = pickle.Unpickler
    vanilla_dump = pickle.dump
    vanilla_dumps = pickle.dumps

    # Here's our unicker that knows how to process old classes.
    class CompatUnpickler(VanillaUnpickler):
        def load_newobj(self):
            cls = self.stack[-2]
            if type(cls) == new.classobj:
                self.stack.pop()  # args
                cls = self.stack.pop()
                obj = new.instance(cls)
                self.append(obj)
            else:
                VanillaUnpickler.load_newobj(self)

    # We also need to explicitly register our own handler in the dispatcher, because
    # otherwise a method of the superclass will be called
    CompatUnpickler.dispatch[  # type: ignore
        pickle.NEWOBJ
    ] = CompatUnpickler.load_newobj

    # Forward-compatible load and loads, nothing is needed to be patched
    compat_load = pickle.load  # type: ignore
    compat_loads = pickle.loads  # type: ignore

    # Forward-compatible dump and dumps, that use the second version of the protocol.
    def compat_dump(obj, file, protocol=None):  # type: ignore
        return vanilla_dump(obj, file, protocol=DEFAULT_PROTOCOL)

    def compat_dumps(obj, protocol=None):  # type: ignore
        return vanilla_dumps(obj, protocol=DEFAULT_PROTOCOL)

    # Backward-compatible versions of functions and classes
    compat = {
        "Unpickler": CompatUnpickler,
        "load": compat_load,
        "loads": compat_loads,
        "dump": compat_dump,
        "dumps": compat_dumps,
    }

patched = False
orig = {
    "Unpickler": None,
    "load": None,
    "loads": None,
    "dump": None,
    "dumps": None,
}


def patch():
    """Replace Unpickler, load and loads with backward-compatible versions."""
    global patched, orig
    if patched:
        return

    for key, value in compat.items():
        orig[key] = getattr(pickle, key)
        setattr(pickle, key, value)

    patched = True


def unpatch():
    """Remove backward-compatible implementations."""
    global patched, orig
    if not patched:
        return

    for key, value in orig.items():
        setattr(pickle, key, value)

    patched = False
