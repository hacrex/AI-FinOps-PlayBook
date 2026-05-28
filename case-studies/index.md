---
layout: default
title: Case Studies
---

# Case Studies

Real-world examples and implementations of AI FinOps practices.

## Available Case Studies

{% assign case_pages = site.pages | where_exp: 'p', "p.path contains 'docs/case-studies/'" %}
{% for p in case_pages %}
- [{{ p.title | default: p.name }}]({{ p.url }})
{% endfor %}

- [Overview](./README.md) - Introduction to case studies
