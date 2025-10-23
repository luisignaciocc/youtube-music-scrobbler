# Using GitHub Actions for Automated Scrobbling

This guide explains how to configure and use GitHub Actions to automatically run the YouTube Music scrobbling script with cookie validation and failure notifications. It covers setting up secrets, configuring the workflow, and best practices for security and reliability.

## Overview

Instead of running the scrobbler manually, you can use a GitHub Actions workflow to run it automatically. This automates the process of fetching your YouTube Music history and scrobbling it to Last.fm. To do this securely, we use GitHub Secrets to store your sensitive information instead of committing them to the repository.

The workflow runs:
- On a schedule (every 30 minutes)
- On pushes to master and dev branches
- Manually via the GitHub Actions UI
- With automatic cookie validation and Discord notifications

## 1. Configuring Secrets

You need to add the following secrets to your GitHub repository. It is recommended to use **Environment-Level Secrets** for better security.

### Required Secrets

-   `LAST_FM_API`: Your Last.fm API key
-   `LAST_FM_API_SECRET`: Your Last.fm API secret  
-   `LASTFM_SESSION`: Your Last.fm session key
-   `YTMUSIC_COOKIE`: Your YouTube Music cookie (with __Secure-3PAPISID token)
-   `DISCORD_WEBHOOK_URL`: Your Discord webhook URL for failure/success notifications

### How to Add Secrets

1.  **Navigate to your repository on GitHub**
2.  Click on **Settings**
3.  In the left sidebar, click on **Environments**
4.  Click on **New environment** and name it `production`
5.  In the `production` environment, click on **Add secret** for each of the secrets listed above
6.  Enter the name of the secret (e.g., `LAST_FM_API`) and its value
7.  Click on **Add secret**

## 2. The GitHub Actions Workflow

The workflow is defined in `.github/workflows/sync.yml` with the following features:

```yaml
name: YouTube Music Scrobble Sync

on:
  schedule:
    - cron: '*/30 * * * *' # Every 30 minutes
  push:
    branches: [master, dev] # Trigger on push to master and dev branches
  workflow_dispatch: # Allows manual triggering from GitHub UI

jobs:
  scrobble:
    runs-on: ubuntu-latest
    environment: production
    outputs:
      scrobble_log: ${{ steps.scrobbler.outputs.scrobble_log }}
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Cache dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-
      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Cache scrobble database
        uses: actions/cache@v3
        with:
          path: data.db
          key: ${{ runner.os }}-scrobble-db-${{ github.run_id }}-${{ github.run_attempt }}
          restore-keys: |
            ${{ runner.os }}-scrobble-db-${{ github.run_id }}-
            ${{ runner.os }}-scrobble-db-

      - name: Run YouTube Music Scrobbler
        id: scrobbler
        env:
          LAST_FM_API: ${{ secrets.LAST_FM_API }}
          LAST_FM_API_SECRET: ${{ secrets.LAST_FM_API_SECRET }}
          YTMUSIC_COOKIE: ${{ secrets.YTMUSIC_COOKIE }}
          LASTFM_SESSION: ${{ secrets.LASTFM_SESSION }}
        run: |
          echo "Starting YouTube Music Scrobbler..."
          output=$(python start_standalone.py)
          echo "$output"
          echo "scrobble_log<<EOF" >> $GITHUB_OUTPUT
          echo "$output" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
          echo "YouTube Music Scrobbler finished."
         
  notify_failure:
    needs: scrobble
    runs-on: ubuntu-latest
    if: failure()
    environment: production
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Send Discord notification
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
          SCROBBLE_LOG: ${{ needs.scrobble.outputs.scrobble_log }}
        run: |
          pip install requests
          python .github/scripts/send_failure_notification.py

  notify_success:
    needs: scrobble
    runs-on: ubuntu-latest
    if: success()
    environment: production
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      - name: Send Discord notification
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
          SCROBBLE_LOG: ${{ needs.scrobble.outputs.scrobble_log }}
        run: |
          pip install requests
          python .github/scripts/send_success_notification.py
```

### How it Works

- **`on.schedule`**: Runs every 30 minutes to catch new listening activity
- **`on.push`**: Runs when code is pushed to master/dev branches
- **`on.workflow_dispatch`**: Allows manual triggering
- **Cookie validation**: The script validates your YouTube Music cookie before processing
- **Notifications**: Discord messages sent on both success and failure
- **Database caching**: The scrobble database is cached between runs
- **Environment**: All secrets are accessed through the `production` environment

## 3. Running the Workflow

You can trigger the workflow in several ways:

*   **Scheduled:** Runs every 30 minutes automatically
*   **Manual:** Click "Run workflow" button in the GitHub Actions UI
*   **Push:** Triggered when commits are pushed to master or dev branches

## 4. Cookie Validation and Notifications

### Cookie Validation
- The script validates your YouTube Music cookie before attempting to fetch history
- If your cookie expires, the script will fail and trigger a notification
- Common cause of failures is expired YouTube Music cookies (typically expire in days)

### Discord Notifications
- **Success notifications**: Show detailed processing information including which tracks were scrobbled
- **Failure notifications**: Provide specific guidance for fixing issues, especially cookie expiration
- **Cookie update guidance**: Clear steps to refresh your YouTube Music cookie when needed

## 5. Best Practices and Security

-   **Never commit secrets** to the repository
-   **Use Environment-level secrets** for production to restrict their use to the `production` environment
-   **Rotate your cookies and API keys** periodically for security
-   **Monitor Discord notifications** to stay informed of any issues
-   **Update YouTube Music cookie** when notified (typically every few days)

## 6. Troubleshooting

-   **"YouTube Music cookie is expired" errors:**
    -   Get a fresh cookie from your browser as described in the README
    -   Cookies typically expire after a few days, which is normal behavior
    
-   **Secret appears empty:**
    -   Confirm the secret exists in the `production` environment
    -   Confirm the job is using the `production` environment

-   **Sync is failing:**
    -   Check the workflow logs in the GitHub Actions tab for specific error details
    -   Run the script locally with the same environment variables to reproduce the issue
    -   Check Discord notifications for detailed error categorization and resolution steps

-   **Notifications not received:**
    -   Verify `DISCORD_WEBHOOK_URL` secret is correctly configured
    -   Check that the Discord webhook URL is valid and has proper permissions
