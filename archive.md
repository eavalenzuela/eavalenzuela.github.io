---
layout: default
title: Archive
permalink: /archive/
---

# Post Archive

{% assign posts_by_year = site.posts | group_by_exp: "post", "post.date | date: '%Y'" %}
{% for year in posts_by_year %}
## {{ year.name }}

<ul class="post-list">
  {% for post in year.items %}
  <li>
    <span class="post-meta">{{ post.date | date: "%b %-d, %Y" }}</span> —
    <a class="post-link" href="{{ post.url | relative_url }}">{{ post.title | escape }}</a>
  </li>
  {% endfor %}
</ul>
{% endfor %}

[&larr; Home]({{ "/" | relative_url }})
