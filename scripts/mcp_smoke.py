"""Verify the local MCP stdio protocol using an owner-scoped ephemeral capability."""
import sys,os,json,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from sandhata.config import ROOT,ISSUER
from sandhata.db import resolve_identity
from sandhata.identity import issue_capability
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    identity=next(p for p in json.loads((ROOT/'runtime/identities.json').read_text(encoding='utf-8')) if p['role']=='admin')
    p=resolve_identity(ISSUER,identity['id'])
    if not p: raise RuntimeError('The local administrator has no active membership')
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),SANDHATA_MCP_CAPABILITY=issue_capability(p))
    params=StdioServerParameters(command=sys.executable,args=['-m','sandhata.mcp_server'],env=env)
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as client:
            await client.initialize()
            listed=await client.list_tools();names=sorted(t.name for t in listed.tools)
            assert names==['list_my_tracker','search_my_evidence','search_my_jobs']
            jobs=await client.call_tool('search_my_jobs',{'query':'SAMPLE'})
            assert not jobs.isError
            unknown=await client.call_tool('not_an_allowed_tool',{})
            assert unknown.isError
    (ROOT/'deliverables/verification/mcp_protocol.json').write_text(json.dumps(dict(transport='local_stdio',initialization='passed',tool_allowlist=names,authorized_read='passed',unknown_tool='rejected',private_content_logged=False),indent=2),encoding='utf-8')
    print('MCP stdio initialization, owner read and unknown-tool rejection passed.')

if __name__=='__main__': asyncio.run(main())
