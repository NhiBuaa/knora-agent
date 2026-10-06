package com.knora.keycloak.reset;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/** Service policy doubles do not stand in for the real relational acceptance tests. */
class OtpChallengeServiceTest {
    private final OtpChallengeStore.ChallengeScope scope =
            new OtpChallengeStore.ChallengeScope("realm", "client", "auth", "tab", "email-digest");
    private final OtpChallengeStore.ChallengeReference reference =
            new OtpChallengeStore.ChallengeReference("generated-challenge", 1);
    private final List<String> events = new ArrayList<>();
    private OtpChallengeStore.SendOutcome sendOutcome = OtpChallengeStore.SendOutcome.SENT;
    private OtpChallengeStore.VerifyOutcome verifyOutcome = OtpChallengeStore.VerifyOutcome.VERIFIED;
    private boolean deliveryThrows;
    private OtpChallengeService.Recipient recipient =
            new OtpChallengeService.Recipient("user", "known@example.test", true);
    private OtpChallengeStore.SendRequest captured;
    private OtpChallengeService.KeyedDigest keyedDigest = (boundScope, ref, account, code) -> "keyed-digest";

    private OtpChallengeService service() {
        var store = new OtpChallengeStore() {
            public SendResult reserve(SendRequest request) {
                events.add("durable-reservation");
                captured = request;
                return new SendResult(sendOutcome, request.reference(), 17);
            }
            public VerifyResult verify(ChallengeScope scope, ChallengeReference reference, String digest) {
                events.add("consume");
                assertEquals("keyed-digest", digest);
                return new VerifyResult(verifyOutcome, verifyOutcome == VerifyOutcome.VERIFIED ? "user" : null);
            }
            public boolean deliveryFailed(ChallengeScope scope, ChallengeReference reference) {
                events.add("conditional-delivery-failure");
                return true;
            }
        };
        return new OtpChallengeService(store, new OtpChallengeService.AccountLookup() {
            public OtpChallengeService.Recipient byEmail(String email) { return recipient; }
            public OtpChallengeService.Recipient byId(String id) { return recipient; }
        }, () -> "000042", keyedDigest,
                (user, code) -> {
                    assertEquals("000042", code);
                    events.add("mail");
                    if (deliveryThrows) throw new IllegalStateException("controlled delivery failure");
                }, Clock.fixed(Instant.parse("2026-10-06T00:00:00Z"), ZoneOffset.UTC),
                () -> reference.id(), "trusted-ip-digest", "known@example.test");
    }

    @Test
    void leadingZeroCodeIsDeliveredOnlyAfterDurableReservationAndDigestOnlyStored() {
        var result = service().request(scope, "known@example.test");
        assertEquals(List.of("durable-reservation", "mail"), events);
        assertEquals("keyed-digest", captured.codeDigest());
        assertEquals(reference, result.reference());
        assertFalse(result.toString().contains("000042"));
    }

    @Test
    void unavailableStoreAndCooldownNeverAuthorizeMail() {
        for (var outcome : List.of(OtpChallengeStore.SendOutcome.UNAVAILABLE,
                OtpChallengeStore.SendOutcome.COOLDOWN, OtpChallengeStore.SendOutcome.EXHAUSTED)) {
            events.clear();
            sendOutcome = outcome;
            var result = service().request(scope, "known@example.test");
            assertEquals(List.of("durable-reservation"), events);
            assertEquals("knoraOtpGenericSent", result.messageKey());
        }
    }

    @Test
    void unknownDisabledAndDeliveryFailureHaveUniformPublicMessageAndRetainReservation() {
        recipient = null;
        var unknown = service().request(scope, "unknown@example.test");
        assertNull(captured.userId());
        assertEquals(List.of("durable-reservation"), events);
        recipient = new OtpChallengeService.Recipient("user", "known@example.test", false);
        events.clear();
        var disabled = service().request(scope, "known@example.test");
        assertNull(captured.userId());
        recipient = new OtpChallengeService.Recipient("user", "known@example.test", true);
        deliveryThrows = true;
        events.clear();
        var failed = service().request(scope, "known@example.test");
        assertEquals(List.of("durable-reservation", "mail", "conditional-delivery-failure"), events);
        assertEquals(unknown.messageKey(), disabled.messageKey());
        assertEquals(unknown.messageKey(), failed.messageKey());
        assertEquals(unknown, disabled);
        assertEquals(unknown, failed);
    }

    @Test
    void verificationRechecksEnabledAccountAndCurrentEmailAfterConsume() {
        var valid = service().verify(scope, reference, "000042");
        assertEquals("user", valid.verifiedUserId());
        recipient = new OtpChallengeService.Recipient("user", "changed@example.test", true);
        assertNull(service().verify(scope, reference, "000042").verifiedUserId());
        recipient = new OtpChallengeService.Recipient("user", "known@example.test", false);
        assertNull(service().verify(scope, reference, "000042").verifiedUserId());
        verifyOutcome = OtpChallengeStore.VerifyOutcome.UNAVAILABLE;
        assertNull(service().verify(scope, reference, "000042").verifiedUserId());
    }

    @Test
    void keyedDigestBindsGenerationScopeAndCodeButAccountBudgetSurvivesEmailChange() {
        byte[] key = new byte[32];
        java.util.Arrays.fill(key, (byte) 7);
        keyedDigest = OtpChallengeService.hmacSha256(key);
        String original = keyedDigest.code(scope, reference, "user:user", "000042");
        assertNotEquals(original, keyedDigest.code(scope,
                new OtpChallengeStore.ChallengeReference(reference.id(), 2), "user:user", "000042"));
        assertNotEquals(original, keyedDigest.code(scope, reference, "user:user", "42"));
        var otherScope = new OtpChallengeStore.ChallengeScope("realm", "client", "other-auth", "tab", "changed-email");
        assertNotEquals(original, keyedDigest.code(otherScope, reference, "user:user", "000042"));
        service().request(scope, "known@example.test");
        String firstAccount = captured.accountDigest();
        recipient = new OtpChallengeService.Recipient("user", "changed@example.test", false);
        service().request(otherScope, "changed@example.test");
        assertEquals(firstAccount, captured.accountDigest());
        assertNull(captured.userId());
        assertThrows(IllegalArgumentException.class, () -> OtpChallengeService.hmacSha256(new byte[31]));
    }
}
