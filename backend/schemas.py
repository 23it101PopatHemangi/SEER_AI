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
    author: Optional[str] = "Contributor"
    date: str

class IssueInfo(BaseModel):
    number: int
    title: str
    state: str
    author: Optional[str] = "Unknown"
    created_at: str
    updated_at: str
    labels: List[str] = []

class PullRequestInfo(BaseModel):
    number: int
    title: str
    state: str
    author: Optional[str] = "Unknown"
    created_at: Optional[str] = "2026-08-20T00:00:00Z"
    updated_at: Optional[str] = "2026-08-20T00:00:00Z"
    merged_at: Optional[str] = None
    is_merged: bool = False


class FileNode(BaseModel):
    path: str
    type: str

class BranchInfo(BaseModel):
    name: str
    protected: bool
    commit_sha: str

class ContributorInfo(BaseModel):
    login: str
    contributions: int
    avatar_url: Optional[str]
    html_url: Optional[str]

class IssuesSummary(BaseModel):
    total: int
    open: int
    closed: int

class PullRequestsSummary(BaseModel):
    total: int
    open: int
    closed: int
    merged: int

class ReadmeInsights(BaseModel):
    has_readme: bool
    summary: Optional[str]
    sections: List[str]

class KeyComponentDetail(BaseModel):
    path: str
    name: str
    purpose: str
    role: str
    relationships: List[str] = []

class ApiSurfaceDetail(BaseModel):
    method: str
    endpoint: str
    description: str
    source_file: str
    parameters: List[str] = []

class CodePatternDetail(BaseModel):
    pattern_name: str
    category: str
    description: str
    source_files: List[str] = []
    reusable_approach: str

class IntegrationPointDetail(BaseModel):
    service_name: str
    integration_type: str
    direction: str
    file_config: str
    purpose: str

class DependencyDetail(BaseModel):
    package: str
    version: str
    ecosystem: str
    purpose: str
    relationships: str

class AnalysisResponse(BaseModel):
    overview: Optional[str] = None
    technologies: List[str] = []
    architecture_overview: Optional[str] = None
    key_components: List[str] = []
    key_components_details: List[KeyComponentDetail] = []
    api_surface: List[str] = []
    api_surface_details: List[ApiSurfaceDetail] = []
    code_patterns: List[str] = []
    code_patterns_details: List[CodePatternDetail] = []
    integration_points: List[str] = []
    integration_points_details: List[IntegrationPointDetail] = []
    dependencies: List[str] = []
    dependencies_details: List[DependencyDetail] = []
    build_deployment_config: List[str] = []
    database_technologies: List[str] = []
    external_services: List[str] = []
    readme_insights: Optional[ReadmeInsights] = None


class RepositoryDetailResponse(BaseModel):
    metadata: RepositoryResponse
    languages: Dict[str, float]
    file_structure: List[FileNode]
    commits: List[CommitInfo]
    total_commits: Optional[int] = 0
    branches: List[BranchInfo] = []
    contributors: List[ContributorInfo] = []
    issues: List[IssueInfo]
    issues_summary: Optional[IssuesSummary] = None
    pull_requests: List[PullRequestInfo]
    pull_requests_summary: Optional[PullRequestsSummary] = None
    analysis: Optional[AnalysisResponse] = None
    analysis_status: str = "Completed"

