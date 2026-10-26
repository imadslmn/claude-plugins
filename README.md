# Solrus plugins for Claude Code

Engineering and compliance skills we use at [Solrus](https://solrus.pro) to build software and AI
automations for Algerian businesses. Anyone can install them.

## Install

Inside Claude Code (or from your shell with `claude plugin …`):

```
/plugin install algeria-data-protection --marketplace imadslmn/claude-plugins
```

or, in two steps:

```
/plugin marketplace add imadslmn/claude-plugins
/plugin install algeria-data-protection@solrus
```

Updates: when a plugin's version changes here, Claude Code offers the update in the `/plugin` panel.

## Plugins

| Plugin | What it does |
|---|---|
| [`algeria-data-protection`](plugins/algeria-data-protection) | Keeps AI-backed projects compliant with Algeria's personal-data law (Law 18-07 as amended by Law 25-11, enforced by the ANPDP): data residency, a de-identifying egress gateway so nothing identifying leaves the country inside an LLM API call, a local-model lane for what can't be de-identified, and the compliance paper trail (register, data-flow map, DPIA, privacy policy, processor annex). Includes a working PII redactor for Algerian formats and a CI audit script. |

## Contributing

Issues and pull requests are welcome, especially corrections to the legal summary (cite the Journal
Officiel) and new PII patterns with fixtures. Keep `SKILL.md` under 500 lines; put detail in
`references/`.

## Disclaimer

These plugins encode an engineering posture, not legal advice. Have an Algerian lawyer with ANPDP
experience review your project's `compliance/` folder before go-live.

## License

MIT — see [LICENSE](LICENSE).
