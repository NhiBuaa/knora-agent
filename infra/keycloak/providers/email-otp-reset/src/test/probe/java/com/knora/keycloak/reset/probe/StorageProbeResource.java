package com.knora.keycloak.reset.probe;

import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.NotFoundException;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.ServiceUnavailableException;
import jakarta.ws.rs.core.MediaType;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.SingleUseObjectProvider;
import org.keycloak.services.resource.RealmResourceProvider;
import org.keycloak.connections.jpa.JpaConnectionProvider;
import org.keycloak.models.utils.KeycloakModelUtils;
import org.keycloak.transaction.JtaTransactionManagerLookup;
import org.keycloak.utils.KeycloakSessionUtil;
import jakarta.persistence.EntityManager;
import java.util.concurrent.atomic.AtomicReference;
import com.knora.keycloak.reset.KeycloakOtpChallengeStore;
import com.knora.keycloak.reset.OtpChallengeStore;
import com.knora.keycloak.reset.OtpChallengeService;

/** Bounded request scheduler; every storage operation uses the real session provider. */
@jakarta.ws.rs.ext.Provider
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public final class StorageProbeResource implements RealmResourceProvider {
    // This map contains only latches and safe observation snapshots, never OTP state.
    private static final Map<String, Gate> GATES = new ConcurrentHashMap<>();
    private static final Set<String> OPERATIONS = Set.of("put", "get", "remove", "replace", "admit", "pause");
    private final KeycloakSession session;

    public StorageProbeResource(KeycloakSession session) { this.session = session; }
    @Override public Object getResource() { return this; }
    @Override public void close() { }

    public record Operation(String operation, String key, String value, int ttl) { }
    public record Request(List<Operation> operations, String gate, boolean rollback) { }
    public record Observation(String operation, boolean accepted, boolean absent, String value, String error) { }
    public record Reply(String provider, boolean transactionActive, List<Observation> results) { }
    public record RuntimeRequest(String key, boolean rollback) { }
    public record StoreRequest(String operation, String account, String challenge, long generation,
            String authSession, String digest, boolean rollback, String ip, String scopeVariant, String gate, String activationId) { }
    public record FixtureRequest(String challenge, String operation) { }
    public record LockRequest(String account, String gate, boolean rollback, String challenge, String mutation, String lockMode) { }
    public record BlockerRequest(String gate) { }
    public record ServiceRequest(String account, String challenge, String mode, String gate) { }
    public record RollbackRequest(String account, String challenge, String operation) { }
    public record RuntimeReply(String factoryId, boolean distinctTransaction,
            boolean outerTransactionRestored, boolean outerSessionRestored,
            boolean independentCommitVisible, boolean failureRestored, boolean innerRollbackInvisible) { }
    private record Gate(CountDownLatch released, Reply snapshot) { }

    private void authorize(String header) {
        String expected = System.getenv("KNORA_STORAGE_PROOF_SECRET");
        if (!"enabled".equals(System.getenv("KNORA_STORAGE_PROOF"))
                || session.getContext().getRealm() == null
                || !"knora-dev".equals(session.getContext().getRealm().getName())
                || expected == null || expected.length() < 32 || header == null
                || !MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8), header.getBytes(StandardCharsets.UTF_8))) {
            throw new NotFoundException();
        }
    }

    @POST
    @Path("jpa-runtime")
    public RuntimeReply jpaRuntime(@HeaderParam("X-Knora-Storage-Proof") String header, RuntimeRequest request)
            throws Exception {
        authorize(header);
        if (request == null || request.key() == null
                || !request.key().matches("knora-otp-proof:[a-zA-Z0-9:-]{1,100}")) throw new NotFoundException();
        var factory = session.getKeycloakSessionFactory();
        var lookup = session.getProvider(JtaTransactionManagerLookup.class);
        var transactionManager = lookup.getTransactionManager();
        var outerTransaction = transactionManager.getTransaction();
        var outerSession = KeycloakSessionUtil.getKeycloakSession();
        var outerEm = session.getProvider(JpaConnectionProvider.class).getEntityManager();
        long outerId = ((Number) outerEm.createNativeQuery("select txid_current()").getSingleResult()).longValue();
        String id = request.key();
        AtomicReference<Long> innerId = new AtomicReference<>();
        KeycloakModelUtils.suspendJtaTransaction(factory, () -> {
            innerId.set(KeycloakModelUtils.runJobInTransactionWithResult(factory, session.getContext(), inner -> {
                var em = inner.getProvider(JpaConnectionProvider.class).getEntityManager();
                insertRuntimeRow(em, id);
                return ((Number) em.createNativeQuery("select txid_current()").getSingleResult()).longValue();
            }, "knora-otp-proof-independent-commit"));
        });
        boolean restoredTransaction = transactionManager.getTransaction() == outerTransaction;
        boolean restoredSession = KeycloakSessionUtil.getKeycloakSession() == outerSession;
        long count = ((Number) outerEm.createNativeQuery("select count(*) from KNORA_OTP_RECOVERY_WINDOW where ID=:id")
                .setParameter("id", id).getSingleResult()).longValue();
        boolean failureRestored;
        try {
            KeycloakModelUtils.suspendJtaTransaction(factory, () -> {
                KeycloakModelUtils.runJobInTransactionWithResult(factory, session.getContext(), inner -> {
                    insertRuntimeRow(inner.getProvider(JpaConnectionProvider.class).getEntityManager(), id + ":failed");
                    throw new IllegalStateException("controlled test rollback");
                }, "knora-otp-proof-independent-rollback");
            });
            throw new IllegalStateException("Expected controlled rollback");
        } catch (IllegalStateException controlled) {
            failureRestored = transactionManager.getTransaction() == outerTransaction
                    && KeycloakSessionUtil.getKeycloakSession() == outerSession;
        }
        long failureCount = ((Number) outerEm.createNativeQuery("select count(*) from KNORA_OTP_RECOVERY_WINDOW where ID=:id")
                .setParameter("id", id + ":failed").getSingleResult()).longValue();
        if (request.rollback()) session.getTransactionManager().setRollbackOnly();
        return new RuntimeReply(factory.getProviderFactory(JpaConnectionProvider.class).getId(),
                innerId.get() != outerId, restoredTransaction, restoredSession, count == 1,
                failureRestored, failureCount == 0);
    }

    @POST
    @Path("jpa-runtime-result")
    public Map<String, Boolean> jpaRuntimeResult(@HeaderParam("X-Knora-Storage-Proof") String header, RuntimeRequest request) {
        authorize(header);
        if (request == null || request.key() == null
                || !request.key().matches("knora-otp-proof:[a-zA-Z0-9:-]{1,100}")) throw new NotFoundException();
        var em = session.getProvider(JpaConnectionProvider.class).getEntityManager();
        long count = ((Number) em.createNativeQuery("select count(*) from KNORA_OTP_RECOVERY_WINDOW where ID=:id")
                .setParameter("id", request.key()).getSingleResult()).longValue();
        em.createNativeQuery("delete from KNORA_OTP_RECOVERY_WINDOW where ID=:id and REALM_ID=:realm and KIND='proof'")
                .setParameter("id", request.key()).setParameter("realm", session.getContext().getRealm().getId()).executeUpdate();
        return Map.of("survivedCallerRollback", count == 1);
    }

    private void insertRuntimeRow(EntityManager em, String id) {
        em.createNativeQuery("insert into KNORA_OTP_RECOVERY_WINDOW "
                + "(ID,REALM_ID,KIND,ANCHOR_MS,ATTEMPTS,SENDS,LAST_SEND_MS) values (:id,:realm,'proof',0,0,0,0)")
                .setParameter("id", id).setParameter("realm", session.getContext().getRealm().getId()).executeUpdate();
    }

    @POST
    @Path("jpa-store")
    public Map<String, Object> jpaStore(@HeaderParam("X-Knora-Storage-Proof") String header, StoreRequest request) {
        authorize(header);
        if (request == null || !proofKey(request.account()) || !proofKey(request.challenge())
                || request.generation() < 1 || request.generation() > 100
                || request.authSession() == null || !request.authSession().matches("session-[a-z]{1,20}")
                || request.digest() == null || !request.digest().matches("[a-z-]{1,64}")
                || (request.ip() != null && !proofKey(request.ip()))) throw new NotFoundException();
        var lookup = session.getProvider(JtaTransactionManagerLookup.class);
        jakarta.transaction.Transaction outerTransaction;
        try { outerTransaction = lookup.getTransactionManager().getTransaction(); }
        catch (jakarta.transaction.SystemException failed) { throw new ServiceUnavailableException(); }
        var outerSession = KeycloakSessionUtil.getKeycloakSession();
        if (request.gate() != null) {
            if (!validGate(request.gate()) || request.gate().isEmpty()) throw new NotFoundException();
            pause(request.gate(), new Reply("real-store-before-transition", session.getTransactionManager().isActive(), List.of()));
        }
        var store = new KeycloakOtpChallengeStore(session);
        if (request.scopeVariant() != null && !Set.of("realm", "client", "tab", "email").contains(request.scopeVariant()))
            throw new NotFoundException();
        String variant = request.scopeVariant() == null ? "" : request.scopeVariant();
        var scope = new OtpChallengeStore.ChallengeScope("realm".equals(variant) ? "other-realm" : session.getContext().getRealm().getId(),
                "client".equals(variant) ? "other-client" : "proof-client", request.authSession(),
                "tab".equals(variant) ? "other-tab" : "proof-tab", "email".equals(variant) ? "other-email" : "proof-email");
        var reference = new OtpChallengeStore.ChallengeReference(request.challenge(), request.generation());
        Map<String, Object> result;
        switch (request.operation()) {
            case "proof-wait" -> result = Map.of("outcome", "WAITED");
            case "send", "resend" -> {
                var previous = "resend".equals(request.operation())
                        ? new OtpChallengeStore.ChallengeReference(request.challenge(), request.generation() - 1) : null;
                var response = store.reserve(new OtpChallengeStore.SendRequest(scope, reference, previous,
                        request.account(), request.ip() == null ? request.account() : request.ip(), "proof-user", request.digest()));
                result = Map.of("outcome", response.outcome().name(), "retryAfter", response.retryAfterSeconds());
            }
            case "verify" -> result = Map.of("outcome", store.verify(scope, reference, request.digest()).outcome().name());
            case "activate", "reconcile" -> result = Map.of("outcome", "activate".equals(request.operation())
                    ? store.activate(scope, reference, request.activationId()).name()
                    : store.reconcileActivation(scope, reference, request.activationId()).name());
            case "delivery-failed" -> result = Map.of("outcome", store.deliveryFailed(scope, reference) ? "INVALIDATED" : "UNCHANGED");
            default -> throw new NotFoundException();
        }
        result = new java.util.HashMap<>(result);
        try { result.put("outerTransactionRestored", lookup.getTransactionManager().getTransaction() == outerTransaction); }
        catch (jakarta.transaction.SystemException failed) { throw new ServiceUnavailableException(); }
        result.put("outerSessionRestored", KeycloakSessionUtil.getKeycloakSession() == outerSession);
        if (request.rollback()) session.getTransactionManager().setRollbackOnly();
        return result;
    }

    @POST
    @Path("jpa-rollback-only")
    public Map<String, Object> jpaRollbackOnly(@HeaderParam("X-Knora-Storage-Proof") String header, RollbackRequest request) throws Exception {
        authorize(header);
        if (request == null || !proofKey(request.account()) || !proofKey(request.challenge())
                || !Set.of("send", "verify", "service-send").contains(request.operation())) throw new NotFoundException();
        var tm = session.getProvider(JtaTransactionManagerLookup.class).getTransactionManager();
        var outer = tm.getTransaction();
        var outerSession = KeycloakSessionUtil.getKeycloakSession();
        boolean[] injected = {false};
        var realFactory = session.getKeycloakSessionFactory();
        var factory = delegate(org.keycloak.models.KeycloakSessionFactory.class, realFactory, (target, method, args) -> {
            Object value = invoke(target, method, args);
            if (!"create".equals(method.getName()) || !(value instanceof KeycloakSession inner)) return value;
            return delegate(KeycloakSession.class, inner, (innerTarget, innerMethod, innerArgs) -> {
                if ("close".equals(innerMethod.getName()) && !injected[0] && inner.getTransactionManager().isActive()) {
                    var em = inner.getProvider(JpaConnectionProvider.class).getEntityManager();
                    var matches = em.createNativeQuery("select CONSUMED from KNORA_OTP_CHALLENGE where ID=:id")
                            .setParameter("id", request.challenge()).getResultList();
                    if (!matches.isEmpty() && (!"verify".equals(request.operation()) || Boolean.TRUE.equals(matches.get(0)))) {
                        // Callback work has returned; exact real independent transaction is still open.
                        inner.getTransactionManager().setRollbackOnly();
                        injected[0] = true;
                    }
                }
                return invoke(innerTarget, innerMethod, innerArgs);
            });
        });
        var caller = delegate(KeycloakSession.class, session, (target, method, args) ->
                "getKeycloakSessionFactory".equals(method.getName()) ? factory : invoke(target, method, args));
        var scope = new OtpChallengeStore.ChallengeScope(session.getContext().getRealm().getId(),
                "proof-client", "session-a", "proof-tab", "proof-email");
        var ref = new OtpChallengeStore.ChallengeReference(request.challenge(), 1);
        var store = new KeycloakOtpChallengeStore(caller);
        if ("service-send".equals(request.operation())) {
            boolean[] attempted = {false};
            String[] reserved = {"NONE"};
            var observedStore = delegate(OtpChallengeStore.class, store, (target, method, args) -> {
                Object value = invoke(target, method, args);
                if ("reserve".equals(method.getName())) reserved[0] = ((OtpChallengeStore.SendResult) value).outcome().name();
                return value;
            });
            var user = new OtpChallengeService.Recipient("proof-user", "rollback@example.test", true);
            var accounts = new OtpChallengeService.AccountLookup() {
                public OtpChallengeService.Recipient byEmail(String email) { return user; }
                public OtpChallengeService.Recipient byId(String id) { return user; }
            };
            var testDigest = new OtpChallengeService.KeyedDigest() {
                public String code(OtpChallengeStore.ChallengeScope bound, OtpChallengeStore.ChallengeReference reference,
                        String identity, String code) { return "digest-good"; }
                public String account(String realm, String identity) { return request.account(); }
            };
            var service = new OtpChallengeService(observedStore, accounts, () -> "000042",
                    testDigest, (recipient, code) -> attempted[0] = true,
                    java.time.Clock.systemUTC(), request::challenge, request.account(), user.email());
            service.request(scope, user.email());
            return Map.of("outcome", reserved[0], "mailAttempted", attempted[0], "rollbackInjectedAfterWork", injected[0],
                    "outerTransactionRestored", tm.getTransaction() == outer,
                    "outerSessionRestored", KeycloakSessionUtil.getKeycloakSession() == outerSession);
        }
        String outcome = "send".equals(request.operation())
                ? store.reserve(new OtpChallengeStore.SendRequest(scope, ref, null, request.account(), request.account(),
                        "proof-user", "digest-good")).outcome().name()
                : store.verify(scope, ref, "digest-good").outcome().name();
        return Map.of("outcome", outcome, "rollbackInjectedAfterWork", injected[0],
                "outerTransactionRestored", tm.getTransaction() == outer,
                "outerSessionRestored", KeycloakSessionUtil.getKeycloakSession() == outerSession);
    }

    private static Object invoke(Object target, java.lang.reflect.Method method, Object[] args) throws Throwable {
        try { return method.invoke(target, args); }
        catch (java.lang.reflect.InvocationTargetException failure) { throw failure.getCause(); }
    }

    @SuppressWarnings("unchecked")
    private static <T> T delegate(Class<T> type, T target, java.lang.reflect.InvocationHandler handler) {
        return (T) java.lang.reflect.Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type},
                (proxy, method, args) -> handler.invoke(target, method, args));
    }

    @POST
    @Path("jpa-service")
    public Map<String, Object> jpaService(@HeaderParam("X-Knora-Storage-Proof") String header, ServiceRequest request) {
        authorize(header);
        if (request == null || !proofKey(request.account()) || !proofKey(request.challenge())
                || !Set.of("success", "failure", "unknown", "disabled", "verify-only", "lost-activation-reply",
                        "crash-before-activation").contains(request.mode())) throw new NotFoundException();
        if ("crash-before-activation".equals(request.mode())
                && !"00000000-0000-4000-8000-000000000006".equals(request.gate())) throw new NotFoundException();
        var tm = session.getProvider(JtaTransactionManagerLookup.class).getTransactionManager();
        jakarta.transaction.Transaction outer;
        try { outer = tm.getTransaction(); }
        catch (jakarta.transaction.SystemException failed) { throw new ServiceUnavailableException(); }
        var outerSession = KeycloakSessionUtil.getKeycloakSession();
        String address = request.account().replace(":", "-") + "@example.test";
        var recipient = new OtpChallengeService.Recipient(request.account(), address, !"disabled".equals(request.mode()));
        var lookup = new OtpChallengeService.AccountLookup() {
            public OtpChallengeService.Recipient byEmail(String email) { return "unknown".equals(request.mode()) ? null : recipient; }
            public OtpChallengeService.Recipient byId(String id) { return "unknown".equals(request.mode()) ? null : recipient; }
        };
        byte[] proofKey = java.util.Base64.getDecoder().decode(System.getenv("KNORA_STORAGE_PROOF_SECRET"));
        var digest = OtpChallengeService.hmacSha256(proofKey);
        java.util.Arrays.fill(proofKey, (byte) 0);
        String realm = session.getContext().getRealm().getId();
        var scope = new OtpChallengeStore.ChallengeScope(realm, "proof-client", "session-a", "proof-tab", digest.email(realm, address));
        boolean[] mailState = new boolean[2];
        var sender = (OtpChallengeService.MailSender) (user, code) -> {
            mailState[0] = true;
            Number budget = (Number) session.getProvider(JpaConnectionProvider.class).getEntityManager()
                    .createNativeQuery("select windows.SENDS from KNORA_OTP_CHALLENGE challenge join "
                            + "KNORA_OTP_RECOVERY_WINDOW windows on windows.ID=challenge.ACCOUNT_ID where challenge.ID=:id")
                    .setParameter("id", request.challenge()).getSingleResult();
            mailState[1] = budget.intValue() == 1;
            if (!mailState[1]) throw new IllegalStateException("Budget must be durable before SMTP");
            var config = new java.util.HashMap<>(session.getContext().getRealm().getSmtpConfig());
            if ("failure".equals(request.mode())) config.put("port", "1");
            try {
                session.getProvider(org.keycloak.email.EmailSenderProvider.class).send(config, user.email(),
                        "Isolated storage proof", "Isolated test recovery code: " + code,
                        "<p>Isolated test recovery code: " + code + "</p>");
            } catch (org.keycloak.email.EmailException failed) { throw new IllegalStateException("Controlled SMTP failure"); }
            if ("crash-before-activation".equals(request.mode()))
                pause(request.gate(), new Reply("known-smtp-success-before-activation",
                        session.getTransactionManager().isActive(), List.of()));
        };
        int[] activationCalls = {0, 0};
        String[] activationState = {"NONE", "NONE", null};
        boolean[] sameOperation = {false};
        OtpChallengeStore realStore = new KeycloakOtpChallengeStore(session);
        var observedStore = delegate(OtpChallengeStore.class, realStore, (target, method, args) -> {
            if ("activate".equals(method.getName())) {
                activationCalls[0]++;
                activationState[2] = (String) args[2];
                if ("lost-activation-reply".equals(request.mode())) armActivationFault(header, activationState[2]);
                Object value = invoke(target, method, args);
                activationState[0] = value.toString();
                return value;
            }
            if ("reconcileActivation".equals(method.getName())) {
                activationCalls[1]++;
                sameOperation[0] = java.util.Objects.equals(activationState[2], args[2]);
                Object value = invoke(target, method, args);
                activationState[1] = value.toString();
                return value;
            }
            return invoke(target, method, args);
        });
        var service = new OtpChallengeService(observedStore, lookup, () -> "000042", digest,
                sender, java.time.Clock.systemUTC(), request::challenge, request.account(), address);
        var render = "verify-only".equals(request.mode()) ? null : service.request(scope, address);
        boolean verified = service.verify(scope, new OtpChallengeStore.ChallengeReference(request.challenge(), 1), "000042")
                .verifiedUserId() != null;
        var reply = new java.util.HashMap<String, Object>();
        reply.put("messageKey", render == null ? "verify-only" : render.messageKey());
        reply.put("mailAttempted", mailState[0]);
        reply.put("durableBeforeMail", mailState[1]);
        reply.put("internallyVerified", verified);
        reply.put("testRecipient", address);
        reply.put("activationCalls", activationCalls[0]);
        reply.put("reconciliationCalls", activationCalls[1]);
        reply.put("activationOutcome", activationState[0]);
        reply.put("reconciliationOutcome", activationState[1]);
        reply.put("sameOperation", sameOperation[0]);
        try { reply.put("outerTransactionRestored", tm.getTransaction() == outer); }
        catch (jakarta.transaction.SystemException failed) { throw new ServiceUnavailableException(); }
        reply.put("outerSessionRestored", KeycloakSessionUtil.getKeycloakSession() == outerSession);
        return reply;
    }

    private static void armActivationFault(String header, String operation) throws Exception {
        // Exact generated operation UUID only; SQL/data and control secret are never logged.
        String body = "{\"activationId\":\"" + java.util.UUID.fromString(operation) + "\"}";
        var response = java.net.http.HttpClient.newBuilder().connectTimeout(java.time.Duration.ofSeconds(2)).build()
                .send(java.net.http.HttpRequest.newBuilder(java.net.URI.create("http://otp-commit-proxy:8765/arm"))
                        .timeout(java.time.Duration.ofSeconds(3)).header("X-Knora-Storage-Proof", header)
                        .header("Content-Type", "application/json")
                        .POST(java.net.http.HttpRequest.BodyPublishers.ofString(body)).build(),
                        java.net.http.HttpResponse.BodyHandlers.discarding());
        if (response.statusCode() != 200) throw new IllegalStateException("Synthetic fault arm rejected");
    }

    @POST
    @Path("jpa-lock")
    public Map<String, Boolean> jpaLock(@HeaderParam("X-Knora-Storage-Proof") String header, LockRequest request) {
        authorize(header);
        if (request == null || !proofKey(request.account()) || !validGate(request.gate()) || request.gate().isEmpty())
            throw new NotFoundException();
        if (request.mutation() != null && (!"rotate-after-expiry".equals(request.mutation()) || !proofKey(request.challenge())))
            throw new NotFoundException();
        if (request.lockMode() != null && !Set.of("ip-account", "account-only").contains(request.lockMode()))
            throw new NotFoundException();
        var em = session.getProvider(JpaConnectionProvider.class).getEntityManager();
        String realm = session.getContext().getRealm().getId();
        for (String kind : "account-only".equals(request.lockMode()) ? List.of("account") : List.of("ip", "account")) {
            String id = proofWindowId(realm, kind, request.account());
            em.createNativeQuery("insert into KNORA_OTP_RECOVERY_WINDOW "
                    + "(ID,REALM_ID,KIND,ANCHOR_MS,ATTEMPTS,SENDS,LAST_SEND_MS) values (:id,:realm,:kind,0,0,0,0) on conflict (ID) do nothing")
                    .setParameter("id", id).setParameter("realm", realm).setParameter("kind", kind).executeUpdate();
            em.createNativeQuery("select ID from KNORA_OTP_RECOVERY_WINDOW where ID=:id for update")
                    .setParameter("id", id).getSingleResult();
        }
        Number backendPid = (Number) em.createNativeQuery("select pg_backend_pid()").getSingleResult();
        pause(request.gate(), new Reply("real-jpa-row-lock", session.getTransactionManager().isActive(),
                List.of(new Observation("jpa-lock", true, false, backendPid.toString(), ""))));
        if (request.mutation() != null) {
            String accountId = proofWindowId(realm, "account", request.account());
            em.createNativeQuery("update KNORA_OTP_CHALLENGE set GENERATION=GENERATION+1,CODE_DIGEST='digest-next',"
                    + "EXPIRES_MS=floor(extract(epoch from clock_timestamp())*1000)::bigint+300000 where ID=:id and REALM_ID=:realm and ACCOUNT_ID=:account")
                    .setParameter("id", request.challenge()).setParameter("realm", realm).setParameter("account", accountId).executeUpdate();
            em.createNativeQuery("update KNORA_OTP_RECOVERY_WINDOW set ANCHOR_MS=floor(extract(epoch from clock_timestamp())*1000)::bigint-900000 where ID=:id")
                    .setParameter("id", accountId).executeUpdate();
        }
        if (request.rollback()) session.getTransactionManager().setRollbackOnly();
        return Map.of("released", true);
    }

    @POST
    @Path("jpa-blockers")
    public Map<String, Object> jpaBlockers(@HeaderParam("X-Knora-Storage-Proof") String header, BlockerRequest request) {
        authorize(header);
        if (request == null || !validGate(request.gate())) throw new NotFoundException();
        Gate gate = GATES.get(request.gate());
        if (gate == null || !"real-jpa-row-lock".equals(gate.snapshot().provider())) throw new NotFoundException();
        int backendPid = Integer.parseInt(gate.snapshot().results().get(0).value());
        Number blocked = (Number) session.getProvider(JpaConnectionProvider.class).getEntityManager()
                  .createNativeQuery("with recursive waiters(pid) as (select cast(:pid as integer) union "
                          + "select activity.pid from pg_stat_activity activity join waiters "
                          + "on waiters.pid=any(pg_blocking_pids(activity.pid))) "
                          + "select count(*)-1 from waiters")
                .setParameter("pid", backendPid).getSingleResult();
        return Map.of("blocked", blocked);
    }

    private static String proofWindowId(String realm, String kind, String account) {
        // Test-only fixture derives the private row address to hold its real database lock.
        try {
            return kind + ":" + java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest((realm + "\u0000" + kind + "\u0000" + account).getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }

    @POST
    @Path("jpa-fixture")
    public Map<String, Object> jpaFixture(@HeaderParam("X-Knora-Storage-Proof") String header, FixtureRequest request) {
        authorize(header);
        if (request == null || !proofKey(request.challenge())) throw new NotFoundException();
        var em = session.getProvider(JpaConnectionProvider.class).getEntityManager();
        String realm = session.getContext().getRealm().getId();
        if ("cleanup-account".equals(request.operation())) {
            em.createNativeQuery("delete from KNORA_OTP_RECOVERY_WINDOW where REALM_ID=:realm and ID in (:account,:ip) "
                    + "and not exists (select 1 from KNORA_OTP_CHALLENGE where ACCOUNT_ID=KNORA_OTP_RECOVERY_WINDOW.ID or IP_ID=KNORA_OTP_RECOVERY_WINDOW.ID)")
                    .setParameter("realm", realm).setParameter("account", proofWindowId(realm, "account", request.challenge()))
                    .setParameter("ip", proofWindowId(realm, "ip", request.challenge())).executeUpdate();
            return Map.of("changed", true);
        }
        List<?> found = em.createNativeQuery("select ACCOUNT_ID,IP_ID from KNORA_OTP_CHALLENGE where ID=:id and REALM_ID=:realm")
                .setParameter("id", request.challenge()).setParameter("realm", realm).getResultList();
        if (found.isEmpty()) return Map.of("changed", false);
        Object[] ids = (Object[]) found.get(0);
        String account = (String) ids[0];
        switch (request.operation()) {
            case "legacy-default" -> em.createNativeQuery("update KNORA_OTP_CHALLENGE set DELIVERY_STATE=DEFAULT,ACTIVATION_OP=null,"
                    + "CONSUMED=false,DELIVERY_FAILED=false where ID=:id").setParameter("id", request.challenge()).executeUpdate();
            case "retention-aged" -> {
                em.createNativeQuery("update KNORA_OTP_CHALLENGE set EXPIRES_MS="
                        + "floor(extract(epoch from clock_timestamp())*1000)::bigint-86401000 where ID=:id")
                        .setParameter("id", request.challenge()).executeUpdate();
                em.createNativeQuery("update KNORA_OTP_RECOVERY_WINDOW set "
                        + "ANCHOR_MS=floor(extract(epoch from clock_timestamp())*1000)::bigint-87301000,"
                        + "LAST_SEND_MS=floor(extract(epoch from clock_timestamp())*1000)::bigint-86401000 "
                        + "where ID in (:account,:ip)")
                        .setParameter("account", account).setParameter("ip", ids[1]).executeUpdate();
            }
            case "retention-within-grace" -> em.createNativeQuery("update KNORA_OTP_CHALLENGE set EXPIRES_MS="
                    + "floor(extract(epoch from clock_timestamp())*1000)::bigint-82800000 where ID=:id")
                    .setParameter("id", request.challenge()).executeUpdate();
            case "state" -> {
                Object[] state = (Object[]) em.createNativeQuery("select ANCHOR_MS,ATTEMPTS,SENDS from KNORA_OTP_RECOVERY_WINDOW where ID=:id")
                        .setParameter("id", account).getSingleResult();
                Number ipSends = (Number) em.createNativeQuery("select SENDS from KNORA_OTP_RECOVERY_WINDOW where ID=:id")
                        .setParameter("id", ids[1]).getSingleResult();
                return Map.of("anchor", state[0], "attempts", state[1], "sends", state[2], "ipSends", ipSends);
            }
            case "cooldown-past" -> em.createNativeQuery("update KNORA_OTP_RECOVERY_WINDOW set LAST_SEND_MS=LAST_SEND_MS-31000 where ID=:id")
                    .setParameter("id", account).executeUpdate();
            case "expired" -> em.createNativeQuery("update KNORA_OTP_CHALLENGE set EXPIRES_MS=floor(extract(epoch from clock_timestamp())*1000)::bigint where ID=:id")
                    .setParameter("id", request.challenge()).executeUpdate();
            case "window-past" -> em.createNativeQuery("update KNORA_OTP_RECOVERY_WINDOW set ANCHOR_MS=floor(extract(epoch from clock_timestamp())*1000)::bigint-900000 where ID in (:account,:ip)")
                    .setParameter("account", account).setParameter("ip", ids[1]).executeUpdate();
            case "cleanup" -> {
                em.createNativeQuery("delete from KNORA_OTP_CHALLENGE where ID=:id and REALM_ID=:realm")
                        .setParameter("id", request.challenge()).setParameter("realm", realm).executeUpdate();
                em.createNativeQuery("delete from KNORA_OTP_RECOVERY_WINDOW where ID in (:account,:ip) "
                        + "and not exists (select 1 from KNORA_OTP_CHALLENGE where ACCOUNT_ID=KNORA_OTP_RECOVERY_WINDOW.ID or IP_ID=KNORA_OTP_RECOVERY_WINDOW.ID)")
                        .setParameter("account", account).setParameter("ip", ids[1]).executeUpdate();
            }
            default -> throw new NotFoundException();
        }
        return Map.of("changed", true);
    }

    private static boolean proofKey(String value) {
        return value != null && value.matches("knora-otp-proof:[a-zA-Z0-9:-]{1,100}");
    }

    @POST
    public Reply operate(@HeaderParam("X-Knora-Storage-Proof") String header, Request request) {
        authorize(header);
        if (request == null || request.operations() == null || request.operations().isEmpty()
                || request.operations().size() > 8 || !validGate(request.gate())) throw new NotFoundException();
        for (Operation op : request.operations()) {
            if (op == null || op.operation() == null || !OPERATIONS.contains(op.operation()) || op.key() == null
                    || !op.key().matches("knora-otp-proof:[a-zA-Z0-9:-]{1,100}")
                    || op.value() == null || !op.value().matches("[a-zA-Z0-9-]{0,64}")
                    || op.ttl() < 1 || op.ttl() > 120) throw new NotFoundException();
        }
        SingleUseObjectProvider store = session.singleUseObjects();
        List<Observation> results = new ArrayList<>();
        boolean paused = false;
        for (Operation op : request.operations()) {
            if ("pause".equals(op.operation())) {
                if (paused || request.gate().isEmpty()) throw new NotFoundException();
                pause(request.gate(), reply(store, results));
                paused = true;
                results.add(new Observation("pause", true, false, "", ""));
                continue;
            }
            String key = "knora-otp-proof:" + session.getContext().getRealm().getId() + ":" + op.key();
            try {
                results.add(switch (op.operation()) {
                    case "put" -> {
                        store.put(key, op.ttl(), Map.of("value", op.value()));
                        yield new Observation("put", true, false, "", "");
                    }
                    case "admit" -> new Observation("admit", store.putIfAbsent(key, op.ttl()), false, "", "");
                    case "replace" -> new Observation("replace", store.replace(key, Map.of("value", op.value())), false, "", "");
                    case "get", "remove" -> {
                        Map<String, String> notes = "get".equals(op.operation()) ? store.get(key) : store.remove(key);
                        yield new Observation(op.operation(), notes != null, notes == null,
                                notes == null ? "" : notes.getOrDefault("value", ""), "");
                    }
                    default -> throw new NotFoundException();
                });
            } catch (IllegalStateException duplicate) {
                results.add(new Observation(op.operation(), false, false, "", "IllegalStateException"));
            }
        }
        if (!paused && !request.gate().isEmpty()) pause(request.gate(), reply(store, results));
        if (request.rollback()) session.getTransactionManager().setRollbackOnly();
        return reply(store, results);
    }

    private Reply reply(SingleUseObjectProvider store, List<Observation> results) {
        return new Reply(store.getClass().getName(), session.getTransactionManager().isActive(), List.copyOf(results));
    }

    private static boolean validGate(String gate) {
        return gate != null && (gate.isEmpty() || gate.matches("[a-f0-9-]{36}"));
    }

    private void pause(String id, Reply snapshot) {
        Gate gate = new Gate(new CountDownLatch(1), snapshot);
        synchronized (GATES) {
            if (GATES.size() >= 16 || GATES.putIfAbsent(id, gate) != null) throw new ServiceUnavailableException();
        }
        try {
            if (!gate.released().await(30, TimeUnit.SECONDS)) {
                session.getTransactionManager().setRollbackOnly();
                throw new ServiceUnavailableException();
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            session.getTransactionManager().setRollbackOnly();
            throw new ServiceUnavailableException();
        } finally {
            GATES.remove(id, gate);
        }
    }

    @GET
    @Path("gate/{id}")
    public Reply observe(@HeaderParam("X-Knora-Storage-Proof") String header, @PathParam("id") String id) {
        authorize(header);
        Gate gate = GATES.get(id);
        if (gate == null) throw new NotFoundException();
        return gate.snapshot();
    }

    @POST
    @Path("gate/{id}")
    public Map<String, Boolean> release(@HeaderParam("X-Knora-Storage-Proof") String header, @PathParam("id") String id) {
        authorize(header);
        Gate gate = GATES.get(id);
        if (gate != null) gate.released().countDown();
        return Map.of("released", gate != null);
    }
}
