# pickle-compat

Python 2/3 compatibility layer for Pickle

## TL;DR

To make your pickle forward- and backward-compatible between Python versions, use this:

```
pip install pickle-compat
```

Then monkey-patch your pickle library with this:

```python
import pickle_compat

pickle_compat.patch()
```

From this point you can safely assume that what's pickled with `pickle.dumps()` in Python 2 can be converted back to the real object in Python 3 with `pickle.loads()`, and vise versa. Note however that it doesn't play well with cPickle, future.moves.pickle or six.moves.cPickle, you need to use plain "import pickle" instead.

If you want to roll back the patch, use:

```
pickle_compat.unpatch()
```

## Problem Statement

You were always aware of how pickle is unsafe, hard to debug, and how backward-incompatibility issues may bite you if you decide to update the version. You also heard that you should never use the pickle in a multi-language environment because it's Python-specific.

You knew it all, but you considered it "good enough" for your case. You worked on a monolith application, and pickle provides a serialization mechanism that works out of the box for anything you can create from your Python code.

Until came the time to migrate to Python 3. Anxious, you postponed it for your big legacy app for as long as you could, but there's no way you can delay it even further. This was when you realized that Python 2 and Python 3 are not two versions of the same language, but actually **two different languages** which happen to share some code constructs.

OK, now all of a sudden, you came up with a multi-language environment, where you need to read the pickle content, serialized by Python 2, from your code in Python 3. If you're making gradual migration, the opposite is also true.

## First frustrations

Things work out of the box only for simplest cases.

```bash
$ python2 -c 'import pickle; print pickle.dumps("Hello world")' | python3 -c 'import pickle, sys; print(repr(pickle.load(sys.stdin.buffer)))'
'Hello world'
```

All of a sudden, things start to get broken in the most unexpected places. For example, Python 3 fails to unpickle Python 2's datetime, spitting the scariest issue of any Python developer, a UnicodeDecodeError.

```bash
$ python2 -c 'import pickle, datetime; print pickle.dumps(datetime.datetime.utcnow())' | python3 -c 'import pickle, sys; print(repr(pickle.load(sys.stdin.buffer)))'
Traceback (most recent call last):
  File "<string>", line 1, in <module>
UnicodeDecodeError: 'ascii' codec can't decode byte 0xe4 in position 1: ordinal not in range(128)
```

Let's follow the rabbit to learn a bit more about the pickle, just enough to make it work for Python 2 and Python 3. At this point, I'm not sure how to make a smooth transition from where you are to where I wanted us to be, so I start throwing random facts at you in the hope that they build a more or less consistent picture in your head.

## Protocol versions

Pickle has several so-called "protocols," or formats in which the file can be written. You can optionally define the protocol version in the `pickle.dumps()`. The default format in Python 2.7 is 0 (also known as ASCII format), but it can read and write in the formats 1 and 2 as well. Formats 1 and 2 are not ASCII-safe, but they are more compact and faster.

```python
>>> pickle.dumps("hello")
"S'hello'\np0\n."
>>> pickle.dumps("hello", protocol=1)
'U\x05helloq\x00.'
>>> pickle.dumps("hello", protocol=2)
'\x80\x02U\x05helloq\x00.'
```

In Python 3, Guido introduced a new version of the protocol, intentionally make it backward-incompatible with Python 2.7. [See the commit](https://github.com/python/cpython/commit/f41698169198b32eecd60337a9437ea8c1714380). The comment around the `DEFAULT_PROTOCOL` constant warns, "We intentionally write a protocol that Python 2.x cannot read; there are too many issues with that."

The main takeaway from us is that if we want to have a backward- and forward-compatible code, we can only use protocols that both Python 2 and Python 3 understand: from 0 to 2 inclusive.

## Pickle format and pickletools

Module [pickletools](https://github.com/python/cpython/blob/master/Lib/pickletools.py) calls itself an "Executable documentation" for the pickle module. I highly recommend we open the source code and read an extensive introduction, starting with the words "A pickle is a program for a virtual pickle machine." Another useful feature of pickletools is that it provides a readable representation of the pickle stack.

```python
$ python2
>>> import pickle, pickletools
>>> pickletools.dis(pickle.dumps("hello"))
    0: S    STRING     'hello'
    9: p    PUT        0
   12: .    STOP
highest protocol among opcodes = 0
```

Here the main takeaway is that data in a pickle are represented in the format of the "opcode - data," where opcode decides, roughly speaking, the type of the following element. The list of opcodes is quite extensive and is always growing. You can find them [here](https://github.com/python/cpython/blob/5eb45d7d4e812e89d77da84cc619e9db81561a34/Lib/pickle.py#L107-L195)

## Strings and bytes

Let's find out how text and bytes are represented in Python 2 and Python 3, and what are the differences between then. We'll use Pickle version 2 for comparison. There's no surprise that Python 2 encodes strings and bytes as `BINSTRING` and Unicode objects as `BINUNICODE`.

```python
$ python2
>>> import pickle, pickletools
>>> pickletools.dis(pickle.dumps("foo", protocol=2))
    0: \x80 PROTO      2
    2: U    SHORT_BINSTRING 'foo'
    7: q    BINPUT     0
    9: .    STOP
highest protocol among opcodes = 2
>>> pickletools.dis(pickle.dumps(b"foo", protocol=2))
    0: \x80 PROTO      2
    2: U    SHORT_BINSTRING 'foo'
    7: q    BINPUT     0
    9: .    STOP
highest protocol among opcodes = 2
>>> pickletools.dis(pickle.dumps(u"foo", protocol=2))
    0: \x80 PROTO      2
    2: X    BINUNICODE u'foo'
   10: q    BINPUT     0
   12: .    STOP
highest protocol among opcodes = 2
```

On the contrary, Python 3 doesn't want to deal with "strings" as the name is ambiguous, and prefers to deal with `BINBYTES` and `BINUNICODE`. I will show how it's encoded in the protocol 3 that doesn't mean to be compatible with Python 2.

```python
$ python3
>>> import pickle, pickletools
>>> pickletools.dis(pickle.dumps(b"foo", protocol=3))
    0: \x80 PROTO      3
    2: C    SHORT_BINBYTES b'foo'
    7: q    BINPUT     0
    9: .    STOP
highest protocol among opcodes = 3
>>> pickletools.dis(pickle.dumps(u"foo", protocol=3))
    0: \x80 PROTO      3
    2: X    BINUNICODE 'foo'
   10: q    BINPUT     0
   12: .    STOP
highest protocol among opcodes = 2
```

Here come two questions:

- How Python 3 encode bytes in the protocol 2? Note that the second protocol knows nothing about `BINBYTES`?
- How Python 3 decodes the `BINSTRING` type, provided that it's a Python 2 type, and it's ambiguous?

Answering the first question is easy. The pickler introduces a backward-compatible hack.

```python
$ python3
>>> pickletools.dis(pickle.dumps(b'foo', protocol=2))
    0: \x80 PROTO      2
    2: c    GLOBAL     '_codecs encode'
   18: q    BINPUT     0
   20: X    BINUNICODE 'foo'
   28: q    BINPUT     1
   30: X    BINUNICODE 'latin1'
   41: q    BINPUT     2
   43: \x86 TUPLE2
   44: q    BINPUT     3
   46: R    REDUCE
   47: q    BINPUT     4
   49: .    STOP
highest protocol among opcodes = 2
```

Converting back to Python, it saves the byte sequence to a Unicode object, puts it to the stack, and tells the unpickler to execute the following command:

```python
import _codecs
_codecs.encode(u"foo", "latin1")
```

A side note. I did not know, but apparently, you can convert safely to Unicode and back any byte sequence.

```python
$ python3
>>> import os
>>> s = os.urandom(100000)
>>> s == s.decode('latin1').encode('latin1')
True
```

It also works for Python 2, so we shouldn't care much about the backward compatibility.

Now, how Python 3 decodes `BINSTRING` opcodes? From the first example, we can see that a string in Python 2 is now a Unicode object in Python 3. In other words, the pickler tries to convert bytes to Unicode.

```bash
$ python2 -c 'import pickle; print pickle.dumps("Hello world")' | python3 -c 'import pickle, sys; print(repr(pickle.load(sys.stdin.buffer)))'
'Hello world'
```

At this point, you probably ask yourself what encoding does it use? Fortunately, the answer is right there, in [the documentation](https://docs.python.org/3/library/pickle.html#pickle.Unpickler). Python 3 introduced a parameter "encoding" that defaults to ASCII.

> The encoding and errors tell pickle how to decode 8-bit string instances pickled by Python 2; these default to ‘ASCII’ and ‘strict’, respectively. The encoding can be ‘bytes’ to read these 8-bit string instances as bytes objects. Using encoding='latin1' is required for unpickling NumPy arrays and instances of datetime, date and time pickled by Python 2.

If you wonder what's wrong with datetime, here's how its output looks like in Python 2.

```python
$ python2

>>> import pickle, pickletools, datetime
>>> pickletools.dis(pickle.dumps(datetime.datetime.utcnow(), protocol=2))
    0: \x80 PROTO      2
    2: c    GLOBAL     'datetime datetime'
   21: q    BINPUT     0
   23: U    SHORT_BINSTRING '\x07\xe4\x05\x1a\x0f\x01\x16\x00\x96\x10'
   35: q    BINPUT     1
   37: \x85 TUPLE1
   38: q    BINPUT     2
   40: R    REDUCE
   41: q    BINPUT     3
   43: .    STOP
highest protocol among opcodes = 2
```

Here comes yet another surprise for me: datetime constructor can accept a byte sequence to initialize its internal state, and pickle takes advantage of this.

```python2
>>> import datetime
>>> datetime.datetime(b'\x07\xe4\x05\x1a\x0f\x01\x16\x00\x96\x10')
datetime.datetime(2020, 5, 26, 15, 1, 22, 38416)
```

Setting the encoding to "latin1" seems to work.

```bash
python2 -c 'import pickle, datetime; print pickle.dumps(datetime.datetime.utcnow())' | python3 -c 'import pickle, sys; print(repr(pickle.load(sys.stdin.buffer, encoding="latin1")))'
datetime.datetime(2020, 5, 26, 15, 19, 6, 275120)
```

The main takeaway is that strings in Python 2 are converted to Unicode objects in Python 3, and you can control the encoding.

## Non-latin strings in Python 2

What if you have a non-ASCII content, represented as an old string and not a Unicode object? If you pickle it in Python 2 and unpickle it back in Python 3, you are in trouble.

The byte string doesn't have any information about the encoding. In Python 2, you probably implicitly supposed that it's a UTF-8, but when you convert it back to Python 3 with Unpickle, it appears as encoded with latin1.

```bash
python2 -c 'import pickle; print pickle.dumps("©")' | python3 -c 'import pickle, sys; print(repr(pickle.load(sys.stdin.buffer, encoding="latin1")))'
'Â©'
```

To workaround, you need to use UTF-8, which will work for this case.

```bash
python2 -c 'import pickle; print pickle.dumps("©")' | python3 -c 'import pickle, sys; print(repr(pickle.load(sys.stdin.buffer, encoding="utf8")))'
'©'
```

Unfortunately, it will not work for datetimes and other binary strings that don't represent a valid UTF-8 sequence.

## Unpickling with "bytes" encoding

Well, we were so close to the victory, and we're back to square one. What we're going to do? Fortunately, there's a documented escape hatch, the "bytes" encoding. This encoding looks precisely the way we need it. It doesn't try to outsmart you and convert bytes to something that looks like a string. Instead, it returns bytes as bytes objects. Even better than "latin1"!

```bash
python2 -c 'import pickle; print pickle.dumps("©")' | python3 -c 'import pickle, sys; print(repr(pickle.load(sys.stdin.buffer, encoding="bytes")))'
b'\xc2\xa9'
```

Datetime objects also work. Is this a victory? Not so fast.

## Unpickling with "bytes" encoding. The string constants

I never bothered annotating my string constants that play the role of the "string constants" with a `u""` prefix. It's ugly and redundant, and in most cases, when my strings don't contain any non-ASCII symbols, the migration works just fine.

It's not the case, though, when pickle comes into play. For example, consider the function which takes two arguments and an operation name as a string:

```python
def apply_operation(a, b, op):
    if op == "ADD":
        return a + b
    elif op == "SUB":
        return a - b
    else:
        raise ValueError("Unknown operation")
```

Somewhere else, I let the `op` pass through the pickle-unpickle pipeline so that Python 2 would convert it to a binary string, and Python 3 would unpickle it exactly as is. In my case, this could be a caching library or a queue processor. Now, I pass my `op` as a binary object to the function, and because `"ADD" != b"ADD"`, it will always fail with an "Unknown operation" exception.

The most common bytes vs. Unicode problems look like these. Case one:

```python
>>> "foo" == b"foo"
False
```

Case two:

```python
>>> {"key": "value"}[b"key"]
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
KeyError: b'key'
```

One solution is to make all string constants behave like Unicode objects. You can convert them explicitly from `""` to `u""` or add `from __future__ import unicode_literals`. Both solutions don't look quite elegant. Fortunately, when you finally migrate to Python 3, you can delete both of them, and you can do this automatically. I prefer the "future" solution because it generates a smaller diff.

```bash
futurize --stage1 --unicode-literals --write --nobackups path/to/code
```

## Unpickling with "bytes" encoding. Objects with attributes

It is, by far, not the worst case. To make things even more complicated let's try to serialize `foo.foo`.

```python
# file: foo.py

class Foo(object):
    a = 'UNSET'
    b = 'UNSET'
    def __init__(self):
        self.a = 1
        self.b = 2
    def __repr__(self):
        return 'Foo(%s, %s)' % (self.a, self.b)

foo = Foo()
```

As long as we use the default settings, we're good.

```bash
$ python2 -c 'import pickle, foo; print pickle.dumps(foo.foo)' | python3 -c 'import pickle, sys; print(repr(pickle.load(sys.stdin.buffer)))'

Foo(1, 2)
```

But if we pass "bytes" as an argument, all of a sudden something goes wrong.

```bash
python2 -c 'import pickle, foo; print pickle.dumps(foo.foo)' | python3 -c 'import pickle, sys; print(repr(pickle.load(sys.stdin.buffer, encoding="bytes")))'

Foo(UNSET, UNSET)
```

We lost the attributes of `a` and `b`. Where do they go? The same `pickletool.dis()` helps us to find the answer:

```python

$ python2
>>> import pickle, pickletools, foo
>>> pickletools.dis(pickle.dumps(foo.foo, protocol=2))
    0: \x80 PROTO      2
    2: c    GLOBAL     'foo Foo'
   11: q    BINPUT     0
   13: )    EMPTY_TUPLE
   14: \x81 NEWOBJ
   15: q    BINPUT     1
   17: }    EMPTY_DICT
   18: q    BINPUT     2
   20: (    MARK
   21: U        SHORT_BINSTRING 'a'
   24: q        BINPUT     3
   26: K        BININT1    1
   28: U        SHORT_BINSTRING 'b'
   31: q        BINPUT     4
   33: K        BININT1    2
   35: u        SETITEMS   (MARK at 20)
   36: b    BUILD
   37: .    STOP
highest protocol among opcodes = 2
```

The pickle loader doesn't call `__init__`. Instead, it creates a new empty "dummy" object of the class `Foo` and populates its state by updating the `__dict__`. If this would be Python, we could write it like this:

```python
obj = object.__new__(foo.Foo)
obj.__dict__ = {"a": 1, "b": 2}
```

I think now you understand what went wrong. Because of the `bytes` encoding, we did not convert b"a" and b"b" to their "python3-string" representations. You can put anything to object's dict, but only the keys that are strings are represented as "proper object attributes."

The next command shows the contents of the `__dict__` of an object and proves that we were right?

```bash
python2 -c 'import pickle, foo; print pickle.dumps(foo.foo)' | python3 -c 'import pickle, sys; print(pickle.load(sys.stdin.buffer, encoding="bytes").__dict__)'

{b'a': 1, b'b': 2}
```

OK, we can't use `ASCII`, `latin1`, `utf8` as an encoding, and now we learned that we couldn't use `bytes`? It looks like a dead-end. Or you can get to your last resort, dirty and evil, monkey-patching. The previous version of the pickle-compat used this approach, but we eventually decided to get away without it in favor of "latin1", due to way too many corner cases.

## Get back to unpickling with "latin1" encoding. Be careful with non-ASCII strings

So, as we learned, the only practical unpickling option is to automatically decode Python 2 str to Python 3 str using "latin1" as an encoding. As we discussed earlier, though, we need to be very careful with byte strings implicitly encoded with UTF-8. I will only provide some examples where you can accidentally come across them. This way or another, you need to fix everything outlined below, regardless of whether you plan to deal with Pickle cases, or not.

### Code

This returns an str:

```python
# coding: utf-8

copy = "©"
```

Use this instead:

```python
# coding: utf-8
from __future__ import unicode_literals

copy = "©"
```

### Files

This returns an str:

```python
open('test.txt').read()
```

Use the variant that returns unicode and works correctly in Python 2 and Python 3:

```python
import io
io.open('test.txt', 'rt', encoding='utf8').read()
```

### Redis

This returns an str:

```python
redis.Redis().get("foo")
```

Use `decode_responses` instead:

```python
redis.Redis(decode_responses=True).get("foo")
```

### CSV reader

This returns str objects:

```python
>>> import csv
>>> list(csv.reader(open("foo.csv")))
[['a', 'b'], ['c', 'd']]
```

Install [backports.csv](https://pypi.org/project/backports.csv/) and open files in text modes instead:

```python
>>> from backports import csv
>>> import io
>>> list(csv.reader(io.open("foo.csv", "rt", encoding="utf8")))
[[u'a', u'b'], [u'c', u'd']]
```

### Requests

This returns an str:

```python
requests.get("https://example.com").content
```

Use the variant that returns unicode:

```python
requests.get("https://example.com").text
```

## Old-style classes

We are almost there, except for one thing: old-style classes. As you know, in Python 3, everything subclasses objects, while in Python 2, unless you explicitly inherit your class from it, the top-level class will be "type". It is considered outdated, but it's still used in different places of the standard library, waiting to ruin your life in the most unexpected moment.

This time we talk about forward-compatibility and want to make sure that anything that is pickled in Python 3 can be successfully unpicked in Python 2.

Let's take an object that is an old-style class in Python 2.

```bash
python3 -c 'import pickle, smtplib, sys; sys.stdout.buffer.write(pickle.dumps(smtplib.SMTP(), protocol=2))' | python2 -c 'import pickle, sys; print pickle.load(sys.stdin)'

Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "2.7.15/lib/python2.7/pickle.py", line 1384, in load
    return Unpickler(file).load()
  File "2.7.15/lib/python2.7/pickle.py", line 864, in load
    dispatch[key](self)
  File "2.7.15/lib/python2.7/pickle.py", line 1089, in load_newobj
    obj = cls.__new__(cls, *args)
AttributeError: class SMTP has no attribute '__new__'
```

The approach is similar to the old one: find out how unpickler loads new objects and then patch it to see if the class is old. The Python 2 implementation lives [here](https://github.com/python/cpython/blob/8d21aa21f2cbc6d50aab3f420bb23be1d081dac4/Lib/pickle.py#L1086-L1091).

Note that the protocol version 0 doesn't contain a NEWOBJ opcode and uses a set of workarounds to make it work, so this approach will only work for version 2 of the protocol.

## cPickle, future and six moves

Here is a word of warning. The patcher doesn't fix cPickle of Python 2 and \_pickle of Python 3. The latter is an undocumented module imported by Python 3's pickle, if possible.

The way we solved the problem for ourselves at Doist is by importing "pickle" everywhere. It works slower on Python 2, but that only serves as an extra incentive to finish the migration faster. You can use [futurize](https://python-future.org/futurize.html) from the "future" package to make it automatically, and it will convert all occurrences of `import cPickle` to `import pickle.`

If you chose a different strategy of migration, with "moves," this can become cumbersome because you can import cPickle unknowingly. More specifically, this will import cPickle implementation under the hood:

```
from future.moves import pickle
```

The same goes for this:

```
from six.moves import cPickle
```

The main takeaway is that this patcher will not as expected if you use cPickle, future.moves.pickle or six.moves.cPickle.

## Putting it all together

What we learned

- The default version of the protocol has to be 2, both for Python 2 and Python 3.
- We must use the "latin1" encoding in the pickle for Python 3.
- We must be careful with plain strings, represented non-ASCII objects.
- We must patch Unpickler in Python 2 to correctly unpickle instances of old-style classes.

Also, we learned some of the internals of pickle and learned how to use pickletools. Finally, we wrapped everything with a `pickle_compat` library that monkey-patches the standard pickle module.
