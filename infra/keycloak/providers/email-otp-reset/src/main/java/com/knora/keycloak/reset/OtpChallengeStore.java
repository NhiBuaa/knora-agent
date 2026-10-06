package com.knora.keycloak.reset;

/** Atomic recovery transitions. No persistence/session handles escape this seam. */
public interface OtpChallengeStore {
    record ChallengeScope(String realmId, String clientId, String authSessionId, String tabId, String emailDigest) { }
    record ChallengeReference(String id, long generation) { }
    enum VerifyOutcome { VERIFIED, INVALID, EXPIRED, EXHAUSTED, UNAVAILABLE }
    enum SendOutcome { SENT, COOLDOWN, EXHAUSTED, INVALID, UNAVAILABLE }
    record SendRequest(ChallengeScope scope, ChallengeReference reference, ChallengeReference previous,
                       String accountDigest, String ipDigest, String userId, String codeDigest) { }
    record SendResult(SendOutcome outcome, ChallengeReference reference, int retryAfterSeconds) { }
    record VerifyResult(VerifyOutcome outcome, String verifiedUserId) { }

    SendResult reserve(SendRequest request);
    VerifyResult verify(ChallengeScope scope, ChallengeReference reference, String submittedDigest);
    boolean deliveryFailed(ChallengeScope scope, ChallengeReference reference);
}
