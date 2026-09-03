# Vobiz Requirements and Limitations

Checked against official Vobiz documentation on 9 August 2026.

## Required before the first call

- A Vobiz account with `VOBIZ_AUTH_ID` and `VOBIZ_AUTH_TOKEN`
- An outbound-capable `VOBIZ_PHONE_NUMBER` or approved caller ID
- Sufficient Vobiz account balance and an available route to the destination
- Any required India number KYC, UCC/NDNC, and calling authorization
- A public HTTPS backend address whose matching WSS endpoint is reachable
- A configured Gemini Live key/model
- A client record with explicit granted call consent

## Cost and account limits

- Vobiz is pay-as-you-go, not permanently free; carrier and streaming charges can apply.
- A successful API response means the call was accepted and queued, not answered.
- Low balance returns HTTP 402; account, routing, KYC, CPS, and concurrency controls can also reject calls.
- Number availability and caller-ID rules differ by country and traffic type.

## Implementation limits

- Only administrator-triggered outbound calls are enabled.
- Transfer, recording, campaigns, bulk dialing, and automated retry dialing are disabled.
- The public callback URL cannot be localhost.
- A temporary tunnel is acceptable for a controlled test, not production.
- The bridge is implemented and tested locally, but no successful PSTN Vobiz call is claimed until credentials, caller ID, balance/KYC, and one explicitly confirmed controlled call are complete.

Official references: [Vobiz introduction](https://vobiz.ai/docs/introduction), [make a call](https://vobiz.ai/docs/call/make-call), [phone numbers](https://vobiz.ai/docs/account-phone-number), [India regulations](https://vobiz.ai/docs/compliance/india/calling-regulations), and [Stream XML](https://vobiz.ai/docs/xml/stream).
