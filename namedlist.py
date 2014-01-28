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

# all of this hassle with ast is solely to provide a decent __init__
#  function, that takes all of the right arguments and defaults. but
#  it's worth it to get all of the normal python error messages.
# for other functions, like __repr__, we don't bother. __init__ is
#  the only function where we really need the argument processing.

import ast as _ast
import sys as _sys
from keyword import iskeyword as _iskeyword
from collections import Mapping as _Mapping

_PY2 = _sys.version_info[0] == 2
_PY3 = _sys.version_info[0] == 3

if _PY2:
    _basestring = basestring
else:
    _basestring = str


NO_DEFAULT = object()

class FACTORY(object):
    def __init__(self, callable):
        self._callable = callable

    def __call__(self):
        return self._callable()


# Keep track of fields, both with and without defaults.
class _Fields(object):
    def __init__(self, default):
        self.default = default
        self.with_defaults = []        # List of (field_name, default).
        self.without_defaults = []     # List of field_name.

    def add_with_default(self, field_name, default):
        if default is NO_DEFAULT:
            self.add_without_default(field_name)
        else:
            self.with_defaults.append((field_name, default))

    def add_without_default(self, field_name):
        if self.default is NO_DEFAULT:
            # No default. There can't be any defaults already specified.
            if self.with_defaults:
                raise ValueError('field {0} without a default follows fields '
                                 'with defaults'.format(field_name))
            self.without_defaults.append(field_name)
        else:
            self.add_with_default(field_name, self.default)


# Used for both the type name and field names. If is_type_name is
#  False, seen_names must be provided. Raise ValueError if the name is
#  bad.
def _check_name(name, is_type_name=False, seen_names=None):
    if len(name) == 0:
        raise ValueError('Type names and field names cannot be zero '
                         'length: {0!r}'.format(name))
    if not all(c.isalnum() or c=='_' for c in name):
        raise ValueError('Type names and field names can only contain '
                         'alphanumeric characters and underscores: '
                         '{0!r}'.format(name))
    if _iskeyword(name):
        raise ValueError('Type names and field names cannot be a keyword: '
                         '{0!r}'.format(name))
    if name[0].isdigit():
        raise ValueError('Type names and field names cannot start with a '
                         'number: {0!r}'.format(name))

    if not is_type_name:
        # these tests don't apply for the typename, just the fieldnames
        if name in seen_names:
            raise ValueError('Encountered duplicate field name: '
                             '{0!r}'.format(name))

        if name.startswith('_'):
            raise ValueError('Field names cannot start with an underscore: '
                             '{0!r}'.format(name))


# Validate a field name. If it's a bad name, and if rename is True,
#  then return a 'sanitized' name. Raise ValueError if the name is bad.
def _check_field_name(name, seen_names, rename, idx):
    try:
        _check_name(name, seen_names=seen_names)
    except ValueError as ex:
        if rename:
            return '_' + str(idx)
        else:
            raise

    seen_names.add(name)
    return name


########################################################################
# member functions

def _repr(self):
    return '{0}({1})'.format(self._name, ', '.join('{0}={1!r}'.format(name, getattr(self, name)) for name in self._fields))


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


def _iter(self):
    return (getattr(self, fieldname) for fieldname in self._fields)
########################################################################


########################################################################
# the function that __init__ calls to do the actual work

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


# returns a function with name 'name', that calls another function 'chain_fn'
# this is used to create the __init__ function with the right argument names and defaults, that
#  calls into _init to do the real work
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


def namedlist(typename, field_names, default=NO_DEFAULT, rename=False,
              use_slots=True):
    # field_names must be a string or an iterable, consisting of fieldname
    #  strings or 2-tuples. Each 2-tuple is of the form (fieldname,
    #  default).

    fields = _Fields(default)

    _check_name(typename, is_type_name=True)

    if isinstance(field_names, _basestring):
        # No per-field defaults. So it's like a namedtuple, but with
        #  a possible default value.
        field_names = field_names.replace(',', ' ').split()

    # If field_names is a Mapping, change it to return the
    #  (field_name, default) pairs, as if it were a list
    if isinstance(field_names, _Mapping):
        field_names = field_names.items()

    # Parse and validate the field names.  Validation serves two
    #  purposes: generating informative error messages and preventing
    #  template injection attacks.

    # field_names is now an iterable. Walk through it,
    # sanitizing as needed, and add to fields.

    seen_names = set()
    for idx, field_name in enumerate(field_names):
        if isinstance(field_name, _basestring):
            field_name = _check_field_name(field_name, seen_names, rename,
                                           idx)
            fields.add_without_default(field_name)
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
            field_name = _check_field_name(field_name[0], seen_names, rename,
                                           idx)
            fields.add_with_default(field_name, default)

    all_field_names = tuple(fields.without_defaults + [name for name, default in
                                                       fields.with_defaults])

    __init = _make_fn('__init__', _init, all_field_names, [default for _, default in fields.with_defaults])

    type_dict = {'__init__': __init,
                 '__repr__': _repr,
                 '__eq__': _eq,
                 '__ne__': _ne,
                 '__len__': _len,
                 '__getstate__': _getstate,
                 '__setstate__': _setstate,
                 '__iter__': _iter,
                 '_asdict': _asdict,
                 '_name': typename,
                 '_fields': all_field_names}

    if use_slots:
        type_dict['__slots__'] = all_field_names

    # and finally, create and return the new type object
    return type(typename, (object,), type_dict)


if __name__ == '__main__':
    import unittest

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

        def test_iterabale(self):
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



    unittest.main()
