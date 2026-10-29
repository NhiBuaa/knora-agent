package com.knora.keycloak.reset;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;
import org.keycloak.models.ProtocolMapperModel;
import org.keycloak.models.UserSessionModel;
import org.keycloak.protocol.ProtocolMapper;
import org.keycloak.protocol.oidc.mappers.AbstractOIDCProtocolMapper;
import org.keycloak.representations.IDToken;

import java.lang.reflect.Proxy;
import java.util.List;
import java.util.ServiceLoader;

class KnoraSessionPolicyMapperTest {

    private UserSessionModel mockSession(boolean offline, boolean rememberMe, int started) {
        return (UserSessionModel)
                Proxy.newProxyInstance(
                        UserSessionModel.class.getClassLoader(),
                        new Class<?>[] {UserSessionModel.class},
                        (proxy, method, args) ->
                                switch (method.getName()) {
                                    case "isOffline" -> offline;
                                    case "isRememberMe" -> rememberMe;
                                    case "getStarted" -> started;
                                    default ->
                                            throw new UnsupportedOperationException(
                                                    method.getName());
                                });
    }

    @Test
    void setsRememberMeTrueAndStartedAt() {
        var online = mockSession(false, true, 1_700_000_000);
        var token =
                new KnoraSessionPolicyMapper()
                        .transformIDToken(
                                new IDToken(), new ProtocolMapperModel(), null, online, null);
        assertEquals(true, token.getOtherClaims().get("knora_remember_me"));
        assertEquals(1_700_000_000, token.getOtherClaims().get("knora_session_started_at"));
    }

    @Test
    void setsRememberMeFalseAndStartedAt() {
        var online = mockSession(false, false, 1_700_000_123);
        var token =
                new KnoraSessionPolicyMapper()
                        .transformIDToken(
                                new IDToken(), new ProtocolMapperModel(), null, online, null);
        assertEquals(false, token.getOtherClaims().get("knora_remember_me"));
        assertEquals(1_700_000_123, token.getOtherClaims().get("knora_session_started_at"));
    }

    @Test
    void nullSessionDoesNotEmitClaims() {
        var token =
                new KnoraSessionPolicyMapper()
                        .transformIDToken(
                                new IDToken(), new ProtocolMapperModel(), null, null, null);
        assertNull(token.getOtherClaims().get("knora_remember_me"));
        assertNull(token.getOtherClaims().get("knora_session_started_at"));
    }

    @Test
    void offlineSessionDoesNotEmitClaims() {
        var offline = mockSession(true, true, 1_700_000_000);
        var token =
                new KnoraSessionPolicyMapper()
                        .transformIDToken(
                                new IDToken(), new ProtocolMapperModel(), null, offline, null);
        assertNull(token.getOtherClaims().get("knora_remember_me"));
        assertNull(token.getOtherClaims().get("knora_session_started_at"));
    }

    @Test
    void zeroOrNegativeStartedDoesNotEmitClaims() {
        for (int started : List.of(0, -1, -100)) {
            var session = mockSession(false, true, started);
            var token =
                    new KnoraSessionPolicyMapper()
                            .transformIDToken(
                                    new IDToken(), new ProtocolMapperModel(), null, session, null);
            assertNull(token.getOtherClaims().get("knora_remember_me"));
            assertNull(token.getOtherClaims().get("knora_session_started_at"));
        }
    }

    @Test
    void metadataAndConfigurationProperties() {
        var mapper = new KnoraSessionPolicyMapper();
        assertEquals("knora-session-policy", mapper.getId());
        assertEquals("Knora session policy", mapper.getDisplayType());
        assertEquals(AbstractOIDCProtocolMapper.TOKEN_MAPPER_CATEGORY, mapper.getDisplayCategory());
        assertNotNull(mapper.getHelpText());
        assertFalse(mapper.getHelpText().isBlank());
        assertTrue(mapper.getConfigProperties().isEmpty());
    }

    @Test
    void loadedThroughServiceLoaderExactlyOnce() {
        var providers =
                ServiceLoader.load(ProtocolMapper.class).stream()
                        .filter(provider -> provider.type() == KnoraSessionPolicyMapper.class)
                        .toList();
        assertEquals(1, providers.size());
        ProtocolMapper mapper = providers.get(0).get();
        assertEquals("knora-session-policy", mapper.getId());
        assertTrue(mapper instanceof KnoraSessionPolicyMapper);
    }
}
