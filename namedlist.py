#######################################################################
# Similar to namedtuple, but supports default values and is writable.
#
# Copyright 2011-2014 True Blade Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Notes:
#  See http://code.activestate.com/recipes/576555/ for a similar
# concept.
#
#  When moving to a newer version of unittest, check that the exceptions
# being caught have the expected text in them.
#
########################################################################

__all__ = ['namedlist', 'NO_DEFAULT', 'FACTORY']

# All of this hassle with ast is solely to provide a decent __init__
#  function, that takes all of the right arguments and defaults. But
#  it's worth it to get all of the normal python error messages.
# For other functions, like __repr__, we don't bother. __init__ is
#  the only function where we really need the argument processing,
#  because __init__ is the only function whose signature will vary
#  per class.

import ast as _ast
import sys as _sys
from keyword import iskeyword as _iskeyword
import collections as _collections
import abc as _abc

_PY2 = _sys.version_info[0] == 2
_PY3 = _sys.version_info[0] == 3

if _PY2:
    _basestring = basestring
else:
    _basestring = str


NO_DEFAULT = object()

# Wrapper around a callable. Used to specify a factory function instead
#  of a plain default value.
class FACTORY(object):
    def __init__(self, callable):
        self._callable = callable

    def __call__(self):
        return self._callable()


########################################################################
# Keep track of fields, both with and without defaults.
class _Fields(object):
    default_not_specified = object()

    def __init__(self, default):
        self.default = default
        self.with_defaults = []        # List of (field_name, default).
        self.without_defaults = []     # List of field_name.

    def add(self, field_name, default):
        if default is self.default_not_specified:
            if self.default is NO_DEFAULT:
                # No default. There can't be any defaults already specified.
                if len(self.with_defaults) != 0:
                    raise ValueError('field {0} without a default follows fields '
                                     'with defaults'.format(field_name))
                self.without_defaults.append(field_name)
            else:
                self.add(field_name, self.default)
        else:
            if default is NO_DEFAULT:
                self.add(field_name, self.default_not_specified)
            else:
                self.with_defaults.append((field_name, default))


########################################################################
# Validate and possibly sanitize the field and type names.
class _NameChecker(object):
    def __init__(self, typename):
        self.seen_fields = set()
        self._check_common(typename, 'Type')

    def check_field_name(self, fieldname, rename, idx):
        try:
            self._check_common(fieldname, 'Field')
            self._check_specific_to_fields(fieldname)
        except ValueError as ex:
            if rename:
                return '_' + str(idx)
            else:
                raise

        self.seen_fields.add(fieldname)
        return fieldname

    def _check_common(self, name, type_of_name):
        # tests that are common to both field names and the type name
        if len(name) == 0:
            raise ValueError('{0} names cannot be zero '
                             'length: {1!r}'.format(type_of_name, name))
        if _PY2:
            if not all(c.isalnum() or c=='_' for c in name):
                raise ValueError('{0} names can only contain '
                                 'alphanumeric characters and underscores: '
                                 '{1!r}'.format(type_of_name, name))
            if name[0].isdigit():
                raise ValueError('{0} names cannot start with a '
                                 'number: {1!r}'.format(type_of_name, name))
        else:
            if not name.isidentifier():
                raise ValueError('{0} names names must be valid '
                                 'identifiers: {1!r}'.format(type_of_name, name))
        if _iskeyword(name):
            raise ValueError('{0} names cannot be a keyword: '
                             '{1!r}'.format(type_of_name, name))

    def _check_specific_to_fields(self, name):
        # these tests don't apply for the typename, just the fieldnames
        if name in self.seen_fields:
            raise ValueError('Encountered duplicate field name: '
                             '{0!r}'.format(name))

        if name.startswith('_'):
            raise ValueError('Field names cannot start with an underscore: '
                             '{0!r}'.format(name))


########################################################################
# Member functions for the generated class.

def _repr(self):
    return '{0}({1})'.format(self.__class__.__name__, ', '.join('{0}={1!r}'.format(name, getattr(self, name)) for name in self._fields))

def _eq(self, other):
    return isinstance(other, self.__class__) and all(getattr(self, name) == getattr(other, name) for name in self._fields)

def _ne(self, other):
    return not _eq(self, other)

def _len(self):
    return len(self._fields)

def _asdict(self):
    return {fieldname: getattr(self, fieldname) for fieldname in self._fields}

def _getstate(self):
    return tuple(getattr(self, fieldname) for fieldname in self._fields)

def _setstate(self, state):
    for fieldname, value in zip(self._fields, state):
        setattr(self, fieldname, value)

def _getitem(self, idx):
    return getattr(self, self._fields[idx])

def _setitem(self, idx, value):
    return setattr(self, self._fields[idx], value)

def _iter(self):
    return (getattr(self, fieldname) for fieldname in self._fields)

def _count(self, value):
    return sum(1 for v in iter(self) if v == value)

def _index(self, value, start=NO_DEFAULT, stop=NO_DEFAULT):
    # not the most efficient way to implement this, but it will work
    l = list(self)
    if start is NO_DEFAULT and stop is NO_DEFAULT:
        return l.index(value)
    if stop is NO_DEFAULT:
        return l.index(value, start)
    return l.index(value, start, stop)

########################################################################
# The function that __init__ calls to do the actual work.

def _init(self, *args):
    # sets all of the fields to their passed in values
    assert len(args) == len(self._fields)
    for fieldname, value in zip(self._fields, args):
        if isinstance(value, FACTORY):
            # instead of using the default value, it's really a
            #  factory function: call it
            value = value()
        setattr(self, fieldname, value)


########################################################################
# Returns a function with name 'name', that calls another function 'chain_fn'
# This is used to create the __init__ function with the right argument names and defaults, that
#  calls into _init to do the real work.
# The new function takes args as arguments, with defaults as given.
def _make_fn(name, chain_fn, args, defaults):
    args_with_self = ['self'] + list(args)
    arguments = [_ast.Name(id=arg, ctx=_ast.Load()) for arg in args_with_self]
    defs = [_ast.Name(id='_def{0}'.format(idx), ctx=_ast.Load()) for idx, _ in enumerate(defaults)]
    if _PY2:
        parameters = _ast.arguments(args=[_ast.Name(id=arg, ctx=_ast.Param()) for arg in args_with_self],
                                    defaults=defs)
    else:
        parameters = _ast.arguments(args=[_ast.arg(arg=arg) for arg in args_with_self],
                                    kwonlyargs=[],
                                    defaults=defs,
                                    kw_defaults=[])
    module_node = _ast.Module(body=[_ast.FunctionDef(name=name,
                                                     args=parameters,
                                                     body=[_ast.Return(value=_ast.Call(func=_ast.Name(id='_chain', ctx=_ast.Load()),
                                                                                       args=arguments,
                                                                                       keywords=[]))],
                                                     decorator_list=[])])
    module_node = _ast.fix_missing_locations(module_node)

    # compile the ast
    code = compile(module_node, '<string>', 'exec')

    # and eval it in the right context
    globals_ = {'_chain': chain_fn}
    locals_ = {'_def{0}'.format(idx): value for idx, value in enumerate(defaults)}
    eval(code, globals_, locals_)

    # extract our function from the newly created module
    return locals_[name]


########################################################################
# The actual namedlist factory function. Needs a docstring.
def namedlist(typename, field_names, default=NO_DEFAULT, rename=False,
              use_slots=True):
    # field_names must be a string or an iterable, consisting of fieldname
    #  strings or 2-tuples. Each 2-tuple is of the form (fieldname,
    #  default).

    # Keeps track of the fields we're adding, with their defaults.
    fields = _Fields(default)

    # Validates field and type names.
    name_checker = _NameChecker(typename)

    if isinstance(field_names, _basestring):
        # No per-field defaults. So it's like a namedtuple, but with
        #  a possible default value.
        field_names = field_names.replace(',', ' ').split()

    # If field_names is a Mapping, change it to return the
    #  (field_name, default) pairs, as if it were a list.
    if isinstance(field_names, _collections.Mapping):
        field_names = field_names.items()

    # Parse and validate the field names.

    # field_names is now an iterable. Walk through it,
    # sanitizing as needed, and add to fields.

    for idx, field_name in enumerate(field_names):
        if isinstance(field_name, _basestring):
            default = fields.default_not_specified
        else:
            try:
                if len(field_name) != 2:
                    raise ValueError('field_name must be a 2-tuple: '
                                     '{0!r}'.format(field_name))
            except TypeError:
                # field_name doesn't have a __len__.
                raise ValueError('field_name must be a 2-tuple: '
                                 '{0!r}'.format(field_name))
            default = field_name[1]
            field_name = field_name[0]

        # Okay: now we have the field_name and the default value (if any).
        # Validate the name, and add the field.
        fields.add(name_checker.check_field_name(field_name, rename, idx), default)

    all_field_names = tuple(fields.without_defaults + [name for name, default in
                                                       fields.with_defaults])
    defaults = [default for _, default in fields.with_defaults]

    type_dict = {'__init__': _make_fn('__init__', _init, all_field_names, defaults),
                 '__repr__': _repr,
                 '__eq__': _eq,
                 '__ne__': _ne,
                 '__len__': _len,
                 '__getstate__': _getstate,
                 '__setstate__': _setstate,
                 '__getitem__': _getitem,
                 '__setitem__': _setitem,
                 '__iter__': _iter,
                 '__hash__': None,
                 'count': _count,
                 'index': _index,
                 '_asdict': _asdict,
                 '_fields': all_field_names}

    if use_slots:
        type_dict['__slots__'] = all_field_names

    # Create the new type object.
    t = type(typename, (object,), type_dict)

    # Register its ABC's
    _collections.Sequence.register(t)

    # And return it.
    return t


if __name__ == '__main__':
    import unittest
    import unicodedata

    # test both pickle and cPickle in 2.x, but just pickle in 3.x
    import pickle
    try:
        import cPickle
        pickle_modules = (pickle, cPickle)
    except ImportError:
        pickle_modules = (pickle,)

    # types used for pickle tests
    TestRT0 = namedlist('TestRT0', '')
    TestRT = namedlist('TestRT', 'x y z')

    class TestNamedlist(unittest.TestCase):
        def test_simple(self):
            Point = namedlist('Point', 'x y')
            p = Point(10, 20)
            self.assertEqual((p.x, p.y), (10, 20))
            self.assertEqual(p._asdict(), {'x':10, 'y':20})

            Point = namedlist('Point', 'x,y')
            p = Point(10, 20)
            self.assertEqual((p.x, p.y), (10, 20))
            self.assertEqual(p._asdict(), {'x':10, 'y':20})

            Point = namedlist('Point', 'x, y')
            p = Point(10, 20)
            self.assertEqual((p.x, p.y), (10, 20))
            self.assertEqual(p._asdict(), {'x':10, 'y':20})

            Point = namedlist('Point', ['x', 'y'])
            p = Point(10, 20)
            self.assertEqual((p.x, p.y), (10, 20))
            self.assertEqual(p._asdict(), {'x':10, 'y':20})

            self.assertEqual(Point(10, 11), Point(10, 11))
            self.assertNotEqual(Point(10, 11), Point(10, 12))

        def test_bad_name(self):
            self.assertRaises(ValueError, namedlist, 'Point*', 'x y')
            self.assertRaises(ValueError, namedlist, 'Point', '# y')
            self.assertRaises(ValueError, namedlist, 'Point', 'x 1y')
            self.assertRaises(ValueError, namedlist, 'Point', 'x y x')
            self.assertRaises(ValueError, namedlist, 'Point', 'x y for')
            self.assertRaises(ValueError, namedlist, 'Point', '_field')
            self.assertRaises(ValueError, namedlist, 'Point', [('', 0)])
            self.assertRaises(ValueError, namedlist, '', 'x y')
            self.assertRaises(ValueError, namedlist, 'Point', unicodedata.lookup('SUPERSCRIPT ONE'))

        def test_bad_defaults(self):
            # if specifying the defaults, must provide a 2-tuple
            self.assertRaises(ValueError, namedlist, 'Point', [('x', 3, 4)])
            self.assertRaises(ValueError, namedlist, 'Point', [('x',)])
            self.assertRaises(ValueError, namedlist, 'Point', [3])

        def test_empty(self):
            Point = namedlist('Point', '')
            self.assertEqual(len(Point()), 0)
            self.assertEqual(list(Point()), [])
            self.assertEqual(Point(), Point())
            self.assertEqual(Point()._asdict(), {})

            Point = namedlist('Point', '', 10)
            self.assertEqual(len(Point()), 0)
            self.assertEqual(Point(), Point())
            self.assertEqual(Point()._asdict(), {})

            Point = namedlist('Point', [])
            self.assertEqual(len(Point()), 0)
            self.assertEqual(Point(), Point())
            self.assertEqual(Point()._asdict(), {})

            Point = namedlist('Point', [], 10)
            self.assertEqual(len(Point()), 0)
            self.assertEqual(Point(), Point())
            self.assertEqual(Point()._asdict(), {})

        def test_list(self):
            Point = namedlist('Point', ['x', 'y'])
            p = Point(10, 20)
            self.assertEqual((p.x, p.y), (10, 20))
            self.assertEqual(p._asdict(), {'x':10, 'y':20})

            Point = namedlist('Point', ('x', 'y'))
            p = Point(10, 20)
            self.assertEqual((p.x, p.y), (10, 20))
            self.assertEqual(p._asdict(), {'x':10, 'y':20})

        def test_default(self):
            Point = namedlist('Point', 'x y z', 100)
            self.assertEqual(Point(), Point(100, 100, 100))
            self.assertEqual(Point(10), Point(10, 100, 100))
            self.assertEqual(Point(10, 20), Point(10, 20, 100))
            self.assertEqual(Point(10, 20, 30), Point(10, 20, 30))
            self.assertEqual(Point()._asdict(), {'x':100, 'y':100, 'z':100})

        def test_default_list(self):
            Point = namedlist('Point', 'x y z'.split(), 100)
            self.assertEqual(Point(), Point(100, 100, 100))
            self.assertEqual(Point(10), Point(10, 100, 100))
            self.assertEqual(Point(10, 20), Point(10, 20, 100))
            self.assertEqual(Point(10, 20, 30), Point(10, 20, 30))
            self.assertEqual(Point()._asdict(), {'x':100, 'y':100, 'z':100})

        def test_default_and_specified_default(self):
            Point = namedlist('Point', ['x', ('y', 10), ('z', 20)], 100)
            self.assertEqual(Point(), Point(100, 10, 20))
            self.assertEqual(Point(0), Point(0, 10, 20))
            self.assertEqual(Point(0, 1), Point(0, 1, 20))
            self.assertEqual(Point(0, 1, 2), Point(0, 1, 2))

            # default doesn't just have to apply to the last field
            Point = namedlist('Point', [('x', 0), 'y', ('z', 20)], 100)
            self.assertEqual(Point(), Point(0, 100, 20))

        def test_equality_inequality(self):
            Point = namedlist('Point', ['x', ('y', 10), ('z', 20)], 100)
            p0 = Point()
            p1 = Point(0)
            self.assertEqual(p0, Point())
            self.assertEqual(p0, Point(100, 10, 20))
            self.assertEqual(p1, Point(0, 10))
            self.assertEqual(Point(), p0)
            self.assertEqual(p0, p0)
            self.assertNotEqual(p0, p1)
            self.assertNotEqual(p0, 3)
            self.assertNotEqual(p0, None)
            self.assertNotEqual(p0, object())
            self.assertNotEqual(p0, Point('100'))
            self.assertNotEqual(p0, Point(100, 10, 21))

        def test_default_order(self):
            # with no default, can't have a field without a
            #  default follow fields with defaults
            self.assertRaises(ValueError, namedlist, 'Point',
                              ['x', ('y', 10), 'z'])

            # but with a default, you can
            Point = namedlist('Point', ['x', ('y', 10), 'z'], -1)
            self.assertEqual(Point(0), Point(0, 10, -1))
            self.assertEqual(Point(z=0), Point(-1, 10, 0))

        def test_repr(self):
            Point = namedlist('Point', 'x y z')
            p = Point(1, 2, 3)
            self.assertEqual(repr(p), 'Point(x=1, y=2, z=3)')
            self.assertEqual(str(p), 'Point(x=1, y=2, z=3)')

        def test_missing_argument(self):
            Point = namedlist('Point', ['x', 'y', ('z', 10)])
            self.assertEqual(Point(1, 2), Point(1, 2, 10))
            self.assertRaises(TypeError, Point, 1)

        def test_identity_of_defaults(self):
            default = object()
            Point = namedlist('Point', [('x', default)])
            # in 2.7 this should become assertIs
            self.assertTrue(Point().x is default)

            Point = namedlist('Point', 'x', default)
            # in 2.7 this should become assertIs
            self.assertTrue(Point().x is default)

        def test_writable(self):
            Point = namedlist('Point', ['x', ('y', 10), ('z', 20)], 100)
            p = Point(0)
            self.assertEqual((p.x, p.y, p.z), (0, 10, 20))
            p.x = -1
            self.assertEqual((p.x, p.y, p.z), (-1, 10, 20))
            p.y = -1
            self.assertEqual((p.x, p.y, p.z), (-1, -1, 20))
            p.z = None
            self.assertEqual((p.x, p.y, p.z), (-1, -1, None))

        def test_complex_defaults(self):
            Point = namedlist('Point', ['x', ('y', 10), ('z', 20)],
                               [1, 2, 3])
            p = Point()
            self.assertEqual((p.x, p.y, p.z), ([1, 2, 3], 10, 20))

            Point = namedlist('Point', [('x', [4, 5, 6]),
                                         ('y', 10),
                                         ('z', 20)])
            p = Point()
            self.assertEqual((p.x, p.y, p.z), ([4, 5, 6], 10, 20))

        def test_iteration(self):
            Point = namedlist('Point', ['x', ('y', 10), ('z', 20)],
                               [1, 2, 3])
            p = Point()
            self.assertEqual(len(p), 3)

            self.assertEqual(list(iter(p)), [[1, 2, 3], 10, 20])

            for expected, found in zip([[1, 2, 3], 10, 20], p):
                self.assertEqual(expected, found)

        def test_fields(self):
            Point = namedlist('Point', 'x y z')
            self.assertEqual(Point._fields, ('x', 'y', 'z'))

            Point = namedlist('Point', 'x y z', 100)
            self.assertEqual(Point._fields, ('x', 'y', 'z'))

            Point = namedlist('Point', [('x', 0), ('y', 0), ('z', 0)])
            self.assertEqual(Point._fields, ('x', 'y', 'z'))

        def test_pickle(self):
            for p in (TestRT0(), TestRT(x=10, y=20, z=30)):
                for module in pickle_modules:
                    loads = getattr(module, 'loads')
                    dumps = getattr(module, 'dumps')
                    for protocol in -1, 0, 1, 2:
                        q = loads(dumps(p, protocol))
                        self.assertEqual(p, q)
                        self.assertEqual(p._fields, q._fields)

        def test_type_has_same_name_as_field(self):
            Point = namedlist('Point',
                               ['Point', ('y', 10), ('z', 20)],
                               [1, 2, 3])
            p = Point()
            self.assertEqual(len(p), 3)
            self.assertEqual(p.Point, [1, 2, 3])

            Point = namedlist('Point', 'Point')
            p = Point(4)
            self.assertEqual(p.Point, 4)

            Point = namedlist('Point', 'x Point')
            p = Point(3, 4)
            self.assertEqual(p.Point, 4)

        def test_slots(self):
            Point = namedlist('Point', '')
            p = Point()
            # p.x = 3 raises AttributeError because of slots
            self.assertRaises(AttributeError, setattr, p, 'x', 3)

            Point = namedlist('Point', '', use_slots=True)
            p = Point()
            # p.x = 3 raises AttributeError because of slots
            self.assertRaises(AttributeError, setattr, p, 'x', 3)

        def test_no_slots(self):
            Point = namedlist('Point', '', use_slots=False)
            p = Point()
            # we should be able to create new attributes
            p.x = 3
            self.assertEqual(p.x, 3)

        def test_rename(self):
            Point = namedlist('Point', ('abc', 'def'), rename=True)
            self.assertEqual(Point._fields, ('abc', '_1'))

            Point = namedlist('Point', ('for', 'def'), rename=True)
            self.assertEqual(Point._fields, ('_0', '_1'))

            Point = namedlist('Point', 'a a b a b c', rename=True)
            self.assertEqual(Point._fields, ('a', '_1', 'b', '_3', '_4', 'c'))

            # nothing needs to be renamed, should still work with rename=True
            Point = namedlist('Point', 'x y z', rename=True)
            self.assertEqual(Point._fields, ('x', 'y', 'z'))

            Point = namedlist('Point', 'x y _z', rename=True)
            self.assertEqual(Point._fields, ('x', 'y', '_2'))

            # rename with defaults
            Point = namedlist('Point', [('', 1), ('', 2)], rename=True)
            p = Point()
            self.assertEqual(p._0, 1)
            self.assertEqual(p._1, 2)

        def test_type_begins_with_underscore(self):
            Point = namedlist('_Point', '')
            p = Point()

        def test_mapping(self):
            # use a regular dict so testing with 2.6 is still possible
            # do not make any assumptions about field order
            Point = namedlist('Point', {'x': 0, 'y': 100})
            p = Point()
            self.assertEqual(p.x, 0)
            self.assertEqual(p.y, 100)

            # in 2.7, test with an OrderedDict

        def test_NO_DEFAULT(self):
            # NO_DEFAULT is only really useful with we're using a mapping
            #  plus a default value. it's the only way to specify that
            #  some of the fields use the default.
            Point = namedlist('Point', {'x':0, 'y':NO_DEFAULT}, default=5)
            p = Point()
            self.assertEqual(p.x, 0)
            self.assertEqual(p.y, 5)

        def test_iterable(self):
            Point = namedlist('Point', iter(['x', 'y']))
            p = Point(1, 2)
            self.assertEqual(p.x, 1)
            self.assertEqual(p.y, 2)

        def test_single_field(self):
            X = namedlist('X', 'xyz')
            self.assertEqual(X._fields, ('xyz',))

        def test_repr_output(self):
            Point = namedlist('Point', 'a b')
            p = Point('0', 0)
            self.assertEqual(repr(p), "Point(a='0', b=0)")

        def test_mutable_defaults(self):
            # this behavior is unfortunate, but it should be tested anyway
            A = namedlist('A', [('x', [])])
            a = A()
            self.assertEqual(a.x, [])

            a.x.append(4)
            self.assertEqual(a.x, [4])

            b = A()
            self.assertEqual(b.x, [4])

        def test_factory_functions(self):
            A = namedlist('A', [('x', FACTORY(list))])
            a = A()
            self.assertEqual(a.x, [])

            a.x.append(4)
            self.assertEqual(a.x, [4])

            b = A()
            self.assertEqual(b.x, [])

        def test_unhashable(self):
            Point = namedlist('Point', 'a b')
            p = Point(1, 2)
            self.assertRaises(TypeError, hash, p)

        def test_getitem(self):
            Point = namedlist('Point', 'a b')
            p = Point(1, 2)
            self.assertEqual((p[0], p[1]), (1, 2))
            self.assertEqual(list(p), [1, 2])
            self.assertRaises(IndexError, p.__getitem__, 2)

        def test_setitem(self):
            Point = namedlist('Point', 'a b')
            p = Point(1, 2)
            p[0] = 10
            self.assertEqual(list(p), [10, 2])
            p[1] = 20
            self.assertEqual(list(p), [10, 20])
            self.assertRaises(IndexError, p.__setitem__, 2, 3)

        def test_container(self):
            # I'm not sure there's much sense in this, but list is a container
            Point = namedlist('Point', 'a b')
            p = Point(1, 2)
            self.assertIn(2, p)

        def test_ABC(self):
            Point = namedlist('Point', 'a b c')
            p = Point(1, 2, 2)
            self.assertIsInstance(p, _collections.Container)
            self.assertIsInstance(p, _collections.Iterable)
            self.assertIsInstance(p, _collections.Sized)
            self.assertIsInstance(p, _collections.Sequence)

            self.assertEqual(list(reversed(p)), [2, 2, 1])
            self.assertEqual(p.count(0), 0)
            self.assertEqual(p.count(2), 2)
            self.assertRaises(ValueError, p.index, 0)
            self.assertEqual(p.index(2), 1)
            self.assertEqual(p.index(1), 0)

            A = namedlist('A', 'a b c d e f g h i j')
            a = A(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            self.assertEqual(a.index(0, 1), 1)
            self.assertEqual(a.index(0, 5), 5)
            self.assertEqual(a.index(0, 1, 3), 1)
            self.assertEqual(a.index(0, 5, 12), 5)
            self.assertRaises(ValueError, a.index, 0, 12)


    unittest.main()
