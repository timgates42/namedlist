#######################################################################
# Tests for namedlist module.
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
#  When moving to a newer version of unittest, check that the exceptions
# being caught have the expected text in them.
#
########################################################################

from namedlist import namedlist, FACTORY, NO_DEFAULT

import sys
import unittest
import collections
import unicodedata

_PY2 = sys.version_info[0] == 2
_PY3 = sys.version_info[0] == 3

# test both pickle and cPickle in 2.x, but just pickle in 3.x
import pickle
try:
    import cPickle
    pickle_modules = (pickle, cPickle)
except ImportError:
    pickle_modules = (pickle,)

# types used for pickle tests
TestNL0 = namedlist('TestNL0', '')
TestNL = namedlist('TestNL', 'x y z')

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

        self.assertEqual(vars(p), p._asdict())                              # verify that vars() works

    def test_asdict_vars_ordered(self):
        Point = namedlist('Point', ['x', 'y'])
        p = Point(10, 20)

        # can't use unittest.skipIf in 2.6
        if sys.version_info[0] <= 2 and sys.version_info[1] <= 6:
            self.assertIsInstance(p.__dict__, dict)
        else:
            self.assertIsInstance(p.__dict__, collections.OrderedDict)

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
        self.assertIsInstance(Point._fields, tuple)

        Point = namedlist('Point', 'x y z', 100)
        self.assertEqual(Point._fields, ('x', 'y', 'z'))

        Point = namedlist('Point', [('x', 0), ('y', 0), ('z', 0)])
        self.assertEqual(Point._fields, ('x', 'y', 'z'))

        Point = namedlist('Point', '')
        self.assertEqual(Point._fields, ())
        self.assertIsInstance(Point._fields, tuple)

    def test_pickle(self):
        for p in (TestNL0(), TestNL(x=10, y=20, z=30)):
            for module in pickle_modules:
                for protocol in range(-1, module.HIGHEST_PROTOCOL + 1):
                    q = module.loads(module.dumps(p, protocol))
                    self.assertEqual(p, q)
                    self.assertEqual(p._fields, q._fields)
                    self.assertNotIn(b'OrderedDict', module.dumps(p, protocol))

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

    def test_factory_for_default(self):
        # make sure FACTORY works for the global default
        A = namedlist('A', 'x y', default=FACTORY(list))
        a = A()
        self.assertEqual(a.x, [])
        self.assertEqual(a.y, [])

        a.x.append(4)
        self.assertEqual(a.x, [4])
        a.y.append(4)
        self.assertEqual(a.y, [4])

        b = A()
        self.assertEqual(b.x, [])
        self.assertEqual(b.y, [])

        # mix and match FACTORY and a non-callable mutable default
        A = namedlist('A', [('x', []), 'y'], default=FACTORY(list))
        a = A()
        self.assertEqual(a.x, [])
        self.assertEqual(a.y, [])

        a.x.append(4)
        self.assertEqual(a.x, [4])
        a.y.append(4)
        self.assertEqual(a.y, [4])

        b = A()
        self.assertEqual(b.x, [4])
        self.assertEqual(b.y, [])

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
        self.assertIsInstance(p, collections.Container)
        self.assertIsInstance(p, collections.Iterable)
        self.assertIsInstance(p, collections.Sized)
        self.assertIsInstance(p, collections.Sequence)

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

    def test_docstring(self):
        Point = namedlist('Point', '')
        self.assertEqual(Point.__doc__, 'Point()')

        Point = namedlist('Point', 'dx')
        self.assertEqual(Point.__doc__, 'Point(dx)')

        Point = namedlist('Point', 'x')
        self.assertEqual(Point.__doc__, 'Point(x)')

        Point = namedlist('Point', 'dx dy, dz')
        self.assertEqual(Point.__doc__, 'Point(dx, dy, dz)')

        Point = namedlist('Point', 'dx dy dz', default=10)
        self.assertEqual(Point.__doc__, 'Point(dx=10, dy=10, dz=10)')

        Point = namedlist('Point', 'dx, dy, dz', default=FACTORY(10))
        self.assertEqual(Point.__doc__, 'Point(dx=FACTORY(10), dy=FACTORY(10), dz=FACTORY(10))')

        Point = namedlist('Point', ['dx', 'dy', ('dz', 11.0)], default=10)
        self.assertEqual(Point.__doc__, 'Point(dx=10, dy=10, dz=11.0)')

        Point = namedlist('Point', ['dx', 'dy', ('dz', 11.0)], default=FACTORY(list))
        if _PY2:
            list_repr = "<type 'list'>"
        else:
            list_repr = "<class 'list'>"
        self.assertEqual(Point.__doc__, "Point(dx=FACTORY({0}), dy=FACTORY({0}), dz=11.0)".format(list_repr))

        Point = namedlist('Point', ['dx', 'dy', ('dz', FACTORY(11.0))], default=[])
        self.assertEqual(Point.__doc__, 'Point(dx=[], dy=[], dz=FACTORY(11.0))')


# 2.6 is missing some unittest.TestCase members. Add
#  trivial implementations for them.
def _assertIsInstance(self, obj, cls):
    self.assertTrue(isinstance(obj, cls))

def _assertIn(self, obj, iterable):
    self.assertTrue(obj in iterable)

def _assertNotIn(self, obj, iterable):
    self.assertTrue(not obj in iterable)

def _add_unittest_methods(cls):
    for name, fn in [('assertIsInstance', _assertIsInstance),
                     ('assertIn', _assertIn),
                     ('assertNotIn', _assertNotIn)]:
        if not hasattr(cls, name):
            setattr(cls, name, fn)

_add_unittest_methods(TestNamedlist)

unittest.main()
