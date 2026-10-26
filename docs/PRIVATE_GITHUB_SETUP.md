# Private GitHub Repository Setup (English Only)

SECURESENSE-24 is **proprietary** and is intended to remain in a **Private** GitHub repository. **No repository has been created or pushed by this package.** You must publish it from your own authenticated GitHub session.

## Before the initial upload

1. Extract the supplied ZIP. Work from the extracted `SECURESENSE-24/` folder, not from inside the ZIP file.
2. Review [PROPRIETARY_NOTICE.md](../PROPRIETARY_NOTICE.md). Do not add a public license or an MIT license.
3. Check that `firmware/main/ss24_wifi_config.h` (containing the actual Wi-Fi password) is not included or tracked. Only `ss24_wifi_config.example.h` is provided.
4. Check report, screenshots and diagrams for personal information before inviting collaborators. The academic report includes author and institutional attribution.
5. Run `git status` and `git diff --cached --name-only` before the first commit. Ensure no real telemetry, credentials, or local environment files are staged.

## Option A — GitHub CLI

Install [Git](https://git-scm.com/download/win) and [GitHub CLI](https://cli.github.com/), then sign in using your own account:

```powershell
gh auth login
```

Open PowerShell in the extracted top-level `SECURESENSE-24/` directory and run:

```powershell
git init -b main
git add .
git status
git commit -m "Initial private proprietary SECURESENSE-24 repository"
gh repo create SECURESENSE-24 --private --source=. --remote=origin --push
```

The flag `--private` is mandatory for the intended deployment. **Do not use `--public`.** If the GitHub repository name already exists on your account, choose a different name or set up an existing private remote deliberately.

Verify visibility:

```powershell
gh repo view --json name,visibility --jq ".name + ': ' + .visibility"
```

The output should indicate `PRIVATE`.

## Option B — GitHub website

1. Go to [github.com/new](https://github.com/new).
2. Name the repository `SECURESENSE-24` and explicitly select **Private**.
3. Do not initialize the new repository with a README, license, or `.gitignore` (these are included in this package).
4. In PowerShell from the extracted folder, run:

```powershell
git init -b main
git add .
git status
git commit -m "Initial private proprietary SECURESENSE-24 repository"
git remote add origin https://github.com/YOUR_USERNAME/SECURESENSE-24.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username and complete GitHub authentication securely. Do not commit access tokens.

## Inviting authorized collaborators

Open the repository's **Settings → Collaborators → Add people** and invite only explicitly authorized users. On personal-account private repositories, collaborators may have write permissions; do not assume access is read-only. Distributing or copying the private repository still requires the rights holder's permission.

## If a public release already existed

Changing the visibility now does not guarantee that previously downloaded or publicly licensed copies can be recalled. If any earlier MIT-licensed version was actually published or distributed, consult the relevant prior license and seek legal advice before assuming those earlier grants are revocable. Do not upload or distribute the older MIT-licensed ZIP as this private edition.

## Updates

```powershell
git add .
git commit -m "Describe the internal update"
git push
```

Always confirm that the repository remains `Private` after configuration changes.
