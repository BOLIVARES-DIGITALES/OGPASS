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
