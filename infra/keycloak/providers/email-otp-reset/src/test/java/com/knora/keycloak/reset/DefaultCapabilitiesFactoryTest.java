package com.knora.keycloak.reset;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import jakarta.ws.rs.core.MultivaluedHashMap;
import org.junit.jupiter.api.Test;
import org.keycloak.events.Event;
import org.keycloak.events.EventType;
import org.keycloak.models.KeycloakContext;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.models.UserProvider;

import static com.knora.keycloak.reset.EmailOtpResetFlowIT.fake;
import static com.knora.keycloak.reset.EmailOtpResetFlowIT.unsupported;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DefaultCapabilitiesFactoryTest {
    @Test
    void noScriptOtpFieldsStillSubmitOneSixDigitCode() {
        var parameters = new MultivaluedHashMap<String, String>();
        parameters.add("code", "");
        for (int index = 0; index < 6; index++) {
            parameters.add("code-digit-" + index, index == 4 ? "4" : index == 5 ? "2" : "0");
        }

        assertEquals("000042", EmailOtpResetAuthenticator.submittedCode(parameters));
    }

    @Test
    void listenerIsOptInThroughRealmEventsConfiguration() {
        assertEquals(false, new DefaultCapabilitiesFactory().isGlobal());
    }

    @Test
    void successfulKnoraRegistrationOverwritesClientSuppliedCapabilitiesWithBaseline() {
        List<String> assigned = new ArrayList<>();
        UserModel user = fake(UserModel.class, (method, args) -> {
            if (!"setAttribute".equals(method)) return unsupported(method);
            assertEquals("capabilities", args[0]);
            assigned.clear();
            assigned.addAll((List<String>) args[1]);
            return null;
        });
        Event event = event(EventType.REGISTER, null);

        new DefaultCapabilitiesFactory().create(session(user, "knora", "realm")).onEvent(event);

        assertEquals(DefaultCapabilitiesFactory.DEFAULT_CAPABILITIES, assigned);
    }

    @Test
    void doesNotProvisionErrorsOtherThemesOrOtherEventKinds() {
        for (Event event : List.of(
                event(EventType.REGISTER, "rejected"),
                event(EventType.UPDATE_PROFILE, null))) {
            Map<String, Object> calls = new HashMap<>();
            UserModel user = fake(UserModel.class, (method, args) -> {
                calls.put(method, args);
                return null;
            });
            new DefaultCapabilitiesFactory().create(session(user, "knora", "realm")).onEvent(event);
            assertTrue(calls.isEmpty());
        }
        UserModel user = fake(UserModel.class, (method, args) -> {
            throw new AssertionError("unexpected call: " + method);
        });
        new DefaultCapabilitiesFactory().create(session(user, "keycloak", "realm"))
                .onEvent(event(EventType.REGISTER, null));
    }

    private static Event event(EventType type, String error) {
        Event event = new Event();
        event.setType(type);
        event.setRealmId("realm");
        event.setUserId("user");
        event.setError(error);
        return event;
    }

    private static KeycloakSession session(UserModel user, String theme, String realmId) {
        RealmModel realm = fake(RealmModel.class, (method, args) -> switch (method) {
            case "getId" -> realmId;
            case "getLoginTheme" -> theme;
            default -> unsupported(method);
        });
        KeycloakContext context = fake(KeycloakContext.class, (method, args) ->
                "getRealm".equals(method) ? realm : unsupported(method));
        UserProvider users = fake(UserProvider.class, (method, args) ->
                "getUserById".equals(method) ? user : unsupported(method));
        return fake(KeycloakSession.class, (method, args) -> switch (method) {
            case "getContext" -> context;
            case "users" -> users;
            default -> unsupported(method);
        });
    }
}
