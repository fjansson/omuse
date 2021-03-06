from __future__ import print_function
# -*- coding: utf-8 -*-
# %run make_eddy_tracker_list_obj.py

"""
===========================================================================
This file is part of py-eddy-tracker.

    py-eddy-tracker is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    py-eddy-tracker is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with py-eddy-tracker.  If not, see <http://www.gnu.org/licenses/>.

Copyright (c) 2014-2015 by Evan Mason
Email: emason@imedea.uib-csic.es
===========================================================================


make_eddy_tracker_list_obj.py

Version 2.0.6


===========================================================================


"""
from .py_eddy_tracker_classes import *
import scipy.spatial as spatial
import scipy.interpolate as interpolate
#from haversine import haversine # needs compiling with f2py
from . import haversine_distmat_python as haversine # pure python version
from operator import itemgetter

def haversine_distance_vector(lon1, lat1, lon2, lat2):
    """
    Haversine formula to calculate distance between two points
    Uses mean earth radius in metres (from scalars.h) = 6371315.0
    """
    #lon1 = np.asfortranarray(lon1)
    #lat1 = np.asfortranarray(lat1)
    #lon2 = np.asfortranarray(lon2)
    #lat2 = np.asfortranarray(lat2)
    #dist = np.empty_like(lon1, order='F')
    #haversine.distance_vector(lon1, lat1, lon2, lat2, dist)
    #return np.ascontiguousarray(dist)
    return haversine.distance_vector(lon1, lat1, lon2, lat2)


#def newPosition(lonin, latin, angle, distance):
    #"""
    #Given the inputs (base lon, base lat, angle, distance) return
    #the lon, lat of the new position...
    #"""
    #lonin = np.asfortranarray(lonin.copy())
    #latin = np.asfortranarray(latin.copy())
    #angle = np.asfortranarray(angle.copy())
    #distance = np.asfortranarray(distance.copy())
    #lonout = np.asfortranarray(np.empty(lonin.shape))
    #latout = np.asfortranarray(np.empty(lonin.shape))
    #haversine.waypoint_vector(lonin, latin, angle, distance, lonout, latout)
    #return np.ascontiguousarray(lonout), np.ascontiguousarray(latout)


def nearest(lon_pt, lat_pt, lon2d, lat2d, theshape):
    """
    Return the nearest i, j point to a given lon, lat point
    in a lat/lon grid
    """
    #print "nearest point for ", lon_pt , " ", lat_pt

    lon_pt += -lon2d
    lat_pt += -lat2d
    d = np.sqrt(lon_pt**2 + lat_pt**2)
    #print "argmin=", d.argmin()

    j, i = np.unravel_index(d.argmin(), theshape)
    #i = d.argmin(axis=0).min()
    #j = d.argmin(axis=1).min()
    #print i,j

    #from matplotlib import pyplot
    #pyplot.imshow(d)
    #pyplot.show()
    #raw_input()

    return i, j


def uniform_resample(x, y, **kwargs):#, method='interp1d', kind='linear'):
    """
    Resample contours to have (nearly) equal spacing
       x, y    : input contour coordinates
       num_fac : factor to increase lengths of output coordinates
       method  : currently only 'interp1d' or 'Akima'
                 (Akima is slightly slower, but may be more accurate)
       kind    : type of interpolation (interp1d only)
       extrapolate : IS NOT RELIABLE (sometimes nans occur)
    """
    if 'method' in kwargs:
        method = kwargs['method']
    else:
        method = 'interp1d'

    if 'extrapolate' in kwargs:
        extrapolate = kwargs['extrapolate']
    else:
        extrapolate = None
        
    if 'num_fac' in kwargs:
        num_fac = kwargs['num_fac']
    else:
        num_fac = 2

    # Get distances
    d = np.zeros_like(x)
    d[1:] = np.cumsum(haversine_distance_vector(
               x[:-1].copy(), y[:-1].copy(), x[1:].copy(), y[1:].copy()))
    # Get uniform distances
    d_uniform = np.linspace(0, d.max(), num=d.size * num_fac, endpoint=True)

    # Do 1d interpolations
    if strcompare('interp1d', method):
        if 'kind' in kwargs:
            kind = kwargs['kind']
        else:
            kind = 'linear'
        xfunc = interpolate.interp1d(d, x, kind=kind)
        yfunc = interpolate.interp1d(d, y, kind=kind)
        xnew = xfunc(d_uniform)
        ynew = yfunc(d_uniform)

    elif strcompare('akima', method):
        xfunc = interpolate.Akima1DInterpolator(d, x)
        yfunc = interpolate.Akima1DInterpolator(d, y)
        xnew = xfunc(d_uniform, extrapolate=extrapolate)
        ynew = yfunc(d_uniform, extrapolate=extrapolate)

    else:
        Exception

    return xnew, ynew


def strcompare(str1, str2):
    return str1 in str2 and str2 in str1


class Track (object):
    """
    Class that holds eddy tracks and related info
        index  - index to each 'track', or track_number
        lon    - longitude
        lat    - latitude
        ocean_time - roms time in seconds
        uavg   - average velocity within eddy contour
        radius_s - eddy radius (as Chelton etal 2011)
        radius_e - eddy radius (as Chelton etal 2011)
        amplitude - max(abs(vorticity/f)) within eddy (as Kurian etal 2011)
        temp
        salt
        bounds - array(imin,imax,jmin,jmax) defining location of eddy
                 qparam contour
        alive - True if eddy active, set to False when eddy becomes active
        saved2nc - Becomes True once saved to netcdf file
        dayzero - True at first appearance of eddy
    """

    def __init__(self, PRODUCT, lon, lat, time, uavg, teke,
                 radius_s, radius_e, amplitude, temp=None, salt=None,
                 save_extras=False, contour_e=None, contour_s=None,
                 uavg_profile=None, shape_error=None):

        #self.eddy_index = eddy_index
        self.PRODUCT = PRODUCT
        self.lon = [lon]
        self.lat = [lat]
        self.ocean_time = [time]
        self.uavg = [uavg]
        self.teke = [teke]
        self.radius_s = [radius_s] # speed-based eddy radius
        self.radius_e = [radius_e] # effective eddy radius
        self.amplitude = [amplitude]
        if 'ROMS' in self.PRODUCT:
            #self.temp = [temp]
            #self.salt = [salt]
            pass
        self.alive = True
        self.dayzero = True
        self.saved2nc = False
        self.save_extras = save_extras
        if self.save_extras:
            self.contour_e = [contour_e]
            self.contour_s = [contour_s]
            #self.uavg_profile = [uavg_profile]
            self.shape_error = [shape_error]

    def append_pos(self, lon, lat, time, uavg, teke, radius_s, radius_e,
                   amplitude, temp=None, salt=None, contour_e=None,
                   contour_s=None, uavg_profile=None, shape_error=None):
        """
        Append track updates
        """
        self.lon.append(lon)
        self.lat.append(lat)
        self.ocean_time.append(time)
        self.uavg.append(uavg)
        self.teke.append(teke)
        self.radius_s.append(radius_s)
        self.radius_e.append(radius_e)
        self.amplitude.append(amplitude)
        if 'ROMS' in self.PRODUCT:
            #self.temp = np.r_[self.temp, temp]
            #self.salt = np.r_[self.salt, salt]
            pass
        if self.save_extras:
            self.contour_e.append(contour_e)
            self.contour_s.append(contour_s)
            #self.uavg_profile.append(uavg_profile)
            #print self.shape_error, shape_error
            self.shape_error.append(shape_error)
        return self

    def _is_alive(self, rtime):
        """
        Query if eddy is still active
          rtime is current 'ocean_time'
        If not active, kill it
        """
        # The eddy...
        #print not self.alive, self.dayzero, self.ocean_time[-1] == rtime
        if not self.alive:  # is already dead
            #print '--AAA'
            return self.alive
        elif self.dayzero:  # has just been initiated
            #print '--BBB'
            self.dayzero = False
            return self.alive
        elif self.ocean_time[-1] == rtime:  # is still alive
            #print '--CCC'
            return self.alive
        else:
            self.alive = False  # is now dead
            return self.alive


class TrackList (object):
    """
    Class that holds list of eddy tracks:
        tracklist - the list of 'track' objects
        qparameter: Q parameter range used for contours
        new_lon, new_lat: new lon/lat centroids
        old_lon, old_lat: old lon/lat centroids
        index:   index of eddy in track_list
    """
    def __init__(self, SIGN_TYPE, SAVE_DIR, grd, search_ellipse,
                 **kwargs):
        """
        Initialise the list 'tracklist'
        """
        self.tracklist = []
        self.PRODUCT = grd.PRODUCT
        self.SIGN_TYPE = SIGN_TYPE
        self.SAVE_DIR = SAVE_DIR

        self.DIAGNOSTIC_TYPE = kwargs.get('DIAGNOSTIC_TYPE', 'SLA')

        self.THE_DOMAIN = kwargs.get('THE_DOMAIN', 'Regional')
        self.LONMIN = np.float64(kwargs.get('LONMIN', -40))
        self.LONMAX = np.float64(kwargs.get('LONMAX', -30))
        self.LATMIN = np.float64(kwargs.get('LATMIN', 20))
        self.LATMAX = np.float64(kwargs.get('LATMAX', 30))
        self.DATE_STR = np.float64(kwargs.get('DATE_STR', 20020101))
        self.DATE_END = np.float64(kwargs.get('DATE_END', 20020630))

        self.TRACK_DURATION_MIN = kwargs.get('TRACK_DURATION_MIN', 28)
        self.TRACK_EXTRA_VARIABLES = kwargs.get('TRACK_EXTRA_VARIABLES', False)
        self.INTERANNUAL = kwargs.get('INTERANNUAL', True)
        self.SEPARATION_METHOD = kwargs.get('SEPARATION_METHOD', 'ellipse')
        self.SMOOTHING = kwargs.get('SMOOTHING', True)
        self.MAX_LOCAL_EXTREMA = kwargs.get('MAX_LOCAL_EXTREMA', 1)

        self.INTERP_METHOD = kwargs.get('INTERP_METHOD', 'RectBivariate')
        self.JDAY_REFERENCE = kwargs.get('JDAY_REFERENCE', 2448623.0)

        # NOTE: '.copy()' suffix is essential here
        self.CONTOUR_PARAMETER = kwargs.get('CONTOUR_PARAMETER',
                                   np.arange(-100., 101, 1)).copy()
        self.INTERVAL = np.diff(self.CONTOUR_PARAMETER)[0]
        if 'Cyclonic' in SIGN_TYPE:
            self.CONTOUR_PARAMETER *= -1

        self.SHAPE_ERROR = kwargs.get('SHAPE_ERROR',
                              np.full(self.CONTOUR_PARAMETER.size, 55.))

        self.DAYS_BTWN_RECORDS = kwargs.get('DAYS_BTWN_RECORDS', 7.)

        self.RADMIN = np.float64(kwargs.get('RADMIN', 0.4))
        self.RADMAX = np.float64(kwargs.get('RADMAX', 4.461))
        self.AMPMIN = np.float64(kwargs.get('AMPMIN', 1.))
        self.AMPMAX = np.float64(kwargs.get('AMPMAX', 150.))

        self.EVOLVE_AMP_MIN = np.float64(kwargs.get('EVOLVE_AMP_MIN', 0.0005))
        self.EVOLVE_AMP_MAX = np.float64(kwargs.get('EVOLVE_AMP_MAX', 500))
        self.EVOLVE_AREA_MIN = np.float64(kwargs.get('EVOLVE_AREA_MIN', 0.0005))
        self.EVOLVE_AREA_MAX = np.float64(kwargs.get('EVOLVE_AREA_MAX', 500))

        self.AREA0 = np.pi * np.float64(kwargs.get('RAD0', 60000.))**2
        self.AMP0 = np.float64(kwargs.get('AMP0', 2.))
        self.DIST0 = np.float64(kwargs.get('DIST0', 25000.))

        self.SAVE_FIGURES = kwargs.get('SAVE_FIGURES', False)

        self.VERBOSE = kwargs.get('VERBOSE', False)

        self.M = grd.M
        self.points = np.array([grd.lon().ravel(),
                                grd.lat().ravel()]).T
        self.i0, self.i1 = grd.i0, grd.i1
        self.j0, self.j1 = grd.j0, grd.j1
        self.FILLVAL = grd.FILLVAL
        self.PRODUCT = grd.PRODUCT

        self.sla = None
        self.slacopy = None

        self.new_lon = []
        self.new_lat = []
        self.new_radii_s = []
        self.new_radii_e = []
        self.new_amp = []
        self.new_uavg = []
        self.new_teke = []
        if 'ROMS' in self.PRODUCT:
            self.new_temp = []
            self.new_salt = []
        # NOTE check if new_time and old_time are necessary... 
        self.new_time = []
        self.old_lon = []
        self.old_lat = []
        self.old_radii_s = []
        self.old_radii_e = []
        self.old_amp = []
        self.old_uavg = []
        self.old_teke = []
        if 'ROMS' in self.PRODUCT:
            #self.old_temp = []
            pass
            #self.old_salt = []
        self.old_time = []
        if self.TRACK_EXTRA_VARIABLES:
            self.new_contour_e = []
            self.new_contour_s = []
            #self.new_uavg_profile = []
            self.new_shape_error = []
            self.old_contour_e = []
            self.old_contour_s = []
            #self.old_uavg_profile = []
            self.old_shape_error = []
        self.new_list = True  # flag indicating new list
        self.index = 0  # counter
        self.ncind = 0  # index to write to nc files, will increase and increase
        self.ch_index = 0  # index for Chelton style nc files
        self.PAD = 2
        self.search_ellipse = None
        self.PIXEL_THRESHOLD = None
        # Check for a correct configuration
        configs = ['ROMS', 'AVISO', 'Generic']
        assert self.PRODUCT in configs, "".join(('Unknown string ',
                                        'in *PRODUCT* parameter'))

    def __getstate__(self):
        """
        Needed for Pickle
        """
        #print '--- removing unwanted attributes'
        pops = ('uspd', 'uspd_coeffs', 'sla_coeffs', 'points',
                'sla', 'slacopy', 'swirl',
                'mask_eff', 'mask_eff_sum', 'mask_eff_1d')
        result = self.__dict__.copy()
        for pop in pops:
            result.pop(pop)
        return result

    def add_new_track(self, lon, lat, time, uavg, teke,
                      radius_s, radius_e, amplitude, temp=None, salt=None,
                      contour_e=None, contour_s=None, uavg_profile=None,
                      shape_error=None):
        """
        Append a new 'track' object to the list
        """
        self.tracklist.append(Track(self.PRODUCT,
                                    lon, lat, time, uavg, teke,
                                    radius_s, radius_e, amplitude,
                                    temp, salt, self.TRACK_EXTRA_VARIABLES,
                                    contour_e, contour_s, uavg_profile,
                                    shape_error))

    def update_track(self, index, lon, lat, time, uavg, teke,
                     radius_s, radius_e, amplitude, temp=None, salt=None,
                     contour_e=None, contour_s=None, uavg_profile=None,
                     shape_error=None):
        """
        Update a track at index
        """
        self.tracklist[index].append_pos(
            lon, lat, time, uavg, teke,
            radius_s, radius_e, amplitude, temp=temp,
            salt=salt, contour_e=contour_e,
            contour_s=contour_s, uavg_profile=uavg_profile,
            shape_error=shape_error)

    def update_eddy_properties(self, properties):
        """
        Append new variable values to track arrays
        """
        self.new_lon_tmp.append(properties.centlon)
        self.new_lat_tmp.append(properties.centlat)
        self.new_radii_s_tmp.append(properties.eddy_radius_s)
        self.new_radii_e_tmp.append(properties.eddy_radius_e)
        self.new_amp_tmp.append(properties.amplitude)
        self.new_uavg_tmp.append(properties.uavg)
        self.new_teke_tmp.append(properties.teke)
        self.new_time_tmp.append(properties.rtime)

        if 'ROMS' in self.PRODUCT:
            #self.new_temp_tmp = np.r_[self.new_temp_tmp, properties.cent_temp]
            #self.new_salt_tmp = np.r_[self.new_salt_tmp, properties.cent_salt]
            pass
        
        if self.TRACK_EXTRA_VARIABLES:
            #print 'aaadddaaa', properties.contour_e
            self.new_contour_e_tmp.append(properties.contour_e)
            self.new_contour_s_tmp.append(properties.contour_s)
            #self.new_uavg_profile_tmp.append(properties.uavg_profile)
            self.new_shape_error_tmp = np.r_[self.new_shape_error_tmp,
                                             properties.shape_error]
        return self

    def reset_holding_variables(self):
        """
        Reset temporary holding variables to empty arrays
        """
        self.new_lon_tmp = [] #np.array([])
        self.new_lat_tmp = []
        self.new_radii_s_tmp = []
        self.new_radii_e_tmp = []
        self.new_amp_tmp = []
        self.new_uavg_tmp = []
        self.new_teke_tmp = []
        self.new_time_tmp = []
        self.new_temp_tmp = []
        self.new_salt_tmp = []
        #self.new_bounds_tmp = np.atleast_2d(np.empty(4, dtype=np.int16))
        if self.TRACK_EXTRA_VARIABLES:
            self.new_contour_e_tmp = []
            self.new_contour_s_tmp = []
            #self.new_uavg_profile_tmp = []
            self.new_shape_error_tmp = np.atleast_1d([])
        return

    def set_old_variables(self):
        """
        Pass all values at time k+1 to k
        """
        self.old_lon = list(self.new_lon_tmp)
        self.old_lat = list(self.new_lat_tmp)
        self.old_radii_s = list(self.new_radii_s_tmp)
        self.old_radii_e = list(self.new_radii_e_tmp)
        self.old_amp = list(self.new_amp_tmp)
        self.old_uavg = list(self.new_uavg_tmp)
        self.old_teke = list(self.new_teke_tmp)
        self.old_temp = list(self.new_temp_tmp)
        self.old_salt = list(self.new_salt_tmp)
        if self.TRACK_EXTRA_VARIABLES:
            self.old_contour_e = list(self.new_contour_e_tmp)
            self.old_contour_s = list(self.new_contour_s_tmp)
            #self.old_uavg_profile = list(self.new_uavg_profile_tmp)
            self.old_shape_error = np.atleast_1d([])

    def get_active_tracks(self, rtime):
        """
        Return list of indices to active tracks.
        A track is defined as active if the last record
        corresponds to current rtime (ocean_time).
        This call also identifies and removes
        inactive tracks.
        """
        active_tracks = []
        for i, track in enumerate(self.tracklist):
            if track._is_alive(rtime):
                active_tracks.append(i)
        return active_tracks

    def get_inactive_tracks(self, rtime, stopper=0):
        """
        Return list of indices to inactive tracks.
        This call also identifies and removes
        inactive tracks
        """
        inactive_tracks = []
        for i, track in enumerate(self.tracklist):
            if not track._is_alive(rtime):
                inactive_tracks.append(i)
        return inactive_tracks

    def kill_all_tracks(self):
        """
        Mark all tracks as not alive
        """
        for track in self.tracklist:
            track.alive = False
        print(('------ all %s tracks killed for final saving'
               % self.SIGN_TYPE.replace('one', 'onic').lower()))

    def create_netcdf(self, directory, savedir,
                      grd=None, YMIN=None, YMAX=None,
                      MMIN=None, MMAX=None, MODEL=None,
                      SIGMA_LEV=None, rho_ntr=None):
        """
        Create netcdf file same style as Chelton etal (2011)
        """
        if not self.TRACK_EXTRA_VARIABLES:
            self.savedir = savedir
        else:
            self.savedir = savedir.replace('.nc', '_ARGO_enabled.nc')
        nc = Dataset(self.savedir, 'w', format='NETCDF4')
        nc.title = ''.join((self.SIGN_TYPE, ' eddy tracks'))
        nc.directory = directory
        nc.PRODUCT = self.PRODUCT
        nc.DAYS_BTWN_RECORDS = np.float64(self.DAYS_BTWN_RECORDS)
        nc.TRACK_DURATION_MIN = np.float64(self.TRACK_DURATION_MIN)

        if 'Q' in self.DIAGNOSTIC_TYPE:
            nc.Q_parameter_contours = self.qparameter
        elif 'SLA' in self.DIAGNOSTIC_TYPE:
            nc.CONTOUR_PARAMETER = self.CONTOUR_PARAMETER
            nc.SHAPE_ERROR = self.SHAPE_ERROR[0]
            nc.PIXEL_THRESHOLD = self.PIXEL_THRESHOLD

        if self.SMOOTHING in locals():
            nc.SMOOTHING = np.str(self.SMOOTHING)
            nc.SMOOTH_FAC = np.float64(self.SMOOTH_FAC)
        else:
            nc.SMOOTHING = 'None'

        nc.i0 = np.int32(self.i0)
        nc.i1 = np.int32(self.i1)
        nc.j0 = np.int32(self.j0)
        nc.j1 = np.int32(self.j1)

        #nc.LONMIN = grd.LONMIN
        #nc.LONMAX = grd.LONMAX
        #nc.LATMIN = grd.LATMIN
        #nc.LATMAX = grd.LATMAX

        if 'ROMS' in self.PRODUCT:
            nc.ROMS_GRID = grd.GRDFILE
            nc.MODEL = MODEL
            nc.YMIN = np.int32(YMIN)
            nc.YMAX = np.int32(YMAX)
            nc.MMIN = np.int32(MMIN)
            nc.MMAX = np.int32(MMAX)
            nc.SIGMA_LEV_index = np.int32(SIGMA_LEV)

            if 'ip_roms' in MODEL:
                nc.rho_ntr = rho_ntr

        nc.EVOLVE_AMP_MIN = self.EVOLVE_AMP_MIN
        nc.EVOLVE_AMP_MAX = self.EVOLVE_AMP_MAX
        nc.EVOLVE_AREA_MIN = self.EVOLVE_AREA_MIN
        nc.EVOLVE_AREA_MAX = self.EVOLVE_AREA_MAX

        # Create dimensions
        nc.createDimension('Nobs', None)#len(Eddy.tracklist))
        #nc.createDimension('time', None) #len(maxlen(ocean_time)))
        #nc.createDimension('four', 4)

        # Create variables
        nc.createVariable('track', np.int32, ('Nobs'), fill_value=self.FILLVAL)   
        nc.createVariable('n', np.int32, ('Nobs'), fill_value=self.FILLVAL)  

        # Use of jday should depend on clim vs interann
        if self.INTERANNUAL: # AVISO or INTERANNUAL ROMS solution
            nc.createVariable('j1', np.int32, ('Nobs'), fill_value=self.FILLVAL)

        else: # climatological ROMS solution
            nc.createVariable('ocean_time', 'f8', ('Nobs'), fill_value=self.FILLVAL)

        nc.createVariable('cyc', np.int32, ('Nobs'), fill_value=self.FILLVAL)
        nc.createVariable('lon', 'f4', ('Nobs'), fill_value=self.FILLVAL)
        nc.createVariable('lat', 'f4', ('Nobs'), fill_value=self.FILLVAL)
        nc.createVariable('A', 'f4', ('Nobs'), fill_value=self.FILLVAL)
        nc.createVariable('L', 'f4', ('Nobs'), fill_value=self.FILLVAL)
        nc.createVariable('U', 'f4', ('Nobs'), fill_value=self.FILLVAL)
        nc.createVariable('Teke', 'f4', ('Nobs'), fill_value=self.FILLVAL)
        nc.createVariable('radius_e', 'f4', ('Nobs'), fill_value=self.FILLVAL)

        if 'Q' in self.DIAGNOSTIC_TYPE:
            nc.createVariable('qparameter', 'f4', ('Nobs'), fill_value=self.FILLVAL)

        if 'ROMS' in self.PRODUCT:
            #nc.createVariable('temp', 'f4', ('Nobs'), fill_value=self.FILLVAL)
            #nc.createVariable('salt', 'f4', ('Nobs'), fill_value=self.FILLVAL)
            pass
        #nc.createVariable('eddy_duration', np.int16, ('Nobs'), fill_value=self.FILLVAL)

        # Meta data for variables
        nc.variables['track'].units = 'ordinal'
        nc.variables['track'].min_val = np.int32(0)
        nc.variables['track'].max_val = np.int32(0)
        nc.variables['track'].long_name = 'track number'
        nc.variables['track'].description = 'eddy identification number'

        nc.variables['n'].units = 'ordinal'
        nc.variables['n'].long_name = 'observation number'
        # Add option here to set length of intervals.....
        nc.variables['n'].description = 'observation sequence number (XX day intervals)'

        ## Use of jday should depend on clim vs interann
        if self.INTERANNUAL: # AVISO or INTERANNUAL ROMS solution
            nc.variables['j1'].units = 'days'
            nc.variables['j1'].long_name = 'Julian date'
            nc.variables['j1'].description = 'date of this observation'
            nc.variables['j1'].reference = self.JDAY_REFERENCE
            nc.variables['j1'].reference_description = "".join(('Julian '
                'date on Jan 1, 1992'))

        else: # climatological ROMS solution
            nc.variables['ocean_time'].units = 'ROMS ocean_time (seconds)'

        #nc.variables['eddy_duration'].units = 'days'
        nc.variables['cyc'].units = 'boolean'
        nc.variables['cyc'].min_val = -1
        nc.variables['cyc'].max_val = 1
        nc.variables['cyc'].long_name = 'cyclonic'
        nc.variables['cyc'].description = 'cyclonic -1; anti-cyclonic +1'

        #nc.variables['eddy_duration'].units = 'days'
        nc.variables['lon'].units = 'deg. longitude'
        nc.variables['lon'].min_val = self.LONMIN
        nc.variables['lon'].max_val = self.LONMAX
        nc.variables['lat'].units = 'deg. latitude'
        nc.variables['lat'].min_val = self.LATMIN
        nc.variables['lat'].max_val = self.LATMAX

        if 'Q' in self.DIAGNOSTIC_TYPE:
            nc.variables['A'].units = 'None, normalised vorticity (abs(xi)/f)'

        elif 'SLA' in self.DIAGNOSTIC_TYPE:
            nc.variables['A'].units = 'cm'

        nc.variables['A'].min_val = self.AMPMIN
        nc.variables['A'].max_val = self.AMPMAX
        nc.variables['A'].long_name = 'amplitude'
        nc.variables['A'].description = "".join(('magnitude of the height ',
            'difference between the extremum of SSH within the eddy and the ',
            'SSH around the contour defining the eddy perimeter'))
        nc.variables['L'].units = 'km'
        nc.variables['L'].min_val = self.RADMIN / 1000.
        nc.variables['L'].max_val = self.RADMAX / 1000.
        nc.variables['L'].long_name = 'speed radius scale'
        nc.variables['L'].description = "".join(('radius of a circle whose ',
            'area is equal to that enclosed by the contour of maximum ',
            'circum-average speed'))

        nc.variables['U'].units = 'cm/sec'
        #nc.variables['U'].min = 0.
        #nc.variables['U'].max = 376.6
        nc.variables['U'].long_name = 'maximum circum-averaged speed'
        nc.variables['U'].description = "".join(('average speed of the ',
            'contour defining the radius scale L'))
        nc.variables['Teke'].units = 'm^2/sec^2'
        #nc.variables['Teke'].min = 0.
        #nc.variables['Teke'].max = 376.6
        nc.variables['Teke'].long_name = 'sum EKE within contour Ceff'
        nc.variables['Teke'].description = "".join(('sum of eddy kinetic ',
            'energy within contour defining the effective radius'))

        nc.variables['radius_e'].units = 'km'
        nc.variables['radius_e'].min_val = self.RADMIN / 1000.
        nc.variables['radius_e'].max_val = self.RADMAX / 1000.
        nc.variables['radius_e'].long_name = 'effective radius scale'
        nc.variables['radius_e'].description = 'effective eddy radius'

        if 'Q' in self.DIAGNOSTIC_TYPE:
            nc.variables['qparameter'].units = 's^{-2}'

        if 'ROMS' in self.PRODUCT:
            #nc.variables['temp'].units = 'deg. C'
            #nc.variables['salt'].units = 'psu'
            pass

        if self.TRACK_EXTRA_VARIABLES:

            nc.createDimension('contour_points', None)
            #nc.createDimension('uavg_contour_count',
                #np.int(self.CONTOUR_PARAMETER.size * 0.333))
            nc.createVariable('contour_e', 'f4',
                ('contour_points', 'Nobs'), fill_value=self.FILLVAL)
            nc.createVariable('contour_s', 'f4',
                ('contour_points', 'Nobs'), fill_value=self.FILLVAL)
            #nc.createVariable('uavg_profile', 'f4',
                #('uavg_contour_count','Nobs'), fill_value=self.FILLVAL)
            nc.createVariable('shape_error', 'f4',
                ('Nobs'), fill_value=self.FILLVAL)

            nc.variables['contour_e'].long_name = "".join(('positions of ',
                'effective contour points'))
            nc.variables['contour_e'].description = "".join(('lons/lats of ',
                'effective contour points; lons (lats) in first (last) ',
                'half of vector'))
            nc.variables['contour_s'].long_name = "".join(('positions of ',
                'speed-based contour points'))
            nc.variables['contour_s'].description = "".join(('lons/lats of ',
                'speed-based contour points; lons (lats) in first (last) ',
                'half of vector'))
            #nc.variables['uavg_profile'].long_name = 'radial profile of uavg'
            #nc.variables['uavg_profile'].description = "".join(('all uavg ',
                #'values from effective contour inwards to ',
                #'smallest inner contour (pixel == 1)'))
            nc.variables['shape_error'].units = '%'

        nc.close()

    def _reduce_inactive_tracks(self):
        """
        Remove dead tracks
        """
        for track in self.tracklist:
            if not track.alive:
                del track.lon[:]
                del track.lat[:]
                del track.amplitude[:]
                #track.__delattr__('amplitude')
                del track.uavg[:]
                del track.teke[:]
                del track.radius_s[:]
                del track.radius_e[:]
                del track.ocean_time[:]
                if self.TRACK_EXTRA_VARIABLES:
                    del track.contour_e[:]
                    del track.contour_s[:]
                    #del track.uavg_profile[:]
                    del track.shape_error[:]
        return

    def _remove_inactive_tracks(self):
        """
        Remove dead tracks from self.tracklist and
        return indices to active tracks.
        """
        new_tracklist = []
        for track in self.tracklist:
            new_tracklist.append(track.alive)
        #print new_tracklist
        alive_inds = np.nonzero(new_tracklist)[0]
        #print alive_inds.shape
        tracklist = np.array(self.tracklist)[alive_inds]
        self.tracklist = tracklist.tolist()
        return alive_inds

    def write2netcdf(self, rtime, stopper=0):
        """
        Write inactive tracks to netcdf file.
        'ncind' is important because prevents writing of
        already written tracks.
        Each inactive track is 'emptied' after saving
        
        rtime - current timestamp
        stopper - dummy value (either 0 or 1)
        """
        rtime += stopper
        tracks2save = np.array([self.get_inactive_tracks(rtime)])
        DBR = self.DAYS_BTWN_RECORDS

        if np.any(tracks2save): # Note, this could break if all eddies become inactive at same time

            with Dataset(self.savedir, 'a') as nc:

                for i in np.nditer(tracks2save):

                    # saved2nc is a flag indicating if track[i] has been saved
                    if (not self.tracklist[i].saved2nc) and \
                       (np.all(self.tracklist[i].ocean_time)):

                        tsize = len(self.tracklist[i].lon)

                        if (tsize >= self.TRACK_DURATION_MIN / DBR) and tsize >= 1.:
                            lon = np.array([self.tracklist[i].lon])
                            lat = np.array([self.tracklist[i].lat])
                            amp = np.array([self.tracklist[i].amplitude])
                            uavg = np.array([self.tracklist[i].uavg]) * 100. # to cm/s
                            teke = np.array([self.tracklist[i].teke])
                            radius_s = np.array([self.tracklist[i].radius_s]) * 1e-3 # to km
                            radius_e = np.array([self.tracklist[i].radius_e]) * 1e-3 # to km
                            n = np.arange(tsize, dtype=np.int32)
                            track = np.full(tsize, self.ch_index)
                            if 'Anticyclonic' in self.SIGN_TYPE:
                                cyc = np.full(tsize, 1)
                            elif 'Cyclonic' in self.SIGN_TYPE:
                                cyc = np.full(tsize, -1)
                            track_max_val = np.array([nc.variables['track'].max_val,
                                                      np.int32(self.ch_index)]).max()
                            #print self.tracklist[i].ocean_time
                            #exit()
                            #eddy_duration = np.array([self.tracklist[i].ocean_time]).ptp()

                            tend = self.ncind + tsize
                            nc.variables['cyc'][self.ncind:tend] = cyc
                            nc.variables['lon'][self.ncind:tend] = lon
                            nc.variables['lat'][self.ncind:tend] = lat
                            nc.variables['A'][self.ncind:tend] = amp
                            nc.variables['U'][self.ncind:tend] = uavg
                            nc.variables['Teke'][self.ncind:tend] = teke
                            nc.variables['L'][self.ncind:tend] = radius_s
                            nc.variables['radius_e'][self.ncind:tend] = radius_e
                            nc.variables['n'][self.ncind:tend] = n
                            nc.variables['track'][self.ncind:tend] = track
                            nc.variables['track'].max_val = track_max_val
                            #nc.variables['eddy_duration'][self.ncind:tend] = eddy_duration

                            if 'ROMS' in self.PRODUCT:
                                #temp = np.array([self.tracklist[i].temp])
                                #salt = np.array([self.tracklist[i].salt])
                                pass
                                #nc.variables['temp'][self.ncind:tend] = temp
                                #nc.variables['salt'][self.ncind:tend] = salt

                            if self.INTERANNUAL:
                                # We add 1 because 'j1' is an integer in ncsavefile; julian day midnight has .5
                                # i.e., dt.julian2num(2448909.5) -> 727485.0
                                j1 = dt.num2julian(np.array([self.tracklist[i].ocean_time])) + 1
                                nc.variables['j1'][self.ncind:tend] = j1

                            else:
                                ocean_time = np.array([self.tracklist[i].ocean_time])
                                nc.variables['ocean_time'][self.ncind:tend] = ocean_time

                            if self.TRACK_EXTRA_VARIABLES:
                                shape_error = np.array([self.tracklist[i].shape_error])
                                nc.variables['shape_error'][self.ncind:tend] = shape_error

                                for j in np.arange(tend - self.ncind):
                                    jj = j + self.ncind
                                    contour_e_arr = np.array([self.tracklist[i].contour_e[j]]).ravel()
                                    contour_s_arr = np.array([self.tracklist[i].contour_s[j]]).ravel()
                                    #uavg_profile_arr = np.array([self.tracklist[i].uavg_profile[j]]).ravel()
                                    nc.variables['contour_e'][:contour_e_arr.size, jj] = contour_e_arr
                                    nc.variables['contour_s'][:contour_s_arr.size, jj] = contour_s_arr
                                    nc.variables['contour_s'][contour_s_arr.size:, jj] = self.FILLVAL
                                    #nc.variables['uavg_profile'][:uavg_profile_arr.size, jj] = uavg_profile_arr

                            # Flag indicating track[i] is now saved
                            self.tracklist[i].saved2nc = True
                            self.ncind += tsize
                            self.ch_index += 1
                            nc.sync()

        # Print final message and return
        if stopper:
            print(('All %ss saved' % self.SIGN_TYPE.replace('one', 'onic').lower()))
            return

        # Get index to first currently active track
        #try:
            #lasti = self.get_active_tracks(rtime)[0]
        #except Exception:
            #lasti = None

        # Remove inactive tracks
        # NOTE: line below used to be below clipping lines below
        #self._reduce_inactive_tracks()
        alive_i = self._remove_inactive_tracks()
        # Clip the tracklist,
        # removes all dead tracks preceding first currently active track
        #self.tracklist = self.tracklist[alive_i:]
        self.index = len(self.tracklist) # adjust index accordingly


        # Update old_lon and old_lat...
        self.old_lon = np.array(self.new_lon)[alive_i].tolist()
        self.old_lat = np.array(self.new_lat)[alive_i].tolist()
        self.old_radii_s = np.array(self.new_radii_s)[alive_i].tolist()
        self.old_radii_e = np.array(self.new_radii_e)[alive_i].tolist()
        self.old_amp = np.array(self.new_amp)[alive_i].tolist()
        self.old_uavg = np.array(self.new_uavg)[alive_i].tolist()
        self.old_teke = np.array(self.new_teke)[alive_i].tolist()

        del(self.new_lon[:])
        del(self.new_lat[:])
        del(self.new_radii_s[:])
        del(self.new_radii_e[:])
        del(self.new_amp[:])
        del(self.new_uavg[:])
        del(self.new_teke[:])
        del(self.new_time[:])

        if 'ROMS' in self.PRODUCT:
            #self.old_temp = self.new_temp[alive_i:]
            #self.old_salt = self.new_salt[alive_i:]
            pass
            #self.new_temp = []
            #self.new_salt = []

        if self.TRACK_EXTRA_VARIABLES:
            #print 'self.new_contour_e', self.new_contour_e
            #print 'ddddddd', alive_i
            #print 'fffffffff', self.new_contour_e[alive_i]
            # http://stackoverflow.com/questions/18272160/access-multiple-elements-of-list-knowing-their-index
            self.old_contour_e = itemgetter(*alive_i)(self.new_contour_e)
            #self.old_contour_e = list(self.new_contour_e[alive_i])
            self.old_contour_s = itemgetter(*alive_i)(self.new_contour_s)
            #self.old_uavg_profile = list(self.new_uavg_profile[alive_i])
            self.old_shape_error = np.array(self.new_shape_error)[alive_i].tolist()

            del(self.new_contour_e[:])
            del(self.new_contour_s[:])
            #del(self.new_uavg_profile[:])
            del(self.new_shape_error[:])

        return self

    def insert_at_index(self, xarr, ind, x):
        """
        This the same as Matlab's native functionality:
            x(3)=4 gives [0  0  4] and then
            x(5)=7 gives [0  0  4  0  7]
        """
        try:
            x = x[0]
        except Exception:
            pass

        val = getattr(self, xarr)
        try:
            val[ind] = x
        except:
            val.extend([0] * (ind - len(val) + 1))
            val[ind] = x
        setattr(self, xarr, val)

    def set_bounds(self, contlon, contlat, grd):
        """
        Get indices to a bounding box around the eddy
        WARNING won't work for a rotated grid
        """
        lonmin, lonmax = contlon.min(), contlon.max()
        latmin, latmax = contlat.min(), contlat.max()
        bl_i, bl_j = nearest(lonmin, latmin, grd.lon(), grd.lat(), grd.shape)
        tl_i, tl_j = nearest(lonmin, latmax, grd.lon(), grd.lat(), grd.shape)
        br_i, br_j = nearest(lonmax, latmin, grd.lon(), grd.lat(), grd.shape)
        tr_i, tr_j = nearest(lonmax, latmax, grd.lon(), grd.lat(), grd.shape)

        iarr = np.array([bl_i, tl_i, br_i, tr_i])
        jarr = np.array([bl_j, tl_j, br_j, tr_j])
        self.imin, self.imax = iarr.min(), iarr.max()
        self.jmin, self.jmax = jarr.min(), jarr.max()

        # For indexing the mins must not be less than zero
        self.imin = np.maximum(self.imin - self.PAD, 0)
        self.jmin = np.maximum(self.jmin - self.PAD, 0)
        self.imax += self.PAD + 1
        self.jmax += self.PAD + 1
        return self

    def set_mask_eff(self, contour, grd):
        """
        Set points within bounding box around eddy and calculate
        mask for effective contour
        """
        self.points = np.array([grd.lon()[self.jmin:self.jmax,
                                          self.imin:self.imax].ravel(),
                                grd.lat()[self.jmin:self.jmax,
                                          self.imin:self.imax].ravel()]).T
        # NOTE: Path.contains_points requires matplotlib 1.2 or higher
        self.mask_eff_1d = contour.contains_points(self.points)
        self.mask_eff_sum = self.mask_eff_1d.sum()
        return self

    def reshape_mask_eff(self, grd):
        """
        """
        shape = grd.lon()[self.jmin:self.jmax, self.imin:self.imax].shape
        self.mask_eff = self.mask_eff_1d.reshape(shape)


class RossbyWaveSpeed (object):

    def __init__(self, THE_DOMAIN, grd, RW_PATH=None):
        """
        Instantiate the RossbyWaveSpeed object
        """
        self.THE_DOMAIN = THE_DOMAIN
        self.M = grd.M
        self.EARTH_RADIUS = grd.EARTH_RADIUS
        self.ZERO_CROSSING = grd.ZERO_CROSSING
        self.RW_PATH = RW_PATH
        self._tree = None
        if self.THE_DOMAIN in ('Global', 'Regional', 'ROMS'):
            assert self.RW_PATH is not None, \
                'Must supply a path for the Rossby deformation radius data'
            data = np.loadtxt(RW_PATH)
            self._lon = data[:, 1] 
            self._lat = data[:, 0]
            self._defrad = data[:, 3]
            self.limits = [grd.LONMIN, grd.LONMAX, grd.LATMIN, grd.LATMAX]
            if grd.LONMIN < 0:
                self._lon -= 360.
            self._make_subset()._make_kdtree()
            self.vartype = 'variable'
        else:
            self.vartype = 'constant'
        self.distance = np.empty(1)
        self.beta = np.empty(1)
        self.r_spd_long = np.empty(1)
        self.start = True
        self.pio180 = np.pi / 180.

    def __getstate__(self):
        """
        Needed for Pickle
        """
        result = self.__dict__.copy()
        result.pop('_tree')
        return result

    def __setstate__(self, thedict):
        """
        Needed for Pickle
        """
        self.__dict__ = thedict
        self._make_kdtree()

    def get_rwdistance(self, xpt, ypt, DAYS_BTWN_RECORDS):
        """
        Return the distance required by SearchEllipse
        to construct a search ellipse for eddy tracking.
        """
        def get_lon_lat(xpt, ypt):
            """
            
            """
            lon, lat = self.M.projtran(xpt, ypt, inverse=True)
            lon, lat = np.round(lon, 2), np.round(lat, 2)
            if lon < 0.:
                lon = "".join((str(lon), 'W'))
            elif lon >= 0:
                lon = "".join((str(lon), 'E'))
            if lat < 0:
                lat = "".join((str(lat), 'S'))
            elif lat >= 0:
                lat = "".join((str(lat), 'N'))
            return lon, lat
            
        if self.THE_DOMAIN in ('Global', 'Regional', 'ROMS'):
            #print 'xpt, ypt', xpt, ypt
            self.distance[:] = self._get_rlongwave_spd(xpt, ypt)
            self.distance *= 86400.
            #if self.THE_DOMAIN in 'ROMS':
                #self.distance *= 1.5

        elif 'BlackSea' in self.THE_DOMAIN:
            self.distance[:] = 15000.  # e.g., Blokhina & Afanasyev, 2003

        elif 'MedSea' in self.THE_DOMAIN:
            self.distance[:] = 20000.

        else:
            Exception  # Unknown THE_DOMAIN

        if self.start:
            lon, lat = get_lon_lat(xpt, ypt)
            if 'Global' in self.THE_DOMAIN:
                print("".join(('--------- setting ellipse for first tracked ',
                            'eddy at %s, %s in the %s domain'
                                % (lon, lat, self.THE_DOMAIN))))
                c = np.abs(self._get_rlongwave_spd(xpt, ypt))[0]
                print("".join(('--------- with extratropical long baroclinic ',
                            'Rossby wave phase speed of %s m/s' % c)))
            elif self.THE_DOMAIN in ('BlackSea', 'MedSea'):
                print("".join(('--------- setting search radius of %s m for '
                                % self.distance[0],
                            'first tracked eddy at %s, %s in the %s domain'
                                % (lon, lat, self.THE_DOMAIN))))
            else:
                Exception
            self.start = False

        self.distance = np.abs(self.distance)
        return self.distance * DAYS_BTWN_RECORDS

    def _make_subset(self):
        """
        Make a subset of _defrad data over the domain.
        If 'Global' is defined then widen the domain.
        """
        pad = 1.5  # degrees
        LONMIN, LONMAX, LATMIN, LATMAX = self.limits

        if self.ZERO_CROSSING:
            ieast, iwest = (((self._lon + 360.) <= LONMAX + pad),
                            (self._lon > LONMIN + pad))
            self._lon[ieast] += 360.
            lloi = iwest + ieast
        else:
            lloi = np.logical_and(self._lon >= LONMIN - pad,
                                  self._lon <= LONMAX + pad)
        lloi *= np.logical_and(self._lat >= LATMIN - pad,
                               self._lat <= LATMAX + pad)
        self._lon = self._lon[lloi]
        self._lat = self._lat[lloi]
        self._defrad = self._defrad[lloi]

        if 'Global' in self.THE_DOMAIN:
            lloi = self._lon > 260.
            self._lon = np.append(self._lon, self._lon[lloi] - 360.)
            self._lat = np.append(self._lat, self._lat[lloi])
            self._defrad = np.append(self._defrad, self._defrad[lloi])

        self.x, self.y = self.M(self._lon, self._lat)
        return self

    def _make_kdtree(self):
        """
        Compute KDE tree for nearest indices.
        """
        points = np.vstack([self.x, self.y]).T
        self._tree = spatial.cKDTree(points)
        return self

    def _get_defrad(self, xpt, ypt):
        """
        Get a point average of the deformation radius
        at xpt, ypt
        """
        weights, i = self._tree.query(np.array([xpt, ypt]), k=4, p=2)
        weights /= weights.sum()
        self._weights = weights
        self.i = i
        return np.average(self._defrad[i], weights=weights)

    def _get_rlongwave_spd(self, xpt, ypt):
        """
        Get the longwave phase speed, see Chelton etal (1998) pg 446:
          c = -beta * defrad ** 2 (this only for extratropical waves...)
        """
        self.r_spd_long[:] = self._get_defrad(xpt, ypt)
        self.r_spd_long *= 1000.  # km to m
        self.r_spd_long **= 2
        self.beta[:] = np.average(self._lat[self.i],
                                  weights=self._weights)  # lat
        self.beta[:] = np.cos(self.pio180 * self.beta)
        self.beta *= 1458e-7  # 1458e-7 ~ (2 * 7.29*10**-5)
        self.beta /= self.EARTH_RADIUS
        self.r_spd_long *= -self.beta
        return self.r_spd_long

    def view_grid_subset(self):
        """
        Figure to check RossbyWaveSpeed grid after call to
        self._make_subset()
        To use, uncomment in SearchEllipse __init__ method
        """
        stride = 30
        plt.figure()
        ax = plt.subplot()
        self.M.scatter(self.x, self.y, c='b')
        self.M.drawcoastlines()
        self.M.fillcontinents()
        self.M.drawparallels(np.arange(-90, 90. + stride, stride),
                             labels=[1, 0, 0, 0], ax=ax)
        self.M.drawmeridians(np.arange(-360, 360. + stride, stride),
                             labels=[0, 0, 0, 1], ax=ax)
        plt.show()


class SearchEllipse (object):
    """
    Class to construct a search ellipse/circle around a specified point.
    See CSS11 Appendix B.4. "Automated eddy tracking" for details.
    """
    def __init__(self, THE_DOMAIN, grd, DAYS_BTWN_RECORDS, RW_PATH=None):
        """
        Set the constant dimensions of the search ellipse.
        Instantiate a RossbyWaveSpeed object

        Arguments:

          *THE_DOMAIN*: string
            Refers to THE_DOMAIN specified in yaml configuration file

          *grd*: An AvisoGrid or RomsGrid object.

          *DAYS_BTWN_RECORDS*: integer
            Constant defined in yaml configuration file.

          *RW_PATH*: string
            Path to rossrad.dat file, specified in yaml configuration file.
        """
        self.THE_DOMAIN = THE_DOMAIN
        self.DAYS_BTWN_RECORDS = DAYS_BTWN_RECORDS
        """NOTE: Testing for use of 'fac' below. Motivation is observation that CSS11
        recommended 3e5 causes lost eddies for DAYS_BTWN_RECORDS of 7. Increasing
        from 3e5 to 6e5 with DAYS_BTWN_RECORDS of 1 fixed observed incorrect 
        lost eddies."""
        fac = np.linspace(2, 1, num=7)[DAYS_BTWN_RECORDS - 1]
        self.e_w_major = self.DAYS_BTWN_RECORDS * fac * 3e5 / 7.
        self.n_s_minor = self.DAYS_BTWN_RECORDS * fac * 3e5 / 7.
        self.semi_n_s_minor = 0.5 * self.n_s_minor
        self.rwv = RossbyWaveSpeed(THE_DOMAIN, grd, RW_PATH=RW_PATH)
        #self.rwv.view_grid_subset() # debug; not relevant for MedSea / BlackSea
        self.rw_c = np.empty(1)
        self.rw_c_mod = np.empty(1)
        self.rw_c_fac = 1.75

    def _set_east_ellipse(self):
        """
        The *east_ellipse* is a full ellipse, but only its eastern
        part is used to build the search ellipse.
        """
        self.east_ellipse = patch.Ellipse((self.xpt, self.ypt),
                                          self.e_w_major, self.n_s_minor)
        return self

    def _set_west_ellipse(self):
        """
        The *west_ellipse* is a full ellipse, but only its western
        part is used to build the search ellipse.
        """
        self.west_ellipse = patch.Ellipse((self.xpt, self.ypt),
                                          self.rw_c_mod, self.n_s_minor)
        return self

    def _set_global_ellipse(self):
        """
        Set a Path object *ellipse_path* built from the eastern vertices of
        *east_ellipse* and the western vertices of *west_ellipse*.
        """
        self._set_east_ellipse()._set_west_ellipse()
        e_verts = self.east_ellipse.get_verts()
        e_size = e_verts[:, 0].size
        e_size *= 0.5
        w_verts = self.west_ellipse.get_verts()
        w_size = w_verts[:, 0].size
        w_size *= 0.5
        ew_x = np.hstack((e_verts[e_size:, 0], w_verts[:w_size, 0]))
        ew_y = np.hstack((e_verts[e_size:, 1], w_verts[:w_size, 1]))
        #print self.xpt, ew_x.min(), ew_x.max()
        if ew_x.max() - self.xpt > self.xpt - ew_x.min():
            ew_x = np.hstack((w_verts[w_size:, 0], e_verts[:e_size, 0]))
            ew_y = np.hstack((w_verts[w_size:, 1], e_verts[:e_size, 1]))
        self.ellipse_path = path.Path(np.array([ew_x, ew_y]).T)

    def _set_black_sea_ellipse(self):
        """
        Set *ellipse_path* for the *black_sea_ellipse*.
        """
        self.black_sea_ellipse = patch.Ellipse((self.xpt, self.ypt),
                               2. * self.rw_c_mod, 2. * self.rw_c_mod)
        verts = self.black_sea_ellipse.get_verts()
        self.ellipse_path = path.Path(np.array([verts[:, 0],
                                                verts[:, 1]]).T)
        return self

    def set_search_ellipse(self, xpt, ypt):
        """
        Set the search ellipse around a point.

        args:

            *xpt*: lon coordinate (Basemap projection)

            *ypt*: lat coordinate (Basemap projection)

        """
        self.xpt = xpt
        self.ypt = ypt
        self.rw_c_mod[:] = 1.75

        if self.THE_DOMAIN in ('Global', 'Regional', 'ROMS'):
            self.rw_c[:] = self.rwv.get_rwdistance(xpt, ypt,
                                  self.DAYS_BTWN_RECORDS)
            self.rw_c_mod *= self.rw_c
            self.rw_c_mod[:] = np.array([self.rw_c_mod,
                                         self.semi_n_s_minor]).max()
            #self.rw_c_mod *= 2. #Ben: I don't understand why this is multiplied by 2.0
            self._set_global_ellipse()

        elif self.THE_DOMAIN in ('BlackSea', 'MedSea'):
            self.rw_c[:] = self.rwv.get_rwdistance(xpt, ypt,
                                   self.DAYS_BTWN_RECORDS)
            self.rw_c_mod *= self.rw_c
            self._set_black_sea_ellipse()

        else:
            Exception

        return self

    def view_search_ellipse(self, Eddy):
        """
        Input A_eddy or C_eddy
        """
        plt.figure()
        ax = plt.subplot()
        #ax.set_title('Rossby def. rad %s m' %self.rw_c[0])
        Eddy.M.scatter(self.xpt, self.ypt, c='b')
        Eddy.M.plot(self.ellipse_path.vertices[:, 0],
                    self.ellipse_path.vertices[:, 1], 'r')
        Eddy.M.drawcoastlines()
        stride = .5
        Eddy.M.drawparallels(np.arange(-90, 90.+stride, stride),
                             labels=[1, 0, 0, 0], ax=ax)
        Eddy.M.drawmeridians(np.arange(-360, 360. + stride, stride),
                             labels=[0, 0, 0, 1], ax=ax)
        plt.show()

"""
def pickle_track(track_list, file):
    file = open(file, 'wb')
    pickle.dump(track_list, file)
    file.close()
    return

def unpickle_track(file):
    file = open(file, 'rb')
    data = pickle.load(file)
    file.close()
    return data
"""
##############################################################


if __name__ == '__main__':

    lon_ini = -10.
    lat_ini = 25.
    time_ini = 247893
    index = 0

    trackA = track_list(index, lon_ini, lat_ini, time_ini, 0, 0)
    print('trackA lon:', trackA.tracklist[0].lon)

    # update track 0
    trackA.update_track(0, -22, 34, 333344, 0, 0)
    trackA.update_track(0, -87, 37, 443344, 0, 0)
    trackA.update_track(0, -57, 57, 543344, 0, 0)
    print('trackA lon:', trackA.tracklist[0].lon)

    # start a new track
    trackA.append_list(-33, 45, 57435, 0, 0)
    print('\ntrackA lat:', trackA.tracklist[1].lat)

    trackA.update_track(1, -32, 32, 4453344, 0, 0)
    print('trackA lat:', trackA.tracklist[1].lat)

    # Pickle
    output = open('data.pkl', 'wb')
    pickle.dump(trackA, output)
    output.close()

    # Unpickle
    pkl_file = open('data.pkl', 'rb')
    data1 = pickle.load(pkl_file)
    pkl_file.close()
