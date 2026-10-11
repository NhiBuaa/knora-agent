package com.knora.keycloak.reset;

import org.keycloak.Config;
import org.keycloak.events.Details;
import org.keycloak.events.Event;
import org.keycloak.events.EventListenerProvider;
import org.keycloak.events.EventListenerProviderFactory;
import org.keycloak.events.EventType;
import org.keycloak.events.admin.AdminEvent;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;

/** Supplies presentation data from a successful native password event, never from client input. */
public final class PasswordUpdatedNoticeFactory implements EventListenerProviderFactory {
    @Override public String getId() { return "knora-password-updated-notice"; }

    // Installed with the theme's provider jar; other realm themes are ignored below.
    @Override public boolean isGlobal() { return true; }

    @Override public EventListenerProvider create(KeycloakSession session) {
        return new EventListenerProvider() {
            @Override public void onEvent(Event event) {
                if (event == null || event.getError() != null) return;
                boolean passwordUpdated = event.getType() == EventType.UPDATE_PASSWORD
                        || (event.getType() == EventType.UPDATE_CREDENTIAL && event.getDetails() != null
                        && "password".equals(event.getDetails().get(Details.CREDENTIAL_TYPE)));
                if (!passwordUpdated) return;
                var realm = session.getContext().getRealm();
                if (realm == null || !"knora".equals(realm.getLoginTheme())
                        || !realm.getId().equals(event.getRealmId())) return;

                // Keycloak 26.3.3 dispatches success synchronously before rendering info.ftl.
                // The default forms provider is request-scoped. No auth/session state is changed.
                session.getProvider(LoginFormsProvider.class).setAttribute("knoraPasswordUpdated", true);
            }

            @Override public void onEvent(AdminEvent event, boolean includeRepresentation) { }
            @Override public void close() { }
        };
    }

    @Override public void init(Config.Scope config) { }
    @Override public void postInit(KeycloakSessionFactory factory) { }
    @Override public void close() { }
}
