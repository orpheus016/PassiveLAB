"""``OpenEMSBackend`` -- the openEMS (FDTD) implementation of ``SimulationBackend`` (sub-phase
1.4.1). Wraps the golden reference's ``simulator_openems.py`` (reference/python/
TCoil_Dataset_Generator_and_Training.py:534-687) behind ``simulate(layout) -> SimulationResult``,
driving the vendored IHP PDK helper modules (``vendor/modules/``) the same way the reference script
does, with the notebook-specific hacks removed rather than reproduced:

- No hardcoded ``/tmp/ray_cache/{index}_sim`` scratch path -- output lives under a caller-supplied
  ``out_dir`` root, in a deterministic ``sample_id``-derived subfolder (see ``_sample_id()``).
- No ``os.chdir()`` -- every path handed to the vendored helpers is absolute.
- No manual "disable the GUI preview" source edit -- ``runSimulation(..., interactive_preview=False)``
  is called explicitly (see ``vendor/NOTICE``).
- Ports are read from what's actually in the merged GDS (``ports.derive_port_definitions``), not
  assumed to always be 3 -- see ``ports.py``'s module docstring for why.
- No silent multi-hour runs and no manual DLL workaround -- ``OpenEMSConfig.install_path``,
  ``num_cpus``, ``verbose``, and ``dump_statistics`` are wired all the way through to
  ``os.add_dll_directory()`` and ``FDTD.Run()`` (1.4.3), and every port excitation's real openEMS
  console output is captured to ``<sim_dir>/sub-N/openems_run.log``.

Ray/distributed fan-out (calling this backend from many concurrent workers) is sub-phase 1.5.2's
scope, not built here -- this backend is designed to be safe under that usage (stateless instance,
no shared mutable state, no global-path collisions across different ``sample_id``s) without needing
to know about Ray at all.
"""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import pathlib
import sys
import time
from importlib import metadata as importlib_metadata

import gdstk

from passivelab.characterization.openems.config import OpenEMSConfig, load_openems_config
from passivelab.characterization.openems.ports import (
    derive_port_definitions,
    merge_layout_for_solver,
)
from passivelab.core.types import Layout, SimulationResult

_UNIT = 1e-6  # geometry is in microns, matching the golden reference and the tcoil generator

# NOTE ON IMPORTS: this module deliberately does NOT import numpy or any of the
# `vendor/modules/` helpers (util_simulation_setup, util_gds_reader, util_meshlines) at module
# level, even though `_simulate()` needs all of them -- util_gds_reader/util_meshlines require
# `gdspy` and util_simulation_setup requires `pylab`/`CSXCAD`/`openEMS`, none of which are
# declared core dependencies (they're the `sim` extra, not pip-installable in default CI). Eager
# imports here would make `import passivelab.characterization.openems` itself fail without the
# `sim` extra installed, which would break plugin self-registration (`__init__.py`) and every
# structural test (config/ports/registry) that's supposed to run without openEMS installed. All
# heavy imports are deferred to inside `_simulate()`, so only an actual `simulate()` call requires
# the `sim` extra -- importing the package, constructing a backend, or listing it in the registry
# never does.
#
# ORDERING NOTE (1.4.3): `os.add_dll_directory(config.install_path)` must run before *any* of the
# deferred imports below, not just before the later explicit `from openEMS import openEMS` --
# `util_simulation_setup` imports `CSXCAD` at its own module level, so on Windows the DLL
# resolution failure actually happens at that earlier import, not the later one.


def _solver_versions() -> dict[str, str]:
    """Best-effort package version lookup for the manifest -- never raises: the compiled
    openEMS/CSXCAD packages don't guarantee a programmatic ``__version__``, so this falls back to
    "unknown" rather than failing a run over a diagnostics field."""
    versions = {}
    for pkg in ("openEMS", "CSXCAD"):
        try:
            versions[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            versions[pkg] = "unknown"
    return versions


@contextlib.contextmanager
def _redirect_to_log(log_path: pathlib.Path):
    """Duplicate the real stdout/stderr file descriptors (1/2) to `log_path` for the block's
    duration, then restore them (1.4.3). openEMS's ``FDTD.Run()`` is a compiled extension that
    writes straight to those real fds -- a Python-level ``sys.stdout = ...``/
    ``contextlib.redirect_stdout`` reassignment does not touch them and would capture nothing.
    Mirrors the golden reference's own ``os.system(f"... > {index}.log")`` shell redirect, scoped
    per port excitation rather than per whole-sample subprocess since this backend runs in-process
    (see ``plugin.py``'s module docstring: no subprocess, no ``os.chdir()``)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout.flush()
    sys.stderr.flush()
    saved_stdout_fd = os.dup(1)
    saved_stderr_fd = os.dup(2)
    log_fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    try:
        os.dup2(log_fd, 1)
        os.dup2(log_fd, 2)
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved_stdout_fd, 1)
        os.dup2(saved_stderr_fd, 2)
        os.close(saved_stdout_fd)
        os.close(saved_stderr_fd)
        os.close(log_fd)


def _sample_id(layout: Layout) -> str:
    """Deterministic id derived from ``layout.parameter_manifest`` -- identical geometry always
    maps to the same output folder, which is what lets ``runSimulation()``'s existing
    hash-based skip-if-unchanged mechanism act as real content-addressed caching (see the 1.4.1
    plan's "sample_id/out_dir wiring" section)."""
    manifest_json = json.dumps(dict(layout.parameter_manifest), sort_keys=True, default=str)
    return hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()[:16]


class OpenEMSBackend:
    """One instance = one output root (``out_dir``) + one solver config. Holds no live
    openEMS/CSXCAD object between ``simulate()`` calls -- every FDTD object is constructed and torn
    down entirely inside one call, so an instance is safe to reuse across many samples (from a
    single caller today; from many concurrent Ray workers once 1.5.2 lands)."""

    #: Lets solver-agnostic callers (e.g. ``scripts/simulate.py``) resolve the right config
    #: loader for whatever solver a registry lookup returned, without importing this module's
    #: config class directly -- mirrors how ``config.solver``/``registry.get()`` already keep the
    #: CLI from hardcoding "openems" anywhere but the JSON file itself.
    load_config = staticmethod(load_openems_config)

    def __init__(self, config: OpenEMSConfig, out_dir: str | pathlib.Path):
        self.config = config
        self.out_dir = pathlib.Path(out_dir)

    def simulate(self, layout: Layout) -> SimulationResult:
        sample_id = _sample_id(layout)
        sim_dir = (self.out_dir / sample_id).resolve()
        sim_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "sample_id": sample_id,
            "solver": "openems",
            "config": dataclasses.asdict(self.config),
            "solver_versions": _solver_versions(),
            "success": False,
        }
        start = time.monotonic()
        try:
            result = self._simulate(layout, sim_dir, sample_id)
            manifest.update(result)
            manifest["success"] = True
            return SimulationResult(backend="openems", raw={**manifest, "sim_dir": str(sim_dir)})
        except Exception as e:
            manifest["error"] = f"{type(e).__name__}: {e}"
            raise
        finally:
            manifest["wall_clock_seconds"] = time.monotonic() - start
            (sim_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _simulate(self, layout: Layout, sim_dir: pathlib.Path, sample_id: str) -> dict:
        config = self.config

        # 1.4.3: must run before any deferred import below -- see the module-level ORDERING NOTE.
        if config.install_path and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(config.install_path)

        # Deferred imports -- see the module-level NOTE ON IMPORTS above.
        import numpy as np
        from passivelab.characterization.openems.vendor.modules import util_gds_reader as gds_reader
        from passivelab.characterization.openems.vendor.modules import util_meshlines
        try:
            from passivelab.characterization.openems.vendor.modules import (
                util_simulation_setup as simulation_setup,
            )
        except ImportError as e:
            if not config.install_path:
                raise ImportError(
                    f"failed to import CSXCAD/openEMS ({e}). On Windows this is usually a DLL "
                    "resolution failure -- set OpenEMSConfig.install_path to your openEMS install "
                    "directory (the folder containing CSXCAD_MSVC.dll etc.)."
                ) from e
            raise
        from passivelab.characterization.openems.vendor.modules import util_stackup_reader as stackup_reader
        from passivelab.characterization.openems.vendor.modules import util_utilities as utilities

        merged_cell = merge_layout_for_solver(layout)
        port_defs = derive_port_definitions(layout.metadata["ports_cell"])
        if not port_defs:
            raise ValueError(
                f"sample {sample_id}: no port markers found in layout.metadata['ports_cell'] -- "
                "cannot simulate a layout with zero excitation ports"
            )

        gds_path = sim_dir / f"{sample_id}.gds"
        lib = gdstk.Library()
        lib.add(merged_cell)
        lib.write_gds(str(gds_path))

        materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(str(config.xml_path))

        simulation_ports = simulation_setup.all_simulation_ports()
        for pd in port_defs:
            simulation_ports.add_port(simulation_setup.simulation_port(
                portnumber=pd.portnumber, voltage=pd.voltage, port_Z0=pd.port_z0,
                source_layernum=pd.source_layernum, from_layername=pd.from_layername,
                to_layername=pd.to_layername, direction=pd.direction))

        layernumbers = metals_list.getlayernumbers()
        layernumbers.extend(simulation_ports.portlayers)
        allpolygons = gds_reader.read_gds(
            str(gds_path), layernumbers, purposelist=[0], metals_list=metals_list,
            preprocess=config.preprocess_gds, merge_polygon_size=config.merge_polygon_size)

        wavelength_air = 3e8 / config.freq_stop / _UNIT
        max_cellsize = wavelength_air / (np.sqrt(materials_list.eps_max) * config.cells_per_wavelength)

        end_criteria = 10 ** (config.energy_limit_db / 10)
        from openEMS import openEMS  # deferred: only importable once the `sim` extra is installed
        FDTD = openEMS(EndCriteria=end_criteria)
        FDTD.SetGaussExcite((config.freq_start + config.freq_stop) / 2,
                             (config.freq_stop - config.freq_start) / 2)
        FDTD.SetBoundaryCond(list(config.boundary_conditions))

        port_logs = {}
        for pd in port_defs:
            excite_ports = [pd.portnumber]
            FDTD = simulation_setup.setupSimulation(
                excite_ports, simulation_ports, FDTD,
                materials_list, dielectrics_list, metals_list,
                allpolygons, max_cellsize, config.refined_cellsize, config.margin, _UNIT,
                xy_mesh_function=util_meshlines.create_xy_mesh_from_polygons)
            # 1.4.3: capture this excitation's real openEMS console output to a log file --
            # verbose/dump_statistics alone only make openEMS *produce* progress text; without
            # redirecting the real fds, that text just vanishes into whatever swallowed this
            # process's stdout (exactly how a real ~72-minute run looked identical to a hang).
            excitation_path = pathlib.Path(utilities.get_excitation_path(str(sim_dir), excite_ports))
            log_path = excitation_path / "openems_run.log"
            with _redirect_to_log(log_path):
                simulation_setup.runSimulation(
                    excite_ports, FDTD, str(sim_dir), sample_id,
                    preview_only=False, postprocess_only=False, interactive_preview=False,
                    num_threads=config.num_cpus, verbose=config.verbose,
                    dump_statistics=config.dump_statistics)
            port_logs[pd.portnumber] = {
                "log": str(log_path),
                "run_stats": str(excitation_path / "openEMS_run_stats.txt"),
                "stats": str(excitation_path / "openEMS_stats.txt"),
            }

        n = len(port_defs)
        f = np.linspace(config.freq_start, config.freq_stop, config.numfreq)
        snm = np.zeros((n, n, config.numfreq), dtype=complex)
        for i in range(n):
            for j in range(n):
                snm[i, j] = utilities.calculate_Sij(
                    port_defs[i].portnumber, port_defs[j].portnumber, f, str(sim_dir), simulation_ports)

        s3p_path = sim_dir / f"{sample_id}.s{n}p"
        utilities.write_snp(snm, f, str(s3p_path))

        # The Touchstone file is the canonical S-parameter artifact (matches how the golden
        # reference's own dataset loader reads results back off disk) -- `raw`/the manifest point
        # to it rather than duplicating the full (n, n, numfreq) matrix as JSON, which would bloat
        # every sample's manifest at 1.5.2's thousands-of-samples scale for no reader that isn't
        # already better served by re-reading the .s3p file (e.g. via `skrf`).
        return {
            "s3p_path": str(s3p_path),
            "ports": [pd._asdict() for pd in port_defs],
            "gds_path": str(gds_path),
            # 1.4.2: the convention every port_defs entry above already encodes
            # (reference_plane_offset/de_embedded/port_z0), surfaced as one top-level summary so a
            # reader of a dataset row doesn't have to infer it by cross-checking every port entry.
            # See docs/PORT_CONVENTION.md.
            "port_convention": {
                "reference_plane": "port box (lumped-port location; CalcPort's uf_ref/uf_inc reference)",
                "de_embedding": "none applied",
                "port_z0": port_defs[0].port_z0,
            },
            # 1.4.3: per-port paths to the captured console log + openEMS's own dump_statistics
            # files, keyed by portnumber (matching "ports" above) -- so "is this run progressing
            # correctly" is answerable by reading a file, not by re-deriving the sub-N/ folder
            # convention or re-running with verbosity turned on after the fact.
            "logs": port_logs,
        }
