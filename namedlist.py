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

try:
    _OrderedDict = _collections.OrderedDict
except AttributeError:
    _OrderedDict = None


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

    def __repr__(self):
        return 'FACTORY({0!r})'.format(self._callable)


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
    # In 2.6, return a dict.
    # Otherwise, return an OrderedDict
    t = _OrderedDict if _OrderedDict is not None else dict
    return t(zip(self._fields, self))

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
    for fieldname, value in _get_values(self._fields, args):
        setattr(self, fieldname, value)


def _get_values(fields, args):
    # Returns [(fieldname, value)]. If the value is a FACTORY, call it.
    assert len(fields) == len(args)
    return [(fieldname, (value._callable() if isinstance(value, FACTORY) else value))
            for fieldname, value in zip(fields, args)]


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
    locals_ = dict(('_def{0}'.format(idx), value) for idx, value in enumerate(defaults))
    eval(code, globals_, locals_)

    # extract our function from the newly created module
    return locals_[name]


########################################################################
# Produce a docstring for the class.

def _field_name_with_default(name, default):
    if default is NO_DEFAULT:
        return name
    return '{0}={1!r}'.format(name, default)

def _build_docstring(typename, fields, defaults):
    # We can use NO_DEFAULT as a sentinel here, becuase it will never be
    #  present in defaults. By this point, it has been removed and replaced
    #  with actual default values.

    # The defaults make this a little tricky. Append a sentinel in
    #  front of defaults until it's the same length as fields. The
    #  sentinel value is used in _name_with_default
    defaults = [NO_DEFAULT] * (len(fields) - len(defaults)) + defaults
    return '{0}({1})'.format(typename, ', '.join(_field_name_with_default(name, default)
                                                 for name, default in zip(fields, defaults)))


########################################################################
# Given the typename, fields_names, default, and the rename flag,
#  return a tuple of fields and a list of defaults.
def _fields_and_defaults(typename, field_names, default, rename):
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

    return (tuple(fields.without_defaults + [name for name, default in
                                             fields.with_defaults]),
            [default for _, default in fields.with_defaults])


########################################################################
# The actual namedlist factory function.
def namedlist(typename, field_names, default=NO_DEFAULT, rename=False,
              use_slots=True):

    fields, defaults = _fields_and_defaults(typename, field_names, default, rename)

    type_dict = {'__init__': _make_fn('__init__', _init, fields, defaults),
                 '__repr__': _repr,
                 '__eq__': _eq,
                 '__ne__': _ne,
                 '__len__': _len,
                 '__getstate__': _getstate,
                 '__setstate__': _setstate,
                 '__getitem__': _getitem,
                 '__setitem__': _setitem,
                 '__iter__': _iter,
                 '__dict__': property(_asdict),
                 '__hash__': None,
                 '__doc__': _build_docstring(typename, fields, defaults),
                 'count': _count,
                 'index': _index,
                 '_asdict': _asdict,
                 '_fields': fields}

    if use_slots:
        type_dict['__slots__'] = fields

    # See collections.namedtuple for a description of
    #  what's happening here
    try:
        type_dict['__module__'] = _sys._getframe(1).f_globals.get('__name__', '__main__')
    except (AttributeError, ValueError):
        pass

    # Create the new type object.
    t = type(typename, (object,), type_dict)

    # Register its ABC's
    _collections.Sequence.register(t)

    # And return it.
    return t
