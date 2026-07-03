# eavalenzuela.github.io

Source for [Security-Minded Mindfulness](https://eavalenzuela.github.io) — a
personal blog/CV covering network security tooling, malware analysis, packet
analysis, and defensive OSINT automation.

Built with [Jekyll](https://jekyllrb.com/) and the `jekyll-theme-midnight`
theme, published via GitHub Pages.

## Local development

```sh
bundle install              # first time / after Gemfile changes
bundle exec jekyll serve    # dev server at http://localhost:4000
bundle exec jekyll build    # static build to _site/
```

Note: `_config.yml` is **not** reloaded by `jekyll serve`; restart the server
after editing it.

## Layout

- `_posts/` — blog posts (`YYYY-MM-DD-Title.markdown`; the filename date drives
  ordering and URLs). Front matter: `layout: post`, `title: ...`.
- `_layouts/` — local overrides of the theme's `home` and `post` layouts.
- `_data/projects.yml` — entries for the [/projects/](https://eavalenzuela.github.io/projects/) page.
- `assets/images/` — image assets referenced from posts.
- `index.md` (home), `about.md`, `projects.md`, `archive.md`, `404.html` — top-level pages.
