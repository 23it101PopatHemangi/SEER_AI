import os
import re
import json
import base64
import requests
from typing import List, Dict, Any, Optional
from github_service import get_headers

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def get_cached_analysis(repo_id: str, last_pushed_at: str) -> Optional[Dict[str, Any]]:
    """
    Checks if a cached analysis file exists on disk and is up to date.
    """
    ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"{repo_id}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                # Invalidate if repo was pushed since cache was saved
                if cached_data.get("last_pushed_at") == last_pushed_at:
                    return cached_data.get("analysis")
        except Exception as e:
            print(f"Failed to read analysis cache for {repo_id}: {e}")
    return None

def save_analysis_cache(repo_id: str, last_pushed_at: str, analysis: Dict[str, Any]):
    """
    Saves the analyzed telemetry results to disk cache.
    """
    ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"{repo_id}.json")
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({
                "last_pushed_at": last_pushed_at,
                "analysis": analysis
            }, f, indent=2)
    except Exception as e:
        print(f"Failed to save analysis cache for {repo_id}: {e}")

def fetch_file_content(owner: str, repo: str, path: str, token: str = None) -> Optional[str]:
    """
    Downloads file content from GitHub and decodes it from base64.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    try:
        res = requests.get(url, headers=get_headers(token), timeout=10)
        if res.status_code == 200:
            data = res.json()
            content_b64 = data.get("content", "")
            if content_b64:
                # Remove newlines and decode
                clean_b64 = content_b64.replace("\n", "").replace("\r", "")
                content_bytes = base64.b64decode(clean_b64)
                return content_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Failed to download file {path}: {e}")
    return None

def extract_readme_description(owner: str, repo: str, paths: List[str], token: str = None) -> Optional[str]:
    """
    Downloads README.md and extracts the first non-empty descriptive paragraph.
    """
    readme_path = next((p for p in paths if p.lower() in ["readme.md", "readme.txt"]), None)
    if not readme_path:
        return None
        
    content = fetch_file_content(owner, repo, readme_path, token)
    if not content:
        return None

    # Parse and clean markdown to get introduction
    lines = content.splitlines()
    clean_lines = []
    for line in lines:
        line = line.strip()
        # Skip headers, lists, links, badges, or empty lines
        if not line:
            continue
        if line.startswith(("#", "-", "*", ">", "!", "[", "<")):
            continue
        # Remove markdown inline links/formatting
        line = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line)
        line = re.sub(r'[`*_]', '', line)
        clean_lines.append(line)
        if len(clean_lines) >= 2:
            break
            
    if clean_lines:
        return " ".join(clean_lines)
    return None

def analyze_repo_pipeline(
    repo_id: str,
    last_pushed_at: str,
    owner: str,
    repo: str,
    file_structure: List[Dict[str, Any]],
    token: str = None
) -> Dict[str, Any]:
    """
    Runs the full static repository parser pipeline, mapping caching logic automatically.
    """
    # 1. Return cached results if valid
    cached = get_cached_analysis(repo_id, last_pushed_at)
    if cached:
        print(f"Analysis Cache HIT for repository: {owner}/{repo}")
        return cached

    print(f"Analysis Cache MISS. Commencing static telemetry extraction for: {owner}/{repo}")

    # 2. Base structures
    technologies = []
    dependencies = []
    key_components = []
    api_surface = []
    code_patterns = []
    integration_points = []
    
    paths = [item.get("path", "") for item in file_structure]

    # Clean file extensions telemetry
    has_typescript = any(p.endswith((".ts", ".tsx")) for p in paths)
    has_javascript = any(p.endswith((".js", ".jsx")) for p in paths)
    has_python = any(p.endswith(".py") for p in paths)
    has_golang = any(p.endswith(".go") for p in paths)
    has_rust = any(p.endswith(".rs") for p in paths)
    has_java = any(p.endswith((".java", ".kt")) for p in paths)
    has_docker = any(p.lower().endswith("dockerfile") or p.lower().endswith("docker-compose.yml") for p in paths)
    has_ci = any(p.startswith(".github/workflows/") for p in paths)

    # 3. Technologies matching
    if has_typescript: technologies.append("TypeScript")
    elif has_javascript: technologies.append("JavaScript")
    if has_python: technologies.append("Python")
    if has_golang: technologies.append("Go")
    if has_rust: technologies.append("Rust")
    if has_java: technologies.append("Java/Kotlin")
    if has_docker: technologies.append("Docker")
    if has_ci: technologies.append("GitHub Actions")

    # DB and framework detectors
    detected_db = "Not detected"
    detected_frontend = "Not detected"
    detected_backend = "Not detected"
    detected_auth = "Not detected"
    detected_payment = "Not detected"

    # A. package.json parser
    package_json_path = next((p for p in paths if p.endswith("package.json")), None)
    if package_json_path:
        content = fetch_file_content(owner, repo, package_json_path, token)
        if content:
            try:
                data = json.loads(content)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                dependencies.extend(deps.keys())

                # Frontend mappings
                if "react" in deps:
                    technologies.append("React")
                    detected_frontend = "React SPA"
                if "vue" in deps:
                    technologies.append("Vue.js")
                    detected_frontend = "Vue SPA"
                if "next" in deps:
                    technologies.append("Next.js")
                    detected_frontend = "Next.js SSR Frontend"
                if "angular" in deps:
                    technologies.append("Angular")
                    detected_frontend = "Angular SPA"
                if "svelte" in deps:
                    technologies.append("Svelte")
                    detected_frontend = "Svelte SPA"

                # Backend mappings
                if "express" in deps:
                    technologies.append("Express.js")
                    detected_backend = "Express.js API Router"
                if "nestjs" in deps:
                    technologies.append("NestJS")
                    detected_backend = "NestJS Controller architecture"

                # Styling
                if "tailwindcss" in deps:
                    technologies.append("Tailwind CSS")
                if "bootstrap" in deps:
                    technologies.append("Bootstrap")

                # Build Tools
                if "vite" in deps:
                    technologies.append("Vite")
                if "webpack" in deps:
                    technologies.append("Webpack")

                # Databases ORM
                if "prisma" in deps:
                    detected_db = "Prisma ORM"
                    integration_points.append("Prisma Database Access")
                elif "sequelize" in deps:
                    detected_db = "Sequelize ORM"
                    integration_points.append("Sequelize Database Access")
                elif "mongoose" in deps:
                    detected_db = "MongoDB (Mongoose)"
                    integration_points.append("Mongoose MongoDB driver")
                elif "typeorm" in deps:
                    detected_db = "TypeORM"
                    integration_points.append("TypeORM Database Access")

                # Auth Mappings
                if "@okta/okta-react" in deps or "@okta/okta-auth-js" in deps:
                    detected_auth = "Okta Single Sign-On"
                    integration_points.append("Okta SSO Authentication")
                elif "auth0" in deps:
                    detected_auth = "Auth0 Authentication"
                    integration_points.append("Auth0 SSO Integration")
                elif "firebase" in deps:
                    detected_auth = "Firebase Auth"
                    integration_points.append("Firebase Services")

                # Integrations
                if "stripe" in deps:
                    detected_payment = "Stripe Payments"
                    integration_points.append("Stripe Payment Gateway")

            except Exception as e:
                print(f"Failed to parse package.json: {e}")

    # B. requirements.txt / pyproject.toml / Pipfile parser
    requirements_path = next((p for p in paths if p.endswith("requirements.txt")), None)
    if requirements_path:
        content = fetch_file_content(owner, repo, requirements_path, token)
        if content:
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    clean_dep = re.split(r"[<>=~]", line)[0].strip()
                    dependencies.append(clean_dep)
                    
                    if clean_dep.lower() == "fastapi":
                        technologies.append("FastAPI")
                        detected_backend = "FastAPI REST Server"
                    elif clean_dep.lower() == "django":
                        technologies.append("Django")
                        detected_backend = "Django MVC framework"
                    elif clean_dep.lower() == "flask":
                        technologies.append("Flask")
                        detected_backend = "Flask REST microservice"
                    elif clean_dep.lower() == "sqlalchemy":
                        detected_db = "SQLAlchemy ORM"
                        integration_points.append("SQLAlchemy ORM integration")
                    elif clean_dep.lower() == "tortoise-orm":
                        detected_db = "Tortoise ORM (Async)"
                    elif clean_dep.lower() == "pymongo":
                        detected_db = "MongoDB (PyMongo)"
                    elif clean_dep.lower() == "psycopg2":
                        detected_db = "PostgreSQL DB"

    # C. Maven pom.xml parser
    pom_path = next((p for p in paths if p.endswith("pom.xml")), None)
    if pom_path:
        content = fetch_file_content(owner, repo, pom_path, token)
        if content:
            technologies.append("Maven")
            # Extract dependencies
            artifacts = re.findall(r"<artifactId>([^<]+)</artifactId>", content)
            for a in artifacts:
                dependencies.append(a)
                if "spring-boot" in a:
                    technologies.append("Spring Boot")
                    detected_backend = "Spring Boot Java API"
                if "hibernate" in a:
                    detected_db = "Hibernate ORM"

    # D. Go go.mod parser
    go_mod_path = next((p for p in paths if p.endswith("go.mod")), None)
    if go_mod_path:
        content = fetch_file_content(owner, repo, go_mod_path, token)
        if content:
            technologies.append("Go Modules")
            requires = re.findall(r"^\s*([^\s]+)\s+v[0-9]", content, re.MULTILINE)
            for r in requires:
                dependencies.append(r)
                if "gin-gonic" in r:
                    technologies.append("Gin")
                    detected_backend = "Go Gin Engine"
                if "gorm" in r:
                    detected_db = "GORM ORM"

    # E. Cargo.toml parser
    cargo_path = next((p for p in paths if p.endswith("Cargo.toml")), None)
    if cargo_path:
        content = fetch_file_content(owner, repo, cargo_path, token)
        if content:
            technologies.append("Cargo")
            # Look for dependencies list
            dep_sections = re.findall(r"\[dependencies\](.*?)(\n\[|$)", content, re.DOTALL)
            if dep_sections:
                for line in dep_sections[0][0].splitlines():
                    if "=" in line:
                        dep_name = line.split("=")[0].strip()
                        dependencies.append(dep_name)

    # Standardize arrays
    technologies = sorted(list(set(technologies)))
    dependencies = sorted(list(set([d for d in dependencies if d])))[:25]

    # 4. Fetch README description
    project_purpose = extract_readme_description(owner, repo, paths, token)
    if not project_purpose:
        project_purpose = f"A codebase project named {repo} hosted on GitHub."

    # Build Architecture Overview
    flow_desc = "Not detected"
    if detected_frontend != "Not detected" and detected_backend != "Not detected":
        flow_desc = (
            f"Asynchronous HTTP REST API flow: Client actions trigger router components in "
            f"the {detected_frontend} frontend, which communicate via standard endpoints with the "
            f"{detected_backend} backend service. The backend queries database rows and redirects responses."
        )
    elif detected_frontend != "Not detected":
        flow_desc = f"Single Page client-rendered flow managed by {detected_frontend} views."
    elif detected_backend != "Not detected":
        flow_desc = f"REST/gRPC API service flow managed by {detected_backend} path controllers."

    arch_sections = []
    arch_sections.append(f"Description: {project_purpose}")
    arch_sections.append(f"Frontend: {detected_frontend}")
    arch_sections.append(f"Backend: {detected_backend}")
    arch_sections.append(f"Database: {detected_db}")
    if detected_auth != "Not detected":
        arch_sections.append(f"Authentication: {detected_auth}")
    if detected_payment != "Not detected":
        arch_sections.append(f"Payments: {detected_payment}")
    arch_sections.append(f"Main Data Flow: {flow_desc}")
    
    architecture_overview = " \n &bull; ".join(arch_sections)
    if not architecture_overview.strip():
        architecture_overview = None
    else:
        architecture_overview = "&bull; " + architecture_overview

    # 5. Key Components Extraction & Documentation
    component_patterns = [
        (r"src/components/([^/]+)\.tsx?$", "Visual Component interface"),
        (r"src/pages/([^/]+)\.tsx?$", "View page module"),
        (r"src/services/([^/]+)\.tsx?$", "Business logic services helper"),
        (r"backend/([^/]+)\.py$", "Backend service router module"),
        (r"app/controllers/([^/]+)\.go$", "Go request controller handler"),
        (r"app/models/([^/]+)\.go$", "Database schema representation schema"),
    ]

    for p in paths:
        for pattern, desc in component_patterns:
            match = re.search(pattern, p)
            if match:
                component_name = match.group(1)
                key_components.append(f"{p} ({desc})")
                break
        if len(key_components) >= 8:
            break

    # 6. API Route Telemetry Checking
    # Scan routing files
    router_paths = [
        p for p in paths 
        if p.endswith(("App.tsx", "main.py", "app.py", "routes.ts", "router.ts", "routes.go"))
    ]
    for rp in router_paths:
        code_content = fetch_file_content(owner, repo, rp, token)
        if code_content:
            # React Router paths
            rr_routes = re.findall(r'path=["\']([^"\']+)["\']', code_content)
            for r in rr_routes:
                if len(api_surface) < 12:
                    api_surface.append(f"Route: {r} (Frontend)")
            
            # FastAPI endpoints
            fastapi_routes = re.findall(r'@app\.(get|post|put|delete)\(["\']([^"\']+)["\']', code_content)
            for method, endpoint in fastapi_routes:
                if len(api_surface) < 12:
                    api_surface.append(f"Endpoint: {method.upper()} {endpoint} (FastAPI)")

    # 7. Code/Design Pattern Detection
    scan_files = [p for p in paths if p.endswith((".ts", ".tsx", ".py", ".go"))][:5]
    code_samples = ""
    for sf in scan_files:
        code_content = fetch_file_content(owner, repo, sf, token)
        if code_content:
            code_samples += "\n" + code_content

    if code_samples:
        if "useContext" in code_samples:
            code_patterns.append("Context Global State Management")
        if "useState" in code_samples or "useEffect" in code_samples:
            code_patterns.append("React Functional Component Lifecycle Hooks")
        if "async/await" in code_samples:
            code_patterns.append("Asynchronous/Non-blocking I/O Promise operations")
        if "declarative_base()" in code_samples or "declarative_base" in code_samples:
            code_patterns.append("SQLAlchemy ORM Declarative Table mapping")
        if "middleware" in code_samples.lower():
            code_patterns.append("Interweaving Request Middleware Interceptor")
        if "gorm.Model" in code_samples:
            code_patterns.append("Go GORM model lifecycle patterns")

    # Docker Mappings
    if any(p.lower().endswith("dockerfile") for p in paths):
        integration_points.append("Docker Container Engine")
    if any(p.lower().endswith("docker-compose.yml") for p in paths):
        integration_points.append("Docker-Compose Orchestrator")

    # Fallback to "Not detected" if arrays are empty
    dependencies = sorted(list(set(dependencies)))
    key_components = sorted(list(set(key_components)))
    api_surface = sorted(list(set(api_surface)))
    code_patterns = sorted(list(set(code_patterns)))
    integration_points = sorted(list(set(integration_points)))

    analysis = {
        "technologies": technologies,
        "architecture_overview": architecture_overview,
        "key_components": key_components,
        "api_surface": api_surface,
        "code_patterns": code_patterns,
        "integration_points": integration_points,
        "dependencies": dependencies
    }

    # Save to disk cache
    save_analysis_cache(repo_id, last_pushed_at, analysis)

    return analysis
