# Kiramido1 — profile setup checklist

Everything in this folder is the content of the **`Kiramido1/Kiramido1`** repo (the special repo GitHub shows on your profile page).
Generated from your two CVs + the photo. Regenerate any time with `cd generator && python3 gen_banner.py` after editing `generator/profile.json`.

Order of operations: **repo → push → self-host stats → snake permissions + run → uncomment snake → verify → account cleanup.**

---

## 1. Create the profile repo (5 min)

1. Go to <https://github.com/new>
2. Repository name: `Kiramido1` (exactly your username). Public. **Do NOT** tick "Add a README" (we push our own).
3. Create. GitHub confirms you "found a secret".
4. Push this folder:

```bash
cd "/media/alpha/36A212E9A212ACFD6/ggithub/profile"
git remote add origin https://github.com/Kiramido1/Kiramido1.git
git push -u origin main
```

5. Open <https://github.com/Kiramido1> — the banner should render (dark or light depending on your theme).
   Test both: avatar → Settings → Appearance → switch theme → reload.

## 2. Self-host the stats cards (20 min) — don't skip

The public `github-readme-stats` instance constantly returns *"API rate limit exceeded"*. Your own Vercel instance never does.

**a. Token**
1. <https://github.com/settings/tokens> → **Tokens (classic)** → Generate new token (classic)
2. Note `readme-stats` · Expiration **No expiration** · Scope: tick **`repo`** (whole group)
3. Generate → **copy it immediately** (shown once). Never paste it into chat, a repo, or any website — it only goes into Vercel.

**b. Deploy**
1. Fork <https://github.com/anuraghazra/github-readme-stats>
2. <https://vercel.com> → Sign up with GitHub → Hobby (free)
3. Add New… → Project → Import the fork → leave build settings alone
4. Environment Variables: name `PAT_1`, value = the token → **Deploy** (~2 min)
5. Copy your URL, e.g. `https://github-readme-stats-abc123.vercel.app`
6. Verify: open `https://<your-instance>/api?username=Kiramido1&show_icons=true` — a card renders.
   If the build fails mentioning `maxDuration`: set it to `10` in the fork's `vercel.json`.

**c. Wire it in**
- Edit `generator/profile.json` → `"stats_instance": "https://<your-instance>"` → `cd generator && python3 gen_banner.py` → commit + push.
  (Or just find-and-replace `https://YOUR-INSTANCE.vercel.app` in `README.md`.)

Why `hide_rank=true`: the letter grade is weighted toward stars/followers, so a new account sits at "C" no matter how much you code. It measures popularity, not skill.

## 3. Contribution snake (10 min)

1. **Repo** settings (not account): <https://github.com/Kiramido1/Kiramido1/settings/actions>
   → scroll to **Workflow permissions** → **Read and write permissions** → Save.
2. Actions tab → **Generate Snake Animation** → **Run workflow**. It should go green in ~1 min and create an `output` branch.
   (The workflow file is already in `.github/workflows/snake.yml`; it also runs every 12 h and on every push to `main`.)
3. **Only after it's green**: open `README.md`, delete the `<!-- SNAKE: …` and `-->` lines around the snake block, commit, push.
   Adding it before the `output` branch exists shows a broken image.

## 4. Badges — already done

LinkedIn (brand blue — shields.io's LinkedIn logo silently vanishes on any other colour), Portfolio, Email.
Instagram/Facebook are omitted because your CVs don't list them. To add: fill the URLs in `generator/profile.json` and regenerate.

## 5. Account cleanup (the part that actually makes it look professional)

Your current profile: bio *"cyber security student"*, location *"Egypt,"* (trailing comma), no website, 27 repos, no profile README.

**Profile settings** (<https://github.com/settings/profile>)
- Name: Mohamed Ahmed Fekry
- Bio: `Penetration Tester & Security-focused QA Engineer @ Zedny · VAPT · OWASP · API Security · B.Sc. Cybersecurity '26`
- Location: `Cairo, Egypt`
- Website: `https://my-portfolio-virid-nine-95.vercel.app`
- Add LinkedIn under social accounts
- Use the same photo as the banner (cropped square) as your avatar.

**Pin these 6** (profile → Customize your pins) — the ones that match your CV story:
1. `NetSentinel` — WiFi security monitoring / pentest tool (Python)
2. `Amenly-Product` — AI compliance & cyber-risk API (ISO 27001 / NIST / GDPR)
3. `ANUBIS-Encryption-Algorithm-` — custom symmetric cipher (Python)
4. `front-green-vision` — NASA Space Apps 2025 finalist (Ultimate Green Vision)
5. `ELHAREEF-Mobile` — production mobile app (TypeScript)
6. **`RECDRAGON`** — it's the #1 project on both CVs but **it's not on your GitHub**. Publish it (README, usage, screenshots). Recruiters will look for it.

**Rename / delete / archive**
- **Delete `Nudes-Nadem`** (description: "made for wiliam to push the nadem nudes"). This is the first thing that will disqualify you with any recruiter or security team. Delete it today.
- Rename `ANUBIS-Encryption-Algorithm-` → `ANUBIS-Encryption-Algorithm` (trailing dash), `paddleGmae_ITI_Task` → `paddle-game` (typo).
- **Archive** the training/lab repos so they don't bury the real work: `day7_ITI`, `ITI_Frontend_day_6`, `Lab2_ITI_Vue.js`, `Vue.js-Lab2-ITI`, `final-lab-vue.js`, `drums_ITI_Task`, `clock_ITI_Task`, `paddleGmae_ITI_Task`, `Product-List-with-Cart-Objective`, `git_test`, `Encryption_Task1`, `plink`. (Repo → Settings → Danger Zone → Archive.) Or consolidate them into one `iti-frontend-training` repo.
- Add a one-line description + topics to every remaining repo that has none (`HITU`, `wa3eny-project`, `sara_project`, `Red_Phantoms`, `front-green-vision`, `plink`). Topics like `penetration-testing`, `owasp`, `cybersecurity`, `python` make you show up in GitHub search.
- Every pinned repo needs a README with: what it does, a screenshot/GIF, install + usage, tech stack. `NetSentinel` and `Amenly-Product` especially.
- Make sure no repo contains `.env` files, API keys, or client data from Zedny/DEPI engagements. Search each pinned repo for `password`, `token`, `secret`, `.env`.

**Commit hygiene going forward**
- Set your git identity so commits count on the graph: `git config --global user.email "mohamedahmedfekry2003@gmail.com"` (the email must be verified on GitHub → Settings → Emails).
- Enable 2FA (Settings → Password and authentication). Security roles get judged on this.

---

## Troubleshooting

"I changed it but nothing happened" → it's the CDN cache 95% of the time:
1. Open `https://raw.githubusercontent.com/Kiramido1/Kiramido1/main/dark.svg?v=999`, Ctrl+U, search for the hex colour you changed. If it's there, generation worked; wait (minutes to a few hours).
2. Check your theme — dark assets only render in dark mode.
3. Actions tab — is the newest snake run green *and* newer than your edit?

| Symptom | Cause |
|---|---|
| "API rate limit exceeded" on cards | Public instance — do step 2 |
| Snake image broken | `output` branch doesn't exist yet — run the Action |
| Snake grid invisible in dark mode | empty-cell colour too close to `#0d1117` (already set to `#2d3343`) |
| LinkedIn badge has no logo | must stay `#0A66C2` |
| Scheduled snake stops after ~60 days | GitHub pauses cron on inactive repos — push or click "Enable workflow" |

## Regenerating the banner

- Source of truth: `generator/gen_banner.py` + `generator/profile.json` + `generator/assets/*.npy`. Never hand-edit the SVGs.
- Crop: `generator/profile.json` → `"crop"` (pixels in the original photo).
- Real logos instead of the `</>`, `>_`, `{ }` glyphs: put a PNG (dark logo on white/transparent) in `generator/logos/` and set `"image": "logos/burp.png"` for each entry.
- Sizes: dark.svg ≈ 1.1 MB, light.svg ≈ 1.7 MB. That's the cost of ~17k/41k animated dots; GitHub serves them fine.
- Known: at ~900 px README width the dot lattice can show faint vertical banding on 1080p screens. It disappears when zooming; the only real fix is a coarser portrait. Don't burn hours on it.
