# Git Setup Guide

## ✅ Git Repository Initialized

Your repository has been initialized. Here's what's been set up:

### Files Created:
- `.gitignore` - Updated with comprehensive ignore patterns
- `.gitattributes` - Line ending normalization for cross-platform compatibility
- `.vscode/settings.json` - Includes file deletion protection settings

## 🔒 File-Deletion Protection Enabled

File deletion protection has been added to your Cursor settings. The AI will now:
- Ask for confirmation before deleting files
- Prevent accidental file deletions
- Require explicit approval for destructive operations

**Note:** You may need to reload Cursor (`Ctrl+Shift+P` → "Developer: Reload Window") for these settings to take effect.

## 📝 Next Steps

### 1. Configure Git (if not already done):
```bash
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### 2. Make Your First Commit:
```bash
# Stage all files (respects .gitignore)
git add .

# Create initial commit
git commit -m "Initial commit: Running coaching platform with calculators and pricing"

# Or commit in stages:
git add apps/
git add docker-compose.yml
git add README.md
git commit -m "Add core application files"
```

### 3. Create a Remote Repository (Optional but Recommended):
```bash
# On GitHub/GitLab/Bitbucket, create a new repository
# Then connect it:
git remote add origin https://github.com/yourusername/your-repo.git
git branch -M main
git push -u origin main
```

### 4. Regular Git Workflow:
```bash
# Check status
git status

# Stage changes
git add .

# Commit with descriptive message
git commit -m "Description of changes"

# Push to remote (if configured)
git push
```

## 🛡️ What's Protected

The `.gitignore` file now excludes:
- Environment variables (`.env` files)
- Build outputs (`.next/`, `node_modules/`, `__pycache__/`)
- IDE settings (`.vscode/`, `.idea/`)
- Docker override files
- Large binary files (PDFs, executables)
- Test coverage reports
- Temporary files

## 💡 Best Practices

1. **Commit Often**: Small, focused commits are better than large ones
2. **Write Clear Messages**: Describe what changed and why
3. **Review Before Committing**: Use `git status` and `git diff` to review changes
4. **Use Branches**: Create branches for features (`git checkout -b feature-name`)
5. **Keep `.env` Out**: Never commit environment variables or secrets

## 🔍 Useful Git Commands

```bash
# View changes
git diff

# View commit history
git log --oneline

# Undo changes (before staging)
git checkout -- filename

# Undo staging (keep changes)
git reset HEAD filename

# Create a new branch
git checkout -b feature-name

# Switch branches
git checkout main

# Merge branch
git merge feature-name
```

