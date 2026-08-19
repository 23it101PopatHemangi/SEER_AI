import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Import database module
from database import get_db, init_db, Project as DBProject, Repository as DBRepository, UserToken
import schemas
import github_service
import github_oauth
import repo_analyzer

# Load environment variables
load_dotenv()

app = FastAPI(
    title="SEER AI API",
    description="Backend API for SEER AI Platform",
    version="1.3.0"
)

# CORS configuration to allow local frontend development server
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register OAuth Router
app.include_router(github_oauth.router)

# Initialize database schemas on boot
@app.on_event("startup")
def startup_event():
    init_db()

# Dependency to retrieve the logged-in user's GitHub OAuth token
def get_user_github_token(
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
    db: Session = Depends(get_db)
) -> Optional[str]:
    if not x_user_email:
        return None
    db_token = db.query(UserToken).filter(UserToken.user_email == x_user_email).first()
    if db_token:
        return db_token.github_access_token
    return None

# Helper to parse dates securely
def parse_github_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.utcnow()
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.utcnow()

# Root / Health endpoint
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "message": "SEER AI backend is healthy",
        "version": "1.3.0",
        "database": "sqlite/postgresql setup active"
    }

# ----------------- PROJECTS ENDPOINTS -----------------

@app.get("/api/projects", response_model=List[schemas.ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(DBProject).all()
    
    from repo_analyzer import CACHE_DIR
    import os
    
    for project in projects:
        repos = db.query(DBRepository).filter(DBRepository.project_id == project.id).all()
        latest_time = project.updated_at
        for r in repos:
            cache_path = os.path.join(CACHE_DIR, f"{r.id}.json")
            if os.path.exists(cache_path):
                mtime = datetime.utcfromtimestamp(os.path.getmtime(cache_path))
                if mtime > latest_time:
                    latest_time = mtime
        if latest_time > project.updated_at:
            project.updated_at = latest_time
            db.commit()
            db.refresh(project)
            
    return projects

@app.post("/api/projects", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project_in: schemas.ProjectCreate, db: Session = Depends(get_db)):
    if not project_in.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name cannot be empty"
        )
    
    new_project = DBProject(
        id=str(uuid.uuid4()),
        name=project_in.name.strip(),
        description=project_in.description.strip() if project_in.description else ""
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project

@app.get("/api/projects/{projectId}", response_model=schemas.ProjectResponse)
def get_project(projectId: str, db: Session = Depends(get_db)):
    project = db.query(DBProject).filter(DBProject.id == projectId).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Sync with repository analysis cache modification times
    from repo_analyzer import CACHE_DIR
    import os
    
    repos = db.query(DBRepository).filter(DBRepository.project_id == projectId).all()
    latest_time = project.updated_at
    for r in repos:
        cache_path = os.path.join(CACHE_DIR, f"{r.id}.json")
        if os.path.exists(cache_path):
            mtime = datetime.utcfromtimestamp(os.path.getmtime(cache_path))
            if mtime > latest_time:
                latest_time = mtime
                
    if latest_time > project.updated_at:
        project.updated_at = latest_time
        db.commit()
        db.refresh(project)
        
    return project

# ----------------- REPOSITORIES ENDPOINTS -----------------

@app.get("/api/projects/{projectId}/repositories", response_model=List[schemas.RepositoryResponse])
def list_repositories(projectId: str, db: Session = Depends(get_db)):
    project = db.query(DBProject).filter(DBProject.id == projectId).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
    repos = db.query(DBRepository).filter(DBRepository.project_id == projectId).all()
    
    import os
    from repo_analyzer import CACHE_DIR
    
    enriched = []
    for r in repos:
        cache_path = os.path.join(CACHE_DIR, f"{r.id}.json")
        status_val = "Analyzed" if os.path.exists(cache_path) else "Not Analyzed"
        
        # Build dictionary matching schema parameters
        enriched.append({
            "id": r.id,
            "project_id": r.project_id,
            "github_url": r.github_url,
            "owner": r.owner,
            "name": r.name,
            "description": r.description,
            "default_branch": r.default_branch,
            "primary_language": r.primary_language,
            "stars": r.stars,
            "forks": r.forks,
            "open_issues_count": r.open_issues_count,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "last_pushed_at": r.last_pushed_at,
            "analysis_status": status_val
        })
    return enriched

@app.post("/api/projects/{projectId}/repositories", response_model=schemas.RepositoryResponse, status_code=status.HTTP_201_CREATED)
def connect_repository(
    projectId: str,
    repo_in: schemas.RepositoryConnect,
    db: Session = Depends(get_db),
    github_token: Optional[str] = Depends(get_user_github_token)
):
    project = db.query(DBProject).filter(DBProject.id == projectId).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # 1. Parse repository URL
    owner, repo_name = github_service.parse_github_url(repo_in.repository_url)

    # 2. Duplicate repository protection
    existing = db.query(DBRepository).filter(
        DBRepository.project_id == projectId,
        DBRepository.owner.ilike(owner),
        DBRepository.name.ilike(repo_name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This repository is already connected to this project."
        )

    # 3. Call GitHub API to fetch metadata (using active user OAuth token if present)
    meta = github_service.fetch_repo_metadata(owner, repo_name, token=github_token)

    # 4. Save metadata to Database
    new_repo = DBRepository(
        id=str(uuid.uuid4()),
        project_id=projectId,
        github_url=f"https://github.com/{owner}/{repo_name}",
        owner=owner,
        name=repo_name,
        description=meta.get("description") or "",
        default_branch=meta.get("default_branch", "main"),
        primary_language=meta.get("language") or "Unknown",
        stars=meta.get("stargazers_count", 0),
        forks=meta.get("forks_count", 0),
        open_issues_count=meta.get("open_issues_count", 0),
        created_at=parse_github_date(meta.get("created_at")),
        updated_at=parse_github_date(meta.get("updated_at")),
        last_pushed_at=parse_github_date(meta.get("pushed_at"))
    )
    db.add(new_repo)
    
    # Update project updated_at date
    project.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(new_repo)
    return new_repo

@app.get("/api/projects/{projectId}/repositories/{repositoryId}", response_model=schemas.RepositoryDetailResponse)
def get_repository_detail(
    projectId: str,
    repositoryId: str,
    db: Session = Depends(get_db),
    github_token: Optional[str] = Depends(get_user_github_token)
):
    project = db.query(DBProject).filter(DBProject.id == projectId).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Fetch repository metadata from Database
    repo = db.query(DBRepository).filter(
        DBRepository.id == repositoryId,
        DBRepository.project_id == projectId
    ).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found in this project")

    # Update parent project updated_at date to match this action
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(repo)

    # Fetch live GitHub data on-demand (injecting the active OAuth token)
    try:
        languages = github_service.fetch_repo_languages(repo.owner, repo.name, token=github_token)
        file_structure = github_service.fetch_repo_tree(repo.owner, repo.name, repo.default_branch, token=github_token)
        commits = github_service.fetch_repo_commits(repo.owner, repo.name, token=github_token)
        issues = github_service.fetch_repo_issues(repo.owner, repo.name, state="all", token=github_token)
        pull_requests = github_service.fetch_repo_pulls(repo.owner, repo.name, state="all", token=github_token)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error fetching live data: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected error communicating with GitHub API."
        )

    # Statically analyze repository
    try:
        analysis = repo_analyzer.analyze_repo_pipeline(
            repo.id,
            repo.last_pushed_at.isoformat(),
            repo.owner,
            repo.name,
            file_structure,
            token=github_token
        )
    except Exception as e:
        print(f"Failed to statically analyze repository: {e}")
        analysis = {
            "technologies": [],
            "architecture_overview": None,
            "key_components": [],
            "api_surface": [],
            "code_patterns": [],
            "integration_points": [],
            "dependencies": []
        }

    return {
        "metadata": repo,
        "languages": languages,
        "file_structure": file_structure,
        "commits": commits,
        "issues": issues,
        "pull_requests": pull_requests,
        "analysis": analysis
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
