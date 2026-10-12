package com.knora.keycloak.reset;

import org.keycloak.Config;
import org.keycloak.events.Event;
import org.keycloak.events.EventListenerProvider;
import org.keycloak.events.EventListenerProviderFactory;
import org.keycloak.events.EventType;
import org.keycloak.events.admin.AdminEvent;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;

import java.util.List;

/**
 * Assigns the least-privilege application baseline to accounts created through Knora registration.
 */
public final class DefaultCapabilitiesFactory implements EventListenerProviderFactory {
    public static final List<String> DEFAULT_CAPABILITIES =
            List.of("documents:read", "documents:write", "questions:ask");
    private static final String CAPABILITIES_ATTRIBUTE = "capabilities";

    @Override
    public String getId() {
        return "knora-default-capabilities";
    }

    @Override
    public EventListenerProvider create(KeycloakSession session) {
        return new EventListenerProvider() {
            @Override
            public void onEvent(Event event) {
                if (event == null
                        || event.getError() != null
                        || event.getType() != EventType.REGISTER) {
                    return;
                }
                RealmModel realm = session.getContext().getRealm();
                if (realm == null
                        || !"knora".equals(realm.getLoginTheme())
                        || !realm.getId().equals(event.getRealmId())
                        || event.getUserId() == null) {
                    return;
                }
                UserModel user = session.users().getUserById(realm, event.getUserId());
                if (user != null) {
                    // Registration input is never trusted for authorization. Overwrite this claim
                    // with the fixed baseline, while leaving workspace ownership to the API.
                    user.setAttribute(CAPABILITIES_ATTRIBUTE, DEFAULT_CAPABILITIES);
                }
            }

            @Override
            public void onEvent(AdminEvent event, boolean includeRepresentation) {
                // Administrative user creation is intentionally outside the registration default.
            }

            @Override
            public void close() {}
        };
    }

    @Override
    public void init(Config.Scope config) {}

    @Override
    public void postInit(KeycloakSessionFactory factory) {}

    @Override
    public void close() {}
}
