"""Encrypted application backup and isolated restore verification. Identity-provider backup is separate."""
import os,sys,json,secrets,hashlib,subprocess,zipfile,io
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from sandhata.config import ROOT,DATA
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def run(*args,input=None):
    p=subprocess.run(args,cwd=ROOT,input=input,capture_output=True)
    if p.returncode: raise RuntimeError('Database backup/restore command failed; no sensitive diagnostics were printed.')
    return p.stdout

def main():
    directory=ROOT/'backups';directory.mkdir(exist_ok=True)
    keypath=ROOT/'runtime/backup.key'
    if not keypath.exists(): keypath.write_bytes(AESGCM.generate_key(bit_length=256))
    key=keypath.read_bytes()
    tables=['profiles','jobs','job_versions','resumes','passages','applications','status_events','assessments','tasks','capabilities','memberships','invitations','admin_audit','deletion_tombstones','maintenance_receipts','watchlists','tailor_runs','tailor_suggestions','suggestion_decisions']
    with psycopg.connect(os.environ['SANDHATA_MIGRATION_URL']) as c:
        # A database that has not been migrated yet must still be backed up, so skip tables it does not have.
        tables=[name for name in tables if c.execute('SELECT to_regclass(%s) IS NOT NULL',(name,)).fetchone()[0]]
        # Lock before exporting a snapshot: upload/delete/worker changes wait until all referenced files are copied.
        c.execute(sql.SQL('LOCK TABLE {} IN SHARE MODE').format(sql.SQL(',').join(map(sql.Identifier,tables))))
        snapshot=c.execute('SELECT pg_export_snapshot()').fetchone()[0]
        counts={name:c.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(name))).fetchone()[0] for name in tables}
        objects=c.execute('SELECT object_key,file_hash FROM resumes').fetchall()
        dump=run('docker','compose','exec','-T','postgres','pg_dump','-U','postgres','-d','sandhata','-Fc','--snapshot='+snapshot)
        content=io.BytesIO()
        with zipfile.ZipFile(content,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('database.dump',dump)
            for keyname,expected_hash in objects:
                path=(DATA/keyname).resolve()
                if not path.is_relative_to(DATA) or not path.is_file(): raise RuntimeError('Referenced original missing; backup not certified.')
                data=path.read_bytes()
                if hashlib.sha256(data).hexdigest()!=expected_hash: raise RuntimeError('Original fingerprint mismatch')
                z.writestr('originals/'+keyname.replace('\\','/'),data)
            z.writestr('manifest.json',json.dumps(dict(counts=counts,objects=len(objects),created_at=datetime.now(timezone.utc).isoformat())))
    nonce=secrets.token_bytes(12)
    encrypted=b'SANDHATA1'+nonce+AESGCM(key).encrypt(nonce,content.getvalue(),b'sandhata-backup-v1')
    target=directory/('sandhata-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.enc')
    target.write_bytes(encrypted)
    # Decrypt the saved artifact and restore to a new, explicitly disposable database.
    saved=target.read_bytes();plain=AESGCM(key).decrypt(saved[9:21],saved[21:],b'sandhata-backup-v1')
    archive=zipfile.ZipFile(io.BytesIO(plain));manifest=json.loads(archive.read('manifest.json'))
    dbname='sandhata_restore_'+secrets.token_hex(4)
    settings=conninfo_to_dict(os.environ['SANDHATA_MIGRATION_URL']);settings['dbname']='postgres'
    with psycopg.connect(make_conninfo(**settings),autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(dbname)))
    try:
        run('docker','compose','exec','-T','postgres','pg_restore','-U','postgres','-d',dbname,'--exit-on-error',input=archive.read('database.dump'))
        settings['dbname']=dbname
        with psycopg.connect(make_conninfo(**settings)) as restored:
            for table,expected in manifest['counts'].items():
                actual=restored.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
                if actual!=expected: raise RuntimeError('Restore count mismatch')
            for keyname,expected_hash in restored.execute('SELECT object_key,file_hash FROM resumes').fetchall():
                if hashlib.sha256(archive.read('originals/'+keyname.replace('\\','/'))).hexdigest()!=expected_hash: raise RuntimeError('Restored original fingerprint mismatch')
            policies=restored.execute("SELECT count(*) FROM pg_class WHERE relname IN ('jobs','resumes','assessments','passages') AND relforcerowsecurity").fetchone()[0]
            if policies!=4: raise RuntimeError('RLS restore verification failed')
        report=dict(created_at=datetime.now(timezone.utc).isoformat(),status='encrypted_backup_and_isolated_restore_verified',file=target.name,sha256=hashlib.sha256(encrypted).hexdigest(),restored_tables=len(tables),originals=manifest['objects'],original_fingerprints='verified',identity_provider_backup='separate_operator_requirement',tombstones='included; reconcile with current tombstones before any real restore')
        (ROOT/'runtime/last_backup.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        public={k:v for k,v in report.items() if k not in ('file','sha256')}
        (ROOT/'deliverables/verification/backup_restore.json').write_text(json.dumps(public,indent=2),encoding='utf-8')
        print('Encrypted backup decrypted and restored successfully to an isolated disposable database. Keep runtime/backup.key separately in a secure vault.')
    finally:
        if not dbname.startswith('sandhata_restore_'): raise RuntimeError('Unsafe restore cleanup')
        settings['dbname']='postgres'
        with psycopg.connect(make_conninfo(**settings),autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(dbname)))

if __name__=='__main__': main()
