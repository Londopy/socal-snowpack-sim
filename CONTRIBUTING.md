# Contributing to socal-snowpack-sim

Issues and pull requests are welcome. Read [DISCLAIMER.md](DISCLAIMER.md) first: this is a
learning model, and changes that make it look more like a forecast than it is will be
turned down.

## Before you open a pull request

- Model changes: run `python src/terrain.py`, `python src/model.py` and `python src/analyze.py`,
  and say in the pull request how the numbers in `results/` moved and why.
- Viewer changes: `cd site`, `npm install`, `npm run dev`, and check the page in a browser,
  light and dark. `npm run build` has to pass. If the model or peak list changed, re-run
  `python src/export_site.py` and commit the new `site/public/data/`.
- Add a line under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md) if the change is
  something a user would notice.
- Fill in the pull request template, including the **AI tools** section.
- Sign the [CLA](CLA.md) when the check asks (once).

## AI-assisted contributions

You may use AI tools to help write a contribution. Three rules, which the
CLA makes binding:

- **Say so in the pull request.** The template has a section for it: which
  tool, and what it did (drafted the change, wrote the tests, explained the
  code, translated the docs, wrote the description). "None" is a fine answer.
  A check on every pull request fails until the section is filled in.
- **You are the author.** Read and understand everything the tool produced
  before you submit it; you are answerable for it in review exactly as for
  code you typed. A pull request whose author cannot explain a change is
  sent back. Commits and files name people, not tools: an AI tool is never
  listed as an author or co-author, and commits carry no "Generated with"
  footers. The check rejects both.
- **No laundering.** Do not submit output that reproduces someone else's
  work under a license incompatible with this project's license, or that you
  have no right to license. If a tool hands you a recognizable chunk of
  another project, leave it out.

An undisclosed AI-assisted contribution is closed when discovered, whatever
its quality. Disclosed ones are reviewed like any other, and labeled
`ai-assisted`.

The same goes for issues: if an AI tool wrote or summarized a bug report,
say so in it.

## Contributor License Agreement

Your first pull request gets a comment from the CLA check asking you to
accept [`CLA.md`](CLA.md) by replying with one sentence. You keep the
copyright in your work; the agreement gives the project a license to
distribute it under its license (or another OSI-approved license, never a
proprietary one) and a patent license for what your contribution
necessarily uses, and it records that the work is yours to give,
AI-assisted or not. Every author of a commit in the pull request signs once,
and that covers all their later pull requests. Companies contributing on
behalf of employees can open an issue naming the covered accounts instead.
