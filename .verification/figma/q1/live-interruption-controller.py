import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.conversation_store import PostgresConversationStore
from knora.adapters.postgres.tables import WorkspaceTable

root = Path.cwd()
evidence = root / '.verification/figma/q1/evidence/live-interruption-2026-10-10'
manifest = json.loads((evidence / 'admission.json').read_text(encoding='utf-8'))
for key in ('workspaceId', 'turnId'):
    UUID(manifest[key])
age = (datetime.now(timezone.utc) - datetime.fromisoformat(manifest['admittedAt'].replace('Z', '+00:00'))).total_seconds()
assert 0 <= age <= 90, 'fresh browser admission required'
assert manifest['workspaceName'].startswith('q1-interruption-')
container = json.loads(subprocess.check_output(['docker', 'inspect', 'knora-figma-e2e-figma-postgres-1'], text=True))[0]
assert container['Config']['Labels']['com.docker.compose.project'] == 'knora-figma-e2e'
assert container['Config']['Labels']['com.docker.compose.service'] == 'figma-postgres'
assert container['State']['Running'] is True
assert container['NetworkSettings']['Ports']['5432/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '5543'}]
env = dict(item.split('=', 1) for item in container['Config']['Env'] if '=' in item)
assert env['POSTGRES_DB'] == 'knora'
engine = create_engine(URL.create('postgresql+psycopg', username=env['POSTGRES_USER'], password=env['POSTGRES_PASSWORD'], host='127.0.0.1', port=5543, database=env['POSTGRES_DB']))
factory = sessionmaker(bind=engine, expire_on_commit=False)
store = PostgresConversationStore(factory)
with factory() as session:
    workspace = session.scalar(select(WorkspaceTable).where(WorkspaceTable.id == manifest['workspaceId']))
    assert workspace and workspace.name == manifest['workspaceName']
conversation_id = manifest['conversationPath'].split('/')[-1]
UUID(conversation_id)
turn = store.get_turn(manifest['workspaceId'], conversation_id, manifest['turnId'])
assert turn and turn.status == 'queued' and turn.question == manifest['question']
claim = store.claim_next_turn('q1-live-lease-expiry-controller', workspace_id=manifest['workspaceId'])
assert claim and claim.turn.id == manifest['turnId']
print('Fresh owned Turn claimed; waiting for actual PostgreSQL lease expiry.', flush=True)
deadline = time.monotonic() + 80
while time.monotonic() < deadline:
    observations = [item for item in store.expired_turns(limit=1000) if item.turn_id == manifest['turnId'] and item.workspace_id == manifest['workspaceId']]
    if observations:
        assert len(observations) == 1
        assert store.apply_expired_turn_recovery(observations[0], None)
        break
    time.sleep(1)
else:
    raise AssertionError('real lease did not expire within bound')
result = store.get_turn(manifest['workspaceId'], conversation_id, manifest['turnId'])
assert result.status == 'interrupted' and result.error_code == 'EXECUTION_OUTCOME_UNKNOWN' and result.result is None
(evidence / 'controller.json').write_text(json.dumps({'workspaceId': manifest['workspaceId'], 'turnId': result.id, 'status': result.status, 'errorCode': result.error_code, 'realLeaseExpiry': True, 'forcedSqlStatus': False, 'recoverySeam': 'apply_expired_turn_recovery'}, indent=2) + '\n', encoding='utf-8')
print('Actual lease-expiry recovery committed interrupted Turn; no direct status override.', flush=True)
