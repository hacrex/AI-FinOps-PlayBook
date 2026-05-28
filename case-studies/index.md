---
layout: default
title: Case Studies
---

# Case Studies

Real-world examples and implementations of AI FinOps practices.

## Available Case Studies

{% for file in site.static_files %}
  {% if file.path contains 'case-studies' and file.name contains '.md' and file.name != 'index.md' and file.name != 'README.md' %}
    - [{{ file.name }}]({{ file.path }})
  {% endif %}
{% endfor %}

- [Overview](./README.md) - Introduction to case studies

