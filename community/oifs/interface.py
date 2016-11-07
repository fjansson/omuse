import os.path
from omuse.units import units
from amuse.community.interface.common import CommonCodeInterface, CommonCode
from amuse.support.interface import InCodeComponentImplementation
from amuse.support.literature import LiteratureReferencesMixIn
from amuse.rfi.core import CodeInterface,LegacyFunctionSpecification
from amuse.rfi.core import legacy_function,remote_function
from amuse.units.core import system,no_system
from amuse.community.interface.stopping_conditions import StoppingConditionInterface, StoppingConditions
from amuse import datamodel

from amuse.units import trigo

class OpenIFSInterface(CodeInterface,
                       CommonCodeInterface,
                       StoppingConditionInterface,
                       LiteratureReferencesMixIn):
    """

    OpenIFS: The Open Integral Forecasting System

    """
    use_modules=["StoppingConditions","openifs_interface"]

    # Constructor
    def __init__(self, **options):
        CodeInterface.__init__(self, name_of_the_worker = self.name_of_the_worker(), **options)
        LiteratureReferencesMixIn.__init__(self)

    # Determines worker binary name
    def name_of_the_worker(self):
        return "openifs_worker"

    # Returns model internal time in sec.
    @remote_function
    def get_model_time():
        returns (time = 0. | units.s)

    # Returns the model time step in sec.
    @remote_function
    def get_timestep():
        returns (dt = 0. | units.s)

    # Inserts grid, not yet implemented
    @remote_function
    def commit_grid():
        pass

    # Utility method returning vertical temperature profiles.
    # Second argument is assumed to be the full vertical range
    @remote_function(must_handle_array=True)
    def get_profiles_T_(i = 0,k = 0):
        returns (out = 0. | units.K)

    # Utility method returning the full temperature field.
    # Both arguments are assumed to be resp. horizontal and vertical full index ranges
    @remote_function(must_handle_array=True)
    def get_field_T_(i = 0,k = 0):
        returns (out = 0. | units.K)

    # Utility method returning the gridpoint latitudes.
    # Argument is assumed to be the full horizontal range.
    @remote_function(must_handle_array=True)
    def get_gridpoint_lats_(i = 0):
        returns (out = 0. | units.rad)

    # Utility method returning the gridpoint longitudes.
    # Argument is assumed to be the full horizontal range.
    @remote_function(must_handle_array=True)
    def get_gridpoint_lons_(i = 0):
        returns (out = 0. | units.rad)

    # Returns the horizontal and vertical index ranges
    @remote_function
    def get_grid_sizes():
        returns (i=1,k=1)

    # Model evolution function
    @remote_function
    def evolve_model(tend = 0. | units.s):
        pass

# OpenIFS class implementation
class OpenIFS(CommonCode):

    # Constructor
    def __init__(self,**options):
        CommonCode.__init__(self,  OpenIFSInterface(**options), **options)
        self.stopping_conditions = StoppingConditions(self)
        self.itot = 0
        self.ktot = 0
        self.latitudes = None
        self.longitudes = None

    # Commit run parameters, not implemented yet
    def commit_parameters(self):
        self.overridden().commit_parameters()

    # Commit grid, reads grid size and fills geometry cache
    def commit_grid(self):
        self.overridden.commit_grid()
        self.itot,self.ktot = self.get_grid_sizes()
        self.latitudes = self.get_gridpoint_lats_(numpy.zeros(self.itot))
        self.longitudes = self.get_gridpoint_lons_(numpy.zeros(self.itot))

    # State machine definition
    def define_state(self, object):
        object.set_initial_state("UNINITIALIZED")
        object.add_transition("UNINITIALIZED","INITIALIZED","initialize_code")
        object.add_method("UNINITIALIZED","before_get_parameter")
        object.add_method("!UNINITIALIZED","before_set_parameter")
        object.add_method("END","before_get_parameter")
        object.add_transition("!UNINITIALIZED!STOPPED","END","cleanup_code")
        object.add_transition("END","STOPPED","stop",False)
        object.add_method("STOPPED","stop")
        object.add_transition("INITIALIZED","EDIT","commit_parameters")
        object.add_transition("EDIT","RUN"."commit_grid")
        object.add_transition("INITIALIZED","before_set_interface_parameter")
        object.add_transition("RUN","EVOLVED","evolve_model",False)
        for state in ["RUN","EDIT","EVOLVED"]:
            object.add_method(state,"get_model_time")
            object.add_method(state,"get_timestep")
#            object.add_method(state,"get_profiles")
#            object.add_method(state,"get_field")
        object.add_method("EVOLVED","evolve_model")

    # Returns the vertical temperature profiles at the gridpoint index array i
    def get_profiles_T(self,i):
        return self.get_profiles_T_(i,numpy.zeros(self.ktot))

    # Returns the full temperature array
    def get_field_T(self):
        return self.get_field_T_(numpy.zeros(self.itot),numpy.zeros(self.ktot))