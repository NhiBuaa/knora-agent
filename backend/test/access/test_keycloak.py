import base64, json, time
import pytest
from knora.access.keycloak import KeycloakAuthenticator
from knora.domain.errors import KnoraError

def token(claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return f'a.{body}.sig'

def test_valid_token_maps_principal():
    auth = KeycloakAuthenticator(issuer='https://issuer', audience='api', token_validator=lambda t: {'iss':'https://issuer','aud':'api','exp':time.time()+60,'sub':'u','workspace_id':'w','capabilities':['documents:write']})
    p = auth.authenticate('Bearer ' + token({}))
    assert (p.subject, p.workspace_id, p.capabilities) == ('u','w',('documents:write',))

@pytest.mark.parametrize('claims', [
    {'iss':'https://issuer','aud':'api','exp':time.time()-1,'sub':'u','workspace_id':'w'},
    {'iss':'https://wrong','aud':'api','exp':time.time()+1,'sub':'u','workspace_id':'w'},
    {'iss':'https://issuer','aud':'wrong','exp':time.time()+1,'sub':'u','workspace_id':'w'},
])
def test_invalid_claims_rejected(claims):
    with pytest.raises(KnoraError):
        KeycloakAuthenticator(issuer='https://issuer', audience='api', token_validator=lambda t, c=claims: c).authenticate('Bearer x.y.z')

def test_malformed_token_rejected_without_validator():
    with pytest.raises(KnoraError):
        KeycloakAuthenticator(issuer='i', audience='a').authenticate('Bearer x.y.z')
