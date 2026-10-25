# Crest CFB wordmark

Source artwork for the wordmark shown in the site header and the phone app bar. The application renders it from `web/src/components/Wordmark.tsx`.

**Selected 2026-10-25:** lettering C / Balance with navy pairing B: navy `#20344D` in light mode and crisp white `#F8FAFC` in dark mode, without an accent stripe. See the [decision record](../../docs/decisions/2026-10-25-crest-wordmark.md).

## Files

- `crest-c.svg`: the wordmark. Uppercase CREST (cap height 66 vector units, Bitstream Charter Bold outlines) beside smaller uppercase CFB (30 units, Arimo Bold outlines) on a shared baseline. Outlined paths with `currentColor`; no runtime font requests.
- `build-wordmark.py`: regenerates `crest-c.svg` and the inline copy in `Wordmark.tsx` from the pinned font files, and `--check` verifies both are current. It refuses font files whose SHA-256 differs from the pinned values.
- `PROVENANCE.md`: font sources, versions, checksums, licence notices and the exact generation command.
- `licenses/`: the verbatim Arimo (SIL Open Font License) and Bitstream Charter licence texts.
- `navy.html`: the reviewed light and dark desktop and 26px phone specimens, embedding the current `crest-c.svg`. Open it from any static server.

Regenerate or verify (the font files are downloaded as described in `PROVENANCE.md`):

```sh
uv run --with fonttools python -I design/crest-wordmarks/build-wordmark.py --charter <bchb8a.pfb> --arimo <Arimo-Bold.ttf> --check
```

Scope: the header and phone app bar only. The favicon, OpenGraph image, share cards and exports keep their earlier look until separately scoped.
