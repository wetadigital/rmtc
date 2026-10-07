# Website

## Feature Description

RMTC currently has no dedicated website — documentation exists only in the repository (README.md, docs/*.md). A static documentation website will provide an accessible entry point for potential users, improve SEO/discoverability, and establish a professional presence within the ASWF. The site will aggregate existing documentation and technical notes into a polished, navigable format. This is greenfield infrastructure.

## Criticality

High. A public website is essential for ASWF project visibility, user onboarding, and community growth. Current reliance on GitHub README limits discoverability and creates a barrier for non-developers. This is a prerequisite for graduating from prototype to community-adopted project.

## T-Shirt Size

M. A minimal viable static site (no server logic) built from existing docs typically requires 2-3 weeks: build-tool setup, template design, documentation structure, deployment to GitHub Pages. No new dependency is needed beyond the build toolchain.

## How to Implement

1. **Static Site Generation**: Adopt a lightweight SSG (e.g., MkDocs, Hugo, or Sphinx) configured to:
   - Ingest Markdown from `docs/` (technical_notes.md, entity_schema.yaml commentary, examples).
   - Include images from `docs/images/` (already present: pipeline diagrams, GUI screenshots).
   - Auto-generate navigation from directory structure.
   - Support responsive CSS for mobile/tablet.

2. **Site Structure**: Create `website/` or similar top-level directory with:
   - `config.{yml,toml}` for the SSG (site metadata, nav, branding).
   - `docs/` or `content/` symlink/copy to `docs/` (or reference directly).
   - `theme/` or `templates/` for custom styling (logo, color scheme, footer attribution).

3. **GitHub Pages Deployment**:
   - Enable GitHub Pages in repository settings to serve from `docs/` or a `gh-pages` branch.
   - Add `.github/workflows/deploy-site.yml` to build and publish on pushes to main (e.g., MkDocs or Hugo CI action).
   - Confirm ASWF domain/subdomain setup (e.g., `https://rmtc.aswf.io` or hosted under ASWF umbrella).

4. **Content Curation**:
   - Create landing page (1-2 sentences about RMTC, key features, quick-start link).
   - Organize docs: Overview → Installation → Usage → API → Contributing → Roadmap.
   - Link to GitHub issues, Slack, and ASWF wiki for support/community.

5. **Testing & Polish**:
   - Build locally to verify rendering, links, and image references.
   - Test on mobile browsers.
   - Deploy to staging/test site first if possible.

## Considerations

- **Greenfield Build Tooling**: No existing website build system — will require initial setup of SSG and CI/CD glue. MkDocs is lightweight and Python-ecosystem-friendly; Hugo is faster but requires Go knowledge.
- **Content Freshness**: Docs that move (technical_notes.md, roadmap) must remain in sync with website or be auto-generated to avoid stale information.
- **Dark Mode**: Consider light/dark theme switching if logo/design supports it; MkDocs and Hugo both have plugins for this.
- **ASWF Integration**: Coordinate with ASWF to register the domain and confirm DNS/GitHub Pages hosting approach.
- **SEO**: Add meta tags, sitemap, and robots.txt once live.
- **Out of Scope**: Blog/news feed, user forums, interactive tutorials (those are phase 2 enhancements).
- **Dependency on Logo**: Website launch should include new logo (see new-logo.md) in header/branding for maximum impact.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
