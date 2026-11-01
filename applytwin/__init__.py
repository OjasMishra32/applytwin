"""ApplyTwin: find internships and jobs, tailor a top-tier resume for each one, and let your own Claude Code or Codex apply."""
__version__ = '1.3.23'

import os as _os
import ssl as _ssl
import sys as _sys

# Python from python.org on macOS ships without root certificates (until "Install Certificates.command" is run), which
# silently breaks sign-in, updates and job scans. Fall back to the certificates the OS already has.
try:
    if not _os.path.exists(_ssl.get_default_verify_paths().cafile or ''):
        _ca = next((p for p in ('/etc/ssl/cert.pem', '/etc/ssl/certs/ca-certificates.crt', '/etc/pki/tls/certs/ca-bundle.crt')
                    if _os.path.exists(p)), None)
        try:
            import certifi as _certifi
            _ca = _certifi.where()
        except ImportError:
            pass
        if _ca:
            _ssl._create_default_https_context = lambda *a, **k: _ssl.create_default_context(cafile=_ca)
except Exception:
    pass
_v = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '_vendor')
if _v not in _sys.path:
    _sys.path.append(_v)  # bundled pure-Python deps (pypdf, BSD-3) so it works with no installs
