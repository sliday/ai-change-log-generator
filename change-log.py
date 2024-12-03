import argparse
from github import Github
from datetime import datetime, timedelta
import os
import re
import ell
from anthropic import Anthropic
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI
import sys
from colorama import init, Fore, Style

# Initialize colorama
init()

# Define constants for colors and emoji
SUCCESS = f"{Fore.GREEN}"
ERROR = f"{Fore.RED}"
INFO = f"{Fore.BLUE}"
WARNING = f"{Fore.YELLOW}"
RESET = Style.RESET_ALL

# Initialize ell with versioning enabled
ell.init(store='./logdir', autocommit=True)

# Initialize clients based on available API keys
anthropic_client = None
openai_client = None

# Add at the top with other constants
STYLE_TEMPLATES = {
    'playful': {
        'description': 'Fun and energetic with emojis',
        'format': {
            'added': '🚀 Launched',
            'updated': '✨ Leveled up',
            'fixed': '🐛 Squashed',
            'removed': '🗑️ Cleaned up',
            'security': '🔒 Secured',
            'performance': '⚡ Turbocharged'
        },
        'tone': 'casual and exciting',
        'example': '🚀 Launched an awesome new chat feature'
    },
    'regular': {
        'description': 'Clear and straightforward',
        'format': {
            'added': 'Added',
            'updated': 'Updated',
            'fixed': 'Fixed',
            'removed': 'Removed',
            'security': 'Secured',
            'performance': 'Improved'
        },
        'tone': 'clear and direct',
        'example': 'Added new chat feature'
    },
    'corporate': {
        'description': 'Professional and detailed',
        'format': {
            'added': 'Implemented',
            'updated': 'Enhanced',
            'fixed': 'Resolved',
            'removed': 'Deprecated',
            'security': 'Strengthened',
            'performance': 'Optimized'
        },
        'tone': 'formal and comprehensive',
        'example': 'Implemented enhanced communication functionality for improved user engagement'
    }
}

def print_welcome_message():
    print(f"\n{INFO}=== GitHub Changelog Generator ==={RESET}")
    print(f"{INFO}Checking prerequisites...{RESET}")
    
    # Check GitHub token
    github_token = os.environ.get('GITHUB_TOKEN')
    if github_token:
        print(f"{SUCCESS}✓ GitHub Token{RESET}")
    else:
        print(f"{ERROR}✗ GitHub Token missing{RESET}")
        print(f"\n{INFO}Get your token at: https://github.com/settings/tokens{RESET}")
        print("Permissions needed: repo:status, public_repo")
        print(f"Then: export GITHUB_TOKEN='your-token'{RESET}")
        sys.exit(1)

# Add this right after imports and constants
print_welcome_message()

def prompt_for_params(args, repo=None):
    """Interactive prompt for missing parameters"""
    print(f"\n{INFO}Configuration{RESET}")
    
    # Style selection
    print(f"\n{INFO}Select writing style:{RESET}")
    style_options = list(STYLE_TEMPLATES.keys())
    for idx, style in enumerate(style_options, 1):
        details = STYLE_TEMPLATES[style]
        print(f"  {idx}. {style}")
        print(f"     {details['description']}")
        print(f"     Example: {details['example']}\n")
    
    default_style = "regular"
    default_idx = style_options.index(default_style) + 1
    choice = input(f"Choice [{default_idx}]: ").strip() or default_idx
    
    try:
        choice = int(choice)
        if 1 <= choice <= len(style_options):
            args.style = style_options[choice - 1]
        else:
            args.style = default_style
    except ValueError:
        args.style = default_style
    
    print(f"\n{INFO}Repository Details{RESET}")
    
    if not args.url:
        print(f"\n{INFO}Enter your repository URL in one of these formats:{RESET}")
        print("- https://github.com/owner/repo")
        print("- github.com/owner/repo")
        print("- owner/repo")
        default_url = "owner/repo"
        args.url = input(f"Repository URL [{default_url}]: ").strip() or default_url
    
    if not args.branch:
        print(f"\n{INFO}The branch to generate changelog from (usually 'main' or 'master'){RESET}")
        default_branch = "main"
        args.branch = input(f"Branch name [{default_branch}]: ").strip() or default_branch
    
    # Only ask about commits if we have a repo object
    if repo:
        total_commits = count_total_commits(repo, args.branch)
        print(f"\n{INFO}How many commits to process?{RESET}")
        print("  Enter a number or 'all' for entire history")
        if total_commits:
            print(f"  Repository has {total_commits} commits")
        default_commits = "100"
        commit_input = input(f"Commits [{default_commits}]: ").strip() or default_commits
        
        if commit_input.lower() == 'all':
            args.num_commits = None
        else:
            try:
                args.num_commits = int(commit_input)
            except ValueError:
                print(f"{WARNING}Invalid input, using default: 100{RESET}")
                args.num_commits = 100
    
    return args

def init_clients():
    global anthropic_client, openai_client
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    openai_key = os.environ.get('OPENAI_API_KEY')
    
    if anthropic_key:
        anthropic_client = Anthropic(api_key=anthropic_key)
    if openai_key:
        openai_client = OpenAI(api_key=openai_key)

def get_universal_prompt(content: str, content_type: str, style: str) -> str:
    """Universal prompt template for both commits and summaries"""
    template = STYLE_TEMPLATES[style]
    
    base_instructions = f"""Transform the content into a {template['tone']} description.
Remove any sensitive information like:
- Internal URLs or endpoints
- Authentication details
- Database structures
- Environment variables
- Internal tool names
- User names or emails
- API keys or tokens

Content: {content}

Style Guide:
- Use {template['tone']} language
- Start changes with appropriate verbs ({', '.join(template['format'].values())})
- Focus on the impact and value of changes
- Remove technical implementation details
- Remove file names and paths
- Remove dates from descriptions

Example format: {template['example']}

Response format: Start each line with "- " and use clear markdown formatting.
No introductions or comments, just the formatted content."""

    if content_type == 'summary':
        base_instructions += """

Additional summary rules:
- Group similar changes together
- Prioritize major features and improvements
- Keep the hierarchy: ## Date followed by bullet points
- Maintain chronological order (newest first)

No introductions or comments, just the formatted content.
"""
    
    return base_instructions

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
@ell.simple(model="claude-3-5-sonnet-20240620", max_tokens=400, client=anthropic_client)
def format_commit_message_anthropic(message: str, diff: str, date: str, style: str) -> str:
    """Anthropic-based commit message formatter"""
    return get_universal_prompt(message, 'commit', style)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
@ell.simple(model="gpt-4o-mini", max_tokens=400, client=openai_client)
def format_commit_message_openai(message: str, diff: str, date: str, style: str) -> str:
    """OpenAI-based commit message formatter"""
    return get_universal_prompt(message, 'commit', style)

def parse_github_url(url):
    # Match patterns like: 
    # - https://github.com/owner/repo
    # - github.com/owner/repo
    # - owner/repo
    pattern = r"(?:https?://)?(?:www\.)?(?:github\.com/)?([^/]+)/([^/]+?)(?:\.git)?/?$"
    match = re.match(pattern, url)
    if not match:
        raise ValueError("Invalid GitHub URL format. Use format: owner/repo or https://github.com/owner/repo")
    return f"{match.group(1)}/{match.group(2)}"

def get_latest_changelog_date():
    """Get the most recent date from existing changelog"""
    try:
        with open("CHANGELOG.md", "r") as f:
            content = f.read()
            # Look for date headers in format ## YYYY-MM-DD
            dates = re.findall(r'## (\d{4}-\d{2}-\d{2})', content)
            if dates:
                return datetime.strptime(dates[0], '%Y-%m-%d').date()
    except FileNotFoundError:
        pass
    return None

def read_existing_changelog():
    """Read existing changelog content"""
    try:
        with open("CHANGELOG.md", "r") as f:
            return f.read()
    except FileNotFoundError:
        today = datetime.now().strftime('%Y-%m-%d')
        return f"# Changelog\n\n## {today}\n\n"

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
@ell.simple(model="claude-3-5-sonnet-20240620", max_tokens=400, client=anthropic_client)
def generate_changelog_summary(changelog_content: str, style: str) -> str:
    """Generate a summary of the changelog content"""
    return get_universal_prompt(changelog_content, 'summary', style)

def group_commits_by_period(commits_by_date, group_by='day'):
    """Group commits by specified time period"""
    grouped = {}
    commits_count = 0  # Add counter
    
    for date, messages in commits_by_date.items():
        if group_by == 'week':
            period = date - timedelta(days=date.weekday())
        elif group_by == 'month':
            period = date.replace(day=1)
        else:  # day or invalid value
            period = date
            
        if period not in grouped:
            grouped[period] = []
        grouped[period].extend(messages)
        commits_count += len(messages)  # Count messages
    
    print(f"\n{INFO}ℹ️ Commit distribution:{RESET}")
    for period in sorted(grouped.keys(), reverse=True):
        print(f"{INFO}  {period}: {len(grouped[period])} commits{RESET}")
    print(f"{INFO}ℹ️ Total commits preserved: {commits_count}{RESET}")
    
    return grouped

def get_preferred_branch(repo, custom_branch=None):
    """Get the preferred branch (custom, main, or master)"""
    if custom_branch:
        try:
            repo.get_branch(custom_branch)
            return custom_branch
        except:
            print(f"{WARNING}⚠️ Custom branch '{custom_branch}' not found, falling back to default branch search{RESET}")
    
    try:
        repo.get_branch("main")
        return "main"
    except:
        try:
            repo.get_branch("master")
            return "master"
        except:
            return repo.default_branch

def count_total_commits(repo, branch):
    """Count total number of commits in the repository"""
    try:
        commits = repo.get_commits(sha=branch)
        total = commits.totalCount
        print(f"{INFO}ℹ️ Repository has {total} total commits{RESET}")
        return total
    except Exception as e:
        print(f"{WARNING}⚠️ Unable to count total commits: {e}{RESET}")
        return None

def format_period_date(date, group_by):
    """Format date based on grouping period"""
    if group_by == 'day':
        # Format: 18 Nov 2024
        return date.strftime('%d %b %Y')
    elif group_by == 'week':
        # Get start and end of week (Monday to Sunday)
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)
        # Format: 18 Nov 2024 - 24 Nov 2024
        return f"{week_start.strftime('%d %b %Y')} - {week_end.strftime('%d %b %Y')}"
    elif group_by == 'month':
        # Return tuple of (year, month) for hierarchical formatting
        return (date.strftime('%Y'), date.strftime('%B'))  # %B gives full month name
    else:
        return date.strftime('%d %b %Y')  # Default to daily format

# Set up argument parser
parser = argparse.ArgumentParser(description='Generate changelog from GitHub repository')
parser.add_argument('url', 
                    help='GitHub repository URL (e.g., https://github.com/owner/repo)',
                    nargs='?')  # Make positional argument optional
parser.add_argument('-b', '--branch',
                   help='Specify custom branch name (default: main or master)',
                   default=None)
parser.add_argument('-n', '--num-commits', 
                    type=str,  # Changed to str to handle 'all'
                    default='100',
                    help='Number of recent commits to process (default: 100, use "all" for entire history)')
parser.add_argument('--model', 
                   choices=['anthropic', 'openai'],
                   default='anthropic',
                   help='Choose AI model provider (default: anthropic)')
parser.add_argument('--group-by', 
                   choices=['day', 'week', 'month'],
                   default='day',
                   help='Group commits by period (default: day)')
parser.add_argument('--style',
                   choices=list(STYLE_TEMPLATES.keys()),
                   default='regular',
                   help='Changelog style (default: regular)')
parser.add_argument('--after-date', 
                   help='Get changes after this date (YYYY-MM-DD format)',
                   type=str)

# Initialize GitHub client
g = Github(os.environ.get('GITHUB_TOKEN'))

args = parser.parse_args()

# First call without repo to get basic info
if not (args.url and args.branch and args.style):
    args = prompt_for_params(args)

# Initialize AI clients
init_clients()

# Verify API key availability based on model choice
if args.model == 'anthropic' and not anthropic_client:
    print(f"\n{ERROR}❌ Error: ANTHROPIC_API_KEY environment variable is not set{RESET}")
    print(f"{INFO}Please set your Anthropic API key:{RESET}")
    print("  export ANTHROPIC_API_KEY='your-key'")
    sys.exit(1)
elif args.model == 'openai' and not openai_client:
    print(f"\n{ERROR}❌ Error: OPENAI_API_KEY environment variable is not set{RESET}")
    print(f"{INFO}Please set your OpenAI API key:{RESET}")
    print("  export OPENAI_API_KEY='your-key'")
    sys.exit(1)

# Initialize GitHub client and get repo
try:
    repo = g.get_repo(parse_github_url(args.url))
    preferred_branch = get_preferred_branch(repo, args.branch)
    total_commits = count_total_commits(repo, args.branch)
    
    print(f"\n{SUCCESS}✅ Repository found: {repo.full_name}{RESET}")
    print(f"{INFO}ℹ️ Branch: {preferred_branch}{RESET}")
    print(f"{INFO}ℹ️ Description: {repo.description or 'No description'}{RESET}")
    print(f"{INFO}ℹ️ Repository has {total_commits} total commits{RESET}")
    
    # Ask about commits
    print(f"\n{INFO}How many commits to process?{RESET}")
    print("  Enter a number or 'all' for entire history")
    default_commits = "100"
    commit_input = input(f"Commits [{default_commits}]: ").strip() or default_commits
    
    if commit_input.lower() == 'all':
        args.num_commits = None
    else:
        try:
            args.num_commits = int(commit_input)
        except ValueError:
            print(f"{WARNING}Invalid input, using default: 100{RESET}")
            args.num_commits = 100
    
    # Ask about grouping
    print(f"\n{INFO}How to group changes?{RESET}")
    print("  1. By day")
    print("  2. By week")
    print("  3. By month")
    default_group = "1"
    group_input = input(f"Choice [{default_group}]: ").strip() or default_group
    
    group_options = {
        "1": "day",
        "2": "week",
        "3": "month"
    }
    args.group_by = group_options.get(group_input, "day")
    
    print(f"\n{INFO}🔄 Fetching commit history...{RESET}")
    latest_date = get_latest_changelog_date()
    
    commits = []
    for commit in repo.get_commits():
        commit_date = commit.commit.author.date.date()
        if latest_date and commit_date <= latest_date:
            break
        commits.append(commit)
        if args.num_commits and len(commits) >= args.num_commits:  # Check if num_commits is not None
            break
                
    if not commits:
        print("No new commits found since last changelog update.")
        exit(0)
            
    total_commits = 0
    changelog = {}
    
    for commit in commits:
        total_commits += 1
        if total_commits % 10 == 0:
            # Update progress message format
            progress = f"{total_commits}" if args.num_commits is None else f"{total_commits}/{args.num_commits}"
            print(f"{INFO}🔄 Processing commit {progress}...{RESET}")
                
        date = commit.commit.author.date.date()
        raw_message = commit.commit.message.split('\n')[0]
        
        # Remove diff handling since we don't need it
        if date not in changelog:
            changelog[date] = []
        
        try:
            format_func = format_commit_message_anthropic if args.model == 'anthropic' else format_commit_message_openai
            # Pass empty string for diff since we don't need it
            formatted_message = format_func(raw_message, "", date.strftime('%Y-%m-%d'), args.style)
            # Ensure proper formatting
            if not formatted_message.startswith('- '):
                formatted_message = f"- {formatted_message}"
        except Exception as e:
            print(f"Warning: Failed to format commit message, using sanitized original: {e}")
            # Basic sanitization of original message
            formatted_message = f"- {raw_message.split(':')[-1].strip()}"
        
        changelog[date].append(formatted_message)

    print(f"\nProcessed {total_commits} commits successfully")
    print("\nGenerating changelog file...")

    # Sort dates in descending order
    sorted_dates = sorted(changelog.keys(), reverse=True)

    # Always group commits (will use 'day' by default from args.group_by)
    changelog = group_commits_by_period(changelog, args.group_by)
    sorted_dates = sorted(changelog.keys(), reverse=True)

    # Generate formatted changelog
    formatted_changelog = "# Changelog\n\n"
    current_year = None
    current_month = None

    for period in sorted_dates:
        year = period.strftime('%Y')
        month = period.strftime('%B')  # Full month name

        # Add year header if it's new
        if year != current_year:
            current_year = year
            formatted_changelog += f"## {year}\n\n"
        
        # Always add month header
        if month != current_month:
            current_month = month
            formatted_changelog += f"### {month}\n\n"

        # Add commit messages
        for message in changelog[period]:
            formatted_changelog += f"{message}\n"
        
        formatted_changelog += "\n"

    # Generate summary using Ell
    try:
        summary = generate_changelog_summary(formatted_changelog, args.style)
        formatted_changelog = f"# Changelog\n\n{summary}\n"
    except Exception as e:
        print(f"Warning: Failed to generate summary: {e}")

    # Combine with existing changelog if it exists
    if latest_date:
        existing_content = read_existing_changelog()
        # Remove the header and summary from the new content
        new_content = formatted_changelog.replace("# Changelog\n\n", "")
        if "## Summary\n" in new_content:
            new_content = new_content.split("## Summary\n")[1].split("\n\n", 1)[1]
        # Combine new content with existing, preserving summary if it exists
        if "## Summary\n" in existing_content:
            formatted_changelog = existing_content.split("## Summary\n")[0] + \
                                   "## Summary\n" + summary + "\n\n" + \
                                   new_content + \
                                   "".join("## " + part for part in existing_content.split("## ")[2:])
        else:
            formatted_changelog = existing_content.split("## ")[0] + new_content + \
                                    "".join("## " + part for part in existing_content.split("## ")[1:])

    # Write changelog to file
    with open("CHANGELOG.md", "w") as f:
        f.write(formatted_changelog)

    print(f"\n{SUCCESS}✅ Changelog has been generated and saved as CHANGELOG.md{RESET}")
    print(f"{INFO}ℹ️ Total unique dates: {len(sorted_dates)}{RESET}")
    print(f"{INFO}ℹ️ Total commits processed: {total_commits}{RESET}")
    print(f"{INFO}Note: Multiple commits on the same day are grouped together{RESET}")
except Exception as e:
    if "404" in str(e):
        print(f"\n{ERROR}❌ Error: Repository '{repo_name}' not found{RESET}")
        print(f"\n{WARNING}⚠️ Possible issues:{RESET}")
        print("1. The repository doesn't exist")
        print("2. The repository URL is incorrect")
        print("3. The repository might be private")
        print("\nTroubleshooting steps:")
        print("1. Verify the repository URL in your browser:")
        print(f"   https://github.com/{repo_name}")
        print("2. If it's a private repository, you'll need:")
        print("   - ✓ repo (Full repository access)")
        print("   Instead of:")
        print("   - ✓ public_repo")
        print("   - ✓ repo:status")
        print("\nNote: Currently configured for public repositories only")
        exit(1)
    else:
        print(f"{ERROR}❌ Error accessing repository: {e}{RESET}")
        exit(1)
except ValueError as e:
    print(f"Error: {e}")
    exit(1)
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    print("Please check your internet connection and GitHub token permissions")
    exit(1)

# Add after argument parser to show available styles
if args.style:
    print(f"\n{INFO}ℹ️ Using {args.style} style:{RESET}")
    print(f"{INFO}Description: {STYLE_TEMPLATES[args.style]['description']}{RESET}")
    print(f"{INFO}Example: {STYLE_TEMPLATES[args.style]['example']}{RESET}\n")

# After writing the changelog
print(f"\n{SUCCESS}✅ All Steps Complete!{RESET}")
print(f"\n{INFO}Next steps:{RESET}")
print("1. Review the generated CHANGELOG.md file")
print("2. Make any necessary manual adjustments")
print("3. Commit the changes to your repository")
