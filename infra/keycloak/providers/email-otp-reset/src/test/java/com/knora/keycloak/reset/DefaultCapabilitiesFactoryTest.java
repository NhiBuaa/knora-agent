package com.knora.keycloak.reset;

import static com.knora.keycloak.reset.EmailOtpResetFlowIT.fake;
import static com.knora.keycloak.reset.EmailOtpResetFlowIT.unsupported;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import jakarta.ws.rs.core.MultivaluedHashMap;

import org.junit.jupiter.api.Test;
import org.keycloak.events.Event;
import org.keycloak.events.EventType;
import org.keycloak.models.KeycloakContext;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.models.KeycloakTransactionManager;
import org.keycloak.models.RealmModel;
import org.keycloak.models.RealmProvider;
import org.keycloak.models.UserModel;
import org.keycloak.models.UserProvider;
import org.keycloak.models.utils.PostMigrationEvent;
import org.keycloak.provider.ProviderEvent;
import org.keycloak.provider.ProviderEventListener;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

class DefaultCapabilitiesFactoryTest {
    @Test
    void startupRepairsPublicDemoRealmAndPreservesOtherListeners() {
        Set<String> listeners = new HashSet<>(Set.of("jboss-logging", "custom-listener"));
        List<String> writes = new ArrayList<>();
        RealmModel realm = demoRealm("Knora Public Demo", listeners, writes);

        assertTrue(DefaultCapabilitiesFactory.reconcilePublicDemoRealm(realm));
        assertEquals(
                Set.of("jboss-logging", "custom-listener", "knora-default-capabilities"),
                listeners);
        assertTrue(DefaultCapabilitiesFactory.reconcilePublicDemoRealm(realm));
        assertEquals(3, listeners.size());
        assertEquals(List.of("setEventsListeners"), writes);
    }

    @Test
    void startupLeavesOtherDeploymentsAndMissingRealmsUntouched() {
        Set<String> listeners = new HashSet<>(Set.of("custom-listener"));
        assertFalse(DefaultCapabilitiesFactory.reconcilePublicDemoRealm(null));
        assertFalse(
                DefaultCapabilitiesFactory.reconcilePublicDemoRealm(
                        demoRealm("Knora Dev", listeners, new ArrayList<>())));
        assertEquals(Set.of("custom-listener"), listeners);
    }

    @Test
    void migrationCallbackReconcilesThroughTransactionalSession() {
        Set<String> listeners = new HashSet<>(Set.of("jboss-logging"));
        List<String> writes = new ArrayList<>();
        RealmModel realm = demoRealm("Knora Public Demo", listeners, writes);
        List<String> lifecycle = new ArrayList<>();
        Map<String, Object> attributes = new HashMap<>();
        RealmProvider realms =
                fake(
                        RealmProvider.class,
                        (method, args) -> {
                            if ("getRealmByName".equals(method)) {
                                assertEquals("knora-dev", args[0]);
                                return realm;
                            }
                            return unsupported(method);
                        });
        KeycloakTransactionManager transaction =
                fake(
                        KeycloakTransactionManager.class,
                        (method, args) -> {
                            if ("begin".equals(method)) {
                                lifecycle.add("begin");
                                return null;
                            }
                            return unsupported(method);
                        });
        KeycloakSession session =
                fake(
                        KeycloakSession.class,
                        (method, args) ->
                                switch (method) {
                                    case "getAttribute" -> attributes.get(args[0]);
                                    case "setAttribute" ->
                                            attributes.put((String) args[0], args[1]);
                                    case "getTransactionManager" -> transaction;
                                    case "realms" -> realms;
                                    case "close" -> {
                                        lifecycle.add("close");
                                        yield null;
                                    }
                                    default -> unsupported(method);
                                });
        List<ProviderEventListener> callbacks = new ArrayList<>();
        KeycloakSessionFactory factory =
                fake(
                        KeycloakSessionFactory.class,
                        (method, args) ->
                                switch (method) {
                                    case "register" -> {
                                        callbacks.add((ProviderEventListener) args[0]);
                                        yield null;
                                    }
                                    case "create" -> session;
                                    default -> unsupported(method);
                                });
        new DefaultCapabilitiesFactory().postInit(factory);
        assertEquals(1, callbacks.size());
        callbacks.getFirst().onEvent(new ProviderEvent() {});
        assertTrue(lifecycle.isEmpty());
        callbacks.getFirst().onEvent(new PostMigrationEvent(factory));
        assertEquals(List.of("begin", "close"), lifecycle);
        assertTrue(listeners.contains("knora-default-capabilities"));
        assertEquals(List.of("setEventsListeners"), writes);
    }

    private static RealmModel demoRealm(
            String displayName, Set<String> listeners, List<String> writes) {
        return fake(
                RealmModel.class,
                (method, args) ->
                        switch (method) {
                            case "getName" -> "knora-dev";
                            case "getDisplayName" -> displayName;
                            case "getLoginTheme" -> "knora";
                            case "getEventsListenersStream" -> listeners.stream();
                            case "setEventsListeners" -> {
                                writes.add(method);
                                listeners.clear();
                                listeners.addAll((Set<String>) args[0]);
                                yield null;
                            }
                            default -> unsupported(method);
                        });
    }

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
        UserModel user =
                fake(
                        UserModel.class,
                        (method, args) -> {
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
    void successfulKnoraLoginDoesNotRestoreMissingOrRevokedCapabilities() {
        Map<String, List<String>> attributes = new HashMap<>();
        UserModel user =
                fake(
                        UserModel.class,
                        (method, args) -> {
                            if ("getAttributes".equals(method)) return attributes;
                            if ("setAttribute".equals(method)) {
                                attributes.put((String) args[0], (List<String>) args[1]);
                                return null;
                            }
                            return unsupported(method);
                        });

        new DefaultCapabilitiesFactory()
                .create(session(user, "knora", "realm"))
                .onEvent(event(EventType.LOGIN, null));

        assertTrue(attributes.isEmpty());
    }

    @Test
    void doesNotProvisionErrorsOtherThemesOrOtherEventKinds() {
        for (Event event :
                List.of(
                        event(EventType.REGISTER, "rejected"),
                        event(EventType.UPDATE_PROFILE, null))) {
            Map<String, Object> calls = new HashMap<>();
            UserModel user =
                    fake(
                            UserModel.class,
                            (method, args) -> {
                                calls.put(method, args);
                                return null;
                            });
            new DefaultCapabilitiesFactory().create(session(user, "knora", "realm")).onEvent(event);
            assertTrue(calls.isEmpty());
        }
        UserModel user =
                fake(
                        UserModel.class,
                        (method, args) -> {
                            throw new AssertionError("unexpected call: " + method);
                        });
        new DefaultCapabilitiesFactory()
                .create(session(user, "keycloak", "realm"))
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
        RealmModel realm =
                fake(
                        RealmModel.class,
                        (method, args) ->
                                switch (method) {
                                    case "getId" -> realmId;
                                    case "getLoginTheme" -> theme;
                                    default -> unsupported(method);
                                });
        KeycloakContext context =
                fake(
                        KeycloakContext.class,
                        (method, args) -> "getRealm".equals(method) ? realm : unsupported(method));
        UserProvider users =
                fake(
                        UserProvider.class,
                        (method, args) ->
                                "getUserById".equals(method) ? user : unsupported(method));
        return fake(
                KeycloakSession.class,
                (method, args) ->
                        switch (method) {
                            case "getContext" -> context;
                            case "users" -> users;
                            default -> unsupported(method);
                        });
    }
}
