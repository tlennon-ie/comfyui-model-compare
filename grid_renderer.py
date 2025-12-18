"""
Grid Renderer Service

Renders HTML grids to high-quality PNG/JPEG images using Playwright.
This enables exporting full "megagrid" images from edited grid configurations.

Features:
- Headless browser rendering
- High-resolution output
- Automatic viewport sizing
- Screenshot with full grid content
"""

import asyncio
import os
from pathlib import Path
from typing import Optional, Tuple
import tempfile

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("[GridRenderer] Playwright not installed. Image rendering will not be available.")
    print("[GridRenderer] Install with: pip install playwright && playwright install chromium")


class GridRenderer:
    """Service for rendering HTML grids as images."""
    
    def __init__(self):
        self.browser = None
        self.playwright = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not HAS_PLAYWRIGHT:
            raise RuntimeError("Playwright is not installed. Cannot render grids to images.")
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def render_html_to_image(
        self,
        html_path: str,
        output_path: str,
        format: str = 'png',
        quality: int = 95,
        viewport_width: int = 1920,
        wait_for_images: bool = True,
        full_page: bool = True,
    ) -> str:
        """
        Render an HTML file to an image.
        
        Args:
            html_path: Path to HTML file to render
            output_path: Output image path
            format: 'png' or 'jpeg'
            quality: JPEG quality 1-100
            viewport_width: Browser viewport width in pixels
            wait_for_images: Wait for all images to load before screenshot
            full_page: Capture the full scrollable page
        
        Returns:
            Path to rendered image
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use 'async with GridRenderer()' context manager.")
        
        # Ensure HTML file exists
        html_path = Path(html_path).resolve()
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")
        
        # Create output directory
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create page with custom viewport
        page = await self.browser.new_page(viewport={'width': viewport_width, 'height': 1080})
        
        try:
            # Navigate to HTML file
            file_url = html_path.as_uri()
            print(f"[GridRenderer] Loading HTML: {file_url}")
            await page.goto(file_url, wait_until='domcontentloaded')
            
            # Wait for images to load if requested
            if wait_for_images:
                print("[GridRenderer] Waiting for images to load...")
                # Wait for all img elements to load
                await page.wait_for_function("""
                    () => {
                        const images = Array.from(document.querySelectorAll('img'));
                        return images.every(img => img.complete && img.naturalHeight > 0);
                    }
                """, timeout=30000)
            
            # Wait a bit for any CSS transitions/animations
            await page.wait_for_timeout(500)
            
            # Hide any floating UI elements that shouldn't be in the export
            await page.evaluate("""
                () => {
                    // Hide common UI elements
                    const elementsToHide = [
                        '.page-header',
                        '.theme-toggle',
                        '.btn-edit',
                        '.btn-export',
                        '.export-menu',
                        '#exportMenu',
                        '#compareToolbar',
                        '#compareModal',
                        '.compare-checkbox',
                        '.lightbox',
                        '.header-right'
                    ];
                    
                    elementsToHide.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => {
                            el.style.display = 'none';
                        });
                    });
                    
                    // Ensure clean background
                    document.body.style.background = 'var(--bg-primary)';
                }
            """)
            
            # Get the content height for proper sizing
            if full_page:
                print("[GridRenderer] Calculating full page dimensions...")
                dimensions = await page.evaluate("""
                    () => {
                        return {
                            width: document.documentElement.scrollWidth,
                            height: document.documentElement.scrollHeight
                        };
                    }
                """)
                print(f"[GridRenderer] Page dimensions: {dimensions['width']}x{dimensions['height']}px")
            
            # Take screenshot
            print(f"[GridRenderer] Capturing screenshot to {output_path}...")
            screenshot_options = {
                'path': str(output_path),
                'full_page': full_page,
            }
            
            if format.lower() == 'jpeg':
                screenshot_options['type'] = 'jpeg'
                screenshot_options['quality'] = quality
            else:
                screenshot_options['type'] = 'png'
            
            await page.screenshot(**screenshot_options)
            
            print(f"[GridRenderer] ✓ Successfully rendered to {output_path}")
            return str(output_path)
        
        finally:
            await page.close()
    
    async def render_html_string_to_image(
        self,
        html_content: str,
        output_path: str,
        format: str = 'png',
        quality: int = 95,
        viewport_width: int = 1920,
    ) -> str:
        """
        Render HTML content (as string) to an image.
        Creates a temporary HTML file and renders it.
        
        Args:
            html_content: HTML content as string
            output_path: Output image path
            format: 'png' or 'jpeg'
            quality: JPEG quality 1-100
            viewport_width: Browser viewport width in pixels
        
        Returns:
            Path to rendered image
        """
        # Create temporary HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_html = f.name
        
        try:
            return await self.render_html_to_image(
                temp_html,
                output_path,
                format=format,
                quality=quality,
                viewport_width=viewport_width,
            )
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_html)
            except:
                pass


def render_grid_sync(
    html_path: str,
    output_path: str,
    format: str = 'png',
    quality: int = 95,
    viewport_width: int = 1920,
) -> str:
    """
    Synchronous wrapper for rendering HTML to image.
    
    Args:
        html_path: Path to HTML file
        output_path: Output image path
        format: 'png' or 'jpeg'
        quality: JPEG quality 1-100
        viewport_width: Browser viewport width
    
    Returns:
        Path to rendered image
    """
    async def _render():
        async with GridRenderer() as renderer:
            return await renderer.render_html_to_image(
                html_path,
                output_path,
                format=format,
                quality=quality,
                viewport_width=viewport_width,
            )
    
    return asyncio.run(_render())


def is_rendering_available() -> bool:
    """Check if grid rendering is available (Playwright installed)."""
    return HAS_PLAYWRIGHT
