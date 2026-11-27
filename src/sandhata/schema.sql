CREATE SCHEMA IF NOT EXISTS appsec;
REVOKE ALL ON SCHEMA appsec FROM PUBLIC;
GRANT USAGE ON SCHEMA appsec TO sandhata_app;
CREATE TABLE IF NOT EXISTS schema_versions (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS accounts (
 id uuid PRIMARY KEY, issuer text NOT NULL, subject text NOT NULL, display_name text NOT NULL,
 email text NOT NULL, timezone text NOT NULL DEFAULT 'America/New_York', UNIQUE(issuer,subject)
);
CREATE TABLE IF NOT EXISTS memberships (
 tenant_id uuid NOT NULL, user_id uuid NOT NULL REFERENCES accounts(id),
 role text NOT NULL CHECK(role IN ('member','admin')), state text NOT NULL DEFAULT 'active' CHECK(state IN ('active','suspended','deletion_pending')),
 auth_version integer NOT NULL DEFAULT 1,
 quota integer NOT NULL DEFAULT 100 CHECK(quota BETWEEN 1 AND 1000),
 last_seen timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,user_id)
);
CREATE TABLE IF NOT EXISTS invitations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, email_hash text NOT NULL,
 email_hint text NOT NULL, issuer text NOT NULL, token_hash text NOT NULL UNIQUE,
 role text NOT NULL CHECK(role IN ('member','admin')), expires_at timestamptz NOT NULL,
 redeemed_at timestamptz, revoked boolean NOT NULL DEFAULT false, inviter uuid NOT NULL REFERENCES accounts(id)
);
CREATE TABLE IF NOT EXISTS public_cache (key text PRIMARY KEY, data jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS admin_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, tenant_id uuid NOT NULL, actor_id uuid NOT NULL,
 action text NOT NULL, target text NOT NULL, reason text NOT NULL, metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS profiles (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL,
 label text NOT NULL, filters jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,owner_user_id,id)
);
CREATE TABLE IF NOT EXISTS jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL,
 title text NOT NULL, company text NOT NULL, location text NOT NULL DEFAULT '', salary text NOT NULL DEFAULT '',
 source text NOT NULL, original_url text NOT NULL DEFAULT '', source_key text NOT NULL, workplace text NOT NULL DEFAULT '',
 created_at timestamptz NOT NULL DEFAULT now(), last_checked timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,owner_user_id,id), UNIQUE(tenant_id,owner_user_id,source,source_key)
);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_type text NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_new boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS watchlists (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL,
 provider text NOT NULL CHECK(provider IN ('Greenhouse','Lever','Ashby')), board text NOT NULL, company text NOT NULL,
 last_checked timestamptz, last_note text NOT NULL DEFAULT '', created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,owner_user_id,provider,board)
);
CREATE TABLE IF NOT EXISTS job_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL, job_id uuid NOT NULL,
 body text NOT NULL, raw_html text NOT NULL, content_hash text NOT NULL, completeness text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,owner_user_id,id),
 UNIQUE(tenant_id,owner_user_id,job_id,content_hash),
 FOREIGN KEY(tenant_id,owner_user_id,job_id) REFERENCES jobs(tenant_id,owner_user_id,id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS resumes (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL, label text NOT NULL,
 object_key text NOT NULL, file_hash text NOT NULL, body text NOT NULL, parser_version text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,owner_user_id,id)
);
ALTER TABLE resumes ADD COLUMN IF NOT EXISTS doc_type text NOT NULL DEFAULT 'resume' CHECK(doc_type IN ('resume','cover_letter','other'));
ALTER TABLE resumes ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true;
CREATE TABLE IF NOT EXISTS passages (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL,
 parent_id uuid NOT NULL, parent_type text NOT NULL CHECK(parent_type IN ('resume','job')),
 start_offset integer NOT NULL, body text NOT NULL,
 search_doc tsvector GENERATED ALWAYS AS (to_tsvector('simple',body)) STORED
);
CREATE INDEX IF NOT EXISTS passage_search_idx ON passages USING gin(search_doc);
CREATE INDEX IF NOT EXISTS passage_scope_idx ON passages(tenant_id,owner_user_id,parent_id);
CREATE TABLE IF NOT EXISTS applications (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL, job_id uuid NOT NULL,
 resume_id uuid, status text NOT NULL DEFAULT 'Saved', notes text NOT NULL DEFAULT '',
 applied_at timestamptz, follow_up date, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,owner_user_id,id), UNIQUE(tenant_id,owner_user_id,job_id),
 FOREIGN KEY(tenant_id,owner_user_id,job_id) REFERENCES jobs(tenant_id,owner_user_id,id),
 FOREIGN KEY(tenant_id,owner_user_id,resume_id) REFERENCES resumes(tenant_id,owner_user_id,id)
);
ALTER TABLE applications ADD COLUMN IF NOT EXISTS recruiter text NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS status_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL,
 application_id uuid NOT NULL, status text NOT NULL, occurred_at timestamptz NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(), request_id text NOT NULL,
 UNIQUE(tenant_id,owner_user_id,request_id),
 FOREIGN KEY(tenant_id,owner_user_id,application_id) REFERENCES applications(tenant_id,owner_user_id,id)
);
CREATE TABLE IF NOT EXISTS assessments (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL,
 resume_id uuid NOT NULL, job_version_id uuid NOT NULL, cache_key text NOT NULL,
 result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,owner_user_id,cache_key),
 FOREIGN KEY(tenant_id,owner_user_id,resume_id) REFERENCES resumes(tenant_id,owner_user_id,id),
 FOREIGN KEY(tenant_id,owner_user_id,job_version_id) REFERENCES job_versions(tenant_id,owner_user_id,id)
);
CREATE TABLE IF NOT EXISTS tasks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL,
 auth_version integer NOT NULL, kind text NOT NULL CHECK(kind IN ('compare')),
 payload jsonb NOT NULL, request_id text NOT NULL, state text NOT NULL DEFAULT 'queued',
 attempts integer NOT NULL DEFAULT 0, lease_until timestamptz, error_code text,
 trace jsonb NOT NULL DEFAULT '[]', result_id uuid, created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
 UNIQUE(tenant_id,owner_user_id,request_id)
);
CREATE TABLE IF NOT EXISTS capabilities (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL,
 token_hash text NOT NULL UNIQUE, auth_version integer NOT NULL, expires_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION appsec.is_admin() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=public,pg_temp AS $$
 SELECT EXISTS(SELECT 1 FROM memberships WHERE tenant_id::text=current_setting('app.tenant_id',true)
 AND user_id::text=current_setting('app.user_id',true) AND role='admin' AND state='active')
$$;
CREATE OR REPLACE FUNCTION appsec.resolve_identity(i text,s text) RETURNS TABLE(user_id uuid,tenant_id uuid,role text,state text,auth_version integer,display_name text,timezone text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
 SELECT a.id,m.tenant_id,m.role,m.state,m.auth_version,a.display_name,a.timezone FROM accounts a JOIN memberships m ON m.user_id=a.id
 WHERE a.issuer=i AND a.subject=s
$$;
CREATE OR REPLACE FUNCTION appsec.redeem_invitation(i text,s text,e text,n text,h text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE inv invitations; uid uuid;
BEGIN
 SELECT * INTO inv FROM invitations WHERE token_hash=h AND issuer=i AND email_hash=encode(sha256(convert_to(lower(e),'UTF8')),'hex')
 AND expires_at>now() AND redeemed_at IS NULL AND NOT revoked FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'invalid_invitation'; END IF;
 INSERT INTO accounts(id,issuer,subject,email,display_name) VALUES(gen_random_uuid(),i,s,lower(e),left(n,100))
 ON CONFLICT(issuer,subject) DO UPDATE SET display_name=EXCLUDED.display_name RETURNING id INTO uid;
 IF EXISTS(SELECT 1 FROM memberships WHERE tenant_id=inv.tenant_id AND user_id=uid) THEN RAISE EXCEPTION 'membership_exists'; END IF;
 INSERT INTO memberships(tenant_id,user_id,role) VALUES(inv.tenant_id,uid,inv.role);
 UPDATE invitations SET redeemed_at=now() WHERE id=inv.id;
 INSERT INTO admin_audit(tenant_id,actor_id,action,target,reason) VALUES(inv.tenant_id,uid,'invitation_redeemed',inv.id::text,'Identity-bound redemption');
 RETURN uid;
END $$;
CREATE OR REPLACE FUNCTION appsec.capability_scope(h text) RETURNS TABLE(user_id uuid,tenant_id uuid,role text,state text,auth_version integer,display_name text,timezone text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
 SELECT a.id,m.tenant_id,m.role,m.state,m.auth_version,a.display_name,a.timezone
 FROM capabilities c JOIN memberships m ON m.tenant_id=c.tenant_id AND m.user_id=c.owner_user_id JOIN accounts a ON a.id=m.user_id
 WHERE c.token_hash=h AND c.expires_at>now() AND c.auth_version=m.auth_version AND m.state='active'
$$;
CREATE OR REPLACE FUNCTION appsec.claim_task() RETURNS SETOF tasks LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE tid uuid;
BEGIN
 UPDATE tasks SET state='failed',error_code='worker_lease_exhausted',finished_at=now(),lease_until=NULL WHERE state='running' AND lease_until<now() AND attempts>=2;
 SELECT t.id INTO tid FROM tasks t JOIN memberships m ON m.tenant_id=t.tenant_id AND m.user_id=t.owner_user_id
 WHERE (t.state='queued' OR (t.state='running' AND t.lease_until<now())) AND t.attempts<2
 AND m.state='active' AND m.auth_version=t.auth_version ORDER BY t.created_at FOR UPDATE OF t SKIP LOCKED LIMIT 1;
 RETURN QUERY UPDATE tasks SET state='running',lease_until=now()+interval '10 minutes',attempts=attempts+1 WHERE id=tid RETURNING *;
END $$;

DO $$ DECLARE tbl text; BEGIN
 FOREACH tbl IN ARRAY ARRAY['profiles','jobs','job_versions','resumes','passages','applications','status_events','assessments','tasks','capabilities','watchlists'] LOOP
 EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tbl);
 EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tbl);
 EXECUTE format('DROP POLICY IF EXISTS owned ON %I',tbl);
 EXECUTE format('CREATE POLICY owned ON %I USING (tenant_id::text=current_setting(''app.tenant_id'',true) AND owner_user_id::text=current_setting(''app.user_id'',true)) WITH CHECK (tenant_id::text=current_setting(''app.tenant_id'',true) AND owner_user_id::text=current_setting(''app.user_id'',true))',tbl);
 EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON %I TO sandhata_app',tbl);
 END LOOP;
END $$;
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS membership_access ON memberships;
CREATE POLICY membership_access ON memberships USING (tenant_id::text=current_setting('app.tenant_id',true) AND (user_id::text=current_setting('app.user_id',true) OR appsec.is_admin()))
 WITH CHECK(tenant_id::text=current_setting('app.tenant_id',true) AND appsec.is_admin());
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS invitation_access ON invitations;
CREATE POLICY invitation_access ON invitations USING(tenant_id::text=current_setting('app.tenant_id',true) AND appsec.is_admin()) WITH CHECK(tenant_id::text=current_setting('app.tenant_id',true) AND appsec.is_admin());
ALTER TABLE admin_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_audit FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_read ON admin_audit;
CREATE POLICY audit_read ON admin_audit FOR SELECT USING(tenant_id::text=current_setting('app.tenant_id',true) AND appsec.is_admin());
DROP POLICY IF EXISTS audit_append ON admin_audit;
CREATE POLICY audit_append ON admin_audit FOR INSERT WITH CHECK(tenant_id::text=current_setting('app.tenant_id',true) AND actor_id::text=current_setting('app.user_id',true) AND appsec.is_admin());
GRANT SELECT ON accounts TO sandhata_app;
GRANT SELECT,UPDATE ON memberships TO sandhata_app;
GRANT SELECT,INSERT,UPDATE ON invitations TO sandhata_app;
GRANT SELECT,INSERT ON admin_audit TO sandhata_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sandhata_app;
GRANT SELECT,INSERT,UPDATE ON public_cache TO sandhata_app;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA appsec FROM PUBLIC;
GRANT EXECUTE ON FUNCTION appsec.is_admin(),appsec.resolve_identity(text,text),appsec.redeem_invitation(text,text,text,text,text),appsec.capability_scope(text) TO sandhata_app;
GRANT EXECUTE ON FUNCTION appsec.claim_task() TO sandhata_worker;
INSERT INTO schema_versions(version) VALUES(1) ON CONFLICT DO NOTHING;
