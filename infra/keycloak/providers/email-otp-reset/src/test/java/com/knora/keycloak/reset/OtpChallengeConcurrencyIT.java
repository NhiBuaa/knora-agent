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
        for (String key : KEYS) operation(0, op("remove", key, null, 60));
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
