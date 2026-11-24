import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SOLVER_DIR = str(Path(os.environ.get("NLIP_SOFTWARE", _PROJECT_ROOT.parent / "solvers" / "matrics-20261124")) / "bin")


@dataclass
class EncodingConfig:
    """Configuration for the NLIPSat encoding and solving pipeline.

    All fields have sensible defaults and can be overridden at construction
    time, e.g. ``EncodingConfig(use_decomposition=True, decomp_threshold=4)``.

    Attributes
    ----------
    encoding : str
        Default encoding name (``"OH"``, ``"UNA"``, ``"BIN"``).
    use_decomposition : bool
        Enable order decomposition for high-degree terms in BIN encoding.
    decomp_threshold : int
        Minimum polynomial degree that triggers decomposition.
    decomp_strategy : str
        Decomposition strategy (``"sequential"`` or ``"binary_tree"``).
    decomp_exact : bool
        Use exact multiplication semantics (*False* = relaxed).
    decomp_shared : bool
        Enable shared substructure caching across terms.
    weight_gcd_normalize : bool
        Divide all soft weights by their GCD (improves core-guided solving).
    save_wcnf : bool
        Whether to persist the generated WCNF file.
    workdir : str
        Working directory for temporary files (default: system temp dir,
        override via ``NLIP_WORKDIR`` env var).
    maxhs_path, wmaxcdcl_path, openwbo_path : str
        Paths to external MaxSAT solver binaries (override via
        ``NLIP_MAXHS``, ``NLIP_WMAXCDCL``, ``NLIP_OPENWBO`` env vars).
    rc2_timeout : float
        RC2 child-process time limit, including startup (0 = unlimited).
    external_solver_timeout : float
        Timeout in seconds for external solvers (0 = no timeout).
    enable_preprocess : bool
        Enable optional linear bound propagation and monotonic objective probing.
        Variable shifting and exact normalization always preserve input semantics.
    preprocess_integerize : bool
        Convert fractional coefficients to integers during preprocessing.
    preprocess_scale_limit : int
        Maximum scaling factor allowed during integerization.
    use_mapping_shift : bool
        Use mapping *y = x − lb* during encoding (OH/UNA/BIN).
    encoding_deadline : float
        Absolute ``time.time()`` deadline for the encoding phase
        (0 = no deadline).
    """

    encoding: str = "OH"

    use_decomposition: bool = False
    decomp_threshold: int = 3
    decomp_strategy: str = "sequential"
    decomp_exact: bool = True
    decomp_shared: bool = True

    weight_gcd_normalize: bool = True

    save_wcnf: bool = True
    workdir: str = os.environ.get("NLIP_WORKDIR", tempfile.gettempdir())

    maxhs_path: str = os.environ.get("NLIP_MAXHS", os.path.join(_SOLVER_DIR, "maxhs"))
    wmaxcdcl_path: str = os.environ.get("NLIP_WMAXCDCL", os.path.join(_SOLVER_DIR, "wmaxcdcl_static"))
    openwbo_path: str = os.environ.get("NLIP_OPENWBO", os.path.join(_SOLVER_DIR, "openwbo"))
    uwrmaxsat_path: str = os.environ.get("NLIP_UWRMAXSAT", os.path.join(_SOLVER_DIR, "uwrmaxsat"))
    evalmaxres_path: str = os.environ.get("NLIP_EVALMAXRES", os.path.join(_SOLVER_DIR, "EvalMaxSAT"))
    external_solver_args: dict = field(default_factory=dict)
    external_solver_timeout: float = 0.0
    rc2_timeout: float = 0.0

    use_lrn: bool = False
    enable_preprocess: bool = True
    preprocess_integerize: bool = True
    preprocess_scale_limit: int = 1000000

    use_mapping_shift: bool = False

    encoding_deadline: float = 0.0


MAINLINE_SOLVER = "RC2"
MAINLINE_OPTIONS = {
    "encoding": "BIN",
    "use_decomposition": True,
    "decomp_threshold": 3,
    "decomp_strategy": "sequential",
    "decomp_exact": True,
    "decomp_shared": True,
    "weight_gcd_normalize": True,
    "use_lrn": False,
    "enable_preprocess": True,
}


def mainline_config():
    """Return the adopted complete BIN+D configuration, with LRN disabled.

    A fresh object is returned so callers can set operational limits without
    changing the shared preset. Matrix experiments may select another solver
    separately while reusing the same BIN+D encoding configuration.
    """
    return EncodingConfig(**MAINLINE_OPTIONS)
