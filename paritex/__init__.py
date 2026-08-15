"""PDF -> LaTeX paper reconstruction with AI backends, and parity evaluation"""

__version__ = "0.0.0"

from paritex.backends import load_backends as load_backends
from paritex.backends import run_backend as run_backend
from paritex.core import parity as parity
from paritex.extract import normalize as normalize
from paritex.extract import pdf_words as pdf_words
from paritex.papers import fetch as fetch
from paritex.project import evaluate as evaluate
from paritex.project import init_project as init_project
from paritex.project import reconstruct as reconstruct
from paritex.project import render as render
from paritex.types import Backend as Backend
from paritex.types import Divergence as Divergence
from paritex.types import Kind as Kind
from paritex.types import ParityReport as ParityReport
from paritex.types import ProjectReport as ProjectReport
from paritex.types import RenderError as RenderError
