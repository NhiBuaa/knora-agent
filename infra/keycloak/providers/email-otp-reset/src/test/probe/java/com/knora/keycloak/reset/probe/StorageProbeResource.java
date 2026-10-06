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
