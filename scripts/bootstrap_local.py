"""Generate private localhost settings. Never prints credentials or overwrites an existing setup."""
from pathlib import Path
import secrets, json, uuid

ROOT = Path(__file__).resolve().parents[1]
private = ROOT / 'runtime'
private.mkdir(exist_ok=True)
if (ROOT / '.env').exists():
    print('Existing configuration preserved; credentials are in runtime/LOCAL_ACCESS.md.')
    raise SystemExit(0)
for d in ['init', 'keycloak', 'data']:
    (private / d).mkdir(exist_ok=True)
secret = lambda: secrets.token_urlsafe(32)
rootpw, apppw, workerpw, operatorpw, clientsecret = [secret() for _ in range(5)]
tenant = str(uuid.uuid4())
people = []
for username, display, role in [('admin', 'Administrator', 'admin'), ('member-a', 'Member A', 'member'), ('member-b', 'Member B', 'member')]:
    people.append(dict(id=str(uuid.uuid4()), username=username, display=display, role=role,
                       email=f'{username}@sandhata.local', password=secret()))
realm = {
    'realm':'sandhata', 'enabled':True, 'displayName':'SANDHĀTĀ',
    'loginTheme':'sandhata', 'registrationAllowed':False, 'resetPasswordAllowed':False, 'rememberMe':False,
    'loginWithEmailAllowed':True, 'duplicateEmailsAllowed':False,
    'bruteForceProtected':True, 'accessTokenLifespan':300,
    'ssoSessionIdleTimeout':1800, 'ssoSessionMaxLifespan':28800,
    'clients':[{'clientId':'sandhata-web','enabled':True,'protocol':'openid-connect',
                'publicClient':False,'secret':clientsecret,'standardFlowEnabled':True,
                'directAccessGrantsEnabled':False,
                'redirectUris':['http://localhost:8605/oauth2callback'],
                'webOrigins':['http://localhost:8605']}],
    'users':[{'id':p['id'],'username':p['username'],'firstName':p['display'], 'lastName':'Account',
              'email':p['email'],'emailVerified':True,'enabled':True,
              'credentials':[{'type':'password','value':p['password'],'temporary':False}]} for p in people]
}
(private/'keycloak/sandhata-realm.json').write_text(json.dumps(realm, indent=2),encoding='utf-8')
(private/'identities.json').write_text(json.dumps(people, indent=2),encoding='utf-8')
(private/'init/001_roles.sql').write_text(
    f"CREATE ROLE sandhata_app LOGIN PASSWORD '{apppw}';\n"
    f"CREATE ROLE sandhata_worker LOGIN PASSWORD '{workerpw}';\n"
    'GRANT sandhata_app TO sandhata_worker;\n', encoding='utf-8')
env = {
    'POSTGRES_ROOT_PASSWORD':rootpw,'KEYCLOAK_OPERATOR_PASSWORD':operatorpw,
    'SANDHATA_DATABASE_URL':f'postgresql+psycopg://sandhata_app:{apppw}@127.0.0.1:8853/sandhata',
    'SANDHATA_WORKER_DATABASE_URL':f'postgresql+psycopg://sandhata_worker:{workerpw}@127.0.0.1:8853/sandhata',
    'SANDHATA_MIGRATION_URL':f'postgresql://postgres:{rootpw}@127.0.0.1:8853/sandhata',
    'SANDHATA_TENANT_ID':tenant,'SANDHATA_OIDC_ISSUER':'http://localhost:18180/realms/sandhata',
    'SANDHATA_MODEL_NAME':'gpt-oss:20b', 'SANDHATA_MODEL_BASE_URL':'http://127.0.0.1:11434',
    'SANDHATA_APP_URL':'http://localhost:8605'
}
(ROOT/'.env').write_text('\n'.join(f'{k}={v}' for k,v in env.items())+'\n',encoding='utf-8')
(ROOT/'.streamlit').mkdir(exist_ok=True)
(ROOT/'.streamlit/secrets.toml').write_text(
    '[auth]\nredirect_uri = "http://localhost:8605/oauth2callback"\n'
    f'cookie_secret = "{secret()}"\n\n[auth.keycloak]\nclient_id = "sandhata-web"\n'
    f'client_secret = "{clientsecret}"\nserver_metadata_url = "{env["SANDHATA_OIDC_ISSUER"]}/.well-known/openid-configuration"\n'
    'client_kwargs = {scope = "openid profile email", prompt = "login", max_age = 28800}\n',encoding='utf-8')
guide=['# SANDHATA localhost access','',
       'This file contains generated credentials. Do not commit, share publicly, or paste into chat.',
       '', 'Application: http://localhost:8605', 'Identity console: http://localhost:18180/admin',
       '', f'Identity operator: operator / {operatorpw}', '',
       'These identities are for the localhost pilot. Member identities must still accept an app invitation.', '']
for p in people: guide.append(f"- {p['display']}: `{p['username']}` / `{p['password']}`; email `{p['email']}`")
guide += ['', 'For additional user identities, the operator creates the identity in the Keycloak console, verifies its email, then an app administrator creates an invitation for that exact email.',
          'Localhost HTTP and the development identity store are not an internet production deployment.']
(private/'LOCAL_ACCESS.md').write_text('\n'.join(guide),encoding='utf-8')
print('Generated SANDHATA localhost settings. Open runtime/LOCAL_ACCESS.md locally for credentials.')
