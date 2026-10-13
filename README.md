# Telegram Job Alerts (free GitHub Actions starter)

A standalone starter workflow for sending two daily job-discovery digests to Telegram.

## What it does
- Runs at 08:00 and 20:00 India Standard Time (GitHub cron uses UTC).
- Searches Google News RSS for relevant job/recruitment announcements.
- Filters and deduplicates headlines across runs using `job_alerts/state.json`.
- Sends the report to your Telegram bot.
- Can also be run manually from the GitHub Actions tab.

## Important limitations
This is a discovery starter, **not a guarantee that every result is open or legitimate**. Google News RSS is an index, not a job portal. Search results may be stale, miss relevant posts, or link to an intermediary. This version labels all results **UNVERIFIED LEADS** and does not claim that an application deadline or portal has been verified. Always open the original publisher/employer page before applying. A later version can add source-specific official career feeds and verification rules.

GitHub Actions free usage limits apply. This does not require a paid API, but external sources can change or rate-limit requests.

## Setup
1. Create a new GitHub repository, e.g. `telegram-job-alerts` (private is recommended).
2. Upload the files from this folder, preserving the `.github/workflows/job-alerts.yml` path.
3. In the repository, open **Settings → Secrets and variables → Actions**.
4. Under **Repository secrets**, add:
   - `TELEGRAM_BOT_TOKEN`: the token from @BotFather. Keep it secret; do not put it in code or commit it.
5. Under **Repository variables**, add:
   - `TELEGRAM_CHAT_ID`: `5201957203`
6. Open **Settings → Actions → General → Workflow permissions** and select **Read and write permissions**, then save. This allows the workflow to commit its deduplication state. If you prefer not to allow write access, remove the state-commit step from the workflow; deduplication will not persist reliably between runs.
7. Open **Actions**, enable workflows if GitHub asks, choose **Telegram Job Alerts**, then click **Run workflow**.
8. Open the run and check the logs. A successful run should send a message to Telegram and commit updated `job_alerts/state.json`.
9. Confirm the message arrived in your private chat with `@Employementjobbot`.

## Schedule
- 08:00 IST = 02:30 UTC
- 20:00 IST = 14:30 UTC

GitHub scheduled workflows may start late during high load and can be disabled after long periods of inactivity on public repositories. Manual dispatch is available for testing.

## Search focus
Lucknow and nearby districts (about 100 km), remote India, and relevant India-wide roles:
Python/backend/software, AI/ML/data, FDE/technical consulting, research/project staff, graduate trainee, apprenticeship, internships, government/PSU, startup hiring, walk-ins, and contract/freelance opportunities.

## Troubleshooting
- `TELEGRAM_BOT_TOKEN` missing: add it under Repository secrets, not variables.
- `chat not found`: open your bot and send `/start`; confirm `TELEGRAM_CHAT_ID` is correct.
- `Unauthorized`: token is wrong or revoked. Regenerate it with @BotFather and update the secret.
- No jobs in report: searches returned no new matching headlines; inspect Actions logs. The script will say so in Telegram.
- Workflow file not visible: make sure it is exactly `.github/workflows/job-alerts.yml`.
