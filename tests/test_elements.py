import re
import pytest

from shapely import wkb
from sqlalchemy import Table, MetaData, Column, String, func
from geoalchemy2.types import Geometry
from geoalchemy2.elements import (
    WKTElement, WKBElement, CompositeElement
)
from geoalchemy2.compat import buffer as buffer_, bytes as bytes_, str as str_
from geoalchemy2.exc import ArgumentError


@pytest.fixture
def geometry_table():
    table = Table('table', MetaData(), Column('geom', Geometry))
    return table


def eq_sql(a, b):
    a = re.sub(r'[\n\t]', '', str(a))
    assert a == b


class TestWKTElement():

    def test_desc(self):
        e = WKTElement('POINT(1 2)')
        assert e.desc == 'POINT(1 2)'

    def test_function_call(self):
        e = WKTElement('POINT(1 2)')
        f = e.ST_Buffer(2)
        eq_sql(f, 'ST_Buffer('
               'ST_GeomFromText(:ST_GeomFromText_1, :ST_GeomFromText_2), '
               ':ST_Buffer_1)')
        assert f.compile().params == {
            u'ST_Buffer_1': 2,
            u'ST_GeomFromText_1': 'POINT(1 2)',
            u'ST_GeomFromText_2': -1
        }

    def test_attribute_error(self):
        e = WKTElement('POINT(1 2)')
        assert not hasattr(e, 'foo')

    def test_pickle_unpickle(self):
        import pickle
        e = WKTElement('POINT(1 2)', srid=3, extended=True)
        pickled = pickle.dumps(e)
        unpickled = pickle.loads(pickled)
        assert unpickled.srid == 3
        assert unpickled.extended is True
        assert unpickled.data == 'POINT(1 2)'
        assert unpickled.name == 'ST_GeomFromEWKT'
        f = unpickled.ST_Buffer(2)
        eq_sql(f, 'ST_Buffer('
               'ST_GeomFromEWKT(:ST_GeomFromEWKT_1), '
               ':ST_Buffer_1)')
        assert f.compile().params == {
            u'ST_Buffer_1': 2,
            u'ST_GeomFromEWKT_1': 'POINT(1 2)',
        }


class TestExtendedWKTElement():

    _srid = 3857  # expected srid
    _wkt = 'POINT (1 2 3)'  # expected wkt
    _ewkt = 'SRID=3857;POINT (1 2 3)'  # expected ewkt

    def test_desc(self):
        e = WKTElement(self._ewkt, extended=True)
        assert e.desc == self._ewkt

    def test_function_call(self):
        e = WKTElement(self._ewkt, extended=True)
        f = e.ST_Buffer(2)
        eq_sql(f, 'ST_Buffer('
               'ST_GeomFromEWKT(:ST_GeomFromEWKT_1), '
               ':ST_Buffer_1)')
        assert f.compile().params == {
            u'ST_Buffer_1': 2,
            u'ST_GeomFromEWKT_1': self._ewkt
        }

    def test_pickle_unpickle(self):
        import pickle
        e = WKTElement(self._ewkt, extended=True)
        pickled = pickle.dumps(e)
        unpickled = pickle.loads(pickled)
        assert unpickled.srid == self._srid
        assert unpickled.extended is True
        assert unpickled.data == self._ewkt
        assert unpickled.name == 'ST_GeomFromEWKT'
        f = unpickled.ST_Buffer(2)
        eq_sql(f, 'ST_Buffer('
               'ST_GeomFromEWKT(:ST_GeomFromEWKT_1), '
               ':ST_Buffer_1)')
        assert f.compile().params == {
            u'ST_Buffer_1': 2,
            u'ST_GeomFromEWKT_1': self._ewkt,
        }

    def test_unpack_srid_from_ewkt(self):
        """
        Unpack SRID from WKT struct (when it is not provided as arg)
        to ensure geometry result processor preserves query SRID.
        """
        e = WKTElement(self._ewkt, extended=True)
        assert e.srid == self._srid
        assert e.desc == self._ewkt

    def test_unpack_srid_from_ewkt_forcing_srid(self):
        e = WKTElement(self._ewkt, srid=9999, extended=True)
        assert e.srid == 9999
        assert e.desc == self._ewkt

    def test_unpack_srid_from_bad_ewkt(self):
        with pytest.raises(ArgumentError):
            WKTElement('SRID=BAD SRID;POINT (1 2 3)', extended=True)


class TestWKTElementFunction():

    def test_ST_Equal_WKTElement_WKTElement(self):
        expr = func.ST_Equals(WKTElement('POINT(1 2)'),
                              WKTElement('POINT(1 2)'))
        eq_sql(expr, 'ST_Equals('
               'ST_GeomFromText(:ST_GeomFromText_1, :ST_GeomFromText_2), '
               'ST_GeomFromText(:ST_GeomFromText_3, :ST_GeomFromText_4))')
        assert expr.compile().params == {
            u'ST_GeomFromText_1': 'POINT(1 2)',
            u'ST_GeomFromText_2': -1,
            u'ST_GeomFromText_3': 'POINT(1 2)',
            u'ST_GeomFromText_4': -1,
        }

    def test_ST_Equal_Column_WKTElement(self, geometry_table):
        expr = func.ST_Equals(geometry_table.c.geom, WKTElement('POINT(1 2)'))
        eq_sql(expr,
               'ST_Equals("table".geom, '
               'ST_GeomFromText(:ST_GeomFromText_1, :ST_GeomFromText_2))')
        assert expr.compile().params == {
            u'ST_GeomFromText_1': 'POINT(1 2)',
            u'ST_GeomFromText_2': -1
        }


class TestExtendedWKTElementFunction():

    def test_ST_Equal_WKTElement_WKTElement(self):
        expr = func.ST_Equals(WKTElement('SRID=3857;POINT(1 2 3)',
                                         extended=True),
                              WKTElement('SRID=3857;POINT(1 2 3)',
                                         extended=True))
        eq_sql(expr, 'ST_Equals('
               'ST_GeomFromEWKT(:ST_GeomFromEWKT_1), '
               'ST_GeomFromEWKT(:ST_GeomFromEWKT_2))')
        assert expr.compile().params == {
            u'ST_GeomFromEWKT_1': 'SRID=3857;POINT(1 2 3)',
            u'ST_GeomFromEWKT_2': 'SRID=3857;POINT(1 2 3)',
        }

    def test_ST_Equal_Column_WKTElement(self, geometry_table):
        expr = func.ST_Equals(geometry_table.c.geom,
                              WKTElement('SRID=3857;POINT(1 2 3)',
                                         extended=True))
        eq_sql(expr,
               'ST_Equals("table".geom, '
               'ST_GeomFromEWKT(:ST_GeomFromEWKT_1))')
        assert expr.compile().params == {
            u'ST_GeomFromEWKT_1': 'SRID=3857;POINT(1 2 3)',
        }


class TestExtendedWKBElement():

    # _bin/_hex computed by following query:
    # SELECT ST_GeomFromEWKT('SRID=3;POINT(1 2)');
    _bin = buffer_(b'\x01\x01\x00\x00 \x03\x00\x00\x00\x00\x00\x00'
                   b'\x00\x00\x00\xf0?\x00\x00\x00\x00\x00\x00\x00@')
    _hex = str_('010100002003000000000000000000f03f0000000000000040')
    _srid = 3  # expected srid
    _wkt = 'POINT (1 2)'  # expected wkt

    def test_desc(self):
        e = WKBElement(self._bin, extended=True)
        assert e.desc == self._hex

    def test_desc_str(self):
        e = WKBElement(self._hex)
        assert e.desc == self._hex

    def test_function_call(self):
        e = WKBElement(self._bin, extended=True)
        f = e.ST_Buffer(2)
        eq_sql(f, 'ST_Buffer('
               'ST_GeomFromEWKB(:ST_GeomFromEWKB_1), '
               ':ST_Buffer_1)')
        assert f.compile().params == {
            u'ST_Buffer_1': 2,
            u'ST_GeomFromEWKB_1': self._bin,
        }

    def test_function_str(self):
        e = WKBElement(self._bin, extended=True)
        assert isinstance(str(e), str)

    def test_pickle_unpickle(self):
        import pickle
        e = WKBElement(self._bin, srid=self._srid, extended=True)
        pickled = pickle.dumps(e)
        unpickled = pickle.loads(pickled)
        assert unpickled.srid == self._srid
        assert unpickled.extended is True
        assert unpickled.data == bytes_(self._bin)
        assert unpickled.name == 'ST_GeomFromEWKB'
        f = unpickled.ST_Buffer(2)
        eq_sql(f, 'ST_Buffer('
               'ST_GeomFromEWKB(:ST_GeomFromEWKB_1), '
               ':ST_Buffer_1)')
        assert f.compile().params == {
            u'ST_Buffer_1': 2,
            u'ST_GeomFromEWKB_1': bytes_(self._bin),
        }

    def test_unpack_srid_from_bin(self):
        """
        Unpack SRID from WKB struct (when it is not provided as arg)
        to ensure geometry result processor preserves query SRID.
        """
        e = WKBElement(self._bin, extended=True)
        assert e.srid == self._srid
        assert wkb.loads(bytes_(e.data)).wkt == self._wkt

    def test_unpack_srid_from_bin_forcing_srid(self):
        e = WKBElement(self._bin, srid=9999, extended=True)
        assert e.srid == 9999
        assert wkb.loads(bytes_(e.data)).wkt == self._wkt

    def test_unpack_srid_from_hex(self):
        e = WKBElement(self._hex, extended=True)
        assert e.srid == self._srid
        assert wkb.loads(e.data, hex=True).wkt == self._wkt


class TestWKBElement():

    def test_desc(self):
        e = WKBElement(b'\x01\x02')
        assert e.desc == '0102'

    def test_function_call(self):
        e = WKBElement(b'\x01\x02')
        f = e.ST_Buffer(2)
        eq_sql(f, 'ST_Buffer('
               'ST_GeomFromWKB(:ST_GeomFromWKB_1, :ST_GeomFromWKB_2), '
               ':ST_Buffer_1)')
        assert f.compile().params == {
            u'ST_Buffer_1': 2, u'ST_GeomFromWKB_1': b'\x01\x02',
            u'ST_GeomFromWKB_2': -1
        }

    def test_attribute_error(self):
        e = WKBElement(b'\x01\x02')
        assert not hasattr(e, 'foo')

    def test_function_str(self):
        e = WKBElement(b'\x01\x02')
        assert isinstance(str(e), str)


class TestCompositeElement():

    def test_compile(self):
        # text fixture
        metadata = MetaData()
        foo = Table('foo', metadata, Column('one', String))

        e = CompositeElement(foo.c.one, 'geom', String)
        assert str(e) == '(foo.one).geom'
