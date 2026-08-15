"""PDF -> LaTeX paper reconstruction with AI backends, and parity evaluation"""

__version__ = "0.1.0"

from paritex.backends import BUILTIN as BUILTIN
from paritex.backends import claude_backend as claude_backend
from paritex.backends import claude_stream_lines as claude_stream_lines
from paritex.backends import load_backends as load_backends
from paritex.backends import parse_backend as parse_backend
from paritex.backends import run_backend as run_backend
from paritex.core import page_starts as page_starts
from paritex.core import parity as parity
from paritex.extract import normalize as normalize
from paritex.extract import pdf_page_words as pdf_page_words
from paritex.extract import pdf_words as pdf_words
from paritex.gate import check_bib as check_bib
from paritex.layout import ASSETS as ASSETS
from paritex.layout import MAIN_TEX as MAIN_TEX
from paritex.layout import ORIGINAL as ORIGINAL
from paritex.layout import REBUILT as REBUILT
from paritex.layout import REFS_BIB as REFS_BIB
from paritex.layout import REPORT as REPORT
from paritex.papers import fetch as fetch
from paritex.project import evaluate as evaluate
from paritex.project import init_project as init_project
from paritex.project import reconstruct as reconstruct
from paritex.project import refine as refine
from paritex.project import render as render
from paritex.project import report_to_dict as report_to_dict
from paritex.types import Auth as Auth
from paritex.types import Backend as Backend
from paritex.types import BackendError as BackendError
from paritex.types import BibError as BibError
from paritex.types import Divergence as Divergence
from paritex.types import Kind as Kind
from paritex.types import ParityReport as ParityReport
from paritex.types import Progress as Progress
from paritex.types import ProjectReport as ProjectReport
from paritex.types import RenderError as RenderError
