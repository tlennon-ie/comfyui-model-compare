"""
Export Service Module

Handles exporting grids in multiple formats:
- PNG/JPEG (large image grid)
- HTML (self-contained or external)
- PDF (with metadata and statistics)
- JSON (configuration and metadata)
- CSV (parameters only)
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional
from io import BytesIO
from PIL import Image

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class ExportService:
    """Service for exporting grids in various formats."""
    
    def __init__(self, base_output_dir: str):
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_as_html(
        self,
        grid_html: str,
        output_path: str,
        embed_images: bool = True,
        include_thumbnails: bool = True,
    ) -> str:
        """
        Export grid as HTML file.
        
        Args:
            grid_html: Complete HTML content
            output_path: Output file path
            embed_images: Whether to embed images as base64
            include_thumbnails: Whether to include thumbnail
        
        Returns:
            Path to exported file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add export metadata to HTML
        metadata_comment = f"""
<!-- Grid exported with EnhancedGridBuilder -->
<!-- Embedded: {embed_images} -->
<!-- Thumbnails: {include_thumbnails} -->
"""
        
        # Insert before closing body tag
        if '</body>' in grid_html:
            grid_html = grid_html.replace('</body>', metadata_comment + '</body>')
        
        output_path.write_text(grid_html, encoding='utf-8')
        return str(output_path)
    
    def export_as_image(
        self,
        grid_image: Image.Image,
        output_path: str,
        format: str = 'PNG',
        quality: int = 95,
    ) -> str:
        """
        Export grid as image file (PNG or JPEG).
        
        Args:
            grid_image: PIL Image object
            output_path: Output file path
            format: 'PNG' or 'JPEG'
            quality: JPEG quality 1-100
        
        Returns:
            Path to exported file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format.upper() == 'JPEG':
            # Convert RGBA to RGB for JPEG
            if grid_image.mode == 'RGBA':
                rgb_image = Image.new('RGB', grid_image.size, (255, 255, 255))
                rgb_image.paste(grid_image, mask=grid_image.split()[3])
                grid_image = rgb_image
            
            grid_image.save(output_path, 'JPEG', quality=quality)
        else:
            grid_image.save(output_path, 'PNG')
        
        return str(output_path)
    
    def export_as_json(
        self,
        metadata: Dict[str, Any],
        images: List[Dict[str, Any]],
        hierarchy: Dict[str, Any],
        styling: Dict[str, Any],
        output_path: str,
    ) -> str:
        """
        Export grid configuration and metadata as JSON.
        
        Args:
            metadata: Grid metadata
            images: List of image entries with parameters
            hierarchy: Row/column hierarchy info
            styling: Styling configuration
            output_path: Output file path
        
        Returns:
            Path to exported file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        export_data = {
            'metadata': metadata,
            'hierarchy': hierarchy,
            'styling': styling,
            'images': images,
        }
        
        output_path.write_text(json.dumps(export_data, indent=2), encoding='utf-8')
        return str(output_path)
    
    def export_as_csv(
        self,
        images: List[Dict[str, Any]],
        output_path: str,
        include_fields: Optional[List[str]] = None,
    ) -> str:
        """
        Export grid parameters as CSV.
        
        Args:
            images: List of image entries with parameters
            output_path: Output file path
            include_fields: Specific fields to include (None = all)
        
        Returns:
            Path to exported file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not images:
            return str(output_path)
        
        # Determine fields to export
        if include_fields is None:
            # Use all fields from first image
            include_fields = list(images[0].keys())
        
        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=include_fields)
            writer.writeheader()
            
            for img in images:
                row = {field: img.get(field, '') for field in include_fields}
                writer.writerow(row)
        
        return str(output_path)
    
    def export_as_pdf(
        self,
        grid_image: Image.Image,
        metadata: Dict[str, Any],
        statistics: Dict[str, Any],
        output_path: str,
    ) -> Optional[str]:
        """
        Export grid as PDF with metadata and statistics.
        
        Args:
            grid_image: PIL Image object
            metadata: Grid metadata
            statistics: Grid statistics
            output_path: Output file path
        
        Returns:
            Path to exported file, or None if reportlab not available
        """
        if not HAS_REPORTLAB:
            return None
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            title=metadata.get('title', 'Grid'),
        )
        
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title = metadata.get('title', 'Grid Report')
        story.append(Paragraph(title, styles['Title']))
        story.append(Spacer(1, 12))
        
        # Metadata section
        story.append(Paragraph('Grid Information', styles['Heading2']))
        
        metadata_data = [
            ['Field', 'Value'],
            ['Title', metadata.get('title', '')],
            ['Created', metadata.get('created', '')],
            ['Total Images', str(statistics.get('image_count', 0))],
            ['Image Format', metadata.get('image_format', 'Unknown')],
        ]
        
        metadata_table = Table(metadata_data)
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(metadata_table)
        story.append(Spacer(1, 12))
        
        # Statistics section
        story.append(Paragraph('Statistics', styles['Heading2']))
        
        stats_data = [
            ['Metric', 'Value'],
            ['Total Cells', str(statistics.get('total_cells', 0))],
            ['Cells with Images', str(statistics.get('cells_with_images', 0))],
            ['Sparsity Ratio', f"{statistics.get('sparsity_ratio', 0):.2%}"],
            ['Grid Dimensions', f"{statistics.get('grid_width', 0)}×{statistics.get('grid_height', 0)} px"],
        ]
        
        stats_table = Table(stats_data)
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(stats_table)
        
        # Build PDF
        doc.build(story)
        
        return str(output_path)
    
    def batch_export(
        self,
        grid_html: str,
        grid_image: Optional[Image.Image],
        metadata: Dict[str, Any],
        statistics: Dict[str, Any],
        output_prefix: str,
        formats: List[str],
        **options,
    ) -> Dict[str, str]:
        """
        Export grid in multiple formats at once.
        
        Args:
            grid_html: HTML content
            grid_image: PIL Image object
            metadata: Grid metadata
            statistics: Grid statistics
            output_prefix: Base name for files (without extension)
            formats: List of formats to export ('html', 'png', 'jpeg', 'pdf', 'json', 'csv')
            **options: Format-specific options
        
        Returns:
            Dictionary of format -> exported file path
        """
        results = {}
        
        if 'html' in formats:
            path = self.export_as_html(
                grid_html,
                str(self.base_output_dir / f'{output_prefix}.html'),
            )
            results['html'] = path
        
        if grid_image:
            if 'png' in formats:
                path = self.export_as_image(
                    grid_image,
                    str(self.base_output_dir / f'{output_prefix}.png'),
                    format='PNG',
                )
                results['png'] = path
            
            if 'jpeg' in formats:
                quality = options.get('jpeg_quality', 95)
                path = self.export_as_image(
                    grid_image,
                    str(self.base_output_dir / f'{output_prefix}.jpg'),
                    format='JPEG',
                    quality=quality,
                )
                results['jpeg'] = path
            
            if 'pdf' in formats and HAS_REPORTLAB:
                path = self.export_as_pdf(
                    grid_image,
                    metadata,
                    statistics,
                    str(self.base_output_dir / f'{output_prefix}.pdf'),
                )
                if path:
                    results['pdf'] = path
        
        if 'json' in formats:
            path = self.export_as_json(
                metadata,
                [],  # Images without base64 data
                options.get('hierarchy', {}),
                options.get('styling', {}),
                str(self.base_output_dir / f'{output_prefix}.json'),
            )
            results['json'] = path
        
        if 'csv' in formats:
            path = self.export_as_csv(
                [],  # Images
                str(self.base_output_dir / f'{output_prefix}.csv'),
                include_fields=options.get('csv_fields'),
            )
            results['csv'] = path
        
        return results
