# Hacker Theme Not Loading - Verification Steps

## Current Configuration (Correct)
Your files are correctly configured according to GitHub's official documentation:

### _config.yml
```yaml
theme: jekyll-theme-hacker  # ✅ Correct for supported themes
```

### Gemfile
```ruby
gem "github-pages", group: :jekyll_plugins  # ✅ Includes jekyll-theme-hacker
```

## Critical Check: GitHub Pages Source Setting

The theme won't load if you're using the wrong publishing source. Follow these steps:

### 1. Verify Publishing Source
Go to your repository → **Settings** → **Pages**

**You MUST have one of these configurations:**

#### Option A: Deploy from Branch (Simpler)
- **Source**: Deploy from a branch
- **Branch**: main/master
- **Folder**: root
- ⚠️ **If using this option**, the theme should work automatically after commit

#### Option B: GitHub Actions (Recommended)
- **Source**: GitHub Actions
- Your workflow file `.github/workflows/jekyll.yml` will handle deployment
- ✅ This is what your current setup uses

### 2. If Using GitHub Actions Source:

Check your latest workflow run:
1. Go to **Actions** tab
2. Click on the latest "Deploy Jekyll with Hacker Theme" run
3. Verify all steps completed successfully (green checkmarks)
4. Look for any warnings in the "Build with Jekyll" step

### 3. Common Issues & Solutions

#### Issue: Build succeeds but theme not applied
**Solution**: Hard refresh your browser
- Chrome/Edge: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- Firefox: `Ctrl+F5` or `Cmd+Shift+R`

#### Issue: Workflow shows errors
**Solution**: Check the build logs for:
- Missing dependencies
- Theme not found errors
- Base URL configuration issues

#### Issue: Still using "Deploy from branch" with old settings
**Solution**: 
1. Go to Settings → Pages
2. Change Source from "Deploy from a branch" to "GitHub Actions"
3. Save changes
4. Trigger a new workflow run

### 4. Verify Theme is Actually Building

Add this test to confirm the theme is loading:

Create a file `test-theme.md` in root:
```markdown
---
title: Theme Test
---

# Theme Test Page

If you see this with Hacker theme styling (monospace font, dark header), the theme is working!

## Testing CSS
This should appear in monospace font with the Hacker theme's green accent colors.
```

Commit and push, then check if the page renders with Hacker theme styling.

### 5. Alternative: Try remote_theme (if theme gem fails)

If `theme: jekyll-theme-hacker` doesn't work, try:

**_config.yml**:
```yaml
remote_theme: pages-themes/hacker@v0.2.0
plugins:
  - jekyll-remote-theme
```

**Gemfile**:
```ruby
gem "github-pages", group: :jekyll_plugins
gem "jekyll-remote-theme", group: :jekyll_plugins
```

## Quick Diagnostic Commands

Run locally to test:
```bash
bundle install
bundle exec jekyll serve
```

Then open http://localhost:4000 to verify theme loads locally.

## Expected Result

When working correctly, your site should have:
- ✅ Monospace fonts throughout
- ✅ Dark header bar with green accents
- ✅ Minimalist, terminal-like appearance
- ✅ Green links and buttons

Reference: https://pages-themes.github.io/hacker/
