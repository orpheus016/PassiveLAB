"""Interactive S-parameter visualization from a :class:`~passivelab.core.types.Metrics`
(``simulate --plot``). Pure ``plotly``/``numpy`` logic -- no ``openEMS``/``CSXCAD`` import, same
footing as ``sparams.py``. Deferred import inside the one function that needs ``plotly`` (the
``viz`` extra, like ``utils/preview.py``'s matplotlib import) so importing this module never
requires it -- only actually calling :func:`plot_sparams_interactive` does.

**Port-label convention**: see ``sparams.py``'s module docstring -- ``metrics.values["s_parameters"]``
is indexed ``[k, a, b]`` with ``a`` the excitation (source) port and ``b`` the response port, so a
trace's label ``S{response}{source}`` reads ``s[:, a, b]`` as ``S{port_numbers[b]}{port_numbers[a]}``.
"""
from __future__ import annotations

import pathlib

import numpy as np

from passivelab.core.types import Metrics


def plot_sparams_interactive(metrics: Metrics, out_path: str | pathlib.Path) -> pathlib.Path:
    """Write a self-contained, interactive (zoomable/hoverable) HTML plot of every S_ij magnitude
    (dB) and phase (degrees) vs. frequency to ``out_path``. Returns ``out_path``.
    """
    from plotly.subplots import make_subplots  # deferred: plotly is the `viz` extra

    v = metrics.values
    freq_hz = np.asarray(v["frequency_hz"])
    s = np.asarray(v["s_parameters"])
    port_numbers = list(v["port_numbers"])
    n = len(port_numbers)

    freq_ghz = freq_hz / 1e9
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        subplot_titles=("Magnitude (dB)", "Phase (deg)"),
    )
    for a in range(n):  # a = excitation (source) port index
        for b in range(n):  # b = response port index
            sij = s[:, a, b]
            label = f"S{port_numbers[b]}{port_numbers[a]}"  # S(response, source) -- see module docstring
            mag_db = 20 * np.log10(np.maximum(np.abs(sij), 1e-300))
            phase_deg = np.angle(sij, deg=True)
            fig.add_trace({"x": freq_ghz, "y": mag_db, "name": label,
                            "legendgroup": label, "mode": "lines"}, row=1, col=1)
            fig.add_trace({"x": freq_ghz, "y": phase_deg, "name": label,
                            "legendgroup": label, "showlegend": False, "mode": "lines"}, row=2, col=1)

    fig.update_xaxes(title_text="Frequency (GHz)", row=2, col=1)
    fig.update_yaxes(title_text="|S| (dB)", row=1, col=1)
    fig.update_yaxes(title_text="angle(S) (deg)", row=2, col=1)
    fig.update_layout(title=f"S-parameters -- {v.get('s3p_path', '')}", hovermode="x unified")

    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path), include_plotlyjs=True, full_html=True)
    return out_path
