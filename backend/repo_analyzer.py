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

def load_raw_cache(repo_id: str) -> Optional[Dict[str, Any]]:
    """
    Reads the raw cache file from disk if it exists.
    """
    ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"{repo_id}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def get_cached_analysis(repo_id: str, last_pushed_at: str) -> Optional[Dict[str, Any]]:
    """
    Checks if a cached analysis file exists on disk and is up to date.
    If the cached analysis contains generic fallbacks or is an older version (< 3),
    it automatically invalidates the cache to force a correct analysis.
    """
    ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"{repo_id}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                
                # Check for stale cache version
                if cached_data.get("cache_version", 0) < 4:
                    print(f"Self-healing: Cache version outdated for {repo_id}. Invalidating cache.")
                    return None
                
                if cached_data.get("last_pushed_at") == last_pushed_at:
                    analysis = cached_data.get("analysis")
                    if analysis:
                        overview = analysis.get("overview", "")
                        # Self-healing: if overview contains the old generic owner template or HTML tags, invalidate cache
                        if overview and ("is a software project owned by" in overview or "This repository," in overview or any(tag in overview for tag in ["<strong>", "<a", "-->", "on Github", "href="])):
                            print(f"Self-healing: Cached overview is generic/raw for {repo_id}. Invalidating cache.")
                            return None

                    # Self-healing: if cache has empty analysis details but there are files, trigger re-analysis
                    if analysis and not analysis.get("key_components_details"):
                        file_struct = cached_data.get("file_structure", [])
                        if len(file_struct) > 10:  # there are actually files in this repo
                            print(f"Self-healing: Cache exists but has empty analysis details for {repo_id}. Invalidating cache.")
                            return None

                    return analysis
        except Exception as e:
            print(f"Failed to read analysis cache for {repo_id}: {e}")
    return None

def save_analysis_cache(repo_id: str, last_pushed_at: str, analysis: Dict[str, Any], extra_data: Dict[str, Any] = None):
    """
    Saves the analyzed telemetry results and extra live data to disk cache.
    """
    ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"{repo_id}.json")
    existing_data = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            pass

    existing_data.update({
        "last_pushed_at": last_pushed_at,
        "analysis": analysis,
        "cache_version": 4
    })

    if extra_data:
        for k, v in extra_data.items():
            if v is not None:
                existing_data[k] = v

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2)
    except Exception as e:
        print(f"Failed to save analysis cache for {repo_id}: {e}")


def fetch_file_content(owner: str, repo: str, path: str, token: str = None, branch: str = "main") -> Optional[str]:
    """
    Downloads file content from GitHub REST API, falling back to raw.githubusercontent.com on rate limits.
    """
    branches_to_try = [branch]
    for b in ["main", "master"]:
        if b not in branches_to_try:
            branches_to_try.append(b)

    for b in branches_to_try:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={b}"
        try:
            res = requests.get(url, headers=get_headers(token), timeout=10)
            if res.status_code == 200:
                data = res.json()
                content_b64 = data.get("content", "")
                if content_b64:
                    clean_b64 = content_b64.replace("\n", "").replace("\r", "")
                    content_bytes = base64.b64decode(clean_b64)
                    return content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            pass

        try:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{b}/{path}"
            res = requests.get(raw_url, timeout=10)
            if res.status_code == 200 and res.text:
                return res.text
        except Exception:
            pass

    return None


def extract_readme_insights(owner: str, repo: str, paths: List[str], token: str = None, branch: str = "main", repo_description: str = None) -> Dict[str, Any]:
    """
    Downloads README.md and extracts a concise plain-text summary (2-4 sentences) and section headers.
    """
    readme_path = next((p for p in paths if p.lower() in ["readme.md", "readme.txt", "readme", "readme.rst"]), None)
    
    clean_headers = []
    content = None
    if readme_path:
        content = fetch_file_content(owner, repo, readme_path, token, branch=branch)

    if not content:
        # Direct GitHub fetch fallback if paths was empty or didn't list README
        for fallback_file in ["README.md", "readme.md", "README", "readme.txt"]:
            content = fetch_file_content(owner, repo, fallback_file, token, branch=branch)
            if content:
                readme_path = fallback_file
                break

    summary = None
    has_readme = False
    
    if content:
        has_readme = True
        # Extract headers for telemetry
        headers = re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)
        clean_headers = [h.strip() for h in headers if len(h.strip()) < 50][:8]

        # 1. Clean HTML comments and raw tags
        cleaned_content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        cleaned_content = re.sub(r'<img[^>]*>', '', cleaned_content)
        cleaned_content = re.sub(r'<a\b[^>]*>(.*?)</a>', r'\1', cleaned_content, flags=re.DOTALL)
        cleaned_content = re.sub(r'</?(?:strong|b|em|i|span|p|div|h\d)\b[^>]*>', '', cleaned_content, flags=re.IGNORECASE)
        cleaned_content = re.sub(r'<[^>]+>', '', cleaned_content)

        lines = cleaned_content.splitlines()
        intro_sentences = []
        feature_terms = []
        
        in_code_block = False
        in_skip_section = False
        
        for line in lines:
            line_strip = line.strip()
            if not line_strip:
                continue
            if line_strip.startswith(("```", ">")):
                if line_strip.startswith("```"):
                    in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            # Ignore markdown table rows
            if "|" in line_strip:
                continue
                
            # Header check
            if line_strip.startswith("#"):
                header_text = re.sub(r'^#+\s*', '', line_strip)
                header_clean = re.sub(r'[^\w\s\-\&]', '', header_text).strip()
                header_lower = header_clean.lower()
                
                # Check if we enter a non-feature section to skip
                if any(skip_kw in header_lower for skip_kw in ["tech stack", "architecture", "setup", "prerequisites", "screens", "commit", "license", "design system", "steps", "first launch", "notes", "algorithm"]):
                    in_skip_section = True
                    continue
                else:
                    in_skip_section = False
                    
                # Only h2/h3 headers (starting with ##) should be considered as sub-features
                if line_strip.startswith("##"):
                    feat_header = re.sub(r'^\d+[\.\)]\s*', '', header_clean)
                    feat_header = re.sub(r'^\d+\s+', '', feat_header).strip()
                    if 3 < len(feat_header) < 40 and feat_header.lower() not in ["features", "overview", "about", repo.lower()]:
                        feature_terms.append(feat_header)
                continue

            if in_skip_section:
                continue

            if line_strip.startswith(("[!", "![", "http://", "https://")):
                continue

            # List item check for features
            bullet_match = re.match(r'^[\s\-\*\+]{1,4}(.*)$', line_strip)
            if bullet_match:
                bullet_content = bullet_match.group(1).strip()
                bold_match = re.match(r'^\*\*([^*]+)\*\*\s*(?::|\s-\s|\s\u2013\s)', bullet_content)
                if bold_match:
                    term = bold_match.group(1).strip()
                    if 3 < len(term) < 40:
                        feature_terms.append(term)
                else:
                    clean_bullet = re.sub(r'[`*_~#]', '', bullet_content)
                    general_match = re.match(r'^([^:\-\n\(\)]+)(?::|\s-\s)', clean_bullet)
                    if general_match:
                        term = general_match.group(1).strip()
                        if 3 < len(term) < 40 and not term.lower().startswith("http"):
                            feature_terms.append(term)
                continue

            # Prose text line (introduction candidate)
            line_clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line_strip)
            line_clean = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', line_clean)
            line_clean = re.sub(r'[`*_~#]', '', line_clean)
            line_clean = re.sub(r'[^\x00-\x7F]+', ' ', line_clean)

            sentences = re.split(r'(?<=[.!?])\s+', line_clean)
            for s in sentences:
                s_clean = s.strip()
                if len(s_clean) > 20 and not s_clean.startswith(("http://", "https://", "[!", ">")):
                    s_clean = re.sub(r'\s+', ' ', s_clean)
                    if s_clean not in intro_sentences:
                        intro_sentences.append(s_clean)

        # Build introduction
        intro_text = " ".join(intro_sentences[:2]) if intro_sentences else ""
        
        # Build features sentence
        features_text = ""
        if feature_terms:
            seen = set()
            unique_features = []
            for f in feature_terms:
                f_clean = re.sub(r'[^\w\s\-\&]', '', f).strip()
                f_clean = re.sub(r'^\d+\s*', '', f_clean).strip()
                f_lower = f_clean.lower()
                if f_lower not in seen and len(f_clean) > 3 and not any(kw in f_lower for kw in ["features", "overview", "app", "category", "categories", repo.lower()]):
                    seen.add(f_lower)
                    unique_features.append(f_clean)
                    
            unique_features = unique_features[:6]
            if unique_features:
                if len(unique_features) == 1:
                    features_str = unique_features[0]
                elif len(unique_features) == 2:
                    features_str = f"{unique_features[0]} and {unique_features[1]}"
                else:
                    features_str = ", ".join(unique_features[:-1]) + f", and {unique_features[-1]}"
                
                features_text = f"Key features include {features_str}."

        if intro_text and features_text:
            summary = f"{intro_text} {features_text}"
        elif intro_text:
            summary = intro_text
        elif features_text:
            summary = features_text

        if summary and not summary.endswith((".", "!", "?")):
            summary += "."

    if summary:
        summary = re.sub(r'<[^>]+>', '', summary)
        summary = re.sub(r'[`*_~#]', '', summary)
        summary = re.sub(r'\s+', ' ', summary).strip()

    return {
        "has_readme": has_readme,
        "summary": summary,
        "sections": clean_headers
    }

def analyze_repo_pipeline(
    repo_id: str,
    last_pushed_at: str,
    owner: str,
    repo: str,
    file_structure: List[Dict[str, Any]],
    token: str = None,
    force_reanalyze: bool = False,
    branch: str = "main",
    commits: List[Dict[str, Any]] = None,
    branches: List[Dict[str, Any]] = None,
    contributors: List[Dict[str, Any]] = None,
    issues: List[Dict[str, Any]] = None,
    pull_requests: List[Dict[str, Any]] = None,
    languages: Dict[str, float] = None,
    total_commits: int = None,
    repo_description: str = None
) -> Dict[str, Any]:
    """
    Runs the full static repository parser pipeline, extracting deep source code telemetry,
    key components, API endpoints, code patterns, dependencies, integrations, and architecture.
    """
    # 1. Return cached results if valid and not forcing re-analysis
    if not force_reanalyze:
        cached = get_cached_analysis(repo_id, last_pushed_at)
        if cached:
            print(f"Analysis Cache HIT for repository: {owner}/{repo}")
            return cached

    print(f"Analysis Execution. Commencing static telemetry extraction for: {owner}/{repo}")

    # Ensure file_structure is hydrated recursively if missing or empty
    if not file_structure:
        try:
            from github_service import fetch_repo_tree
            file_structure = fetch_repo_tree(owner, repo, branch, token=token)
        except Exception as fe:
            print(f"Failed hydrating file structure for {owner}/{repo}: {fe}")
            file_structure = []

    paths = [item.get("path", "") for item in file_structure if item.get("path")]

    # Base telemetry data structures
    technologies = []
    dependencies = []
    dependencies_details = []
    key_components = []
    key_components_details = []
    api_surface = []
    api_surface_details = []
    code_patterns = []
    code_patterns_details = []
    integration_points = []
    integration_points_details = []
    build_deployment_config = []
    database_technologies = []
    external_services = []

    detected_db = "Not detected"
    detected_frontend = "Not detected"
    detected_backend = "Not detected"
    detected_auth = "Not detected"
    detected_payment = "Not detected"

    # Integrate language telemetry into technologies list
    if languages:
        for lang, pct in languages.items():
            if pct >= 2.0 and lang not in technologies:
                technologies.append(lang)

    # Analyze branch names for branching model
    if branches:
        branch_names = [b.get("name") for b in branches if b.get("name")]
        if "develop" in branch_names and "main" in branch_names:
            build_deployment_config.append("Git Flow Branching (main, develop)")
        elif len(branch_names) > 3:
            build_deployment_config.append("Feature-Branch Development Workflow")

    # Analyze commit history messages for Conventional Commit patterns
    if commits:
        msg_lower = [c.get("message", "").lower() for c in commits if c.get("message")]
        feat_cnt = sum(1 for m in msg_lower if m.startswith("feat"))
        fix_cnt = sum(1 for m in msg_lower if m.startswith("fix"))
        chore_cnt = sum(1 for m in msg_lower if m.startswith("chore") or m.startswith("docs") or m.startswith("refactor"))
        if feat_cnt + fix_cnt + chore_cnt > 1:
            code_patterns.append("Conventional Commit Specification")
            code_patterns_details.append({
                "pattern_name": "Conventional Commits Specification",
                "category": "Development Lifecycle",
                "description": "Standardized commit prefixing (feat, fix, chore, docs) for automated changelogs and semver release versioning.",
                "source_files": ["Git Commit History"],
                "reusable_approach": "Enforces structured message formats to streamline release management."
            })

    # ==========================================
    # 1. PARSE DEPENDENCY MANIFESTS ACROSS TREE
    # ==========================================
    try:
        # A. package.json manifests (Root & Subfolders)
        pkg_paths = [p for p in paths if p.endswith("package.json")]
        for pkg_path in pkg_paths:
            content = fetch_file_content(owner, repo, pkg_path, token, branch=branch)
            if content:
                try:
                    data = json.loads(content)
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    for d_name, d_ver in deps.items():
                        if d_name not in dependencies:
                            dependencies.append(d_name)
                            ecosystem = "npm"
                            purpose = "JavaScript/TypeScript package dependency"
                            d_lower = d_name.lower()
                            if "react" in d_lower: purpose = "Frontend UI library for component views"
                            elif "fastapi" in d_lower: purpose = "High-performance Python Web framework"
                            elif "express" in d_lower: purpose = "Node.js REST API router framework"
                            elif "sqlalchemy" in d_lower: purpose = "Python SQL toolkit and Object Relational Mapper"
                            elif "vite" in d_lower: purpose = "Next-generation frontend tooling bundler"
                            elif "tailwindcss" in d_lower: purpose = "Utility-first CSS styling framework"
                            elif "okta" in d_lower: purpose = "Enterprise identity & Single Sign-On SDK"
                            elif "prisma" in d_lower: purpose = "Next-generation Node.js and TypeScript ORM"
                            elif "cypress" in d_lower: purpose = "End-to-end web test automation engine"

                            dependencies_details.append({
                                "package": d_name,
                                "version": str(d_ver) if d_ver else "Manifest defined",
                                "ecosystem": ecosystem,
                                "purpose": purpose,
                                "relationships": pkg_path
                            })

                    # Framework & Service Mapping
                    if "react" in deps and "React" not in technologies:
                        technologies.append("React")
                        detected_frontend = "React SPA"
                    if "vue" in deps and "Vue.js" not in technologies:
                        technologies.append("Vue.js")
                        detected_frontend = "Vue SPA"
                    if "next" in deps and "Next.js" not in technologies:
                        technologies.append("Next.js")
                        detected_frontend = "Next.js SSR Frontend"
                    if "express" in deps and "Express.js" not in technologies:
                        technologies.append("Express.js")
                        detected_backend = "Express.js API Router"
                    if "nestjs" in deps or "@nestjs/core" in deps:
                        technologies.append("NestJS")
                        detected_backend = "NestJS Controller Architecture"
                    if "tailwindcss" in deps and "Tailwind CSS" not in technologies:
                        technologies.append("Tailwind CSS")
                    if "vite" in deps and "Vite" not in technologies:
                        technologies.append("Vite")
                        build_deployment_config.append("Vite Bundler")
                    if "prisma" in deps:
                        detected_db = "Prisma ORM"
                        database_technologies.append("Prisma ORM")
                        integration_points.append("Prisma Database Access")
                    elif "mongoose" in deps:
                        detected_db = "MongoDB (Mongoose)"
                        database_technologies.append("MongoDB (Mongoose)")
                        integration_points.append("Mongoose MongoDB driver")
                    elif "sequelize" in deps:
                        detected_db = "Sequelize ORM"
                        database_technologies.append("Sequelize ORM")
                    if "stripe" in deps or "@stripe/stripe-js" in deps:
                        detected_payment = "Stripe Payments"
                        external_services.append("Stripe Payment Gateway")
                        integration_points.append("Stripe Payment Gateway")
                    if "cypress" in deps:
                        technologies.append("Cypress E2E")
                        integration_points.append("Cypress Automation Framework")

                except Exception as pe:
                    print(f"Error parsing {pkg_path}: {pe}")

        # B. Python dependency manifests
        req_paths = [p for p in paths if p.endswith(("requirements.txt", "Pipfile", "pyproject.toml"))]
        for req_path in req_paths:
            content = fetch_file_content(owner, repo, req_path, token, branch=branch)
            if content:
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("["):
                        clean_dep = re.split(r"[<>=~]", line)[0].strip()
                        if clean_dep and clean_dep not in dependencies:
                            dependencies.append(clean_dep)
                            dependencies_details.append({
                                "package": clean_dep,
                                "version": "Manifest defined",
                                "ecosystem": "PyPI",
                                "purpose": "Python package dependency",
                                "relationships": req_path
                            })
                            c_lower = clean_dep.lower()
                            if c_lower == "fastapi":
                                technologies.append("FastAPI")
                                detected_backend = "FastAPI REST Server"
                            elif c_lower == "django":
                                technologies.append("Django")
                                detected_backend = "Django MVC Framework"
                            elif c_lower == "flask":
                                technologies.append("Flask")
                                detected_backend = "Flask REST Microservice"
                            elif c_lower in ["sqlalchemy", "alembic"]:
                                detected_db = "SQLAlchemy ORM"
                                database_technologies.append("SQLAlchemy ORM")

        # C. Flutter / Dart pubspec.yaml
        pub_paths = [p for p in paths if p.endswith("pubspec.yaml")]
        for pub_path in pub_paths:
            content = fetch_file_content(owner, repo, pub_path, token, branch=branch)
            if content:
                technologies.extend(["Flutter", "Dart"])
                detected_frontend = "Flutter Mobile App"
                in_deps = False
                for line in content.splitlines():
                    line_s = line.strip()
                    if line_s.startswith("dependencies:"):
                        in_deps = True
                        continue
                    elif line_s.startswith(("dev_dependencies:", "flutter:", "environment:", "flutter_test:")):
                        in_deps = False
                        continue
                    if in_deps and ":" in line_s and not line_s.startswith("#"):
                        dep_name = line_s.split(":")[0].strip()
                        if dep_name and dep_name not in ["flutter", "sdk"] and dep_name not in dependencies:
                            dependencies.append(dep_name)
                            dependencies_details.append({
                                "package": dep_name,
                                "version": "Pubspec defined",
                                "ecosystem": "pub.dev",
                                "purpose": "Flutter / Dart package dependency",
                                "relationships": pub_path
                            })
                            if "hive" in dep_name:
                                detected_db = "Hive Offline DB"
                                database_technologies.append("Hive Local Database")
                            elif "firebase" in dep_name:
                                detected_auth = "Firebase Auth"
                                external_services.append("Firebase Services")

        # D. Maven pom.xml & Gradle
        java_paths = [p for p in paths if p.endswith(("pom.xml", "build.gradle"))]
        for java_path in java_paths:
            content = fetch_file_content(owner, repo, java_path, token, branch=branch)
            if content:
                technologies.append("Java")
                build_deployment_config.append("Maven/Gradle Build System")
                artifacts = re.findall(r"<artifactId>([^<]+)</artifactId>", content) or re.findall(r"implementation\s+['\"]([^'\"]+)['\"]", content)
                for a in artifacts:
                    if a not in dependencies:
                        dependencies.append(a)
                        dependencies_details.append({
                            "package": a,
                            "version": "Build defined",
                            "ecosystem": "Maven/Gradle",
                            "purpose": "Java/Kotlin framework dependency",
                            "relationships": java_path
                        })
                        if "spring-boot" in a:
                            technologies.append("Spring Boot")
                            detected_backend = "Spring Boot Java API"

        # E. Go go.mod
        go_paths = [p for p in paths if p.endswith("go.mod")]
        for go_path in go_paths:
            content = fetch_file_content(owner, repo, go_path, token, branch=branch)
            if content:
                technologies.append("Go Modules")
                build_deployment_config.append("Go Module System")
                requires = re.findall(r"^\s*([^\s]+)\s+v[0-9]", content, re.MULTILINE)
                for r_dep in requires:
                    if r_dep not in dependencies:
                        dependencies.append(r_dep)
                        dependencies_details.append({
                            "package": r_dep,
                            "version": "go.mod defined",
                            "ecosystem": "Go Modules",
                            "purpose": "Go package module dependency",
                            "relationships": go_path
                        })
                        if "gin-gonic" in r_dep:
                            technologies.append("Gin")
                            detected_backend = "Go Gin Engine"

    except Exception as me:
        print(f"Error scanning dependency manifests: {me}")

    # ==========================================
    # 2. KEY COMPONENTS EXTRACTION & MAPPING
    # ==========================================
    try:
        # Filter out binary, generated, and vendor files
        code_paths = [
            p for p in paths
            if not any(skip in p for skip in ["node_modules/", "dist/", "build/", ".git/", ".lock", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"])
            and not p.endswith((".g.dart", ".freezed.dart", ".min.js", ".min.css"))
            and p.endswith((".js", ".jsx", ".ts", ".tsx", ".py", ".java", ".kt", ".dart", ".go", ".cpp", ".c", ".cs", ".php", ".rb", ".rs", ".swift", ".vue", ".svelte", ".html", ".css", ".json", ".yaml"))
        ]

        for p in code_paths:
            p_lower = p.lower()
            comp_name = os.path.basename(p)
            comp_clean = os.path.splitext(comp_name)[0]
            comp_title = comp_clean.replace("_", " ").replace("-", " ").title()

            role = None
            purpose = None

            # Category matching
            if any(kw in p_lower for kw in ["/components/", "/widgets/", "/views/", "/screens/", "/pages/", "component", "screen", "widget"]):
                role = "UI Component View"
                purpose = f"Renders visual user interface component in {p}."
            elif any(kw in p_lower for kw in ["/controllers/", "/routers/", "/routes/", "/api/", "/endpoints/", "/handlers/", "controller", "router", "route", "endpoint"]):
                role = "API Router & Controller"
                purpose = f"Processes HTTP requests and handles endpoint routing logic in {p}."
            elif any(kw in p_lower for kw in ["/models/", "/entities/", "/schema/", "/dto/", "/db/", "/repository/", "/store/", "model", "schema", "entity"]):
                role = "Data Entity & Model"
                purpose = f"Defines data structure schemas and persistence mapping in {p}."
            elif any(kw in p_lower for kw in ["/services/", "/utils/", "/helpers/", "/providers/", "/context/", "/hooks/", "/middleware/", "/config/", "service", "provider", "context", "helper"]):
                role = "Service & Business Logic Module"
                purpose = f"Encapsulates core business logic, utility functions, or state management in {p}."
            elif comp_name in ["main.py", "App.tsx", "index.ts", "server.js", "app.js", "main.dart", "index.js", "App.js", "main.go", "Application.java"]:
                role = "Core Application Entrypoint"
                purpose = f"Main application entrypoint and initialization module in {p}."

            if role:
                component_key = f"{p} ({role})"
                if component_key not in key_components and len(key_components_details) < 25:
                    key_components.append(component_key)
                    key_components_details.append({
                        "path": p,
                        "name": comp_title,
                        "role": role,
                        "purpose": purpose,
                        "relationships": [os.path.dirname(p)] if os.path.dirname(p) else ["root"]
                    })

        # Fallback if no components matched strict categories: use primary source code files
        if not key_components_details and code_paths:
            for p in code_paths[:15]:
                comp_name = os.path.basename(p)
                comp_clean = os.path.splitext(comp_name)[0]
                comp_title = comp_clean.replace("_", " ").replace("-", " ").title()
                role = "Source Code Module"
                purpose = f"Source code implementation file in {p}."
                key_components.append(f"{p} ({role})")
                key_components_details.append({
                    "path": p,
                    "name": comp_title,
                    "role": role,
                    "purpose": purpose,
                    "relationships": [os.path.dirname(p)] if os.path.dirname(p) else ["root"]
                })

        if not key_components:
            key_components.append("None detected")

    except Exception as ke:
        print(f"Error extracting key components: {ke}")
        if not key_components:
            key_components.append("None detected")

    # ==========================================
    # 3. DEEP API SURFACE ROUTE EXTRACTION
    # ==========================================
    try:
        router_candidate_files = [
            p for p in paths 
            if p.endswith((".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".java", ".dart", ".cs"))
            and not any(skip in p for skip in ["node_modules/", "dist/", "build/"])
            and (
                any(kw in p.lower() for kw in ["app", "main", "server", "router", "route", "controller", "api", "handler", "endpoint", "service"])
                or p.count("/") <= 2
            )
        ][:20]

        for rp in router_candidate_files:
            code_content = fetch_file_content(owner, repo, rp, token, branch=branch)
            if code_content:
                # React Router / Client Routes
                rr_routes = re.findall(r'path=["\']([^"\']+)["\']', code_content)
                for r in rr_routes:
                    if len(api_surface_details) < 25 and not r.startswith("http"):
                        api_entry = f"Route: {r} (Frontend)"
                        if api_entry not in api_surface:
                            api_surface.append(api_entry)
                            api_surface_details.append({
                                "method": "ROUTE",
                                "endpoint": r,
                                "description": f"Client-side view route defined in {rp}",
                                "source_file": rp,
                                "parameters": [p_param for p_param in ["id", "projectId", "repositoryId"] if ":" in r or "{" in r]
                            })

                # FastAPI / Flask / Django Endpoints
                py_routes = re.findall(r'@(?:app|router|api)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', code_content, re.IGNORECASE)
                for method, endpoint in py_routes:
                    if len(api_surface_details) < 25:
                        api_entry = f"Endpoint: {method.upper()} {endpoint} (REST API)"
                        if api_entry not in api_surface:
                            api_surface.append(api_entry)
                            api_surface_details.append({
                                "method": method.upper(),
                                "endpoint": endpoint,
                                "description": f"REST API handler endpoint serving data for {endpoint}",
                                "source_file": rp,
                                "parameters": [p_param for p_param in ["projectId", "repositoryId", "id", "user_id"] if p_param in endpoint or "{" in endpoint]
                            })

                # Express / NestJS Endpoints
                node_routes = re.findall(r'(?:app|router)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', code_content)
                for method, endpoint in node_routes:
                    if len(api_surface_details) < 25:
                        api_entry = f"Endpoint: {method.upper()} {endpoint} (Express/Node)"
                        if api_entry not in api_surface:
                            api_surface.append(api_entry)
                            api_surface_details.append({
                                "method": method.upper(),
                                "endpoint": endpoint,
                                "description": f"Node.js API handler endpoint serving data for {endpoint}",
                                "source_file": rp,
                                "parameters": [p_param for p_param in ["id", "userId", "projectId"] if ":" in endpoint]
                            })

                # Dart / Flutter / HTTP Client Service Calls
                if rp.endswith(".dart"):
                    http_calls = re.findall(r'(?:http|client|Dio|dio)\.(get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']', code_content)
                    for method, endpoint in http_calls:
                        if len(api_surface_details) < 25:
                            api_entry = f"Client API: {method.upper()} {endpoint}"
                            if api_entry not in api_surface:
                                api_surface.append(api_entry)
                                api_surface_details.append({
                                    "method": method.upper(),
                                    "endpoint": endpoint,
                                    "description": f"HTTP network API call executed from {rp}",
                                    "source_file": rp,
                                    "parameters": []
                                })

        if not api_surface:
            api_surface.append("None detected")

    except Exception as ae:
        print(f"Error extracting API surface: {ae}")
        if not api_surface:
            api_surface.append("None detected")

    # ==========================================
    # 4. CODE PATTERNS EXTRACTION
    # ==========================================
    try:
        scan_files = [
            p for p in paths
            if p.endswith((".ts", ".tsx", ".py", ".go", ".dart", ".java", ".kt", ".js", ".jsx"))
            and not any(skip in p for skip in ["node_modules/", "dist/", "build/"])
            and not p.endswith(".g.dart")
        ][:15]

        code_samples = ""
        sample_file_map = {}
        for sf in scan_files:
            content = fetch_file_content(owner, repo, sf, token, branch=branch)
            if content:
                code_samples += f"\n--- {sf} ---\n" + content
                sample_file_map[sf] = content

        if code_samples:
            if any(kw in code_samples for kw in ["useState", "useEffect", "useContext"]):
                code_patterns.append("React Hooks Component Lifecycle")
                code_patterns_details.append({
                    "pattern_name": "Functional State & Lifecycle Management",
                    "category": "State Management",
                    "description": "Uses React functional hooks (useState, useEffect, useContext) for local and global state handling.",
                    "source_files": [sf for sf, c in sample_file_map.items() if any(kw in c for kw in ["useState", "useEffect"])],
                    "reusable_approach": "Encapsulates reactive view logic inside functional components."
                })
            if any(kw in code_samples.lower() for kw in ["riverpod", "ref.watch", "stateprovider", "changenotifier"]):
                code_patterns.append("Reactive State Management & Provider Pattern")
                code_patterns_details.append({
                    "pattern_name": "Declarative Reactive State Management",
                    "category": "State Management",
                    "description": "Uses compile-safe state providers (Riverpod/Provider) for decoupled state synchronization.",
                    "source_files": [sf for sf in scan_files if sf.endswith(".dart")],
                    "reusable_approach": "Decouples application state logic completely from visual UI widgets."
                })
            if any(kw in code_samples for kw in ["SQLAlchemy", "prisma", "mongoose", "sequelize", "typeorm", "Hive", "gorm"]):
                code_patterns.append("Object-Relational Mapping (ORM) Persistence")
                code_patterns_details.append({
                    "pattern_name": "Data Mapper ORM & Database Persistence",
                    "category": "Data Access & Architecture",
                    "description": "Utilizes object-relational mapping frameworks for structured entity persistence and queries.",
                    "source_files": [sf for sf in scan_files if any(kw in sf.lower() for kw in ["model", "entity", "schema", "db"])],
                    "reusable_approach": "Abstracts SQL database queries into typed object models."
                })
            if "async" in code_samples or "await" in code_samples or "Future<" in code_samples:
                code_patterns.append("Non-blocking Asynchronous I/O")
                code_patterns_details.append({
                    "pattern_name": "Asynchronous Non-blocking Execution",
                    "category": "Concurrency & I/O",
                    "description": "Utilizes async/await futures and non-blocking I/O operations for REST requests and database operations.",
                    "source_files": scan_files[:4],
                    "reusable_approach": "Prevents event-loop blocking during network and disk operations."
                })
            if "Depends(" in code_samples or "@Injectable" in code_samples or "@Autowired" in code_samples:
                code_patterns.append("Dependency Injection Architecture")
                code_patterns_details.append({
                    "pattern_name": "Dependency Injection & Modular Inversion",
                    "category": "Architecture",
                    "description": "Injects database sessions and services dynamically into request controllers.",
                    "source_files": [sf for sf, c in sample_file_map.items() if "Depends(" in c or "@Injectable" in c],
                    "reusable_approach": "Decouples connection lifecycle management from controller handlers."
                })
            if any(kw in code_samples for kw in ["try:", "catch", "HTTPException"]):
                code_patterns.append("Centralized Exception Guarding")
                code_patterns_details.append({
                    "pattern_name": "Structured Exception Guarding",
                    "category": "Error Handling",
                    "description": "Wraps external API communications and database sessions in try/except guards returning standard error payloads.",
                    "source_files": scan_files[:5],
                    "reusable_approach": "Ensures clean status codes and structured diagnostic error messages."
                })

        if not code_patterns:
            code_patterns.append("None detected")

    except Exception as cpe:
        print(f"Error extracting code patterns: {cpe}")
        if not code_patterns:
            code_patterns.append("None detected")

    # ==========================================
    # 5. INTEGRATION POINTS & EXTERNAL SERVICES
    # ==========================================
    try:
        if any(p.lower().endswith("dockerfile") for p in paths):
            integration_points.append("Docker Container Runtime Engine")
            integration_points_details.append({
                "service_name": "Docker Engine",
                "integration_type": "Containerization & Runtime",
                "direction": "Outbound",
                "file_config": "Dockerfile",
                "purpose": "Package application logic into reproducible container runtime images."
            })
        if any(p.lower().endswith("docker-compose.yml") for p in paths):
            integration_points.append("Docker-Compose Service Orchestrator")
            integration_points_details.append({
                "service_name": "Docker Compose",
                "integration_type": "Container Orchestration",
                "direction": "Bi-directional",
                "file_config": "docker-compose.yml",
                "purpose": "Orchestrates multi-container development environment services."
            })
        if any(p.startswith(".github/workflows/") for p in paths):
            integration_points.append("GitHub Actions CI/CD Pipeline")
            integration_points_details.append({
                "service_name": "GitHub Actions",
                "integration_type": "CI/CD Automation",
                "direction": "Outbound",
                "file_config": ".github/workflows",
                "purpose": "Automated build, test, and continuous integration workflows."
            })

        if not integration_points:
            integration_points.append("None detected")

    except Exception as ie:
        print(f"Error extracting integration points: {ie}")
        if not integration_points:
            integration_points.append("None detected")

    # Clean duplicates
    dependencies = sorted(list(set([d for d in dependencies if d])))[:30]
    key_components = sorted(list(set([k for k in key_components if k])))
    api_surface = sorted(list(set([a for a in api_surface if a])))
    code_patterns = sorted(list(set([c for c in code_patterns if c])))
    integration_points = sorted(list(set([i for i in integration_points if i])))

    # ==========================================
    # 6. FETCH README & ARCHITECTURE OVERVIEW
    # ==========================================
    readme_insights = extract_readme_insights(owner, repo, paths, token, branch=branch, repo_description=repo_description)
    project_purpose = readme_insights.get("summary")
    
    if project_purpose:
        project_purpose = re.sub(r'<[^>]+>', '', project_purpose)
        project_purpose = re.sub(r'[`*_~#]', '', project_purpose).strip()

    if not project_purpose:
        desc_sentences = []
        if repo_description:
            clean_desc = re.sub(r'<[^>]+>', '', repo_description)
            clean_desc = re.sub(r'[`*_~#]', '', clean_desc).strip()
            if clean_desc:
                if not clean_desc.endswith((".", "!", "?")):
                    clean_desc += "."
                desc_sentences.append(clean_desc)
        else:
            desc_sentences.append(f"This repository, {repo}, is a software project owned by {owner}.")
            
        if languages:
            top_langs = sorted(languages.keys(), key=lambda k: languages[k], reverse=True)[:3]
            desc_sentences.append(f"It is primarily developed using {', '.join(top_langs)}.")
        if technologies:
            desc_sentences.append(f"The project leverages key technologies including {', '.join(technologies[:5])}.")
        project_purpose = " ".join(desc_sentences)

    # Construct System Data Flow & Architecture Overview
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
    if project_purpose:
        arch_sections.append(f"- **Repository Purpose**: {project_purpose}")
    arch_sections.append(f"- **Frontend Tier**: {detected_frontend}")
    arch_sections.append(f"- **Backend Tier**: {detected_backend}")
    arch_sections.append(f"- **Database Tier**: {detected_db}")
    if detected_auth != "Not detected":
        arch_sections.append(f"- **Authentication Security**: {detected_auth}")
    if detected_payment != "Not detected":
        arch_sections.append(f"- **Payment Gateway**: {detected_payment}")
    arch_sections.append(f"- **System Data Flow**: {flow_desc}")

    architecture_overview = "\n".join(arch_sections)

    analysis = {
        "overview": project_purpose,
        "technologies": technologies,
        "architecture_overview": architecture_overview,
        "key_components": key_components,
        "key_components_details": key_components_details,
        "api_surface": api_surface,
        "api_surface_details": api_surface_details,
        "code_patterns": code_patterns,
        "code_patterns_details": code_patterns_details,
        "integration_points": integration_points,
        "integration_points_details": integration_points_details,
        "dependencies": dependencies,
        "dependencies_details": dependencies_details,
        "build_deployment_config": build_deployment_config,
        "database_technologies": database_technologies,
        "external_services": external_services,
        "readme_insights": readme_insights
    }

    # Persist results to disk cache
    save_analysis_cache(
        repo_id,
        last_pushed_at,
        analysis,
        extra_data={
            "languages": languages,
            "file_structure": file_structure,
            "commits": commits,
            "total_commits": total_commits,
            "branches": branches,
            "contributors": contributors,
            "issues": issues,
            "pull_requests": pull_requests
        }
    )

    return analysis


