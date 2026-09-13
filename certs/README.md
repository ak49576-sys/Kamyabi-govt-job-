# IBPS chain repair

The public GlobalSign RSA OV SSL CA 2018 intermediate was copied from GlobalSign's OrganizationSSL support page on 2026-09-13:

https://support.globalsign.com/ca-certificates/intermediate-certificates/organizationssl-intermediate-certificates

SHA-256 of DER certificate:
`b676ffa3179e8812093a1b5eafee876ae7a6aaf231078dad1bfb21cd2893764a`

Subject: GlobalSign RSA OV SSL CA 2018. Issuer: GlobalSign Root CA - R3. Valid until 2028-11-21.

Before use, the monitor verifies the fingerprint and verifies the intermediate against the system roots using openssl. It combines it with the system bundle only for IBPS requests. TLS validation remains enabled. If IBPS changes issuer or this intermediate expires, recheck the actual server chain and update the certificate deliberately.
