package com.knora.keycloak.reset;

import org.keycloak.models.ClientSessionContext;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.ProtocolMapperModel;
import org.keycloak.models.UserSessionModel;
import org.keycloak.protocol.oidc.mappers.AbstractOIDCProtocolMapper;
import org.keycloak.protocol.oidc.mappers.OIDCIDTokenMapper;
import org.keycloak.provider.ProviderConfigProperty;
import org.keycloak.representations.IDToken;

import java.util.List;

public final class KnoraSessionPolicyMapper extends AbstractOIDCProtocolMapper
        implements OIDCIDTokenMapper {

    public static final String PROVIDER_ID = "knora-session-policy";

    @Override
    public String getId() {
        return PROVIDER_ID;
    }

    @Override
    public String getDisplayType() {
        return "Knora session policy";
    }

    @Override
    public String getDisplayCategory() {
        return TOKEN_MAPPER_CATEGORY;
    }

    @Override
    public String getHelpText() {
        return "Signed browser session mode and SSO start";
    }

    @Override
    public List<ProviderConfigProperty> getConfigProperties() {
        return List.of();
    }

    @Override
    public IDToken transformIDToken(
            IDToken token,
            ProtocolMapperModel model,
            KeycloakSession session,
            UserSessionModel userSession,
            ClientSessionContext clientSession) {
        if (userSession == null || userSession.isOffline() || userSession.getStarted() <= 0) {
            return token;
        }
        token.getOtherClaims().put("knora_remember_me", userSession.isRememberMe());
        token.getOtherClaims().put("knora_session_started_at", userSession.getStarted());
        return token;
    }
}
