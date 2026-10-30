"""Bounded path-interferometer design for the native balanced exchange.

One photon occupies L**2 paths encoding one independent data coordinate and
one pointer at a fixed pair sum. Paths are not independent qubits. This is
a netlist/ideal-transfer adapter, not a fabrication file or a new simulator.
"""
from dataclasses import dataclass
from fractions import Fraction as F

from .model import Config, ResourceLimit, index, integer
from .register import _config
from .sector_control import pulse_coefficients

MAX_PATHS=4097


@dataclass(frozen=True)
class PhotonicExchange:
    grid: int
    pair_sum: int
    reference: int
    pairs: tuple
    fixed: tuple
    guard: int

    @property
    def core_paths(self):return self.grid**2

    def decode(self,path):
        """Native (target, reservoir, pointer); guard has no native label."""
        index(path,self.core_paths,"core path")
        u,m=divmod(path,self.grid);j=(self.reference+u)%self.grid
        return j,(self.pair_sum-j)%self.grid,m

    def encode(self,target,reservoir,pointer):
        for value in (target,reservoir,pointer):index(value,self.grid,"wrapped label")
        if (target+reservoir)%self.grid!=self.pair_sum:raise ValueError("outside declared pair-sum code")
        return ((target-self.reference)%self.grid)*self.grid+pointer

    def partner(self,path):
        index(path,self.core_paths+1,"optical path")
        if path==self.guard:return path
        u,m=divmod(path,self.grid)
        return m*self.grid+u

    def column(self,path,steps):
        """At most two exact scattering entries; no state preparation/executor."""
        other=self.partner(path);alpha,beta=pulse_coefficients(steps)
        if path==other:return ((path,alpha+beta),)
        return tuple((p,c) for p,c in ((path,alpha),(other,beta)) if c)

    def resources(self):
        width=self.grid.bit_length()-1
        return dict(grid=self.grid,signal_photons_in_code=1,independent_data_label_bits=width,
                    retained_pointer_label_bits=width,core_optical_paths=self.core_paths,
                    monitored_guard_paths=1,total_layout_paths=self.core_paths+1,
                    exchange_interferometers=len(self.pairs),balanced_couplers_in_exchange_core=2*len(self.pairs),
                    variable_differential_phases=len(self.pairs),fixed_bypass_paths=len(self.fixed),
                    independent_physical_qubits_claim=False,physical_device_built=False,
                    excluded_from_core_count=["photon source and herald channel","input routing and coherent preparation",
                                              "phase trims and stabilization","output analysis, detectors and time tagging",
                                              "guard-injection test coupler","second pass or second bank for recovery tests"],
                    scaling="L**2 paths for this restricted pair plus one pointer; full fixed four-mode sector plus one pointer needs L**4")

    def netlist(self):
        if not verify_photonic_exchange(self):raise ValueError("invalid photonic exchange layout")
        return dict(schema="native-photonic-exchange-netlist-v1",author="Monty",status="DESIGN_ONLY",
                    encoding=dict(pair_sum=self.pair_sum,reference=self.reference,path="u*L+m; target=a+u; reservoir=q-a-u (mod L)",
                                  fixed_spectator_modes="two other native modes fixed at zero"),
                    modes=[dict(path=p,target=self.decode(p)[0],reservoir=self.decode(p)[1],pointer=self.decode(p)[2])
                           for p in range(self.core_paths)],
                    exchange_blocks=[dict(id=f"exchange_{i}",ports=list(pair),
                                          transfer="H diag(1,exp(-i*theta)) H; calibrated Hadamard port convention",
                                          variable_phase_radians="-theta",additional_port_phase_calibration_required=True)
                                     for i,pair in enumerate(self.pairs)],
                    bypass_ports=list(self.fixed),guard_ports=[self.guard],
                    guard_contract="outside encoded path space; no independent native closure label assigned",
                    resources=self.resources(),measurements=None,
                    engineering_choice=dict(carrier="single photon in Si3N4 waveguide paths",nominal_wavelength_nm=1550,
                                            source="external heralded SPDC photon-pair source",readout="SNSPDs and time tagging",
                                            guard_test="physically bypassed or removed in normal operation"),
                    physical_parameters=dict(measured_wavelength_nm=None,coupler_length_um=None,waveguide_cross_section_nm=None,
                                             heater_voltage_map=None,loss_and_crosstalk=None),
                    release_boundary="logical optical netlist, not foundry layout or fabrication-ready GDS")

    def experiment_plan(self):
        if not verify_photonic_exchange(self):raise ValueError("invalid photonic exchange layout")
        settings=[]
        for step in (0,8,16,24,32):
            for path in range(self.core_paths):
                settings.append(dict(id=f"basis_{step}_{path}",kind="basis_transfer",input_path=path,
                                     phase_steps_pi_over_32=step,analysis="direct path detection",
                                     ideal_probabilities={str(p):c.norm2().to_dict() for p,c in self.column(path,step)}))
        # A fixed path is essential: population-only tests miss block phases.
        reference=self.fixed[0]
        for pair_id,(p,q) in enumerate(self.pairs):
            for phase in (0,16,32,48):
                _,beta=pulse_coefficients(phase);probability=1-beta.norm2()
                settings.append(dict(id=f"phase_{pair_id}_{phase}",kind="cross_block_coherence",
                                     input_paths=[p,reference],input_relative_phase_steps=0,
                                     phase_steps_pi_over_32=32,analysis_paths=[q,reference],
                                     analyzer_relative_phase_steps=phase,
                                     ideal_plus_probability=probability.to_dict(),
                                     ideal_minus_probability=(1-probability).to_dict()))
        probe=self.grid  # u=1,m=0: fresh pointer
        for step in (0,16):
            _,beta=pulse_coefficients(step)
            settings.append(dict(id=f"guard_{step}",kind="deliberate_guard_coupling",input_path=probe,
                                 core_phase_steps_pi_over_32=0,extra_test_coupler_ports=[probe,self.guard],
                                 injection_configuration="physically_bypassed_or_removed" if step==0 else "inserted_active",
                                 extra_test_phase_steps_pi_over_32=step,
                                 ideal_guard_probability=beta.norm2().to_dict()))
        return dict(schema="native-photonic-exchange-experiment-v1",status="NOT_RUN",settings=settings,
                    settings_count=len(settings),herald_windows_per_setting=None,
                    ordinary_guard_configuration="test injection element physically bypassed or removed",
                    pre_run_requirements=["calibrated source/multiphoton characterization","detector response and dark/background runs",
                                          "port phase convention and relative block phases","loss/crosstalk and phase-voltage maps",
                                          "predeclared statistical confidence and tolerances","all herald-window outcome categories retained"],
                    outcomes_per_herald=["exactly one core-path click","exactly one guard-path click","no click","multiple clicks"],
                    denominator="all admitted herald windows; conditional core distributions reported separately",
                    does_not_certify=["arbitrary process tomography","four independent physical native modes",
                                      "nondestructive pointer readout","scalable multi-photon quantum computing"])


def design_photonic_exchange(*,grid=4,pair_sum=0,reference=0,max_paths=MAX_PATHS):
    _config(Config(grid=grid))
    index(pair_sum,grid,"pair sum");index(reference,grid,"reference")
    integer(max_paths,"optical path cap")
    if not 1 <= max_paths <= MAX_PATHS:raise ValueError("path cap out of range")
    if grid**2+1>max_paths:raise ResourceLimit("optical path cap exceeded; no layout returned")
    pairs=tuple((u*grid+m,m*grid+u) for u in range(grid) for m in range(u+1,grid))
    fixed=tuple(u*grid+u for u in range(grid))
    return PhotonicExchange(grid,pair_sum,reference,pairs,fixed,grid**2)


def verify_photonic_exchange(layout):
    """Canonical wiring consistency, not physical certification."""
    try:
        if type(layout) is not PhotonicExchange:return False
        for n in (layout.grid,layout.pair_sum,layout.reference,layout.guard):integer(n,"layout integer")
        if type(layout.pairs) is not tuple or type(layout.fixed) is not tuple:return False
        for pair in layout.pairs:
            if type(pair) is not tuple or len(pair)!=2:return False
            for path in pair:integer(path,"path")
        for path in layout.fixed:integer(path,"fixed path")
        return design_photonic_exchange(grid=layout.grid,pair_sum=layout.pair_sum,reference=layout.reference)==layout
    except (ValueError,TypeError,AttributeError,IndexError):return False


def observed_rates(layout,*,heralds,core_counts,guard_count,no_click,multi_click):
    """Account for mutually exclusive herald-window categories, without scoring.

    Inputs are counts of classified windows, not raw detector totals. This
    checks bookkeeping only; no photon purity, fidelity or confidence follows.
    """
    if not verify_photonic_exchange(layout):raise ValueError("invalid layout")
    integer(heralds,"herald windows")
    if heralds<=0:raise ValueError("positive herald window count required")
    if type(core_counts) is not tuple or len(core_counts)!=layout.core_paths:raise ValueError("one count per core path required")
    for value in (*core_counts,guard_count,no_click,multi_click):
        integer(value,"window count")
        if value<0:raise ValueError("negative window count")
    core=sum(core_counts)
    if core+guard_count+no_click+multi_click!=heralds:raise ValueError("herald accounting does not close")
    return dict(core_per_herald=F(core,heralds),guard_per_herald=F(guard_count,heralds),
                no_click_per_herald=F(no_click,heralds),multi_click_per_herald=F(multi_click,heralds),
                core_distribution_conditioned_on_core_click=tuple(F(n,core) for n in core_counts) if core else None,
                physical_acceptance="NOT_ASSESSED",statistical_confidence="NOT_COMPUTED")
