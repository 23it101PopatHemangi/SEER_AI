import os
import re
import requests
from fastapi import HTTPException, status

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)

def get_headers(token: str = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # Prioritize user's OAuth token, then fall back to server's GITHUB_TOKEN
    active_token = token or GITHUB_TOKEN
    if active_token:
        headers["Authorization"] = f"Bearer {active_token}"
    return headers

def parse_github_url(url: str) -> tuple[str, str]:
    """
    Parses owner and repository name from a GitHub URL.
    Example: https://github.com/facebook/react -> ('facebook', 'react')
    """
    pattern = r"github\.com/([^/]+)/([^/]+?)(?:\.git|/)?$"
    match = re.search(pattern, url.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub repository URL. Format must be: https://github.com/owner/repository"
        )
    return match.group(1), match.group(2)

def handle_github_response(response: requests.Response):
    """
    Utility to handle GitHub response codes and raise friendly HTTPExceptions.
    """
    if response.status_code == 200:
        return response.json()
    
    if response.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub repository not found. Please verify the URL is correct and public."
        )
    elif response.status_code == 403:
        # Check if rate limit is reached
        rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
        if rate_limit_remaining == "0":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="GitHub API rate limit reached. Please configure a GITHUB_TOKEN in your environment or try again later."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to the repository is forbidden. Private repositories are not supported."
            )
    elif response.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub token configured. Please check your GITHUB_TOKEN variable."
        )
    
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"GitHub API returned an error: {response.reason} (Status {response.status_code})"
    )

def fetch_repo_metadata(owner: str, repo: str, token: str = None) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    res = requests.get(url, headers=get_headers(token))
    return handle_github_response(res)

def fetch_repo_languages(owner: str, repo: str, token: str = None) -> dict:
    """
    Fetches language statistics and computes percentage allocations.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    res = requests.get(url, headers=get_headers(token))
    raw_langs = handle_github_response(res)
    
    total_bytes = sum(raw_langs.values())
    if total_bytes == 0:
        return {}
    
    return {
        lang: round((bytes_count / total_bytes) * 100, 1)
        for lang, bytes_count in raw_langs.items()
    }

def fetch_repo_tree(owner: str, repo: str, branch: str, token: str = None) -> list:
    """
    Fetches the recursive file tree structure of the repository.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    res = requests.get(url, headers=get_headers(token))
    data = handle_github_response(res)
    
    # Return structured path strings
    tree = data.get("tree", [])
    # Return path and type (blob/tree)
    return [
        {"path": item.get("path"), "type": item.get("type")}
        for item in tree
    ]

def fetch_repo_commits(owner: str, repo: str, token: str = None) -> list:
    """
    Fetches the latest 10 commits of the repository.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=10"
    res = requests.get(url, headers=get_headers(token))
    commits_data = handle_github_response(res)
    
    normalized = []
    for item in commits_data:
        commit_info = item.get("commit", {})
        git_author_name = commit_info.get("author", {}).get("name")
        github_author = item.get("author") or {}
        github_login = github_author.get("login")
        
        # Decide which name to display:
        # If the git name is null, empty, or literally "unknown", fall back to the GitHub login.
        author_name = git_author_name
        if not author_name or author_name.lower() == "unknown":
            author_name = github_login or "Unknown"

        normalized.append({
            "sha": item.get("sha"),
            "message": commit_info.get("message"),
            "author": author_name,
            "date": commit_info.get("author", {}).get("date"),
        })
    return normalized

def fetch_repo_issues(owner: str, repo: str, state: str = "all", token: str = None) -> list:
    """
    Fetches issues for the repository. Skips Pull Requests (which are returned by default).
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues?per_page=50&state={state}"
    res = requests.get(url, headers=get_headers(token))
    issues_data = handle_github_response(res)
    
    normalized = []
    for item in issues_data:
        # GitHub's issues endpoint returns pull requests as well. Filter them out.
        if "pull_request" in item:
            continue
            
        normalized.append({
            "number": item.get("number"),
            "title": item.get("title"),
            "state": item.get("state"),
            "author": item.get("user", {}).get("login"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "labels": [label.get("name") for label in item.get("labels", [])]
        })
    return normalized

def fetch_repo_pulls(owner: str, repo: str, state: str = "all", token: str = None) -> list:
    """
    Fetches pull requests for the repository.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?per_page=50&state={state}"
    res = requests.get(url, headers=get_headers(token))
    pulls_data = handle_github_response(res)
    
    normalized = []
    for item in pulls_data:
        normalized.append({
            "number": item.get("number"),
            "title": item.get("title"),
            "state": item.get("state"),
            "author": item.get("user", {}).get("login"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "merged_at": item.get("merged_at"),
            "is_merged": item.get("merged_at") is not None
        })
    return normalized
