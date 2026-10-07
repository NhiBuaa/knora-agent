<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        ${msg("knoraOtpTitle")}
    <#elseif section = "form">
        <aside class="knora-brand-panel" aria-label="Knora">
            <div class="knora-brand"><img src="${url.resourcesPath}/images/ad252.svg" width="18" height="18" alt="" /><span>Knora</span></div>
            <div class="knora-brand-copy">
                <p class="knora-eyebrow">${msg("knoraEvidenceFirst")}</p>
                <h2><span>${msg("knoraGroundedAnswers")}</span><span>${msg("knoraVerifiedEvidence")}</span></h2>
                <p class="knora-brand-description">${msg("knoraEvidenceDescription")}</p>
                <div class="knora-evidence-cues"><span>${msg("knoraSources")}</span><span>${msg("knoraPageRanges")}</span><span>${msg("knoraProvenance")}</span></div>
            </div>
            <p class="knora-brand-footnote">${msg("knoraSecureReturn")}</p>
        </aside>
        <div class="knora-auth">
            <p class="knora-auth-description">${msg("knoraOtpDescription", maskedEmail!"")}</p>
            <#if otpInvalid!false>
                <div id="otp-error" class="knora-notice" role="alert"><strong>${msg("knoraOtpErrorTitle")}</strong><p>${msg("knoraOtpInvalid")}</p></div>
            </#if>
            <form class="${properties.kcFormClass!}" action="${url.loginAction}" method="post">
                <label class="knora-visually-hidden" for="code">${msg("knoraOtpLabel")}</label>
                <div class="knora-otp-entry">
                    <input id="code" name="code" type="text" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" minlength="6" maxlength="6" required autofocus aria-invalid="${(otpInvalid!false)?c}" <#if otpInvalid!false>aria-describedby="otp-error otp-expiry"<#else>aria-describedby="otp-expiry"</#if> />
                    <div class="knora-otp-cells" aria-hidden="true"><#list 1..6 as cell><span></span></#list></div>
                </div>
                <button class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!}" type="submit" name="intent" value="verify">${msg("knoraOtpVerify")}</button>
                <div class="knora-otp-utilities">
                    <button class="knora-text-button" type="submit" name="intent" value="change-email" formnovalidate>${msg("knoraOtpChangeEmail")}</button>
                    <#assign retry = retryAfterSeconds!0>
                    <button id="otp-resend" class="knora-text-button" type="submit" name="intent" value="resend" formnovalidate data-ready-label="${msg("knoraOtpResend")}"><span id="otp-resend-label"><#if retry gt 0>${msg("knoraOtpResendPending")}<#else>${msg("knoraOtpResend")}</#if></span><#if retry gt 0> <span id="otp-retry" data-seconds="${retry?c}">${(retry / 60)?floor?string("00")}:${(retry % 60)?string("00")}</span></#if></button>
                </div>
                <p id="otp-expiry" class="knora-disclaimer">${msg("knoraOtpExpires")}</p>
            </form>
        </div>
        <script>
            (() => {
                const input = document.getElementById('code');
                const cells = document.querySelectorAll('.knora-otp-cells span');
                input.closest('.knora-otp-entry').classList.add('knora-otp-enhanced');
                const paint = () => cells.forEach((cell, index) => { cell.textContent = input.value[index] || ''; });
                input.addEventListener('input', paint);
                paint();
                const countdown = document.getElementById('otp-retry');
                if (!countdown) return;
                const retry = Number(countdown.dataset.seconds);
                if (!Number.isFinite(retry) || retry <= 0) return;
                const resend = document.getElementById('otp-resend');
                const resendLabel = document.getElementById('otp-resend-label');
                <#noparse>
                const formatCountdown = (seconds) =>
                    `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
                </#noparse>
                resend.disabled = true;
                const end = Date.now() + retry * 1000;
                const timer = setInterval(() => {
                    const remaining = Math.max(0, Math.ceil((end - Date.now()) / 1000));
                    countdown.textContent = formatCountdown(remaining);
                    if (remaining === 0) {
                        resend.disabled = false;
                        resendLabel.textContent = resend.dataset.readyLabel;
                        countdown.remove();
                        clearInterval(timer);
                    }
                }, 250);
            })();
        </script>
    </#if>
</@layout.registrationLayout>
