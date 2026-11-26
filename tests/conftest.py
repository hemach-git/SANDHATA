import uuid,os,json,shutil
from pathlib import Path
import pytest,psycopg
from sandhata.config import DATA,ISSUER
from sandhata.db import Principal

@pytest.fixture
def family():
    tenant=str(uuid.uuid4()); users=[str(uuid.uuid4()) for _ in range(3)]
    url=os.getenv('SANDHATA_MIGRATION_URL')
    if not url: pytest.fail('Run bootstrap_local.py and migrate.py before integration tests.')
    with psycopg.connect(url) as c:
        for uid,name,role in zip(users,['Fixture Admin','Fixture Member A','Fixture Member B'],['admin','member','member']):
            c.execute('INSERT INTO accounts(id,issuer,subject,email,display_name) VALUES(%s,%s,%s,%s,%s)',(uid,ISSUER,'test-'+uid,uid+'@fixture.local',name))
            c.execute('INSERT INTO memberships(tenant_id,user_id,role) VALUES(%s,%s,%s)',(tenant,uid,role))
    principals=[Principal(uid,tenant,role,1,name) for uid,role,name in zip(users,['admin','member','member'],['Fixture Admin','Fixture Member A','Fixture Member B'])]
    yield principals
    with psycopg.connect(url) as c:
        # Test-created tenant UUID only; never truncate or delete the owner's real tenant.
        for table in ['maintenance_receipts','deletion_tombstones','capabilities','tasks','assessments','status_events','applications','passages','resumes','job_versions','jobs','profiles','watchlists','admin_audit','invitations','memberships']:
            c.execute(f'DELETE FROM {table} WHERE tenant_id=%s',(tenant,))
        c.execute('DELETE FROM accounts WHERE id=ANY(%s::uuid[])',(users,))
    folder=(DATA/tenant).resolve()
    assert folder.is_relative_to(DATA.resolve()) and folder.name==tenant
    if folder.exists(): shutil.rmtree(folder)

@pytest.fixture
def docx_bytes():
    from docx import Document
    from io import BytesIO
    d=Document();d.add_heading('Synthetic Engineering Resume',0)
    d.add_paragraph('Built Python data pipelines and SQL analytics on AWS. Delivered reliable ETL services and stakeholder reports. Led project delivery and testing.')
    out=BytesIO();d.save(out);return out.getvalue()

@pytest.fixture
def job_text(): return 'Required skills: Python and SQL. Build data pipelines on AWS. Preferred experience: Kubernetes. This synthetic role is remote in the United States.'
