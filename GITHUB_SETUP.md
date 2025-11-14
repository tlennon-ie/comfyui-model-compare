# GitHub Repository Setup Guide

## ✅ What's Been Done

Your git repository is fully initialized locally with:
- ✅ All 19 files committed
- ✅ Initial commit created with detailed message
- ✅ Branch set to `main`
- ✅ Remote configured: `https://github.com/tlennon-ie/comfyui-model-compare.git`

## 📋 Next Steps (You Need to Do These)

### Step 1: Create Private Repository on GitHub

1. Go to **https://github.com/new**
2. Enter repository name: **`comfyui-model-compare`**
3. Set visibility: **Private** ← Important!
4. Do NOT initialize with README, .gitignore, or license (already have them locally)
5. Click **Create repository**

### Step 2: Push to GitHub

Run this command in PowerShell:

```powershell
cd e:\AI\Comf\ComfyUI\custom_nodes\comfyui-model-compare
git push -u origin main
```

When prompted, use your GitHub authentication:
- **Username**: `tlennon-ie` (or paste your GitHub username)
- **Password**: Your GitHub Personal Access Token (PAT) or password

### Step 3: Verify on GitHub

1. Go to **https://github.com/tlennon-ie/comfyui-model-compare**
2. You should see:
   - All 19 files
   - "Initial commit" message
   - Private repository badge

---

## 🔐 Authentication Options

### Option A: Personal Access Token (Recommended)
1. Go to **GitHub Settings** → **Developer settings** → **Personal access tokens**
2. Click **Generate new token**
3. Name: `comfyui-model-compare`
4. Scopes: Select `repo` (full control of private repositories)
5. Click **Generate token** and copy it
6. Use token as password when `git push` asks

### Option B: SSH Key (More Secure)
If you have SSH configured:
```powershell
git remote set-url origin git@github.com:tlennon-ie/comfyui-model-compare.git
git push -u origin main
```

### Option C: GitHub CLI (Easiest)
If you have GitHub CLI installed:
```powershell
gh repo create comfyui-model-compare --private --source=. --remote=origin --push
```

---

## 📝 Update Configuration Files

After repository is created, update these files with your info:

### 1. `node_list.json` (Lines 5-7)
```json
"author": "tlennon-ie",
"repository": "https://github.com/tlennon-ie/comfyui-model-compare",
"reference": "https://github.com/tlennon-ie/comfyui-model-compare",
```

### 2. `__init__.py` (Line 15)
```python
WEB_DIRECTORY = None  # Update version as needed
```

### 3. `README.md` (Top of file)
```markdown
# ComfyUI Model Compare
[Update author info, links, etc.]
```

---

## 🚀 Typical Workflow (Going Forward)

```powershell
# After making changes:
cd e:\AI\Comf\ComfyUI\custom_nodes\comfyui-model-compare

# Stage changes
git add .

# Commit with message
git commit -m "feat: Add new feature description"

# Push to GitHub
git push origin main
```

---

## ✅ Commit Message Format

For consistency, use these prefixes:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation update
- `refactor:` - Code reorganization
- `perf:` - Performance improvement
- `test:` - Test additions

Example:
```
git commit -m "feat: Add LoRA strength curve support"
```

---

## 🔗 Repository URL

After creation, your repository will be at:
```
https://github.com/tlennon-ie/comfyui-model-compare
```

---

## ❓ Troubleshooting

### "Repository not found"
- Verify repository was created on GitHub
- Check username is correct: `tlennon-ie`
- Ensure it's set to **Private** (not Public)

### "Authentication failed"
- Use Personal Access Token instead of password
- Ensure token has `repo` scope
- Token must be valid (not expired)

### "Updates were rejected"
This usually means GitHub has different content. To force:
```powershell
git push -u origin main --force
```
⚠️ Only use `--force` on initial push with empty repo!

### "Cannot find the path"
Make sure current directory is correct:
```powershell
cd e:\AI\Comf\ComfyUI\custom_nodes\comfyui-model-compare
git status  # Should show no uncommitted changes
```

---

## 📞 Need Help?

1. Check GitHub Desktop app for visual interface
2. Run `git status` to see current state
3. Run `git log` to see commit history
4. Use `git --help` for git documentation

---

## ✨ What's Included in Your Repository

```
comfyui-model-compare/
├── Core Nodes (4 files)
│   ├── __init__.py
│   ├── model_compare_loaders.py
│   ├── sampler_compare.py
│   └── grid_compare.py
│
├── Documentation (8 files)
│   ├── README.md
│   ├── START_HERE.md
│   ├── QUICK_REFERENCE.md
│   ├── SETUP.md
│   ├── TECHNICAL.md
│   ├── CONTRIBUTING.md
│   ├── CHANGELOG.md
│   └── PROJECT_SUMMARY.md
│
├── Configuration (4 files)
│   ├── requirements.txt
│   ├── node_list.json
│   ├── LICENSE
│   └── .gitignore
│
├── Examples & Tools (2 files)
│   ├── example_workflow.json
│   └── verify_installation.py
│
└── Info (1 file)
    └── INSTALLATION_COMPLETE.txt
```

---

## 🎉 You're Ready!

Local repository: ✅ Complete and committed
GitHub repository: ⏳ Waiting for you to create and push

**Next action**: Create the private repository on GitHub and run `git push`

---

**Total Time**: ~5 minutes to create repo and push

Questions? Check GitHub's documentation: https://docs.github.com/en/repositories
