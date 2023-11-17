#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2017-2023 Satpy developers
#
# This file is part of satpy.
#
# satpy is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# satpy is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# satpy.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for the CF Area."""
import dask.array as da
import numpy as np
import pytest
import xarray as xr
from pyresample import AreaDefinition, SwathDefinition


class TestCFArea:
    """Test case for CF Area."""

    def test_area2cf(self):
        """Test the conversion of an area to CF standards."""
        from satpy.cf.area import area2cf

        ds_base = xr.DataArray(data=[[1, 2], [3, 4]], dims=("y", "x"), coords={"y": [1, 2], "x": [3, 4]},
                               attrs={"name": "var1"})

        # a) Area Definition and strict=False
        geos = AreaDefinition(
            area_id="geos",
            description="geos",
            proj_id="geos",
            projection={"proj": "geos", "h": 35785831., "a": 6378169., "b": 6356583.8},
            width=2, height=2,
            area_extent=[-1, -1, 1, 1])
        ds = ds_base.copy(deep=True)
        ds.attrs["area"] = geos

        res = area2cf(ds, include_lonlats=False)
        assert len(res) == 2
        assert res[0].size == 1  # grid mapping variable
        assert res[0].name == res[1].attrs["grid_mapping"]

        # b) Area Definition and include_lonlats=False
        ds = ds_base.copy(deep=True)
        ds.attrs["area"] = geos
        res = area2cf(ds, include_lonlats=True)
        # same as above
        assert len(res) == 2
        assert res[0].size == 1  # grid mapping variable
        assert res[0].name == res[1].attrs["grid_mapping"]
        # but now also have the lon/lats
        assert "longitude" in res[1].coords
        assert "latitude" in res[1].coords

        # c) Swath Definition
        swath = SwathDefinition(lons=[[1, 1], [2, 2]], lats=[[1, 2], [1, 2]])
        ds = ds_base.copy(deep=True)
        ds.attrs["area"] = swath

        res = area2cf(ds, include_lonlats=False)
        assert len(res) == 1
        assert "longitude" in res[0].coords
        assert "latitude" in res[0].coords
        assert "grid_mapping" not in res[0].attrs

    def test_add_grid_mapping(self):
        """Test the conversion from pyresample area object to CF grid mapping."""
        from satpy.cf.area import _add_grid_mapping

        def _gm_matches(gmapping, expected):
            """Assert that all keys in ``expected`` match the values in ``gmapping``."""
            for attr_key, attr_val in expected.attrs.items():
                test_val = gmapping.attrs[attr_key]
                if attr_val is None or isinstance(attr_val, str):
                    assert test_val == attr_val
                else:
                    np.testing.assert_almost_equal(test_val, attr_val, decimal=3)

        ds_base = xr.DataArray(data=[[1, 2], [3, 4]], dims=("y", "x"), coords={"y": [1, 2], "x": [3, 4]},
                               attrs={"name": "var1"})

        # a) Projection has a corresponding CF representation (e.g. geos)
        a = 6378169.
        b = 6356583.8
        h = 35785831.
        geos = AreaDefinition(
            area_id="geos",
            description="geos",
            proj_id="geos",
            projection={"proj": "geos", "h": h, "a": a, "b": b,
                        "lat_0": 0, "lon_0": 0},
            width=2, height=2,
            area_extent=[-1, -1, 1, 1])
        geos_expected = xr.DataArray(data=0,
                                     attrs={"perspective_point_height": h,
                                            "latitude_of_projection_origin": 0,
                                            "longitude_of_projection_origin": 0,
                                            "grid_mapping_name": "geostationary",
                                            "semi_major_axis": a,
                                            "semi_minor_axis": b,
                                            # 'sweep_angle_axis': None,
                                            })

        ds = ds_base.copy()
        ds.attrs["area"] = geos
        new_ds, grid_mapping = _add_grid_mapping(ds)
        if "sweep_angle_axis" in grid_mapping.attrs:
            # older versions of pyproj might not include this
            assert grid_mapping.attrs["sweep_angle_axis"] == "y"

        assert new_ds.attrs["grid_mapping"] == "geos"
        _gm_matches(grid_mapping, geos_expected)
        # should not have been modified
        assert "grid_mapping" not in ds.attrs

        # b) Projection does not have a corresponding CF representation (COSMO)
        cosmo7 = AreaDefinition(
            area_id="cosmo7",
            description="cosmo7",
            proj_id="cosmo7",
            projection={"proj": "ob_tran", "ellps": "WGS84", "lat_0": 46, "lon_0": 4.535,
                        "o_proj": "stere", "o_lat_p": 90, "o_lon_p": -5.465},
            width=597, height=510,
            area_extent=[-1812933, -1003565, 814056, 1243448]
        )

        ds = ds_base.copy()
        ds.attrs["area"] = cosmo7

        new_ds, grid_mapping = _add_grid_mapping(ds)
        assert "crs_wkt" in grid_mapping.attrs
        wkt = grid_mapping.attrs["crs_wkt"]
        assert 'ELLIPSOID["WGS 84"' in wkt
        assert 'PARAMETER["lat_0",46' in wkt
        assert 'PARAMETER["lon_0",4.535' in wkt
        assert 'PARAMETER["o_lat_p",90' in wkt
        assert 'PARAMETER["o_lon_p",-5.465' in wkt
        assert new_ds.attrs["grid_mapping"] == "cosmo7"

        # c) Projection Transverse Mercator
        lat_0 = 36.5
        lon_0 = 15.0

        tmerc = AreaDefinition(
            area_id="tmerc",
            description="tmerc",
            proj_id="tmerc",
            projection={"proj": "tmerc", "ellps": "WGS84", "lat_0": 36.5, "lon_0": 15.0},
            width=2, height=2,
            area_extent=[-1, -1, 1, 1])

        tmerc_expected = xr.DataArray(data=0,
                                      attrs={"latitude_of_projection_origin": lat_0,
                                             "longitude_of_central_meridian": lon_0,
                                             "grid_mapping_name": "transverse_mercator",
                                             "reference_ellipsoid_name": "WGS 84",
                                             "false_easting": 0.,
                                             "false_northing": 0.,
                                             })

        ds = ds_base.copy()
        ds.attrs["area"] = tmerc
        new_ds, grid_mapping = _add_grid_mapping(ds)
        assert new_ds.attrs["grid_mapping"] == "tmerc"
        _gm_matches(grid_mapping, tmerc_expected)

        # d) Projection that has a representation but no explicit a/b
        h = 35785831.
        geos = AreaDefinition(
            area_id="geos",
            description="geos",
            proj_id="geos",
            projection={"proj": "geos", "h": h, "datum": "WGS84", "ellps": "GRS80",
                        "lat_0": 0, "lon_0": 0},
            width=2, height=2,
            area_extent=[-1, -1, 1, 1])
        geos_expected = xr.DataArray(data=0,
                                     attrs={"perspective_point_height": h,
                                            "latitude_of_projection_origin": 0,
                                            "longitude_of_projection_origin": 0,
                                            "grid_mapping_name": "geostationary",
                                            # 'semi_major_axis': 6378137.0,
                                            # 'semi_minor_axis': 6356752.314,
                                            # 'sweep_angle_axis': None,
                                            })

        ds = ds_base.copy()
        ds.attrs["area"] = geos
        new_ds, grid_mapping = _add_grid_mapping(ds)

        assert new_ds.attrs["grid_mapping"] == "geos"
        _gm_matches(grid_mapping, geos_expected)

        # e) oblique Mercator
        area = AreaDefinition(
            area_id="omerc_otf",
            description="On-the-fly omerc area",
            proj_id="omerc",
            projection={"alpha": "9.02638777018478", "ellps": "WGS84", "gamma": "0", "k": "1",
                        "lat_0": "-0.256794486098476", "lonc": "13.7888658224205",
                        "proj": "omerc", "units": "m"},
            width=2837,
            height=5940,
            area_extent=[-1460463.0893, 3455291.3877, 1538407.1158, 9615788.8787]
        )

        omerc_dict = {"azimuth_of_central_line": 9.02638777018478,
                      "false_easting": 0.,
                      "false_northing": 0.,
                      # 'gamma': 0,  # this is not CF compliant
                      "grid_mapping_name": "oblique_mercator",
                      "latitude_of_projection_origin": -0.256794486098476,
                      "longitude_of_projection_origin": 13.7888658224205,
                      # 'prime_meridian_name': "Greenwich",
                      "reference_ellipsoid_name": "WGS 84"}
        omerc_expected = xr.DataArray(data=0, attrs=omerc_dict)

        ds = ds_base.copy()
        ds.attrs["area"] = area
        new_ds, grid_mapping = _add_grid_mapping(ds)

        assert new_ds.attrs["grid_mapping"] == "omerc_otf"
        _gm_matches(grid_mapping, omerc_expected)

        # f) Projection that has a representation but no explicit a/b
        h = 35785831.
        geos = AreaDefinition(
            area_id="geos",
            description="geos",
            proj_id="geos",
            projection={"proj": "geos", "h": h, "datum": "WGS84", "ellps": "GRS80",
                        "lat_0": 0, "lon_0": 0},
            width=2, height=2,
            area_extent=[-1, -1, 1, 1])
        geos_expected = xr.DataArray(data=0,
                                     attrs={"perspective_point_height": h,
                                            "latitude_of_projection_origin": 0,
                                            "longitude_of_projection_origin": 0,
                                            "grid_mapping_name": "geostationary",
                                            "reference_ellipsoid_name": "WGS 84",
                                            })

        ds = ds_base.copy()
        ds.attrs["area"] = geos
        new_ds, grid_mapping = _add_grid_mapping(ds)

        assert new_ds.attrs["grid_mapping"] == "geos"
        _gm_matches(grid_mapping, geos_expected)

    @pytest.mark.parametrize("dims", [("y", "x"), ("bands", "y", "x")])
    def test_add_lonlat_coords(self, dims):
        """Test the conversion from areas to lon/lat."""
        from satpy.cf.area import _add_lonlat_coords

        area = AreaDefinition(
            "seviri",
            "Native SEVIRI grid",
            "geos",
            "+a=6378169.0 +h=35785831.0 +b=6356583.8 +lon_0=0 +proj=geos",
            2, 2,
            [-5570248.686685662, -5567248.28340708, 5567248.28340708, 5570248.686685662]
        )
        lons_ref, lats_ref = area.get_lonlats()
        if len(dims) == 2:
            data_arr = xr.DataArray(data=[[1, 2], [3, 4]], dims=dims, attrs={"area": area})
        else:
            data_arr = xr.DataArray(
                data=da.from_array(np.arange(3 * 10 * 10).reshape(3, 10, 10), chunks=(1, 5, 5)),
                dims=("bands", "y", "x"),
                attrs={"area": area},
            )

        res = _add_lonlat_coords(data_arr)

        # original should be unmodified
        assert "longitude" not in data_arr.coords
        assert set(res.coords) == {"longitude", "latitude"}
        lat = res["latitude"]
        lon = res["longitude"]
        np.testing.assert_array_equal(lat.data, lats_ref)
        np.testing.assert_array_equal(lon.data, lons_ref)
        assert {"name": "latitude", "standard_name": "latitude", "units": "degrees_north"}.items() <= lat.attrs.items()
        assert {"name": "longitude", "standard_name": "longitude", "units": "degrees_east"}.items() <= lon.attrs.items()
