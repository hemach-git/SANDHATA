from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from sqlalchemy import create_engine
from .config import DATABASE_URL, WORKER_DATABASE_URL, TENANT, AppError, require_config

@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    role: str
    auth_version: int
    display_name: str = ''
    timezone: str = 'America/New_York'

@lru_cache(maxsize=2)
def engine(worker=False):
    require_config()
    return create_engine(WORKER_DATABASE_URL if worker else DATABASE_URL, pool_pre_ping=True, pool_size=8, max_overflow=4)

def rows(c, sql, params=None):
    return [dict(r) for r in c.exec_driver_sql(sql, params or {}).mappings().all()]

def one(c, sql, params=None):
    found=rows(c,sql,params)
    return found[0] if found else None

def resolve_identity(issuer, subject):
    # Only call with validated OIDC claims, never browser form fields or model output.
    with engine().begin() as c:
        r=one(c,'SELECT * FROM appsec.resolve_identity(%(issuer)s,%(subject)s) WHERE tenant_id=%(tenant)s::uuid',
              dict(issuer=issuer,subject=subject,tenant=TENANT))
    if not r or r['state']!='active':
        return None
    return Principal(str(r['user_id']),str(r['tenant_id']),r['role'],r['auth_version'],r['display_name'],r['timezone'])

@contextmanager
def transaction(p: Principal, admin=False, worker=False):
    if not isinstance(p,Principal): raise AppError('Authentication required.')
    with engine(worker).begin() as c:
        c.exec_driver_sql("SELECT set_config('app.tenant_id',%(tenant)s,true),set_config('app.user_id',%(user)s,true)",dict(tenant=p.tenant_id,user=p.user_id))
        if admin:
            c.exec_driver_sql('SELECT pg_advisory_xact_lock(hashtextextended(%(t)s,0))',dict(t=p.tenant_id))
        # Lock membership until commit; suspension waits for in-flight writes then denies future operations.
        m=one(c,'SELECT role,state,auth_version FROM memberships WHERE tenant_id=%(t)s::uuid AND user_id=%(u)s::uuid FOR SHARE',dict(t=p.tenant_id,u=p.user_id))
        if not m or m['state']!='active' or m['auth_version']!=p.auth_version:
            raise AppError('Your access has changed. Sign in again or contact your administrator.')
        if admin and m['role']!='admin': raise AppError('Administrator permission required.')
        yield c

def scoped(p, **extra): return dict(t=p.tenant_id,u=p.user_id,**extra)
