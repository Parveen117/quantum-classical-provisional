"""Reproducible heated optical core subassembly; optional CAD dependencies.

Pure metadata/phase targets are dependency-free. Geometry generation uses
gdstk; independent GDS checks use KLayout. No Maxwell/thermal model or device
performance is inferred from polygon connectivity or feature checks.
"""
from datetime import datetime
import hashlib
import json
from math import cos, pi, sin
from pathlib import Path

from .photonic_exchange import design_photonic_exchange

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "layout/vendor/cornerstone_sin300"
VENDOR_HASHES = {"mmi2x2.gds":"11f66e914be0068099119e58d24b9f2749eae105fccf4121421f07247d5b2fbd",
                 "heater.gds":"ae90704456839d8d7685a317405b27b1f01d9d88094a6e5c4d9f9f1b502cb656",
                 "LICENSE":"855dd6b4623121391bdc1e0c8c4a7ec7a09b7a6f1202bf69b51375b5bb24b525"}
EXTRA_CHANNELS = tuple(f"core_{i}_{kind}" for i in range(6) for kind in ("common","input_trim","output_trim")) + tuple(f"bypass_{p}" for p in (0,5,10,15))
LENGTH = 3164
ORIGIN_X = 1000


def layout_spec():
    layout=design_photonic_exchange();ports=[];heaters=[];groups=[]
    for i,(p,q) in enumerate(layout.pairs):
        y=600+900*i;group=f"exchange_{i}"
        groups.append(dict(id=group,labels=[p,q],origin_um=[ORIGIN_X,y]))
        for label,dy in ((p,63.5),(q,-63.5)):
            for side,x in (("in",ORIGIN_X),("out",ORIGIN_X+LENGTH)):
                ports.append(dict(label=label,side=side,xy_um=[x,y+dy],component=group))
        for name,x,dy,down in ((f"core_{i}",1582,-75,True),
                               (f"core_{i}_common",1582,75,False),
                               (f"core_{i}_input_trim",200,-63.5,True),
                               (f"core_{i}_output_trim",2964,-63.5,True)):
            heaters.append(dict(channel=name,center_um=[ORIGIN_X+x,y+dy],pads_down=down,component=group))
    for i,label in enumerate((*layout.fixed,layout.guard)):
        y=6000+400*i;group=f"path_{label}"
        groups.append(dict(id=group,labels=[label]))
        for side,x in (("in",ORIGIN_X),("out",ORIGIN_X+LENGTH)):
            ports.append(dict(label=label,side=side,xy_um=[x,y],component=group))
        if label!=layout.guard:
            heaters.append(dict(channel=f"bypass_{label}",center_um=[2500,y],pads_down=False,component=group))
    return dict(schema="native-photonic-layout-v1",author="Monty",status="CORE_SUBASSEMBLY_ONLY",
                top_cell="NATIVE_EXCHANGE_CORE",unit_um=1,manufacturing_grid_nm=1,
                design_area_um=[11470,15450],strip_width_um=1.2,transition_length_um=300,
                min_analytic_centerline_radius_um=2*300**2/(71.95*pi*pi),
                exchange_groups=groups,optical_ports=ports,heaters=heaters,
                resources=dict(mmi2x2=12,heaters=28,electrical_pads=56,open_optical_ports=34,
                               isolated_guard_paths=1,external_phase_channels=3,total_recorded_channels=31),
                layers={"nitride":203,"filament":39,"contact":41,"outline":99},
                vendor_sha256=dict(VENDOR_HASHES),
                missing=["fiber/edge couplers and packaging","electrical fan-out beyond imported bond pads",
                         "source, detectors and external preparation/analysis/guard modules",
                         "measured phase/loss/crosstalk, thermal model and foundry approval"],
                boundary="geometric subassembly; open optical interfaces are not a packaged experiment")


def physical_phase_targets(logical):
    """Ideal D-coupler convention; values are phase targets, not voltages.

    D=[[1,i],[i,1]]/sqrt(2). Z D diag(1,-exp(-i theta)) D Z
    equals H diag(1,exp(-i theta)) H, with Z=diag(1,-i).
    Common-arm and bypass baselines require actual optical calibration.
    """
    out=dict(logical)
    for i in range(6):
        out[f"core_{i}"]=(32+logical[f"core_{i}"])%64
        out[f"core_{i}_common"]=0
        out[f"core_{i}_input_trim"]=48
        out[f"core_{i}_output_trim"]=48
    out.update({f"bypass_{p}":0 for p in (0,5,10,15)})
    return out


def _vendor_cell(filename,name,new_name):
    import gdstk
    path=VENDOR/filename
    if hashlib.sha256(path.read_bytes()).hexdigest()!=VENDOR_HASHES[filename]:
        raise ValueError("vendor geometry hash mismatch")
    cell=gdstk.read_gds(path)[name]
    return cell.copy(new_name)


def _curve(path,x,y0,y1,length=300):
    d=y1-y0
    path.parametric(lambda t:(x+length*t,y0+d*(1-cos(pi*t))/2),
                    lambda t:(length,d*pi*sin(pi*t)/2),relative=False)


def build_layout(destination):
    """Write deterministic hierarchical GDS and the geometry/port manifest."""
    import gdstk
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    spec=layout_spec();lib=gdstk.Library(unit=1e-6,precision=1e-9)
    mmi=_vendor_cell("mmi2x2.gds","SiN300nm_1550nm_TE_STRIP_2x2_MMI","CS_SIN300_MMI2X2")
    heater=_vendor_cell("heater.gds","Heater","CS_SIN300_HEATER")
    lib.add(mmi,heater);unit=lib.new_cell("HEATED_EXCHANGE_UNIT")
    unit.add(gdstk.Reference(mmi,(700,0)),gdstk.Reference(mmi,(2132,0)))
    for sign in (1,-1):
        lead=gdstk.RobustPath((0,sign*63.5),1.2,tolerance=0.001,layer=203)
        lead.segment((400,sign*63.5));_curve(lead,400,sign*63.5,sign*3.05)
        arm=gdstk.RobustPath((1032,sign*3.05),1.2,tolerance=0.001,layer=203)
        _curve(arm,1032,sign*3.05,sign*75);arm.segment((1832,sign*75))
        _curve(arm,1832,sign*75,sign*3.05)
        tail=gdstk.RobustPath((2464,sign*3.05),1.2,tolerance=0.001,layer=203)
        _curve(tail,2464,sign*3.05,sign*63.5);tail.segment((LENGTH,sign*63.5))
        for path in (lead,arm,tail):unit.add(*path.to_polygons())
    for x,y,down in ((200,-63.5,True),(1582,-75,True),(1582,75,False),(2964,-63.5,True)):
        unit.add(gdstk.Reference(heater,(x-123.5,y+1 if down else y-1),x_reflection=down))
    top=lib.new_cell(spec["top_cell"])
    top.add(gdstk.rectangle((0,0),spec["design_area_um"],layer=99))
    for i in range(6):top.add(gdstk.Reference(unit,(ORIGIN_X,600+900*i)))
    for i,label in enumerate((0,5,10,15,16)):
        y=6000+400*i
        top.add(gdstk.rectangle((ORIGIN_X,y-0.6),(ORIGIN_X+LENGTH,y+0.6),layer=203))
        if label!=16:top.add(gdstk.Reference(heater,(2500-123.5,y-1)))
    lib.write_gds(destination/"exchange_core.gds",timestamp=datetime(2026,10,24))
    (destination/"exchange_core_ports.json").write_text(json.dumps(spec,indent=2)+"\n")
    return spec


def check_layout(path,spec=None):
    """Independent KLayout geometry checks, not the proprietary foundry deck.

    This subset checks widths/gaps, grid/outline, intended optical component
    partition and heater/pad connectivity. It does not check optical transfer,
    bend radiation, thermal isolation, packaging, or all manufacturing rules.
    """
    import klayout.db as k
    spec=layout_spec() if spec is None else spec
    ly=k.Layout();ly.read(str(path));top=ly.top_cell()
    if top is None or top.name!=spec["top_cell"]:raise ValueError("unexpected layout top cell")
    if abs(ly.dbu-0.001)>1e-12:raise ValueError("1 nm database grid required")
    used={(x.layer,x.datatype) for x in ly.layer_infos()}
    if used!={(39,0),(41,0),(99,0),(203,0)}:raise ValueError("unexpected/missing process layers")
    regions={n:k.Region(top.begin_shapes_rec(ly.layer(n,0))).merged() for n in (39,41,99,203)}
    failures={};rules={}
    # Table 4: use the >=350 nm SiN branch everywhere (our strips are 1.2 um).
    # Angle limit 1 degree follows the published pre-DRC convention for acute joins.
    for layer,width,gap in ((203,350,250),(39,600,5000),(41,2000,5000)):
        rules[f"layer_{layer}_width_nm"]=width;rules[f"layer_{layer}_gap_nm"]=gap
        failures[f"layer_{layer}_width"]=regions[layer].width_check(width,False,k.Region.Euclidian,1).count()
        failures[f"layer_{layer}_gap"]=regions[layer].space_check(gap,False,k.Region.Euclidian,1).count()
    area=k.Region(k.Box(0,0,11470000,15450000))
    failures["outline"]=0 if (regions[99]^area).is_empty() else 1
    failures["outside_outline"]=sum((regions[n]-area).count() for n in (39,41,203))
    failures["grid"]=sum(regions[n].grid_check(1,1).count() for n in regions)
    optical=list(regions[203].each_merged());filaments=list(regions[39].each_merged());pads=list(regions[41].each_merged())
    observed=[]
    for polygon in optical:
        members=[]
        for port in spec["optical_ports"]:
            # Move 10 nm inside the open port rather than relying on boundary inclusion.
            x,y=port["xy_um"];x+=0.01 if port["side"]=="in" else -0.01
            if polygon.inside(k.Point(round(x*1000),round(y*1000))):members.append((port["label"],port["side"]))
        observed.append(sorted(members))
    expected=[sorted((label,side) for label in group["labels"] for side in ("in","out")) for group in spec["exchange_groups"]]
    failures["optical_partition"]=0 if sorted(observed)==sorted(expected) else 1
    failures["heater_count"]=0 if len(filaments)==28 else 1
    failures["pad_count"]=0 if len(pads)==56 else 1
    contacts=[]
    for fil in filaments:
        contacts.append([i for i,pad in enumerate(pads) if not (k.Region(fil)&k.Region(pad)).is_empty()])
    failures["two_pads_per_heater"]=sum(len(c)!=2 for c in contacts)
    failures["one_heater_per_pad"]=sum(sum(i in c for c in contacts)!=1 for i in range(len(pads)))
    # A central 1 um strip must lie inside both guide and heater polygons.
    # This is lateral alignment only; vertical stack/thermal response are untested.
    failures["heater_alignment"]=0
    for h in spec["heaters"]:
        x,y=h["center_um"]
        probe=k.Region(k.Box(round((x-90)*1000),round((y-0.5)*1000),round((x+90)*1000),round((y+0.5)*1000)))
        if not (probe-regions[39]).is_empty() or not (probe-regions[203]).is_empty():failures["heater_alignment"]+=1
    return dict(status="LOCAL_GEOMETRY_CHECKS",passed=not any(failures.values()),failures=failures,
                checked_thresholds=rules,optical_connected_components=len(optical),heaters=len(filaments),pads=len(pads),
                klayout_version=k.__version__,foundry_drc_run=False,foundry_approved=False,
                limitations=["not the proprietary foundry pre-DRC script or full deck","angle-limited width checks do not cover every geometric rule",
                             "no coupling/loss/thermal/power/phase-response prediction","optical interfaces are unconnected to fiber couplers"])


def render_layout(path,destination):
    """Plot actual GDS polygons; no generated illustration or physical claim."""
    import gdstk
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon,Patch
    lib=gdstk.read_gds(path);destination=Path(destination)
    colors={203:"#136f9b",39:"#d44a3a",41:"#e5ae3c"}
    for cell_name,filename,figsize in (("HEATED_EXCHANGE_UNIT","exchange_unit.png",(15,4.8)),
                                     ("NATIVE_EXCHANGE_CORE","exchange_core.png",(7,12))):
        fig,ax=plt.subplots(figsize=figsize)
        for p in lib[cell_name].get_polygons():
            if p.layer in colors:ax.add_patch(Polygon(p.points/1000,closed=True,facecolor=colors[p.layer],
                                                    edgecolor=colors[p.layer] if p.layer==203 else "none",
                                                    linewidth=.35 if p.layer==203 else 0))
        ax.autoscale_view();ax.set_aspect("equal");ax.set_xlabel("x (mm)");ax.set_ylabel("y (mm)")
        ax.set_title("Heated two-port exchange unit" if cell_name.startswith("HEATED") else "Six exchange units, four bypasses and isolated guard",pad=16)
        if cell_name.startswith("HEATED"):
            for x,y,label in ((200,-320,"Input trim"),(1582,-340,"Exchange arm"),(1582,345,"Common phase"),(2964,-320,"Output trim")):
                ax.text(x/1000,y/1000,label,ha="center",va="center",fontsize=10)
            ax.set_xlim(-0.12,3.30);ax.set_ylim(-0.40,0.40)
        else:
            for i,pair in enumerate(design_photonic_exchange().pairs):ax.text(4.27,(600+900*i)/1000,f"{pair[0]} ↔ {pair[1]}",va="center",fontsize=10)
            for i,label in enumerate((0,5,10,15,16)):ax.text(4.27,(6000+400*i)/1000,f"Guard {label}" if label==16 else f"Bypass {label}",va="center",fontsize=9)
            ax.set_xlim(.8,5.1)
        ax.legend(handles=[Patch(color=c,label={203:"SiN waveguide",39:"Heater filament",41:"Contact pads"}[n]) for n,c in colors.items()],loc="upper center",bbox_to_anchor=(.5,-.13),ncol=3,frameon=False)
        fig.text(.5,.02,"Open optical ports • Not fabricated • Waveguide edges emphasized for visibility",ha="center",fontsize=9,color="#555555")
        fig.tight_layout(rect=(0,.10,1,1));fig.savefig(destination/filename,dpi=180);plt.close(fig)
