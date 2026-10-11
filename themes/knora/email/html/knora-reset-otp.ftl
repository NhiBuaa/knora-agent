<!doctype html>
<html lang="en">
<body class="knora-email" style="margin:0;padding:0;background:#EFFCFA;color:#1F3B36;font-family:Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#EFFCFA;padding:32px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border:1px solid #D9E2DE;border-radius:12px;overflow:hidden;">
                    <tr>
                        <td style="height:6px;background:#33A15B;font-size:0;line-height:0;">&nbsp;</td>
                    </tr>
                    <tr>
                        <td style="padding:28px 32px 12px;">
                            <p style="margin:0;color:#784131;font-family:Georgia,serif;font-size:22px;font-weight:bold;line-height:28px;">&#10087; Knora</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:8px 32px 32px;">
                            <h1 style="margin:0 0 14px;color:#784131;font-family:Georgia,serif;font-size:28px;line-height:36px;">${msg("knoraResetOtpHeading")}</h1>
                            <p style="margin:0 0 24px;color:#546B63;font-size:16px;line-height:24px;">${msg("knoraResetOtpInstruction")}</p>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#E6F5EB;border:1px solid #33A15B;border-radius:10px;">
                                <tr>
                                    <td align="center" style="padding:20px 12px;color:#1F3B36;font-family:Consolas,Menlo,monospace;font-size:32px;font-weight:bold;letter-spacing:8px;line-height:40px;">${code}</td>
                                </tr>
                            </table>
                            <p style="margin:20px 0 8px;color:#1F3B36;font-size:14px;line-height:22px;">${msg("knoraResetOtpExpiry", expirationMinutes)}</p>
                            <p style="margin:0;color:#546B63;font-size:14px;line-height:22px;">${msg("knoraResetOtpIgnore")}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:16px 32px;border-top:1px solid #D9E2DE;color:#546B63;font-size:12px;line-height:18px;">Knora · Evidence-first knowledge</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
