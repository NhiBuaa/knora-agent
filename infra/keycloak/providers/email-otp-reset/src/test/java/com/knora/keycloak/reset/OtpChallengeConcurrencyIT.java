package com.knora.keycloak.reset;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.ConcurrentLinkedQueue;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;

import static org.junit.jupiter.api.Assertions.*;

/** Real Keycloak storage characterization. Passing these tests is not OTP acceptance. */
class OtpChallengeConcurrencyIT {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3)).build();
    private static final String[] NODES = Boolean.getBoolean("proofDockerNetwork")
            ? new String[] {"http://keycloak:8080", "http://keycloak-proof:8080"}
            : new String[] {"http://127.0.0.1:8380", "http://127.0.0.1:8381"};
    private static final String PATH = "/realms/knora-dev/knora-otp-storage-proof";
    private static final String SECRET = System.getenv("KNORA_STORAGE_PROOF_SECRET");
    private static final ConcurrentLinkedQueue<String> KEYS = new ConcurrentLinkedQueue<>();

    @AfterAll
    static void removeOnlySyntheticProofKeys() throws Exception {
        if (SECRET == null) return;
        for (String key : KEYS) {
            operation(0, op("remove", key, null, 60));
            post(0, "/jpa-fixture", Map.of("challenge", key, "operation", "cleanup"));
        }
        for (String key : KEYS) post(0, "/jpa-fixture", Map.of("challenge", key, "operation", "cleanup-account"));
    }

    @BeforeAll
    static void requireRealProbe() throws Exception {
        assertNotNull(SECRET, "Real two-node proof needs the isolated probe header in environment");
        assertTrue(SECRET.length() >= 32);
        for (int node = 0; node < 2; node++) {
            JsonNode result = operation(node, op("get", key(), null, 60));
            assertEquals("org.keycloak.models.sessions.infinispan.InfinispanSingleUseObjectProvider",
                    result.path("provider").asText());
            assertTrue(result.path("transactionActive").asBoolean());
        }
    }

    @Test
    void probeRejectsMissingHeaderBeforeStorage() throws Exception {
        HttpResponse<String> result = HTTP.send(HttpRequest.newBuilder(URI.create(NODES[0] + PATH))
                .POST(HttpRequest.BodyPublishers.ofString("{}"))
                .header("Content-Type", "application/json").build(), HttpResponse.BodyHandlers.ofString());
        assertEquals(404, result.statusCode());
    }

    @Test
    void probeRejectsAnotherRealmAndNonProofKey() throws Exception {
        for (boolean otherRealm : List.of(true, false)) {
            String uri = NODES[0] + (otherRealm ? PATH.replace("knora-dev", "master") : PATH);
            String key = otherRealm ? key() : "outside-proof-namespace";
            String body = JSON.writeValueAsString(Map.of("operations", List.of(op("admit", key, null, 60)),
                    "gate", "", "rollback", false));
            HttpResponse<String> result = HTTP.send(HttpRequest.newBuilder(URI.create(uri))
                    .header("X-Knora-Storage-Proof", SECRET).header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body)).build(), HttpResponse.BodyHandlers.ofString());
            assertEquals(404, result.statusCode());
        }
    }

    @Test
    void independentJpaCommitRestoresOuterJtaAndSessionOnBothNodes() throws Exception {
        for (int node = 0; node < 2; node++) {
            String key = key();
            JsonNode runtime = post(node, "/jpa-runtime", Map.of("key", key, "rollback", true));
            assertEquals("quarkus", runtime.path("factoryId").asText());
            assertTrue(runtime.path("distinctTransaction").asBoolean());
            assertTrue(runtime.path("outerTransactionRestored").asBoolean());
            assertTrue(runtime.path("outerSessionRestored").asBoolean());
            assertTrue(runtime.path("independentCommitVisible").asBoolean());
            assertTrue(runtime.path("failureRestored").asBoolean());
            assertTrue(runtime.path("innerRollbackInvisible").asBoolean());
            JsonNode completed = post(1 - node, "/jpa-runtime-result", Map.of("key", key, "rollback", false));
            assertTrue(completed.path("survivedCallerRollback").asBoolean());
        }
    }

    @Test
    void relationalAccountBudgetDoesNotResetAcrossSessionsOrCallerRollback() throws Exception {
        String account = key();
        String challenge = key();
        JsonNode sent = store(0, "send", account, challenge, 1, "session-a", "digest-good", true);
        assertEquals("SENT", sent.path("outcome").asText());
        for (int attempt = 0; attempt < 5; attempt++) {
            assertEquals("INVALID", store(attempt % 2, "verify", account, challenge, 1,
                    "session-a", "wrong-digest", false).path("outcome").asText());
        }
        assertEquals("EXHAUSTED", store(1, "verify", account, challenge, 1,
                "session-a", "digest-good", false).path("outcome").asText());
        JsonNode newSession = store(1, "send", account, key(), 1, "session-b", "digest-good", false);
        assertNotEquals("SENT", newSession.path("outcome").asText());
    }

    @Test
    void relationalParallelConsumeAndRotationNeverReviveConsumedOrOldGeneration() throws Exception {
        String account = key();
        String challenge = key();
        assertEquals("SENT", store(0, "send", account, challenge, 1, "session-a", "digest-good", false)
                .path("outcome").asText());
        var first = CompletableFuture.supplyAsync(() -> uncheckedStore(0, "verify", account, challenge, 1, "digest-good"));
        var second = CompletableFuture.supplyAsync(() -> uncheckedStore(1, "verify", account, challenge, 1, "digest-good"));
        List<String> outcomes = List.of(first.get(10, TimeUnit.SECONDS).path("outcome").asText(),
                second.get(10, TimeUnit.SECONDS).path("outcome").asText());
        assertEquals(1, outcomes.stream().filter("VERIFIED"::equals).count());
        assertEquals(1, outcomes.stream().filter("INVALID"::equals).count());
        assertEquals("INVALID", store(0, "resend", account, challenge, 2, "session-a", "digest-next", false)
                .path("outcome").asText());
        assertEquals("INVALID", store(1, "verify", account, challenge, 1, "session-a", "digest-good", false)
                .path("outcome").asText());

        String rotatedAccount = key();
        String rotated = key();
        assertEquals("SENT", store(0, "send", rotatedAccount, rotated, 1, "session-a", "digest-old", false)
                .path("outcome").asText());
        post(0, "/jpa-fixture", Map.of("challenge", rotated, "operation", "cooldown-past"));
        assertEquals("SENT", store(1, "resend", rotatedAccount, rotated, 2, "session-a", "digest-new", false)
                .path("outcome").asText());
        assertEquals("INVALID", store(0, "verify", rotatedAccount, rotated, 1, "session-a", "digest-old", false)
                .path("outcome").asText());
        assertEquals("VERIFIED", store(1, "verify", rotatedAccount, rotated, 2, "session-a", "digest-new", false)
                .path("outcome").asText());
    }

    private static JsonNode uncheckedStore(int node, String operation, String account, String challenge,
                                          long generation, String digest) {
        try { return store(node, operation, account, challenge, generation, "session-a", digest, false); }
        catch (Exception e) { throw new RuntimeException("Relational proof request failed", e); }
    }

    @Test
    void relationalHeldFirstRowRollbackFailsClosedThenAdmitsExactlyOnce() throws Exception {
        String account = key();
        String gate = UUID.randomUUID().toString();
        var holder = CompletableFuture.supplyAsync(() -> {
            try { return post(0, "/jpa-lock", Map.of("account", account, "gate", gate, "rollback", true)); }
            catch (Exception e) { throw new RuntimeException("Controlled lock fixture failed", e); }
        });
        try {
            awaitGate(0, gate);
            JsonNode blocked = store(1, "send", account, key(), 1, "session-a", "digest-good", false);
            assertEquals("UNAVAILABLE", blocked.path("outcome").asText());
            assertTrue(blocked.path("outerTransactionRestored").asBoolean());
            assertTrue(blocked.path("outerSessionRestored").asBoolean());
        } finally {
            release(0, gate);
            holder.get(10, TimeUnit.SECONDS);
        }
        String challenge = key();
        assertEquals("SENT", store(1, "send", account, challenge, 1, "session-a", "digest-good", false)
                .path("outcome").asText());
        JsonNode state = post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"));
        assertEquals(1, state.path("sends").asInt());
        assertEquals(1, state.path("ipSends").asInt());
    }

    @Test
    void relationalCooldownSendCapAndFixedWindowSurviveNewSessionAndResend() throws Exception {
        String account = key();
        String first = key();
        assertEquals("SENT", store(0, "send", account, first, 1, "session-a", "digest-good", false).path("outcome").asText());
        long anchor = post(1, "/jpa-fixture", Map.of("challenge", first, "operation", "state")).path("anchor").asLong();
        assertEquals("COOLDOWN", store(1, "resend", account, first, 2, "session-a", "digest-next", false).path("outcome").asText());
        post(0, "/jpa-fixture", Map.of("challenge", first, "operation", "cooldown-past"));
        String second = key();
        assertEquals("SENT", store(1, "send", account, second, 1, "session-b", "digest-good", false).path("outcome").asText());
        assertEquals("INVALID", store(0, "verify", account, first, 1, "session-a", "wrong-digest", false).path("outcome").asText());
        post(0, "/jpa-fixture", Map.of("challenge", second, "operation", "cooldown-past"));
        assertEquals("SENT", store(0, "resend", account, second, 2, "session-b", "digest-next", false).path("outcome").asText());
        JsonNode state = post(1, "/jpa-fixture", Map.of("challenge", second, "operation", "state"));
        assertEquals(anchor, state.path("anchor").asLong());
        assertEquals(1, state.path("attempts").asInt());
        assertEquals(3, state.path("sends").asInt());
        assertEquals("EXHAUSTED", store(1, "send", account, key(), 1, "session-c", "digest-good", false).path("outcome").asText());
        post(0, "/jpa-fixture", Map.of("challenge", second, "operation", "window-past"));
        post(0, "/jpa-fixture", Map.of("challenge", second, "operation", "cooldown-past"));
        String fresh = key();
        assertEquals("SENT", store(1, "send", account, fresh, 1, "session-c", "digest-good", false).path("outcome").asText());
        JsonNode nextWindow = post(0, "/jpa-fixture", Map.of("challenge", fresh, "operation", "state"));
        assertTrue(nextWindow.path("anchor").asLong() > anchor);
        assertEquals(0, nextWindow.path("attempts").asInt());
        assertEquals(1, nextWindow.path("sends").asInt());
    }

    @Test
    void relationalExpiryAndLateDeliveryFailureNeverReviveAConsumedOrRotatedGeneration() throws Exception {
        String account = key();
        String challenge = key();
        assertEquals("SENT", store(0, "send", account, challenge, 1, "session-a", "digest-good", false).path("outcome").asText());
        post(1, "/jpa-fixture", Map.of("challenge", challenge, "operation", "expired"));
        assertEquals("EXPIRED", store(1, "verify", account, challenge, 1, "session-a", "digest-good", false).path("outcome").asText());
        post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "cooldown-past"));
        assertEquals("SENT", store(1, "resend", account, challenge, 2, "session-a", "digest-next", false).path("outcome").asText());
        assertEquals("UNCHANGED", store(0, "delivery-failed", account, challenge, 1, "session-a", "digest-good", false).path("outcome").asText());
        assertEquals("VERIFIED", store(0, "verify", account, challenge, 2, "session-a", "digest-next", false).path("outcome").asText());
        assertEquals("UNCHANGED", store(1, "delivery-failed", account, challenge, 2, "session-a", "digest-next", false).path("outcome").asText());
        assertEquals("INVALID", store(1, "verify", account, challenge, 2, "session-a", "digest-next", false).path("outcome").asText());
    }

    @Test
    void relationalConcurrentFirstRequestsShareTwentySendIpBudget() throws Exception {
        String ip = key();
        List<CompletableFuture<JsonNode>> submissions = new java.util.ArrayList<>();
        for (int request = 0; request < 24; request++) {
            int node = request % 2;
            String account = key();
            String challenge = key();
            submissions.add(CompletableFuture.supplyAsync(() -> {
                try { return post(node, "/jpa-store", Map.of("operation", "send", "account", account,
                        "challenge", challenge, "generation", 1, "authSession", "session-a",
                        "digest", "digest-good", "rollback", false, "ip", ip)); }
                catch (Exception e) { throw new RuntimeException("Concurrent IP admission failed", e); }
            }));
        }
        List<String> outcomes = new java.util.ArrayList<>();
        for (var submission : submissions) outcomes.add(submission.get(15, TimeUnit.SECONDS).path("outcome").asText());
        assertEquals(20, outcomes.stream().filter("SENT"::equals).count());
        assertEquals(4, outcomes.stream().filter("EXHAUSTED"::equals).count());
    }

    @Test
    void relationalScopeBindsRealmClientTabAndCurrentEmail() throws Exception {
        String account = key();
        String challenge = key();
        assertEquals("SENT", store(0, "send", account, challenge, 1, "session-a", "digest-good", false).path("outcome").asText());
        for (String variant : List.of("realm", "client", "tab", "email")) {
            JsonNode result = post(1, "/jpa-store", Map.of("operation", "verify", "account", account,
                    "challenge", challenge, "generation", 1, "authSession", "session-a",
                    "digest", "digest-good", "rollback", false, "scopeVariant", variant));
            assertEquals("INVALID", result.path("outcome").asText());
        }
        assertEquals("INVALID", store(1, "verify", account, challenge, 1, "session-b", "digest-good", false).path("outcome").asText());
        assertEquals("VERIFIED", store(0, "verify", account, challenge, 1, "session-a", "digest-good", false).path("outcome").asText());
    }

    @Test
    void relationalVerifierReReadsGenerationAfterHeldLockAndWindowExpiry() throws Exception {
        String account = key();
        String challenge = key();
        assertEquals("SENT", store(0, "send", account, challenge, 1, "session-a", "digest-good", false).path("outcome").asText());
        String gate = UUID.randomUUID().toString();
        var holder = CompletableFuture.supplyAsync(() -> {
            try { return post(0, "/jpa-lock", Map.of("account", account, "gate", gate, "rollback", false,
                    "challenge", challenge, "mutation", "rotate-after-expiry")); }
            catch (Exception e) { throw new RuntimeException("Controlled generation fixture failed", e); }
        });
        CompletableFuture<JsonNode> verifier = null;
        try {
            awaitGate(0, gate);
            verifier = CompletableFuture.supplyAsync(() -> uncheckedStore(1, "verify", account, challenge, 1, "digest-good"));
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(1);
            boolean blocked = false;
            while (!blocked && System.nanoTime() < deadline) {
                blocked = post(0, "/jpa-blockers", Map.of("gate", gate)).path("blocked").asInt() > 0;
                if (!blocked) Thread.sleep(25);
            }
            assertTrue(blocked, "Competing store transition must really be blocked on the held database row");
        } finally { release(0, gate); holder.get(10, TimeUnit.SECONDS); }
        assertEquals("INVALID", verifier.get(10, TimeUnit.SECONDS).path("outcome").asText());
        assertEquals("VERIFIED", store(1, "verify", account, challenge, 2, "session-a", "digest-next", false).path("outcome").asText());
    }

    @Test
    @EnabledIfSystemProperty(named = "requireNodeCrashProof", matches = "true")
    void relationalNodeCrashRollsBackUncommittedAdmission() throws Exception {
        String account = key();
        String gate = "00000000-0000-4000-8000-000000000002";
        var holder = CompletableFuture.supplyAsync(() -> {
            try { return post(1, "/jpa-lock", Map.of("account", account, "gate", gate, "rollback", false)); }
            catch (Exception e) { throw new RuntimeException("Expected controlled node transport failure", e); }
        });
        awaitGate(1, gate);
        assertThrows(java.util.concurrent.ExecutionException.class, () -> holder.get(20, TimeUnit.SECONDS));
        String challenge = key();
        JsonNode survivor = store(0, "send", account, challenge, 1, "session-a", "digest-good", false);
        assertEquals("SENT", survivor.path("outcome").asText());
        assertTrue(survivor.path("outerTransactionRestored").asBoolean());
        assertTrue(survivor.path("outerSessionRestored").asBoolean());
        JsonNode state = post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"));
        assertEquals(1, state.path("sends").asInt());
        assertEquals(1, state.path("ipSends").asInt());
    }

    @Test
    void relationalHeldProductionResendAndVerifyHonorBothLockOrderings() throws Exception {
        for (boolean resendFirst : List.of(false, true)) {
            String account = key();
            String challenge = key();
            assertEquals("SENT", store(0, "send", account, challenge, 1, "session-a", "digest-good", false)
                    .path("outcome").asText());
            post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "cooldown-past"));
            String gate = UUID.randomUUID().toString();
            var holder = CompletableFuture.supplyAsync(() -> {
                try { return post(0, "/jpa-lock", Map.of("account", account, "gate", gate, "rollback", true,
                        "lockMode", resendFirst ? "account-only" : "ip-account")); }
                catch (Exception e) { throw new RuntimeException("Controlled operation ordering failed", e); }
            });
            CompletableFuture<JsonNode> first = null;
            CompletableFuture<JsonNode> second = null;
            try {
                awaitGate(0, gate);
                first = CompletableFuture.supplyAsync(() -> uncheckedStore(1,
                        resendFirst ? "resend" : "verify", account, challenge,
                        resendFirst ? 2 : 1, resendFirst ? "digest-next" : "digest-good"));
                awaitBlocked(0, gate, 1);
                second = CompletableFuture.supplyAsync(() -> uncheckedStore(1,
                        resendFirst ? "verify" : "resend", account, challenge,
                        resendFirst ? 1 : 2, resendFirst ? "digest-good" : "digest-next"));
                awaitBlocked(0, gate, 2);
            } finally { release(0, gate); holder.get(10, TimeUnit.SECONDS); }
            assertEquals(resendFirst ? "SENT" : "VERIFIED", first.get(10, TimeUnit.SECONDS).path("outcome").asText());
            assertEquals("INVALID", second.get(10, TimeUnit.SECONDS).path("outcome").asText());
            if (resendFirst) assertEquals("VERIFIED", store(0, "verify", account, challenge, 2,
                    "session-a", "digest-next", false).path("outcome").asText());
            JsonNode state = post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"));
            assertEquals(resendFirst ? 2 : 1, state.path("sends").asInt());
        }
    }

    private static void awaitBlocked(int node, String gate, int count) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(800);
        int blocked = 0;
        while (blocked < count && System.nanoTime() < deadline) {
            blocked = post(node, "/jpa-blockers", Map.of("gate", gate)).path("blocked").asInt();
            if (blocked < count) Thread.sleep(20);
        }
        assertTrue(blocked >= count, "All scheduled transitions must hold real database waits before release");
    }

    @Test
    @EnabledIfSystemProperty(named = "requireDatabaseOutageProof", matches = "true")
    void relationalDatabaseOutageReturnsUnavailableAndRecoversCoherentBudget() throws Exception {
        String account = key();
        String challenge = key();
        assertEquals("SENT", store(0, "send", account, challenge, 1, "session-a", "digest-good", false)
                .path("outcome").asText());
        String unavailableChallenge = key();
        var send = CompletableFuture.supplyAsync(() -> gatedStore("send", account, unavailableChallenge, "00000000-0000-4000-8000-000000000003"));
        var verify = CompletableFuture.supplyAsync(() -> gatedStore("verify", account, challenge, "00000000-0000-4000-8000-000000000004"));
        awaitGate(1, "00000000-0000-4000-8000-000000000003");
        awaitGate(1, "00000000-0000-4000-8000-000000000004");
        for (var future : List.of(send, verify)) {
            JsonNode result = future.get(25, TimeUnit.SECONDS);
            assertEquals("UNAVAILABLE", result.path("outcome").asText());
            assertTrue(result.path("outerTransactionRestored").asBoolean());
            assertTrue(result.path("outerSessionRestored").asBoolean());
        }
        // The host restores only the owned database while this bounded no-SQL gate is held.
        JsonNode recovered = gatedStore("proof-wait", account, challenge, "00000000-0000-4000-8000-000000000005");
        assertEquals("WAITED", recovered.path("outcome").asText());
        JsonNode state = post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"));
        assertEquals(1, state.path("sends").asInt());
        assertEquals(1, state.path("ipSends").asInt());
        assertEquals(0, state.path("attempts").asInt());
        assertEquals("VERIFIED", store(0, "verify", account, challenge, 1, "session-a", "digest-good", false)
                .path("outcome").asText());
    }

    private static JsonNode gatedStore(String operation, String account, String challenge, String gate) {
        try { return post(1, "/jpa-store", Map.of("operation", operation, "account", account,
                "challenge", challenge, "generation", 1, "authSession", "session-a",
                "digest", "digest-good", "rollback", false, "gate", gate)); }
        catch (Exception e) { throw new RuntimeException("Controlled outage probe failed", e); }
    }

    @Test
    @EnabledIfSystemProperty(named = "requireCommitReplyFault", matches = "true")
    void relationalLostConfirmedCommitReplyFailsClosedButPreservesBudget() throws Exception {
        assertTrue(Boolean.getBoolean("proofDockerNetwork"), "Fault proxy has no host port");
        String account = key();
        String challenge = key();
        commitProxy("POST", "/arm", Map.of("challenge", challenge));
        try {
            JsonNode ambiguous = store(1, "send", account, challenge, 1, "session-a", "digest-good", false);
            assertEquals("UNAVAILABLE", ambiguous.path("outcome").asText());
            assertTrue(ambiguous.path("outerTransactionRestored").asBoolean());
            assertTrue(ambiguous.path("outerSessionRestored").asBoolean());
            JsonNode fault = commitProxy("GET", "/state", null);
            assertEquals(1, fault.path("confirmedCommitRepliesDropped").asInt());
            assertFalse(fault.path("armed").asBoolean());
            JsonNode durable = post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"));
            assertEquals(1, durable.path("sends").asInt());
            assertEquals(1, durable.path("ipSends").asInt());
            assertEquals("COOLDOWN", store(0, "send", account, key(), 1, "session-b", "digest-next", false)
                    .path("outcome").asText());
            // An unavailable outcome exposes no permission to send. The orphan digest is never known to a user.
        } finally { commitProxy("DELETE", "/arm", null); }
    }

    private static JsonNode commitProxy(String method, String path, Object body) throws Exception {
        var publisher = body == null ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(body));
        HttpResponse<String> response = HTTP.send(HttpRequest.newBuilder(URI.create("http://otp-commit-proxy:8765" + path))
                .timeout(Duration.ofSeconds(3)).header("X-Knora-Storage-Proof", SECRET)
                .header("Content-Type", "application/json").method(method, publisher).build(), HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode(), "Proxy control status only; bodies not logged");
        return JSON.readTree(response.body());
    }

    @Test
    @EnabledIfSystemProperty(named = "requireCommitReplyFault", matches = "true")
    void serviceLostActivationReplyReconcilesExactOperationWithoutRepeatingMail() throws Exception {
        String account = key();
        String challenge = key();
        try {
            JsonNode result = post(1, "/jpa-service", Map.of("account", account, "challenge", challenge,
                    "mode", "lost-activation-reply"));
            assertTrue(result.path("mailAttempted").asBoolean());
            assertTrue(result.path("durableBeforeMail").asBoolean());
            assertEquals(1, result.path("activationCalls").asInt());
            assertEquals(1, result.path("reconciliationCalls").asInt());
            assertEquals("UNAVAILABLE", result.path("activationOutcome").asText());
            assertEquals("ACTIVE", result.path("reconciliationOutcome").asText());
            assertTrue(result.path("sameOperation").asBoolean());
            assertTrue(result.path("outerTransactionRestored").asBoolean());
            assertTrue(result.path("outerSessionRestored").asBoolean());
            assertTrue(result.path("internallyVerified").asBoolean());
            assertEquals(1, commitProxy("GET", "/state", null).path("confirmedCommitRepliesDropped").asInt());
            JsonNode state = post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"));
            assertEquals(1, state.path("sends").asInt());
            assertEquals(1, state.path("ipSends").asInt());
            assertEquals(1, mailboxCount(result.path("testRecipient").asText()));
        } finally { commitProxy("DELETE", "/arm", null); }
    }

    @Test
    @EnabledIfSystemProperty(named = "requireActivationCrash", matches = "true")
    void serviceCrashAfterSmtpBeforeActivationLeavesPendingAndNoBudgetRefund() throws Exception {
        String account = key();
        String challenge = key();
        String gate = "00000000-0000-4000-8000-000000000006";
        var held = CompletableFuture.supplyAsync(() -> {
            try { return post(1, "/jpa-service", Map.of("account", account, "challenge", challenge,
                    "mode", "crash-before-activation", "gate", gate)); }
            catch (Exception expectedTransportFailure) { return null; }
        });
        try {
            awaitGate(1, gate);
            JsonNode pending = post(0, "/jpa-service", Map.of("account", account, "challenge", challenge,
                    "mode", "verify-only"));
            assertFalse(pending.path("internallyVerified").asBoolean());
            assertEquals(1, mailboxCount(pending.path("testRecipient").asText()));
            assertNull(held.get(50, TimeUnit.SECONDS), "Owned proof-node restart must interrupt the held request");
            JsonNode survivor = post(0, "/jpa-service", Map.of("account", account, "challenge", challenge,
                    "mode", "verify-only"));
            assertFalse(survivor.path("internallyVerified").asBoolean());
            JsonNode state = post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"));
            assertEquals(1, state.path("sends").asInt());
            assertEquals(1, state.path("ipSends").asInt());
            assertEquals(1, mailboxCount(survivor.path("testRecipient").asText()));
        } finally {
            // Restart destroys the latch and may still be starting; durable assertions use the survivor.
            try { release(1, gate); } catch (java.io.IOException nodeRestarting) { }
        }
    }

    private static int mailboxCount(String address) throws Exception {
        HttpResponse<String> response = HTTP.send(HttpRequest.newBuilder(URI.create("http://mail:8025/api/v1/search?query="
                + java.net.URLEncoder.encode("to:" + address, java.nio.charset.StandardCharsets.UTF_8))).GET().build(),
                HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
        return JSON.readTree(response.body()).path("messages").size();
    }

    @Test
    void relationalCleanupCannotReviveHeldStaleVerifyResendOrFirstAdmission() throws Exception {
        for (String operation : List.of("verify", "resend", "send")) {
            String account = key();
            String old = key();
            assertEquals("SENT", store(0, "send", account, old, 1, "session-a", "digest-good", false)
                    .path("outcome").asText());
            post(0, "/jpa-fixture", Map.of("challenge", old, "operation", "retention-aged"));
            String gate = UUID.randomUUID().toString();
            var holder = CompletableFuture.supplyAsync(() -> {
                try { return post(0, "/jpa-lock", Map.of("account", account, "gate", gate, "rollback", true)); }
                catch (Exception e) { throw new RuntimeException("Controlled cleanup lock failed", e); }
            });
            String candidate = "send".equals(operation) ? key() : old;
            CompletableFuture<JsonNode> stale = null;
            try {
                awaitGate(0, gate);
                stale = CompletableFuture.supplyAsync(() -> uncheckedStore(1, operation, account, candidate,
                        "resend".equals(operation) ? 2 : 1, "digest-good"));
                awaitBlocked(0, gate, 1);
                assertEquals("SENT", store(0, "send", key(), key(), 1, "session-a", "digest-good", false)
                        .path("outcome").asText());
                assertFalse(post(0, "/jpa-fixture", Map.of("challenge", old, "operation", "state"))
                        .path("changed").asBoolean(true), "Production admission must clean beyond the24h grace");
            } finally { release(0, gate); holder.get(10, TimeUnit.SECONDS); }
            assertEquals("send".equals(operation) ? "SENT" : "INVALID",
                    stale.get(10, TimeUnit.SECONDS).path("outcome").asText());
            assertEquals("INVALID", store(0, "resend", account, old, 2, "session-a", "digest-good", false)
                    .path("outcome").asText());
            String fresh = "send".equals(operation) ? candidate : key();
            if (!"send".equals(operation)) assertEquals("SENT", store(0, "send", account, fresh, 1,
                    "session-a", "digest-good", false).path("outcome").asText());
            JsonNode state = post(0, "/jpa-fixture", Map.of("challenge", fresh, "operation", "state"));
            assertEquals(1, state.path("sends").asInt());
            assertEquals(1, state.path("ipSends").asInt());
            assertEquals("INVALID", store(1, "verify", account, old, 1, "session-a", "digest-good", false)
                    .path("outcome").asText());
        }
    }

    @Test
    void relationalCleanupPreservesGraceAndActiveBudgetAndBoundsBatchWork() throws Exception {
        String account = key();
        String protectedChallenge = key();
        assertEquals("SENT", store(0, "send", account, protectedChallenge, 1, "session-a", "digest-good", false)
                .path("outcome").asText());
        post(0, "/jpa-fixture", Map.of("challenge", protectedChallenge, "operation", "retention-within-grace"));
        assertEquals("SENT", store(1, "send", key(), key(), 1, "session-a", "digest-good", false).path("outcome").asText());
        JsonNode protectedState = post(0, "/jpa-fixture", Map.of("challenge", protectedChallenge, "operation", "state"));
        assertEquals(1, protectedState.path("sends").asInt());
        assertEquals("COOLDOWN", store(1, "send", account, key(), 1, "session-b", "digest-good", false).path("outcome").asText());
        List<String> aged = new java.util.ArrayList<>();
        for (int index = 0; index < 105; index++) {
            String challenge = key();
            assertEquals("SENT", store(index % 2, "send", key(), challenge, 1, "session-a", "digest-good", false)
                    .path("outcome").asText());
            aged.add(challenge);
        }
        // Age only after creating the batch so opportunistic admission cannot drain it early.
        for (String challenge : aged) post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "retention-aged"));
        assertEquals("SENT", store(1, "send", key(), key(), 1, "session-a", "digest-good", false).path("outcome").asText());
        int remaining = 0;
        for (String challenge : aged) if (post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"))
                .has("sends")) remaining++;
        assertEquals(5, remaining, "One admission cleans at most100 expired challenges");
        assertEquals(1, post(0, "/jpa-fixture", Map.of("challenge", protectedChallenge, "operation", "state"))
                .path("sends").asInt());
    }

    @Test
    void pendingReservationNeverVerifiesBeforeKnownSmtpActivation() throws Exception {
        String account = key();
        String challenge = key();
        assertEquals("SENT", post(0, "/jpa-store", Map.of("operation", "send", "account", account,
                "challenge", challenge, "generation", 1, "authSession", "session-a",
                "digest", "digest-good", "rollback", false)).path("outcome").asText());
        assertEquals("INVALID", store(1, "verify", account, challenge, 1, "session-a", "digest-good", false)
                .path("outcome").asText());
    }

    @Test
    void historicDefaultPendingCannotVerifyDespiteLegacyCompatibilityFlags() throws Exception {
        String account = key();
        String challenge = key();
        store(0, "send", account, challenge, 1, "session-a", "digest-good", false);
        post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "legacy-default"));
        assertEquals("INVALID", store(1, "verify", account, challenge, 1, "session-a", "digest-good", false)
                .path("outcome").asText());
    }

    @Test
    void rollbackOnlyAfterReservationWorkCannotAuthorizeServiceSmtp() throws Exception {
        String account = key();
        String challenge = key();
        JsonNode result = post(1, "/jpa-rollback-only", Map.of("operation", "service-send", "account", account, "challenge", challenge));
        assertEquals("UNAVAILABLE", result.path("outcome").asText());
        assertTrue(result.path("rollbackInjectedAfterWork").asBoolean());
        assertFalse(result.path("mailAttempted").asBoolean());
        assertTrue(result.path("outerTransactionRestored").asBoolean());
        assertTrue(result.path("outerSessionRestored").asBoolean());
        assertFalse(post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"))
                .path("changed").asBoolean(true));
    }

    @Test
    void activationRequiresExactGenerationOperationAndLiveUnconsumedState() throws Exception {
        String account = key();
        String challenge = key();
        rawReserve(0, "send", account, challenge, 1);
        String operation = UUID.randomUUID().toString();
        assertEquals("INVALID", activation(1, "reconcile", account, challenge, 1, "session-a", operation).path("outcome").asText());
        assertEquals("ACTIVE", activation(1, "activate", account, challenge, 1, "session-a", operation).path("outcome").asText());
        assertEquals("ACTIVE", activation(0, "activate", account, challenge, 1, "session-a", operation).path("outcome").asText());
        assertEquals("ACTIVE", activation(0, "reconcile", account, challenge, 1, "session-a", operation).path("outcome").asText());
        assertEquals("INVALID", activation(1, "activate", account, challenge, 1, "session-a", UUID.randomUUID().toString()).path("outcome").asText());
        assertEquals("VERIFIED", store(1, "verify", account, challenge, 1, "session-a", "digest-good", false).path("outcome").asText());
        assertEquals("INVALID", activation(0, "reconcile", account, challenge, 1, "session-a", operation).path("outcome").asText());

        account = key(); challenge = key();
        rawReserve(0, "send", account, challenge, 1);
        post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "cooldown-past"));
        rawReserve(1, "resend", account, challenge, 2);
        assertEquals("INVALID", activation(0, "activate", account, challenge, 1, "session-a", operation).path("outcome").asText());
        assertEquals("INVALID", store(0, "verify", account, challenge, 2, "session-a", "digest-good", false).path("outcome").asText());
        post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "expired"));
        assertEquals("INVALID", activation(1, "activate", account, challenge, 2, "session-a", operation).path("outcome").asText());
        assertEquals("INVALID", activation(1, "activate", account, key(), 1, "session-a", operation).path("outcome").asText());
    }

    @Test
    void heldLateActivationCannotActivateResentGenerationOrInvalidateIt() throws Exception {
        String account = key();
        String challenge = key();
        rawReserve(0, "send", account, challenge, 1);
        String gate = UUID.randomUUID().toString();
        String operation = UUID.randomUUID().toString();
        var late = CompletableFuture.supplyAsync(() -> {
            try { return post(1, "/jpa-store", Map.of("operation", "activate", "account", account,
                    "challenge", challenge, "generation", 1, "authSession", "session-a", "digest", "digest-good",
                    "rollback", false, "gate", gate, "activationId", operation)); }
            catch (Exception e) { throw new RuntimeException("Controlled late activation failed", e); }
        });
        try {
            awaitGate(1, gate);
            post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "cooldown-past"));
            rawReserve(0, "resend", account, challenge, 2);
        } finally { release(1, gate); }
        assertEquals("INVALID", late.get(10, TimeUnit.SECONDS).path("outcome").asText());
        assertEquals("INVALID", activation(0, "reconcile", account, challenge, 1, "session-a", operation).path("outcome").asText());
        assertEquals("INVALID", store(1, "verify", account, challenge, 2, "session-a", "digest-good", false).path("outcome").asText());
        assertEquals("ACTIVE", activation(0, "activate", account, challenge, 2, "session-a", UUID.randomUUID().toString()).path("outcome").asText());
        assertEquals("VERIFIED", store(1, "verify", account, challenge, 2, "session-a", "digest-good", false).path("outcome").asText());
        assertEquals(2, post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state")).path("sends").asInt());
    }

    private static JsonNode rawReserve(int node, String operation, String account, String challenge, long generation) throws Exception {
        JsonNode result = post(node, "/jpa-store", Map.of("operation", operation, "account", account,
                "challenge", challenge, "generation", generation, "authSession", "session-a",
                "digest", "digest-good", "rollback", false));
        assertEquals("SENT", result.path("outcome").asText());
        return result;
    }

    @Test
    void unavailableActivationAndReconciliationLeavePendingUnverifiable() throws Exception {
        String account = key();
        String challenge = key();
        rawReserve(0, "send", account, challenge, 1);
        String gate = UUID.randomUUID().toString();
        var holder = CompletableFuture.supplyAsync(() -> {
            try { return post(0, "/jpa-lock", Map.of("account", account, "gate", gate, "rollback", true)); }
            catch (Exception e) { throw new RuntimeException("Controlled activation wait failed", e); }
        });
        try {
            awaitGate(0, gate);
            String operation = UUID.randomUUID().toString();
            assertEquals("UNAVAILABLE", activation(1, "activate", account, challenge, 1, "session-a", operation).path("outcome").asText());
            assertEquals("UNAVAILABLE", activation(1, "reconcile", account, challenge, 1, "session-a", operation).path("outcome").asText());
        } finally { release(0, gate); holder.get(10, TimeUnit.SECONDS); }
        assertEquals("INVALID", store(1, "verify", account, challenge, 1, "session-a", "digest-good", false).path("outcome").asText());
        assertEquals(1, post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state")).path("sends").asInt());
    }

    @Test
    void rollbackOnlyAfterWorkCannotPublishReservationOrVerifiedResult() throws Exception {
        rollbackOnlyResult("send");
    }

    @Test
    void rollbackOnlyAfterWorkCannotPublishVerifiedResult() throws Exception {
        rollbackOnlyResult("verify");
    }

    private void rollbackOnlyResult(String operation) throws Exception {
            String account = key();
            String challenge = key();
            if ("verify".equals(operation)) assertEquals("SENT", store(0, "send", account, challenge, 1,
                    "session-a", "digest-good", false).path("outcome").asText());
            JsonNode result = post(1, "/jpa-rollback-only", Map.of("operation", operation, "account", account, "challenge", challenge));
            assertTrue(result.path("rollbackInjectedAfterWork").asBoolean());
            assertTrue(result.path("outerTransactionRestored").asBoolean());
            assertTrue(result.path("outerSessionRestored").asBoolean());
            assertEquals("UNAVAILABLE", result.path("outcome").asText());
            JsonNode durable = post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"));
            if ("send".equals(operation)) assertFalse(durable.path("changed").asBoolean(true));
            else {
                assertEquals(1, durable.path("sends").asInt());
                assertEquals(0, durable.path("attempts").asInt());
                assertEquals("VERIFIED", store(0, "verify", account, challenge, 1,
                        "session-a", "digest-good", false).path("outcome").asText());
            }
    }

    @Test
    void realServiceCommitsBeforeSmtpAndDeliveryFailureRetainsBudget() throws Exception {
        for (String mode : List.of("success", "failure", "unknown", "disabled")) {
            String account = key();
            String challenge = key();
            JsonNode result = post(0, "/jpa-service", Map.of("account", account, "challenge", challenge, "mode", mode));
            assertEquals("knoraOtpGenericSent", result.path("messageKey").asText());
            assertEquals("success".equals(mode) || "failure".equals(mode), result.path("mailAttempted").asBoolean());
            if (result.path("mailAttempted").asBoolean()) assertTrue(result.path("durableBeforeMail").asBoolean());
            JsonNode state = post(1, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"));
            assertEquals(1, state.path("sends").asInt());
            assertEquals(1, state.path("ipSends").asInt());
            assertEquals("success".equals(mode), result.path("internallyVerified").asBoolean());
            String address = result.path("testRecipient").asText();
            HttpResponse<String> mailbox = HTTP.send(HttpRequest.newBuilder(URI.create("http://mail:8025/api/v1/search?query="
                    + java.net.URLEncoder.encode("to:" + address, java.nio.charset.StandardCharsets.UTF_8))).GET().build(),
                    HttpResponse.BodyHandlers.ofString());
            assertEquals(200, mailbox.statusCode());
            assertEquals("success".equals(mode) ? 1 : 0, JSON.readTree(mailbox.body()).path("messages").size());
        }
    }

    @Test
    void realServiceLockTimeoutNeverAuthorizesSmtpOrBudgetMutation() throws Exception {
        String account = key();
        String challenge = key();
        String gate = UUID.randomUUID().toString();
        var holder = CompletableFuture.supplyAsync(() -> {
            try { return post(0, "/jpa-lock", Map.of("account", account, "gate", gate, "rollback", true)); }
            catch (Exception e) { throw new RuntimeException("Controlled service lock failed", e); }
        });
        try {
            awaitGate(0, gate);
            JsonNode render = post(1, "/jpa-service", Map.of("account", account, "challenge", challenge, "mode", "success"));
            assertEquals("knoraOtpGenericSent", render.path("messageKey").asText());
            assertFalse(render.path("mailAttempted").asBoolean());
            assertFalse(render.path("internallyVerified").asBoolean());
            assertFalse(post(0, "/jpa-fixture", Map.of("challenge", challenge, "operation", "state"))
                    .path("changed").asBoolean(true));
        } finally { release(0, gate); holder.get(10, TimeUnit.SECONDS); }
    }

    private static JsonNode store(int node, String operation, String account, String challenge, long generation,
                                  String authSession, String digest, boolean rollback) throws Exception {
        JsonNode result = post(node, "/jpa-store", Map.of("operation", operation, "account", account,
                "challenge", challenge, "generation", generation, "authSession", authSession,
                "digest", digest, "rollback", rollback));
        // Legacy store contracts exercise delivered challenges; raw POST retains PENDING for delivery tests.
        if (("send".equals(operation) || "resend".equals(operation)) && "SENT".equals(result.path("outcome").asText()))
            assertEquals("ACTIVE", activation(node, "activate", account, challenge, generation, authSession,
                    UUID.randomUUID().toString()).path("outcome").asText());
        return result;
    }

    private static JsonNode activation(int node, String operation, String account, String challenge, long generation,
            String authSession, String activationId) throws Exception {
        return post(node, "/jpa-store", Map.of("operation", operation, "account", account, "challenge", challenge,
                "generation", generation, "authSession", authSession, "digest", "digest-good", "rollback", false,
                "activationId", activationId));
    }

    @Test
    void deferredPutIsPrivateUntilCompletionAndRemovalDoesNotCancelIt() throws Exception {
        String key = key();
        seed(key, "initial");
        String gate = UUID.randomUUID().toString();
        var writer = held(0, gate, false, op("put", key, "queued", 60), op("get", key, null, 60));
        try {
            JsonNode paused = awaitGate(0, gate);
            assertEquals("queued", paused.path("results").get(1).path("value").asText());
            assertEquals("initial", value(operation(1, op("get", key, null, 60))));
            assertEquals("initial", value(operation(1, op("remove", key, null, 60))));
            assertTrue(operation(1, op("get", key, null, 60)).path("results").get(0).path("absent").asBoolean());
        } finally {
            release(0, gate);
            writer.get(10, TimeUnit.SECONDS);
        }
        assertEquals("queued", value(operation(1, op("get", key, null, 60))));
        assertEquals("queued", value(operation(1, op("remove", key, null, 60))));
    }

    @Test
    void bothCommitOrdersCanOverwriteAnotherCompletedGeneration() throws Exception {
        for (boolean firstWriterFirst : List.of(true, false)) {
            String key = key();
            String a = UUID.randomUUID().toString();
            String b = UUID.randomUUID().toString();
            var first = held(0, a, false, op("put", key, "generation-a", 60));
            var second = held(1, b, false, op("put", key, "generation-b", 60));
            try {
                awaitGate(0, a);
                awaitGate(1, b);
                if (firstWriterFirst) {
                    release(0, a); first.get(10, TimeUnit.SECONDS);
                    release(1, b); second.get(10, TimeUnit.SECONDS);
                } else {
                    release(1, b); second.get(10, TimeUnit.SECONDS);
                    release(0, a); first.get(10, TimeUnit.SECONDS);
                }
                assertEquals(firstWriterFirst ? "generation-b" : "generation-a",
                        value(operation(0, op("get", key, null, 60))));
            } finally {
                release(0, a); release(1, b);
            }
        }
    }

    @Test
    void immediateUniqueAdmissionAndConsumeAreSharedAcrossNodes() throws Exception {
        String key = key();
        assertTrue(result(operation(0, op("admit", key, null, 60))).path("accepted").asBoolean());
        assertFalse(result(operation(1, op("admit", key, null, 60))).path("accepted").asBoolean());
        assertTrue(result(operation(0, op("replace", key, "generation-1", 60))).path("accepted").asBoolean());
        var a = asyncOperation(0, op("remove", key, null, 60));
        var b = asyncOperation(1, op("remove", key, null, 60));
        List<JsonNode> replies = List.of(a.get(10, TimeUnit.SECONDS), b.get(10, TimeUnit.SECONDS));
        assertEquals(1, replies.stream().filter(r -> "generation-1".equals(value(r))).count());
        assertEquals(1, replies.stream().filter(r -> result(r).path("absent").asBoolean()).count());
    }

    @Test
    void rollbackDropsQueuedPutButDoesNotUndoImmediateAdmissionOrConsume() throws Exception {
        String pending = key();
        String reservation = key();
        String consumed = key();
        seed(consumed, "generation-1");
        request(0, List.of(op("put", pending, "queued", 60),
                op("admit", reservation, null, 60), op("remove", consumed, null, 60)), null, true);
        assertTrue(result(operation(1, op("get", pending, null, 60))).path("absent").asBoolean());
        assertFalse(result(operation(1, op("admit", reservation, null, 60))).path("accepted").asBoolean());
        assertTrue(result(operation(1, op("get", consumed, null, 60))).path("absent").asBoolean());
    }

    @Test
    void duplicateQueuedPutThrowsWithoutReplacingFirstQueuedValue() throws Exception {
        String key = key();
        JsonNode reply = request(0, List.of(op("put", key, "first", 60),
                op("put", key, "second", 60)), null, false);
        assertEquals("IllegalStateException", reply.path("results").get(1).path("error").asText());
        assertEquals("first", value(operation(1, op("get", key, null, 60))));
    }

    @Test
    void expiredReusedAnchorAcceptsStaleInitializerAndOverwritesNewWindow() throws Exception {
        assertEquals("old-window", staleAnchorSchedule());
    }

    @Test
    @EnabledIfSystemProperty(named = "requireCandidateSafety", matches = "true")
    void anchoredAccountWindowMustFenceStaleInitializer() throws Exception {
        assertEquals("new-window", staleAnchorSchedule(),
                "Rejected candidate: expired/reused anchor accepts stale initializer, resets budget/window");
    }

    private static String staleAnchorSchedule() throws Exception {
        String key = key();
        String gate = UUID.randomUUID().toString();
        var stale = held(0, gate, false, op("admit", key, null, 1),
                op("pause", key, null, 1), op("replace", key, "old-window", 60));
        try {
            assertTrue(awaitGate(0, gate).path("results").get(0).path("accepted").asBoolean());
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
            boolean admitted = false;
            while (System.nanoTime() < deadline && !admitted) {
                admitted = result(operation(1, op("admit", key, null, 60))).path("accepted").asBoolean();
                if (!admitted) Thread.sleep(100);
            }
            assertTrue(admitted, "Original reservation must actually expire before takeover");
            assertTrue(result(operation(1, op("replace", key, "new-window", 60))).path("accepted").asBoolean());
            assertEquals("new-window", value(operation(1, op("get", key, null, 60))));
        } finally {
            release(0, gate);
        }
        assertTrue(stale.get(10, TimeUnit.SECONDS).path("results").get(2).path("accepted").asBoolean());
        return value(operation(1, op("get", key, null, 60)));
    }

    private static Map<String, Object> op(String operation, String key, String value, int ttl) {
        return Map.of("operation", operation, "key", key, "value", value == null ? "" : value, "ttl", ttl);
    }

    private static String key() {
        String key = "knora-otp-proof:" + UUID.randomUUID();
        KEYS.add(key);
        return key;
    }
    private static JsonNode result(JsonNode response) { return response.path("results").get(0); }
    private static String value(JsonNode response) { return result(response).path("value").asText(); }

    private static void seed(String key, String value) throws Exception {
        assertTrue(result(operation(0, op("admit", key, null, 60))).path("accepted").asBoolean());
        assertTrue(result(operation(0, op("replace", key, value, 60))).path("accepted").asBoolean());
    }

    private static JsonNode operation(int node, Map<String, Object> op) throws Exception {
        return request(node, List.of(op), null, false);
    }

    private static JsonNode request(int node, List<Map<String, Object>> ops, String gate, boolean rollback)
            throws Exception {
        return post(node, "", Map.of("operations", ops, "gate", gate == null ? "" : gate, "rollback", rollback));
    }

    @SafeVarargs
    private static CompletableFuture<JsonNode> held(int node, String gate, boolean rollback,
                                                   Map<String, Object>... ops) {
        return CompletableFuture.supplyAsync(() -> {
            try { return request(node, List.of(ops), gate, rollback); }
            catch (Exception e) { throw new RuntimeException("Probe request failed", e); }
        });
    }

    private static CompletableFuture<JsonNode> asyncOperation(int node, Map<String, Object> op) {
        return held(node, "", false, op);
    }

    private static JsonNode awaitGate(int node, String gate) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (System.nanoTime() < deadline) {
            HttpResponse<String> response = HTTP.send(HttpRequest.newBuilder(URI.create(NODES[node] + PATH + "/gate/" + gate))
                    .header("X-Knora-Storage-Proof", SECRET).GET().build(), HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == 200) return JSON.readTree(response.body());
            assertEquals(404, response.statusCode());
            Thread.sleep(50);
        }
        fail("Real session did not reach its controlled pause");
        return null;
    }

    private static void release(int node, String gate) throws Exception {
        post(node, "/gate/" + gate, Map.of());
    }

    private static JsonNode post(int node, String suffix, Object body) throws Exception {
        HttpResponse<String> response = HTTP.send(HttpRequest.newBuilder(URI.create(NODES[node] + PATH + suffix))
                .timeout(Duration.ofSeconds(40)).header("X-Knora-Storage-Proof", SECRET)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(body))).build(),
                HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode(), "Probe HTTP status only; response bodies are not logged");
        return JSON.readTree(response.body());
    }
}
