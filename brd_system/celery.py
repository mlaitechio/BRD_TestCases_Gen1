import os
import ssl
import warnings
from celery import Celery

# ==============================================================================
# GLOBAL SSL VERIFICATION DISABLE (Bypass Enterprise Proxy & IP Mismatch)
# ==============================================================================
try:
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    def _custom_unverified_context(*args, **kwargs):
        ctx = ssl._create_unverified_context(*args, **kwargs)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ssl.create_default_context = _custom_unverified_context
except Exception:
    pass

os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
warnings.filterwarnings('ignore')
# ==============================================================================

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'brd_system.settings')

app = Celery('brd_system')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
