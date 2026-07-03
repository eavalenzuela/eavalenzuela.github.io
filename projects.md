---
layout: default
title: Projects
permalink: /projects/
---

# Projects

Public tools I've built. Entries live in
[`_data/projects.yml`](https://github.com/eavalenzuela/eavalenzuela.github.io/blob/master/_data/projects.yml).

{% for project in site.data.projects %}
## [{{ project.name }}]({{ project.url }})

{{ project.description }}
{% if project.post %}
{% assign write_up = site.posts | where: "url", project.post | first %}
Related write-up: [{{ write_up.title | default: project.post }}]({{ project.post | relative_url }})
{% endif %}
{% endfor %}

[&larr; Home]({{ "/" | relative_url }})
