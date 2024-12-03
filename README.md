# Git Changelog AI Generator

AI-powered changelog generator that creates clean, public-safe changelogs from GitHub commits using Claude or GPT-4o-mini.

![output3](https://github.com/user-attachments/assets/8c4ced91-1e1c-4b6f-a394-b4f2b84c28e0)

## Features

- AI-powered commit message formatting with multiple styles
- Automatic sensitive information removal
- Flexible date grouping and incremental updates
- Supports Claude 3.5 and GPT-4o-mini
- Preserves existing changelog entries

## Quick Start

1. Install packages:
   ```bash
   pip install PyGithub tenacity anthropic openai ell colorama
   ```

2. Set API keys:
   ```bash
   export GITHUB_TOKEN='your-token'           # Required
   export ANTHROPIC_API_KEY='your-key'        # For Claude 3.5+
   # OR
   export OPENAI_API_KEY='your-key'          # For GPT-4o-mini
   ```

3. Run:
   ```bash
   python change-log.py                      # Interactive mode
   # OR
   python change-log.py owner/repo           # Quick mode
   ```

## Usage Options

```bash
python change-log.py owner/repo \
  --num-commits 100 \     # Commits to process
  --model anthropic \     # AI provider
  --group-by day \       # day/week/month
  --style regular \      # playful/regular/corporate
  --branch main \        # Branch name
  --after-date 2024-03-01  # Get changes after date
```

## Output Styles

### Playful (with emojis)
```markdown
- 🚀 Launched new chat features
- ✨ Leveled up dashboard
```

![CleanShot 2024-11-18 at 20 45 32@2x](https://github.com/user-attachments/assets/d7df1010-48ae-4845-9b46-6ec648aefdb9)

### Regular (default)
```markdown
- Added chat functionality
- Updated dashboard
```

### Corporate (formal)
```markdown
- Implemented communication features
- Enhanced dashboard interface
```

## API Keys Setup

### GitHub Token (Required)
1. Visit [GitHub Token Settings](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Give it a descriptive name (e.g., "Changelog Generator")
4. Select required permissions:
   - `repo:status`
   - `public_repo`
5. Click "Generate token"
6. Copy and save the token immediately (it won't be shown again)

### Anthropic API Key (For Claude)
1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in to your account
3. Navigate to "API Keys" section
4. Click "Create Key"
5. Copy and save your API key

### OpenAI API Key (For GPT-4)
1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign up or log in to your account
3. Click "Create new secret key"
4. Give it a name (optional)
5. Copy and save your API key
6. Ensure your account has GPT-4 API access enabled

Note: Store your API keys securely and never commit them to version control.

## Troubleshooting

### GitHub Token
- Visit: https://github.com/settings/tokens
- Generate classic token
- Required permissions: `repo:status`, `public_repo`

### Common Issues
- Repository not found: Check URL and permissions
- API issues: Verify keys and quotas
- Rate limiting: Reduce commit count

## Limitations

- Requires valid API keys
- Subject to API rate limits
- Text-based commits only
- Default branch priority: custom → main → master
