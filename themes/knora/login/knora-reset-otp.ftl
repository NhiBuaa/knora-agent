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
                    <div class="knora-otp-digits" role="group" aria-labelledby="code-label">
                        <span id="code-label" class="knora-visually-hidden">${msg("knoraOtpLabel")}</span>
                        <#list 0..5 as index>
                            <input class="knora-otp-digit" name="code-digit-${index}" type="text" inputmode="numeric" maxlength="1" pattern="[0-9]" autocomplete="<#if index == 0>one-time-code<#else>off</#if>" aria-label="${msg("knoraOtpDigit", index + 1)}" data-otp-index="${index}" <#if index == 0>autofocus</#if> aria-invalid="${(otpInvalid!false)?c}" />
                        </#list>
                    </div>
                </div>
                <button id="otp-verify" class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!}" type="submit" name="intent" value="verify">${msg("knoraOtpVerify")}</button>
                <div class="knora-otp-utilities">
                    <button class="knora-text-button" type="submit" name="intent" value="change-email" formnovalidate>${msg("knoraOtpChangeEmail")}</button>
                    <#assign expiry = otpExpiresInSeconds!retryAfterSeconds!0>
                    <button id="otp-resend" class="knora-text-button" type="submit" name="intent" value="resend" formnovalidate data-ready-label="${msg("knoraOtpResend")}"><span id="otp-resend-label"><#if expiry gt 0>${msg("knoraOtpResendPending")}<#else>${msg("knoraOtpResend")}</#if></span><#if expiry gt 0> <span id="otp-retry" data-seconds="${expiry?c}">${(expiry / 60)?floor?string("00")}:${(expiry % 60)?string("00")}</span></#if></button>
                </div>
            </form>
        </div>
        <script>
            (() => {
                const code = document.getElementById('code');
                const digits = Array.from(document.querySelectorAll('.knora-otp-digit'));
                const form = code.closest('form');
                const verify = document.getElementById('otp-verify');
                let submitting = false;
                let movingFocus = false;
                const syncCode = () => {
                    code.value = digits.map((digit) => digit.value).join('');
                };
                const submitWhenComplete = () => {
                    if (submitting || !verify || digits.length !== 6 || digits.some((digit) => !/^[0-9]$/.test(digit.value))) return;
                    submitting = true;
                    form.requestSubmit(verify);
                };
                const focusDigit = (index, select = false) => {
                    const digit = digits[Math.max(0, Math.min(index, digits.length - 1))];
                    movingFocus = true;
                    digit.focus();
                    movingFocus = false;
                    if (select) digit.select();
                };
                const applyDigits = (value, start = 0) => {
                    const clean = value.replace(/\D/g, '').slice(0, digits.length - start);
                    digits.slice(start).forEach((digit) => { digit.value = ''; });
                    clean.split('').forEach((character, offset) => {
                        digits[start + offset].value = character;
                    });
                    syncCode();
                    if (clean.length) focusDigit(Math.min(start + clean.length, digits.length - 1));
                    submitWhenComplete();
                };
                digits.forEach((digit, index) => {
                    digit.addEventListener('focus', () => {
                        if (!movingFocus && digit.value) digit.select();
                    });
                    let composing = false;
                    const acceptInput = (event) => {
                        const raw = event.inputType === 'insertText' && /^[0-9]$/.test(event.data || '')
                            ? event.data : digit.value;
                        if (raw.length > 1) {
                            applyDigits(raw, index);
                            return;
                        }
                        digit.value = raw.replace(/\D/g, '').slice(-1);
                        syncCode();
                        if (digit.value && index < digits.length - 1) focusDigit(index + 1);
                        submitWhenComplete();
                    };
                    digit.addEventListener('compositionstart', () => { composing = true; });
                    digit.addEventListener('compositionend', (event) => {
                        composing = false;
                        acceptInput(event);
                    });
                    digit.addEventListener('input', (event) => {
                        if (!composing && !event.isComposing) acceptInput(event);
                    });
                    digit.addEventListener('keydown', (event) => {
                        if (event.key === 'Backspace' && !digit.value && index > 0) {
                            digits[index - 1].value = '';
                            focusDigit(index - 1);
                            syncCode();
                        } else if (event.key === 'ArrowLeft' && index > 0) {
                            event.preventDefault();
                            focusDigit(index - 1, true);
                        } else if (event.key === 'ArrowRight' && index < digits.length - 1) {
                            event.preventDefault();
                            focusDigit(index + 1, true);
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
