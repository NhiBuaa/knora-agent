package com.knora.keycloak.reset;

import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.keycloak.events.Details;
import org.keycloak.events.Event;
import org.keycloak.events.EventType;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.KeycloakContext;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import static com.knora.keycloak.reset.EmailOtpResetFlowIT.fake;
import static com.knora.keycloak.reset.EmailOtpResetFlowIT.unsupported;
import static org.junit.jupiter.api.Assertions.*;

class PasswordUpdatedNoticeTest {
    @Test void onlySuccessfulPasswordEventsMarkTheCurrentKnoraRequest() {
        assertEquals(Map.of("knoraPasswordUpdated", true), emit(EventType.UPDATE_PASSWORD, null, null, "knora", "realm"));
        assertEquals(Map.of("knoraPasswordUpdated", true), emit(EventType.UPDATE_CREDENTIAL, "password", null, "knora", "realm"));
        assertTrue(emit(EventType.UPDATE_PROFILE, null, null, "knora", "realm").isEmpty());
        assertTrue(emit(EventType.UPDATE_CREDENTIAL, "otp", null, "knora", "realm").isEmpty());
        assertTrue(emit(EventType.UPDATE_CREDENTIAL, null, null, "knora", "realm").isEmpty());
        assertTrue(emit(EventType.UPDATE_PASSWORD_ERROR, "password", "rejected", "knora", "realm").isEmpty());
        assertTrue(emit(EventType.UPDATE_PASSWORD, null, "rejected", "knora", "realm").isEmpty());
        assertTrue(emit(EventType.UPDATE_PASSWORD, null, null, "keycloak", "realm").isEmpty());
        assertTrue(emit(EventType.UPDATE_PASSWORD, null, null, "knora", "other-realm").isEmpty());
    }

    private Map<String, Object> emit(EventType type, String credential, String error, String theme, String eventRealm) {
        var attributes = new HashMap<String, Object>();
        var realm = fake(RealmModel.class, (method, args) -> switch (method) {
            case "getId" -> "realm";
            case "getLoginTheme" -> theme;
            default -> unsupported(method);
        });
        var context = fake(KeycloakContext.class, (method, args) -> "getRealm".equals(method) ? realm : unsupported(method));
        var form = fake(LoginFormsProvider.class, (method, args) -> {
            if (!"setAttribute".equals(method)) return unsupported(method);
            attributes.put((String) args[0], args[1]);
            return null;
        });
        var session = fake(KeycloakSession.class, (method, args) -> switch (method) {
            case "getContext" -> context;
            case "getProvider" -> {
                assertEquals(LoginFormsProvider.class, args[0]);
                yield form;
            }
            default -> unsupported(method);
        });
        var event = new Event();
        event.setType(type);
        event.setError(error);
        event.setRealmId(eventRealm);
        if (credential != null) event.setDetails(Map.of(Details.CREDENTIAL_TYPE, credential));
        new PasswordUpdatedNoticeFactory().create(session).onEvent(event);
        return attributes;
    }
}
