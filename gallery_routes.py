"""
Gallery Routes for Model Compare

Provides web routes for:
- /model-compare/gallery - Main gallery page
- /model-compare/gallery/api/grids - List all grids
- /model-compare/gallery/api/settings - User settings for scan paths
- /model-compare/view/<path> - Serve HTML grids with correct content-type
- /model-compare/static/<path> - Serve static assets (CSS, JS, images)
"""

import os
import json
import glob
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from aiohttp import web
import folder_paths

# Signature to identify our HTML grids
GRID_SIGNATURE = "comfyui-model-compare-grid"
GRID_META_ID = "model-compare-metadata"

# Settings file location
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "gallery_settings.json")


def get_default_settings() -> Dict:
    """Get default gallery settings."""
    output_dir = folder_paths.get_output_directory()
    default_scan_path = os.path.join(output_dir, "model-compare")
    return {
        "scan_paths": [default_scan_path],
        "thumbnail_size": 300,
    }


def load_settings() -> Dict:
    """Load user settings from file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Merge with defaults for any missing keys
                defaults = get_default_settings()
                for key, value in defaults.items():
                    if key not in settings:
                        settings[key] = value
                return settings
        except Exception as e:
            print(f"[ModelCompare Gallery] Error loading settings: {e}")
    return get_default_settings()


def save_settings(settings: Dict) -> bool:
    """Save user settings to file."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"[ModelCompare Gallery] Error saving settings: {e}")
        return False


def find_grid_files(scan_paths: List[str]) -> List[Dict]:
    """
    Scan directories for HTML grid files created by Model Compare.
    
    Returns list of dicts with grid metadata:
    - path: Full file path
    - title: Grid title
    - created: Creation timestamp
    - thumbnail: Base64 thumbnail data
    - image_count: Number of images in grid
    """
    grids = []
    
    for scan_path in scan_paths:
        if not os.path.exists(scan_path):
            continue
            
        # Find all HTML files recursively
        pattern = os.path.join(scan_path, "**", "*.html")
        html_files = glob.glob(pattern, recursive=True)
        
        for html_path in html_files:
            grid_info = extract_grid_metadata(html_path)
            if grid_info:
                grids.append(grid_info)
    
    # Sort by creation date, newest first
    grids.sort(key=lambda x: x.get("created", ""), reverse=True)
    
    return grids


def extract_grid_metadata(html_path: str) -> Optional[Dict]:
    """
    Extract metadata from an HTML grid file.
    Returns None if not a valid Model Compare grid.
    """
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read(200000)  # Read first 200KB for metadata (thumbnails can be large)
        
        # Check for our signature
        if GRID_SIGNATURE not in content:
            return None
        
        # Extract metadata from JSON block
        # The script tag can have attributes in any order, so match on id alone
        metadata = {}
        meta_match = re.search(
            rf'<script[^>]*id="{GRID_META_ID}"[^>]*>(.*?)</script>',
            content, re.DOTALL
        )
        if meta_match:
            try:
                metadata = json.loads(meta_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Fallback: extract title from <title> tag
        title = metadata.get("title", "")
        if not title:
            title_match = re.search(r'<title>([^<]+)</title>', content)
            if title_match:
                title = title_match.group(1)
        
        # Get file creation/modification time
        stat = os.stat(html_path)
        created = metadata.get("created", datetime.fromtimestamp(stat.st_mtime).isoformat())
        
        # Get relative path for URL
        output_dir = folder_paths.get_output_directory()
        try:
            rel_path = os.path.relpath(html_path, output_dir)
        except ValueError:
            # On Windows, relpath fails if paths are on different drives
            rel_path = html_path
        
        # Generate base64 encoded path for API operations
        import base64
        encoded_path = base64.urlsafe_b64encode(html_path.encode('utf-8')).decode('ascii')
        
        return {
            "path": html_path,
            "rel_path": rel_path.replace("\\", "/"),
            "encoded_path": encoded_path,
            "title": title or os.path.basename(html_path),
            "created": created,
            "thumbnail": metadata.get("thumbnail", ""),
            "image_count": metadata.get("image_count", 0),
            "varying_dims": metadata.get("varying_dims", []),
        }
        
    except Exception as e:
        print(f"[ModelCompare Gallery] Error reading {html_path}: {e}")
        return None


def get_gallery_html() -> str:
    """Generate the gallery HTML page."""
    
    # Read the logo SVG for inline use
    logo_path = os.path.join(os.path.dirname(__file__), "web", "images", "logo.svg")
    logo_svg = ""
    try:
        with open(logo_path, 'r', encoding='utf-8') as f:
            logo_svg = f.read()
    except:
        pass
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="{GRID_SIGNATURE}">
    <title>Model Compare Gallery</title>
    <link rel="icon" type="image/svg+xml" href="/model-compare/static/images/logo.svg">
    <style>
{GALLERY_CSS}
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Header -->
        <header class="header">
            <div class="header-left">
                <div class="logo-container">
                    <img src="/model-compare/static/images/logo.svg" alt="MC" class="header-logo">
                </div>
                <div class="header-title">
                    <h1>Model Compare Gallery</h1>
                    <div class="header-tagline">
                        Browse and view your comparison grids •
                        <a href="https://github.com/tlennon-ie/comfyui-model-compare" target="_blank" rel="noopener">
                            <svg class="github-icon" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                                <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                            </svg>
                            GitHub
                        </a>
                    </div>
                </div>
            </div>
            <div class="header-right">
                <button id="settingsBtn" class="btn btn-icon" title="Settings">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                        <path d="M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.74,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.07,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.44-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.47-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z"/>
                    </svg>
                </button>
                <button id="refreshBtn" class="btn btn-icon" title="Refresh">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                        <path d="M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z"/>
                    </svg>
                </button>
                <button id="themeToggle" class="btn btn-icon" title="Toggle theme">
                    <svg id="themeIcon" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                        <path d="M12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,2L14.39,5.42C13.65,5.15 12.84,5 12,5C11.16,5 10.35,5.15 9.61,5.42L12,2M3.34,7L7.5,6.65C6.9,7.16 6.36,7.78 5.94,8.5C5.5,9.24 5.25,10 5.11,10.79L3.34,7M3.36,17L5.12,13.23C5.26,14 5.53,14.78 5.95,15.5C6.37,16.24 6.91,16.86 7.5,17.37L3.36,17M20.65,7L18.88,10.79C18.74,10 18.47,9.23 18.05,8.5C17.63,7.78 17.1,7.15 16.5,6.64L20.65,7M20.64,17L16.5,17.36C17.09,16.85 17.62,16.22 18.04,15.5C18.46,14.77 18.73,14 18.87,13.21L20.64,17M12,22L9.59,18.56C10.33,18.83 11.14,19 12,19C12.82,19 13.63,18.83 14.37,18.56L12,22Z"/>
                    </svg>
                </button>
            </div>
        </header>

        <!-- Main Content -->
        <main class="main-content">
            <!-- Gallery View -->
            <div id="galleryView" class="view active">
                <div class="stats-bar">
                    <span id="gridCount">0 grids found</span>
                    <span class="separator">•</span>
                    <span id="scanPathsInfo">Scanning default path</span>
                </div>
                
                <div id="gridGallery" class="grid-gallery">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Scanning for grids...</p>
                    </div>
                </div>
            </div>
            
            <!-- Grid Viewer (embedded) -->
            <div id="viewerView" class="view">
                <div class="viewer-header">
                    <button id="backToGallery" class="btn btn-secondary">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                            <path d="M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z"/>
                        </svg>
                        Back to Gallery
                    </button>
                    <span id="viewerTitle" class="viewer-title"></span>
                    <button id="openInNewTab" class="btn btn-secondary">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                            <path d="M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z"/>
                        </svg>
                        Open in New Tab
                    </button>
                </div>
                <iframe id="gridViewer" class="grid-viewer-frame" src="about:blank"></iframe>
            </div>
        </main>
        
        <!-- Settings Modal -->
        <div id="settingsModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Gallery Settings</h2>
                    <button class="modal-close" id="closeSettings">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="setting-group">
                        <label>Scan Paths</label>
                        <p class="setting-desc">Directories to scan for HTML grids (one per line)</p>
                        <textarea id="scanPathsInput" rows="4" placeholder="Enter paths to scan..."></textarea>
                        <button id="addDefaultPath" class="btn btn-small">Add Default Path</button>
                    </div>
                </div>
                <div class="modal-footer">
                    <button id="saveSettings" class="btn btn-primary">Save Settings</button>
                    <button id="cancelSettings" class="btn btn-secondary">Cancel</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
{GALLERY_JS}
    </script>
</body>
</html>'''


GALLERY_CSS = '''
:root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-card: #0f3460;
    --bg-card-hover: #1a4a7a;
    --text-primary: #eaeaea;
    --text-secondary: #a0a0a0;
    --accent: #4a9eff;
    --accent-hover: #6ab0ff;
    --border: #2a2a4a;
    --shadow: rgba(0, 0, 0, 0.3);
    --success: #4caf50;
    --warning: #ff9800;
}

[data-theme="light"] {
    --bg-primary: #f5f5f5;
    --bg-secondary: #ffffff;
    --bg-card: #ffffff;
    --bg-card-hover: #f0f7ff;
    --text-primary: #333333;
    --text-secondary: #666666;
    --accent: #2563eb;
    --accent-hover: #1d4ed8;
    --border: #e0e0e0;
    --shadow: rgba(0, 0, 0, 0.1);
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
}

.app-container {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
}

/* Header */
.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 16px;
}

.logo-container {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    overflow: hidden;
}

.header-logo {
    width: 100%;
    height: 100%;
    object-fit: contain;
}

.header-title h1 {
    font-size: 1.4rem;
    font-weight: 600;
    margin-bottom: 2px;
}

.header-tagline {
    font-size: 0.85rem;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: 6px;
}

.header-tagline a {
    color: var(--accent);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.header-tagline a:hover {
    text-decoration: underline;
}

.github-icon {
    width: 14px;
    height: 14px;
    fill: currentColor;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primary {
    background: var(--accent);
    color: white;
}

.btn-primary:hover {
    background: var(--accent-hover);
}

.btn-secondary {
    background: var(--bg-card);
    color: var(--text-primary);
    border: 1px solid var(--border);
}

.btn-secondary:hover {
    background: var(--bg-card-hover);
}

.btn-icon {
    width: 36px;
    height: 36px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border);
    border-radius: 6px;
}

.btn-icon:hover {
    background: var(--bg-card);
    color: var(--text-primary);
}

.btn-small {
    padding: 4px 12px;
    font-size: 0.8rem;
}

/* Main Content */
.main-content {
    flex: 1;
    padding: 20px 24px;
}

.view {
    display: none;
}

.view.active {
    display: block;
}

/* Stats Bar */
.stats-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--bg-secondary);
    border-radius: 8px;
    margin-bottom: 20px;
    font-size: 0.9rem;
    color: var(--text-secondary);
}

.separator {
    opacity: 0.5;
}

/* Grid Gallery */
.grid-gallery {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
}

.grid-card {
    background: var(--bg-card);
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border);
    cursor: pointer;
    transition: all 0.2s;
}

.grid-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px var(--shadow);
    border-color: var(--accent);
}

.grid-card-thumbnail {
    width: 100%;
    aspect-ratio: 16/9;
    object-fit: cover;
    background: var(--bg-primary);
}

.grid-card-thumbnail.placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 3rem;
    color: var(--text-secondary);
}

.grid-card-info {
    padding: 16px;
}

.grid-card-title {
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.grid-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 0.8rem;
    color: var(--text-secondary);
}

.grid-card-meta span {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

/* Viewer */
.viewer-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px 16px;
    background: var(--bg-secondary);
    border-radius: 8px;
    margin-bottom: 16px;
}

.viewer-title {
    flex: 1;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.grid-viewer-frame {
    width: 100%;
    height: calc(100vh - 200px);
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-card);
}

/* Modal */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.7);
    z-index: 1000;
    align-items: center;
    justify-content: center;
}

.modal.active {
    display: flex;
}

.modal-content {
    background: var(--bg-secondary);
    border-radius: 12px;
    width: 90%;
    max-width: 500px;
    max-height: 90vh;
    overflow: auto;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
}

.modal-header h2 {
    font-size: 1.2rem;
}

.modal-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: var(--text-secondary);
    cursor: pointer;
}

.modal-close:hover {
    color: var(--text-primary);
}

.modal-body {
    padding: 20px;
}

.modal-footer {
    padding: 16px 20px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
}

.setting-group {
    margin-bottom: 20px;
}

.setting-group label {
    display: block;
    font-weight: 600;
    margin-bottom: 6px;
}

.setting-desc {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-bottom: 8px;
}

.setting-group textarea,
.setting-group input {
    width: 100%;
    padding: 10px 12px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-primary);
    font-family: monospace;
    font-size: 0.9rem;
    resize: vertical;
}

.setting-group textarea:focus,
.setting-group input:focus {
    outline: none;
    border-color: var(--accent);
}

/* Loading */
.loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px;
    color: var(--text-secondary);
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 16px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-secondary);
}

.empty-state svg {
    width: 80px;
    height: 80px;
    margin-bottom: 16px;
    opacity: 0.5;
}

.empty-state h3 {
    margin-bottom: 8px;
    color: var(--text-primary);
}

/* Responsive */
@media (max-width: 768px) {
    .header {
        flex-direction: column;
        gap: 12px;
    }
    
    .header-left {
        width: 100%;
    }
    
    .header-right {
        width: 100%;
        justify-content: flex-end;
    }
    
    .grid-gallery {
        grid-template-columns: 1fr;
    }
}

/* Bulk Toolbar */
.bulk-toolbar {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-secondary);
    padding: 12px 24px;
    border-radius: 12px;
    box-shadow: 0 4px 20px var(--shadow);
    display: flex;
    gap: 16px;
    align-items: center;
    z-index: 200;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s, visibility 0.3s;
    border: 1px solid var(--border);
}

.bulk-toolbar.visible {
    opacity: 1;
    visibility: visible;
}

.bulk-toolbar .btn-danger {
    background: #dc3545;
    color: white;
}

.bulk-toolbar .btn-danger:hover:not(:disabled) {
    background: #c82333;
}

.bulk-toolbar .btn-danger:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* Selection Mode */
.grid-card.selectable {
    cursor: pointer;
}

.grid-card.selectable:hover {
    outline: 2px dashed var(--accent);
}

.grid-card.selected {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
}

.grid-card.selected::after {
    content: '✓';
    position: absolute;
    top: 8px;
    right: 8px;
    background: var(--accent);
    color: white;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 14px;
}

.btn-icon.active {
    background: var(--accent);
    color: white;
}

/* Context Menu */
.context-menu {
    position: fixed;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 4px 20px var(--shadow);
    padding: 4px;
    min-width: 150px;
    z-index: 300;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.15s, visibility 0.15s;
}

.context-menu.visible {
    opacity: 1;
    visibility: visible;
}

.context-menu-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 10px 12px;
    background: none;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 14px;
    border-radius: 4px;
    text-align: left;
}

.context-menu-item:hover {
    background: var(--bg-card-hover);
}

.context-menu-item.danger {
    color: #dc3545;
}

.context-menu-item.danger:hover {
    background: rgba(220, 53, 69, 0.1);
}
'''


GALLERY_JS = '''
(function() {
    // State
    let grids = [];
    let settings = {};
    let currentGridPath = null;
    
    // DOM elements
    const galleryView = document.getElementById('galleryView');
    const viewerView = document.getElementById('viewerView');
    const gridGallery = document.getElementById('gridGallery');
    const gridViewer = document.getElementById('gridViewer');
    const viewerTitle = document.getElementById('viewerTitle');
    const gridCount = document.getElementById('gridCount');
    const scanPathsInfo = document.getElementById('scanPathsInfo');
    const settingsModal = document.getElementById('settingsModal');
    const scanPathsInput = document.getElementById('scanPathsInput');
    
    // Initialize
    document.addEventListener('DOMContentLoaded', init);
    
    async function init() {
        setupEventListeners();
        loadTheme();
        await loadSettings();
        await loadGrids();
    }
    
    function setupEventListeners() {
        // Theme toggle
        document.getElementById('themeToggle').addEventListener('click', toggleTheme);
        
        // Refresh
        document.getElementById('refreshBtn').addEventListener('click', loadGrids);
        
        // Settings
        document.getElementById('settingsBtn').addEventListener('click', openSettings);
        document.getElementById('closeSettings').addEventListener('click', closeSettings);
        document.getElementById('cancelSettings').addEventListener('click', closeSettings);
        document.getElementById('saveSettings').addEventListener('click', saveSettings);
        document.getElementById('addDefaultPath').addEventListener('click', addDefaultPath);
        
        // Viewer
        document.getElementById('backToGallery').addEventListener('click', showGallery);
        document.getElementById('openInNewTab').addEventListener('click', openCurrentInNewTab);
    }
    
    // Theme
    function loadTheme() {
        const saved = localStorage.getItem('mc-gallery-theme') || 'dark';
        document.documentElement.setAttribute('data-theme', saved);
        updateThemeIcon(saved);
    }
    
    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('mc-gallery-theme', next);
        updateThemeIcon(next);
    }
    
    function updateThemeIcon(theme) {
        const icon = document.getElementById('themeIcon');
        if (theme === 'light') {
            icon.innerHTML = '<path d="M17.75,4.09L15.22,6.03L16.13,9.09L13.5,7.28L10.87,9.09L11.78,6.03L9.25,4.09L12.44,4L13.5,1L14.56,4L17.75,4.09M21.25,11L19.61,12.25L20.2,14.23L18.5,13.06L16.8,14.23L17.39,12.25L15.75,11L17.81,10.95L18.5,9L19.19,10.95L21.25,11M18.97,15.95C19.8,15.87 20.69,17.05 20.16,17.8C19.84,18.25 19.5,18.67 19.08,19.07C15.17,23 8.84,23 4.94,19.07C1.03,15.17 1.03,8.83 4.94,4.93C5.34,4.53 5.76,4.17 6.21,3.85C6.96,3.32 8.14,4.21 8.06,5.04C7.79,7.9 8.75,10.87 10.95,13.06C13.14,15.26 16.1,16.22 18.97,15.95Z"/>';
        } else {
            icon.innerHTML = '<path d="M12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,2L14.39,5.42C13.65,5.15 12.84,5 12,5C11.16,5 10.35,5.15 9.61,5.42L12,2M3.34,7L7.5,6.65C6.9,7.16 6.36,7.78 5.94,8.5C5.5,9.24 5.25,10 5.11,10.79L3.34,7M3.36,17L5.12,13.23C5.26,14 5.53,14.78 5.95,15.5C6.37,16.24 6.91,16.86 7.5,17.37L3.36,17M20.65,7L18.88,10.79C18.74,10 18.47,9.23 18.05,8.5C17.63,7.78 17.1,7.15 16.5,6.64L20.65,7M20.64,17L16.5,17.36C17.09,16.85 17.62,16.22 18.04,15.5C18.46,14.77 18.73,14 18.87,13.21L20.64,17M12,22L9.59,18.56C10.33,18.83 11.14,19 12,19C12.82,19 13.63,18.83 14.37,18.56L12,22Z"/>';
        }
    }
    
    // Settings
    async function loadSettings() {
        try {
            const response = await fetch('/model-compare/gallery/api/settings');
            settings = await response.json();
            updateSettingsUI();
        } catch (e) {
            console.error('Error loading settings:', e);
            settings = { scan_paths: [] };
        }
    }
    
    function updateSettingsUI() {
        scanPathsInput.value = (settings.scan_paths || []).join('\\n');
        const pathCount = settings.scan_paths?.length || 0;
        scanPathsInfo.textContent = pathCount === 1 ? 'Scanning 1 path' : `Scanning ${pathCount} paths`;
    }
    
    function openSettings() {
        updateSettingsUI();
        settingsModal.classList.add('active');
    }
    
    function closeSettings() {
        settingsModal.classList.remove('active');
    }
    
    async function saveSettings() {
        const paths = scanPathsInput.value
            .split('\\n')
            .map(p => p.trim())
            .filter(p => p.length > 0);
        
        try {
            const response = await fetch('/model-compare/gallery/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scan_paths: paths })
            });
            
            if (response.ok) {
                settings.scan_paths = paths;
                updateSettingsUI();
                closeSettings();
                await loadGrids();
            }
        } catch (e) {
            console.error('Error saving settings:', e);
        }
    }
    
    async function addDefaultPath() {
        try {
            const response = await fetch('/model-compare/gallery/api/default-path');
            const data = await response.json();
            if (data.path) {
                const current = scanPathsInput.value.trim();
                if (current && !current.includes(data.path)) {
                    scanPathsInput.value = current + '\\n' + data.path;
                } else if (!current) {
                    scanPathsInput.value = data.path;
                }
            }
        } catch (e) {
            console.error('Error getting default path:', e);
        }
    }
    
    // Load grids
    async function loadGrids() {
        gridGallery.innerHTML = '<div class="loading"><div class="spinner"></div><p>Scanning for grids...</p></div>';
        
        try {
            const response = await fetch('/model-compare/gallery/api/grids');
            grids = await response.json();
            renderGrids();
        } catch (e) {
            console.error('Error loading grids:', e);
            gridGallery.innerHTML = '<div class="empty-state"><h3>Error loading grids</h3><p>Please check the console for details.</p></div>';
        }
    }
    
    function renderGrids() {
        if (!grids || grids.length === 0) {
            gridGallery.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M19,3H5C3.89,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5C21,3.89 20.1,3 19,3M19,5V19H5V5H19M13.96,12.29L11.21,15.83L9.25,13.47L6.5,17H17.5L13.96,12.29Z"/>
                    </svg>
                    <h3>No grids found</h3>
                    <p>Generate some comparison grids with Model Compare, or check your scan paths in settings.</p>
                </div>
            `;
            gridCount.textContent = '0 grids found';
            return;
        }
        
        gridCount.textContent = grids.length === 1 ? '1 grid found' : `${grids.length} grids found`;
        
        gridGallery.innerHTML = grids.map(grid => {
            // Check if thumbnail is a valid data URL (base64 image)
            const hasValidThumbnail = grid.thumbnail && 
                                      grid.thumbnail.startsWith('data:image/') && 
                                      grid.thumbnail.length > 100;
            return `
            <div class="grid-card" data-path="${escapeAttr(grid.rel_path)}">
                ${hasValidThumbnail 
                    ? `<img class="grid-card-thumbnail" src="${grid.thumbnail}" alt="${escapeAttr(grid.title)}" onerror="this.outerHTML='<div class=grid-card-thumbnail placeholder>🖼️</div>'">`
                    : `<div class="grid-card-thumbnail placeholder">🖼️</div>`
                }
                <div class="grid-card-info">
                    <div class="grid-card-title">${escapeHtml(grid.title)}</div>
                    <div class="grid-card-meta">
                        ${grid.image_count ? `<span>📊 ${grid.image_count} images</span>` : ''}
                        <span>📅 ${formatDate(grid.created)}</span>
                    </div>
                </div>
            </div>
        `}).join('');
        
        // Add click handlers
        document.querySelectorAll('.grid-card').forEach(card => {
            card.addEventListener('click', () => {
                const path = card.dataset.path;
                viewGrid(path);
            });
        });
    }
    
    // View grid
    function viewGrid(relPath) {
        const grid = grids.find(g => g.rel_path === relPath);
        currentGridPath = relPath;
        
        viewerTitle.textContent = grid?.title || 'Grid';
        gridViewer.src = '/model-compare/view/' + encodeURIComponent(relPath);
        
        galleryView.classList.remove('active');
        viewerView.classList.add('active');
    }
    
    function showGallery() {
        viewerView.classList.remove('active');
        galleryView.classList.add('active');
        gridViewer.src = 'about:blank';
        currentGridPath = null;
    }
    
    function openCurrentInNewTab() {
        if (currentGridPath) {
            window.open('/model-compare/view/' + encodeURIComponent(currentGridPath), '_blank');
        }
    }
    
    // Helpers
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
    
    function escapeAttr(text) {
        return (text || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    
    function formatDate(isoDate) {
        if (!isoDate) return 'Unknown';
        try {
            const date = new Date(isoDate);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
        } catch {
            return isoDate;
        }
    }
    
    // ============ Grid Management Functions ============
    let selectionMode = false;
    let selectedGrids = new Set();
    
    // Add management buttons to header
    document.addEventListener('DOMContentLoaded', function() {
        const headerRight = document.querySelector('.header-right');
        
        // Selection mode toggle button
        const selectBtn = document.createElement('button');
        selectBtn.id = 'selectModeBtn';
        selectBtn.className = 'btn btn-icon';
        selectBtn.title = 'Select grids for bulk operations';
        selectBtn.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5A2,2 0 0,0 19,3M19,5V19H5V5H19M10,17L6,13L7.41,11.58L10,14.17L16.59,7.58L18,9"/>
        </svg>`;
        selectBtn.addEventListener('click', toggleSelectionMode);
        headerRight.insertBefore(selectBtn, headerRight.firstChild);
        
        // Bulk action toolbar (hidden by default)
        const toolbar = document.createElement('div');
        toolbar.id = 'bulkToolbar';
        toolbar.className = 'bulk-toolbar';
        toolbar.innerHTML = `
            <span id="selectedCount">0 selected</span>
            <button class="btn btn-danger" id="bulkDeleteBtn" disabled>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z"/>
                </svg>
                Delete Selected
            </button>
            <button class="btn btn-secondary" id="cancelSelectBtn">Cancel</button>
        `;
        document.body.appendChild(toolbar);
        
        document.getElementById('bulkDeleteBtn').addEventListener('click', confirmBulkDelete);
        document.getElementById('cancelSelectBtn').addEventListener('click', toggleSelectionMode);
    });
    
    function toggleSelectionMode() {
        selectionMode = !selectionMode;
        selectedGrids.clear();
        
        const toolbar = document.getElementById('bulkToolbar');
        const selectBtn = document.getElementById('selectModeBtn');
        
        if (selectionMode) {
            selectBtn.classList.add('active');
            toolbar.classList.add('visible');
            document.querySelectorAll('.grid-card').forEach(card => {
                card.classList.add('selectable');
            });
        } else {
            selectBtn.classList.remove('active');
            toolbar.classList.remove('visible');
            document.querySelectorAll('.grid-card').forEach(card => {
                card.classList.remove('selectable', 'selected');
            });
        }
        updateSelectedCount();
    }
    
    function updateSelectedCount() {
        const countEl = document.getElementById('selectedCount');
        const deleteBtn = document.getElementById('bulkDeleteBtn');
        const count = selectedGrids.size;
        countEl.textContent = count === 1 ? '1 selected' : `${count} selected`;
        deleteBtn.disabled = count === 0;
    }
    
    // Override card click in selection mode
    document.addEventListener('click', function(e) {
        if (!selectionMode) return;
        
        const card = e.target.closest('.grid-card');
        if (!card) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        const path = card.dataset.path;
        if (selectedGrids.has(path)) {
            selectedGrids.delete(path);
            card.classList.remove('selected');
        } else {
            selectedGrids.add(path);
            card.classList.add('selected');
        }
        updateSelectedCount();
    }, true);
    
    async function confirmBulkDelete() {
        if (selectedGrids.size === 0) return;
        
        const count = selectedGrids.size;
        if (!confirm(`Delete ${count} grid${count > 1 ? 's' : ''}? This cannot be undone.`)) {
            return;
        }
        
        // Convert relative paths to encoded absolute paths
        const paths = Array.from(selectedGrids).map(relPath => {
            const grid = grids.find(g => g.rel_path === relPath);
            return grid?.encoded_path || relPath;
        });
        
        try {
            const response = await fetch('/model-compare/gallery/api/bulk-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paths })
            });
            
            const result = await response.json();
            
            if (result.deletedCount > 0) {
                alert(`Deleted ${result.deletedCount} grid${result.deletedCount > 1 ? 's' : ''}.${result.errorCount > 0 ? ` (${result.errorCount} failed)` : ''}`);
                toggleSelectionMode();
                await loadGrids();
            } else if (result.errors?.length > 0) {
                alert('Failed to delete grids: ' + result.errors[0].error);
            }
        } catch (e) {
            console.error('Bulk delete error:', e);
            alert('Error deleting grids');
        }
    }
    
    // Context menu for individual grid actions
    let contextMenuGrid = null;
    
    document.addEventListener('DOMContentLoaded', function() {
        // Create context menu
        const menu = document.createElement('div');
        menu.id = 'gridContextMenu';
        menu.className = 'context-menu';
        menu.innerHTML = `
            <button class="context-menu-item" id="ctxRename">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M14.06,9L15,9.94L5.92,19H5V18.08L14.06,9M17.66,3C17.41,3 17.15,3.1 16.96,3.29L15.13,5.12L18.88,8.87L20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18.17,3.09 17.92,3 17.66,3M14.06,6.19L3,17.25V21H6.75L17.81,9.94L14.06,6.19Z"/>
                </svg>
                Rename
            </button>
            <button class="context-menu-item danger" id="ctxDelete">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z"/>
                </svg>
                Delete
            </button>
        `;
        document.body.appendChild(menu);
        
        document.getElementById('ctxRename').addEventListener('click', renameGrid);
        document.getElementById('ctxDelete').addEventListener('click', deleteGrid);
        
        // Show context menu on right-click
        document.addEventListener('contextmenu', function(e) {
            const card = e.target.closest('.grid-card');
            if (!card || selectionMode) return;
            
            e.preventDefault();
            contextMenuGrid = card.dataset.path;
            
            const menu = document.getElementById('gridContextMenu');
            menu.style.left = e.pageX + 'px';
            menu.style.top = e.pageY + 'px';
            menu.classList.add('visible');
        });
        
        // Hide context menu on click elsewhere
        document.addEventListener('click', function() {
            document.getElementById('gridContextMenu').classList.remove('visible');
        });
    });
    
    async function renameGrid() {
        if (!contextMenuGrid) return;
        
        const grid = grids.find(g => g.rel_path === contextMenuGrid);
        if (!grid) return;
        
        const currentName = grid.title || contextMenuGrid.split('/').pop().replace('.html', '');
        const newName = prompt('Enter new name:', currentName);
        
        if (!newName || newName === currentName) return;
        
        try {
            const response = await fetch('/model-compare/gallery/api/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    path: grid.encoded_path,
                    newName: newName
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                await loadGrids();
            } else {
                alert('Failed to rename: ' + result.error);
            }
        } catch (e) {
            console.error('Rename error:', e);
            alert('Error renaming grid');
        }
    }
    
    async function deleteGrid() {
        if (!contextMenuGrid) return;
        
        const grid = grids.find(g => g.rel_path === contextMenuGrid);
        if (!grid) return;
        
        if (!confirm(`Delete "${grid.title || contextMenuGrid}"? This cannot be undone.`)) {
            return;
        }
        
        try {
            const response = await fetch('/model-compare/gallery/api/delete?path=' + encodeURIComponent(grid.encoded_path), {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                await loadGrids();
            } else {
                alert('Failed to delete: ' + result.error);
            }
        } catch (e) {
            console.error('Delete error:', e);
            alert('Error deleting grid');
        }
    }
})();
'''


async def handle_gallery_page(request):
    """Serve the main gallery page."""
    return web.Response(text=get_gallery_html(), content_type='text/html')


async def handle_api_grids(request):
    """API endpoint to list all grids."""
    settings = load_settings()
    grids = find_grid_files(settings.get("scan_paths", []))
    return web.json_response(grids)


async def handle_api_settings_get(request):
    """API endpoint to get settings."""
    settings = load_settings()
    return web.json_response(settings)


async def handle_api_settings_post(request):
    """API endpoint to save settings."""
    try:
        data = await request.json()
        settings = load_settings()
        
        if "scan_paths" in data:
            settings["scan_paths"] = data["scan_paths"]
        
        if save_settings(settings):
            return web.json_response({"success": True})
        else:
            return web.json_response({"success": False, "error": "Failed to save"}, status=500)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=400)


async def handle_api_default_path(request):
    """API endpoint to get default scan path."""
    output_dir = folder_paths.get_output_directory()
    default_path = os.path.join(output_dir, "model-compare")
    return web.json_response({"path": default_path})


async def handle_api_rename_grid(request):
    """API endpoint to rename a grid file.
    
    POST body: {"path": "encoded_path", "newName": "new_filename"}
    """
    import base64
    
    try:
        data = await request.json()
        encoded_path = data.get("path", "")
        new_name = data.get("newName", "")
        
        if not encoded_path or not new_name:
            return web.json_response({"success": False, "error": "Missing path or newName"}, status=400)
        
        # Decode path
        try:
            decoded_bytes = base64.urlsafe_b64decode(encoded_path)
            full_path = decoded_bytes.decode('utf-8')
        except Exception:
            return web.json_response({"success": False, "error": "Invalid path encoding"}, status=400)
        
        full_path = os.path.abspath(full_path)
        
        # Security check
        if not _is_path_allowed(full_path):
            return web.json_response({"success": False, "error": "Path not allowed"}, status=403)
        
        if not os.path.exists(full_path):
            return web.json_response({"success": False, "error": "File not found"}, status=404)
        
        # Sanitize new name
        new_name = re.sub(r'[<>:"/\\|?*]', '_', new_name)
        if not new_name.endswith('.html'):
            new_name += '.html'
        
        # Build new path
        dir_name = os.path.dirname(full_path)
        new_path = os.path.join(dir_name, new_name)
        
        if os.path.exists(new_path):
            return web.json_response({"success": False, "error": "A file with that name already exists"}, status=409)
        
        # Rename the file
        os.rename(full_path, new_path)
        
        # Generate new encoded path for the response
        new_encoded = base64.urlsafe_b64encode(new_path.encode('utf-8')).decode('ascii')
        
        return web.json_response({
            "success": True,
            "newPath": new_encoded,
            "newName": new_name
        })
        
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_delete_grid(request):
    """API endpoint to delete a grid file.
    
    DELETE query param: path=encoded_path
    """
    import base64
    
    try:
        encoded_path = request.query.get("path", "")
        
        if not encoded_path:
            return web.json_response({"success": False, "error": "Missing path"}, status=400)
        
        # Decode path
        try:
            decoded_bytes = base64.urlsafe_b64decode(encoded_path)
            full_path = decoded_bytes.decode('utf-8')
        except Exception:
            return web.json_response({"success": False, "error": "Invalid path encoding"}, status=400)
        
        full_path = os.path.abspath(full_path)
        
        # Security check
        if not _is_path_allowed(full_path):
            return web.json_response({"success": False, "error": "Path not allowed"}, status=403)
        
        if not os.path.exists(full_path):
            return web.json_response({"success": False, "error": "File not found"}, status=404)
        
        # Delete the file
        os.remove(full_path)
        
        return web.json_response({"success": True})
        
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_bulk_delete_grids(request):
    """API endpoint to delete multiple grid files.
    
    POST body: {"paths": ["encoded_path1", "encoded_path2", ...]}
    """
    import base64
    
    try:
        data = await request.json()
        encoded_paths = data.get("paths", [])
        
        if not encoded_paths:
            return web.json_response({"success": False, "error": "No paths provided"}, status=400)
        
        deleted = []
        errors = []
        
        for encoded_path in encoded_paths:
            try:
                # Decode path
                decoded_bytes = base64.urlsafe_b64decode(encoded_path)
                full_path = decoded_bytes.decode('utf-8')
                full_path = os.path.abspath(full_path)
                
                # Security check
                if not _is_path_allowed(full_path):
                    errors.append({"path": encoded_path, "error": "Path not allowed"})
                    continue
                
                if not os.path.exists(full_path):
                    errors.append({"path": encoded_path, "error": "File not found"})
                    continue
                
                # Delete the file
                os.remove(full_path)
                deleted.append(encoded_path)
                
            except Exception as e:
                errors.append({"path": encoded_path, "error": str(e)})
        
        return web.json_response({
            "success": len(errors) == 0,
            "deleted": deleted,
            "errors": errors,
            "deletedCount": len(deleted),
            "errorCount": len(errors)
        })
        
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


def _is_path_allowed(full_path: str) -> bool:
    """Check if a path is in an allowed directory."""
    allowed_paths = [os.path.abspath(folder_paths.get_output_directory())]
    settings = load_settings()
    for scan_path in settings.get("scan_paths", []):
        if os.path.exists(scan_path):
            allowed_paths.append(os.path.abspath(scan_path))
    
    for allowed in allowed_paths:
        try:
            # Check if full_path starts with an allowed path
            if full_path.startswith(allowed + os.sep) or full_path == allowed:
                return True
        except Exception:
            continue
    
    return False


async def handle_view_grid(request):
    """Serve an HTML grid file with proper content-type.
    
    Accepts two path formats:
    1. Base64 URL-safe encoded absolute path (from tracker button)
    2. Relative path from output directory (from gallery)
    """
    import base64
    import urllib.parse
    
    path_param = request.match_info.get('path', '')
    
    if not path_param:
        return web.Response(text="No path specified", status=400)
    
    # URL decode first
    path_param = urllib.parse.unquote(path_param)
    
    # Try to decode as base64 first (tracker button format)
    full_path = None
    try:
        # Base64 URL-safe decode
        decoded_bytes = base64.urlsafe_b64decode(path_param)
        decoded_path = decoded_bytes.decode('utf-8')
        # Check if it looks like an absolute path
        if os.path.isabs(decoded_path):
            full_path = decoded_path
    except Exception:
        # Not base64, treat as relative path from output directory
        pass
    
    # If not base64, treat as relative path
    if full_path is None:
        output_dir = folder_paths.get_output_directory()
        full_path = os.path.join(output_dir, path_param)
    
    # Normalize the path
    full_path = os.path.abspath(full_path)
    
    # Security: Check if path is in allowed directories
    # Allow output directory and all scan paths from settings
    allowed_paths = [os.path.abspath(folder_paths.get_output_directory())]
    settings = load_settings()
    for scan_path in settings.get("scan_paths", []):
        if os.path.exists(scan_path):
            allowed_paths.append(os.path.abspath(scan_path))
    
    is_allowed = False
    for allowed in allowed_paths:
        if full_path.startswith(allowed):
            is_allowed = True
            break
    
    if not is_allowed:
        print(f"[ModelCompare Gallery] Access denied for path: {full_path}")
        print(f"[ModelCompare Gallery] Allowed paths: {allowed_paths}")
        return web.Response(text="Access denied - path not in allowed directories", status=403)
    
    if not os.path.exists(full_path):
        return web.Response(text=f"File not found: {full_path}", status=404)
    
    if not full_path.lower().endswith('.html'):
        return web.Response(text="Invalid file type - must be .html", status=400)
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return web.Response(text=content, content_type='text/html')
    except Exception as e:
        return web.Response(text=f"Error reading file: {e}", status=500)


async def handle_static(request):
    """Serve static files (images, css, js)."""
    file_path = request.match_info.get('path', '')
    
    if not file_path:
        return web.Response(text="No path specified", status=400)
    
    # Build full path from web directory
    base_dir = os.path.join(os.path.dirname(__file__), "web")
    full_path = os.path.join(base_dir, file_path)
    
    # Security: ensure path is under web directory
    full_path = os.path.abspath(full_path)
    base_dir = os.path.abspath(base_dir)
    
    if not full_path.startswith(base_dir):
        return web.Response(text="Access denied", status=403)
    
    if not os.path.exists(full_path):
        return web.Response(text="File not found", status=404)
    
    # Determine content type
    ext = os.path.splitext(full_path)[1].lower()
    content_types = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
    }
    content_type = content_types.get(ext, 'application/octet-stream')
    
    try:
        if content_type.startswith('text/') or content_type in ['application/javascript', 'application/json', 'image/svg+xml']:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return web.Response(text=content, content_type=content_type)
        else:
            with open(full_path, 'rb') as f:
                content = f.read()
            return web.Response(body=content, content_type=content_type)
    except Exception as e:
        return web.Response(text=f"Error reading file: {e}", status=500)


def setup_gallery_routes():
    """Register gallery routes with ComfyUI server."""
    try:
        from server import PromptServer
        
        if PromptServer.instance is None:
            print("[ModelCompare Gallery] PromptServer not available yet, will retry on first request")
            return False
        
        app = PromptServer.instance.app
        
        # Check if routes are already registered
        for resource in app.router.resources():
            if hasattr(resource, '_path') and resource._path == '/model-compare/gallery':
                print("[ModelCompare] Gallery routes already registered")
                return True
        
        # Gallery page
        app.router.add_get('/model-compare/gallery', handle_gallery_page)
        
        # API endpoints
        app.router.add_get('/model-compare/gallery/api/grids', handle_api_grids)
        app.router.add_get('/model-compare/gallery/api/settings', handle_api_settings_get)
        app.router.add_post('/model-compare/gallery/api/settings', handle_api_settings_post)
        app.router.add_get('/model-compare/gallery/api/default-path', handle_api_default_path)
        
        # Grid management endpoints
        app.router.add_post('/model-compare/gallery/api/rename', handle_api_rename_grid)
        app.router.add_delete('/model-compare/gallery/api/delete', handle_api_delete_grid)
        app.router.add_post('/model-compare/gallery/api/bulk-delete', handle_api_bulk_delete_grids)
        
        # View grid with proper content-type (supports base64 encoded paths)
        app.router.add_get('/model-compare/view/{path:.*}', handle_view_grid)
        
        # Static files
        app.router.add_get('/model-compare/static/{path:.*}', handle_static)
        
        print("[ModelCompare] Gallery routes registered at /model-compare/gallery")
        return True
        
    except Exception as e:
        print(f"[ModelCompare Gallery] Error setting up routes: {e}")
        import traceback
        traceback.print_exc()
        return False


# Global flag to track if setup has been attempted
_routes_setup_attempted = False

def ensure_routes_setup():
    """Ensure routes are set up, called lazily if initial setup failed."""
    global _routes_setup_attempted
    if not _routes_setup_attempted:
        _routes_setup_attempted = True
        setup_gallery_routes()

# Auto-register routes when module is imported
setup_gallery_routes()
