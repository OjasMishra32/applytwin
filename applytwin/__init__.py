"""ApplyTwin: find internships and jobs, tailor a top-tier resume for each one, and let your own Claude Code or Codex apply."""
__version__ = '1.1.3'

import os as _os
import sys as _sys
_v = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '_vendor')
if _v not in _sys.path:
    _sys.path.append(_v)  # bundled pure-Python deps (pypdf, BSD-3) so it works with no installs
