"""
Grid Builder API Routes

Provides REST endpoints for interactive grid builder UI.
Handles parsing, configuration, hierarchy editing, and export.
"""

import json
import os
from aiohttp import web
from pathlib import Path
from typing import Dict, Any, List

from .grid_parser import GridParser, GridConfigLoader, GridConfig
from .hierarchy_builder import HierarchyBuilder, NestedGridLayout, HeaderMerger
from .html_grid_generator import generate_nested_html_grid


class GridBuilderAPI:
    """API endpoints for grid builder functionality."""
    
    def __init__(self, base_output_dir: str):
        """
        Initialize grid builder API.
        
        Args:
            base_output_dir: Base directory for grid output files
        """
        self.base_output_dir = Path(base_output_dir)
        self.cache = {}  # Cache parsed grids to avoid re-parsing
    
    async def load_grid(self, request: web.Request) -> web.Response:
        """
        Load and parse an existing grid HTML file.
        
        POST /api/grid/load
        Body: {"grid_path": "/path/to/grid.html"}
        
        Returns: GridConfig JSON
        """
        try:
            data = await request.json()
            grid_path = data.get('grid_path')
            print(f"Load grid request: {grid_path}")
            
            if not grid_path:
                return web.json_response(
                    {'error': 'grid_path required'},
                    status=400
                )
            
            # Security: Validate path is within allowed directory
            grid_path = Path(grid_path).resolve()
            print(f"Resolved grid path: {grid_path}")
            print(f"Base output dir: {self.base_output_dir}")
            if not str(grid_path).startswith(str(self.base_output_dir)):
                return web.json_response(
                    {'error': 'Access denied: path outside allowed directory'},
                    status=403
                )
            
            # Parse grid
            parser = GridParser(str(grid_path))
            config = parser.parse()
            
            # If no hierarchy defined, use smart detection
            if not config.row_hierarchy and not config.col_hierarchy:
                from .hierarchy_builder import SmartHierarchyDetector
                
                # Convert images to combinations format
                combinations = [img.params for img in config.images]
                
                # Detect smart hierarchy with preferences
                row_hierarchy, col_hierarchy = SmartHierarchyDetector.detect_hierarchy(
                    combinations,
                    preferred_rows=['prompt', 'prompt_positive', 'text'],
                    preferred_cols=['model', 'diffusion_model', 'base_model']
                )
                
                # Update config
                config.row_hierarchy = row_hierarchy
                config.col_hierarchy = col_hierarchy
                config.depth = max(len(row_hierarchy), len(col_hierarchy))
            
            # Cache for later use
            self.cache[grid_path] = config
            
            return web.json_response({
                'status': 'ok',
                'grid': {
                    'metadata': {
                        'title': config.metadata.title,
                        'created': config.metadata.created,
                        'image_count': config.metadata.image_count,
                        'varying_dims': config.metadata.varying_dims,
                    },
                    'hierarchy': {
                        'row_hierarchy': config.row_hierarchy,
                        'col_hierarchy': config.col_hierarchy,
                        'depth': config.depth,
                    },
                    'styling': config.styling,
                    'varying_dimensions': parser.get_varying_dimensions(),
                }
            })
        
        except FileNotFoundError as e:
            print(f"Grid file not found: {e}")
            return web.json_response({'error': str(e)}, status=404)
        except Exception as e:
            import traceback
            print(f"Error loading grid: {e}")
            traceback.print_exc()
            return web.json_response({'error': str(e)}, status=500)
    
    async def analyze_hierarchy(self, request: web.Request) -> web.Response:
        """
        Analyze hierarchy structure and detect potential issues.
        
        POST /api/grid/analyze-hierarchy
        Body: {
            "grid_path": "/path/to/grid.html",
            "row_hierarchy": ["field1", "field2"],
            "col_hierarchy": ["field3", "field4"]
        }
        
        Returns: Analysis with recommendations
        """
        try:
            data = await request.json()
            grid_path = data.get('grid_path')
            row_hierarchy = data.get('row_hierarchy', [])
            col_hierarchy = data.get('col_hierarchy', [])
            
            # Validate hierarchy
            is_valid, error_msg = GridConfigLoader.validate_hierarchy(
                row_hierarchy, col_hierarchy
            )
            
            if not is_valid:
                return web.json_response({
                    'status': 'invalid',
                    'error': error_msg
                })
            
            # Load grid and build hierarchy tree
            grid_path = Path(grid_path).resolve()
            parser = GridParser(str(grid_path))
            config = parser.parse()
            
            # Get field values for callback
            varying_dims = parser.get_varying_dimensions()
            
            # Analyze sparsity
            expected_cells = (
                len(set(img.params.get(row_hierarchy[0]) for img in config.images if row_hierarchy)) or 1
            ) * (
                len(set(img.params.get(col_hierarchy[0]) for img in config.images if col_hierarchy)) or 1
            )
            actual_cells = len(config.images)
            sparsity = 1.0 - (actual_cells / expected_cells) if expected_cells > 0 else 0
            
            return web.json_response({
                'status': 'valid',
                'analysis': {
                    'total_images': len(config.images),
                    'expected_cells': expected_cells,
                    'actual_cells': actual_cells,
                    'sparsity_ratio': round(sparsity, 2),
                    'is_sparse': sparsity > 0.2,
                    'varying_dimensions': {k: len(v) for k, v in varying_dims.items()},
                    'row_hierarchy': row_hierarchy,
                    'col_hierarchy': col_hierarchy,
                }
            })
        
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def generate_preview(self, request: web.Request) -> web.Response:
        """
        Generate a preview of the grid with new hierarchy.
        
        POST /api/grid/preview
        Body: {
            "grid_path": "/path/to/grid.html",
            "row_hierarchy": ["field1"],
            "col_hierarchy": ["field2"],
            "title": "New Title"
        }
        
        Returns: Preview metadata and layout info
        """
        try:
            data = await request.json()
            grid_path = data.get('grid_path')
            row_hierarchy = data.get('row_hierarchy', [])
            col_hierarchy = data.get('col_hierarchy', [])
            title = data.get('title', 'Preview')
            
            grid_path = Path(grid_path).resolve()
            parser = GridParser(str(grid_path))
            config = parser.parse()
            
            # Build hierarchy trees
            builder = HierarchyBuilder()
            
            def get_field_value(combo, field):
                # Use grid_utils function
                from .grid_utils import get_combo_field_value
                return get_combo_field_value(combo, {}, field)
            
            # Mock combinations from images
            combinations = [{
                **img.params,
                'index': img.index
            } for img in config.images]
            
            builder.build_from_combinations(
                combinations,
                row_hierarchy,
                col_hierarchy,
                get_field_value
            )
            
            valid_cells = builder.get_valid_cells()
            row_paths = builder.get_filtered_row_paths()
            col_paths = builder.get_filtered_col_paths()
            
            # Calculate layout
            layout = NestedGridLayout(
                row_paths, col_paths,
                row_hierarchy, col_hierarchy
            )
            width, height = layout.calculate_dimensions()
            
            return web.json_response({
                'status': 'ok',
                'preview': {
                    'title': title,
                    'dimensions': {'width': width, 'height': height},
                    'cells': {
                        'total': len(valid_cells),
                        'rows': len(row_paths),
                        'cols': len(col_paths),
                    },
                    'hierarchy': {
                        'row_hierarchy': row_hierarchy,
                        'col_hierarchy': col_hierarchy,
                        'depth': max(len(row_hierarchy), len(col_hierarchy)),
                    }
                }
            })
        
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def export_grid(self, request: web.Request) -> web.Response:
        """
        Export grid with new configuration.
        
        POST /api/grid/export
        Body: {
            "grid_path": "/path/to/grid.html",
            "row_hierarchy": ["field1"],
            "col_hierarchy": ["field2"],
            "title": "New Title",
            "format": "html",  # or "png", "pdf"
            "output_name": "my_grid"
        }
        
        Returns: Export result with file path
        """
        try:
            data = await request.json()
            grid_path = data.get('grid_path')
            row_hierarchy = data.get('row_hierarchy', [])
            col_hierarchy = data.get('col_hierarchy', [])
            title = data.get('title', 'Grid')
            export_format = data.get('format', 'html')
            output_name = data.get('output_name', 'exported_grid')
            
            # Load and parse original grid
            grid_path = Path(grid_path).resolve()
            parser = GridParser(str(grid_path))
            config = parser.parse()
            
            # Sanitize output name
            output_name = "".join(c for c in output_name if c.isalnum() or c in '-_')
            
            from .export_service import ExportService
            export_service = ExportService(str(self.base_output_dir))
            
            if export_format == 'html':
                # Generate new HTML with reconfigured hierarchy
                output_path = self.base_output_dir / f"{output_name}.html"
                
                # Generate HTML using the hierarchy builder
                html_content = generate_nested_html_grid(
                    images=config.images,
                    row_hierarchy=row_hierarchy,
                    col_hierarchy=col_hierarchy,
                    title=title,
                    styling=config.styling,
                )
                
                output_path.write_text(html_content, encoding='utf-8')
                
                return web.json_response({
                    'status': 'ok',
                    'export': {
                        'format': 'html',
                        'path': str(output_path),
                        'rel_path': str(output_path.relative_to(self.base_output_dir)),
                        'size_bytes': output_path.stat().st_size,
                    }
                })
            
            elif export_format in ['png', 'jpeg']:
                # Export as image (requires rendering HTML to image - placeholder for now)
                return web.json_response({
                    'error': 'Image export requires browser rendering. Use HTML export and screenshot the page.',
                    'suggestion': 'Export as HTML and use browser\'s built-in screenshot feature'
                }, status=501)
            
            elif export_format == 'pdf':
                # Export as PDF - requires rendering grid to image first
                return web.json_response({
                    'error': 'PDF export requires grid image rendering. Use HTML export for now.',
                    'suggestion': 'Export as HTML and use browser print-to-PDF feature'
                }, status=501)
                
                return web.json_response({
                    'status': 'ok',
                    'export': {
                        'format': 'pdf',
                        'path': result_path,
                        'rel_path': Path(result_path).relative_to(self.base_output_dir).as_posix(),
                        'size_bytes': Path(result_path).stat().st_size,
                    }
                })
            
            elif export_format == 'csv':
                # Export as CSV
                output_path = str(self.base_output_dir / f"{output_name}.csv")
                
                # Prepare data - convert GridImage params to flat dict
                csv_data = [img.params for img in config.images]
                
                result_path = export_service.export_as_csv(
                    images=csv_data,
                    output_path=output_path,
                    include_fields=None  # All fields
                )
                
                return web.json_response({
                    'status': 'ok',
                    'export': {
                        'format': 'csv',
                        'path': result_path,
                        'rel_path': Path(result_path).relative_to(self.base_output_dir).as_posix(),
                        'size_bytes': Path(result_path).stat().st_size,
                    }
                })
            
            elif export_format == 'json':
                # Export as JSON config
                output_path = str(self.base_output_dir / f"{output_name}.json")
                
                # Match export_service.export_as_json signature
                metadata_dict = {
                    'title': title,
                    'row_hierarchy': row_hierarchy,
                    'col_hierarchy': col_hierarchy
                }
                images_list = [{'params': img.params, 'label': img.label, 'index': img.index} for img in config.images]
                hierarchy_dict = {'row_hierarchy': row_hierarchy, 'col_hierarchy': col_hierarchy}
                
                result_path = export_service.export_as_json(
                    metadata=metadata_dict,
                    images=images_list,
                    hierarchy=hierarchy_dict,
                    styling=config.styling,
                    output_path=output_path
                )
                
                return web.json_response({
                    'status': 'ok',
                    'export': {
                        'format': 'json',
                        'path': result_path,
                        'rel_path': Path(result_path).relative_to(self.base_output_dir).as_posix(),
                        'size_bytes': Path(result_path).stat().st_size,
                    }
                })
            
            else:
                return web.json_response(
                    {'error': f'Unknown format: {export_format}'},
                    status=400
                )
        
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_field_values(self, request: web.Request) -> web.Response:
        """
        Get unique values for a specific field across all images in a grid.
        
        GET /api/grid/field-values?grid_path={path}&field={field_name}
        
        Returns: List of unique values
        """
        try:
            grid_path = request.rel_url.query.get('grid_path')
            field = request.rel_url.query.get('field')
            
            if not grid_path or not field:
                return web.json_response(
                    {'error': 'grid_path and field parameters required'},
                    status=400
                )
            
            grid_path = Path(grid_path).resolve()
            parser = GridParser(str(grid_path))
            
            # Get unique values for field
            values = set()
            for img in parser.images:
                val = img.params.get(field)
                if val is not None:
                    values.add(str(val))
            
            return web.json_response({
                'status': 'ok',
                'field': field,
                'values': sorted(list(values))
            })
        
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)


def add_grid_builder_routes(app: web.Application, base_output_dir: str) -> None:
    """
    Register grid builder routes with the aiohttp application.
    
    Args:
        app: aiohttp Application instance
        base_output_dir: Base directory for grid files
    """
    api = GridBuilderAPI(base_output_dir)
    
    app.router.add_post('/api/grid/load', api.load_grid)
    app.router.add_post('/api/grid/analyze-hierarchy', api.analyze_hierarchy)
    app.router.add_post('/api/grid/preview', api.generate_preview)
    app.router.add_post('/api/grid/export', api.export_grid)
    app.router.add_get('/api/grid/field-values', api.get_field_values)
