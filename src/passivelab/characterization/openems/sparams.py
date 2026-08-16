"""S-parameter post-processing: openEMS ``.s3p`` -> ``core.types.Metrics`` (sub-phase 1.4.4).

Pure ``skrf``/``numpy`` logic, no ``openEMS``/``CSXCAD`` import -- independently testable without
the solver installed (same footing as ``ports.py``). Reads back the Touchstone file
``characterization/openems/plugin.py`` already writes via the vendored ``write_snp()``; does not
change that writer.

**Mechanism matches the golden reference exactly, not reinvented.** The reference
(``reference/python/TCoil_Dataset_Generator_and_Training.py``) reads every S3P it produces or
predicts via ``skrf.Network`` (``load_sparameters()`` at lines 883-904, ``GetPredictedNetwork()`` at
1248-1278, 1.7's ngspice transcription at line 1355) -- this module uses the same library for the
same reason: it is what 1.4.5/1.4.8/1.5/1.6/1.7 already assume a ``.s3p`` is readable with.

**Port-ordering convention (load-bearing, tested -- see ``test_sparams.py``'s
``test_...convention...`` case).** ``skrf.Network(...).s[k]``'s row/column axes turn out to be the
*reverse* of what "S_ij = response i / source j" notation alone would suggest, for this repo's
specific ``write_snp()`` (vendored, column-grouped-by-source-port Touchstone writer) + ``skrf``
reader combination:

    s_parameters[k, a, b] == S(source=port_numbers[a], response=port_numbers[b])

i.e. the **row** axis is the excitation port, the **column** axis is the response port. This was
confirmed empirically (asymmetric synthetic S-values through the real ``write_snp()``/``skrf``
round-trip), not assumed from the Touchstone spec alone -- for a genuinely reciprocal passive
device (S_ij ~= S_ji, as 1.4.1's live validation confirmed for the T-coil) this is nearly invisible
in practice, which is exactly the kind of silent mismatch the board task's "port ordering explicit
and asserted, not incidental" validation bar exists to catch. Not "fixed" here: the golden
reference's own ``load_sparameters()``/downstream training pipeline consumes ``ntwk.s`` exactly this
way too (no transpose), so correcting it here would make this repo's S-parameters diverge from what
the notebook itself produces -- breaking 1.4.5's/1.4.8's bit-for-bit equivalence comparisons.
"""
from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import numpy as np
import skrf

from passivelab.core.types import Metrics

if TYPE_CHECKING:
    from passivelab.characterization.openems.ports import PortDef

#: Golden reference's own training-target frequency count
#: (``TCoil_Dataset_Generator_and_Training.py:868``, ``n_freq = 101``) -- 0-100 GHz at 1 GHz step,
#: decimated from the raw 1001-point 0.1 GHz-step solver grid (``step_freq = 10``).
GOLDEN_TRAINING_N_FREQ = 101

_CONVENTION_NOTE = (
    "s_parameters[k, a, b] == S(source=port_numbers[a], response=port_numbers[b]) -- skrf's row "
    "axis is the excitation port and column axis the response port for this repo's "
    "write_snp()+skrf.Network() combination (see sparams.py's module docstring and "
    "test_sparams.py's convention regression test); the reverse of the 'row=response,col=source' "
    "convention S_ij notation alone might suggest."
)


def decimate_to_training_grid(freq_hz: np.ndarray, s: np.ndarray,
                               n_freq: int = GOLDEN_TRAINING_N_FREQ) -> tuple[np.ndarray, np.ndarray]:
    """Pick ``n_freq`` evenly-spaced points out of the raw solved grid, generalizing the golden
    reference's ``range(0, original_freq, step_freq)`` (``load_sparameters()``,
    ``TCoil_Dataset_Generator_and_Training.py:883-904``) beyond its hardcoded 1001/101/10. Raises
    ``ValueError`` rather than silently mis-decimating if the raw grid doesn't divide evenly --
    the board task's own named risk ("an off-by-one grid here silently corrupts the 1818-dim
    target") becomes a loud failure instead.
    """
    original_n = len(freq_hz)
    if n_freq < 2 or (original_n - 1) % (n_freq - 1) != 0:
        raise ValueError(
            f"cannot decimate {original_n} raw frequency points onto {n_freq} evenly-spaced "
            "training points -- (original_n - 1) must divide evenly by (n_freq - 1) to match the "
            "golden reference's range(0, original_freq, step_freq) decimation "
            "(TCoil_Dataset_Generator_and_Training.py:868-904)"
        )
    step = (original_n - 1) // (n_freq - 1)
    idx = np.arange(0, original_n, step)[:n_freq]
    return freq_hz[idx], s[idx]


def flatten_training_vector(s_decimated: np.ndarray) -> np.ndarray:
    """Byte-for-byte replica of the golden reference's ``load_sparameters()`` flatten
    (``TCoil_Dataset_Generator_and_Training.py:883-904``): per frequency, row-major-flatten the
    n x n S-matrix, concatenate real then imaginary parts, then concatenate across all
    frequencies -- for the 3-port/101-freq case this reproduces the reference's 1818-dim vector
    exactly (``101 * 3 * 3 * 2``)."""
    parts = []
    for k in range(s_decimated.shape[0]):
        flat = s_decimated[k].flatten()
        parts.append(np.concatenate((flat.real, flat.imag)))
    return np.concatenate(parts)


def sparams_to_metrics(s3p_path: str | pathlib.Path, port_defs: list["PortDef"]) -> Metrics:
    """Read ``s3p_path`` via ``skrf.Network`` and reduce it to a :class:`Metrics`. ``port_defs``
    (from ``ports.derive_port_definitions``) makes port count/ordering explicit and asserted, not
    incidental: raises ``ValueError`` if the file's port count doesn't match.
    """
    ntwk = skrf.Network(str(s3p_path))
    if ntwk.number_of_ports != len(port_defs):
        raise ValueError(
            f"{s3p_path}: Touchstone file has {ntwk.number_of_ports} ports but "
            f"{len(port_defs)} port definitions were supplied -- port count/ordering mismatch"
        )
    port_numbers = [pd.portnumber for pd in port_defs]
    training_freq, training_s = decimate_to_training_grid(ntwk.f, ntwk.s)
    training_vector = flatten_training_vector(training_s)
    return Metrics(values={
        "s3p_path": str(s3p_path),
        "port_numbers": port_numbers,
        "s_parameters_convention": _CONVENTION_NOTE,
        "frequency_hz": ntwk.f,
        "s_parameters": ntwk.s,
        "training_frequency_hz": training_freq,
        "training_vector": training_vector,
    })


def metrics_to_full_json(metrics: Metrics) -> dict:
    """The complete, JSON-serializable form of ``sparams_to_metrics()``'s output -- unlike
    :func:`metrics_summary_for_report`, this keeps the full raw ``frequency_hz``/``s_parameters``
    (complex, not directly JSON-serializable, so split into ``{"real": [...], "imag": [...]}``).
    For the on-demand ``simulate --plot`` output (one sample at a time, not the per-dataset-row
    path 1.5.2 will run at scale), so the bloat ``metrics_summary_for_report()`` deliberately avoids
    is an acceptable, deliberate tradeoff here -- this *is* the deep-dive artifact.
    """
    v = metrics.values
    s = np.asarray(v["s_parameters"])
    return {
        "s3p_path": v["s3p_path"],
        "port_numbers": list(v["port_numbers"]),
        "s_parameters_convention": v["s_parameters_convention"],
        "frequency_hz": np.asarray(v["frequency_hz"]).tolist(),
        "s_parameters": {"real": s.real.tolist(), "imag": s.imag.tolist()},
        "training_frequency_hz": np.asarray(v["training_frequency_hz"]).tolist(),
        "training_vector": np.asarray(v["training_vector"]).tolist(),
    }


def metrics_summary_for_report(metrics: Metrics) -> dict:
    """The lightweight, JSON-serializable subset of ``sparams_to_metrics()``'s output for
    embedding directly in the per-sample ``report.json`` (1.4.4) -- deliberately excludes
    ``frequency_hz``/``s_parameters`` (the full raw 1001-point matrix): duplicating that into every
    sample's report would bloat it at 1.5.2's thousands-of-samples scale for no reader that isn't
    already better served by re-reading the ``.s3p`` file directly (same reasoning
    ``plugin.py`` already applies to ``s3p_path`` vs. embedding the matrix). The much smaller
    decimated ``training_vector`` (1818 floats for the 3-port case) is real post-processed output,
    not just a pointer, so it's kept.
    """
    v = metrics.values
    return {
        "s3p_path": v["s3p_path"],
        "port_numbers": list(v["port_numbers"]),
        "s_parameters_convention": v["s_parameters_convention"],
        "training_frequency_hz": np.asarray(v["training_frequency_hz"]).tolist(),
        "training_vector": np.asarray(v["training_vector"]).tolist(),
    }
