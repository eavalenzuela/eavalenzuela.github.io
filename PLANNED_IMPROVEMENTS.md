# Planned Improvements

Plan for the eavalenzuela.github.io Jekyll blog ("Security-Minded Mindfulness").
Scope: committed content only — untracked draft posts in `_posts/` are
work-in-progress and are intentionally left untouched.

## Improvements (existing behavior/quality/docs)

1. **Fix `baseurl: "/"` → `""` in `_config.yml`** — `""` is the correct value for a
   root-hosted user site; `"/"` can produce protocol-relative `//` links through the
   `relative_url` filter on some Jekyll versions.
2. **Flesh out site metadata in `_config.yml`** (`description`, `author`, `lang`) — the
   description is currently the placeholder "Personal blog/CV."; these values feed the
   RSS feed and SEO meta tags.
3. **Add an explicit `exclude` list to `_config.yml`** — keeps repo-management files
   (CLAUDE.md, PLANNED_IMPROVEMENTS.md, README.md, Gemfile) from being copied into the
   published `_site` output.
4. **Replace the boilerplate `about.md`** — the live About page still shows the default
   Minima theme placeholder text; replace with a short factual page (who/what/links).
5. **Normalize old post titles** — 2018-era posts use underscored titles
   (`Intro_to_Responder`, `Scapy_RPC_Layer`, ...); newer posts use readable titles.
   URLs are filename-derived, so this is display-only and safe.
6. **Fix typos in committed posts** — e.g. "poisioning", "authenciate", "recieved",
   "reponse", "heirarchical", "Final Thoughs", "GitHub Monitr", "It's purpose".
7. **Update dead/moved external links** — SpiderLabs/Responder repo is archived (point
   to the maintained lgandx fork), `tools.ietf.org` → `datatracker.ietf.org`, dead
   TechNet and Catchpoint blog links → archive.org snapshots.
8. **Make image references portable** — replace `{{site.url}}/assets/images/...` with
   the `relative_url` filter so images resolve on any host and in local dev.
9. **Improve the 404 page** — add front matter (`permalink: /404.html`, title) and a
   link back to the home page.
10. **Add a repo README and extend `.gitignore`** — document local dev commands
    (bundle install / jekyll serve) and ignore `Gemfile.lock` (deliberately removed in
    commit c293f5c), `vendor/`, and `.bundle/`.

Note on CI: a GitHub Actions build-check workflow (jekyll build on PR) would be a
natural 11th item, but workflow files cannot be committed from this environment
(push token lacks `workflow` scope), so it is intentionally not implemented.

## New Features

11. **Archive page (`/archive/`)** — all posts grouped by year via pure Liquid
    (`group_by_exp`), no new plugins needed.
12. **Projects page (`/projects/`) driven by `_data/projects.yml`** — a data-file-backed
    index of the public tools already described in published posts, easy to extend.
13. **Previous/next post navigation** — links to adjacent posts at the bottom of
    `_layouts/post.html` using `page.previous`/`page.next`.
14. **Reading-time estimate in the post header** — word-count-based "N min read" in the
    post meta line, pure Liquid.
15. **Site navigation + discoverability** — nav links (About · Projects · Archive · RSS)
    on the home page, plus enable the GitHub-Pages-whitelisted `jekyll-sitemap` and
    `jekyll-seo-tag` plugins for crawlers and social previews.
