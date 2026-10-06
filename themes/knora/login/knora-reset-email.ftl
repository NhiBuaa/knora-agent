<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        ${msg("knoraResetEmailTitle")}
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
            <p class="knora-auth-description">${msg("knoraResetEmailDescription")}</p>
            <#if emailInvalid!false>
                <p id="email-error" class="knora-notice" role="alert">${msg("knoraResetEmailInvalid")}</p>
            </#if>
            <form class="${properties.kcFormClass!}" action="${url.loginAction}" method="post">
                <div class="${properties.kcFormGroupClass!}">
                    <label class="${properties.kcLabelClass!}" for="email">${msg("email")}</label>
                    <div class="${properties.kcInputClass!}"><input id="email" name="email" type="email" autocomplete="email" maxlength="254" placeholder="${msg("knoraEmailPlaceholder")}" required autofocus aria-invalid="${(emailInvalid!false)?c}" <#if emailInvalid!false>aria-describedby="email-error"</#if> /></div>
                </div>
                <button class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!}" type="submit" name="intent" value="request">${msg("knoraResetSendCode")}</button>
                <p class="knora-secondary">${msg("knoraResetRemembered")} <a href="${url.loginUrl}">${msg("knoraResetBackToSignIn")}</a></p>
                <p class="knora-disclaimer">${msg("knoraResetPrivacy")}</p>
            </form>
        </div>
    </#if>
</@layout.registrationLayout>
