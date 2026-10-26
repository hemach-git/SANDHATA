import hashlib,secrets,json
from .config import ISSUER,AppError
from .db import engine,one,rows,transaction,scoped,Principal

def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def accept_invitation(claims,token):
    if claims.get('iss')!=ISSUER or not claims.get('sub') or claims.get('email_verified') is not True:
        raise AppError('A verified identity from the configured provider is required.')
    try:
        with engine().begin() as c:
            c.exec_driver_sql('SELECT appsec.redeem_invitation(%(i)s,%(s)s,%(e)s,%(n)s,%(h)s)',
                dict(i=ISSUER,s=claims['sub'],e=claims.get('email',''),n=claims.get('name',claims.get('preferred_username','Member')),h=digest(token)))
    except Exception as exc:
        raise AppError('Invitation invalid, expired, already redeemed, or not intended for this identity.') from exc

def audit(c,p,action,target,reason,metadata=None):
    c.exec_driver_sql('INSERT INTO admin_audit(tenant_id,actor_id,action,target,reason,metadata) VALUES(%(t)s::uuid,%(u)s::uuid,%(a)s,%(target)s,%(r)s,%(m)s::jsonb)',
                     scoped(p,a=action,target=str(target),r=reason[:300],m=json.dumps(metadata or {})))

def invite(p,email,role='member'):
    email=email.strip().lower()
    if '@' not in email or len(email)>200 or role not in ('member','admin'): raise AppError('Enter a valid email and role.')
    token=secrets.token_urlsafe(32)
    with transaction(p,admin=True) as c:
        r=one(c,"INSERT INTO invitations(tenant_id,email_hash,email_hint,issuer,token_hash,role,expires_at,inviter) VALUES(%(t)s::uuid,%(hash)s,%(hint)s,%(issuer)s,%(token)s,%(role)s,now()+interval '48 hours',%(u)s::uuid) RETURNING id",scoped(p,hash=digest(email),hint=email,issuer=ISSUER,token=digest(token),role=role))
        audit(c,p,'invitation_created',r['id'],'Administrator created identity-bound invitation',dict(role=role))
    return token

def list_accounts(p):
    with transaction(p,admin=True) as c:
        return rows(c,'SELECT m.user_id,a.display_name,a.email,m.role,m.state,m.quota,m.last_seen FROM memberships m JOIN accounts a ON a.id=m.user_id ORDER BY a.display_name')

def list_invitations(p):
    with transaction(p,admin=True) as c:
        return rows(c,'SELECT id,email_hint,role,expires_at,redeemed_at,revoked FROM invitations ORDER BY expires_at DESC LIMIT 100')

def revoke_invitation(p,invitation_id):
    with transaction(p,admin=True) as c:
        r=one(c,'UPDATE invitations SET revoked=true WHERE id=%(id)s::uuid AND redeemed_at IS NULL RETURNING id',dict(id=str(invitation_id)))
        if not r: raise AppError('Invitation unavailable.')
        audit(c,p,'invitation_revoked',invitation_id,'Administrator revoked invitation')

def change_account(p,user_id,role,state,quota,reason):
    if role not in ('admin','member') or state not in ('active','suspended') or not 1<=int(quota)<=1000 or len(reason.strip())<5:
        raise AppError('Choose a valid role, state and quota, and include a reason of at least five characters.')
    with transaction(p,admin=True) as c:
        c.exec_driver_sql('SELECT pg_advisory_xact_lock(hashtextextended(%(t)s,0))',dict(t=p.tenant_id))
        old=one(c,'SELECT * FROM memberships WHERE user_id=%(id)s::uuid FOR UPDATE',dict(id=str(user_id)))
        if not old or old['state']=='deletion_pending': raise AppError('Account unavailable.')
        if old['role']=='admin' and old['state']=='active' and (role!='admin' or state!='active'):
            n=one(c,"SELECT count(*) n FROM memberships WHERE role='admin' AND state='active'")['n']
            if n<=1: raise AppError('The last active administrator must remain active.')
        c.exec_driver_sql('UPDATE memberships SET role=%(r)s,state=%(s)s,quota=%(q)s,auth_version=auth_version+1 WHERE user_id=%(id)s::uuid',dict(r=role,s=state,q=int(quota),id=str(user_id)))
        audit(c,p,'membership_changed',user_id,reason,dict(role=role,state=state,quota=int(quota)))

def admin_metrics(p):
    with transaction(p,admin=True) as c: return one(c,'SELECT appsec.admin_metrics() data')['data']

def audit_events(p):
    with transaction(p,admin=True) as c: return rows(c,'SELECT actor_id,action,target,reason,metadata,created_at FROM admin_audit ORDER BY created_at DESC LIMIT 200')

def maintenance(p,kind,target=None,preview=True,count=0,request_id='',reason=''):
    with transaction(p,admin=True) as c:
        result=one(c,'SELECT appsec.housekeeping(%(k)s,%(target)s::uuid,%(preview)s,%(n)s,%(rid)s,%(why)s) data',
                   dict(k=kind,target=str(target) if target else None,preview=preview,n=count,rid=request_id,why=reason))['data']
    if not preview:
        from .repository import private_path
        for key in result.get('object_keys',[]): private_path(key).unlink(missing_ok=True)
    return {k:v for k,v in result.items() if k!='object_keys'}

def issue_capability(p):
    token=secrets.token_urlsafe(32)
    with transaction(p) as c:
        c.exec_driver_sql("INSERT INTO capabilities(tenant_id,owner_user_id,token_hash,auth_version,expires_at) VALUES(%(t)s::uuid,%(u)s::uuid,%(h)s,%(v)s,now()+interval '15 minutes')",scoped(p,h=digest(token),v=p.auth_version))
    return token

def capability_principal(token):
    with engine().begin() as c: r=one(c,'SELECT * FROM appsec.capability_scope(%(h)s)',dict(h=digest(token)))
    if not r: raise AppError('Capability expired or revoked. Create a new capability in the signed-in app.')
    return Principal(str(r['user_id']),str(r['tenant_id']),r['role'],r['auth_version'],r['display_name'],r['timezone'])
