# GitHub Pages Setup Instructions for Hacker Theme

## Files Updated

1. **`_config.yml`** - Configured with `remote_theme: pages-themes/hacker@v0.2.0`
2. **`Gemfile`** - Uses `github-pages` gem for compatibility
3. **`.github/workflows/jekyll.yml`** - GitHub Actions workflow for automated deployment

## How to Enable GitHub Pages

### Option 1: Using GitHub Actions (Recommended)

The workflow file `.github/workflows/jekyll.yml` is already configured. Just:

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Configure Jekyll with Hacker theme for GitHub Pages"
   git push origin main
   ```

2. **Go to your repository on GitHub**:
   - Navigate to **Settings** → **Pages**
   - Under **Build and deployment**:
     - **Source**: Select "GitHub Actions"
   - The workflow will automatically build and deploy your site

3. **Wait for deployment**:
   - Go to **Actions** tab
   - Wait for the "Deploy Jekyll" workflow to complete
   - Your site will be live at `https://<username>.github.io/<repo-name>/`

### Option 2: Using Deploy from Branch (Legacy)

If you prefer the legacy method:

1. **Go to Settings** → **Pages**
2. Under **Build and deployment**:
   - **Source**: Select "Deploy from a branch"
   - **Branch**: Select `main` (or `master`) and `/ (root)` folder
   - Click **Save**
3. GitHub will automatically build your site using the configuration in `_config.yml`

## Troubleshooting

### Theme Not Loading

If the Hacker theme is not loading properly:

1. **Check `_config.yml`**: Ensure this line exists:
   ```yaml
   remote_theme: pages-themes/hacker@v0.2.0
   ```

2. **Verify plugins**: Ensure `jekyll-remote-theme` is in the plugins list:
   ```yaml
   plugins:
     - jekyll-remote-theme
   ```

3. **Check build logs**: 
   - Go to **Actions** tab
   - Click on the latest workflow run
   - Review the build logs for errors

4. **Clear cache**: Sometimes GitHub caches old builds. Try:
   - Going to **Actions** → Select workflow → **Run workflow** (manual re-run)

### Common Issues

- **404 errors**: Make sure you have an `index.md` or `index.html` in the root
- **CSS not loading**: Check that the theme is properly referenced in `_config.yml`
- **Build fails**: Review the Actions logs for specific error messages

## Testing Locally

To test your site locally before pushing:

```bash
# Install dependencies
bundle install

# Build and serve locally
bundle exec jekyll serve

# Visit http://localhost:4000
```

## Reference

Official GitHub Pages documentation:
- [Adding a theme to your GitHub Pages site using Jekyll](https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll/adding-a-theme-to-your-github-pages-site-using-jekyll)
- [Hacker Theme Repository](https://github.com/pages-themes/hacker)
