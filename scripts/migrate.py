"""Apply versioned schema with separate migration credentials and bootstrap one administrator."""
from pathlib import Path
import os,json,sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from sandhata.config import ROOT, TENANT, ISSUER
import psycopg

parser=argparse.ArgumentParser()
parser.add_argument('--schema-only',action='store_true',help='Apply schema without the local pilot identity bootstrap')
args=parser.parse_args()
url=os.getenv('SANDHATA_MIGRATION_URL')
if not url: raise SystemExit('Missing private migration URL; run bootstrap_local.py.')
with psycopg.connect(url) as c:
    c.execute((ROOT/'src/sandhata/schema.sql').read_text(encoding='utf-8'))
    extra=ROOT/'src/sandhata/admin_schema.sql'
    if extra.exists(): c.execute(extra.read_text(encoding='utf-8'))
    if not args.schema_only:
        identities=json.loads((ROOT/'runtime/identities.json').read_text(encoding='utf-8'))
        p=next(x for x in identities if x['role']=='admin')
        c.execute('INSERT INTO accounts(id,issuer,subject,display_name,email) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(issuer,subject) DO NOTHING',
                  (p['id'],ISSUER,p['id'],p['display'],p['email']))
        c.execute("INSERT INTO memberships(tenant_id,user_id,role) VALUES(%s,%s,'admin') ON CONFLICT DO NOTHING",(TENANT,p['id']))
print('Schema applied; existing members preserved; first administrator provisioned.')
