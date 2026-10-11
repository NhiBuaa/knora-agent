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
                    <input id="code" name="code" type="hidden" value="" required />
                    <div class="knora-otp-digits" role="group" aria-labelledby="code-label" aria-describedby="otp-expiry">
                        <span id="code-label" class="knora-visually-hidden">${msg("knoraOtpLabel")}</span>
                        <#list 0..5 as index>
                            <input class="knora-otp-digit" type="text" inputmode="numeric" maxlength="1" pattern="[0-9]" autocomplete="<#if index == 0>one-time-code<#else>off</#if>" aria-label="${msg("knoraOtpDigit", index + 1)}" data-otp-index="${index}" <#if index == 0>autofocus</#if> aria-invalid="${(otpInvalid!false)?c}" />
                        </#list>
                    </div>
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
                const code = document.getElementById('code');
                const digits = Array.from(document.querySelectorAll('.knora-otp-digit'));
                const form = code.closest('form');
                const syncCode = () => {
                    code.value = digits.map((digit) => digit.value).join('');
                };
                const focusDigit = (index) => {
                    const digit = digits[Math.max(0, Math.min(index, digits.length - 1))];
                    digit.focus();
                    digit.select();
                };
                const applyDigits = (value, start = 0) => {
                    const clean = value.replace(/\D/g, '').slice(0, digits.length - start);
                    clean.split('').forEach((character, offset) => {
                        digits[start + offset].value = character;
                    });
                    syncCode();
                    focusDigit(Math.min(start + clean.length, digits.length - 1));
                };
                digits.forEach((digit, index) => {
                    digit.addEventListener('input', () => {
                        const raw = digit.value;
                        if (raw.length > 1) {
                            digit.value = '';
                            applyDigits(raw, index);
                            return;
                        }
                        digit.value = raw.replace(/\D/g, '').slice(-1);
                        syncCode();
                        if (digit.value && index < digits.length - 1) focusDigit(index + 1);
                    });
                    digit.addEventListener('keydown', (event) => {
                        if (event.key === 'Backspace' && !digit.value && index > 0) {
                            digits[index - 1].value = '';
                            focusDigit(index - 1);
                            syncCode();
                        } else if (event.key === 'ArrowLeft' && index > 0) {
                            event.preventDefault();
                            focusDigit(index - 1);
                        } else if (event.key === 'ArrowRight' && index < digits.length - 1) {
                            event.preventDefault();
                            focusDigit(index + 1);
                        }
                    });
                    digit.addEventListener('paste', (event) => {
                        event.preventDefault();
                        applyDigits(event.clipboardData.getData('text'), index);
                    });
                });
                form.addEventListener('submit', syncCode);
                syncCode();
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
