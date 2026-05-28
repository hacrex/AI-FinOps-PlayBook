# GitHub Pages Deployment Instructions for Hacker Theme

## What Was Fixed

The theme wasn't loading because we were using `remote_theme` which requires special handling. We've switched to using the official `jekyll-theme-hacker` gem which is the recommended approach per GitHub's documentation.

## Changes Made

1. **_config.yml**: Changed from `remote_theme: pages-themes/hacker@v0.2.0` to `theme: jekyll-theme-hacker`
2. **Gemfile**: Updated to use `jekyll` and `jekyll-theme-hacker` gems directly
3. **Gemfile.lock**: Added complete lock file with all dependencies
4. **GitHub Actions workflow**: Updated to properly build with Bundler and the theme gem

## Deployment Steps

### 1. Commit and Push All Changes

```bash
git add _config.yml Gemfile Gemfile.lock .github/workflows/jekyll.yml
git commit -m "Fix: Switch to jekyll-theme-hacker gem for proper theme loading"
git push origin main
```

### 2. Verify GitHub Pages Settings

Go to your repository on GitHub:
1. Navigate to **Settings** → **Pages**
2. Ensure **Source** is set to "GitHub Actions" (NOT "Deploy from a branch")
3. If it's set to "Deploy from a branch", change it to "GitHub Actions"

### 3. Monitor the Build

1. Go to the **Actions** tab in your repository
2. You should see a workflow running named "Deploy Jekyll with Hacker Theme"
3. Wait for the build to complete (usually 1-2 minutes)
4. Check for any errors in the build logs

### 4. Verify the Site

Once the deployment shows a green checkmark:
1. Visit your GitHub Pages URL (shown in the Actions deployment output)
2. The Hacker theme should now be properly applied with:
   - Monospace fonts
   - Dark header with project title
   - Clean, minimalist design
   - Proper syntax highlighting

## Troubleshooting

### If Theme Still Doesn't Load

1. **Clear browser cache**: Press Ctrl+Shift+R (or Cmd+Shift+R on Mac)
2. **Check build logs**: Look for any warnings about the theme in the Actions tab
3. **Verify workflow source**: Make sure Pages is set to use GitHub Actions, not a branch
4. **Wait 5-10 minutes**: Sometimes CDN caching can delay theme loading

### Common Issues

- **"Theme not found" error**: Ensure you pushed Gemfile and Gemfile.lock
- **Old theme showing**: Hard refresh your browser (Ctrl+Shift+R)
- **Build fails**: Check that ruby/setup-ruby action can install dependencies

## Reference

Official GitHub documentation: https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll/adding-a-theme-to-your-github-pages-site-using-jekyll
