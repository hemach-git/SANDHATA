CREATE TABLE IF NOT EXISTS maintenance_receipts (
 tenant_id uuid NOT NULL, request_id text NOT NULL, result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,request_id)
);
CREATE TABLE IF NOT EXISTS deletion_tombstones (
 tenant_id uuid NOT NULL, owner_user_id uuid NOT NULL, object_id uuid NOT NULL, object_type text NOT NULL,
 deleted_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant_id,owner_user_id,object_id)
);
ALTER TABLE deletion_tombstones ENABLE ROW LEVEL SECURITY;
ALTER TABLE deletion_tombstones FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tombstone_owner ON deletion_tombstones;
CREATE POLICY tombstone_owner ON deletion_tombstones USING(tenant_id::text=current_setting('app.tenant_id',true) AND owner_user_id::text=current_setting('app.user_id',true)) WITH CHECK(tenant_id::text=current_setting('app.tenant_id',true) AND owner_user_id::text=current_setting('app.user_id',true));
GRANT SELECT,INSERT ON deletion_tombstones TO sandhata_app;

CREATE OR REPLACE FUNCTION appsec.admin_metrics() RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE t uuid; result jsonb;
BEGIN
 IF NOT appsec.is_admin() THEN RAISE EXCEPTION 'admin_required'; END IF;
 t:=current_setting('app.tenant_id')::uuid;
 SELECT jsonb_build_object('members',(SELECT count(*) FROM memberships WHERE tenant_id=t),
 'active',(SELECT count(*) FROM memberships WHERE tenant_id=t AND state='active'),
 'queued',(SELECT count(*) FROM tasks WHERE tenant_id=t AND state IN ('queued','running')),
 'failed',(SELECT count(*) FROM tasks WHERE tenant_id=t AND state='failed' AND created_at>now()-interval '24 hours'),
 'public_cache_age_seconds',(SELECT extract(epoch FROM now()-max(updated_at)) FROM public_cache),
 'usage',coalesce((SELECT jsonb_agg(s) FROM (SELECT m.user_id,m.quota,
 (SELECT count(*) FROM resumes r WHERE r.tenant_id=t AND r.owner_user_id=m.user_id) resume_versions,
 (SELECT count(*) FROM tasks q WHERE q.tenant_id=t AND q.owner_user_id=m.user_id AND q.created_at>date_trunc('day',now())) comparisons_today
 FROM memberships m WHERE m.tenant_id=t) s),'[]'::jsonb)) INTO result;
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION appsec.housekeeping(k text,target_user uuid,preview boolean,expected_count integer,rid text,why text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE t uuid; n integer; keys jsonb:='[]'; result jsonb; tbl text;
BEGIN
 IF NOT appsec.is_admin() THEN RAISE EXCEPTION 'admin_required'; END IF;
 t:=current_setting('app.tenant_id')::uuid;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text,0));
 SELECT r.result INTO result FROM maintenance_receipts r WHERE r.tenant_id=t AND r.request_id=rid;
 IF FOUND AND NOT preview THEN RETURN result; END IF;
 IF k='expired_invitations' THEN
   SELECT count(*) INTO n FROM invitations WHERE tenant_id=t AND expires_at<now() AND NOT revoked AND redeemed_at IS NULL;
 ELSIF k='old_tasks' THEN
   SELECT count(*) INTO n FROM tasks WHERE tenant_id=t AND state IN ('completed','failed','cancelled') AND created_at<now()-interval '14 days';
 ELSIF k='cancel_revoked_tasks' THEN
   SELECT count(*) INTO n FROM tasks q JOIN memberships m ON m.user_id=q.owner_user_id AND m.tenant_id=q.tenant_id WHERE q.tenant_id=t AND q.state IN ('queued','running') AND (m.state<>'active' OR m.auth_version<>q.auth_version);
 ELSIF k='erase_account' THEN
   IF target_user::text=current_setting('app.user_id') THEN RAISE EXCEPTION 'use_another_admin_for_own_erasure'; END IF;
   IF NOT EXISTS(SELECT 1 FROM memberships WHERE tenant_id=t AND user_id=target_user) THEN RAISE EXCEPTION 'target_not_found'; END IF;
   SELECT count(*) INTO n FROM resumes WHERE tenant_id=t AND owner_user_id=target_user;
   n:=n+(SELECT count(*) FROM jobs WHERE tenant_id=t AND owner_user_id=target_user);
 ELSE RAISE EXCEPTION 'maintenance_not_allowed'; END IF;
 IF preview THEN RETURN jsonb_build_object('kind',k,'count',n,'target',target_user); END IF;
 IF n<>expected_count THEN RAISE EXCEPTION 'preview_changed'; END IF;
 IF length(trim(why))<5 THEN RAISE EXCEPTION 'reason_required'; END IF;
 IF k='expired_invitations' THEN
   UPDATE invitations SET revoked=true WHERE tenant_id=t AND expires_at<now() AND NOT revoked AND redeemed_at IS NULL;
 ELSIF k='old_tasks' THEN
   DELETE FROM tasks WHERE tenant_id=t AND state IN ('completed','failed','cancelled') AND created_at<now()-interval '14 days';
 ELSIF k='cancel_revoked_tasks' THEN
   UPDATE tasks q SET state='cancelled',finished_at=now(),error_code='access_revoked' FROM memberships m WHERE q.tenant_id=t AND q.owner_user_id=m.user_id AND q.tenant_id=m.tenant_id AND q.state IN ('queued','running') AND (m.state<>'active' OR m.auth_version<>q.auth_version);
 ELSE
   IF (SELECT role FROM memberships WHERE tenant_id=t AND user_id=target_user)='admin' AND (SELECT count(*) FROM memberships WHERE tenant_id=t AND role='admin' AND state='active')<=1 THEN RAISE EXCEPTION 'last_admin'; END IF;
   UPDATE memberships SET state='deletion_pending',auth_version=auth_version+1 WHERE tenant_id=t AND user_id=target_user;
   SELECT coalesce(jsonb_agg(object_key),'[]') INTO keys FROM resumes WHERE tenant_id=t AND owner_user_id=target_user;
   INSERT INTO deletion_tombstones(tenant_id,owner_user_id,object_id,object_type) SELECT t,target_user,id,'resume' FROM resumes WHERE tenant_id=t AND owner_user_id=target_user ON CONFLICT DO NOTHING;
   FOREACH tbl IN ARRAY ARRAY['capabilities','tasks','assessments','status_events','applications','passages','resumes','job_versions','jobs','profiles'] LOOP
     EXECUTE format('DELETE FROM %I WHERE tenant_id=$1 AND owner_user_id=$2',tbl) USING t,target_user;
   END LOOP;
 END IF;
 result:=jsonb_build_object('kind',k,'count',n,'target',target_user,'object_keys',keys);
 INSERT INTO maintenance_receipts(tenant_id,request_id,result) VALUES(t,rid,result);
 INSERT INTO admin_audit(tenant_id,actor_id,action,target,reason,metadata) VALUES(t,current_setting('app.user_id')::uuid,'housekeeping_'||k,coalesce(target_user::text,'household'),left(why,300),jsonb_build_object('request_id',rid,'count',n));
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION appsec.admin_metrics(),appsec.housekeeping(text,uuid,boolean,integer,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION appsec.admin_metrics(),appsec.housekeeping(text,uuid,boolean,integer,text,text) TO sandhata_app;

CREATE OR REPLACE FUNCTION appsec.delete_tracker(target uuid,why text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE t uuid; owner_id uuid;
BEGIN
 IF NOT appsec.is_admin() THEN RAISE EXCEPTION 'admin_required'; END IF;
 IF length(trim(why))<5 THEN RAISE EXCEPTION 'reason_required'; END IF;
 t:=current_setting('app.tenant_id')::uuid;
 SELECT owner_user_id INTO owner_id FROM applications WHERE id=target AND tenant_id=t FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'tracker_unavailable'; END IF;
 DELETE FROM status_events WHERE tenant_id=t AND application_id=target;
 DELETE FROM applications WHERE tenant_id=t AND id=target;
 INSERT INTO admin_audit(tenant_id,actor_id,action,target,reason) VALUES(t,current_setting('app.user_id')::uuid,'delete_tracker',target::text,left(why,300));
END $$;
REVOKE ALL ON FUNCTION appsec.delete_tracker(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION appsec.delete_tracker(uuid,text) TO sandhata_app;
