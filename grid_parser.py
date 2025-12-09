"""
Grid Parser Module

Extracts metadata, image data, and configuration from existing HTML grids.
Enables the grid builder to load and reconfigure previously generated grids.
"""

import json
import re
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class GridMetadata:
    """Extracted metadata from a grid HTML file."""
    title: str
    created: str
    image_count: int
    varying_dims: List[str]
    thumbnail: Optional[str] = None
    description: Optional[str] = None


@dataclass
class GridImage:
    """A single image entry in the grid."""
    index: int
    label: str
    params: Dict[str, Any]
    image_data: Optional[str] = None  # Base64 if embedded
    image_path: Optional[str] = None  # External path


@dataclass
class GridConfig:
    """Complete parsed grid configuration."""
    metadata: GridMetadata
    images: List[GridImage]
    row_hierarchy: List[str]
    col_hierarchy: List[str]
    depth: int
    styling: Dict[str, Any]
    raw_html: Optional[str] = None


class GridParser:
    """
    Parse HTML grid files and extract all relevant data.
    
    Handles both self-contained (base64-embedded) and external-image grids.
    """
    
    # Pattern to extract metadata script tag (correct ID from our generator)
    METADATA_PATTERN = re.compile(
        r'<script[^>]*id="model-compare-metadata"[^>]*>(.*?)</script>',
        re.DOTALL
    )
    
    # Pattern to extract grid data array from main script
    GRID_DATA_PATTERN = re.compile(
        r'const gridData\s*=\s*(\[.*?\]);',
        re.DOTALL
    )
    
    # Pattern to extract varying dimensions
    VARYING_DIMS_PATTERN = re.compile(
        r'const varyingDimensions\s*=\s*(\{.*?\});',
        re.DOTALL
    )
    
    # Pattern to extract style config (not used yet, but kept for future)
    STYLE_PATTERN = re.compile(
        r'<style[^>]*>(.*?)</style>',
        re.DOTALL
    )
    
    def __init__(self, html_path: str):
        """
        Initialize parser with a grid HTML file.
        
        Args:
            html_path: Absolute path to HTML grid file
        """
        self.html_path = Path(html_path)
        self.grid_dir = self.html_path.parent
        
        if not self.html_path.exists():
            raise FileNotFoundError(f"Grid file not found: {html_path}")
        
        self.raw_html = self._read_html()
        self.is_embedded = self._check_if_embedded()
        
        # Cached parsed data
        self._config = None
    
    def _read_html(self) -> str:
        """Read HTML file content."""
        with open(self.html_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _check_if_embedded(self) -> bool:
        """Check if grid uses embedded base64 images."""
        return 'data:image' in self.raw_html
    
    def parse(self) -> GridConfig:
        """
        Parse the entire grid HTML.
        
        Returns:
            Complete GridConfig with all extracted data
        """
        # Return cached if available
        if self._config:
            return self._config
        metadata = self._parse_metadata()
        images = self._parse_images()
        row_hierarchy, col_hierarchy = self._parse_hierarchy()
        styling = self._parse_styling()
        
        depth = max(len(row_hierarchy), len(col_hierarchy))
        
        self._config = GridConfig(
            metadata=metadata,
            images=images,
            row_hierarchy=row_hierarchy,
            col_hierarchy=col_hierarchy,
            depth=depth,
            styling=styling,
            raw_html=self.raw_html
        )
        
        return self._config
    
    def _parse_metadata(self) -> GridMetadata:
        """Extract metadata from script tag."""
        match = self.METADATA_PATTERN.search(self.raw_html)
        
        if match:
            try:
                json_str = match.group(1).strip()
                data = json.loads(json_str)
                return GridMetadata(
                    title=data.get('title', 'Untitled'),
                    created=data.get('created', ''),
                    image_count=data.get('image_count', 0),
                    varying_dims=data.get('varying_dims', []),
                    thumbnail=data.get('thumbnail'),
                    description=data.get('description')
                )
            except json.JSONDecodeError:
                pass
        
        # Fallback: extract from title tag
        title_match = re.search(r'<title>(.*?)</title>', self.raw_html)
        title = title_match.group(1) if title_match else self.html_path.stem
        
        return GridMetadata(
            title=title,
            created='',
            image_count=0,
            varying_dims=[]
        )
    
    def _parse_images(self) -> List[GridImage]:
        """Extract image data from grid data array."""
        match = self.GRID_DATA_PATTERN.search(self.raw_html)
        
        if not match:
            return []
        
        try:
            json_str = match.group(1)
            data = json.loads(json_str)
            
            images = []
            for idx, item in enumerate(data):
                # Extract image data
                image_data = None
                image_path = None
                
                if isinstance(item.get('image'), str):
                    if item['image'].startswith('data:image'):
                        image_data = item['image']
                    else:
                        # External path
                        image_path = item['image']
                
                images.append(GridImage(
                    index=idx,
                    label=item.get('label', ''),
                    params=item.get('params', {}),
                    image_data=image_data,
                    image_path=image_path
                ))
            
            return images
        except (json.JSONDecodeError, KeyError, TypeError):
            return []
    
    def _parse_hierarchy(self) -> Tuple[List[str], List[str]]:
        """Extract row and column hierarchy information."""
        # Our current grids don't have explicit hierarchy - they're flat filterable grids
        # Return empty hierarchies for now
        # Future: Could infer hierarchy from varying_dims in metadata
        varying_dims_match = self.VARYING_DIMS_PATTERN.search(self.raw_html)
        
        if varying_dims_match:
            try:
                json_str = varying_dims_match.group(1)
                varying_dims = json.loads(json_str)
                # Use varying dimensions as potential hierarchy fields
                dim_names = list(varying_dims.keys())
                # For now, return empty - user can configure in editor
                return [], []
            except json.JSONDecodeError:
                pass
        
        return [], []
    
    def _parse_styling(self) -> Dict[str, Any]:
        """Extract styling configuration from CSS or data attributes."""
        styling = {
            'header_colors': ['#E8E8E8', '#D4D4D4', '#C0C0C0'],
            'border_width': 2,
            'gap_size': 4,
            'font_size': 32,
            'theme': 'dark'
        }
        
        # Try to extract from style tag
        style_match = self.STYLE_PATTERN.search(self.raw_html)
        if style_match:
            style_content = style_match.group(1)
            
            # Look for CSS variables
            if '--border-width' in style_content:
                border_match = re.search(r'--border-width:\s*(\d+)px', style_content)
                if border_match:
                    styling['border_width'] = int(border_match.group(1))
            
            if '--gap-size' in style_content:
                gap_match = re.search(r'--gap-size:\s*(\d+)px', style_content)
                if gap_match:
                    styling['gap_size'] = int(gap_match.group(1))
        
        return styling
    
    def get_varying_dimensions(self) -> Dict[str, List[Any]]:
        """
        Detect which parameters vary across images.
        
        Returns:
            Dictionary of field_name -> list of unique values
        """
        varying = {}
        
        # Ensure we have parsed config
        if not self._config:
            self.parse()
        
        if not self._config or not self._config.images:
            return varying
        
        # For each parameter in images
        all_params = {}
        for img in self._config.images:
            for key, value in img.params.items():
                if key not in all_params:
                    all_params[key] = set()
                # Normalize tuples to comparable format
                if isinstance(value, (list, tuple)):
                    all_params[key].add(tuple(value) if isinstance(value, list) else value)
                else:
                    all_params[key].add(value)
        
        # Keep only fields with variation
        for key, values in all_params.items():
            if len(values) > 1:
                # Convert back to list and sort
                value_list = list(values)
                try:
                    value_list.sort()
                except TypeError:
                    pass  # Can't sort mixed types
                varying[key] = value_list
        
        return varying
    
    def get_image_by_index(self, index: int) -> Optional[GridImage]:
        """Get a specific image by index."""
        for img in self.images:
            if img.index == index:
                return img
        return None
    
    def get_image_data(self, image: GridImage) -> Optional[bytes]:
        """
        Extract image bytes from either embedded data or external file.
        
        Returns:
            PIL Image or None if data not available
        """
        if image.image_data and image.image_data.startswith('data:image'):
            try:
                # Extract base64 part after comma
                base64_data = image.image_data.split(',', 1)[1]
                return base64.b64decode(base64_data)
            except Exception:
                return None
        
        elif image.image_path:
            # Try to load external file
            external_path = self.grid_dir / image.image_path
            if external_path.exists():
                with open(external_path, 'rb') as f:
                    return f.read()
        
        return None
    
    def get_varying_dimensions(self) -> Dict[str, List[Any]]:
        """
        Get fields that vary across images with their unique values.
        
        Returns:
            Dict mapping field names to sorted lists of unique values
        """
        config = self.parse() if not self._config else self._config
        
        if not config or not config.images:
            return {}
        
        from collections import defaultdict
        field_values = defaultdict(set)
        
        # Collect all unique values for each parameter
        for img in config.images:
            for key, value in img.params.items():
                # Skip internal fields
                if key.startswith('_'):
                    continue
                # Convert lists/tuples to strings for hashability
                if isinstance(value, (list, tuple)):
                    value = str(value)
                # Skip None values
                if value is not None:
                    field_values[key].add(str(value))
        
        # Only return fields that actually vary (more than 1 unique value)
        varying = {}
        for field, values in field_values.items():
            if len(values) > 1:
                varying[field] = sorted(list(values))
        
        return varying
    
    def export_config(self, config_path: str) -> None:
        """
        Export parsed configuration to JSON for later reuse.
        
        Args:
            config_path: Path to save configuration file
        """
        config = self.parse()
        
        config_dict = {
            'metadata': asdict(config.metadata),
            'row_hierarchy': config.row_hierarchy,
            'col_hierarchy': config.col_hierarchy,
            'depth': config.depth,
            'styling': config.styling,
            'image_count': len(config.images),
            'source_grid': str(self.html_path)
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2)


class GridConfigLoader:
    """Load and validate grid configurations."""
    
    @staticmethod
    def from_html(html_path: str) -> GridConfig:
        """Load configuration from HTML grid file."""
        parser = GridParser(html_path)
        return parser.parse()
    
    @staticmethod
    def from_json(json_path: str) -> Dict[str, Any]:
        """Load configuration from exported JSON."""
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def validate_hierarchy(row_hierarchy: List[str], col_hierarchy: List[str]) -> Tuple[bool, str]:
        """
        Validate that row and column hierarchies are valid.
        
        Returns:
            (is_valid, error_message)
        """
        # Check for duplicates
        combined = row_hierarchy + col_hierarchy
        if len(combined) != len(set(combined)):
            duplicates = [x for x in combined if combined.count(x) > 1]
            return False, f"Duplicate fields in hierarchy: {duplicates}"
        
        # Check depth
        depth = max(len(row_hierarchy), len(col_hierarchy))
        if depth > 5:
            return False, "Hierarchy depth exceeds maximum of 5 levels"
        
        if depth == 0:
            return False, "At least one field must be in row or column hierarchy"
        
        return True, ""
