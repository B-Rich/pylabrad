# Copyright (C) 2007  Matthew Neeley
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from datetime import datetime
import unittest
import numpy as np

import sys
import os
sys.path.insert(0, os.path.abspath('../..'))

import labrad.types as T
import labrad.units as U

from labrad.units import Value, ValueArray, Complex


class LabradTypesTests(unittest.TestCase):

    def testTags(self):
        """Test the parsing of type tags into LRType objects."""
        tests = {
            '_': T.LRNone(),
            'b': T.LRBool(),
            'i': T.LRInt(),
            'w': T.LRWord(),
            's': T.LRStr(),
            't': T.LRTime(),

            # clusters
            'ii': T.LRCluster(T.LRInt(), T.LRInt()),
            'b(t)': T.LRCluster(T.LRBool(), T.LRCluster(T.LRTime())),
            '(ss)': T.LRCluster(T.LRStr(), T.LRStr()),
            '(s)': T.LRCluster(T.LRStr()),
            '((siw))': T.LRCluster(T.LRCluster(T.LRStr(), T.LRInt(),
                                               T.LRWord())),

            # lists
            '*b': T.LRList(T.LRBool()),
            '*_': T.LRList(),
            '*2b': T.LRList(T.LRBool(), depth=2),
            '*2_': T.LRList(depth=2),
            '*2v[Hz]': T.LRList(T.LRValue('Hz'), depth=2),
            '*3v': T.LRList(T.LRValue(), depth=3),
            '*v[]': T.LRList(T.LRValue(''), depth=1),

            # unit types
            'v': T.LRValue(),
            'v[]': T.LRValue(''),
            'v[m/s]': T.LRValue('m/s'),
            'c': T.LRComplex(),
            'c[]': T.LRComplex(''),
            'c[m/s]': T.LRComplex('m/s'),

            # errors
            'E': T.LRError(),
            'Ew': T.LRError(T.LRWord()),
            'E(w)': T.LRError(T.LRCluster(T.LRWord())),

            # more complex stuff
            '*b*i': T.LRCluster(T.LRList(T.LRBool()), T.LRList(T.LRInt())),
        }
        for tag, type_ in tests.items():
            self.assertEqual(T.parseTypeTag(tag), type_)
            newtag = str(type_)
            if isinstance(type_, T.LRCluster) and tag[0] + tag[-1] != '()':
                # just added parentheses in this case
                self.assertEqual(newtag, '(%s)' % tag)
            else:
                self.assertEqual(newtag, tag)

    def testTagComments(self):
        """Test the parsing of type tags with comments and whitespace."""
        tests = {
            '': T.LRNone(),
            ' ': T.LRNone(),
            ': this is a test': T.LRNone(),
            '  : this is a test': T.LRNone(),
            '   i  ': T.LRInt(),
            '   i  :': T.LRInt(),
            '   i  : blah': T.LRInt(),
        }
        for tag, type_ in tests.items():
            self.assertEqual(T.parseTypeTag(tag), type_)

    def testDefaultFlatAndBack(self):
        """
        Test roundtrip python->LabRAD->python conversion.

        No type requirements are given in these tests. In other words, we allow
        pylabrad to choose a default type for flattening.

        In this test, we expect A == unflatten(*flatten(A)). In other words,
        we expect the default type chosen for each object to unflatten as
        an object equal to the one originally flattened.
        """
        tests = [
            # simple types
            None,
            True, False,
            1, -1, 2, -2,
            1L, 2L, 3L, 4L,
            '', 'a', '\x00\x01\x02\x03',
            datetime.now(),

            # values
            5.0,
            Value(6, ''),
            Value(7, 'ms'),
            8+0j,
            Complex(9+0j, ''),
            Complex(10+0j, 'GHz'),

            # ValueArray and ndarray
            # These types should be invariant under flattening followed by
            # unflattening. Note, however, that since eg. [1, 2, 3] will
            # unflatten as ndarray with dtype=int32, we do not put lists
            # in this test.
            U.ValueArray([1, 2, 3], 'm'),
            np.array([1, 3, 4], dtype='int32'),
            np.array([1.1, 2.2, 3.3]),

            # clusters
            (1, True, 'a'),
            ((1, 2), ('a', False)),

            # lists
            [],
            #[1, 2, 3, 4],
            #[1L, 2L, 3L, 4L],
            [[]],
            [['a', 'bb', 'ccc'], ['dddd', 'eeeee', 'ffffff']],

            # more complex stuff
            [(1L, 'a'), (2L, 'b')],
        ]
        for data_in in tests:
            data_out = T.unflatten(*T.flatten(data_in))
            if isinstance(data_in, U.ValueArray):
                self.assertTrue(data_in.allclose(data_out))
            elif isinstance(data_in, np.ndarray):
                np.testing.assert_array_equal(data_out, data_in)
            else:
                self.assertEqual(data_in, data_out)

    def testBufferTypes(self):
        """
        Test flattening of types supporting python's buffer interface (str, bytes, etc.).

        All such types can be considered as arrays of bytes, and so flatten to 's' in labrad.
        TODO: introduce a separation between bytes and text (unicode), as in python3.
        """
        tests = [
            # strings
            '', 'a', '\x00\x01\x02\x03',

            # bytes (immutable)
            b'', b'a', 'b\x00\x01\x02\x03',

            # bytearray (mutable)
            bytearray(b''), bytearray(b'a'), bytearray(b'\x00\x01\x02\x03'),

            # memoryview
            memoryview(b''), memoryview(b'a'), memoryview(b'\x00\x01\x02\x03')
        ]
        for data_in in tests:
            s, t = T.flatten(data_in)
            self.assertEquals(t, T.parseTypeTag('s'))
            data_out = T.unflatten(s, t)
            if isinstance(data_in, memoryview):
                expected = data_in.tobytes()
            else:
                expected = bytes(data_in)
            self.assertEqual(data_out, expected)

    def testUnicode(self):
        """
        Test flattening of unicode strings.

        These will be encoded as utf-8 and flattened to 's' in labrad.
        TODO: introduce a separation between bytes and text (unicode), as in python3.
        """
        tests = [
            u'', u'a', u'\u02C0'
        ]
        for data_in in tests:
            s, t = T.flatten(data_in)
            self.assertEquals(t, T.parseTypeTag('s'))
            data_out = unicode(T.unflatten(s, t), 'utf-8')
            self.assertEqual(data_out, data_in)

    def testDefaultFlatAndBackNonIdentical(self):
        """
        Test flattening/unflattening of objects which change type.

        No type requirements are given in these tests. In other words, we allow
        pylabrad to choose a default type for flattening.

        In this test, we do not expect A == unflatten(*flatten(A)). This is
        mostly because list of numbers, both with an without units, should
        unflatten to ndarray or ValueArray, rather than actual python lists.
        """
        def compareValueArrays(a, b):
            """I check near equality of two ValueArrays"""
            self.assertTrue(a.allclose(b))

        tests = [
            ([1, 2, 3], np.array([1, 2, 3], dtype='int32'),
                np.testing.assert_array_equal),
            ([1.1, 2.2, 3.3], np.array([1.1, 2.2, 3.3], dtype='float64'),
                np.testing.assert_array_almost_equal),
            (np.array([3, 4], dtype='int32'), np.array([3, 4], dtype='int32'),
                np.testing.assert_array_equal),
            (np.array([1.2, 3.4]), np.array([1.2, 3.4]),
                np.testing.assert_array_almost_equal),
            ([Value(1.0, 'm'), Value(3.0, 'm')], ValueArray([1.0, 3.0], 'm'),
                compareValueArrays),
            ([Value(1.0, 'm'), Value(10, 'cm')], ValueArray([1.0, 0.1], 'm'),
                compareValueArrays),
            (ValueArray([1, 2], 'Hz'), ValueArray([1, 2], 'Hz'),
                compareValueArrays),
            (ValueArray([1.0, 2], ''), np.array([1.0, 2]),
                np.testing.assert_array_almost_equal)
        ]
        for input, expected, comparison_func in tests:
            unflat = T.unflatten(*T.flatten(input))
            if isinstance(unflat, np.ndarray):
                self.assertEqual(unflat.dtype, expected.dtype)
            comparison_func(unflat, expected)

    def testFlatAndBackWithTypeRequirements(self):
        tests = [
            ([1, 2, 3], ['*i'], np.array([1, 2, 3]),
                np.testing.assert_array_equal),
            ([1, 2], ['*v[]'], np.array([1, 2]),
                np.testing.assert_array_almost_equal),
            ([1.1, 2.], ['*v[]'], np.array([1.1, 2.], dtype='float64'),
                np.testing.assert_array_almost_equal)
        ]
        for input, types, expected, comparison_func in tests:
            flat = T.flatten(input, types)
            unflat = T.unflatten(*flat)
            comparison_func(expected, unflat)

    def testFailedFlattening(self):
        """
        Trying to flatten data to an incompatible type should raise an error.
        """
        cases = [
            # Simple cases
            (1, ['s', 'v[Hz]']),
            ('X', ['i', 'v', 'w']),
            (5.0, ['s', 'b', 't', 'w', 'i', 'v[Hz]']),
            # Value
            (5.0, 'v[Hz]'),
            (Value(4, 'm'), 'v[]'),
            (Value(3, 's'), ['v[Hz]', 'i', 'w']),
            # ndarray
            (np.array([1, 2, 3], dtype='int32'), '*v[Hz]'),
            (np.array([1.0, 2.4]), ['*i', '*w']),
            # ValueArray
            (U.ValueArray([1, 2, 3], 'm'), '*v[s]'),
            (U.ValueArray([1, 2], 'm'), '*v[]')
        ]
        for data, targetTag in cases:
            self.assertRaises(T.FlatteningError, T.flatten, data, targetTag)

    def testTypeHints(self):
        """Test conversion to specified allowed types."""
        passingTests = [
            # convert to default type
            (1, [], 'i'),

            # convert to first compatible type
            (1, ['s', 'w'], 'w'),
            (1, ['s', 'v'], 'v[]'),
            (1*U.m, ['s', 'v[m]'], 'v[m]'),
            # 'v' not allowed on wire
            (3.0, 'v', 'v[]'),
            (3, 'v', 'v[]'),

            # empty list gets type from hint
            ([], ['s', '*(ww)'], '*(ww)'),

            # handle unknown pieces inside clusters and lists
            (['a', 'b'], ['*?'], '*s'),
            ((1, 2, 'a'), ['ww?'], 'wws'),
            ((1, 1L), ['??'], 'iw'),
        ]
        for data, hints, tag in passingTests:
            self.assertEqual(T.flatten(data, hints)[1], T.parseTypeTag(tag))

    def testTypeSpecialization(self):
        """Test specialization of the type during flattening."""
        tests = [
            # specialization without hints
            ([([],), ([5.0],)], '*(*v)'),
            ([([],), ([Value(5, 'm')],)], '*(*v[m])'),
        ]
        for data, tag in tests:
            self.assertEqual(T.flatten(data)[1], T.parseTypeTag(tag))

    def testUnitTypes(self):
        """Test flattening with units.

        The flattening code should not do unit conversion,
        but should leave that up to the LabRAD manager to handle.
        Basically, for purposes of flattening, a unit is a unit.
        """
        tests = [
            (Value(5.0, 'ft'), ['v[m]'], 'v[ft]'),
            (U.ValueArray([1, 2, 3], 'm'), ['*v[m]'], '*v[m]')
        ]
        for data, hints, tag in tests:
            self.assertEqual(T.flatten(data, hints)[1], T.parseTypeTag(tag))

        # we disallow flattening a float to a value with units,
        # as this is a major source of bugs
        try:
            T.flatten(5.0, 'v[m]')
        except Exception:
            pass
        else:
            raise Exception('Cannot flatten float to value with units')

    def testNumpySupport(self):
        """Test flattening and unflattening of numpy arrays"""
        import numpy as np

        # TODO: flesh this out with more array types
        a = np.array([1, 2, 3, 4, 5], dtype='int32')
        b = T.unflatten(*T.flatten(a))
        self.assertTrue(np.all(a == b))

    def testIntegerRanges(self):
        """Test flattening of out-of-range integer values"""
        tests = [
            (0x80000000, 'i'),
            (-0x80000001, 'i'),
            (0x100000000, 'w'),
            (-1, 'w')
        ]
        for n, t in tests:
            with self.assertRaises(T.FlatteningError):
                T.flatten(n, t)

if __name__ == "__main__":
    unittest.main()
