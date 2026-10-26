"""Create a disposable database; never run tests against family application data."""
from pathlib import Path
import sys,os,secrets,subprocess,json
from dotenv import load_dotenv
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
base=os.environ['SANDHATA_MIGRATION_URL']
name='sandhata_test_'+secrets.token_hex(4)
admin=conninfo_to_dict(base);admin['dbname']='postgres'
test=conninfo_to_dict(base);test['dbname']=name
env=os.environ.copy()
env['SANDHATA_MIGRATION_URL']=make_conninfo(**test)
for key in ['SANDHATA_DATABASE_URL','SANDHATA_WORKER_DATABASE_URL']:
    env[key]=make_url(env[key]).set(database=name).render_as_string(hide_password=False)
env['SANDHATA_TENANT_ID']='00000000-0000-0000-0000-000000000002'
env['PYTHONPATH']=str(ROOT/'src')
with psycopg.connect(make_conninfo(**admin),autocommit=True) as c:
    c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
try:
    migrate=subprocess.run([sys.executable,str(ROOT/'scripts/migrate.py')],cwd=ROOT,env=env,capture_output=True,text=True)
    if migrate.returncode: print(migrate.stderr);raise SystemExit(migrate.returncode)
    result=subprocess.run([sys.executable,'-m','pytest','-q','--tb=short',*sys.argv[1:]],cwd=ROOT,env=env,capture_output=True,text=True)
    print(result.stdout)
    if result.stderr:print(result.stderr)
    target=ROOT/'deliverables/verification';target.mkdir(parents=True,exist_ok=True)
    (target/'application_tests.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
finally:
    if not name.startswith('sandhata_test_'):raise RuntimeError('Refusing non-test cleanup')
    with psycopg.connect(make_conninfo(**admin),autocommit=True) as c:
        c.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
if 'result' in locals():raise SystemExit(result.returncode)
