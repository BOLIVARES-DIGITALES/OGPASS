<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Project decisions

- Keep the public OGPASS preview isolated from the legacy sandbox API; only authenticated server functions may bridge production data, because the repository is public and its lookup endpoints are not authorization boundaries.
- Design the OGPASS entry experience mobile-first with vertically stacked audience choices and a short branded elephant loading state, because most visitors will enter from small iOS screens.
- The client consultation must use the authenticated same-origin API under `/api/transit/credentials/`; do not call Movired, Red or SUBE directly from browser code and do not scrape their public pages.
- Never render a demonstration amount as a real balance. A monetary value is visible only when the backend returns `status: verified`, with `source` and `observed_at`; all other states render without an amount.
- External references are personal data. The UI collects explicit versioned consent, never asks for PINs or banking credentials, and only receives a masked reference back from the backend.
- A verified OG consultation may return `product_details.red_metro` and `product_details.red_web3`. Keep these as expandable, source-separated views: never combine CLP with XLM or testnet with mainnet, and render `null` financial fields as unavailable rather than zero.
- The developer hardware check uses Web Serial at 115200 baud and must require an explicit port selection. Only show the reader as ready after a valid firmware `OGPASS_STATUS` response confirms ESP32, PN532, Wi-Fi and a recent backend heartbeat; browser capability or an open port alone is not proof of readiness.
