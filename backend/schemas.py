from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime

# Project Schemas
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Repository Schemas
class RepositoryConnect(BaseModel):
    repository_url: str

class RepositoryResponse(BaseModel):
    id: str
    project_id: str
    github_url: str
    owner: str
    name: str
    description: Optional[str]
    default_branch: str
    primary_language: Optional[str]
    stars: int
    forks: int
    open_issues_count: int
    created_at: datetime
    updated_at: datetime
    last_pushed_at: datetime
    analysis_status: Optional[str] = "Not Analyzed"

    class Config:
        from_attributes = True

# Extended Details (For Frontend On-Demand Fetching)
class CommitInfo(BaseModel):
    sha: str
    message: str
    author: Optional[str]
    date: str

class IssueInfo(BaseModel):
    number: int
    title: str
    state: str
    author: str
    created_at: str
    updated_at: str
    labels: List[str]

class PullRequestInfo(BaseModel):
    number: int
    title: str
    state: str
    author: str
    created_at: str
    updated_at: str
    merged_at: Optional[str]
    is_merged: bool

class FileNode(BaseModel):
    path: str
    type: str

class AnalysisResponse(BaseModel):
    technologies: List[str]
    architecture_overview: Optional[str]
    key_components: List[str]
    api_surface: List[str]
    code_patterns: List[str]
    integration_points: List[str]
    dependencies: List[str]

class RepositoryDetailResponse(BaseModel):
    metadata: RepositoryResponse
    languages: Dict[str, float]
    file_structure: List[FileNode]
    commits: List[CommitInfo]
    issues: List[IssueInfo]
    pull_requests: List[PullRequestInfo]
    analysis: Optional[AnalysisResponse] = None
